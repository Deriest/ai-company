"""Attachment binary storage tests.

The app previously stored only attachment METADATA in the ``attachments`` table —
the binary was sent inline to the LLM and never persisted. This suite verifies the
new storage layer: binaries are written under ``DATA_DIR/attachments/<id>``, can be
read back, are removed on delete, and end up inside full backups (backup.py zips the
whole DATA_DIR, so ``attachments/`` is included automatically).
"""
import base64
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.config import settings
from backend.services.attachment_store import (
    attachment_path,
    save_attachment,
    read_attachment,
    delete_attachment,
    decode_data_url,
    derive_file_type,
)


def test_save_read_delete_lifecycle():
    """save_attachment writes a file, read_attachment returns it, delete removes it."""
    attachment_id = "0102030405060708090a0b0c0d0e0f10"  # hex-shaped uuid
    payload = b"\x89PNG\r\n\x1a\n binary payload \x00\xff"

    path = save_attachment(attachment_id, payload)
    assert path == attachment_path(attachment_id)
    assert path.is_file()
    assert path.parent == Path(settings.DATA_DIR) / "attachments"
    assert path.read_bytes() == payload

    assert read_attachment(attachment_id) == payload

    delete_attachment(attachment_id)
    assert read_attachment(attachment_id) is None

    # delete on a missing file is a no-op
    delete_attachment(attachment_id)


def test_read_missing_returns_none():
    assert read_attachment("00000000000000000000000000000000") is None


def test_decode_data_url():
    raw = b"hello attachment bytes"
    b64 = base64.b64encode(raw).decode()
    data_url = f"data:image/png;base64,{b64}"
    assert decode_data_url(data_url) == raw

    # empty / non-data-url / invalid base64 all return None (no crash)
    assert decode_data_url("") is None
    assert decode_data_url("not-a-data-url") is None
    assert decode_data_url("data:image/png;base64,!!!not-base64!!!") is None


def test_derive_file_type():
    assert derive_file_type("image/png", "a.png") == "images"
    assert derive_file_type("application/pdf", "a.pdf") == "pdf"
    assert derive_file_type("text/markdown", "a.md") == "markdown"
    assert derive_file_type("application/json", "a.json") == "json"
    assert derive_file_type("text/plain", "a.txt") == "text"
    assert derive_file_type("text/x-python", "a.py") == "code"
    assert derive_file_type("application/octet-stream", "blob.bin") == "binary"
    assert derive_file_type("", "") == "binary"


def test_attachment_path_rejects_traversal():
    with pytest.raises(ValueError):
        attachment_path("../../etc/passwd")
    with pytest.raises(ValueError):
        attachment_path("../secrets")
    with pytest.raises(ValueError):
        attachment_path("a/b")
    with pytest.raises(ValueError):
        attachment_path("")


# ── Backup includes attachments ─────────────────────────────────

def _ensure_fake_db(data_dir: Path) -> None:
    db_path = data_dir / "aic.db"
    if db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO app_meta VALUES ('marker', 'attachment-test')")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_backup_includes_attachment_binaries():
    """A full backup zip must contain DATA_DIR/attachments/<id> files."""
    from backend.main import app

    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    _ensure_fake_db(data_dir)

    # Ensure the backups dir starts clean for this test.
    backups_dir = data_dir / "backups"
    if backups_dir.exists():
        import shutil
        shutil.rmtree(backups_dir, ignore_errors=True)

    attachment_id = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    payload = b"att-binary-payload-for-backup"
    save_attachment(attachment_id, payload)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/backup/create")
        assert create.status_code == 200, create.text
        body = create.json()
        zip_path = data_dir / "backups" / body["filename"]
        assert zip_path.is_file()

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert f"attachments/{attachment_id}" in names
            assert zf.read(f"attachments/{attachment_id}") == payload
            # excluded dirs still absent
            assert not any(n.lower().startswith("cache/") for n in names)
            assert not any(n.startswith("logs/") for n in names)


# ── Renderer chat path persists the binary ─────────────────────

@pytest.mark.asyncio
async def test_chat_execute_persists_attachment_binary(tmp_path):
    """POST /chat/execute (the renderer's actual path) must persist the base64
    data URL as a file under DATA_DIR/attachments/ with a linked metadata row,
    even though no LLM provider is configured (the agent run errors out)."""
    from backend.main import app
    from sqlalchemy import text as sa_text
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import Conversation

    await init_db()

    async with AsyncSessionLocal() as db:
        conv = Conversation(id="attach-conv-1", title="Attachment Test")
        db.add(conv)
        await db.commit()

    raw = b"\x89PNG\r\n\x1a\nrenderer-image-bytes"
    data_url = f"data:image/png;base64,{base64.b64encode(raw).decode()}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": "attach-conv-1",
            "messages": [{"role": "user", "content": "What is in this image?"}],
            "worker_role": "thinker",
            "model_tier": "vision",
            "attachments": [{"name": "pic.png", "mime_type": "image/png", "data_url": data_url}],
        })
        assert resp.status_code == 200
        # SSE body may end with an error event (no LLM provider) — that is fine:
        # the attachment was persisted before the agent run started.

    # The metadata row exists and a binary file was written.
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(sa_text(
            "SELECT id, file_name, mime_type, file_size FROM attachments"
        ))).all()
        assert len(rows) == 1
        att_id, file_name, mime_type, file_size = rows[0]
        assert file_name == "pic.png"
        assert mime_type == "image/png"
        assert file_size == len(raw)

    path = attachment_path(att_id)
    assert path.is_file()
    assert path.read_bytes() == raw
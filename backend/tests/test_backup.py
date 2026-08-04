"""Full app-data backup/restore endpoint tests.

Follows the suite convention (conftest points AIC_DATA_DIR at a per-session temp
dir before ``backend.config`` is imported). Seeds a controlled data dir — a fake
``aic.db`` plus representative app files and excluded dirs (logs/, Cache/) —
then exercises ``POST /backup/create``, ``POST /backup/validate`` and
``GET /backup/list`` end to end with the async TestClient (same transport the
rest of the suite uses).
"""
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import settings


def _ensure_fake_db(data_dir: Path) -> None:
    """Create a valid SQLite aic.db if one does not already exist."""
    db_path = data_dir / "aic.db"
    if db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO app_meta VALUES ('marker', 'backup-test')")
        conn.commit()
    finally:
        conn.close()


def _seed_data_dir() -> Path:
    """Create representative app files in the session data dir; return data_dir."""
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    _ensure_fake_db(data_dir)
    (data_dir / "identity.json").write_text(json.dumps({"username": "admin"}))
    (data_dir / "engine_config.json").write_text(json.dumps({"provider_name": "test"}))
    (data_dir / "models_dev.json").write_text(json.dumps({"models": []}))

    for folder in ("plugins", "skills", "workspace", "tasks", "feedback"):
        (data_dir / folder).mkdir(parents=True, exist_ok=True)
    (data_dir / "plugins" / "plugin-info.json").write_text(json.dumps({"name": "p1"}))
    (data_dir / "skills" / "skill-info.json").write_text(json.dumps({"name": "s1"}))
    (data_dir / "workspace" / "notes.txt").write_text("project notes")
    (data_dir / "tasks" / "task-1.json").write_text(json.dumps({"id": "t1"}))
    (data_dir / "feedback" / "feedback-1.json").write_text(json.dumps({"ok": True}))

    # Excluded dirs — must never appear in the backup zip.
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs" / "app.log").write_text("should not be backed up")
    (data_dir / "Cache").mkdir(parents=True, exist_ok=True)
    (data_dir / "Cache" / "blobs.dat").write_text("cache junk")

    return data_dir


@pytest.fixture(autouse=True)
def _isolated_backups():
    """Ensure the backups dir starts clean for each test."""
    backups_dir = Path(settings.DATA_DIR) / "backups"
    if backups_dir.exists():
        import shutil
        shutil.rmtree(backups_dir, ignore_errors=True)
    yield


@pytest.mark.asyncio
async def test_backup_create_validate_list_end_to_end(tmp_path):
    """Create a full backup, verify its contents, validate it, and list it."""
    data_dir = _seed_data_dir()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/backup/create")
        assert create.status_code == 200, create.text
        body = create.json()
        assert "filename" in body and "size" in body and "created_at" in body
        assert body["filename"].startswith("aic-backup-") and body["filename"].endswith(".zip")
        assert body["size"] > 0

        # ── Zip exists on disk ────────────────────────────────────────
        zip_path = data_dir / "backups" / body["filename"]
        assert zip_path.is_file()
        assert zip_path.stat().st_size == body["size"]

        # ── Inspect zip contents ──────────────────────────────────────
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            manifest_raw = zf.read("backup-manifest.json")
            # aic.db snapshot present
            assert "aic.db" in names
            # representative app files present
            assert "identity.json" in names
            assert "engine_config.json" in names
            assert "models_dev.json" in names
            assert "plugins/plugin-info.json" in names
            assert "skills/skill-info.json" in names
            assert "workspace/notes.txt" in names
            assert "tasks/task-1.json" in names
            assert "feedback/feedback-1.json" in names
            # excluded content absent
            assert not any(n.startswith("logs/") for n in names)
            assert not any(n.lower().startswith("cache/") for n in names)
            assert not any(n.endswith((".db-wal", ".db-shm")) for n in names)

        manifest = json.loads(manifest_raw)
        assert manifest["app"] == "AIC-ADE"
        assert manifest["version"]
        assert manifest["created_at"]
        assert "aic.db" in manifest["data_dir"]

        # ── Validate ──────────────────────────────────────────────────
        validate = await ac.post("/backup/validate", json={"filename": body["filename"]})
        assert validate.status_code == 200, validate.text
        vbody = validate.json()
        assert vbody["valid"] is True
        assert vbody["version"] == manifest["version"]
        assert vbody["created_at"] == manifest["created_at"]
        assert vbody["entries"] > 0
        assert vbody["error"] is None

        # ── List ──────────────────────────────────────────────────────
        listing = await ac.get("/backup/list")
        assert listing.status_code == 200
        listed = listing.json()
        assert any(item["filename"] == body["filename"] for item in listed)
        listed_item = next(item for item in listed if item["filename"] == body["filename"])
        assert listed_item["size"] == body["size"]
        assert listed_item["created_at"]


@pytest.mark.asyncio
async def test_backup_validate_missing_and_invalid():
    """Unknown filenames 404 and path-traversal filenames are rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        missing = await ac.post("/backup/validate", json={"filename": "nope.zip"})
        assert missing.status_code == 404

        traversal = await ac.post(
            "/backup/validate", json={"filename": "../../etc/passwd.zip"}
        )
        assert traversal.status_code == 400


@pytest.mark.asyncio
async def test_backup_list_empty_and_after_create():
    """List is empty before any backup and reflects created backups."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        empty = await ac.get("/backup/list")
        assert empty.status_code == 200
        assert empty.json() == []

        _seed_data_dir()
        create = await ac.post("/backup/create")
        assert create.status_code == 200
        after = await ac.get("/backup/list")
        assert any(item["filename"] == create.json()["filename"] for item in after.json())
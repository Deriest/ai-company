"""/chat/execute discovery/clarify gate tests.

Regression: a vague task_request with no selected workspace used to spawn an
agent immediately, which then started writing files into an arbitrary location.
The gate emits a structured ``clarify`` SSE event and does NOT spawn the agent —
the sandbox workspace stays empty.
"""
import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.config import settings


@staticmethod
def _parse_sse(body: str) -> list[dict]:
    """Parse an SSE response body into a list of event payloads."""
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:].strip()))
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.asyncio
async def test_chat_execute_vague_request_emits_clarify_and_no_files():
    """POST /chat/execute with a vague task_request + no project must emit a
    ``clarify`` event, must NOT spawn the agent, and must leave the sandbox
    workspace empty."""
    from backend.main import app
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import Conversation

    await init_db()

    conv_id = "clarify-conv-1"
    async with AsyncSessionLocal() as db:
        db.add(Conversation(id=conv_id, title="Clarify Gate Test"))
        await db.commit()

    sandbox_dir = Path(settings.DATA_DIR) / "workspaces" / conv_id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
        assert resp.status_code == 200
        body = resp.text
        events = _parse_sse(body)

    # Must contain a clarify event with the structured shape.
    clarify_events = [e for e in events if e.get("type") == "clarify"]
    assert clarify_events, f"No clarify event in SSE:\n{body}"
    clarify = clarify_events[0]["data"]
    assert "reason" in clarify
    assert isinstance(clarify.get("questions"), list) and clarify["questions"]
    for q in clarify["questions"]:
        assert "id" in q and "question" in q and "options" in q

    # Must NOT proceed to agent execution (no 'executing' status / no done).
    statuses = [e.get("status") for e in events if e.get("type") == "status"]
    assert "executing" not in statuses
    assert not any(e.get("type") == "done" for e in events)

    # The assistant message must be finalized (not stuck in streaming).
    async with AsyncSessionLocal() as db:
        from storage.models import Message
        msgs = (await db.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "assistant",
            )
        )).scalars().all()
        assert msgs, "Expected a persisted assistant message"
        assert msgs[0].status == "completed"
        assert clarify["questions"][0]["question"] in str(msgs[0].content)

    # No file may be written to the sandbox workspace.
    assert sandbox_dir.exists(), "Sandbox dir should be created by resolution"
    files = [p for p in sandbox_dir.rglob("*") if p.is_file()]
    assert files == [], f"Sandbox workspace must stay empty, found: {files}"


@pytest.mark.asyncio
async def test_chat_execute_with_workspace_skips_clarify():
    """An explicit payload.workspace resolves the workspace, so a task_request
    with complete intake must NOT trigger the clarify gate (it proceeds to the
    agent path when a provider is absent; no clarify event is emitted)."""
    from backend.main import app
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import Conversation

    await init_db()

    conv_id = "clarify-conv-2"
    async with AsyncSessionLocal() as db:
        db.add(Conversation(id=conv_id, title="Clarify Gate Skip Test"))
        await db.commit()

    import tempfile
    ws = tempfile.mkdtemp(prefix="aic-ws-")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{
                "role": "user",
                "content": "buat website AICompany untuk banyak pengguna dengan fitur login, gallery, dan kontak",
            }],
            "worker_role": "backend",
            "workspace": ws,
        })
        assert resp.status_code == 200
        body = resp.text

    events = _parse_sse(body)
    clarify_events = [e for e in events if e.get("type") == "clarify"]
    assert clarify_events == [], f"Unexpected clarify event in SSE:\n{body}"
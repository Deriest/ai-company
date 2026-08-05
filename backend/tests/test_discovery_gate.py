"""DiscoveryEngine-powered clarify gate tests.

Verifies the "if not sure, run real discovery" behavior on /chat/execute:
- a vague task_request runs the real DiscoveryEngine and emits its clarification
  questions as a `clarify` SSE event, persisting the discovery session id
- a follow-up reply auto-continues the session (respond_to_clarification) and
  proceeds to the agent when readiness completes
- disabling discovery falls back to the static clarify questions
- DiscoveryEngine unit-level behavior (not-ready with questions / ready with brief)
"""
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.config import settings


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:].strip()))
            except json.JSONDecodeError:
                pass
    return events


async def _create_conv(app, conv_id: str, title: str):
    from backend.database.session import AsyncSessionLocal
    from storage.models import Conversation
    async with AsyncSessionLocal() as db:
        db.add(Conversation(id=conv_id, title=title))
        await db.commit()


# ── gate emits DiscoveryEngine questions + persists session id ──────

@pytest.mark.asyncio
async def test_vague_request_clarify_from_discovery():
    """A vague task_request runs the real DiscoveryEngine: the clarify event
    carries the engine's questions (id/question/options), the agent is NOT
    spawned, the sandbox stays empty, the assistant message is completed, and
    the discovery session id is persisted in the assistant meta."""
    from backend.main import app
    from backend.database.session import init_db
    from storage.models import Message

    await init_db()
    conv_id = "disc-gate-conv-1"
    await _create_conv(app, conv_id, "Discovery Gate Test")

    sandbox_dir = Path(settings.DATA_DIR) / "workspaces" / conv_id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)

    clarify_events = [e for e in events if e.get("type") == "clarify"]
    assert clarify_events, f"No clarify event in SSE:\n{resp.text}"
    clarify = clarify_events[0]["data"]
    assert "reason" in clarify
    assert isinstance(clarify.get("questions"), list) and clarify["questions"]
    for q in clarify["questions"]:
        assert "id" in q and "question" in q and "options" in q

    # No agent spawn.
    statuses = [e.get("status") for e in events if e.get("type") == "status"]
    assert "executing" not in statuses
    assert not any(e.get("type") == "done" for e in events)

    # Assistant finalized + discovery session id persisted.
    from backend.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
        )).scalars().all()
        assert msgs, "Expected a persisted assistant message"
        assert msgs[0].status == "completed"
        assert clarify["questions"][0]["question"] in str(msgs[0].content)
        assert (msgs[0].meta or {}).get("discovery_session_id"), "discovery_session_id must be persisted in assistant meta"

    # Sandbox stays empty.
    files = [p for p in sandbox_dir.rglob("*") if p.is_file()]
    assert files == [], f"Sandbox workspace must stay empty, found: {files}"


# ── auto-continuation ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clarify_then_answer_auto_continues(monkeypatch):
    """First vague request → clarify. Second detailed reply + workspace →
    the pending discovery session is auto-continued; when readiness completes
    there is NO second clarify event and the agent path starts."""
    from backend.main import app
    from backend.database.session import init_db
    from backend.database.session import AsyncSessionLocal
    from storage.models import Message
    from discovery.config import discovery_config

    await init_db()
    conv_id = "disc-gate-conv-2"
    await _create_conv(app, conv_id, "Discovery Gate Auto Continue")

    # Round 1: vague request → clarify
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
        assert resp1.status_code == 200
        events1 = _parse_sse(resp1.text)
    assert [e for e in events1 if e.get("type") == "clarify"], resp1.text

    async with AsyncSessionLocal() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
        )).scalars().all()
        assert (msgs[0].meta or {}).get("discovery_session_id")

    # Round 2: detailed reply + workspace, permissive readiness so the reply
    # completes the discovery session.
    monkeypatch.setattr(discovery_config, "readiness_threshold", 0.1)
    monkeypatch.setattr(discovery_config, "dimension_floor", 0.0)
    ws = tempfile.mkdtemp(prefix="aic-ws2-")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp2 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": (
                "untuk restoran Italia, dengan fitur menu, galeri foto, kontak dan "
                "booking meja, untuk pelanggan, dengan halaman utama dan halaman menu"
            )}],
            "worker_role": "backend",
            "workspace": ws,
        })
        assert resp2.status_code == 200
        events2 = _parse_sse(resp2.text)

    clarify2 = [e for e in events2 if e.get("type") == "clarify"]
    assert clarify2 == [], f"Unexpected clarify on auto-continue:\n{resp2.text}"
    statuses = [e.get("status") for e in events2 if e.get("type") == "status"]
    assert "executing" in statuses or any(e.get("type") == "done" for e in events2), \
        f"expected agent to start, events: {events2}"

    # The pending discovery marker is cleared so it cannot re-trigger.
    async with AsyncSessionLocal() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
        )).scalars().all()
        past_metas = [dict(m.meta or {}) for m in msgs if (m.meta or {}).get("discovery_session_id")]
        assert past_metas == [], "pending discovery meta should be cleared after readiness"


# ── disabled discovery → static fallback ────────────────────────────

@pytest.mark.asyncio
async def test_discovery_disabled_static_fallback(monkeypatch):
    """When discovery is disabled, the gate falls back to the static clarify
    questions (including the workspace question when the workspace is
    unresolved) instead of crashing the stream."""
    from backend.main import app
    from backend.database.session import init_db
    from discovery.config import discovery_config

    await init_db()
    monkeypatch.setattr(discovery_config, "enabled", False)
    conv_id = "disc-gate-conv-3"
    await _create_conv(app, conv_id, "Discovery Disabled")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)

    clarify_events = [e for e in events if e.get("type") == "clarify"]
    assert clarify_events, f"No clarify event in SSE:\n{resp.text}"
    questions = clarify_events[0]["data"]["questions"]
    assert any(q["id"] == "workspace" for q in questions), \
        f"static fallback must include the workspace question: {questions}"


# ── DiscoveryEngine unit checks ─────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_vague_not_ready_with_questions(db_session):
    from discovery.engine import DiscoveryEngine
    from storage.models import Conversation

    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        result = await DiscoveryEngine(session).discover(
            conversation=conv, content="buat website AICompany", history=[]
        )
        assert result.is_ready is False
        assert result.clarification is not None
        assert result.clarification.questions
        assert result.metadata.get("session_id")


@pytest.mark.asyncio
async def test_discover_detailed_reaches_ready(monkeypatch, db_session):
    from discovery.config import discovery_config
    from discovery.engine import DiscoveryEngine
    from storage.models import Conversation

    monkeypatch.setattr(discovery_config, "readiness_threshold", 0.1)
    monkeypatch.setattr(discovery_config, "dimension_floor", 0.0)

    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        result = await DiscoveryEngine(session).discover(
            conversation=conv,
            content="Add a created_at timestamp column to the users table in PostgreSQL",
            history=[],
        )
        assert result.is_ready is True
        assert result.brief is not None
        assert result.metadata.get("brief_id")


# ── HIGH: non-task reply never spawns the agent ─────────────────────────

@pytest.mark.asyncio
async def test_clarify_reply_hi_never_spawns_agent():
    """A chit-chat reply ("hi") to a pending clarification must NOT spawn the
    agent — the stream re-emits clarification (or a nudge) instead."""
    from backend.main import app
    from backend.database.session import init_db

    await init_db()
    conv_id = "disc-gate-hi-conv"
    await _create_conv(app, conv_id, "Hi reply")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
    assert resp1.status_code == 200
    events1 = _parse_sse(resp1.text)
    assert [e for e in events1 if e.get("type") == "clarify"], resp1.text

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp2 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hi"}],
            "worker_role": "backend",
        })
        assert resp2.status_code == 200
        events2 = _parse_sse(resp2.text)

    # No agent spawn on "hi".
    statuses = [e.get("status") for e in events2 if e.get("type") == "status"]
    assert "executing" not in statuses
    assert not any(e.get("type") == "done" for e in events2)
    # A clarify (either re-asked questions or the nudge) is emitted.
    assert [e for e in events2 if e.get("type") == "clarify"], \
        f"expected clarify/nudge on 'hi', events: {events2}"


@pytest.mark.asyncio
async def test_aborted_session_nudges_without_agent(monkeypatch):
    """When the discovery session is aborted by a non-task reply (is_ready=False,
    no questions, terminal state), the auto-continuation must emit the nudge and
    return WITHOUT spawning the agent."""
    from backend.main import app
    from backend.database.session import init_db
    from backend.database.session import AsyncSessionLocal
    from discovery.engine import DiscoveryResult
    from storage.models import Message
    from sqlalchemy import select

    await init_db()
    conv_id = "disc-gate-abort-conv"
    await _create_conv(app, conv_id, "Abort reply")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
    assert resp1.status_code == 200
    assert [e for e in _parse_sse(resp1.text) if e.get("type") == "clarify"]

    # Make the auto-continuation hit the aborted path.
    async def _fake_abort(session_id, response, history=None):
        return DiscoveryResult(
            state="aborted",
            is_ready=False,
            clarification=None,
            message="Not a task request (intent: chat)",
        )

    monkeypatch.setattr("backend.api.routes.chat._respond_to_clarification", _fake_abort)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp2 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hi"}],
            "worker_role": "backend",
        })
        assert resp2.status_code == 200
        events2 = _parse_sse(resp2.text)

    statuses = [e.get("status") for e in events2 if e.get("type") == "status"]
    assert "executing" not in statuses
    assert not any(e.get("type") == "done" for e in events2)

    clarifies = [e for e in events2 if e.get("type") == "clarify"]
    assert clarifies, f"expected a nudge clarify, events: {events2}"
    from backend.api.routes.chat import _CLARIFY_NUDGE_TEXT
    assert _CLARIFY_NUDGE_TEXT in clarifies[-1]["data"]["reason"]

    # The assistant message is finalized with the nudge (never left streaming).
    async with AsyncSessionLocal() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
        )).scalars().all()
        assert msgs
        # msgs[-1] is the round-2 nudge; msgs[0] is the round-1 clarify.
        assert msgs[-1].status == "completed"
        assert _CLARIFY_NUDGE_TEXT in str(msgs[-1].content)


# ── MEDIUM: workspace answer with an absolute path ──────────────────────

@pytest.mark.asyncio
async def test_workspace_answer_pins_project_path(monkeypatch):
    """When the user answers the workspace question with an absolute path, a
    Project row is created (conversation.project_id set), the workspace resolves
    to that path, and there is NO second clarify — the request proceeds."""
    from backend.main import app
    from backend.database.session import init_db
    from backend.database.session import AsyncSessionLocal
    from storage.models import Conversation, Message, Project
    from discovery.config import discovery_config
    from sqlalchemy import select

    await init_db()
    conv_id = "disc-gate-ws-conv"
    await _create_conv(app, conv_id, "Workspace answer")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
    assert resp1.status_code == 200
    assert [e for e in _parse_sse(resp1.text) if e.get("type") == "clarify"]

    monkeypatch.setattr(discovery_config, "readiness_threshold", 0.1)
    monkeypatch.setattr(discovery_config, "dimension_floor", 0.0)
    ws_path = tempfile.mkdtemp(prefix="aic-ws-answer-")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp2 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": (
                f"buat website untuk restoran Italia dengan fitur menu, galeri foto, "
                f"kontak dan booking meja, untuk pelanggan, di {ws_path}"
            )}],
            "worker_role": "backend",
        })
        assert resp2.status_code == 200
        events2 = _parse_sse(resp2.text)

    # No second clarify — the workspace answer resolved the gate.
    assert [e for e in events2 if e.get("type") == "clarify"] == [], \
        f"unexpected second clarify: {events2}"

    # Conversation is linked to a Project pointing at the answered path.
    async with AsyncSessionLocal() as db:
        conv = await db.get(Conversation, conv_id)
        assert conv is not None and conv.project_id, "conversation.project_id must be set"
        proj = await db.get(Project, conv.project_id)
        assert proj is not None
        assert proj.repo_path == ws_path
        assert Path(ws_path).is_dir()


# ── MEDIUM: INTENT_TASK_CONFIRM must not bypass the gate ────────────────

@pytest.mark.asyncio
async def test_task_confirm_without_workspace_clarifies():
    """'yes / go ahead' with no pending discovery session and no workspace must
    emit the clarify gate (workspace/details) instead of spawning the agent on a
    bare confirmation."""
    from backend.main import app
    from backend.database.session import init_db

    await init_db()
    conv_id = "disc-gate-confirm-conv"
    await _create_conv(app, conv_id, "Confirm no workspace")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "yes go ahead"}],
            "worker_role": "backend",
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)

    clarifies = [e for e in events if e.get("type") == "clarify"]
    assert clarifies, f"expected a clarify gate for task_confirm without workspace: {events}"
    questions = clarifies[0]["data"]["questions"]
    assert any(q["id"] == "workspace" for q in questions), f"workspace question missing: {questions}"
    statuses = [e.get("status") for e in events if e.get("type") == "status"]
    assert "executing" not in statuses
    assert not any(e.get("type") == "done" for e in events)


@pytest.mark.asyncio
async def test_task_confirm_with_workspace_proceeds():
    """'yes go ahead' with a resolved workspace proceeds (no clarify gate)."""
    from backend.main import app
    from backend.database.session import init_db

    await init_db()
    conv_id = "disc-gate-confirm-ws-conv"
    await _create_conv(app, conv_id, "Confirm with workspace")
    ws = tempfile.mkdtemp(prefix="aic-ws-confirm-")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "yes go ahead"}],
            "worker_role": "backend",
            "workspace": ws,
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)

    assert [e for e in events if e.get("type") == "clarify"] == [], \
        f"unexpected clarify with workspace resolved: {events}"


# ── HIGH: race guard + idempotency ─────────────────────────────────────

@pytest.mark.asyncio
async def test_clarify_lock_get_release_cleanup():
    """The per-conversation lock is get-or-create and is cleaned up once free."""
    import backend.api.routes.chat as chat_mod
    from backend.api.routes.chat import _get_clarify_lock, _release_clarify_lock

    chat_mod._clarify_locks.clear()
    lock = _get_clarify_lock("race-lock-conv")
    assert _get_clarify_lock("race-lock-conv") is lock  # get-or-create returns the same
    assert not lock.locked()
    await lock.acquire()
    lock.release()
    _release_clarify_lock("race-lock-conv", lock)
    assert "race-lock-conv" not in chat_mod._clarify_locks  # cleaned up when free


@pytest.mark.asyncio
async def test_clarification_idempotency_helpers():
    """processed_message_ids round-trip: a consumed message id is skipped."""
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import DiscoverySession
    from discovery.states import DiscoveryState
    from backend.api.routes.chat import (
        _mark_clarification_processed, _clarification_message_processed,
    )

    await init_db()
    async with AsyncSessionLocal() as db:
        ds = DiscoverySession(
            conversation_id="disc-gate-idem-conv",
            status=DiscoveryState.CLARIFICATION.value,
            context={"original_content": "x"},
        )
        db.add(ds)
        await db.commit()
        ds_id = ds.id

    assert await _clarification_message_processed(ds_id, "msg-1") is False
    await _mark_clarification_processed(ds_id, "msg-1")
    assert await _clarification_message_processed(ds_id, "msg-1") is True
    assert await _clarification_message_processed(ds_id, "msg-2") is False


@pytest.mark.asyncio
async def test_concurrent_auto_continuation_serialized(monkeypatch):
    """Two concurrent /chat/execute replies to the same clarification must not
    both consume the session — the per-conversation lock + idempotency serialize
    them so respond_to_clarification runs exactly once."""
    import asyncio
    import backend.api.routes.chat as chat_mod
    from backend.main import app
    from backend.database.session import init_db
    from discovery.config import discovery_config
    from storage.models import Message
    from sqlalchemy import select

    await init_db()
    conv_id = "disc-gate-race-conv"
    await _create_conv(app, conv_id, "Race")

    # Round 1: create a real pending clarification session.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/chat/execute", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "buat website AICompany"}],
            "worker_role": "backend",
        })
    assert resp1.status_code == 200
    assert [e for e in _parse_sse(resp1.text) if e.get("type") == "clarify"]

    monkeypatch.setattr(discovery_config, "readiness_threshold", 0.1)
    monkeypatch.setattr(discovery_config, "dimension_floor", 0.0)

    calls = {"n": 0}
    orig_respond = chat_mod._respond_to_clarification

    async def counting_respond(session_id, response, history=None):
        calls["n"] += 1
        return await orig_respond(session_id, response, history)

    monkeypatch.setattr(chat_mod, "_respond_to_clarification", counting_respond)

    body = {
        "conversation_id": conv_id,
        "messages": [{"role": "user", "content": (
            "buat website untuk restoran Italia dengan fitur menu, galeri foto, "
            "kontak dan booking meja, untuk pelanggan"
        )}],
        "worker_role": "backend",
        "workspace": tempfile.mkdtemp(prefix="aic-ws-race-"),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = asyncio.create_task(ac.post("/chat/execute", json=body))
        r2 = asyncio.create_task(ac.post("/chat/execute", json=body))
        resp_a, resp_b = await asyncio.gather(r1, r2)

    assert resp_a.status_code == 200 and resp_b.status_code == 200
    assert calls["n"] == 1, (
        f"respond_to_clarification must run exactly once under the lock, "
        f"called {calls['n']} times"
    )


# ── M4: brief_id metadata matches persisted row ─────────────────────────

@pytest.mark.asyncio
async def test_brief_id_metadata_matches_persisted_row(monkeypatch, db_session):
    """result.metadata['brief_id'] must be the EngineeringBriefModel row id
    (assigned on flush), not the dataclass id."""
    from discovery.config import discovery_config
    from discovery.engine import DiscoveryEngine
    from storage.models import Conversation, EngineeringBrief
    from sqlalchemy import select

    monkeypatch.setattr(discovery_config, "readiness_threshold", 0.1)
    monkeypatch.setattr(discovery_config, "dimension_floor", 0.0)

    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        result = await DiscoveryEngine(session).discover(
            conversation=conv,
            content="Add a created_at timestamp column to the users table in PostgreSQL",
            history=[],
        )
        assert result.is_ready is True
        brief_id = result.metadata.get("brief_id")
        assert brief_id, "metadata.brief_id must be set"
        rows = (await session.execute(
            select(EngineeringBrief).where(
                EngineeringBrief.discovery_session_id == result.metadata["session_id"]
            )
        )).scalars().all()
        assert len(rows) == 1
        assert brief_id == rows[0].id, (
            f"brief_id {brief_id!r} must equal the persisted row id {rows[0].id!r}"
        )


# ── M6: QUICK tasks have approval_required=False ────────────────────────

@pytest.mark.asyncio
async def test_quick_task_has_no_approval_required(db_session):
    """A QUICK triage task must have approval_required=False (the old
    enum-vs-string comparison always returned True)."""
    from conversation.engine import ConversationEngine
    from storage.models import Conversation

    async with db_session() as session:
        conv = await session.get(Conversation, "conv-1")
        engine = ConversationEngine(session)
        task, _code = await engine._create_task(
            conv,
            "Fix typo in welcome message on the home page",
            "Fix typo in welcome message",
            "bugfix",
            "frontend",
        )
        assert task is not None
        assert task.approval_required is False


# ── M7: legacy /chat/stream tool workspace never uses cwd ───────────────

@pytest.mark.asyncio
async def test_chat_stream_tool_workspace_uses_project_repo_path(monkeypatch):
    """The legacy /chat/stream tool path must resolve the workspace from the
    conversation's project repo_path — never the process cwd."""
    import os
    from backend.main import app
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import Conversation, Project

    await init_db()
    conv_id = "tool-ws-conv-1"
    proj_path = tempfile.mkdtemp(prefix="aic-toolws-")
    async with AsyncSessionLocal() as db:
        proj = Project(name="ToolWS", slug="toolws-proj", repo_path=proj_path)
        db.add(proj)
        await db.flush()
        db.add(Conversation(id=conv_id, title="Tool WS", project_id=proj.id))
        await db.commit()

    captured = {}

    class _FakeToolService:
        def __init__(self, workspace_root="", worker_type=None, permission_checker=None):
            captured["workspace_root"] = workspace_root

        async def stream_with_tools(self, **kwargs):
            yield 'data: {"type": "done", "content": ""}\n\n'

    monkeypatch.setattr(
        "backend.services.tool_chat_service.ToolAwareChatService", _FakeToolService
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/chat/stream", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hello there"}],
            "worker_role": "backend",
        })
        assert resp.status_code == 200

    assert captured.get("workspace_root") == proj_path, (
        f"workspace_root must be the project repo_path, got {captured.get('workspace_root')!r}"
    )
    assert captured.get("workspace_root") != os.getcwd()
"""Hybrid (Option C) workspace resolution tests.

Verifies that resolve_conversation_workspace honors the priority:
conversation.project_id -> active profile project -> last_used_repo_path ->
per-conversation sandbox (is_resolved False).
"""
import os
import tempfile
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _ensure_backend_tables(db_session):
    """Create the backend Base tables (incl. local_profile) on the test engine.

    The db_session fixture only creates storage.Base tables; LocalProfile lives
    in backend.database.session.Base, so its table must be created explicitly.
    """
    import storage.database
    # Import the model so its table is registered on the backend Base metadata
    # BEFORE create_all runs (otherwise local_profile is not created).
    import backend.models.local_profile  # noqa: F401
    from backend.database.session import Base as BackendBase
    engine = storage.database.engine
    async with engine.begin() as conn:
        await conn.run_sync(BackendBase.metadata.create_all)
    yield


async def _make_conversation(session, project_id=None):
    from storage.models import Conversation
    conv = Conversation(
        id="ws-test-conv",
        title="WS Test",
        context={"status": "active"},
    )
    if project_id:
        conv.project_id = project_id
    session.add(conv)
    await session.flush()
    return conv


async def _make_project(session, repo_path=None, owner_id=None):
    from storage.models import Project
    proj = Project(
        id="ws-test-proj",
        slug="ws-test-proj",
        name="WS Test Project",
        repo_path=repo_path,
        owner_id=owner_id,
    )
    session.add(proj)
    await session.flush()
    return proj


async def _make_profile(session, active_project_id=None, last_used_repo_path=None):
    import uuid
    from backend.models.local_profile import LocalProfile
    prof = LocalProfile(
        id="ws-test-profile",
        display_name="tester",
        device_id=f"dev-{uuid.uuid4().hex[:12]}",
        active_project_id=active_project_id,
        last_used_repo_path=last_used_repo_path,
    )
    session.add(prof)
    await session.flush()
    return prof


async def test_explicit_payload_wins(db_session):
    from shared.workspace import resolve_conversation_workspace
    async with db_session() as s:
        ws, resolved = await resolve_conversation_workspace(s, "/explicit/path", "conv-x")
    assert ws == "/explicit/path"
    assert resolved is True


async def test_conversation_project_repo_path_wins(db_session):
    from storage.models import Conversation
    from shared.workspace import resolve_conversation_workspace
    async with db_session() as s:
        p = await _make_project(s, repo_path="/proj/a")
        await _make_profile(s, last_used_repo_path="/proj/last-used")  # should be lower priority
        await _make_conversation(s, project_id=p.id)
        await s.commit()
        ws, resolved = await resolve_conversation_workspace(s, None, "ws-test-conv")
    assert ws == "/proj/a"
    assert resolved is True


async def test_last_used_repo_path_fallback(db_session):
    """When no conversation.project_id / active project, use last_used_repo_path."""
    from shared.workspace import resolve_conversation_workspace
    folder = tempfile.mkdtemp(prefix="ws-hybrid-")
    async with db_session() as s:
        await _make_profile(s, last_used_repo_path=folder)
        await s.commit()
        ws, resolved = await resolve_conversation_workspace(s, None, "conv-noproj")
    assert ws == folder
    assert resolved is True


async def test_last_used_missing_dir_falls_to_sandbox(db_session):
    """A last_used_repo_path whose dir no longer exists must NOT be used."""
    from shared.workspace import resolve_conversation_workspace
    async with db_session() as s:
        await _make_profile(s, last_used_repo_path="/definitely/does/not/exist-xyz")
        await s.commit()
        ws, resolved = await resolve_conversation_workspace(s, None, "conv-noproj")
    assert resolved is False  # sandbox fallback
    assert "workspaces" in ws


async def test_no_project_no_last_used_sandbox(db_session):
    from shared.workspace import resolve_conversation_workspace
    async with db_session() as s:
        ws, resolved = await resolve_conversation_workspace(s, None, "conv-empty")
    assert resolved is False
    assert "workspaces" in ws


async def test_active_profile_project_used(db_session):
    from shared.workspace import resolve_conversation_workspace
    async with db_session() as s:
        p = await _make_project(s, repo_path="/proj/active")
        await _make_profile(s, active_project_id=p.id)
        await _make_conversation(s, project_id=None)
        await s.commit()
        ws, resolved = await resolve_conversation_workspace(s, None, "ws-test-conv")
    assert ws == "/proj/active"
    assert resolved is True

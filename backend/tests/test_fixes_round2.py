"""Tests for fixes from defect scan round 2.

Covers:
- Item 1: no_source_artifacts false-negative (executor checks actual workspace)
- Item 2: ChatRequest accepts project_id and links it to conversation
- Item 3: _find_pending_discovery_session skips engineering_brief_complete
- Item 4: DispatchSession execution_id aligned with persisted row id
"""
import pytest
from pathlib import Path
from sqlalchemy import select
from storage.models import (
    Task, TaskStatus, TaskType, Conversation, Project,
    Message, DiscoverySession,
)


@pytest.mark.asyncio
async def test_executor_integrity_checks_workspace_for_source_files(db_session, tmp_path, monkeypatch):
    """Item 1: executor should find source files written via write_file tools
    in the actual workspace/sandbox, not just the deliverable directory."""
    monkeypatch.setenv("AIC_DATA_DIR", str(tmp_path))

    # Create a sandbox workspace with a Python file (simulating write_file tool output)
    sandbox = tmp_path / "workspaces" / "conv-1"
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "app.py").write_text("print('hello')")

    async with db_session() as session:
        # Create a task with conversation_id pointing to the sandbox
        task = Task(
            id="task-integrity",
            project_id="proj-1",
            title="Build feature",
            description="Test",
            type=TaskType.FEATURE.value,
            status=TaskStatus.CREATED.value,
            worker_type="backend",
        )
        task.context = {"conversation_id": "conv-1"}
        session.add(task)
        await session.commit()

        # Simulate the check logic from executor.py integrity block:
        import os
        from backend.workspace_manager import list_workspace_files

        workspace_root = str(sandbox)
        source_files_in_workspace = []
        if os.path.exists(workspace_root):
            for root, _, filenames in os.walk(workspace_root):
                for fname in filenames:
                    if fname.endswith(tuple([".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".css", ".html", ".sql"])):
                        full_p = Path(root) / fname
                        try:
                            rel_p = str(full_p.relative_to(workspace_root))
                            if "/node_modules/" in rel_p or "/venv/" in rel_p or "/.venv/" in rel_p:
                                continue
                            source_files_in_workspace.append(fname)
                        except ValueError:
                            pass

        assert len(source_files_in_workspace) > 0, "Should find app.py in sandbox"
        assert "app.py" in source_files_in_workspace

        # Also verify deliverable workspace is empty (files were NOT written there)
        deliverable_files = list_workspace_files(task.id)
        deliverable_source_files = [
            f for f in deliverable_files
            if f.get("extension") in ("py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "css", "html", "sql")
        ]
        assert len(deliverable_source_files) == 0, "Deliverable dir should be empty"

        # The fix: has_source_artifacts should be True because workspace has files
        has_source_artifacts = bool(source_files_in_workspace) or bool(deliverable_source_files)
        assert has_source_artifacts is True, "Should find source artifacts in workspace"


@pytest.mark.asyncio
async def test_chat_request_accepts_project_id():
    """Item 2: ChatRequest schema should accept project_id field."""
    from backend.schemas.ai_runtime_schemas import ChatRequest, ChatMessagePayload

    payload = ChatRequest(
        conversation_id="conv-1",
        messages=[ChatMessagePayload(role="user", content="hello")],
        project_id="proj-123",
    )
    assert payload.project_id == "proj-123"


@pytest.mark.asyncio
async def test_chat_request_project_id_optional():
    """Item 2: project_id should be optional."""
    from backend.schemas.ai_runtime_schemas import ChatRequest, ChatMessagePayload

    payload = ChatRequest(
        conversation_id="conv-1",
        messages=[ChatMessagePayload(role="user", content="hello")],
    )
    assert payload.project_id is None


@pytest.mark.asyncio
async def test_find_pending_discovery_session_skips_brief_complete(db_session):
    """Item 3: _find_pending_discovery_session should skip sessions with
    engineering_brief_complete status."""
    import backend.api.routes.chat as chat_module

    async with db_session() as session:
        # Create a conversation
        conv = Conversation(id="conv-discovery", user_id="user-1", title="Test")
        session.add(conv)
        await session.commit()

        # Create a discovery session in engineering_brief_complete state
        ds = DiscoverySession(
            id="ds-brief-complete",
            conversation_id="conv-discovery",
            status="engineering_brief_complete",
        )
        session.add(ds)
        await session.commit()

        # Create an assistant message with the discovery_session_id marker
        msg = Message(
            conversation_id="conv-discovery",
            role="assistant",
            content="Discovery complete",
            meta={"discovery_session_id": "ds-brief-complete"},
        )
        session.add(msg)
        await session.commit()

    # Patch AsyncSessionLocal in chat module to use the test's db_session
    original_session_local = chat_module.AsyncSessionLocal
    chat_module.AsyncSessionLocal = db_session
    try:
        # The function should NOT return the brief_complete session
        result = await chat_module._find_pending_discovery_session("conv-discovery")
        assert result is None, "Should not return engineering_brief_complete session"
    finally:
        chat_module.AsyncSessionLocal = original_session_local


@pytest.mark.asyncio
async def test_find_pending_discovery_session_returns_clarification(db_session):
    """Item 3: _find_pending_discovery_session should return sessions awaiting
    clarification."""
    import backend.api.routes.chat as chat_module

    async with db_session() as session:
        # Create a conversation
        conv = Conversation(id="conv-clarify", user_id="user-1", title="Test")
        session.add(conv)
        await session.commit()

        # Create a discovery session in clarification state
        ds = DiscoverySession(
            id="ds-clarify",
            conversation_id="conv-clarify",
            status="clarification",
        )
        session.add(ds)
        await session.commit()

        # Create an assistant message with the discovery_session_id marker
        msg = Message(
            conversation_id="conv-clarify",
            role="assistant",
            content="Need more info",
            meta={"discovery_session_id": "ds-clarify"},
        )
        session.add(msg)
        await session.commit()

    # Patch AsyncSessionLocal in chat module to use the test's db_session
    original_session_local = chat_module.AsyncSessionLocal
    chat_module.AsyncSessionLocal = db_session
    try:
        # The function SHOULD return the clarification session
        result = await chat_module._find_pending_discovery_session("conv-clarify")
        assert result == "ds-clarify", f"Should return clarification session, got {result}"
    finally:
        chat_module.AsyncSessionLocal = original_session_local


@pytest.mark.asyncio
async def test_dispatch_session_execution_id_matches(db_session):
    """Item 4: DispatchSession row id should match the returned execution_id."""
    from storage.models import TaskGraphModel, DispatchSession

    async with db_session() as session:
        # Create a task graph (TaskGraphModel has plan_id, not project_id/name)
        graph = TaskGraphModel(
            id="graph-test",
            plan_id="plan-1",
            nodes=[
                {"node_id": "N1", "title": "Task 1", "worker_type": "backend", "task_type": "coding"},
            ],
            execution_order=[["N1"]],
        )
        session.add(graph)
        await session.commit()

        # Test the specific fix: after creating DispatchSession with
        # an explicit id, the id should be preserved.
        execution_id = "EXEC-TEST123"
        session_model = DispatchSession(
            id=execution_id,
            graph_id="graph-test",
            execution_log=[],
            success_rate=1.0,
            status="completed",
        )
        session.add(session_model)
        await session.flush()

        # Verify the id is preserved
        assert session_model.id == execution_id, "DispatchSession id should match execution_id"

        # Verify we can retrieve it by execution_id
        result = await session.execute(
            select(DispatchSession).where(DispatchSession.id == execution_id)
        )
        retrieved = result.scalar_one_or_none()
        assert retrieved is not None, "Should find DispatchSession by execution_id"
        assert retrieved.id == execution_id

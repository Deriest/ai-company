"""Per-role artifact workflow tests.

Covers:
- qa (TestingWorker): writes docs/QA_REPORT.md; keeps shell; cannot write src/x.py
- rex (GovernorWorker): writes docs/COMPLIANCE.md; cannot shell
- PRD materialization from EngineeringBrief
- Updated basenames in _validate_doc_path pass validation
"""
import os
import pytest

from workers.tools import ToolExecutor
from backend.services.tool_permissions import check_tool_permission, clear_cache


@pytest.fixture(autouse=True)
def fresh_perms():
    """Clear permission cache before each test."""
    clear_cache()
    yield


# ── QA TestingWorker artifact writing ────────────────────────────────────────


def test_qa_role_allows_write_file_and_shell():
    """qa allows both write_file AND shell."""
    assert check_tool_permission("qa", "write_file") is True
    assert check_tool_permission("qa", "shell") is True
    assert check_tool_permission("qa", "read_file") is True


@pytest.mark.asyncio
async def test_qa_cannot_write_source_with_docs_scope(tmp_path):
    """qa cannot write source files when using docs-scoped ToolExecutor."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file("src/app.py", "print(1)")
    assert tc.status == "error"
    assert not (tmp_path / "src" / "app.py").exists()


@pytest.mark.asyncio
async def test_qa_can_write_qa_report_md(tmp_path):
    """qa can write docs/QA_REPORT.md via docs-scoped executor."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file("docs/QA_REPORT.md", "# QA Report")
    assert tc.status == "completed"
    assert (tmp_path / "docs" / "QA_REPORT.md").exists()


# ── Rex GovernorWorker artifact writing ─────────────────────────────────────


def test_rex_role_allows_write_file_deny_shell():
    """rex allows write_file but denies shell."""
    assert check_tool_permission("rex", "write_file") is True
    assert check_tool_permission("rex", "shell") is False
    assert check_tool_permission("rex", "read_file") is True


@pytest.mark.asyncio
async def test_rex_can_write_compliance_md(tmp_path):
    """rex can write docs/COMPLIANCE.md via docs-scoped executor."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file("docs/COMPLIANCE.md", "# Compliance")
    assert tc.status == "completed"
    assert (tmp_path / "docs" / "COMPLIANCE.md").exists()


# ── PRD Materialization ─────────────────────────────────────────────────────


class _MockBrief:
    """Mock EngineeringBrief object for testing."""
    def __init__(self, goal="Build a todo app", intent="Enable users to manage tasks"):
        self.engineering_goal = goal
        self.user_intent = intent
        self.request_category = "feature"
        self.scope = {"in_scope": ["CRUD"], "out_of_scope": []}
        self.functional_requirements = ["Add task", "Delete task"]
        self.non_functional_requirements = ["Fast response"]
        self.constraints = ["No auth required yet"]
        self.assumptions = ["Users have accounts"]
        self.dependencies = ["SQLite DB"]
        self.risks = ["Data loss"]
        self.acceptance_criteria = ["Task persists"]
        self.readiness_status = "ready"
        self.readiness_score = 0.85
        self.discovery_metadata = {}
        self.outstanding_unknowns = []
        import datetime
        self.updated_at = datetime.datetime.now(datetime.timezone.utc)


def test_brief_to_prd_renders_goal_and_requirements():
    """brief_to_prd renders goal + functional requirements from a brief object."""
    from backend.services.prd_writer import brief_to_prd
    brief = _MockBrief()
    content = brief_to_prd(brief)
    assert brief.engineering_goal in content
    assert "Build a todo app" in content
    assert brief.functional_requirements[0] in content


def test_materialize_prd_creates_file_in_workspace(tmp_path):
    """materialize_prd creates docs/PRD.md in the workspace directory."""
    from backend.services.prd_writer import materialize_prd
    brief = _MockBrief()
    path = materialize_prd(str(tmp_path), brief)
    assert path is not None
    assert path.endswith("docs/PRD.md")
    assert (tmp_path / "docs" / "PRD.md").exists()
    written = (tmp_path / "docs" / "PRD.md").read_text()
    assert "Build a todo app" in written
    assert "Functional Requirements" in written


def test_materialize_prd_idempotent_same_content(tmp_path):
    """Second call with identical brief returns same path (no rewrite needed)."""
    from backend.services.prd_writer import materialize_prd
    brief = _MockBrief()
    path1 = materialize_prd(str(tmp_path), brief)
    assert path1 is not None

    # Get the file mtime before second call
    mtime1 = os.path.getmtime(path1)

    # Second call with identical content should skip rewrite
    path2 = materialize_prd(str(tmp_path), brief)
    assert path2 == path1
    # File should NOT have been rewritten (mtime unchanged)
    mtime2 = os.path.getmtime(path2)
    assert mtime1 == mtime2


def test_materialize_prd_none_brief_returns_none(tmp_path):
    """Passing None brief returns None without error."""
    from backend.services.prd_writer import materialize_prd
    result = materialize_prd(str(tmp_path), None)
    assert result is None


# ── Extended Basenames Validation ───────────────────────────────────────────


@pytest.mark.parametrize("basename,ext", [
    ("QA_REPORT", ""),
    ("qa_report", ""),
    ("qa_report", ".md"),
    ("TEST_REPORT", ""),
    ("project_plan", ""),
    ("PROJECT_PLAN", ".md"),
    ("COMPLIANCE", ""),
    ("compliance", ".md"),
])
@pytest.mark.asyncio
async def test_valid_doc_basenames_accepted(tmp_path, basename, ext):
    """All valid doc basenames are accepted by _validate_doc_path."""
    path = f"{basename}{ext}"
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file(path, "content")
    assert tc.status == "completed", f"{path} should be writable"


@pytest.mark.parametrize("invalid_ext", [".py", ".ts", ".js", ".json", ".sql", ".yaml"])
@pytest.mark.asyncio
async def test_invalid_extensions_rejected_with_valid_names(tmp_path, invalid_ext):
    """Invalid extensions are rejected even with valid basenames."""
    for name in ("app", "main", "config"):
        path = f"{name}{invalid_ext}"
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file(path, "content")
        assert tc.status == "error", f"{path} should be rejected"


# ── Worker ToolExecutor Construction Verification ───────────────────────────


def test_testing_worker_constructs_docs_executor():
    """TestingWorker.execute constructs a ToolExecutor with write_scope='docs'."""
    import inspect
    from workers import base as wb
    src = inspect.getsource(wb.TestingWorker.execute)
    assert 'write_scope="docs"' in src or '"write_file"' in src


def test_governor_worker_constructs_docs_executor():
    """GovernorWorker.execute constructs a ToolExecutor with write_scope='docs'."""
    import inspect
    from workers import base as wb
    src = inspect.getsource(wb.GovernorWorker.execute)
    assert 'write_scope="docs"' in src
    assert '"write_file"' in src


def test_coders_still_full_scope():
    """Backend/frontend/coding workers keep full write access (no docs scope)."""
    import inspect
    from workers import base as wb
    for cls in (wb.BackendWorker, wb.FrontendWorker, wb.CodingWorker):
        src = inspect.getsource(cls.execute)
        assert 'write_scope="docs"' not in src, f"{cls.__name__} must not use docs scope"



# ── PRD DRAFT Status Marker ───────────────────────────────────────────────


def test_prd_draft_status_marker():
    """materialize_prd output contains the DRAFT status marker."""
    from backend.services.prd_writer import brief_to_prd
    
    class _MockBrief:
        engineering_goal = "Todo app"
        user_intent = "Manage tasks"
        request_category = "feature"
        scope = {"in_scope": [], "out_of_scope": []}
        functional_requirements = []
        non_functional_requirements = []
        constraints = []
        assumptions = []
        dependencies = []
        risks = []
        acceptance_criteria = []
        readiness_status = "ready"
        readiness_score = 0.85
        discovery_metadata = {}
        outstanding_unknowns = []
        import datetime
        updated_at = datetime.datetime.now(datetime.timezone.utc)
    
    brief = _MockBrief()
    content = brief_to_prd(brief)
    assert "> **Status: DRAFT**" in content
    assert "PM must review and finalize this PRD" in content


# ── PM Worker PRD Ownership Workflow ──────────────────────────────────────


def test_pm_system_prompt_prd_ownership():
    """PMWorker.SYSTEM_PROMPT mentions finalizing docs/PRD.md."""
    from workers.base import PMWorker
    prompt = PMWorker.SYSTEM_PROMPT
    assert "docs/PRD.md" in prompt
    assert "FINALIZE" in prompt or "finalized" in prompt.lower()
    assert "PROJECT_PLAN.md" in prompt


@pytest.mark.asyncio
async def test_pm_executor_docs_scoped(tmp_path):
    """PM worker ToolExecutor is docs-scoped: can write docs/* but not src/*."""
    from workers.tools import ToolExecutor
    # PM uses write_scope="docs" like other artifact writers
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    
    # Should be able to write docs files
    tc1 = await ex.write_file("docs/PRD.md", "# PRD")
    assert tc1.status == "completed"
    
    tc2 = await ex.write_file("docs/PROJECT_PLAN.md", "# Plan")
    assert tc2.status == "completed"
    
    # Should NOT be able to write source files
    tc3 = await ex.write_file("src/app.py", "print(1)")
    assert tc3.status == "error"
    assert not (tmp_path / "src" / "app.py").exists()


# ── QA Traceability Against PRD Acceptance Criteria ─────────────────────────


def test_qa_system_prompt_prd_traceability():
    """QA TestingWorker.SYSTEM_PROMPT references docs/PRD.md acceptance criteria."""
    from workers.base import TestingWorker
    prompt = TestingWorker.SYSTEM_PROMPT
    assert "docs/PRD.md" in prompt
    assert "acceptance criteria" in prompt.lower()


# ── Dispatcher PRD Materialization Tests ───────────────────────────────────


class TestDispatcherPRDMaterialization:
    """Tests for dispatcher's primary PRD materialization ownership."""

    @pytest.mark.asyncio
    async def test_dispatch_materializes_prd_with_brief(self, db_session, tmp_path, monkeypatch):
        """dispatch() with a linked brief -> docs/PRD.md exists in workspace;
        metadata["prd_path"] set; summary mentions the PRD."""
        import datetime as _dt
        from storage.models import (
            TaskGraphModel, EngineeringPlan, EngineeringBrief, DiscoverySession, Project,
        )
        from dispatcher.engine import DispatcherEngine

        async with db_session() as session:
            repo_path = str(tmp_path / "repo")
            project = Project(
                id="proj-prd", name="PRD Project", slug="prd-proj",
                description="t", repo_path=repo_path, owner_id="user-1",
            )
            ds = DiscoverySession(id="ds-prd", conversation_id="conv-1")
            brief = EngineeringBrief(
                id="brief-prd", discovery_session_id="ds-prd",
                engineering_goal="Build the PRD pipeline",
                user_intent="Dispatcher delivers PRD to workers",
                request_category="feature",
                scope={"in_scope": ["PRD"], "out_of_scope": []},
                functional_requirements=["FR-1: materialize PRD"],
                non_functional_requirements=[], constraints=[], assumptions=[],
                dependencies=[], risks=[], acceptance_criteria=["AC-1"],
                readiness_status="ready", readiness_score=0.9,
                discovery_metadata={}, outstanding_unknowns=[],
                updated_at=_dt.datetime.now(_dt.timezone.utc),
            )
            plan = EngineeringPlan(
                id="plan-prd", brief_id="brief-prd",
                engineering_goal="g", technical_approach="t",
                implementation_strategy="hybrid",
            )
            graph = TaskGraphModel(
                id="graph-prd", plan_id="plan-prd",
                nodes=[{"node_id": "N1", "title": "T1", "worker_type": "backend", "task_type": "coding"}],
                execution_order=[["N1"]],
            )
            session.add_all([project, ds, brief, plan, graph])
            await session.commit()

            engine = DispatcherEngine(session)

            # Avoid running the real FSM — stub node execution to success.
            async def _stub_node(node_data, execution_id_prefix, project_id, session=None):
                return {"success": True}
            monkeypatch.setattr(engine, "_execute_node_in_new_session", _stub_node)

            result = await engine.dispatch(graph.id, project_id="proj-prd")

            assert result.state != "error", f"dispatch failed: {result.message}"
            prd_path = result.metadata.get("prd_path")
            assert prd_path is not None, "metadata should include prd_path"
            assert prd_path.endswith("docs/PRD.md")

            # PRD file exists in the project workspace with DRAFT marker
            from pathlib import Path as _P
            prd_file = _P(repo_path) / "docs" / "PRD.md"
            assert prd_file.exists(), f"PRD.md should exist at {prd_file}"
            content = prd_file.read_text()
            assert "Status: DRAFT" in content
            assert "Build the PRD pipeline" in content

            # Dispatch summary mentions the PRD
            assert "PRD delivered to workers" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_without_brief_no_crash(self, db_session, tmp_path, monkeypatch):
        """dispatch() without a brief -> no crash, no PRD, execution proceeds."""
        from storage.models import TaskGraphModel, Project
        from dispatcher.engine import DispatcherEngine

        async with db_session() as session:
            project = Project(
                id="proj-nobrief", name="No Brief", slug="no-brief",
                description="t", repo_path=str(tmp_path / "repo2"), owner_id="user-1",
            )
            # Graph with NO plan/brief chain (plan_id points to nothing)
            graph = TaskGraphModel(
                id="graph-nobrief", plan_id="missing-plan",
                nodes=[{"node_id": "N1", "title": "T1", "worker_type": "backend", "task_type": "coding"}],
                execution_order=[["N1"]],
            )
            session.add_all([project, graph])
            await session.commit()

            engine = DispatcherEngine(session)

            async def _stub_node(node_data, execution_id_prefix, project_id, session=None):
                return {"success": True}
            monkeypatch.setattr(engine, "_execute_node_in_new_session", _stub_node)

            # Must not raise
            result = await engine.dispatch(graph.id, project_id="proj-nobrief")

            # Execution proceeds (state is complete, not an error)
            assert result.state != "error", f"dispatch should proceed without brief: {result.message}"
            # No PRD materialized
            assert result.metadata.get("prd_path") is None
            assert "PRD delivered to workers" not in result.message


# ── Dispatcher Persona & Conversation Reporting Tests ───────────────────────


def test_hermes_system_prompt_mentions_prd_creation_routing():
    """HermesWorker.SYSTEM_PROMPT mentions PRD creation, routing, and reporting to the user."""
    from workers.base import HermesWorker
    prompt = HermesWorker.SYSTEM_PROMPT

    assert "PRD" in prompt, "Should mention PRD creation"
    assert "route" in prompt.lower() or "dispatch" in prompt.lower(), "Should mention routing tasks"
    assert "report" in prompt.lower(), "Should mention reporting results to user"
    # The existing constraint must be preserved
    assert ("NEVER write source code" in prompt) or ("NEVER write code" in prompt),         "Should keep the never-write-code constraint"


@pytest.mark.asyncio
async def test_pipeline_completion_appends_assistant_message(db_session, monkeypatch):
    """Pipeline completion appends an assistant summary message to the conversation
    (success path). Uses a mocked run_engineering_pipeline result."""
    from storage.models import Task, Message, Conversation
    from sqlalchemy import select

    async with db_session() as session:
        task = Task(
            id="task-pipe-msg", project_id="proj-1", title="Pipeline Msg",
            description="d", type="feature", status="created", worker_type="coding",
            approval_required=False, progress=0,
            context={"source": "chat", "conversation_id": "conv-1"},
        )
        session.add(task)
        await session.commit()

    # Drive the background closure by invoking the engine's _launch_pipeline with a
    # mocked pipeline result.
    from conversation.engine import ConversationEngine
    import backend.services.master_orchestrator as mo_mod

    class _MockResult:
        success = True
        stage = "DISPATCH"
        task_id = "task-pipe-msg"
        brief_id = "b1"
        plan_id = "p1"
        graph_id = "g1"
        dispatch_id = "d1"
        message = "ok"
        error = ""

    async def _mock_pipeline(session, task):
        return _MockResult()

    monkeypatch.setattr(mo_mod, "run_engineering_pipeline", _mock_pipeline)

    async with db_session() as session:
        engine = ConversationEngine(session)
        task_obj = (await session.execute(
            select(Task).where(Task.id == "task-pipe-msg")
        )).scalar_one()
        await engine._launch_pipeline(task_obj)

    # _launch_pipeline schedules a background asyncio task; await it directly.
    import asyncio as _aio
    import conversation.engine as ce_mod
    bg_tasks = list(ce_mod._global_background_tasks)
    assert bg_tasks, "Background pipeline task should have been scheduled"
    await _aio.gather(*bg_tasks, return_exceptions=True)

    async with db_session() as session:
        msgs = (await session.execute(
            select(Message).where(
                Message.conversation_id == "conv-1",
                Message.role == "assistant",
            )
        )).scalars().all()
        report_msgs = [m for m in msgs if "Dispatcher Report" in (m.content or "")]
        assert report_msgs, "No dispatcher report message was appended to the conversation"
        content = report_msgs[-1].content
        assert "Dispatcher Report" in content
        assert "Pipeline Complete" in content


@pytest.mark.asyncio
async def test_pipeline_failure_appends_message(db_session, monkeypatch):
    """Pipeline FAILURE path also appends an assistant summary message."""
    from storage.models import Task, Message
    from sqlalchemy import select

    async with db_session() as session:
        task = Task(
            id="task-pipe-fail", project_id="proj-1", title="Pipeline Fail",
            description="d", type="feature", status="created", worker_type="coding",
            approval_required=False, progress=0,
            context={"source": "chat", "conversation_id": "conv-1"},
        )
        session.add(task)
        await session.commit()

    from conversation.engine import ConversationEngine
    import backend.services.master_orchestrator as mo_mod

    class _MockFailResult:
        success = False
        stage = "DISCOVERY"
        task_id = "task-pipe-fail"
        brief_id = ""
        plan_id = ""
        graph_id = ""
        dispatch_id = ""
        message = ""
        error = "DISCOVERY: discovery engine exploded"

    async def _mock_pipeline(session, task):
        return _MockFailResult()

    monkeypatch.setattr(mo_mod, "run_engineering_pipeline", _mock_pipeline)

    async with db_session() as session:
        engine = ConversationEngine(session)
        task_obj = (await session.execute(
            select(Task).where(Task.id == "task-pipe-fail")
        )).scalar_one()
        await engine._launch_pipeline(task_obj)

    import asyncio as _aio
    import conversation.engine as ce_mod
    bg_tasks = list(ce_mod._global_background_tasks)
    assert bg_tasks, "Background pipeline task should have been scheduled"
    await _aio.gather(*bg_tasks, return_exceptions=True)

    async with db_session() as session:
        msgs = (await session.execute(
            select(Message).where(
                Message.conversation_id == "conv-1",
                Message.role == "assistant",
            )
        )).scalars().all()
        fail_msgs = [m for m in msgs if "Pipeline Failed" in (m.content or "")]
        assert fail_msgs, "No failure report message was appended to the conversation"
        content = fail_msgs[-1].content
        assert "Pipeline Failed" in content
        assert "DISCOVERY" in content

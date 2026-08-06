"""Per-task-type workflow plans, bughunt classification, and Eve audit changes.

Covers:
- WORKFLOW_PLANS phases per task type
- skip_phases composition with level-based skips
- bughunt classification + audit team triage
- Eve docs-scoped write_file to BUG_REPORT.md
- Validation of bug_report basename
"""
import pytest
from pathlib import Path as _P

from workflow.triage import perform_smart_triage, ExecutionLevel, WORKFLOW_PLANS
from conversation.engine import TASK_PATTERNS
from workers.base import TestingWorker as EveWorker
from workers.tools import ToolExecutor
from backend.services.tool_permissions import check_tool_permission


# ── WORKFLOW_PLANS structure validation ───────────────────────────────────


class TestWorkflowPlansStructure:
    """Validate the WORKFLOW_PLANS mapping."""

    def test_workflows_cover_all_task_types(self):
        """All TaskType enum values should have a plan."""
        # "build" is an alias for "feature" (both map to the full lifecycle plan)
        expected_task_types = {"build", "feature", "bugfix", "bughunt", "refactor",
                               "docs", "infra", "test", "research"}
        assert set(WORKFLOW_PLANS.keys()) == expected_task_types

    def test_build_plan_all_phases(self):
        """build workflow includes all execution phases."""
        from workflow.fsm import EXECUTION_PHASES
        assert len(WORKFLOW_PLANS["build"]) == 6

    def test_bugfix_plan_no_discovery_or_closeout(self):
        """bugfix workflow excludes formal discovery/closeout."""
        assert "discovery" not in WORKFLOW_PLANS["bugfix"]
        assert "closeout" not in WORKFLOW_PLANS["bugfix"]
        assert "investigate" in WORKFLOW_PLANS["bugfix"]
        assert "implementation" in WORKFLOW_PLANS["bugfix"]
        assert "verification" in WORKFLOW_PLANS["bugfix"]

    def test_bughunt_plan_no_implementation(self):
        """bughunt is read-only — no implementation phase."""
        assert "investigate" in WORKFLOW_PLANS["bughunt"]
        assert "verification" in WORKFLOW_PLANS["bughunt"]
        assert "implementation" not in WORKFLOW_PLANS["bughunt"]
        assert "planning" not in WORKFLOW_PLANS["bughunt"]
        assert "discovery" not in WORKFLOW_PLANS["bughunt"]

    def test_test_only_verification(self):
        """test tasks run verification only."""
        assert len(WORKFLOW_PLANS["test"]) == 1
        assert WORKFLOW_PLANS["test"][0] == "verification"

    def test_docs_only_closeout(self):
        """docs tasks land in closeout only."""
        assert len(WORKFLOW_PLANS["docs"]) == 1
        assert WORKFLOW_PLANS["docs"][0] == "closeout"


# ── Skip-phase composition with levels ────────────────────────────────────


class TestSkipPhaseComposition:
    """verify skip_phases are composed correctly (level + plan)."""

    def test_full_feature_no_skips(self):
        """FULL-level feature/build retains all phases."""
        r = perform_smart_triage(
            "Build an entire platform from scratch",
            task_type="feature"
        )
        assert r.level == ExecutionLevel.FULL
        assert len(r.skip_phases) == 0

    def test_bugfix_quicks_impl_verification(self):
        """QUICK bugfix only runs implementation+verification."""
        r = perform_smart_triage(
            "Fix typo in docstring",
            task_type="bugfix"
        )
        assert r.level == ExecutionLevel.QUICK
        allowed = ["implementation", "verification"]
        for p in allowed:
            assert p not in r.skip_phases, f"{p} should NOT be skipped"
        for p in ["discovery", "investigate", "planning", "closeout"]:
            assert p in r.skip_phases, f"{p} should be skipped"

    def test_bugfix_standard_invest_impl_verify(self):
        """STANDARD bugfix runs investigate/implementation/verification."""
        r = perform_smart_triage(
            "Fix calculation error",
            task_type="bugfix"
        )
        assert r.level == ExecutionLevel.STANDARD
        allowed = ["investigate", "implementation", "verification"]
        for p in allowed:
            assert p not in r.skip_phases
        for p in ["discovery", "planning", "closeout"]:
            assert p in r.skip_phases

    def test_bughunt_only_investigate_verify(self):
        """BUGHUNT runs investigate + verification (no implementation)."""
        r = perform_smart_triage(
            "cari bug di project ini",
            task_type="bughunt"
        )
        assert r.level == ExecutionLevel.STANDARD
        allowed = ["investigate", "verification"]
        for p in allowed:
            assert p not in r.skip_phases, f"{p} should NOT be skipped"
        for p in ["discovery", "planning", "implementation", "closeout"]:
            assert p in r.skip_phases, f"{p} should be skipped"

    def test_test_only_verification(self):
        """test tasks skip everything except verification."""
        r = perform_smart_triage("write unit tests for utils", task_type="test")
        allowed = ["verification"]
        for p in allowed:
            assert p not in r.skip_phases
        for p in ["discovery", "investigate", "planning", "implementation", "closeout"]:
            assert p in r.skip_phases

    def test_docs_only_closeout(self):
        """docs tasks skip everything except closeout."""
        r = perform_smart_triage("update readme documentation", task_type="docs")
        allowed = ["closeout"]
        for p in allowed:
            assert p not in r.skip_phases
        for p in ["discovery", "investigate", "planning", "implementation", "verification"]:
            assert p in r.skip_phases


# ── bughunt Classification ─────────────────────────────────────────────────


class TestBugHuntClassification:
    """Test that buggy hunts are classified correctly by conversation patterns."""

    @pytest.mark.parametrize("content", [
        "cari bug di project ini",
        "find bugs in the payment module",
        "bug hunt please scan this repo",
        "audit kode dan cari bug",
        "scan for bugs",
        "carikan bug di aplikasi",
        "cari masalah dan bug",
        "bug audit on production",
    ])
    def test_bughunt_patterns_classify_to_qa(self, content):
        """These text fragments classify as bughunt/task_type qa."""
        from conversation.engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        task_type, worker = engine._classify_task(content)
        assert task_type == "bughunt", f"{content!r} should classify as bughunt"
        assert worker == "qa", f"{content!r} should pick qa worker"

    def test_fix_typo_still_bugfix_backend(self):
        """A fix typo message does NOT classify as bughunt."""
        from conversation.engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        task_type, worker = engine._classify_task("fix the typo in this file")
        assert task_type == "bugfix"
        assert worker == "backend"


class TestBugHuntTriage:
    """Verify bughunt task triage behavior."""

    def test_bughunt_forces_standard_level(self):
        """Bug hunt forces STANDARD execution level."""
        r = perform_smart_triage(
            "cari bug di project ini",
            task_type="bughunt"
        )
        assert r.level == ExecutionLevel.STANDARD

    def test_bughunt_audit_team_workers(self):
        """Bug hunt selected workers are research, security, and qa."""
        r = perform_smart_triage(
            "cari bug di project ini",
            task_type="bughunt"
        )
        audit_team = ["research", "security", "qa"]
        for w in audit_team:
            assert w in r.selected_workers, f"{w} missing from selected workers"

    def test_bughunt_approval_not_required(self):
        """Bughunt tasks do not require approval."""
        # Check at the classification layer (conversation/engine _classify_task LLm fallback path)
        from conversation.engine import ConversationEngine
        import asyncio
        async def dummy_llm_classification():
            return "bughunt", "qa", "Title", False
        # The actual code path is via _classify_task_llm -> _classify_task
        engine = ConversationEngine.__new__(ConversationEngine)
        task_type, worker = engine._classify_task("cari bug di project ini")
        approval_required = task_type not in ("test", "docs", "bughunt")
        assert approval_required is False, "bughunt should be approved exemption"


# ── Eve Documentation Artifact Writing ────────────────────────────────────


class TestEveAuditDocumentation:
    """Eve can write docs/BUG_REPORT.md (docs-scoped), cannot write src/x.py."""

    @pytest.mark.asyncio
    async def test_eve_writes_bug_report_md(self, tmp_path):
        """Eve's docs-scoped executor can write docs/BUG_REPORT.md."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file("docs/BUG_REPORT.md", "# Bug Report")
        assert tc.status == "completed", f"Expected completed, got {tc.error}"
        assert (_P(str(tmp_path)) / "docs" / "BUG_REPORT.md").exists()

    @pytest.mark.asyncio
    async def test_eve_cannot_write_source_files(self, tmp_path):
        """Eve cannot write source files despite having write_file permission."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file("src/app.py", "print('hello')")
        assert tc.status == "error", f"Expected error, got {tc.error[:100]}"
        assert "documentation artifacts" in tc.error.lower(), f"Should mention docs restriction: {tc.error}"
        assert not (_P(str(tmp_path)) / "src" / "app.py").exists()

    def test_system_prompt_mentions_bug_report_md(self):
        """Eve's SYSTEM_PROMPT mentions writing docs/BUG_REPORT.md."""
        prompt = EveWorker.SYSTEM_PROMPT
        assert "BUG_REPORT.md" in prompt or "bug report" in prompt.lower(),             f"System prompt should mention docs/BUG_REPORT.md or bug report: {prompt[:200]}"
        assert any(phr in prompt.lower() for phr in ("read_file", "read files", "reading files")),             "Prompt should reference reading files"


class TestBugHuntToolPermissions:
    """tool_permissions check for debugger: write_file allowed, shell allowed."""

    def test_debugger_allows_write_file(self):
        """debugger allows write_file (enforced docs-scoped by tool_executor)."""
        assert check_tool_permission("debugger", "write_file") is True

    def test_debugger_allows_shell(self):
        """debugger allows shell (for diagnostics/test execution only)."""
        assert check_tool_permission("debugger", "shell") is True

    def test_debugger_allowed_tools(self):
        """debugger has correct allowed tools."""
        from backend.services.tool_permissions import get_allowed_tools
        allowed = get_allowed_tools("debugger")
        assert allowed is not None
        assert "read_file" in allowed
        assert "search" in allowed
        assert "write_file" in allowed
        assert "shell" in allowed


# ── Basename Validation for bug_report ────────────────────────────────────


class TestBugReportBasenames:
    """Validate that bug_report basenames pass _validate_doc_path."""

    @pytest.mark.asyncio
    async def test_bug_report_basename_accepted(self, tmp_path):
        """bug_report without extension should be writable."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file("bug_report", "Summary of findings...")
        assert tc.status == "completed", f"Expected completed, got {tc.error}"

    @pytest.mark.asyncio
    async def test_bug_report_md_accepted(self, tmp_path):
        """BUG_REPORT.md with doc extension should be writable."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file("bug_report.md", "# Bug Report")
        assert tc.status == "completed", f"Expected completed, got {tc.error}"

    @pytest.mark.asyncio
    async def test_case_insensitive_bug_report_accepted(self, tmp_path):
        """Case-insensitive matching works."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        tc = await ex.write_file("Bug_Report.md", "# Bug Report")
        assert tc.status == "completed", f"Expected completed, got {tc.error}"

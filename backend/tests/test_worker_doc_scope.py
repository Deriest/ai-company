"""Tests for docs-scoped artifact writing (thinker workers).

Covers:
- ToolExecutor write_scope="docs" allows documentation paths only
- ToolExecutor write_scope="docs" rejects source code and traversal
- ToolExecutor write_scope="full" (coders) allows any path
- tool_permissions: docs-writer roles allow write_file, deny shell
- tool_permissions: coders allow both; rex/review/hermes deny both
"""
import os
import pytest

from workers.tools import ToolExecutor
from backend.services.tool_permissions import check_tool_permission, clear_cache


@pytest.fixture(autouse=True)
def fresh_permissions():
    """Clear the permission cache before each test."""
    clear_cache()
    yield


# ── Docs-scoped write_file: allowed documentation paths ──────────────────


@pytest.mark.asyncio
async def test_docs_scope_writes_prd_md(tmp_path):
    """A docs-scoped worker can write docs/PRD.md; the file is created."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file("docs/PRD.md", "# PRD\n\nGoals...")
    assert tc.status == "completed", f"expected completed, got {tc.status}: {tc.error}"
    assert (tmp_path / "docs" / "PRD.md").exists()
    assert (tmp_path / "docs" / "PRD.md").read_text() == "# PRD\n\nGoals..."


@pytest.mark.asyncio
async def test_docs_scope_writes_architecture_and_research(tmp_path):
    """A docs-scoped worker can write ARCHITECTURE.md and RESEARCH.md."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")

    tc1 = await ex.write_file("docs/ARCHITECTURE.md", "# Architecture")
    assert tc1.status == "completed"
    assert (tmp_path / "docs" / "ARCHITECTURE.md").exists()

    tc2 = await ex.write_file("docs/RESEARCH.md", "# Research")
    assert tc2.status == "completed"
    assert (tmp_path / "docs" / "RESEARCH.md").exists()


@pytest.mark.asyncio
async def test_docs_scope_writes_standard_doc_basenames(tmp_path):
    """README / LICENSE / CHANGELOG / DESIGN / PRD basenames are allowed."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    for name in ("README", "LICENSE", "CHANGELOG", "DESIGN", "PRD", "RESEARCH"):
        tc = await ex.write_file(name, f"# {name}")
        assert tc.status == "completed", f"{name} should be writable, got {tc.error}"
    # README.md variant also allowed
    tc = await ex.write_file("README.md", "# readme")
    assert tc.status == "completed"


@pytest.mark.asyncio
async def test_docs_scope_writes_txt_rst_adoc(tmp_path):
    """Other doc extensions (.txt/.rst/.adoc/.markdown) are allowed."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    for path in ("notes.txt", "guide.rst", "manual.adoc", "spec.markdown"):
        tc = await ex.write_file(path, "content")
        assert tc.status == "completed", f"{path} should be writable, got {tc.error}"


# ── Docs-scoped write_file: rejected source paths ────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_path", [
    "src/app.py",
    "index.html",
    "package.json",
    "main.ts",
    "styles.css",
    "schema.sql",
    "config.yaml",
    "run.sh",
])
async def test_docs_scope_rejects_source_files(tmp_path, bad_path):
    """A docs-scoped worker cannot write source code; file is NOT created."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file(bad_path, "print('hi')")
    assert tc.status == "error", f"{bad_path} should be rejected"
    assert "documentation artifacts" in (tc.error or "")
    # File must not exist anywhere in the workspace
    assert not (tmp_path / bad_path).exists(), f"{bad_path} must not be created"


@pytest.mark.asyncio
async def test_docs_scope_rejects_source_under_docs_dir(tmp_path):
    """Even under docs/, only documentation extensions are allowed."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file("docs/helper.py", "x = 1")
    assert tc.status == "error"
    assert not (tmp_path / "docs" / "helper.py").exists()


# ── Docs-scoped write_file: path traversal rejected ─────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("evil_path", [
    "../../etc/passwd",
    "foo/../../x.py",
    "../escape.md",
    "/etc/passwd",
])
async def test_docs_scope_rejects_traversal(tmp_path, evil_path):
    """Path traversal attempts are rejected before any write."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="docs")
    tc = await ex.write_file(evil_path, "payload")
    assert tc.status == "error", f"{evil_path} should be rejected"
    # Nothing escapes the workspace
    assert not (tmp_path.parent / "etc" / "passwd").exists()
    assert not (tmp_path.parent / "x.py").exists()
    assert not (tmp_path.parent / "escape.md").exists()


# ── Full-scope (coders): any path allowed ───────────────────────────────


@pytest.mark.asyncio
async def test_full_scope_coder_writes_source(tmp_path):
    """A coder (write_scope='full') can write src/app.py."""
    ex = ToolExecutor(workspace_root=str(tmp_path), write_scope="full")
    tc = await ex.write_file("src/app.py", "print('hello')")
    assert tc.status == "completed", f"got {tc.error}"
    assert (tmp_path / "src" / "app.py").exists()


@pytest.mark.asyncio
async def test_default_scope_is_full(tmp_path):
    """write_scope defaults to 'full' (backward-compatible)."""
    ex = ToolExecutor(workspace_root=str(tmp_path))
    tc = await ex.write_file("src/lib.py", "x = 1")
    assert tc.status == "completed"
    assert (tmp_path / "src" / "lib.py").exists()


# ── tool_permissions: docs-writer roles ──────────────────────────────────


@pytest.mark.parametrize("role", ["pm", "research", "architect", "designer",
                                  "security", "performance", "documentation"])
def test_docs_writer_roles_allow_write_deny_shell(role):
    """Docs-writer roles allow write_file but deny shell."""
    assert check_tool_permission(role, "write_file") is True, f"{role} should allow write_file"
    assert check_tool_permission(role, "shell") is False, f"{role} should deny shell"
    assert check_tool_permission(role, "read_file") is True, f"{role} should allow read_file"


@pytest.mark.parametrize("role", ["pm", "research", "architect", "designer"])
def test_artifact_roles_expose_write_file_not_shell(role):
    """pm/research/architect/designer expose write_file; shell not allowed."""
    from backend.services.tool_permissions import get_allowed_tools
    allowed = get_allowed_tools(role)
    assert allowed is not None
    assert "write_file" in allowed, f"{role} should expose write_file"
    assert "shell" not in allowed, f"{role} should not expose shell"


# ── tool_permissions: coders allow both ──────────────────────────────────


@pytest.mark.parametrize("role", ["backend", "frontend", "coding", "database"])
def test_coder_roles_allow_write_and_shell(role):
    """Coder roles allow both write_file and shell."""
    assert check_tool_permission(role, "write_file") is True
    assert check_tool_permission(role, "shell") is True


# ── tool_permissions: rex/hermes deny both ────────────────────────
# (review worker removed in round-6 audit)

def test_hermes_denies_write_and_shell():
    """hermes (router) denies both write_file and shell."""
    assert check_tool_permission("hermes", "write_file") is False, "hermes should deny write_file"
    assert check_tool_permission("hermes", "shell") is False, "hermes should deny shell"
    assert check_tool_permission("hermes", "read_file") is True, "hermes should allow read_file"


def test_rex_allows_docs_write_denies_shell():
    """rex (governor) is a docs-scoped writer: allows write_file (COMPLIANCE.md), denies shell."""
    assert check_tool_permission("rex", "write_file") is True, "rex should allow docs-scoped write_file"
    assert check_tool_permission("rex", "shell") is False, "rex should deny shell"
    assert check_tool_permission("rex", "read_file") is True, "rex should allow read_file"


# ── Worker ToolExecutor construction carries docs scope ──────────────────


def test_docs_writer_workers_construct_docs_scope_executor():
    """PM/research/architect/designer/security/performance/documentation
    workers construct their ToolExecutor with write_scope='docs' and expose
    write_file in allowed_tools."""
    import inspect
    from workers import base as workers_base

    docs_writer_classes = [
        workers_base.PMWorker,
        workers_base.ResearchWorker,
        workers_base.ArchitectWorker,
        workers_base.DesignerWorker,
        workers_base.SecurityWorker,
        workers_base.PerformanceWorker,
        workers_base.DocumentationWorker,
    ]
    for cls in docs_writer_classes:
        src = inspect.getsource(cls.execute)
        assert 'write_scope="docs"' in src, f"{cls.__name__}.execute must pass write_scope='docs'"
        assert '"write_file"' in src, f"{cls.__name__}.execute must expose write_file"


def test_rex_uses_docs_scoped_write():
    """GovernorWorker (rex) uses docs-scoped write_file for COMPLIANCE.md.
    (ReviewWorker removed in round-6 audit — QA handles code reviews.)"""
    import inspect
    from workers import base as workers_base

    src = inspect.getsource(workers_base.GovernorWorker.execute)
    # rex produces COMPLIANCE.md via write_file (docs-scoped only)
    assert '"write_file"' in src, "GovernorWorker exposes write_file (for COMPLIANCE.md)"
    assert 'write_scope="docs"' in src, "GovernorWorker uses docs scope (COMPLIANCE.md paths only)"
    # Verify shell is denied in allowed_tools list
    assert '"shell"' not in src, "GovernorWorker does not have shell access"


def test_coder_workers_use_full_scope():
    """Backend/frontend/coding workers keep full write access (no docs scope)."""
    import inspect
    from workers import base as workers_base

    for cls in (workers_base.BackendWorker, workers_base.FrontendWorker,
                workers_base.CodingWorker):
        src = inspect.getsource(cls.execute)
        assert 'write_scope="docs"' not in src, f"{cls.__name__} must not be docs-scoped"


# ── Eve owns QA + bug-hunt auditing ───────────────────────────────────────


def test_canonical_agent_count_stays_fifteen():
    """Debugger is consolidated into Eve; canonical agents remain fifteen."""
    from agents.registry import AGENT_REGISTRY
    assert len(AGENT_REGISTRY) == 15
    assert "debugger" not in AGENT_REGISTRY


def test_qa_get_model_config_sprinter_tier():
    """Eve remains the canonical QA + bug-hunt agent."""
    from agents.context_assembly import get_model_config
    cfg = get_model_config("qa")
    assert cfg["tier"] == "sprinter"


def test_qa_assemble_system_prompt_includes_bug_audit():
    """Eve's canonical prompt covers QA and structured bug audits."""
    from agents.context_assembly import assemble_system_prompt
    prompt = assemble_system_prompt(
        "qa",
        {"title": "Bug audit", "description": "Investigate errors"},
        "verification",
    )
    assert "BUG_REPORT.md" in prompt, "prompt should reference BUG_REPORT.md artifact"
    assert "QA_REPORT.md" in prompt
    assert "audit" in prompt.lower()


def test_debugger_alias_resolves_to_eve_worker():
    """The legacy debugger name remains an alias, not a sixteenth agent."""
    from workers.base import WORKER_REGISTRY, TestingWorker as EveWorker
    assert WORKER_REGISTRY["debugger"] is EveWorker


def test_qa_tools_include_write_file():
    """Eve's tool permissions include QA shell and docs-scoped writing."""
    from agents.registry import AGENT_REGISTRY
    qa = AGENT_REGISTRY["qa"]
    assert "write_file" in qa.tools.allowed
    assert "read_file" in qa.tools.allowed
    assert "search" in qa.tools.allowed
    assert "shell" in qa.tools.allowed


# ── Nexus template fix (round-6 audit finding 2) ─────────────────────────


def test_nexus_template_is_integration_specific():
    """DevOpsWorker (nexus persona) template outputs Integration Analysis, not DevOps/Docker."""
    import inspect
    from workers import base as workers_base

    src = inspect.getsource(workers_base.DevOpsWorker.execute)
    # Template must be integration-specific
    assert "Integration Analysis" in src, "template should be Integration Analysis"
    assert "Interfaces" in src, "template should include Interfaces section"
    assert "Contract Tests" in src, "template should include Contract Tests section"
    assert "Dependencies" in src, "template should include Dependencies section"
    # Must NOT have the old DevOps/Docker content
    assert "DevOps Report" not in src, "should not use old DevOps Report header"
    assert "CI/CD" not in src, "should not have flint's CI/CD content"


# ── Documentation tier upgrade (round-6 audit finding 4) ─────────────────


def test_documentation_tier_is_crafter():
    """DocumentationWorker uses crafter tier (not sprinter)."""
    from agents.registry import AGENT_REGISTRY
    from agents.context_assembly import get_model_config

    doc = AGENT_REGISTRY["documentation"]
    assert doc.identity.tier == "crafter", f"documentation identity tier should be crafter, got {doc.identity.tier}"
    cfg = get_model_config("documentation")
    assert cfg["tier"] == "crafter", f"documentation model tier should be crafter, got {cfg['tier']}"


# ── Architect reads RESEARCH.md (round-6 audit finding 5) ─────────────────


def test_architect_prompt_reads_research_md():
    """Architect system_prompt mentions reading docs/RESEARCH.md."""
    from agents.registry import AGENT_REGISTRY
    architect = AGENT_REGISTRY["architect"]
    assert "RESEARCH.md" in architect.soul.system_prompt, "architect prompt should reference RESEARCH.md"
    assert "evidence-backed trade-offs" in architect.soul.system_prompt or "research findings" in architect.soul.system_prompt


# ── QA determinism honesty (round-6 audit finding 6) ─────────────────────


def test_qa_soul_states_deterministic_verification():
    """QA soul documents deterministic verification, not LLM code review."""
    from agents.registry import AGENT_REGISTRY
    qa = AGENT_REGISTRY["qa"]
    assert "DETERMINISTIC" in qa.soul.core_purpose.upper() or "deterministic" in qa.soul.core_purpose.lower(), \
        "qa core_purpose should mention deterministic verification"
    assert "pytest" in qa.soul.system_prompt or "npm" in qa.soul.system_prompt, \
        "qa system_prompt should reference actual test runners"
    assert "QA_REPORT.md" in qa.soul.system_prompt, "qa system_prompt should reference QA_REPORT.md"


# ── Alias docstrings (round-6 audit finding 7) ───────────────────────────


def test_devops_worker_docstring_notes_nexus_alias():
    """DevOpsWorker docstring clarifies devops alias resolves to nexus persona."""
    from workers.base import DevOpsWorker
    assert "devops" in DevOpsWorker.__doc__.lower() or "nexus" in DevOpsWorker.__doc__.lower(), \
        "DevOpsWorker docstring should mention devops/nexus alias"


def test_deployment_worker_docstring_notes_flint_alias():
    """DeploymentWorker docstring clarifies deployment alias resolves to flint persona."""
    from workers.base import DeploymentWorker
    assert "deployment" in DeploymentWorker.__doc__.lower() or "flint" in DeploymentWorker.__doc__.lower(), \
        "DeploymentWorker docstring should mention deployment/flint alias"

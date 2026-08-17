"""Unit tests for WorkerToolExecutor path safety and tool permissions."""
import os
import pytest

from backend.services.tool_executor import (
    WorkerToolExecutor,
    check_permission,
    get_tools_for_worker,
    DEFAULT_MINIMAL_TOOLS,
    WORKER_PERMISSIONS,
)


@pytest.mark.asyncio
async def test_resolve_path_blocks_traversal(tmp_path):
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    with pytest.raises(ValueError):
        executor._resolve_path("../escape.txt")
    with pytest.raises(ValueError):
        executor._resolve_path("a/../../escape.txt")
    with pytest.raises(ValueError):
        executor._resolve_path("/etc/passwd")
    with pytest.raises(ValueError):
        executor._resolve_path(os.path.join(str(tmp_path.parent), "outside.txt"))


@pytest.mark.asyncio
async def test_resolve_path_allows_inside(tmp_path):
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    resolved = executor._resolve_path("sub/file.txt")
    assert resolved == os.path.join(str(tmp_path), "sub", "file.txt")
    assert resolved.startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_read_file_blocks_outside_workspace(tmp_path):
    victim = tmp_path.parent / "victim.txt"
    victim.write_text("secret")
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.read_file("../victim.txt")
    assert result.success is False
    assert "outside" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_write_file_blocks_traversal(tmp_path):
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.write_file("../../evil.txt", "pwned")
    assert result.success is False
    assert not (tmp_path.parent / "evil.txt").exists()


@pytest.mark.asyncio
async def test_check_permission_default_deny_unknown_worker():
    """Unknown worker types get the minimal read-only set, not full access."""
    assert check_permission("totally_unknown_worker", "run_shell") is False
    assert check_permission("totally_unknown_worker", "write_file") is False
    assert check_permission("totally_unknown_worker", "mcp_call") is False
    # Read-only tools remain available to unknown workers.
    assert check_permission("totally_unknown_worker", "read_file") is True
    assert check_permission("totally_unknown_worker", "list_directory") is True


@pytest.mark.asyncio
async def test_check_permission_known_worker():
    assert check_permission("crafter", "run_shell") is True
    assert check_permission("research", "run_shell") is False
    assert check_permission("research", "read_file") is True
    # mcp_* prefixed tools require mcp_call permission.
    assert check_permission("crafter", "mcp_my_tool") is True
    assert check_permission("research", "mcp_my_tool") is False


@pytest.mark.asyncio
async def test_check_permission_plugin_tools_auto_granted():
    assert check_permission("crafter", "plugin_cmd_scan", allowed_plugin_tools=["plugin_cmd_scan"]) is True
    assert check_permission("crafter", "plugin_cmd_scan", allowed_plugin_tools=[]) is False


@pytest.mark.asyncio
async def test_get_tools_for_worker_unknown_defaults_to_minimal():
    tools = get_tools_for_worker("nonexistent_worker")
    names = {t["function"]["name"] for t in tools}
    expected_names = {"read_file", "explore", "search", "git_status"}
    assert names == expected_names
    assert "run_shell" not in names
    assert "write_file" not in names


@pytest.mark.asyncio
async def test_get_tools_for_worker_full_access():
    tools = get_tools_for_worker("crafter")
    names = {t["function"]["name"] for t in tools}
    assert "run_shell" in names
    assert "write_file" in names
    assert "read_file" in names


@pytest.mark.asyncio
async def test_get_tools_for_worker_read_only():
    tools = get_tools_for_worker("research")
    names = {t["function"]["name"] for t in tools}
    assert "run_shell" not in names
    assert "read_file" in names


@pytest.mark.asyncio
async def test_known_workers_are_explicitly_enumerated():
    """Every worker in WORKER_PERMISSIONS maps to a real tool set."""
    assert set(WORKER_PERMISSIONS) == {
        "research", "pm", "designer", "review", "vision", "thinker", "planner",
        "reviewer", "documentation",
        "qa", "security", "performance", "sprinter", "crafter", "testing",
        "backend", "frontend", "coding", "fullstack", "architect", "database",
        "devops", "deployment", "hermes", "rex", "nexus", "flint", "debugger",
    }
    for worker, allowed in WORKER_PERMISSIONS.items():
        assert allowed, f"worker {worker} has an empty permission set"
        # Verify permissions are valid subsets of known role categories:
        # - Full-access (shell-capable workers)
        # - Docs-scoped writers (extend research with write_file_docs)
        # - Read-only governance (may have git_status or mcp_call)
        if "run_shell" in allowed:
            assert allowed <= WORKER_PERMISSIONS["crafter"], f"{worker} should be subset of full-access crafter"
        elif "write_file_docs" in allowed:
            assert allowed <= WORKER_PERMISSIONS["research"] | {"write_file_docs"}, f"{worker} docs-scoped should extend research with write_file_docs only"
        else:
            # Specialized read-only roles may have git_status and/or mcp_call
            allowed_with_special = WORKER_PERMISSIONS["research"] | {"git_status", "mcp_call"}
            assert allowed <= allowed_with_special, f"{worker} should be subset of research plus optional git_status/mcp_call"


# ── Registry permission-alignment regression (QA-verify) ──────────────────

def test_registry_agent_with_prohibited_shell_cannot_run_shell():
    """rex is a registry agent whose ToolPermissions prohibits 'shell'."""
    assert check_permission("rex", "run_shell") is False


def test_registry_docs_writer_roles_cannot_run_shell():
    """Docs-writer roles restrict shell by policy (registry + override)."""
    for worker in ("research", "pm", "architect", "designer", "security", "documentation"):
        assert check_permission(worker, "run_shell") is False


def test_registry_agent_with_allowed_tools_can_execute_them():
    """backend is a registry agent that explicitly allows shell + write_file."""
    assert check_permission("backend", "run_shell") is True
    assert check_permission("backend", "write_file") is True
    assert check_permission("backend", "read_file") is True


def test_registry_allowed_tools_survive_get_tools_for_worker():
    """The allowed-tool list a worker gets honors the registry restriction."""
    rex_tools = {t["function"]["name"] for t in get_tools_for_worker("rex")}
    assert "run_shell" not in rex_tools
    assert "read_file" in rex_tools

    backend_tools = {t["function"]["name"] for t in get_tools_for_worker("backend")}
    assert "run_shell" in backend_tools
    assert "write_file" in backend_tools


def test_unknown_non_registry_worker_default_deny_read_only():
    """Unknown / non-registry workers get conservative read-only permissions."""
    assert check_permission("ghost_worker", "run_shell") is False
    assert check_permission("ghost_worker", "write_file") is False
    assert check_permission("ghost_worker", "mcp_call") is False
    # Read-only tools remain available.
    assert check_permission("ghost_worker", "read_file") is True
    assert check_permission("ghost_worker", "list_directory") is True


# ── MCP policy regression (QA-verify) ───────────────────────────────────────
#
# MCP POLICY: MCP servers/tools are external integrations the user explicitly
# configures, so ``mcp_call`` is auto-granted to shell-capable workers and
# denied to read-only / docs-only / governance agents. This is centralized in
# tool_executor._registry_allowed_tools: if a worker can run shell, it also
# gets mcp_call automatically.


def test_mcp_call_auto_granted_to_shell_capable_agents():
    """Shell-capable canonical agents get mcp_call + access to mcp_* tools."""
    shell_capable = ["backend", "frontend", "database", "qa", "nexus", "flint", "debugger"]
    for agent in shell_capable:
        assert check_permission(agent, "run_shell"), f"{agent} should have shell"
        assert check_permission(agent, "mcp_call"), f"{agent} should have mcp_call"
        assert check_permission(agent, "mcp_create_entities"), f"{agent} should call mcp_* tools"


def test_mcp_call_denied_to_read_only_governance_agents():
    """Read-only/governance/docs agents have NO shell AND NO mcp_call."""
    readonly_gov = ["hermes", "rex", "pm", "research", "architect", "designer",
                    "security", "performance", "documentation"]
    for agent in readonly_gov:
        assert not check_permission(agent, "run_shell"), f"{agent} should NOT have shell"
        assert not check_permission(agent, "mcp_call"), f"{agent} should NOT have mcp_call"
        assert not check_permission(agent, "mcp_create_entities"), f"{agent} cannot call mcp_* tools"


def test_get_tools_for_worker_includes_mcp_call_when_has_shell():
    """get_tools_for_worker returns mcp_call tool definition when shell present."""
    # Shell-capable -> includes mcp_call
    backend_tools = {t["function"]["name"] for t in get_tools_for_worker("backend")}
    assert "run_shell" in backend_tools
    assert "mcp_call" in backend_tools

    # Read-only -> no mcp_call
    research_tools = {t["function"]["name"] for t in get_tools_for_worker("research")}
    assert "run_shell" not in research_tools
    assert "mcp_call" not in research_tools


def test_mcp_policy_unified_registry_fallback():
    """MCP follows shell capability across registry agents AND legacy aliases."""
    # Legacy fallback aliases with full tools keep mcp_call.
    for alias in ["coding", "devops", "crafter"]:
        assert check_permission(alias, "mcp_call"), f"{alias} fallback should allow mcp"

    # Canonical registry agents follow the shell rule.
    assert check_permission("backend", "mcp_call")      # shell-capable canonical
    assert not check_permission("architect", "mcp_call")  # docs-writer canonical
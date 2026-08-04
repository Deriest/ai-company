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
    assert names == set(DEFAULT_MINIMAL_TOOLS)
    assert "run_shell" not in names


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
        assert allowed <= WORKER_PERMISSIONS["crafter"] or allowed <= WORKER_PERMISSIONS["research"]
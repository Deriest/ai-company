"""Unit tests for tool dispatcher."""
import pytest
import pytest_asyncio
import os
import tempfile


@pytest.fixture
def workspace(tmp_path):
    os.environ["AIC_DATA_DIR"] = str(tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_current_time(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    result = await dispatcher.execute("current_time", {})
    assert result["error"] is None
    assert "current_time" in result["result"]


@pytest.mark.asyncio
async def test_write_and_read_file(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    # Write
    result = await dispatcher.execute("write_file", {"path": "test.txt", "content": "hello world"})
    assert result["error"] is None
    assert result["result"]["bytes_written"] == 11
    # Read
    result = await dispatcher.execute("read_file", {"path": "test.txt"})
    assert result["error"] is None
    assert result["result"]["content"] == "hello world"


@pytest.mark.asyncio
async def test_read_nonexistent_file(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    result = await dispatcher.execute("read_file", {"path": "nonexistent.txt"})
    assert result["error"] is not None
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_list_directory(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    await dispatcher.execute("write_file", {"path": "a.txt", "content": "a"})
    await dispatcher.execute("write_file", {"path": "b.txt", "content": "b"})
    result = await dispatcher.execute("list_directory", {"path": "."})
    assert result["error"] is None
    names = [e["name"] for e in result["result"]["entries"]]
    assert "a.txt" in names
    assert "b.txt" in names


@pytest.mark.asyncio
async def test_search_workspace(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    await dispatcher.execute("write_file", {"path": "code.py", "content": "def hello(): pass"})
    result = await dispatcher.execute("search_workspace", {"query": "hello"})
    assert result["error"] is None
    assert "code.py" in result["result"]["matches"]


@pytest.mark.asyncio
async def test_path_traversal_blocked(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    result = await dispatcher.execute("read_file", {"path": "../../../etc/passwd"})
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_unknown_tool(workspace):
    from backend.services.tool_dispatcher import ToolDispatcher
    dispatcher = ToolDispatcher(str(workspace / "workspace"))
    result = await dispatcher.execute("nonexistent_tool", {})
    assert result["error"] is not None
    assert "unknown tool" in result["error"].lower()

"""Shell background-process / hang regression tests.

Covers the layered fix for the "agent runs `python -m http.server 8080 &` and
the task never finishes" bug:
- background commands are detached and return immediately (no pipe-hold hang)
- timeouts kill the whole process group (no orphaned children)
- the agent tool loop is bounded so a hanging tool cannot stall the generator
- port-in-use errors are surfaced explicitly
"""
import asyncio
import os
import shlex
import socket
import sys
from unittest.mock import patch

import pytest

from backend.services.tool_executor import WorkerToolExecutor


def _pid_alive(pid: int) -> bool:
    """True if the pid exists and is not a zombie (Linux /proc stat)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open(f"/proc/{pid}/stat") as f:
            parts = f.read().rsplit(")", 1)[-1].split()
            return len(parts) > 0 and parts[0].strip() != "Z"
    except (OSError, IndexError):
        return True


async def _wait_pidfile(pidfile, timeout: float = 3.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if pidfile.exists():
            return True
        await asyncio.sleep(0.05)
    return pidfile.exists()


# ── background commands return immediately ─────────────────────────

@pytest.mark.asyncio
async def test_run_shell_background_returns_immediately(tmp_path):
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    start = asyncio.get_event_loop().time()
    result = await executor.run_shell("sleep 0.2 & echo done", timeout=30)
    elapsed = asyncio.get_event_loop().time() - start

    assert result.success is True
    assert "background" in (result.output or "").lower()
    assert result.metadata.get("background") is True
    assert elapsed < 5, f"background command took {elapsed:.1f}s — hung on pipe"


@pytest.mark.asyncio
async def test_run_shell_background_short_lived_no_orphan(tmp_path):
    """A backgrounded short-lived child exits on its own and leaves no orphan."""
    pidfile = tmp_path / "bg.pid"
    code = f"import time,os;open({str(pidfile)!r},'w').write(str(os.getpid()));time.sleep(4)"
    cmd = f"{sys.executable} -c {shlex.quote(code)} &"

    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    start = asyncio.get_event_loop().time()
    result = await executor.run_shell(cmd, timeout=30)
    elapsed = asyncio.get_event_loop().time() - start
    assert result.success is True
    assert elapsed < 5, f"background command took {elapsed:.1f}s"

    assert await _wait_pidfile(pidfile), "background child never wrote its pidfile"
    pid = int(pidfile.read_text())

    # Child sleeps 4s then exits on its own; poll up to 8s for it to be gone.
    deadline = asyncio.get_event_loop().time() + 8
    while asyncio.get_event_loop().time() < deadline:
        if not _pid_alive(pid):
            break
        await asyncio.sleep(0.2)
    assert not _pid_alive(pid), f"orphaned background process {pid} still running"


# ── foreground commands keep normal behavior ────────────────────────

@pytest.mark.asyncio
async def test_run_shell_foreground_unchanged(tmp_path):
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.run_shell("echo hello", timeout=10)
    assert result.success is True
    assert "hello" in result.output
    assert result.metadata.get("background") is not True


@pytest.mark.asyncio
async def test_run_shell_does_not_detach_and_operator(tmp_path):
    """`&&` must keep foreground semantics (not be mistaken for a background `&`)."""
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.run_shell("echo a && echo b", timeout=10)
    assert result.success is True
    assert "a" in result.output and "b" in result.output


@pytest.mark.asyncio
async def test_run_shell_does_not_detach_redirect(tmp_path):
    """`2>&1` must keep foreground semantics."""
    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.run_shell("echo redirected 2>&1", timeout=10)
    assert result.success is True
    assert "redirected" in result.output


# ── timeout kills the whole process group (no orphan) ───────────────

@pytest.mark.asyncio
async def test_run_shell_timeout_kills_process_no_orphan(tmp_path):
    pidfile = tmp_path / "t.pid"
    code = f"import time,os;open({str(pidfile)!r},'w').write(str(os.getpid()));time.sleep(60)"
    cmd = f"{sys.executable} -c {shlex.quote(code)}"

    executor = WorkerToolExecutor(workspace_root=str(tmp_path))
    result = await executor.run_shell(cmd, timeout=2)

    assert result.success is False
    assert "timed out" in (result.error or "").lower()
    assert await _wait_pidfile(pidfile), "python never wrote its pidfile"
    pid = int(pidfile.read_text())

    # The process must actually be killed (process-group SIGKILL), not orphaned.
    deadline = asyncio.get_event_loop().time() + 3
    while asyncio.get_event_loop().time() < deadline:
        if not _pid_alive(pid):
            break
        await asyncio.sleep(0.1)
    assert not _pid_alive(pid), f"timed-out process {pid} still alive (orphan)"


# ── workers/tools.py ToolExecutor.shell path ────────────────────────

@pytest.mark.asyncio
async def test_tool_executor_shell_background_returns_immediately(tmp_path):
    from workers.tools import ToolExecutor

    ex = ToolExecutor(workspace_root=str(tmp_path), permission_checker=lambda tn: True)
    start = asyncio.get_event_loop().time()
    tc = await ex.shell("sleep 0.2 & echo done", timeout=30)
    elapsed = asyncio.get_event_loop().time() - start

    assert tc.status == "completed"
    assert "background" in (tc.output or "").lower()
    assert elapsed < 5, f"ToolExecutor.shell background took {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_tool_executor_shell_timeout_kills_process(tmp_path):
    from workers.tools import ToolExecutor

    pidfile = tmp_path / "t2.pid"
    code = f"import time,os;open({str(pidfile)!r},'w').write(str(os.getpid()));time.sleep(60)"
    cmd = f"{sys.executable} -c {shlex.quote(code)}"

    ex = ToolExecutor(workspace_root=str(tmp_path), permission_checker=lambda tn: True)
    tc = await ex.shell(cmd, timeout=2)

    assert tc.status == "error"
    assert "timed out" in (tc.error or "").lower()
    assert await _wait_pidfile(pidfile)
    pid = int(pidfile.read_text())
    deadline = asyncio.get_event_loop().time() + 3
    while asyncio.get_event_loop().time() < deadline:
        if not _pid_alive(pid):
            break
        await asyncio.sleep(0.1)
    assert not _pid_alive(pid), f"timed-out process {pid} still alive (orphan)"


# ── port-in-use surfacing ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_shell_surfaces_port_in_use(tmp_path):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.listen(1)
    try:
        executor = WorkerToolExecutor(workspace_root=str(tmp_path))
        code = f"import socket;s=socket.socket();s.bind(('127.0.0.1',{port}));s.listen(1)"
        cmd = f"{sys.executable} -c {shlex.quote(code)}"
        result = await executor.run_shell(cmd, timeout=15)
    finally:
        sock.close()

    assert result.success is False
    assert "already in use" in (result.error or "").lower(), result.error


# ── agent loop: a hanging tool cannot stall the generator ───────────

class _FakeConfig:
    def __init__(self):
        self.models = {
            "thinker": "test-thinker",
            "crafter": "test-crafter",
            "sprinter": "test-sprinter",
            "vision": "test-vision",
        }

    def get_model(self, tier):
        t = tier.value if hasattr(tier, "value") else str(tier)
        return self.models.get(t, "test-crafter")


class _FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.config = _FakeConfig()
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            return self._final_answer("done")
        return self.responses.pop(0)

    @staticmethod
    def _final_answer(content):
        return {
            "content": content,
            "raw": {"choices": [{"message": {"content": content, "tool_calls": []}}]},
        }

    @staticmethod
    def _tool_call(fn_name, arguments, call_id="call_1"):
        import json
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": fn_name, "arguments": json.dumps(arguments)},
        }

    @staticmethod
    def _response_with_tool_calls(tool_calls):
        return {
            "content": "",
            "raw": {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}]},
        }


async def _collect_events(runner, **kwargs):
    events = []
    async for event in runner.run_agent(**kwargs):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_run_agent_hanging_tool_does_not_stall(tmp_path, monkeypatch):
    """A tool that hangs forever must still produce a tool_result error and a
    done event within the bounded per-tool timeout."""
    import backend.services.agent_runner as ar_module
    from backend.services.agent_runner import AgentRunner

    monkeypatch.setattr(ar_module, "MAX_SHELL_TIMEOUT", 2)  # per-tool bound = 7s

    provider = _FakeProvider([
        _FakeProvider._response_with_tool_calls([
            _FakeProvider._tool_call("read_file", {"path": "x.txt"}, "call_1")
        ]),
    ])
    runner = AgentRunner(workspace_root=str(tmp_path))

    async def _hang(path="x.txt", offset=0, limit=-1, **kwargs):
        await asyncio.sleep(3600)

    runner.executor.read_file = _hang

    with patch("llm.provider.provider_manager.get_active_with_key", return_value=provider):
        events = await asyncio.wait_for(
            _collect_events(
                runner, worker_type="crafter", prompt="Read the file", model_tier="crafter"
            ),
            timeout=20,
        )

    types = [e["type"] for e in events]
    assert "done" in types, f"generator stalled — event types: {types}"
    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert tool_result["success"] is False
    assert "timed out" in (tool_result["error"] or "").lower()
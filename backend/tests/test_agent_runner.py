"""Unit tests for the AgentRunner tool loop (no real LLM calls).

These tests mock ``provider_manager.get_active_with_key`` and drive the
agent loop with canned tool_calls / final-answer responses.
"""
import asyncio
import pytest
from unittest.mock import patch

from backend.services.agent_runner import AgentRunner, _truncate_output, _format_tool_result


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
    """Canned responses; each call pops the next response from the queue."""

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
    def _final_answer(content: str) -> dict:
        return {
            "content": content,
            "raw": {"choices": [{"message": {"content": content, "tool_calls": []}}]},
        }

    @staticmethod
    def _tool_call(fn_name: str, arguments: dict, call_id: str = "call_1") -> dict:
        import json
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": fn_name, "arguments": json.dumps(arguments)},
        }

    @staticmethod
    def _response_with_tool_calls(tool_calls: list[dict]) -> dict:
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
async def test_run_agent_tool_loop(tmp_path):
    """A run_shell tool call is executed and its result fed back before done."""
    provider = _FakeProvider([
        _FakeProvider._response_with_tool_calls([
            _FakeProvider._tool_call("run_shell", {"command": "echo hello"}, "call_1")
        ]),
    ])
    runner = AgentRunner(workspace_root=str(tmp_path))

    with patch("llm.provider.provider_manager.get_active_with_key", return_value=provider):
        events = await _collect_events(
            runner,
            worker_type="crafter",
            prompt="List the files",
            model_tier="crafter",
        )

    types = [e["type"] for e in events]
    assert "tool_start" in types
    assert "tool_result" in types
    assert "done" in types

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert tool_result["tool"] == "run_shell"
    assert tool_result["success"] is True
    assert "hello" in tool_result["output"]

    done = next(e for e in events if e["type"] == "done")
    assert done["tool_results"][0]["tool"] == "run_shell"

    # The tool result must have been fed back to the LLM as a tool message.
    last_chat = provider.calls[-1]
    tool_messages = [m for m in last_chat["messages"] if m.get("role") == "tool"]
    assert tool_messages, "expected a tool message to be fed back to the LLM"
    assert "hello" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_run_agent_shell_failure_feedback(tmp_path):
    """A failing shell command surfaces output + exit code + error to the LLM."""
    provider = _FakeProvider([
        _FakeProvider._response_with_tool_calls([
            _FakeProvider._tool_call("run_shell", {"command": "exit 3"}, "call_1")
        ]),
    ])
    runner = AgentRunner(workspace_root=str(tmp_path))

    with patch("llm.provider.provider_manager.get_active_with_key", return_value=provider):
        events = await _collect_events(
            runner,
            worker_type="crafter",
            prompt="Run the failing command",
            model_tier="crafter",
        )

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert tool_result["success"] is False
    assert tool_result["metadata"]["exit_code"] == 3

    # Feedback for the LLM always includes the exit code.
    last_chat = provider.calls[-1]
    tool_messages = [m for m in last_chat["messages"] if m.get("role") == "tool"]
    assert tool_messages, "expected a tool message to be fed back to the LLM"
    assert "[exit 3]" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_run_agent_no_provider(tmp_path):
    """Without a configured provider the runner yields an error event."""
    runner = AgentRunner(workspace_root=str(tmp_path))
    with patch("llm.provider.provider_manager.get_active_with_key", return_value=None):
        events = await _collect_events(
            runner,
            worker_type="crafter",
            prompt="hello",
            model_tier="crafter",
        )
    assert events[0]["type"] == "error"
    assert "provider" in events[0]["error"].lower()


@pytest.mark.asyncio
async def test_run_agent_stuck_loop_detection(tmp_path):
    """Three identical tool calls emit a stuck-loop warning once."""
    same_call = _FakeProvider._tool_call("run_shell", {"command": "echo ste same"}, "call_1")
    provider = _FakeProvider([
        _FakeProvider._response_with_tool_calls([same_call]),
        _FakeProvider._response_with_tool_calls([same_call]),
        _FakeProvider._response_with_tool_calls([same_call]),
    ])
    runner = AgentRunner(workspace_root=str(tmp_path))

    with patch("llm.provider.provider_manager.get_active_with_key", return_value=provider):
        events = await _collect_events(
            runner,
            worker_type="crafter",
            prompt="repeat",
            model_tier="crafter",
        )

    warnings = [e for e in events if e["type"] == "warning"]
    assert len(warnings) == 1
    assert "looping" in warnings[0]["message"].lower()

    # The nudge is injected into the LLM context exactly once (the same
    # message persists across later calls, so it must appear once per call).
    for call in provider.calls:
        nudge_count = sum(
            1 for m in call["messages"]
            if m.get("role") == "system" and "You appear to be looping" in m.get("content", "")
        )
        assert nudge_count <= 1


def test_truncate_output_marker():
    """Long output is truncated with an explicit marker."""
    long_text = "x" * 6000
    truncated = _truncate_output(long_text)
    assert len(truncated) > 5000
    assert "truncated" in truncated
    assert "6000" in truncated

    short = _truncate_output("short")
    assert short == "short"


def test_format_tool_result_shell_failure():
    """Failed shell results include output, exit code and error."""
    from backend.services.tool_executor import ToolResult

    result = ToolResult(
        tool="run_shell",
        success=False,
        output="stdout-diagnostic",
        error="stderr-detail",
        metadata={"exit_code": 2},
    )
    formatted = _format_tool_result(result)
    assert "stdout-diagnostic" in formatted
    assert "[exit 2]" in formatted
    assert "stderr-detail" in formatted
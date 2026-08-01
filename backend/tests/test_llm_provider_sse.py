"""Unit tests for SSE tool_calls merge in LLM provider.

BUG-19 regression test: VansRouter always returns SSE even for non-streaming
requests. The SSE parser in chat() must correctly merge tool_calls deltas
(concatenate function.name and function.arguments across chunks).
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm.provider import LLMProvider, ProviderConfig


def _make_sse_response(chunks: list[dict]) -> str:
    """Build a fake SSE response body from a list of chunk dicts."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}")
    lines.append("data: [DONE]")
    return "\n".join(lines)


def _sse_chunk(content="", tool_calls=None, usage=None):
    """Build a single SSE chunk dict."""
    delta = {}
    if content:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    chunk = {"choices": [{"delta": delta}]}
    if usage:
        chunk["usage"] = usage
    return chunk


@pytest.mark.asyncio
async def test_sse_merge_tool_calls_single_tool():
    """SSE chunks with a single tool_call split across multiple deltas."""
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    # Simulate VansRouter SSE response with tool_calls split across chunks
    sse_body = _make_sse_response([
        # First chunk: tool_call id and function name start
        _sse_chunk(tool_calls=[{
            "index": 0,
            "id": "call_abc123",
            "type": "function",
            "function": {"name": "list_dir", "arguments": ""}
        }]),
        # Second chunk: arguments part 1
        _sse_chunk(tool_calls=[{
            "index": 0,
            "function": {"name": "", "arguments": '{"path": "/tmp"}'}
        }]),
        # Final chunk with usage
        _sse_chunk(content="", usage={"prompt_tokens": 10, "completion_tokens": 5}),
    ])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sse_body
    mock_resp.json = MagicMock(side_effect=ValueError("Not JSON — SSE body"))
    provider.client.post = AsyncMock(return_value=mock_resp)

    result = await provider.chat(
        messages=[{"role": "user", "content": "list /tmp"}],
        tools=[{"type": "function", "function": {"name": "list_dir", "parameters": {}}}],
    )

    raw_msg = result["raw"]["choices"][0]["message"]
    assert "tool_calls" in raw_msg, f"tool_calls missing from message! Keys: {list(raw_msg.keys())}"
    assert len(raw_msg["tool_calls"]) == 1

    tc = raw_msg["tool_calls"][0]
    assert tc["id"] == "call_abc123"
    assert tc["function"]["name"] == "list_dir"
    assert tc["function"]["arguments"] == '{"path": "/tmp"}'


@pytest.mark.asyncio
async def test_sse_merge_tool_calls_multiple_tools():
    """SSE chunks with two tool_calls interleaved."""
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    sse_body = _make_sse_response([
        # First tool starts
        _sse_chunk(tool_calls=[{
            "index": 0, "id": "call_1", "type": "function",
            "function": {"name": "create_ent", "arguments": ""}
        }]),
        # Second tool starts
        _sse_chunk(tool_calls=[{
            "index": 1, "id": "call_2", "type": "function",
            "function": {"name": "search_nod", "arguments": ""}
        }]),
        # First tool arguments
        _sse_chunk(tool_calls=[{
            "index": 0,
            "function": {"name": "", "arguments": '{"name": "Project"}'}
        }]),
        # Second tool arguments
        _sse_chunk(tool_calls=[{
            "index": 1,
            "function": {"name": "", "arguments": '{"query": "FastAPI"}'}
        }]),
    ])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sse_body
    mock_resp.json = MagicMock(side_effect=ValueError("SSE body"))
    provider.client.post = AsyncMock(return_value=mock_resp)

    result = await provider.chat(
        messages=[{"role": "user", "content": "create and search"}],
        tools=[],
    )

    raw_msg = result["raw"]["choices"][0]["message"]
    assert "tool_calls" in raw_msg
    assert len(raw_msg["tool_calls"]) == 2

    tc0 = raw_msg["tool_calls"][0]
    assert tc0["id"] == "call_1"
    assert tc0["function"]["name"] == "create_ent"
    assert tc0["function"]["arguments"] == '{"name": "Project"}'

    tc1 = raw_msg["tool_calls"][1]
    assert tc1["id"] == "call_2"
    assert tc1["function"]["name"] == "search_nod"
    assert tc1["function"]["arguments"] == '{"query": "FastAPI"}'


@pytest.mark.asyncio
async def test_sse_merge_tool_calls_with_content():
    """SSE chunks with both content AND tool_calls (model thinks then calls tools)."""
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    sse_body = _make_sse_response([
        _sse_chunk(content="I'll help you "),
        _sse_chunk(content="list the files. "),
        _sse_chunk(tool_calls=[{
            "index": 0, "id": "call_xyz", "type": "function",
            "function": {"name": "list_directory", "arguments": '{"path": "/tmp"}'}
        }]),
    ])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sse_body
    mock_resp.json = MagicMock(side_effect=ValueError("SSE body"))
    provider.client.post = AsyncMock(return_value=mock_resp)

    result = await provider.chat(
        messages=[{"role": "user", "content": "list /tmp"}],
        tools=[],
    )

    assert "I'll help you" in result["content"] and "list the files" in result["content"]
    raw_msg = result["raw"]["choices"][0]["message"]
    assert "tool_calls" in raw_msg
    assert len(raw_msg["tool_calls"]) == 1
    assert raw_msg["tool_calls"][0]["function"]["name"] == "list_directory"


@pytest.mark.asyncio
async def test_sse_merge_no_tool_calls():
    """SSE chunks with only content (no tool_calls) — should not add tool_calls key."""
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    sse_body = _make_sse_response([
        _sse_chunk(content="Hello "),
        _sse_chunk(content="world!"),
    ])

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sse_body
    mock_resp.json = MagicMock(side_effect=ValueError("SSE body"))
    provider.client.post = AsyncMock(return_value=mock_resp)

    result = await provider.chat(
        messages=[{"role": "user", "content": "say hello"}],
    )

    assert result["content"] == "Hello world!"
    raw_msg = result["raw"]["choices"][0]["message"]
    assert "tool_calls" not in raw_msg, "tool_calls should NOT be present when no tool_calls in SSE"


@pytest.mark.asyncio
async def test_sse_merge_tool_calls_arguments_concatenation():
    """Verify function.arguments is correctly concatenated across many small chunks."""
    config = ProviderConfig(name="test", base_url="http://test/v1", api_key="key")
    provider = LLMProvider(config)

    # Simulate arguments split character by character (worst case)
    args_str = '{"entity": "ProjectTech", "observations": ["FastAPI", "SQLite"]}'
    chunks = []
    # First chunk: tool id + name
    chunks.append(_sse_chunk(tool_calls=[{
        "index": 0, "id": "call_long", "type": "function",
        "function": {"name": "create_entities", "arguments": ""}
    }]))
    # Arguments split into small pieces
    for i in range(0, len(args_str), 10):
        chunks.append(_sse_chunk(tool_calls=[{
            "index": 0,
            "function": {"name": "", "arguments": args_str[i:i+10]}
        }]))

    sse_body = _make_sse_response(chunks)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sse_body
    mock_resp.json = MagicMock(side_effect=ValueError("SSE body"))
    provider.client.post = AsyncMock(return_value=mock_resp)

    result = await provider.chat(
        messages=[{"role": "user", "content": "create entities"}],
        tools=[],
    )

    raw_msg = result["raw"]["choices"][0]["message"]
    assert "tool_calls" in raw_msg
    tc = raw_msg["tool_calls"][0]
    assert tc["function"]["name"] == "create_entities"
    assert tc["function"]["arguments"] == args_str
    # Verify it's valid JSON
    parsed = json.loads(tc["function"]["arguments"])
    assert parsed["entity"] == "ProjectTech"
    assert "FastAPI" in parsed["observations"]

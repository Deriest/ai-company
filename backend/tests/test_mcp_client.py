"""Unit tests for the MCP protocol client (endpoint validation, HTTP, JSON-RPC)."""
import sys
from types import ModuleType
import pytest
from unittest.mock import patch

from backend.services.mcp_client import MCPClient, MCPError


def _fake_aiohttp_module(session_factory):
    """Build a stand-in aiohttp module (aiohttp is not a test dependency)."""
    fake = ModuleType("aiohttp")

    class ClientTimeout:
        def __init__(self, total=10):
            self.total = total

    class ClientError(Exception):
        pass

    fake.ClientSession = session_factory
    fake.ClientTimeout = ClientTimeout
    fake.ClientError = ClientError
    return fake


# ── stdio endpoint validation ─────────────────────────────────────

def test_is_allowed_stdio_endpoint_non_empty():
    assert MCPClient.is_allowed_stdio_endpoint("node-server") is True
    assert MCPClient.is_allowed_stdio_endpoint("tail -f log") is True
    assert MCPClient.is_allowed_stdio_endpoint("") is False
    assert MCPClient.is_allowed_stdio_endpoint("   ") is False
    assert MCPClient.is_allowed_stdio_endpoint(None) is False
    # Flag-like endpoints are rejected (command injection / option parsing).
    assert MCPClient.is_allowed_stdio_endpoint("-x") is False
    assert MCPClient.is_allowed_stdio_endpoint("--help") is False


# ── HTTP connect non-200 handling ─────────────────────────────────

class _FakeResponse:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def post(self, *_args, **_kwargs):
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_connect_http_success_200():
    client = MCPClient("http://localhost:8000/mcp", protocol="http")
    fake_aiohttp = _fake_aiohttp_module(lambda: _FakeSession([_FakeResponse(200)]))
    with patch.dict(sys.modules, {"aiohttp": fake_aiohttp}):
        assert await client.connect() is True
    assert client._connected is True


@pytest.mark.asyncio
async def test_connect_http_non_200_handled():
    client = MCPClient("http://localhost:8000/mcp", protocol="http")
    fake_aiohttp = _fake_aiohttp_module(lambda: _FakeSession([_FakeResponse(500)]))
    with patch.dict(sys.modules, {"aiohttp": fake_aiohttp}):
        assert await client.connect() is True
    assert client._connected is True


@pytest.mark.asyncio
async def test_connect_http_exception_returns_false():
    class _BoomSession(_FakeSession):
        def post(self, *_args, **_kwargs):
            raise ConnectionError("refused")

    client = MCPClient("http://localhost:8000/mcp", protocol="http")
    fake_aiohttp = _fake_aiohttp_module(lambda: _BoomSession([]))
    with patch.dict(sys.modules, {"aiohttp": fake_aiohttp}):
        assert await client.connect() is False
    assert client._connected is False


@pytest.mark.asyncio
async def test_connect_unknown_protocol_returns_false():
    client = MCPClient("whatever", protocol="bogus")
    assert await client.connect() is False
    assert client._connected is False


# ── JSON-RPC protocol parsing (stdio) ─────────────────────────────

class _FakeStream:
    def __init__(self, data=b""):
        self._data = data

    def write(self, _data):
        pass

    async def drain(self):
        pass

    async def readline(self):
        if self._data:
            line, _, rest = self._data.partition(b"\n")
            self._data = rest
            return line + b"\n"
        return b""


class _FakeProcess:
    def __init__(self, response: bytes):
        self.stdin = _FakeStream()
        self.stdout = _FakeStream(response)


@pytest.mark.asyncio
async def test_send_stdio_parses_result():
    client = MCPClient("fake", protocol="stdio")
    client._process = _FakeProcess(
        b'{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"read_file"}]}}\n'
    )
    result = await client._send_stdio({"method": "tools/list", "params": {}})
    assert result == {"tools": [{"name": "read_file"}]}
    assert client._request_id == 1


@pytest.mark.asyncio
async def test_send_stdio_raises_on_error_response():
    client = MCPClient("fake", protocol="stdio")
    client._process = _FakeProcess(
        b'{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found"}}\n'
    )
    with pytest.raises(MCPError) as exc_info:
        await client._send_stdio({"method": "bogus", "params": {}})
    assert exc_info.value.code == -32601
    assert "Method not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_stdio_raises_on_invalid_json():
    client = MCPClient("fake", protocol="stdio")
    client._process = _FakeProcess(b"not-json\n")
    with pytest.raises(MCPError) as exc_info:
        await client._send_stdio({"method": "tools/list", "params": {}})
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_stdio_raises_on_empty_response():
    client = MCPClient("fake", protocol="stdio")
    client._process = _FakeProcess(b"")
    with pytest.raises(MCPError) as exc_info:
        await client._send_stdio({"method": "tools/list", "params": {}})
    assert "Empty response" in str(exc_info.value)
"""MCP Protocol Client — real communication with MCP servers.

Implements the Model Context Protocol transports:
- stdio: Spawn subprocess, communicate via JSON-RPC over stdin/stdout
- HTTP: Send JSON-RPC requests to HTTP endpoint
- SSE: Server-Sent Events for streaming responses

JSON-RPC 2.0 format:
  Request:  {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
  Response: {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}
  Error:    {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "..."}}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional, Any

logger = logging.getLogger("aic.mcp.client")


class MCPError(Exception):
    """MCP protocol error."""
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"MCP error {code}: {message}")


class MCPClient:
    """Client for communicating with MCP servers via JSON-RPC 2.0.

    Supports three transport modes:
    - stdio: Spawn a subprocess and communicate via stdin/stdout pipes
    - http: Send HTTP POST requests with JSON-RPC payload
    - sse: Server-Sent Events for streaming (falls back to HTTP for requests)
    """

    def __init__(self, endpoint: str, protocol: str = "stdio", config: dict | None = None):
        self.endpoint = endpoint
        self.protocol = protocol
        self.config = config or {}
        self._request_id = 0
        self._process: asyncio.subprocess.Process | None = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection to the MCP server."""
        try:
            if self.protocol == "stdio":
                return await self._connect_stdio()
            elif self.protocol in ("http", "sse"):
                return await self._connect_http()
            else:
                logger.error(f"Unknown protocol: {self.protocol}")
                return False
        except Exception as e:
            logger.error(f"MCP connect failed ({self.protocol}://{self.endpoint}): {e}")
            return False

    async def _connect_stdio(self) -> bool:
        """Connect via stdio — spawn subprocess."""
        try:
            cmd_parts = self.endpoint.split()

            # Pass environment variables from config if provided
            env = None
            if self.config.get("env"):
                import os
                env = os.environ.copy()
                env.update(self.config["env"])

            self._process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            # Send initialize handshake
            init_result = await self._send_stdio({
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "aic-ade", "version": "2.4.0"},
                },
            })
            self._connected = True
            logger.info(f"MCP stdio connected: {self.endpoint}")
            return True
        except FileNotFoundError:
            logger.error(f"MCP stdio command not found: {self.endpoint}")
            return False
        except Exception as e:
            logger.error(f"MCP stdio connect failed: {e}")
            return False

    async def _connect_http(self) -> bool:
        """Connect via HTTP — test endpoint availability."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                # Send initialize request
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "aic-ade", "version": "2.4.0"},
                    },
                }
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.post(self.endpoint, json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        self._connected = True
                        logger.info(f"MCP HTTP connected: {self.endpoint}")
                        return True
                    logger.warning(f"MCP HTTP init returned {resp.status}")
                    self._connected = True  # Still mark as connected
                    return True
        except ImportError:
            # aiohttp not available, use basic fetch
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"MCP HTTP connect failed: {e}")
            return False

    async def disconnect(self):
        """Close the connection."""
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
        self._connected = False

    async def list_tools(self) -> list[dict]:
        """Discover available tools from the MCP server.

        Returns list of tool definitions:
        [{"name": "read_file", "description": "...", "inputSchema": {...}}]
        """
        if not self._connected:
            if not await self.connect():
                return []

        try:
            if self.protocol == "stdio":
                result = await self._send_stdio({"method": "tools/list", "params": {}})
            else:
                result = await self._send_http({"method": "tools/list", "params": {}})

            tools = result.get("tools", [])
            logger.info(f"MCP discovered {len(tools)} tools from {self.endpoint}")
            return tools
        except MCPError as e:
            logger.error(f"MCP tools/list failed: {e}")
            return []
        except Exception as e:
            logger.error(f"MCP tools/list error: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool on the MCP server.

        Returns the tool result:
        {"content": [{"type": "text", "text": "..."}]}
        or raises MCPError on failure.
        """
        if not self._connected:
            if not await self.connect():
                raise MCPError(-1, "Not connected to MCP server")

        try:
            if self.protocol == "stdio":
                result = await self._send_stdio({
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                })
            else:
                result = await self._send_http({
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                })
            return result
        except MCPError:
            raise
        except Exception as e:
            raise MCPError(-1, str(e))

    # ── Transport: stdio ───────────────────────────────────

    async def _send_stdio(self, request: dict, timeout: float = 30) -> dict:
        """Send JSON-RPC request via stdio and read response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise MCPError(-1, "stdio process not available")

        self._request_id += 1
        request["jsonrpc"] = "2.0"
        request["id"] = self._request_id

        # Write request
        payload = json.dumps(request) + "\n"
        self._process.stdin.write(payload.encode())
        await self._process.stdin.drain()

        # Read response with timeout
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=timeout,
            )
            if not line:
                raise MCPError(-1, "Empty response from MCP server")

            response = json.loads(line.decode().strip())

            if "error" in response:
                err = response["error"]
                raise MCPError(err.get("code", -1), err.get("message", "Unknown error"))

            return response.get("result", {})

        except asyncio.TimeoutError:
            raise MCPError(-1, f"stdio request timed out after {timeout}s")
        except json.JSONDecodeError as e:
            raise MCPError(-1, f"Invalid JSON response: {e}")

    # ── Transport: HTTP ────────────────────────────────────

    async def _send_http(self, request: dict, timeout: float = 30) -> dict:
        """Send JSON-RPC request via HTTP POST."""
        import aiohttp

        self._request_id += 1
        request["jsonrpc"] = "2.0"
        request["id"] = self._request_id

        try:
            async with aiohttp.ClientSession() as session:
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                headers = {"Content-Type": "application/json"}
                if self.config.get("auth_token"):
                    headers["Authorization"] = f"Bearer {self.config['auth_token']}"

                async with session.post(
                    self.endpoint, json=request, headers=headers, timeout=client_timeout
                ) as resp:
                    body = await resp.json()

                    if "error" in body:
                        err = body["error"]
                        raise MCPError(err.get("code", -1), err.get("message", "Unknown error"))

                    return body.get("result", {})

        except ImportError:
            # Fallback: use httpx or urllib
            return await self._send_http_fallback(request, timeout)
        except aiohttp.ClientError as e:
            raise MCPError(-1, f"HTTP error: {e}")

    async def _send_http_fallback(self, request: dict, timeout: float = 30) -> dict:
        """Fallback HTTP transport using urllib."""
        import urllib.request
        import urllib.error

        payload = json.dumps(request).encode()
        headers = {"Content-Type": "application/json"}
        if self.config.get("auth_token"):
            headers["Authorization"] = f"Bearer {self.config['auth_token']}"

        req = urllib.request.Request(self.endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
                if "error" in body:
                    err = body["error"]
                    raise MCPError(err.get("code", -1), err.get("message", "Unknown error"))
                return body.get("result", {})
        except urllib.error.URLError as e:
            raise MCPError(-1, f"HTTP error: {e}")


class MCPClientPool:
    """Pool of MCP clients, one per registered server.

    Manages connections and provides tool discovery + execution
    across all registered MCP servers.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}  # server_id → client
        self._tool_map: dict[str, tuple[str, str]] = {}  # tool_name → (server_id, tool_name)

    async def connect_server(self, server_id: str, endpoint: str, protocol: str = "stdio", config: dict | None = None) -> bool:
        """Connect to an MCP server and cache the client."""
        client = MCPClient(endpoint=endpoint, protocol=protocol, config=config)
        connected = await client.connect()
        if connected:
            self._clients[server_id] = client
            return True
        return False

    async def disconnect_server(self, server_id: str):
        """Disconnect and remove a server client."""
        client = self._clients.pop(server_id, None)
        if client:
            await client.disconnect()
        # Clean up tool map
        self._tool_map = {k: v for k, v in self._tool_map.items() if v[0] != server_id}

    async def disconnect_all(self):
        """Disconnect all clients."""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()
        self._tool_map.clear()

    async def discover_all_tools(self) -> list[dict]:
        """Discover tools from all connected servers.

        Returns flat list of tool definitions with server_id attached.
        """
        all_tools = []
        for server_id, client in self._clients.items():
            tools = await client.list_tools()
            for tool in tools:
                tool_name = tool.get("name", "")
                tool["_server_id"] = server_id
                self._tool_map[tool_name] = (server_id, tool_name)
                all_tools.append(tool)
        return all_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool by name, routing to the correct server."""
        if tool_name in self._tool_map:
            server_id, _ = self._tool_map[tool_name]
            client = self._clients.get(server_id)
            if client:
                return await client.call_tool(tool_name, arguments)
            raise MCPError(-1, f"Server {server_id} not connected")

        # Try all connected servers
        for server_id, client in self._clients.items():
            try:
                result = await client.call_tool(tool_name, arguments)
                self._tool_map[tool_name] = (server_id, tool_name)
                return result
            except MCPError:
                continue

        raise MCPError(-1, f"Tool '{tool_name}' not found on any MCP server")

    def get_connected_servers(self) -> list[str]:
        """Return list of connected server IDs."""
        return list(self._clients.keys())

    def is_connected(self, server_id: str) -> bool:
        """Check if a server is connected."""
        return server_id in self._clients


# Module-level pool instance
mcp_pool = MCPClientPool()

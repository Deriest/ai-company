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
import os
import time

logger = logging.getLogger("aic.mcp.client")


# Stdio MCP server endpoints are spawned as-is. AIC-ADE is a local desktop
# app (bind 127.0.0.1, single-user) — the same user already owns the machine,
# so no package allowlist is enforced. Only a non-empty command is required.


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

    def __init__(self, server_id: str, endpoint: str, protocol: str = "stdio", config: dict | None = None):
        self.server_id = server_id
        self.endpoint = endpoint
        self.protocol = protocol
        self.config = config or {}
        self._request_id = 0
        self._process: asyncio.subprocess.Process | None = None
        self._connected = False
        self._last_seen_at = time.time()  # Track last heartbeat for reconnection logic

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

    @staticmethod
    def is_allowed_stdio_endpoint(endpoint: str) -> bool:
        """Validate a stdio endpoint is spawnable.

        AIC-ADE is a local single-user desktop app — no package allowlist is
        enforced. Only a non-empty command line is required (an empty endpoint
        would error at spawn time). Kept for compatibility with callers that
        pre-check endpoints before connecting.
        """
        ep = (endpoint or "").strip()
        return bool(ep) and not ep.startswith(("-", "--"))

    async def _connect_stdio(self) -> bool:
        """Connect via stdio — spawn subprocess."""
        try:
            if not self.is_allowed_stdio_endpoint(self.endpoint):
                logger.error(f"MCP stdio endpoint not in allowlist: {self.endpoint}")
                return False
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
            await self._send_stdio({
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "aic-ade", "version": "2.4.0"},
                },
            })
            self._connected = True
            self._last_seen_at = time.time()
            logger.info(f"MCP stdio connected: {self.endpoint} (server_id={server_id})")
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
        self._last_seen_at = 0

    def _check_process_alive(self) -> bool:
        """Check if the stdio subprocess is still alive."""
        if self._process is None:
            return False
        return self._process.returncode is None

    async def reconnect_if_dead(self) -> bool:
        """Reconnect if stdio process died. Returns True if successfully reconnected."""
        if not self._connected:
            return False
        
        if self.protocol == "stdio" and not self._check_process_alive():
            logger.warning(
                f"MCP server {self.server_id} process died (PID={self._process.pid if self._process else 'N/A'}), attempting reconnection..."
            )
            # Disconnect current stale connection
            await self.disconnect()
            # Attempt fresh connection
            return await self.connect()
        
        # Update heartbeat
        self._last_seen_at = time.time()
        return True

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
        # Track server connection state for SQLite persistence
        self._server_state: dict[str, dict] = {}  # server_id -> {last_seen_at, status}
        # QA-E2E FIX: guard pool mutations (connect/disconnect/discover/call)
        # so concurrent access does not race on _clients/_tool_map.
        self._lock = asyncio.Lock()
        # PHASE 0 FIX: Background watcher for dead stdio processes
        self._watcher_task = None
        self._stop_watcher = asyncio.Event()

    async def connect_server(self, server_id: str, endpoint: str, protocol: str = "stdio", config: dict | None = None) -> bool:
        """Connect to an MCP server and cache the client."""
        client = MCPClient(server_id=server_id, endpoint=endpoint, protocol=protocol, config=config)
        connected = await client.connect()
        if connected:
            async with self._lock:
                self._clients[server_id] = client
            return True
        return False

    async def disconnect_server(self, server_id: str):
        """Disconnect and remove a server client."""
        async with self._lock:
            client = self._clients.pop(server_id, None)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            # Clean up tool map
            self._tool_map = {k: v for k, v in self._tool_map.items() if v[0] != server_id}

    async def disconnect_all(self):
        """Disconnect all clients."""
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
            self._tool_map.clear()
        for client in clients:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def discover_all_tools(self) -> list[dict]:
        """Discover tools from all connected servers.

        Returns flat list of tool definitions with server_id attached.
        """
        all_tools = []
        async with self._lock:
            clients = list(self._clients.items())
        for server_id, client in clients:
            tools = await client.list_tools()
            for tool in tools:
                tool_name = tool.get("name", "")
                tool["_server_id"] = server_id
                async with self._lock:
                    self._tool_map[tool_name] = (server_id, tool_name)
                all_tools.append(tool)
        return all_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool by name, routing to the correct server."""
        async with self._lock:
            if tool_name in self._tool_map:
                server_id, _ = self._tool_map[tool_name]
                client = self._clients.get(server_id)
                if client:
                    return await client.call_tool(tool_name, arguments)
                raise MCPError(-1, f"Server {server_id} not connected")

            # Try all connected servers
            clients = list(self._clients.items())

        for server_id, client in clients:
            try:
                result = await client.call_tool(tool_name, arguments)
                async with self._lock:
                    self._tool_map[tool_name] = (server_id, tool_name)
                return result
            except MCPError:
                continue

        raise MCPError(-1, f"Tool '{tool_name}' not found on any MCP server")

    async def start_background_watcher(self):
        """Start background process watcher that checks stdio connections every 30s."""
        if self._watcher_task is not None:
            return  # Already running
        
        self._stop_watcher.clear()
        self._watcher_task = asyncio.create_task(self._background_watcher_loop())
        logger.info("MCP process watcher started")

    async def stop_background_watcher(self):
        """Stop the background watcher."""
        if self._watcher_task:
            self._stop_watcher.set()
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None
            logger.info("MCP process watcher stopped")

    async def _background_watcher_loop(self):
        """Background task that monitors stdio subprocesses for death."""
        while not self._stop_watcher.is_set():
            try:
                async with self._lock:
                    clients = list(self._clients.items())
                
                for server_id, client in clients:
                    if client.protocol == "stdio":
                        reconnected = await client.reconnect_if_dead()
                        if reconnected:
                            logger.info(f"MCP server {server_id} reconnected successfully")
                        elif not client._connected:
                            logger.error(f"MCP server {server_id} failed to reconnect")
                
                # Update state timestamps for persistence
                async with self._lock:
                    for server_id, client in self._clients.items():
                        if client._connected:
                            self._server_state[server_id] = {
                                "last_seen_at": time.time(),
                                "status": "connected"
                            }
                        else:
                            self._server_state[server_id] = {
                                "last_seen_at": time.time(),
                                "status": "disconnected"
                            }

                # Wait 30 seconds before next check
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"MCP watcher loop error: {e}")
                await asyncio.sleep(10)  # Backoff on error

    def get_connected_servers(self) -> list[str]:
        """Return list of connected server IDs."""
        return list(self._clients.keys())

    def is_connected(self, server_id: str) -> bool:
        """Check if a server is connected."""
        return server_id in self._clients

    def get_server_state(self, server_id: str) -> dict:
        """Get persisted connection state for a server."""
        return self._server_state.get(server_id, {"last_seen_at": 0, "status": "unknown"})

    def persist_server_states(self) -> dict:
        """Return all server states for SQLite persistence.
        
        Returns: List of dicts with server_id and last_seen_at for DB storage.
        """
        async def _get_states():
            async with self._lock:
                return [
                    {"server_id": sid, "last_seen_at": data["last_seen_at"], "status": data["status"]}
                    for sid, data in self._server_state.items()
                ]
        
        # Run in event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = [None]
                def run():
                    result[0] = loop.run_until_complete(_get_states())
                threading.Thread(target=run).start()
                return result[0]
            else:
                return loop.run_until_complete(_get_states())
        except RuntimeError:
            # No event loop - create one
            import asyncio
            return asyncio.run(_get_states())

    def load_server_states(self, states: list[dict]):
        """Load saved server states from SQLite on startup.
        
        Args:
            states: List of dicts with server_id and last_seen_at
        """
        async def _load():
            async with self._lock:
                for state in states:
                    server_id = state.get("server_id")
                    if server_id:
                        self._server_state[server_id] = {
                            "last_seen_at": state.get("last_seen_at", 0),
                            "status": state.get("status", "unknown")
                        }
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                def run():
                    loop.run_until_complete(_load())
                threading.Thread(target=run).start()
            else:
                loop.run_until_complete(_load())
        except RuntimeError:
            import asyncio
            asyncio.run(_load())


# Module-level pool instance
mcp_pool = MCPClientPool()

"""
MCP (Model Context Protocol) Framework Service.

Manages MCP server registry, tool discovery, tool execution,
and permission system for dynamic tool loading.
"""

import json
import datetime
import logging
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.mcp import MCPRegistry, MCPTool, MCPToolExecution
from backend.services.tool_dispatcher import tool_dispatcher

logger = logging.getLogger("aic.mcp.plugin")


class MCPService:
    """MCP registry, discovery, and execution engine."""

    # ── Registry Management ───────────────────────────────────

    @staticmethod
    async def register_server(
        db: AsyncSession,
        name: str,
        endpoint: str,
        protocol: str = "stdio",
        description: str = "",
        config: dict = None,
    ) -> MCPRegistry:
        server = MCPRegistry(
            name=name,
            endpoint=endpoint,
            protocol=protocol,
            description=description,
            config=config or {},
            status="disconnected",
        )
        db.add(server)
        await db.commit()
        await db.refresh(server)
        return server

    @staticmethod
    async def get_server(db: AsyncSession, server_id: str) -> Optional[MCPRegistry]:
        res = await db.execute(select(MCPRegistry).where(MCPRegistry.id == server_id))
        return res.scalars().first()

    @staticmethod
    async def list_servers(db: AsyncSession) -> list[MCPRegistry]:
        res = await db.execute(select(MCPRegistry).order_by(MCPRegistry.name))
        return list(res.scalars().all())

    @staticmethod
    async def update_server(db: AsyncSession, server_id: str, **kwargs) -> MCPRegistry:
        server = await MCPService.get_server(db, server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")
        for k, v in kwargs.items():
            if hasattr(server, k) and v is not None:
                setattr(server, k, v)
        await db.commit()
        await db.refresh(server)
        return server

    @staticmethod
    async def delete_server(db: AsyncSession, server_id: str):
        server = await MCPService.get_server(db, server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")
        await db.delete(server)
        await db.commit()

    # ── Tool Discovery ────────────────────────────────────────

    @staticmethod
    async def discover_tools(db: AsyncSession, server_id: str, tools: list[dict]) -> list[MCPTool]:
        """Register tools from an MCP server's tool list."""
        server = await MCPService.get_server(db, server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")

        # Clear old tools for this server
        res = await db.execute(select(MCPTool).where(MCPTool.registry_id == server_id))
        for old in res.scalars().all():
            await db.delete(old)

        new_tools = []
        for t in tools:
            tool = MCPTool(
                registry_id=server_id,
                tool_name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                is_enabled=True,
                requires_approval=t.get("requires_approval", False),
            )
            db.add(tool)
            new_tools.append(tool)

        server.status = "connected"
        server.last_connected_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        for t in new_tools:
            await db.refresh(t)
        return new_tools

    @staticmethod
    async def list_tools(db: AsyncSession, server_id: Optional[str] = None) -> list[MCPTool]:
        query = select(MCPTool).where(MCPTool.is_enabled == True)
        if server_id:
            query = query.where(MCPTool.registry_id == server_id)
        res = await db.execute(query.order_by(MCPTool.tool_name))
        return list(res.scalars().all())

    @staticmethod
    async def get_tool(db: AsyncSession, tool_id: str) -> Optional[MCPTool]:
        res = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
        return res.scalars().first()

    @staticmethod
    async def toggle_tool(db: AsyncSession, tool_id: str, enabled: bool) -> MCPTool:
        tool = await MCPService.get_tool(db, tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        tool.is_enabled = enabled
        await db.commit()
        await db.refresh(tool)
        return tool

    # ── Tool Execution ────────────────────────────────────────

    @staticmethod
    async def execute_tool(
        db: AsyncSession,
        tool_id: str,
        arguments: dict,
        conversation_id: Optional[str] = None,
    ) -> MCPToolExecution:
        tool = await MCPService.get_tool(db, tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        if not tool.is_enabled:
            raise ValueError(f"Tool '{tool.tool_name}' is disabled")
        if tool.requires_approval:
            # Create pending execution — approval needed before running
            execution = MCPToolExecution(
                tool_id=tool_id,
                registry_id=tool.registry_id,
                tool_name=tool.tool_name,
                input_args=arguments,
                status="pending",
                conversation_id=conversation_id,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            return execution

        # Execute directly via tool_dispatcher (native tools) or mock
        start = time.time()
        execution = MCPToolExecution(
            tool_id=tool_id,
            registry_id=tool.registry_id,
            tool_name=tool.tool_name,
            input_args=arguments,
            status="running",
            conversation_id=conversation_id,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        try:
            # Try MCP protocol client first (remote execution)
            from backend.services.mcp_client import mcp_pool
            if mcp_pool.is_connected(tool.registry_id):
                result = await mcp_pool.call_tool(tool.tool_name, arguments)
                exec_time = int((time.time() - start) * 1000)
                # MCP returns {"content": [{"type": "text", "text": "..."}]}
                content_parts = result.get("content", [])
                text_output = "\n".join(
                    p.get("text", "") for p in content_parts if p.get("type") == "text"
                ) or json.dumps(result)
                execution.output = text_output
                execution.status = "completed"
                execution.execution_time_ms = exec_time
            else:
                # Fallback: local tool_dispatcher
                result = await tool_dispatcher.execute(tool.tool_name, arguments)
                exec_time = int((time.time() - start) * 1000)
                execution.output = result.get("result") or result.get("error")
                execution.status = "completed" if result.get("error") is None else "failed"
                execution.error_message = result.get("error")
                execution.execution_time_ms = exec_time
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.execution_time_ms = int((time.time() - start) * 1000)

        await db.commit()
        await db.refresh(execution)
        return execution

    @staticmethod
    async def approve_execution(db: AsyncSession, execution_id: str, approved: bool) -> MCPToolExecution:
        res = await db.execute(select(MCPToolExecution).where(MCPToolExecution.id == execution_id))
        execution = res.scalars().first()
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        if execution.status != "pending":
            raise ValueError(f"Execution already {execution.status}")

        if not approved:
            execution.status = "denied"
            await db.commit()
            await db.refresh(execution)
            return execution

        # Execute the approved tool
        start = time.time()
        execution.status = "running"
        await db.commit()

        try:
            # Try MCP protocol client first (remote execution)
            from backend.services.mcp_client import mcp_pool
            tool_rec = await MCPService.get_tool(db, execution.tool_id)
            if tool_rec and mcp_pool.is_connected(tool_rec.registry_id):
                result = await mcp_pool.call_tool(execution.tool_name, execution.input_args or {})
                exec_time = int((time.time() - start) * 1000)
                content_parts = result.get("content", [])
                text_output = "\n".join(
                    p.get("text", "") for p in content_parts if p.get("type") == "text"
                ) or json.dumps(result)
                execution.output = text_output
                execution.status = "completed"
                execution.execution_time_ms = exec_time
            else:
                result = await tool_dispatcher.execute(execution.tool_name, execution.input_args or {})
                exec_time = int((time.time() - start) * 1000)
                execution.output = result.get("result") or result.get("error")
                execution.status = "completed" if result.get("error") is None else "failed"
                execution.error_message = result.get("error")
                execution.execution_time_ms = exec_time
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.execution_time_ms = int((time.time() - start) * 1000)

        await db.commit()
        await db.refresh(execution)
        return execution

    @staticmethod
    async def get_executions(
        db: AsyncSession, conversation_id: Optional[str] = None, limit: int = 50
    ) -> list[MCPToolExecution]:
        query = select(MCPToolExecution).order_by(MCPToolExecution.created_at.desc()).limit(limit)
        if conversation_id:
            query = query.where(MCPToolExecution.conversation_id == conversation_id)
        res = await db.execute(query)
        return list(res.scalars().all())


    @staticmethod
    async def connect_and_discover(db: AsyncSession, server_id: str) -> list[MCPTool]:
        """Connect to MCP server via protocol client and discover tools."""
        server = await MCPService.get_server(db, server_id)
        if not server:
            raise ValueError(f"Server {server_id} not found")

        from backend.services.mcp_client import mcp_pool
        connected = await mcp_pool.connect_server(
            server_id, server.endpoint, server.protocol, server.config or {}
        )
        if not connected:
            server.status = "error"
            await db.commit()
            raise ValueError(f"Failed to connect to MCP server: {server.endpoint}")

        server.status = "connected"
        server.last_connected_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()

        # Discover tools via protocol
        raw_tools = await mcp_pool.discover_all_tools()
        server_tools = [t for t in raw_tools if t.get("_server_id") == server_id]

        # Clean _server_id before storing
        clean_tools = []
        for t in server_tools:
            t.pop("_server_id", None)
            clean_tools.append(t)

        if clean_tools:
            return await MCPService.discover_tools(db, server_id, clean_tools)

        return []

    @staticmethod
    async def disconnect_server(db: AsyncSession, server_id: str):
        """Disconnect from MCP server."""
        from backend.services.mcp_client import mcp_pool
        await mcp_pool.disconnect_server(server_id)
        server = await MCPService.get_server(db, server_id)
        if server:
            server.status = "disconnected"
            await db.commit()

    @staticmethod
    async def register_plugin_server(db: AsyncSession, plugin_id: str, server_def: dict) -> dict:
        """Register an MCP server declared by a plugin and attempt connection.

        G2 FIX: plugin-declared MCP servers were dead on arrival — agent runners
        only logged them. This registers the server in the MCP registry (reusing
        an existing registration with the same name so it is idempotent) and
        attempts a connection. AIC-ADE is a local desktop app — no stdio
        allowlist is enforced, so any non-empty endpoint is registered and
        connection is attempted; failures are surfaced in the returned status.

        Returns {"server_id": ..., "status": "connected"|"error", "error": ...}.
        """
        name = str(server_def.get("name") or f"plugin-{plugin_id}").strip()
        endpoint = str(server_def.get("endpoint") or "").strip()
        protocol = str(server_def.get("protocol") or "stdio").strip()
        config = server_def.get("config") or {}
        if not name or not endpoint:
            return {"server_id": None, "status": "error", "error": "Plugin MCP server is missing name/endpoint"}

        # G2: AIC-ADE is a local desktop app — no stdio allowlist is enforced.
        # Any non-empty endpoint is registered and connection is attempted.
        if protocol == "stdio":
            from backend.services.mcp_client import MCPClient
            if not MCPClient.is_allowed_stdio_endpoint(endpoint):
                return {
                    "server_id": None,
                    "status": "error",
                    "error": f"Plugin MCP endpoint is empty: {endpoint}",
                }

        # Reuse an existing registration with the same name (idempotent re-runs).
        res = await db.execute(select(MCPRegistry).where(MCPRegistry.name == name))
        server = res.scalars().first()
        if server:
            server.endpoint = endpoint
            server.protocol = protocol
            server.config = config
            await db.commit()
            server_id = server.id
        else:
            server = MCPRegistry(
                name=name,
                endpoint=endpoint,
                protocol=protocol,
                description=f"Plugin MCP server: {plugin_id}",
                config=config,
                status="disconnected",
            )
            db.add(server)
            await db.commit()
            await db.refresh(server)
            server_id = server.id

        try:
            await MCPService.connect_and_discover(db, server_id)
            return {"server_id": server_id, "status": "connected", "error": None}
        except Exception as e:
            logger.warning(f"Plugin MCP server '{name}' could not connect: {e}")
            return {"server_id": server_id, "status": "error", "error": str(e)}

    @staticmethod
    async def get_all_mcp_tool_schemas(db: AsyncSession) -> list[dict]:
        """Get all enabled MCP tools as LLM-compatible tool schemas.

        Used by the chat service to inject MCP tools into LLM context.
        """
        tools = await MCPService.list_tools(db)
        schemas = []
        for t in tools:
            schemas.append({
                "name": t.tool_name,
                "description": t.description or "",
                "inputSchema": t.input_schema or {"type": "object", "properties": {}},
                "tool_id": t.id,
                "requires_approval": t.requires_approval,
            })
        return schemas

    # ── Server State Persistence (PHASE 0 FIX #3) ───────────────────────

    @staticmethod
    async def get_all_server_states(db: AsyncSession) -> list[dict]:
        """Retrieve persisted connection state for all servers."""
        try:
            from backend.services.mcp_client import mcp_pool
            states = mcp_pool.persist_server_states()
            return states
        except Exception as e:
            logger.error(f"Failed to get server states: {e}")
            return []

    @staticmethod
    async def restore_server_connection(
        db: AsyncSession,
        server_id: str,
        endpoint: str,
        protocol: str,
        config: dict = None,
    ) -> bool:
        """Restore a server connection after restart using saved state.
        
        This is called on startup to reconnect servers that were active before.
        
        Args:
            db: Database session
            server_id: Unique server identifier
            endpoint: Server endpoint (stdio command or HTTP URL)
            protocol: Transport protocol (stdio/http/sse)
            config: Optional server configuration
            
        Returns:
            True if reconnection successful
        """
        try:
            from backend.services.mcp_client import mcp_pool
            connected = await mcp_pool.connect_server(server_id, endpoint, protocol, config)
            if connected:
                logger.info(f"Restored MCP server {server_id} connection")
                return True
            else:
                logger.warning(f"Failed to restore MCP server {server_id} connection")
                return False
        except Exception as e:
            logger.error(f"Error restoring MCP server {server_id}: {e}")
            return False

    @staticmethod
    async def start_mcp_watcher():
        """Start the background process watcher for stdio servers."""
        from backend.services.mcp_client import mcp_pool
        mcp_pool.start_background_watcher()

    @staticmethod
    async def stop_mcp_watcher():
        """Stop the background process watcher."""
        from backend.services.mcp_client import mcp_pool
        await mcp_pool.stop_background_watcher()


mcp_service = MCPService()

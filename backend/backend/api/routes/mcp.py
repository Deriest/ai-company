from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import json
import logging

from backend.database.session import get_db
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)]))

logger = logging.getLogger("aic.mcp")

from backend.services.mcp_service import mcp_service
from backend.models.mcp import MCPRegistry, MCPTool, MCPToolExecution


# ── MCP Framework Endpoints ──────────────────────────────────

@router.post("/mcp/servers")
async def register_mcp_server(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    name = payload.get("name")
    endpoint = payload.get("endpoint")
    if not name or not endpoint:
        raise HTTPException(status_code=400, detail="name and endpoint are required")
    server = await mcp_service.register_server(
        db, name=name, endpoint=endpoint,
        protocol=payload.get("protocol", "stdio"),
        description=payload.get("description", ""),
        config=payload.get("config"),
    )
    logger.info("MCP server registered: id=%s name=%s protocol=%s", server.id, server.name, server.protocol)
    return {"id": server.id, "name": server.name, "endpoint": server.endpoint, "status": server.status}

@router.get("/mcp/servers")
async def list_mcp_servers(db: AsyncSession = Depends(get_db)):
    servers = await mcp_service.list_servers(db)
    return [
        {"id": s.id, "name": s.name, "endpoint": s.endpoint, "protocol": s.protocol,
         "isEnabled": s.is_enabled, "status": s.status, "description": s.description}
        for s in servers
    ]

@router.patch("/mcp/servers/{server_id}")
async def update_mcp_server(
    server_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    try:
        server = await mcp_service.update_server(db, server_id, **payload)
        return {"id": server.id, "name": server.name, "status": server.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/mcp/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    try:
        await mcp_service.delete_server(db, server_id)
        logger.info("MCP server deleted: server_id=%s", server_id)
        return {"status": "ok"}
    except ValueError as e:
        logger.warning("MCP server delete failed: server_id=%s error=%s", server_id, e)
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/mcp/servers/{server_id}/discover")
async def discover_mcp_tools(
    server_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    try:
        tools = await mcp_service.discover_tools(db, server_id, payload.get("tools", []))
        return [{"id": t.id, "toolName": t.tool_name, "description": t.description} for t in tools]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/mcp/tools")
async def list_mcp_tools(server_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    tools = await mcp_service.list_tools(db, server_id)
    return [
        {"id": t.id, "registryId": t.registry_id, "toolName": t.tool_name,
         "description": t.description, "isEnabled": t.is_enabled, "requiresApproval": t.requires_approval}
        for t in tools
    ]

@router.post("/mcp/tools/{tool_id}/execute")
async def execute_mcp_tool(
    tool_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    try:
        execution = await mcp_service.execute_tool(
            db, tool_id, payload.get("arguments", {}), payload.get("conversation_id")
        )
        return {
            "id": execution.id, "toolName": execution.tool_name,
            "status": execution.status, "output": execution.output,
            "errorMessage": execution.error_message,
            "executionTimeMs": execution.execution_time_ms,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/mcp/executions/{execution_id}/approve")
async def approve_mcp_execution(
    execution_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    try:
        execution = await mcp_service.approve_execution(db, execution_id, payload.get("approved", False))
        return {"id": execution.id, "status": execution.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mcp/executions")
async def list_mcp_executions(
    conversation_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)
):
    executions = await mcp_service.get_executions(db, conversation_id)
    return [
        {"id": e.id, "toolName": e.tool_name, "status": e.status,
         "executionTimeMs": e.execution_time_ms, "createdAt": e.created_at.isoformat()}
        for e in executions
    ]


@router.post("/mcp/servers/{server_id}/connect")
async def connect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Connect to MCP server via protocol client and discover tools."""
    try:
        tools = await mcp_service.connect_and_discover(db, server_id)
        logger.info("MCP server connected: server_id=%s tools_discovered=%d", server_id, len(tools))
        return {
            "status": "connected",
            "server_id": server_id,
            "tools_discovered": len(tools),
            "tools": [{"id": t.id, "toolName": t.tool_name, "description": t.description} for t in tools],
        }
    except ValueError as e:
        logger.warning("MCP server connect failed: server_id=%s error=%s", server_id, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mcp/servers/{server_id}/disconnect")
async def disconnect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Disconnect from MCP server."""
    await mcp_service.disconnect_server(db, server_id)
    logger.info("MCP server disconnected: server_id=%s", server_id)
    return {"status": "disconnected", "server_id": server_id}


@router.get("/mcp/tools/schema")
async def get_mcp_tool_schemas(db: AsyncSession = Depends(get_db)):
    """Get all MCP tools as LLM-compatible schemas (for chat injection)."""
    schemas = await mcp_service.get_all_mcp_tool_schemas(db)
    return schemas


# ── FITUR 1: MCP Memory Server Preset ──────────────────────

MCP_MEMORY_PRESETS = [
    {
        "name": "Memory (MCP)",
        "endpoint": "npx -y @modelcontextprotocol/server-memory",
        "protocol": "stdio",
        "description": "Persistent knowledge graph memory server. Tools: create_entities, add_observations, search_nodes, open_nodes, read_graph.",
        "config": {
            "memory_file": "__AIC_DATA_DIR__/memory/memory.json",
        },
    },
]


@router.get("/mcp/presets")
async def get_mcp_presets():
    """Return available MCP server presets for quick registration."""
    import os
    data_dir = os.environ.get("AIC_DATA_DIR", "")
    presets = []
    for p in MCP_MEMORY_PRESETS:
        preset = dict(p)
        # Resolve AIC_DATA_DIR placeholder in config
        if data_dir and preset.get("config"):
            resolved_config = {}
            for k, v in preset["config"].items():
                if isinstance(v, str) and "__AIC_DATA_DIR__" in v:
                    resolved_config[k] = v.replace("__AIC_DATA_DIR__", data_dir)
                else:
                    resolved_config[k] = v
            preset["config"] = resolved_config
        presets.append(preset)
    return presets


@router.post("/mcp/servers/register-memory")
async def register_memory_server(
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Register the MCP Memory server preset with auto-connect.

    Creates the memory directory if needed, registers the server,
    and triggers connect + discover.
    """
    import os
    data_dir = os.environ.get("AIC_DATA_DIR", "")

    # Resolve memory file path
    if data_dir:
        memory_dir = os.path.join(data_dir, "memory")
        os.makedirs(memory_dir, exist_ok=True)
        memory_file = os.path.join(memory_dir, "memory.json")
    else:
        memory_file = "memory.json"

    # Check if already registered
    servers = await mcp_service.list_servers(db)
    for s in servers:
        if s.name == "Memory (MCP)":
            # Already registered — reconnect
            try:
                tools = await mcp_service.connect_and_discover(db, s.id)
                return {
                    "status": "reconnected",
                    "server_id": s.id,
                    "tools_discovered": len(tools),
                    "tools": [{"id": t.id, "toolName": t.tool_name, "description": t.description} for t in tools],
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}

    # Register new
    server = await mcp_service.register_server(
        db,
        name="Memory (MCP)",
        endpoint="npx -y @modelcontextprotocol/server-memory",
        protocol="stdio",
        description="Persistent knowledge graph memory server. Tools: create_entities, add_observations, search_nodes, open_nodes, read_graph.",
        config={"memory_file": memory_file, "env": {"MEMORY_FILE_PATH": memory_file}},
    )

    # Auto-connect and discover tools
    try:
        tools = await mcp_service.connect_and_discover(db, server.id)
        return {
            "status": "connected",
            "server_id": server.id,
            "name": server.name,
            "tools_discovered": len(tools),
            "tools": [{"id": t.id, "toolName": t.tool_name, "description": t.description} for t in tools],
            "memory_file": memory_file,
        }
    except Exception as e:
        return {
            "status": "registered",
            "server_id": server.id,
            "name": server.name,
            "warning": f"Registered but connect failed: {e}. Tools will be discovered on next connect.",
            "memory_file": memory_file,
        }

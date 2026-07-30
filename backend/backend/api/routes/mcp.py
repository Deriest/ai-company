from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import json

from backend.database.session import get_db

router = APIRouter()

from backend.services.mcp_service import mcp_service
from backend.models.mcp import MCPRegistry, MCPTool, MCPToolExecution


# ── MCP Framework Endpoints ──────────────────────────────────

@router.post("/mcp/servers")
async def register_mcp_server(payload: dict, db: AsyncSession = Depends(get_db)):
    server = await mcp_service.register_server(
        db, name=payload["name"], endpoint=payload["endpoint"],
        protocol=payload.get("protocol", "stdio"),
        description=payload.get("description", ""),
        config=payload.get("config"),
    )
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
async def update_mcp_server(server_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    try:
        server = await mcp_service.update_server(db, server_id, **payload)
        return {"id": server.id, "name": server.name, "status": server.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/mcp/servers/{server_id}")
async def delete_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await mcp_service.delete_server(db, server_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/mcp/servers/{server_id}/discover")
async def discover_mcp_tools(server_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
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
async def execute_mcp_tool(tool_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
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
async def approve_mcp_execution(execution_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
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
async def connect_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Connect to MCP server via protocol client and discover tools."""
    try:
        tools = await mcp_service.connect_and_discover(db, server_id)
        return {
            "status": "connected",
            "server_id": server_id,
            "tools_discovered": len(tools),
            "tools": [{"id": t.id, "toolName": t.tool_name, "description": t.description} for t in tools],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mcp/servers/{server_id}/disconnect")
async def disconnect_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Disconnect from MCP server."""
    await mcp_service.disconnect_server(db, server_id)
    return {"status": "disconnected", "server_id": server_id}


@router.get("/mcp/tools/schema")
async def get_mcp_tool_schemas(db: AsyncSession = Depends(get_db)):
    """Get all MCP tools as LLM-compatible schemas (for chat injection)."""
    schemas = await mcp_service.get_all_mcp_tool_schemas(db)
    return schemas

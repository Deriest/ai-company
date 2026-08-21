"""AIC-ADE — Tool Execution & Audit Log Routes.

Provides:
- Safe tool execution endpoint (GET/POST /api/tools/execute)
- Tool call audit log query endpoint (GET /api/tools/audit?conversation_id=X)
"""

import logging
from typing import Optional, Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database.session import get_db
from backend.models.ai_runtime import ToolCallLog
from pydantic import BaseModel
router = APIRouter(prefix="/tools", tags=["tools"])




class ToolExecuteRequest(BaseModel):
    """Request for unauthenticated tool execution."""
    tool_name: str
    arguments: dict = {}


@router.post("/execute")
async def execute_tool_unauth(
    request: ToolExecuteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Execute a tool without authentication (limited allowlist)."""
    from backend.services.tool_dispatcher import tool_dispatcher
    
    _ALLOWED_TOOLS = {
        "read_file", "write_file", "list_directory", 
        "search_workspace", "current_time"
    }
    
    if request.tool_name not in _ALLOWED_TOOLS:
        raise HTTPException(status_code=403, detail="Tool not allowed")
    
    result = await tool_dispatcher.execute(
        request.tool_name,
        request.arguments,
        conversation_id=None,  # No conversation tracking for unauth calls
        message_id=None
    )
    
    return result


@router.get("/audit")
async def get_tool_call_audit_log(
    conversation_id: Annotated[str, Query(description="Filter by conversation ID")],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get tool call audit logs for a specific conversation.
    
    Returns structured history of all tool executions including:
    - Tool name and arguments
    - Result or error details  
    - Execution time and status
    - Timestamp
    
    Useful for debugging, transparency, and user verification.
    """
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
    
    query = (
        select(ToolCallLog)
        .where(ToolCallLog.conversation_id == conversation_id)
        .order_by(ToolCallLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "tool_name": log.tool_name,
            "arguments": log.arguments,
            "result": log.result,
            "error": log.error,
            "execution_time_ms": log.execution_time_ms,
            "status": log.status,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/audit/count")
async def get_audit_log_count(
    conversation_id: Annotated[str, Query(description="Filter by conversation ID")],
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get total count of tool call audit logs for a conversation."""
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
    
    query = select(func.count(ToolCallLog.id)).where(ToolCallLog.conversation_id == conversation_id)
    result = await db.execute(query)
    count = result.scalar() or 0
    
    return {"conversation_id": conversation_id, "total_tool_calls": count}

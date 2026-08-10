"""AIC Platform — Engineering Dispatcher API Routes."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from storage.database import get_session
from backend.api.dependencies import require_current_user

logger = logging.getLogger("aic.dispatcher.api")

router = APIRouter()


class DispatchRequest(BaseModel):
    graph_id: str


@router.post("/dispatch")
async def dispatch_tasks(
    req: DispatchRequest,
    _auth: str = require_current_user,
):
    """Dispatch tasks from a Task Graph."""
    async with get_session(auto_commit=True) as session:
        from dispatcher.engine import DispatcherEngine

        engine = DispatcherEngine(session)
        result = await engine.dispatch(req.graph_id)

        if result.state == "error":
            raise HTTPException(400, result.message)

        return {
            "state": result.state,
            "result": result.result.to_dict() if result.result else None,
            "message": result.message,
            "metadata": result.metadata,
        }


@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
):
    """Get execution status."""
    async with get_session(auto_commit=True) as session:
        from storage.models import DispatchSession
        from sqlalchemy import select

        result = await session.execute(
            select(DispatchSession).where(DispatchSession.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise HTTPException(404, "Execution not found")

        return {
            "id": execution.id,
            "graph_id": execution.graph_id,
            "status": execution.status,
            "success_rate": execution.success_rate,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        }
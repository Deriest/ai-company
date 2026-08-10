"""AIC Platform — Task Graph Engine API Routes."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from backend.api.dependencies import require_current_user

logger = logging.getLogger("aic.taskgraph.api")

router = APIRouter()


class GraphRequest(BaseModel):
    plan_id: str


@router.post("/generate")
async def generate_graph(
    req: GraphRequest,
    _auth: str = require_current_user,
):
    """Generate a Task Graph from a Plan."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("taskgraph.engine", fromlist=["TaskGraphEngine"]).TaskGraphEngine(session)
        result = await engine.generate_graph(req.plan_id)

        if result.state == "error":
            raise HTTPException(400, result.message)

        return {
            "state": result.state,
            "graph": result.graph.to_dict() if result.graph else None,
            "message": result.message,
            "metadata": result.metadata,
        }


@router.get("/{graph_id}")
async def get_graph(
    graph_id: str,
):
    """Get a Task Graph by ID."""
    async with get_session(auto_commit=True) as session:
        from storage.models import TaskGraphModel

        result = await session.execute(
            select(TaskGraphModel).where(TaskGraphModel.id == graph_id)
        )
        graph = result.scalar_one_or_none()
        if not graph:
            raise HTTPException(404, "Task Graph not found")

        return {
            "id": graph.id,
            "plan_id": graph.plan_id,
            "nodes": graph.nodes or [],
            "edges": graph.edges or [],
            "execution_order": graph.execution_order or [],
            "critical_path": graph.critical_path or [],
            "status": graph.status,
            "parallelism_factor": graph.parallelism_factor,
            "created_at": graph.created_at.isoformat() if graph.created_at else None,
        }


@router.get("/plan/{plan_id}")
async def get_graph_for_plan(
    plan_id: str,
):
    """Get Task Graph for a Plan."""
    async with get_session(auto_commit=True) as session:
        from storage.models import TaskGraphModel

        result = await session.execute(
            select(TaskGraphModel)
            .where(TaskGraphModel.plan_id == plan_id)
            .order_by(TaskGraphModel.created_at.desc())
            .limit(1)
        )
        graph = result.scalar_one_or_none()
        if not graph:
            raise HTTPException(404, "No graph found for this plan")

        return {
            "id": graph.id,
            "plan_id": graph.plan_id,
            "status": graph.status,
            "parallelism_factor": graph.parallelism_factor,
            "created_at": graph.created_at.isoformat() if graph.created_at else None,
        }

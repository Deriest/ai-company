"""Pipeline routes — engineering pipeline status and control.

Provides endpoints for the frontend to:
- Query pipeline status for a task
- List all active pipelines
- Get pipeline stage details (brief, plan, graph, dispatch)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime

from backend.database.session import get_db
from backend.api.dependencies import require_current_user
from storage.models import (
    Task,
    EngineeringBrief as EngineeringBriefORM,
    EngineeringPlan as EngineeringPlanORM,
    TaskGraphModel,
    DispatchSession,
)

router = APIRouter(dependencies=[Depends(require_current_user)])dependencies=[Depends(require_current_user)])


@router.get("/pipeline/task/{task_id}")
async def get_task_pipeline(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full pipeline status for a task."""
    # Load task
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    ctx = task.context or {}
    brief_id = ctx.get("brief_id")
    plan_id = ctx.get("plan_id")
    graph_id = ctx.get("graph_id")
    dispatch_id = ctx.get("dispatch_id")

    pipeline = {
        "task_id": task.id,
        "task_title": task.title,
        "task_status": task.status,
        "task_progress": task.progress,
        "stages": {},
    }

    # Discovery stage
    if brief_id:
        brief_result = await db.execute(
            select(EngineeringBriefORM).where(EngineeringBriefORM.id == brief_id)
        )
        brief = brief_result.scalar_one_or_none()
        if brief:
            pipeline["stages"]["discovery"] = {
                "status": "completed",
                "brief_id": brief.id,
                "engineering_goal": brief.engineering_goal,
                "readiness_score": brief.readiness_score,
                "requirements_count": len(brief.functional_requirements or []),
                "created_at": brief.created_at.isoformat() if brief.created_at else None,
            }

    # Planning stage
    if plan_id:
        plan_result = await db.execute(
            select(EngineeringPlanORM).where(EngineeringPlanORM.id == plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        if plan:
            pipeline["stages"]["planning"] = {
                "status": "completed",
                "plan_id": plan.id,
                "technical_approach": plan.technical_approach,
                "confidence_score": plan.confidence_score,
                "decisions_count": len(plan.architecture_decisions or []),
                "effort_estimates": plan.effort_estimates or [],
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
            }

    # TaskGraph stage
    if graph_id:
        graph_result = await db.execute(
            select(TaskGraphModel).where(TaskGraphModel.id == graph_id)
        )
        graph = graph_result.scalar_one_or_none()
        if graph:
            pipeline["stages"]["taskgraph"] = {
                "status": "completed",
                "graph_id": graph.id,
                "nodes_count": len(graph.nodes or []),
                "edges_count": len(graph.edges or []),
                "parallelism_factor": graph.parallelism_factor,
                "critical_path": graph.critical_path or [],
                "created_at": graph.created_at.isoformat() if graph.created_at else None,
            }

    # Dispatch stage
    if dispatch_id:
        dispatch_result = await db.execute(
            select(DispatchSession).where(DispatchSession.id == dispatch_id)
        )
        dispatch = dispatch_result.scalar_one_or_none()
        if dispatch:
            pipeline["stages"]["dispatch"] = {
                "status": dispatch.status,
                "dispatch_id": dispatch.id,
                "success_rate": dispatch.success_rate,
                "execution_log": dispatch.execution_log or [],
                "created_at": dispatch.created_at.isoformat() if dispatch.created_at else None,
            }

    return pipeline


@router.get("/pipeline/active")
async def list_active_pipelines(db: AsyncSession = Depends(get_db)):
    """List all tasks with active pipelines."""
    active_statuses = ["created", "discovery", "investigate", "planning",
                       "implementation", "verification", "closeout"]
    result = await db.execute(
        select(Task)
        .where(Task.status.in_(active_statuses))
        .order_by(Task.created_at.desc())
        .limit(50)
    )
    tasks = result.scalars().all()

    pipelines = []
    for task in tasks:
        ctx = task.context or {}
        pipelines.append({
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "progress": task.progress,
            "worker_type": task.worker_type,
            "has_brief": bool(ctx.get("brief_id")),
            "has_plan": bool(ctx.get("plan_id")),
            "has_graph": bool(ctx.get("graph_id")),
            "has_dispatch": bool(ctx.get("dispatch_id")),
            "created_at": task.created_at.isoformat() if task.created_at else None,
        })

    return pipelines

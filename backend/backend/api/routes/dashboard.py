"""Dashboard API — aggregated stats for the WorkspaceView.

Provides a single endpoint that returns all the data the dashboard needs:
- Active missions count
- Workers online count
- Projects count
- Completed tasks count
- Recent activity
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import datetime, timezone

from backend.database.session import get_db
from storage.models import Task, Project
from agents.registry import AGENT_REGISTRY

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Aggregated dashboard stats for the WorkspaceView."""
    # Count active tasks
    active_statuses = ["created", "discovery", "investigate", "planning",
                       "implementation", "verification", "closeout"]
    active_result = await db.execute(
        select(func.count(Task.id)).where(Task.status.in_(active_statuses))
    )
    active_count = active_result.scalar() or 0

    # Count total tasks
    total_result = await db.execute(select(func.count(Task.id)))
    total_tasks = total_result.scalar() or 0

    # Count completed tasks
    completed_result = await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )
    completed_count = completed_result.scalar() or 0

    # Count projects
    project_result = await db.execute(select(func.count(Project.id)))
    project_count = project_result.scalar() or 0

    # BUG-13 FIX: Count actual agent roster (AGENT_REGISTRY = 15 agents),
    # not worker_runtime table rows (5 tier configs).
    worker_count = len(AGENT_REGISTRY)

    # Recent tasks (last 10)
    recent_result = await db.execute(
        select(Task)
        .order_by(Task.updated_at.desc())
        .limit(10)
    )
    recent_tasks = recent_result.scalars().all()

    activity = []
    for t in recent_tasks:
        status_label = {
            "completed": "Completed",
            "created": "Created",
            "planning": "Planning",
            "implementation": "Building",
            "verification": "Verifying",
        }.get(t.status, t.status.title())
        activity.append({
            "title": f"{status_label}: {t.title or 'Untitled'}",
            "time": t.updated_at.isoformat() if t.updated_at else t.created_at.isoformat() if t.created_at else "",
            "tone": "success" if t.status == "completed" else "primary",
            "task_id": t.id,
            "status": t.status,
        })

    return {
        "active_missions": active_count,
        "total_tasks": total_tasks,
        "completed_tasks": completed_count,
        "projects": project_count,
        "workers": worker_count,
        "activity": activity,
    }

"""Task listing routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.database.session import get_db
from storage.models import Task

router = APIRouter()

@router.get("/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    status: str = Query(None),
    project_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).order_by(Task.updated_at.desc())
    if status:
        query = query.where(Task.status == status)
    if project_id:
        query = query.where(Task.project_id == project_id)
    query = query.limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "type": t.type,
            "status": t.status,
            "worker_type": t.worker_type,
            "progress": t.progress,
            "project_id": t.project_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]

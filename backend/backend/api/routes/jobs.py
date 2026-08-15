from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database.session import get_db
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)])

from backend.services.job_scheduler import job_scheduler


# ── Job Scheduler Endpoints ──────────────────────────────────

@router.post("/jobs")
async def create_job(payload: dict, db: AsyncSession = Depends(get_db)):
    title = payload.get("title")
    job_type = payload.get("job_type")
    if not title or not job_type:
        raise HTTPException(status_code=400, detail="title and job_type are required")
    job = await job_scheduler.create_job(
        db,
        title=title,
        job_type=job_type,
        payload=payload.get("payload", {}),
        priority=payload.get("priority", 5),
        max_retries=payload.get("max_retries", 3),
        conversation_id=payload.get("conversation_id"),
        session_id=payload.get("session_id"),
    )
    return {
        "id": job.id, "title": job.title, "jobType": job.job_type,
        "priority": job.priority, "status": job.status, "progress": job.progress,
    }

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    jobs = await job_scheduler.list_jobs(db, status, job_type, limit)
    return [
        {
            "id": j.id, "title": j.title, "jobType": j.job_type,
            "priority": j.priority, "status": j.status, "progress": j.progress,
            "retryCount": j.retry_count, "maxRetries": j.max_retries,
            "errorMessage": j.error_message,
            "startedAt": j.started_at.isoformat() if j.started_at else None,
            "completedAt": j.completed_at.isoformat() if j.completed_at else None,
            "createdAt": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await job_scheduler.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    logs = await job_scheduler.get_logs(db, job_id)
    return {
        "id": job.id, "title": job.title, "jobType": job.job_type,
        "priority": job.priority, "status": job.status, "progress": job.progress,
        "result": job.result, "errorMessage": job.error_message,
        "retryCount": job.retry_count, "maxRetries": job.max_retries,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
        "logs": [{"level": l.level, "message": l.message, "createdAt": l.created_at.isoformat()} for l in logs],
    }

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = await job_scheduler.cancel_job(db, job_id)
        return {"id": job.id, "status": job.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = await job_scheduler.pause_job(db, job_id)
        return {"id": job.id, "status": job.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = await job_scheduler.resume_job(db, job_id)
        return {"id": job.id, "status": job.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

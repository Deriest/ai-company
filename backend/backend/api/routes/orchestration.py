from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import json

from backend.database.session import get_db

router = APIRouter()

from backend.schemas.orchestration_schemas import (
    OrchestrationSessionCreate, OrchestrationTaskCreate, ApprovalResolve
)
from backend.services.orchestrator_service import orchestrator_service
from backend.models.orchestration import OrchestrationSession, OrchestrationTask, OrchestrationApproval


# ── Orchestration Endpoints ──────────────────────────────────

@router.post("/orchestration/sessions")
async def create_orchestration_session(payload: OrchestrationSessionCreate, db: AsyncSession = Depends(get_db)):
    session = await orchestrator_service.create_session(db, payload.conversation_id, payload.mode)
    return {
        "id": session.id,
        "conversationId": session.conversation_id,
        "mode": session.mode,
        "status": session.status,
        "sharedContext": session.shared_context,
        "createdAt": session.created_at.isoformat() if session.created_at else None,
    }

@router.get("/orchestration/sessions")
async def list_orchestration_sessions(
    conversation_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    sessions = await orchestrator_service.list_sessions(db, conversation_id, status)
    return [
        {
            "id": s.id,
            "conversationId": s.conversation_id,
            "mode": s.mode,
            "status": s.status,
            "sharedContext": s.shared_context,
            "createdBy": s.created_by,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "completedAt": s.completed_at.isoformat() if s.completed_at else None,
            "createdAt": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]

@router.get("/orchestration/sessions/{session_id}")
async def get_orchestration_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await orchestrator_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    tasks = await orchestrator_service.get_tasks(db, session_id)
    approvals = await orchestrator_service.get_approvals(db, session_id)
    return {
        "id": session.id,
        "conversationId": session.conversation_id,
        "mode": session.mode,
        "status": session.status,
        "sharedContext": session.shared_context,
        "createdBy": session.created_by,
        "errorMessage": session.error_message,
        "startedAt": session.started_at.isoformat() if session.started_at else None,
        "completedAt": session.completed_at.isoformat() if session.completed_at else None,
        "tasks": [
            {
                "id": t.id,
                "workerRole": t.worker_role,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "dependsOn": t.depends_on or [],
                "sequenceOrder": t.sequence_order,
                "errorMessage": t.error_message,
                "startedAt": t.started_at.isoformat() if t.started_at else None,
                "completedAt": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
        "approvals": [
            {
                "id": a.id,
                "taskId": a.task_id,
                "status": a.status,
                "reason": a.reason,
                "reviewerNotes": a.reviewer_notes,
                "requestedAt": a.requested_at.isoformat() if a.requested_at else None,
                "resolvedAt": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in approvals
        ],
    }

@router.post("/orchestration/sessions/{session_id}/tasks")
async def add_orchestration_task(session_id: str, payload: OrchestrationTaskCreate, db: AsyncSession = Depends(get_db)):
    session = await orchestrator_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in ("pending", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot add tasks to session with status '{session.status}'")
    task = await orchestrator_service.add_task(
        db, session_id, payload.worker_role, payload.title, payload.description,
        payload.input_context, payload.depends_on,
    )
    return {
        "id": task.id,
        "workerRole": task.worker_role,
        "title": task.title,
        "status": task.status,
        "sequenceOrder": task.sequence_order,
    }

@router.post("/orchestration/sessions/{session_id}/execute")
async def execute_orchestration_session(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session = await orchestrator_service.execute_session(db, session_id)
        return {"id": session.id, "status": session.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/orchestration/sessions/{session_id}/cancel")
async def cancel_orchestration_session(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session = await orchestrator_service.cancel_session(db, session_id)
        return {"id": session.id, "status": session.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/orchestration/tasks/{task_id}/approval")
async def request_task_approval(task_id: str, reason: str = Query(""), db: AsyncSession = Depends(get_db)):
    approval = await orchestrator_service.request_approval(db, task_id, reason)
    return {"id": approval.id, "status": approval.status}

@router.patch("/orchestration/approvals/{approval_id}")
async def resolve_approval(approval_id: str, payload: ApprovalResolve, db: AsyncSession = Depends(get_db)):
    try:
        approval = await orchestrator_service.resolve_approval(db, approval_id, payload.approved, payload.notes)
        return {"id": approval.id, "status": approval.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

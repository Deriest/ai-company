from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import json

from backend.database.session import get_db

router = APIRouter(dependencies=[Depends(require_current_user)]))

from backend.services.orchestrator_service import orchestrator_service, MalformedDefinitionError
from backend.models.orchestration import WorkflowDefinition, Checkpoint


# ── Workflow Definition Endpoints ─────────────────────────────

@router.post("/workflows")
async def create_workflow(payload: dict, db: AsyncSession = Depends(get_db)):
    name = payload.get("name")
    dag = payload.get("dag")
    if not name or not dag:
        raise HTTPException(status_code=400, detail="name and dag are required")
    wf = await orchestrator_service.create_workflow(
        db, name=name, dag=dag, description=payload.get("description", "")
    )
    return {"id": wf.id, "name": wf.name, "description": wf.description, "dag": wf.dag, "version": wf.version}

@router.get("/workflows")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    workflows = await orchestrator_service.list_workflows(db)
    return [
        {"id": w.id, "name": w.name, "description": w.description, "dag": w.dag, "version": w.version}
        for w in workflows
    ]

@router.get("/workflows/{wf_id}")
async def get_workflow(wf_id: str, db: AsyncSession = Depends(get_db)):
    wf = await orchestrator_service.get_workflow(db, wf_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"id": wf.id, "name": wf.name, "description": wf.description, "dag": wf.dag, "version": wf.version}

@router.post("/workflows/{wf_id}/instantiate")
async def instantiate_workflow(wf_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    # QA-R5 FIX: a missing conversation_id previously raised KeyError → 500.
    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        raise HTTPException(status_code=400, detail="missing conversation_id")
    try:
        session = await orchestrator_service.instantiate_workflow(db, wf_id, conversation_id)
        return {"id": session.id, "status": session.status, "mode": session.mode}
    except MalformedDefinitionError as e:
        # QA-R5 FIX: malformed DAG nodes/edges mapped to 400 instead of a raw 500.
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/orchestration/sessions/{session_id}/resume")
async def resume_orchestration(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session = await orchestrator_service.resume_from_checkpoint(db, session_id)
        return {"id": session.id, "status": session.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestration/sessions/{session_id}/checkpoints")
async def list_checkpoints(session_id: str, db: AsyncSession = Depends(get_db)):
    checkpoints = await orchestrator_service.get_checkpoints(db, session_id)
    return [
        {"id": c.id, "taskId": c.task_id, "state": c.state, "createdAt": c.created_at.isoformat()}
        for c in checkpoints
    ]

"""Worker routes — runtime management, worker CRUD, tool execution."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.session import get_db
from backend.models.schema import WorkerRuntime
from backend.schemas.api_models_v2 import (
    WorkerRuntimeUpdate, WorkerRuntimeResponse, WorkerMetricsResponse,
)
from backend.schemas.ai_runtime_schemas import ToolExecuteRequest
from backend.services.worker_runtime_service import worker_runtime_service, WorkerMetrics
from backend.services.tool_dispatcher import tool_dispatcher

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /runtime/workers
# ---------------------------------------------------------------------------

@router.get("/runtime/workers", response_model=List[WorkerRuntimeResponse])
async def list_worker_runtimes(db: AsyncSession = Depends(get_db)):
    runtimes = await worker_runtime_service.get_all_workers(db)
    all_metrics = await worker_runtime_service.get_all_metrics(db)

    responses = []
    for r in runtimes:
        m = all_metrics.get(r.role, WorkerMetrics(role=r.role))
        responses.append(WorkerRuntimeResponse(
            id=r.id,
            role=r.role,
            label=r.label or r.role,
            description=r.description or "",
            systemPrompt=r.system_prompt or "",
            providerId=r.provider_id or "",
            modelId=r.model_id or "",
            temperature=r.temperature,
            topP=r.top_p,
            maxOutputTokens=r.max_output_tokens,
            isEnabled=r.is_enabled if r.is_enabled is not None else True,
            metrics=WorkerMetricsResponse(
                role=m.role,
                totalExecutions=m.total_executions,
                completed=m.completed,
                errors=m.errors,
                avgLatencyMs=m.avg_latency_ms,
                lastExecutedAt=m.last_executed_at,
                currentlyRunning=m.currently_running,
            ),
        ))

    return responses


# ---------------------------------------------------------------------------
# PATCH /runtime/workers/{role}
# ---------------------------------------------------------------------------

@router.patch("/runtime/workers/{role}", response_model=WorkerRuntimeResponse)
async def update_worker_runtime(role: str, update: WorkerRuntimeUpdate, db: AsyncSession = Depends(get_db)):
    runtime = await worker_runtime_service.get_worker(db, role)

    if not runtime:
        raise HTTPException(status_code=404, detail=f"Worker '{role}' not found")

    if update.providerId is not None: runtime.provider_id = update.providerId
    if update.modelId is not None: runtime.model_id = update.modelId
    if update.temperature is not None: runtime.temperature = update.temperature
    if update.topP is not None: runtime.top_p = update.topP
    if update.maxOutputTokens is not None: runtime.max_output_tokens = update.maxOutputTokens
    if update.systemPrompt is not None: runtime.system_prompt = update.systemPrompt
    if update.isEnabled is not None: runtime.is_enabled = update.isEnabled

    await db.commit()
    await db.refresh(runtime)

    metrics = await worker_runtime_service.get_metrics(db, role)
    return WorkerRuntimeResponse(
        id=runtime.id,
        role=runtime.role,
        label=runtime.label or runtime.role,
        description=runtime.description or "",
        systemPrompt=runtime.system_prompt or "",
        providerId=runtime.provider_id or "",
        modelId=runtime.model_id or "",
        temperature=runtime.temperature,
        topP=runtime.top_p,
        maxOutputTokens=runtime.max_output_tokens,
        isEnabled=runtime.is_enabled if runtime.is_enabled is not None else True,
        metrics=WorkerMetricsResponse(
            role=metrics.role,
            totalExecutions=metrics.total_executions,
            completed=metrics.completed,
            errors=metrics.errors,
            avgLatencyMs=metrics.avg_latency_ms,
            lastExecutedAt=metrics.last_executed_at,
            currentlyRunning=metrics.currently_running,
        ),
    )


# ---------------------------------------------------------------------------
# GET /workers
# ---------------------------------------------------------------------------

@router.get("/workers")
async def list_workers(db: AsyncSession = Depends(get_db)):
    workers = await worker_runtime_service.get_all_workers(db)
    return [
        {
            "id": w.id,
            "role": w.role,
            "providerId": w.provider_id or "",
            "modelId": w.model_id or "",
            "temperature": w.temperature,
            "topP": w.top_p,
            "maxOutputTokens": w.max_output_tokens
        }
        for w in workers
    ]


# ---------------------------------------------------------------------------
# PATCH /workers/{id}
# ---------------------------------------------------------------------------

@router.patch("/workers/{id}")
async def update_worker_by_id(id: str, payload: WorkerRuntimeUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(WorkerRuntime).where(WorkerRuntime.id == id))
    w = res.scalars().first()
    if not w:
        raise HTTPException(status_code=404, detail="Worker not found")

    if payload.providerId is not None: w.provider_id = payload.providerId
    if payload.modelId is not None: w.model_id = payload.modelId
    if payload.temperature is not None: w.temperature = payload.temperature
    if payload.topP is not None: w.top_p = payload.topP
    if payload.maxOutputTokens is not None: w.max_output_tokens = payload.maxOutputTokens

    await db.commit()
    await db.refresh(w)
    return {
        "id": w.id,
        "role": w.role,
        "providerId": w.provider_id or "",
        "modelId": w.model_id or "",
        "temperature": w.temperature,
        "topP": w.top_p,
        "maxOutputTokens": w.max_output_tokens
    }


# ---------------------------------------------------------------------------
# POST /tools/execute
# ---------------------------------------------------------------------------

@router.post("/tools/execute")
async def execute_tool(payload: ToolExecuteRequest):
    return await tool_dispatcher.execute(payload.tool_name, payload.arguments)

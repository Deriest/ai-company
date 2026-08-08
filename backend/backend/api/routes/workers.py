"""Worker routes — runtime management, worker CRUD, tool execution."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.session import get_db
from backend.api.dependencies import require_current_user
from backend.models.schema import WorkerRuntime
from backend.schemas.api_models_v2 import (
    WorkerRuntimeUpdate, WorkerRuntimeResponse, WorkerMetricsResponse,
)
from backend.schemas.ai_runtime_schemas import ToolExecuteRequest
from backend.services.worker_runtime_service import worker_runtime_service, WorkerMetrics
from backend.services.tool_dispatcher import tool_dispatcher

logger = logging.getLogger(__name__)

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
async def update_worker_runtime(
    role: str,
    update: WorkerRuntimeUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    runtime = await worker_runtime_service.get_worker(db, role)

    # BUG-03 FIX: Auto-create worker_runtime row if role doesn't exist yet
    # (e.g. "sprinter" is not in WORKER_DEFAULTS but is a valid tier role)
    if not runtime:
        runtime = WorkerRuntime(
            role=role.lower(),
            label=role.title(),
            description=f"Auto-created worker runtime for {role}",
            system_prompt="",
            temperature=0.4,
            top_p=1.0,
            is_enabled=True,
        )
        db.add(runtime)
        await db.commit()
        await db.refresh(runtime)

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
async def update_worker_by_id(
    id: str,
    payload: WorkerRuntimeUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
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

# Allowlist for the unauthenticated /tools/execute endpoint (P0 #2).
# Defense-in-depth: tool_dispatcher already rejects unknown tools, but the
# endpoint must not forward arbitrary tool names — validate before dispatch.
_ALLOWED_EXECUTE_TOOLS = {"read_file", "write_file", "list_directory", "search_workspace", "current_time"}


@router.post("/tools/execute")
async def execute_tool(payload: ToolExecuteRequest, _auth: str = Depends(require_current_user)):
    """Execute a tool only if it is on the allowlist.

    Rejects unknown tools with a clean 400 and never surfaces raw exceptions.
    """
    tool_name = (payload.tool_name or "").strip().lower()
    if tool_name not in _ALLOWED_EXECUTE_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
    try:
        result = await tool_dispatcher.execute(tool_name, payload.arguments or {})
    except Exception as e:
        logger.warning(f"Tool execution failed for {tool_name}: {e}")
        raise HTTPException(status_code=500, detail="Tool execution failed")
    if result.get("error"):
        # Log the raw error server-side; return a clean result to the client.
        logger.warning(f"Tool {tool_name} execution error: {result['error']}")
        return {"result": None, "error": "Tool execution failed", "execution_time_ms": result.get("execution_time_ms", 0)}
    return result




# ---------------------------------------------------------------------------
# GET /runtime/workforce — Office Floor Live Status
# ---------------------------------------------------------------------------
from storage.models import Lease, LeaseStatus, Task
from sqlalchemy import select, or_, case
from sqlalchemy import func as sqlfunc

@router.get("/runtime/workforce")
async def list_workforce(db: AsyncSession = Depends(get_db)):
    """Returns the 15 canonical workers with live lease status for the office floor."""
    # Fetch all canonical agent IDs from registry
    from agents.registry import AGENT_REGISTRY
    from storage.models import Task
    
    # Query active leases joined with task info so the office floor can show
    # WHAT each busy worker is working on (title, phase, progress).
    active_lease_result = await db.execute(
        select(
            Lease.worker_type,
            Lease.phase,
            Lease.task_id,
            Task.title,
            Task.progress,
        )
        .join(Task, Lease.task_id == Task.id)
        .where(Lease.status == LeaseStatus.ACTIVE.value)
    )
    # Pick one (most recent) active task per worker_type
    active_task_by_worker: dict[str, dict] = {}
    for row in active_lease_result.all():
        wtype = row[0]
        if wtype not in active_task_by_worker:
            active_task_by_worker[wtype] = {
                "phase": row[1],
                "taskId": row[2],
                "taskTitle": row[3] or "",
                "progress": row[4] or 0,
            }
    
    responses = []
    # Aggregate running executions per tier ONCE (avoid N+1 per agent)
    from backend.models.ai_runtime import WorkerExecution
    running_res = await db.execute(
        select(WorkerExecution.worker_role, sqlfunc.count(WorkerExecution.id))
        .where(WorkerExecution.status == "running")
        .group_by(WorkerExecution.worker_role)
    )
    running_by_role = {row[0]: row[1] for row in running_res.all()}

    # BE-1: Pre-fetch runtime model config per role ONCE (avoid N queries per agent).
    # Roles in worker_runtime may use tier names (thinker/crafter) or canonical
    # agent ids, so map both keys.
    runtimes = await worker_runtime_service.get_all_workers(db)
    model_by_role: dict[str, str | None] = {}
    for rt in runtimes:
        if rt.model_id:
            model_by_role[rt.role] = rt.model_id

    for agent_id, agent in sorted(AGENT_REGISTRY.items()):
        active_info = active_task_by_worker.get(agent_id)
        currently_running = active_info is not None

        # Resolve configured model: exact agent id first, then its tier role.
        tier = agent.model.tier.lower()
        model_id = model_by_role.get(agent_id) or model_by_role.get(tier)

        responses.append({
            "id": agent.identity.id,
            "name": agent.identity.name,
            "role": agent.identity.role,
            "department": agent.identity.department,
            "tier": agent.model.tier,
            "phase": agent.identity.phase,
            "currentlyRunning": currently_running,
            "activeTaskInfo": active_info,  # phase, title, progress of current work
            "totalRunningInTier": running_by_role.get(tier, 0),
            "modelId": model_id,  # configured runtime model, or None if unset
            "isEnabled": True,
        })
    
    return responses

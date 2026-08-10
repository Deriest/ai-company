"""Agent execution API — run workers with real tool execution (OpenCode-style).

This is the core API that enables workers to actually DO things:
- Read files
- Write code
- Run tests
- Search codebases
- Execute shell commands

Not just chat.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging

from backend.database.session import get_db
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)]))

logger = logging.getLogger("aic.agent")


@router.post("/agent/run")
async def run_agent(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Run an AI agent with real tool execution.
    
    Body:
        worker_type: str — agent type (backend, frontend, qa, architect, etc.)
        prompt: str — task description
        system_prompt: str — optional custom system prompt
        model_tier: str — thinker/crafter/sprinter (default: crafter)
        workspace: str — workspace root path (default: ".")
    """
    worker_type = payload.get("worker_type", "backend")
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system_prompt", "")
    model_tier = payload.get("model_tier", "crafter")
    workspace = payload.get("workspace", ".")
    
    if not prompt:
        logger.warning("Agent run rejected: prompt is empty (worker_type=%s)", worker_type)
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE, AGENT_RUN_QUEUE_TIMEOUT, AgentRunner
    runner = AgentRunner(workspace_root=workspace)
    logger.info(
        "Agent run started: worker_type=%s model_tier=%s", worker_type, model_tier,
    )
    
    async def event_stream():
        try:
            # QA-R5 FIX: cap concurrent agent runs — same shared semaphore as
            # /chat/execute, so the two entry points cannot collectively exceed
            # the limit. Excess runs queue (awaited) instead of overloading the
            # box with parallel LLM streams / subprocesses.
            # Round-6 FIX: emit a "queued" status before waiting so the UI shows
            # the run is queued instead of silently hanging, and bound the wait
            # with a generous timeout (clean error on timeout).
            semaphore_acquired = False
            try:
                yield f"data: {json.dumps({'type': 'status', 'status': 'queued', 'worker': worker_type})}\n\n"
                await asyncio.wait_for(AGENT_RUN_SEMAPHORE.acquire(), timeout=AGENT_RUN_QUEUE_TIMEOUT)
                semaphore_acquired = True
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Agent queue is full. Try again in a moment.'})}\n\n"
                return
            try:
                async for event in runner.run_agent(
                    worker_type, prompt, system_prompt, model_tier,
                    db=db,  # BUG-17 FIX: pass db so MCP tools can be fetched
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                if semaphore_acquired:
                    AGENT_RUN_SEMAPHORE.release()
        except Exception as e:
            # F14 FIX: a mid-stream exception would otherwise kill the SSE
            # generator with no structured error (renderer would fire onDone
            # with a truncated response). Surface a proper error event instead.
            # Round-6 FIX: log the raw error server-side, keep the client-facing
            # message fixed and friendly.
            logger.error("Agent run failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Agent execution failed. Please try again.'})}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/agent/run-sync")
async def run_agent_sync(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Run agent synchronously (wait for completion).
    
    Same parameters as /agent/run but returns final result.
    """
    worker_type = payload.get("worker_type", "backend")
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system_prompt", "")
    model_tier = payload.get("model_tier", "crafter")
    workspace = payload.get("workspace", ".")
    
    if not prompt:
        logger.warning("Agent run-sync rejected: prompt is empty (worker_type=%s)", worker_type)
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    from backend.services.agent_runner import AGENT_RUN_SEMAPHORE, AGENT_RUN_QUEUE_TIMEOUT, run_worker_with_tools
    logger.info(
        "Agent run-sync started: worker_type=%s model_tier=%s", worker_type, model_tier,
    )
    # QA-R5 FIX: same global concurrency cap as /agent/run and /chat/execute.
    # Round-6 FIX: bound the wait so a full queue degrades to a clean 503
    # instead of hanging the request forever.
    try:
        await asyncio.wait_for(AGENT_RUN_SEMAPHORE.acquire(), timeout=AGENT_RUN_QUEUE_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("Agent run-sync rejected: queue full for > %ss", AGENT_RUN_QUEUE_TIMEOUT)
        raise HTTPException(status_code=503, detail="Agent queue is full. Try again in a moment.")
    try:
        result = await run_worker_with_tools(
            worker_type, prompt, system_prompt, workspace, model_tier,
            db=db,  # BUG-17 FIX: pass db so MCP tools can be fetched
        )
    finally:
        AGENT_RUN_SEMAPHORE.release()
    logger.info(
        "Agent run-sync finished: worker_type=%s success=%s", worker_type, result.get("success"),
    )
    return result

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
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from backend.database.session import get_db

router = APIRouter()


@router.post("/agent/run")
async def run_agent(payload: dict, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    from backend.services.agent_runner import AgentRunner
    runner = AgentRunner(workspace_root=workspace)
    
    async def event_stream():
        async for event in runner.run_agent(worker_type, prompt, system_prompt, model_tier):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/agent/run-sync")
async def run_agent_sync(payload: dict, db: AsyncSession = Depends(get_db)):
    """Run agent synchronously (wait for completion).
    
    Same parameters as /agent/run but returns final result.
    """
    worker_type = payload.get("worker_type", "backend")
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system_prompt", "")
    model_tier = payload.get("model_tier", "crafter")
    workspace = payload.get("workspace", ".")
    
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    from backend.services.agent_runner import run_worker_with_tools
    result = await run_worker_with_tools(worker_type, prompt, system_prompt, workspace, model_tier)
    return result

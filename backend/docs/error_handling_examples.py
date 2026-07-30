"""Example implementations showing how to apply error handling improvements.

These are reference implementations demonstrating the recommended patterns.
Copy these patterns to actual route files during implementation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from storage.models import Project, Task, TaskStatus, User, Conversation
from auth.dependencies import get_current_user
from backend.validation import (
    validate_enum_value,
    validate_positive_integer,
    validate_resource_exists,
    validate_resource_ownership,
    validate_string_length,
    string_length_validator,
    non_empty_string_validator,
    BatchAction,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# Example 1: Fixed Projects Route with Authorization
# ═══════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}")
async def get_project_fixed(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now checks project ownership before returning."""
    result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id  # ✅ Authorization check added
        )
    )
    project = result.scalar_one_or_none()
    
    # Use validation helper
    validate_resource_exists(project, "Project", project_id)
    
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "repo_path": project.repo_path,
        "status": project.status,
        "owner_id": project.owner_id,
    }


@router.get("/projects/{project_id}/tasks")
async def get_project_tasks_fixed(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now verifies user owns project before returning tasks."""
    # First verify project ownership
    project_result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id  # ✅ Authorization check
        )
    )
    project = project_result.scalar_one_or_none()
    validate_resource_exists(project, "Project", project_id)
    
    # Now fetch tasks
    result = await session.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "title": t.title,
            "type": t.type,
            "status": t.status,
            "progress": t.progress,
            "worker_type": t.worker_type,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


# ═══════════════════════════════════════════════════════════════════
# Example 2: Fixed Task Routes with Enum Validation
# ═══════════════════════════════════════════════════════════════════

@router.get("/tasks")
async def list_tasks_fixed(
    project_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),  # ✅ Added bounds
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now validates status enum and limit bounds."""
    # Validate status is a valid enum value
    validate_enum_value(status, TaskStatus, "status")  # ✅ Enum validation
    
    # Validate limit
    validate_positive_integer(limit, "limit", max_value=500)  # ✅ Range validation
    
    # If project_id provided, verify it exists and user has access
    if project_id:
        project_result = await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == user.id
            )
        )
        project = project_result.scalar_one_or_none()
        validate_resource_exists(project, "Project", project_id)  # ✅ Existence check
    
    query = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)

    result = await session.execute(query)
    tasks = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "type": t.type,
            "status": t.status,
            "progress": t.progress,
            "worker_type": t.worker_type,
            "project_id": t.project_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task_fixed(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now checks task ownership and project access before dispatching."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    validate_resource_exists(task, "Task", task_id)
    
    # ✅ Verify user owns the project this task belongs to
    project_result = await session.execute(
        select(Project).where(
            Project.id == task.project_id,
            Project.owner_id == user.id
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Task not found or access denied",
                "code": "TASK_NOT_FOUND",
            }
        )
    
    if task.status not in ("created", "blocked"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Task cannot be dispatched from current status",
                "code": "INVALID_TASK_STATUS",
                "details": {
                    "current_status": task.status,
                    "allowed_statuses": ["created", "blocked"],
                },
            }
        )
    
    # Dispatch logic...
    return {"message": "Task dispatched", "task_id": task_id}


# ═══════════════════════════════════════════════════════════════════
# Example 3: Fixed Conversation Routes with Enum and Length Validation
# ═══════════════════════════════════════════════════════════════════

class BatchRequestFixed(BaseModel):
    """FIXED: Uses enum instead of string for action."""
    action: BatchAction  # ✅ Changed from str to enum
    ids: list[str]


class MessageSendFixed(BaseModel):
    """FIXED: Added content length validation."""
    content: str
    
    # ✅ Validate content length (max 50KB)
    _validate_content_length = validator('content', allow_reuse=True)(
        string_length_validator('content', min_length=1, max_length=50000)
    )
    
    # ✅ Ensure content is not empty/whitespace
    _validate_content_not_empty = validator('content', allow_reuse=True)(
        non_empty_string_validator('content')
    )


@router.post("/conversations/batch")
async def batch_conversations_fixed(
    req: BatchRequestFixed,  # ✅ Now uses enum
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Uses enum for action validation."""
    # Fetch only user's own conversations from the requested IDs
    result = await session.execute(
        select(Conversation).where(
            Conversation.id.in_(req.ids),
            Conversation.user_id == user.id  # ✅ Authorization check
        )
    )
    convs = result.scalars().all()

    if req.action == BatchAction.DELETE:
        # Delete logic...
        pass
    elif req.action == BatchAction.ARCHIVE:
        # Archive logic...
        pass
    elif req.action == BatchAction.UNARCHIVE:
        # Unarchive logic...
        pass
    
    return {"action": req.action.value, "processed": len(convs)}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages_fixed(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now verifies conversation ownership before returning messages."""
    # ✅ First verify user owns this conversation
    conv_result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id  # Authorization check
        )
    )
    conv = conv_result.scalar_one_or_none()
    validate_resource_exists(conv, "Conversation", conversation_id)
    
    # Now safe to fetch messages
    from storage.models import Message
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "metadata": m.meta if hasattr(m, 'meta') and m.meta else {},  # ✅ NULL check
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


# ═══════════════════════════════════════════════════════════════════
# Example 4: Fixed LLM Provider Test with Error Classification
# ═══════════════════════════════════════════════════════════════════

@router.post("/llm/providers/{provider_id}/test")
async def test_provider_fixed(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """FIXED: Now classifies different types of provider errors."""
    from storage.models import LLMProviderConfig
    from llm.provider import ProviderConfig, LLMProvider
    import httpx
    
    result = await session.execute(
        select(LLMProviderConfig).where(LLMProviderConfig.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    validate_resource_exists(provider, "Provider", provider_id)

    cfg = ProviderConfig(
        name=provider.name,
        base_url=provider.base_url,
        api_key=provider.api_key,
        models=provider.models or {},
    )
    test_llm = LLMProvider(cfg)

    try:
        models = await test_llm.list_models()
        await test_llm.close()
        return {
            "status": "ok",
            "models": [m.get("id", "") for m in models[:20]],
            "count": len(models),
        }
    except httpx.TimeoutException:
        # ✅ Specific error for timeout
        await test_llm.close()
        return {
            "status": "error",
            "error": "Connection to provider timed out",
            "code": "TIMEOUT",
            "details": {"timeout_seconds": cfg.timeout if hasattr(cfg, 'timeout') else 120},
        }
    except httpx.ConnectError as e:
        # ✅ Specific error for connection failure
        await test_llm.close()
        return {
            "status": "error",
            "error": "Cannot connect to provider",
            "code": "CONNECTION_FAILED",
            "details": {"base_url": provider.base_url},
        }
    except httpx.HTTPStatusError as e:
        # ✅ Specific error for HTTP errors (401, 403, etc.)
        await test_llm.close()
        status_code = e.response.status_code
        if status_code == 401:
            error_msg = "Invalid API key or authentication failed"
            code = "AUTH_FAILED"
        elif status_code == 403:
            error_msg = "Access forbidden. Check API key permissions"
            code = "FORBIDDEN"
        else:
            error_msg = f"Provider returned HTTP {status_code}"
            code = "HTTP_ERROR"
        
        return {
            "status": "error",
            "error": error_msg,
            "code": code,
            "details": {"status_code": status_code},
        }
    except Exception as e:
        # ✅ Catch-all with more context
        await test_llm.close()
        return {
            "status": "error",
            "error": "Provider test failed",
            "code": "UNKNOWN_ERROR",
            "details": {"error_type": type(e).__name__},
        }


# ═══════════════════════════════════════════════════════════════════
# Example 5: Fixed Background Task with Status Update on Failure
# ═══════════════════════════════════════════════════════════════════

async def _dispatch_created_task_fixed(task_id: str):
    """FIXED: Updates task status on failure."""
    import asyncio as _aio
    import logging
    from storage.database import async_session as _db
    from runtime.executor import execute_task
    
    logger = logging.getLogger("aic.dispatch")
    
    await _aio.sleep(2)
    try:
        async with _db() as s:
            result = await s.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.warning(f"Dispatch bg: task {task_id} not found")
                return
            
            task_code = f"TASK-{task.id[:8].upper()}"
            logger.info(f"Dispatch bg: starting {task_code} ({task.worker_type})")
            
            exec_result = await execute_task(s, task)
            await s.commit()
            
            logger.info(f"Dispatch bg: {task_code} complete — success={exec_result.get('success')}")
    
    except Exception as e:
        logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
        
        # ✅ UPDATE TASK STATUS ON FAILURE
        try:
            async with _db() as s:
                result = await s.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = f"Dispatch failed: {str(e)[:500]}"  # Truncate long errors
                    await s.commit()
                    logger.info(f"Task {task_id} marked as failed")
        except Exception as update_error:
            logger.error(f"Failed to update task status: {update_error}")

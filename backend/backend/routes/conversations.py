"""AIC Platform — Conversations API Routes.

DEPRECATED: These routes are legacy and will be removed in a future version.
The primary chat path is now /chat/stream in backend/api/routes/core.py.
These routes are kept for backward compatibility only.

Full conversation lifecycle: create, rename, archive, delete, clear history.
SSE streaming for real-time chat responses.
"""
import json
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from storage.models import Conversation, Message, Project, Task, DiscoverySession
from backend.models.conversation import Attachment
from conversation.engine import ConversationEngine, LLMUnavailableError, LLMInferenceError

logger = logging.getLogger("aic.chat")

router = APIRouter()


class ConversationCreate(BaseModel):
    project_id: str | None = None
    title: str = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str | None = None
    status: str | None = None  # active, archived


class BatchRequest(BaseModel):
    action: str  # delete, archive, unarchive
    ids: list[str]


class MessageSend(BaseModel):
    content: str


@router.get("")
async def list_conversations(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import func
    query = select(Conversation)
    convs = (await session.execute(query.order_by(Conversation.updated_at.desc()))).scalars().all()
    # Get real message counts from DB
    conv_ids = [c.id for c in convs]
    msg_counts: dict[str, int] = {}
    if conv_ids:
        count_q = (
            select(Message.conversation_id, func.count())
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        rows = (await session.execute(count_q)).all()
        msg_counts = {row[0]: row[1] for row in rows}
    # Filter by status stored in context
    result = []
    for c in convs:
        ctx = c.context or {}
        conv_status = ctx.get("status", "active")
        if status and conv_status != status:
            continue
        result.append({
            "id": c.id,
            "title": c.title,
            "project_id": c.project_id,
            "status": conv_status,
            "message_count": msg_counts.get(c.id, 0),
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@router.post("/batch")
async def batch_conversations(
    req: BatchRequest,
    session: AsyncSession = Depends(get_session),
):
    if req.action not in ("delete", "archive", "unarchive"):
        raise HTTPException(400, "Invalid action")

    # Fetch only user's own conversations from the requested IDs
    result = await session.execute(
        select(Conversation).where(Conversation.id.in_(req.ids))
    )
    convs = result.scalars().all()

    if req.action == "delete":
        conv_ids = [c.id for c in convs]
        if conv_ids:
            await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
            await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
            await session.commit()
    else:
        target_status = "archived" if req.action == "archive" else "active"
        for conv in convs:
            ctx = conv.context or {}
            ctx["status"] = target_status
            conv.context = ctx
        await session.commit()

    return {"action": req.action, "processed": len(convs)}


@router.post("")
async def create_conversation(
    req: ConversationCreate,
    session: AsyncSession = Depends(get_session),
):
    conv = Conversation(
        project_id=req.project_id,
        title=req.title,
        context={"project_id": req.project_id, "status": "active", "message_count": 0} if req.project_id
        else {"status": "active", "message_count": 0},
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return {"id": conv.id, "title": conv.title, "project_id": conv.project_id, "status": "active"}


@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    req: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    if req.title is not None:
        conv.title = req.title
    if req.status is not None:
        ctx = conv.context or {}
        ctx["status"] = req.status
        conv.context = ctx

    await session.commit()
    return {"id": conv.id, "title": conv.title, "status": (conv.context or {}).get("status", "active")}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Delete all messages first
    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
    # FIX (round-5): discovery_sessions reference the conversation with no
    # cascade, and Attachment rows have no FK — delete both explicitly so the
    # ORM delete of the conversation does not hit a NOT NULL/FK violation.
    await session.execute(delete(DiscoverySession).where(DiscoverySession.conversation_id == conversation_id))
    await session.execute(delete(Attachment).where(Attachment.message_id.in_(
        select(Message.id).where(Message.conversation_id == conversation_id)
    )))
    await session.delete(conv)
    await session.commit()
    return {"deleted": True, "id": conversation_id}


@router.delete("/{conversation_id}/messages")
async def clear_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
    ctx = conv.context or {}
    ctx["message_count"] = 0
    conv.context = ctx
    await session.commit()
    return {"cleared": True, "id": conversation_id}


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    ctx = conv.context or {}
    return {
        "id": conv.id,
        "title": conv.title,
        "project_id": conv.project_id,
        "status": ctx.get("status", "active"),
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
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
            "metadata": m.meta if hasattr(m, 'meta') else {},
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: MessageSend,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    import time as _time
    _t0 = _time.monotonic()
    try:
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, req.content)
        await session.commit()
        _elapsed = _time.monotonic() - _t0
        _meta = response.meta if hasattr(response, 'meta') else {}
        logger.info(f"[CHAT] conv={conversation_id[:8]} provider={_meta.get('provider','?')} model={_meta.get('model','?')} "
                     f"tokens={_meta.get('total_tokens',0)} duration={_elapsed:.1f}s")
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(500, f"Chat processing error: {str(e)}")

    # Auto-dispatch task in background if one was created
    task_id = (response.meta or {}).get("task_id") if hasattr(response, "meta") else None
    if task_id:
        background_tasks.add_task(_dispatch_created_task, task_id)

    return {
        "response": response.content,
        "intent": response.intent,
        "metadata": response.meta if hasattr(response, 'meta') else {},
    }


@router.post("/{conversation_id}/stream")
@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    req: MessageSend,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """SSE streaming endpoint for chat."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    import time as _time
    _t0 = _time.monotonic()
    try:
        engine = ConversationEngine(session)
        response = await engine.process_message(conv, req.content)
        await session.commit()
        _elapsed = _time.monotonic() - _t0
        _meta = response.meta if hasattr(response, 'meta') else {}
        logger.info(f"[STREAM] conv={conversation_id[:8]} provider={_meta.get('provider','?')} model={_meta.get('model','?')} "
                     f"tokens={_meta.get('total_tokens',0)} duration={_elapsed:.1f}s")
    except LLMUnavailableError as e:
        await session.rollback()
        raise HTTPException(503, str(e))
    except LLMInferenceError as e:
        await session.rollback()
        raise HTTPException(502, str(e))
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(500, f"Internal error: {str(e)}")

    # Auto-dispatch task in background if one was created
    task_id = (response.meta or {}).get("task_id") if hasattr(response, "meta") else None
    if task_id:
        background_tasks.add_task(_dispatch_created_task, task_id)

    async def event_generator():
        content = response.content
        metadata = response.meta if hasattr(response, 'meta') else {}
        chunk_size = 20  # characters per chunk
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'intent': response.intent, 'metadata': metadata})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _dispatch_created_task(task_id: str):
    """Background: dispatch a newly created task through the worker pipeline."""
    import asyncio as _aio
    from runtime.executor import execute_task
    await _aio.sleep(2)
    try:
        from storage.database import async_session as _db
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

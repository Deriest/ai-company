"""AIC Platform — Conversations API Routes.

DEPRECATED: These routes are legacy and will be removed in a future version.
The primary chat path is now /chat/stream in backend/api/routes/core.py.
These routes are kept for backward compatibility only.

Full conversation lifecycle: create, rename, archive, delete, clear history.
SSE streaming for real-time chat responses.
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from backend.api.dependencies import require_current_user
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
    _auth: str = Depends(require_current_user),
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
            from sqlalchemy import bindparam

            async def _del(sql: str):
                """Run a raw DELETE with an expanding :cids IN-list."""
                await session.execute(
                    text(sql).bindparams(bindparam("cids", expanding=True)),
                    {"cids": conv_ids},
                )

            # Same FK cascade as the single-delete route, bottom-up:
            # lessons_learned <- engineering_reports <- engineering_briefs
            #   <- discovery_sessions <- conversations, plus the
            # plans/graphs/dispatch/planning/verification chains off briefs.
            await _del(
                "DELETE FROM lessons_learned WHERE report_id IN ("
                "SELECT id FROM engineering_reports WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids)))"
            )
            await _del(
                "DELETE FROM engineering_reports WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids))"
            )
            await _del(
                "DELETE FROM dispatch_sessions WHERE graph_id IN ("
                "SELECT tg.id FROM task_graphs tg JOIN engineering_plans ep ON tg.plan_id = ep.id "
                "WHERE ep.brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids)))"
            )
            await _del(
                "DELETE FROM task_graphs WHERE plan_id IN ("
                "SELECT id FROM engineering_plans WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids)))"
            )
            await _del(
                "DELETE FROM engineering_plans WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids))"
            )
            await _del(
                "DELETE FROM planning_sessions WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids))"
            )
            await _del(
                "DELETE FROM verification_sessions WHERE brief_id IN ("
                "SELECT id FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids))"
            )
            await _del(
                "DELETE FROM engineering_briefs WHERE discovery_session_id IN ("
                "SELECT id FROM discovery_sessions WHERE task_conversation_ref IN :cids)"
            )
            # Attachment rows + their binary files
            att_res = await session.execute(
                select(Attachment.id).where(Attachment.message_id.in_(
                    select(Message.id).where(Message.conversation_id.in_(conv_ids))
                ))
            )
            att_ids = [row[0] for row in att_res.all()]
            await session.execute(delete(Attachment).where(Attachment.message_id.in_(
                select(Message.id).where(Message.conversation_id.in_(conv_ids))
            )))
            await _del("DELETE FROM discovery_sessions WHERE task_conversation_ref IN :cids")
            await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
            await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
            await session.commit()
            from backend.services.attachment_store import delete_attachment
            for att_id in att_ids:
                delete_attachment(att_id)
            # Keep FTS index in sync with deleted conversations
            from backend.services.search_service import remove_fts_by_conversation
            for cid in conv_ids:
                await remove_fts_by_conversation(session, cid)
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
    _auth: str = Depends(require_current_user),
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
    _auth: str = Depends(require_current_user),
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
    _auth: str = Depends(require_current_user),
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
    # Also remove each attachment's binary file from DATA_DIR/attachments/.
    att_res = await session.execute(
        select(Attachment.id).where(Attachment.message_id.in_(
            select(Message.id).where(Message.conversation_id == conversation_id)
        ))
    )
    att_ids = [row[0] for row in att_res.all()]
    # CASCADE: delete brief chain first (FK to discovery_sessions), then briefs/discovery_sessions
    await session.execute(text("""
        DELETE FROM lessons_learned 
        WHERE report_id IN (
            SELECT id FROM engineering_reports WHERE brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
                )
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM engineering_reports 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM dispatch_sessions 
        WHERE graph_id IN (
            SELECT tg.id FROM task_graphs tg JOIN engineering_plans ep ON tg.plan_id=ep.id 
            WHERE ep.brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
                )
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM task_graphs 
        WHERE plan_id IN (
            SELECT id FROM engineering_plans WHERE brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
                )
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM engineering_plans 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM planning_sessions 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM verification_sessions 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
            )
        )
    """), {"cid": conversation_id})
    await session.execute(text("""
        DELETE FROM engineering_briefs 
        WHERE discovery_session_id IN (
            SELECT id FROM discovery_sessions WHERE task_conversation_ref = :cid
        )
    """), {"cid": conversation_id})
    await session.execute(delete(DiscoverySession).where(DiscoverySession.task_conversation_ref == conversation_id))
    await session.execute(delete(Attachment).where(Attachment.message_id.in_(
        select(Message.id).where(Message.conversation_id == conversation_id)
    )))
    await session.delete(conv)
    await session.commit()
    from backend.services.attachment_store import delete_attachment
    for att_id in att_ids:
        delete_attachment(att_id)
    return {"deleted": True, "id": conversation_id}


@router.delete("/{conversation_id}/messages")
async def clear_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
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
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
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

    # The parent task is dispatched by conversation/engine._launch_pipeline
    # (the canonical MasterOrchestrator pipeline), so no redundant dispatch
    # is scheduled here. _dispatch_created_task remains defined for self_healing.
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
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
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

    # The parent task is dispatched by conversation/engine._launch_pipeline
    # (the canonical MasterOrchestrator pipeline); no redundant dispatch here.
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
    from sqlalchemy.exc import OperationalError
    await _aio.sleep(2)

    # SQLite WAL allows a single writer. The request path commits the task row
    # before returning (conversation/engine._launch_pipeline commits, and the
    # stream handler commits before building the StreamingResponse), but other
    # background work (a pipeline task, a concurrent request's brief write
    # window, worker commits) can still legitimately hold the write lock for a
    # few ms. Retry ONLY the "database is locked" OperationalError with a
    # bounded backoff, reopening a fresh session each attempt; any other error
    # is logged and returned immediately.
    last_err = None
    for attempt in range(1, 6):
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
                return
        except OperationalError as e:
            msg = str(e.orig) if e.orig is not None else str(e)
            if "locked" not in msg.lower():
                logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
                return
            last_err = e
            logger.warning(
                f"Dispatch bg: SQLite write locked (attempt {attempt}/5) for {task_id}: {msg}"
            )
            await _aio.sleep(0.2 * attempt)
        except Exception as e:
            logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
            return

    logger.error(
        f"Dispatch bg failed for {task_id} after 5 lock-retry attempts: {last_err}",
        exc_info=True,
    )

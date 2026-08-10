"""Message routes — CRUD for conversation messages."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List

from backend.database.session import get_db
from backend.api.dependencies import require_current_user
from storage.models import Conversation, Message
from backend.models.conversation import Attachment
from backend.schemas.conversation_schemas import (
    MessageCreate, MessageUpdate, MessageResponse, AttachmentResponse,
)
from backend.services.attachment_store import (
    save_attachment, delete_attachment, read_attachment, decode_data_url,
)
from backend.services.search_service import index_message_fts, remove_fts
from backend.api.routes.conversations import _build_msg_responses, _build_msg_response

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_current_user)])


@router.get("/conversations/{id}/messages", response_model=List[MessageResponse])
async def list_messages(
    id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    # PERF-FIX: explicit column projection + one batched attachment query.
    # Note: pagination is intentionally NOT applied (the renderer's loadMessages
    # replaces the full list in one fetch), so the safe default limit + explicit
    # projection is kept.
    res = await db.execute(
        select(
            Message.id, Message.conversation_id, Message.role, Message.content,
            Message.meta, Message.token_count, Message.model_id,
            Message.provider_id, Message.status, Message.created_at, Message.updated_at,
        )
        .where(Message.conversation_id == id)
        # created_at is the primary conversation order. id makes results
        # deterministic for legacy rows that share the same timestamp.
        .order_by(Message.created_at, Message.id)
        .offset(skip)
        .limit(limit)
    )
    msgs = res.all()
    if not msgs:
        return []
    # Rehydrate Message objects from the projected rows for the shared builder.
    projected = [
        Message(
            id=m.id, conversation_id=m.conversation_id, role=m.role, content=m.content,
            meta=m.meta, token_count=m.token_count,
            model_id=m.model_id, provider_id=m.provider_id, status=m.status,
            created_at=m.created_at, updated_at=m.updated_at,
        )
        for m in msgs
    ]
    return await _build_msg_responses(db, projected)


@router.post("/conversations/{id}/messages", response_model=MessageResponse)
async def create_message(id: str, payload: MessageCreate, db: AsyncSession = Depends(get_db)):
    conv_res = await db.execute(select(Conversation).where(Conversation.id == id))
    if not conv_res.scalars().first():
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = Message(
        conversation_id=id,
        role=payload.role,
        content=payload.content,
        message_metadata=payload.message_metadata,
        token_count=payload.token_count,
        model_id=payload.model_id,
        provider_id=payload.provider_id,
        status=payload.status or "completed"
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    if payload.attachments:
        for a in payload.attachments:
            att = Attachment(
                message_id=msg.id,
                file_name=a.file_name,
                file_type=a.file_type,
                mime_type=a.mime_type,
                file_size=a.file_size,
                attachment_metadata=a.attachment_metadata
            )
            db.add(att)
            # Persist the binary when the client supplied a base64 data URL so
            # the attachment survives backup/restore. Flush first to obtain the
            # generated attachment id (DATA_DIR/attachments/<id>).
            if a.data_url:
                try:
                    await db.flush()
                    data = decode_data_url(a.data_url)
                    if data is not None:
                        save_attachment(att.id, data)
                except Exception as e:
                    logger.warning(f"Failed to persist attachment {att.id} binary: {e}")
        await db.commit()

    await index_message_fts(db, msg.id, id, msg.content)
    # New message → cached context assembly for this conversation is stale.
    try:
        from context.cache import get_context_cache
        get_context_cache().invalidate_conversation(id)
    except Exception:
        pass
    return await _build_msg_response(db, msg)


@router.patch("/messages/{id}", response_model=MessageResponse)
async def update_message(id: str, payload: MessageUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Message).where(Message.id == id))
    msg = res.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if payload.content is not None: msg.content = payload.content
    if payload.message_metadata is not None: msg.message_metadata = payload.message_metadata
    if payload.token_count is not None: msg.token_count = payload.token_count
    if payload.status is not None: msg.status = payload.status

    await db.commit()
    await db.refresh(msg)

    if payload.content is not None:
        await index_message_fts(db, msg.id, msg.conversation_id, msg.content)

    return await _build_msg_response(db, msg)


@router.delete("/messages/{id}")
async def delete_message(id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Message).where(Message.id == id))
    msg = res.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # FIX: Attachment rows have no FK/relationship to messages — delete them
    # explicitly so they don't become orphans. Also remove each attachment's
    # binary file from DATA_DIR/attachments/.
    att_res = await db.execute(select(Attachment.id).where(Attachment.message_id == id))
    att_ids = [row[0] for row in att_res.all()]
    await db.execute(delete(Attachment).where(Attachment.message_id == id))
    for att_id in att_ids:
        delete_attachment(att_id)
    await db.delete(msg)
    await db.commit()
    await remove_fts(db, 'message', id)
    return {"status": "ok"}


@router.get("/attachments/{attachment_id}")
async def get_attachment(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """Serve an attachment's binary with its stored mime_type.

    Restored messages carry attachment metadata but no live base64 payload, so
    the renderer fetches the binary here (GET /attachments/{id}). Attachments
    created before binary storage existed (or whose file was removed) 404 with
    a clear message.
    """
    att_res = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    att = att_res.scalars().first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    data = read_attachment(attachment_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Attachment binary not found (created before binary storage existed)",
        )
    # S4 FIX: strip CR/LF and other control chars from the stored filename so
    # it cannot inject headers into the Content-Disposition value.
    safe_name = "".join(c for c in (att.file_name or "") if ord(c) >= 32 and c not in '"\r\n')
    return Response(
        content=data,
        media_type=att.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )

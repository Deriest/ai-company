"""Message routes — CRUD for conversation messages."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from backend.database.session import get_db
from storage.models import Conversation, Message
from backend.models.conversation import Attachment
from backend.schemas.conversation_schemas import (
    MessageCreate, MessageUpdate, MessageResponse, AttachmentResponse,
)
from backend.services.search_service import index_message_fts, remove_fts
from backend.api.routes.conversations import _build_msg_response

router = APIRouter()


@router.get("/conversations/{id}/messages", response_model=List[MessageResponse])
async def list_messages(
    id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Message)
        .where(Message.conversation_id == id)
        # created_at is the primary conversation order. id makes results
        # deterministic for legacy rows that share the same timestamp.
        .order_by(Message.created_at, Message.id)
        .offset(skip)
        .limit(limit)
    )
    msgs = res.scalars().all()
    return [await _build_msg_response(db, m) for m in msgs]


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
            db.add(Attachment(
                message_id=msg.id,
                file_name=a.file_name,
                file_type=a.file_type,
                mime_type=a.mime_type,
                file_size=a.file_size,
                attachment_metadata=a.attachment_metadata
            ))
        await db.commit()

    await index_message_fts(db, msg.id, id, msg.content)
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

    await db.delete(msg)
    await db.commit()
    await remove_fts(db, 'message', id)
    return {"status": "ok"}

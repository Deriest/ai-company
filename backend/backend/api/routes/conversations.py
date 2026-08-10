"""Conversation routes — CRUD, search, folders, tags, export/import."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, desc, text
from typing import List, Optional
import json


from backend.api.dependencies import Role.USER
from backend.database.session import get_db
from backend.api.dependencies import require_current_user
from storage.models import Conversation, Message
from backend.models.conversation import (
    Attachment,
    ConversationTag, ConversationPin, ConversationFolder,
)
from backend.schemas.conversation_schemas import (
    BaseModel,
    ConversationCreate, ConversationUpdate, ConversationResponse,
    MessageCreate, MessageUpdate, MessageResponse, AttachmentResponse,
    SearchResultItem, ImportConversationPayload, ExportConversationPayload,
)
from backend.services.search_service import (
    index_conversation_fts, index_message_fts,
    remove_fts_by_conversation, init_fts5,
)
from backend.services.attachment_store import (
    save_attachment, delete_attachment, read_attachment, decode_data_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_current_user)])


# ---------------------------------------------------------------------------
# Pydantic models for folders
# ---------------------------------------------------------------------------

class FolderCreate(BaseModel):
    name: str


class FolderResponse(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _build_conv_response(db: AsyncSession, conv: Conversation) -> ConversationResponse:
    # check pins
    pin_res = await db.execute(select(ConversationPin).where(ConversationPin.conversation_id == conv.id))
    is_pinned = pin_res.scalars().first() is not None
    # check tags
    tags_res = await db.execute(select(ConversationTag).where(ConversationTag.conversation_id == conv.id))
    tags = [t.tag for t in tags_res.scalars().all()]
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        folder_id=conv.folder_id,
        project_id=conv.project_id,
        is_archived=conv.is_archived,
        is_favorite=conv.is_favorite,
        is_pinned=is_pinned,
        tags=tags,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )


async def _build_conv_responses(db: AsyncSession, convs: list[Conversation]) -> list[ConversationResponse]:
    """Build ConversationResponse for a batch of conversations with 2 batched
    queries (pins + tags) instead of 2 queries per conversation (N+1 fix)."""
    if not convs:
        return []
    conv_ids = [c.id for c in convs]

    pin_res = await db.execute(
        select(ConversationPin.conversation_id).where(ConversationPin.conversation_id.in_(conv_ids))
    )
    pinned_ids = set(pin_res.scalars().all())

    tag_res = await db.execute(
        select(ConversationTag.conversation_id, ConversationTag.tag).where(
            ConversationTag.conversation_id.in_(conv_ids)
        )
    )
    tags_map: dict[str, list[str]] = {}
    for conv_id, tag in tag_res.all():
        tags_map.setdefault(conv_id, []).append(tag)

    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            folder_id=c.folder_id,
            project_id=c.project_id,
            is_archived=c.is_archived,
            is_favorite=c.is_favorite,
            is_pinned=c.id in pinned_ids,
            tags=tags_map.get(c.id, []),
            created_at=c.created_at,
            updated_at=c.updated_at
        )
        for c in convs
    ]


def _build_msg_response_from_attachments(msg: Message, attachments: list[Attachment]) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        message_metadata=msg.message_metadata,
        token_count=msg.token_count,
        model_id=msg.model_id,
        provider_id=msg.provider_id,
        status=msg.status,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
        attachments=[
            AttachmentResponse(
                id=a.id,
                message_id=a.message_id,
                file_name=a.file_name,
                file_type=a.file_type,
                mime_type=a.mime_type,
                file_size=a.file_size,
                attachment_metadata=a.attachment_metadata,
                created_at=a.created_at
            )
            for a in attachments
        ]
    )


async def _build_msg_response(db: AsyncSession, msg: Message) -> MessageResponse:
    att_res = await db.execute(select(Attachment).where(Attachment.message_id == msg.id))
    attachments = att_res.scalars().all()
    return _build_msg_response_from_attachments(msg, attachments)


async def _build_msg_responses(db: AsyncSession, msgs: list[Message]) -> list[MessageResponse]:
    """Build MessageResponse for a batch of messages with ONE attachment query
    (N+1 fix) instead of one query per message."""
    if not msgs:
        return []
    att_res = await db.execute(
        select(Attachment).where(Attachment.message_id.in_([m.id for m in msgs]))
    )
    att_map: dict[str, list[Attachment]] = {}
    for a in att_res.scalars().all():
        att_map.setdefault(a.message_id, []).append(a)
    return [_build_msg_response_from_attachments(m, att_map.get(m.id, [])) for m in msgs]


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    folder_id: Optional[str] = Query(None),
    is_archived: Optional[bool] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    tag: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    query = select(Conversation).order_by(desc(Conversation.updated_at))
    if folder_id is not None:
        query = query.where(Conversation.folder_id == folder_id)
    if is_archived is not None:
        query = query.where(Conversation.is_archived == is_archived)
    if is_favorite is not None:
        query = query.where(Conversation.is_favorite == is_favorite)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    convs = result.scalars().all()

    # PERF-FIX: batched pins/tags queries (N+1 fix) instead of 2 queries per conv.
    conv_responses = await _build_conv_responses(db, convs)
    res = []
    for c_res in conv_responses:
        if tag is not None and tag not in c_res.tags:
            continue
        res.append(c_res)
    return res


from datetime import datetime, timezone

router.post(post, [require_roles(Role.USER)])
async def create_conversation(payload: ConversationCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    conv = Conversation(
        title=payload.title,
        folder_id=payload.folder_id,
        project_id=payload.project_id,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    if payload.tags:
        for t in payload.tags:
            db.add(ConversationTag(conversation_id=conv.id, tag=t))
        await db.commit()

    await index_conversation_fts(db, conv.id, conv.title, payload.tags)
    return await _build_conv_response(db, conv)


@router.get("/conversations/search", response_model=List[SearchResultItem])
async def search_conversations(q: str = Query(...), db: AsyncSession = Depends(get_db)):
    if not q.strip():
        return []
    try:
        query = text("""
            SELECT target_type, target_id, conversation_id, title,
                   snippet(search_fts, 4, '<b>', '</b>', '...', 15) as snip, tags
            FROM search_fts
            WHERE search_fts MATCH :query
            LIMIT 50
        """)
        # QA-SEC FIX: quote each term so FTS5 operators (AND/OR/NOT/NEAR/"")
        # cannot be injected through the MATCH string. Embedded double quotes
        # are escaped by doubling them (FTS5 phrase escaping), and a trailing
        # * keeps prefix behavior.
        terms = [t for t in q.strip().split() if t.strip('"')]
        if not terms:
            return []
        formatted_query = " ".join(f'"{t.replace(chr(34), chr(34) * 2)}"*' for t in terms)
        result = await db.execute(query, {"query": formatted_query})
        rows = result.fetchall()

        items = []
        for row in rows:
            items.append(SearchResultItem(
                target_type=row[0],
                target_id=row[1],
                conversation_id=row[2],
                title=row[3] or "Conversation Match",
                snippet=row[4] or "",
                tags=row[5] or ""
            ))
        return items
    except Exception as e:
        # Fallback if invalid fts syntax (quoted terms should prevent this).
        logger.warning(f"FTS5 search failed for q={q!r}: {e}")
        return []


@router.get("/conversations/{id}", response_model=ConversationResponse)
async def get_conversation(id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Conversation).where(Conversation.id == id))
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await _build_conv_response(db, conv)


router.patch(patch, [require_roles(Role.USER)])
async def update_conversation(id: str, payload: ConversationUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Conversation).where(Conversation.id == id))
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.title is not None: conv.title = payload.title
    if payload.folder_id is not None: conv.folder_id = payload.folder_id
    if payload.is_archived is not None: conv.is_archived = payload.is_archived
    if payload.is_favorite is not None: conv.is_favorite = payload.is_favorite

    if payload.is_pinned is not None:
        pin_res = await db.execute(select(ConversationPin).where(ConversationPin.conversation_id == id))
        pin = pin_res.scalars().first()
        if payload.is_pinned and not pin:
            db.add(ConversationPin(conversation_id=id))
        elif not payload.is_pinned and pin:
            await db.delete(pin)

    if payload.tags is not None:
        await db.execute(delete(ConversationTag).where(ConversationTag.conversation_id == id))
        for t in payload.tags:
            db.add(ConversationTag(conversation_id=id, tag=t))

    await db.commit()
    await db.refresh(conv)

    c_res = await _build_conv_response(db, conv)
    await index_conversation_fts(db, conv.id, conv.title, c_res.tags)
    return c_res


router.delete(delete, [require_roles(Role.USER)])
async def delete_conversation(id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Conversation).where(Conversation.id == id))
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # CASCADE: lessons_learned ← engineering_reports ← engineering_briefs ← discovery_sessions → conversation/messages/attachments
    # Also engineering_plans/task_graphs/dispatch_sessions ← engineering_briefs
    # Delete in reverse dependency order to avoid foreign key violations
    await db.execute(text("""
        DELETE FROM lessons_learned 
        WHERE report_id IN (
            SELECT id FROM engineering_reports WHERE brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE conversation_id = :cid
                )
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM engineering_reports 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE conversation_id = :cid
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM dispatch_sessions 
        WHERE graph_id IN (
            SELECT tg.id FROM task_graphs tg JOIN engineering_plans ep ON tg.plan_id=ep.id 
            WHERE ep.brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE conversation_id = :cid
                )
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM task_graphs 
        WHERE plan_id IN (
            SELECT id FROM engineering_plans WHERE brief_id IN (
                SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                    SELECT id FROM discovery_sessions WHERE conversation_id = :cid
                )
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM engineering_plans 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE conversation_id = :cid
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM planning_sessions 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE conversation_id = :cid
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM verification_sessions 
        WHERE brief_id IN (
            SELECT id FROM engineering_briefs WHERE discovery_session_id IN (
                SELECT id FROM discovery_sessions WHERE conversation_id = :cid
            )
        )
    """), {"cid": id})
    await db.execute(text("""
        DELETE FROM engineering_briefs 
        WHERE discovery_session_id IN (
            SELECT id FROM discovery_sessions WHERE conversation_id = :cid
        )
    """), {"cid": id})
    # Attachment cleanup + files
    att_res = await db.execute(select(Attachment.id).where(
        Attachment.message_id.in_(
            select(Message.id).where(Message.conversation_id == id)
        )
    ))
    att_ids = [row[0] for row in att_res.all()]
    await db.execute(text(
        "DELETE FROM attachments WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = :cid)"
    ), {"cid": id})
    await db.execute(text("DELETE FROM discovery_sessions WHERE conversation_id = :cid"), {"cid": id})
    await db.delete(conv)
    await db.commit()
    for att_id in att_ids:
        delete_attachment(att_id)
    await remove_fts_by_conversation(db, id)
    return {"status": "ok"}


router.post(post, [require_roles(Role.USER)])
async def duplicate_conversation(id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Conversation).where(Conversation.id == id))
    orig = res.scalars().first()
    if not orig:
        raise HTTPException(status_code=404, detail="Conversation not found")

    c_res = await _build_conv_response(db, orig)
    new_conv = Conversation(
        title=f"{orig.title} (Copy)",
        folder_id=orig.folder_id,
        is_archived=orig.is_archived,
        is_favorite=orig.is_favorite
    )
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)

    if c_res.tags:
        for t in c_res.tags:
            db.add(ConversationTag(conversation_id=new_conv.id, tag=t))

    # duplicate messages
    msg_res = await db.execute(select(Message).where(Message.conversation_id == id).order_by(Message.created_at))
    msgs = msg_res.scalars().all()
    for m in msgs:
        new_msg = Message(
            conversation_id=new_conv.id,
            role=m.role,
            content=m.content,
            message_metadata=m.message_metadata,
            token_count=m.token_count,
            model_id=m.model_id,
            provider_id=m.provider_id,
            status=m.status
        )
        db.add(new_msg)
        await db.commit()
        await db.refresh(new_msg)
        # duplicate attachments
        att_res = await db.execute(select(Attachment).where(Attachment.message_id == m.id))
        atts = att_res.scalars().all()
        for a in atts:
            new_att = Attachment(
                message_id=new_msg.id,
                file_name=a.file_name,
                file_type=a.file_type,
                mime_type=a.mime_type,
                file_size=a.file_size,
                attachment_metadata=a.attachment_metadata
            )
            db.add(new_att)
            # Copy the source attachment's binary to the new attachment id so
            # the duplicate is fully restorable too.
            try:
                await db.flush()
                src = read_attachment(a.id)
                if src is not None:
                    save_attachment(new_att.id, src)
            except Exception as e:
                logger.warning(f"Failed to copy attachment binary {a.id}: {e}")
        await index_message_fts(db, new_msg.id, new_conv.id, new_msg.content)

    await db.commit()
    await index_conversation_fts(db, new_conv.id, new_conv.title, c_res.tags)
    return await _build_conv_response(db, new_conv)


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

@router.get("/conversations/{id}/export")
async def export_conversation(id: str, format: str = Query("json"), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Conversation).where(Conversation.id == id))
    conv = res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    c_res = await _build_conv_response(db, conv)
    msg_res = await db.execute(select(Message).where(Message.conversation_id == id).order_by(Message.created_at))
    msgs = msg_res.scalars().all()

    # PERF-FIX: batch-load attachments (one query) instead of one per message.
    msg_responses = await _build_msg_responses(db, msgs)
    msg_payloads = []
    for m, m_res in zip(msgs, msg_responses):
        msg_payloads.append(MessageCreate(
            role=m.role,
            content=m.content,
            message_metadata=m.message_metadata,
            token_count=m.token_count,
            model_id=m.model_id,
            provider_id=m.provider_id,
            status=m.status,
            attachments=[
                {
                    "file_name": a.file_name,
                    "file_type": a.file_type,
                    "mime_type": a.mime_type,
                    "file_size": a.file_size,
                    "attachment_metadata": a.attachment_metadata
                }
                for a in m_res.attachments
            ]
        ))

    if format == "markdown":
        lines = [f"# {c_res.title}\n"]
        for mp in msg_payloads:
            role_header = "## User" if mp.role == "user" else f"## {mp.role.capitalize()}"
            lines.append(f"{role_header}\n\n{mp.content}\n")
        content_str = "\n".join(lines)
        return Response(content=content_str, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{c_res.title}.md"'})

    payload = ExportConversationPayload(
        id=c_res.id,
        title=c_res.title,
        folder_id=c_res.folder_id,
        is_archived=c_res.is_archived,
        is_favorite=c_res.is_favorite,
        tags=c_res.tags,
        created_at=c_res.created_at.isoformat(),
        updated_at=c_res.updated_at.isoformat(),
        messages=msg_payloads
    )
    return Response(content=json.dumps(payload.model_dump(), indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{c_res.title}.json"'})


router.post(post, [require_roles(Role.USER)])
async def import_conversation(payload: ImportConversationPayload, db: AsyncSession = Depends(get_db)):
    conv = Conversation(
        title=payload.title,
        folder_id=payload.folder_id,
        is_archived=payload.is_archived or False,
        is_favorite=payload.is_favorite or False
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    if payload.tags:
        for t in payload.tags:
            db.add(ConversationTag(conversation_id=conv.id, tag=t))
        await db.commit()

    for m in payload.messages:
        msg = Message(
            conversation_id=conv.id,
            role=m.role,
            content=m.content,
            message_metadata=m.message_metadata,
            token_count=m.token_count,
            model_id=m.model_id,
            provider_id=m.provider_id,
            status=m.status or "completed"
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        if m.attachments:
            for a in m.attachments:
                att = Attachment(
                    message_id=msg.id,
                    file_name=a.file_name,
                    file_type=a.file_type,
                    mime_type=a.mime_type,
                    file_size=a.file_size,
                    attachment_metadata=a.attachment_metadata
                )
                db.add(att)
                # Persist the binary when the import payload carries a base64
                # data URL (exported via the attachment-creation path).
                if a.data_url:
                    try:
                        await db.flush()
                        data = decode_data_url(a.data_url)
                        if data is not None:
                            save_attachment(att.id, data)
                    except Exception as e:
                        logger.warning(f"Failed to persist imported attachment binary {att.id}: {e}")
            await db.commit()
        await index_message_fts(db, msg.id, conv.id, msg.content)

    await index_conversation_fts(db, conv.id, conv.title, payload.tags)
    return await _build_conv_response(db, conv)


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@router.get("/folders", response_model=List[FolderResponse])
async def list_folders(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ConversationFolder).order_by(ConversationFolder.name))
    folders = res.scalars().all()
    return [
        FolderResponse(
            id=f.id,
            name=f.name,
            created_at=f.created_at.isoformat() if f.created_at else "",
            updated_at=f.updated_at.isoformat() if f.updated_at else ""
        ) for f in folders
    ]


router.post(post, [require_roles(Role.USER)])
async def create_folder(payload: FolderCreate, db: AsyncSession = Depends(get_db)):
    f = ConversationFolder(name=payload.name)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return FolderResponse(
        id=f.id,
        name=f.name,
        created_at=f.created_at.isoformat() if f.created_at else "",
        updated_at=f.updated_at.isoformat() if f.updated_at else ""
    )


router.delete(delete, [require_roles(Role.USER)])
async def delete_folder(id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ConversationFolder).where(ConversationFolder.id == id))
    f = res.scalars().first()
    if not f:
        raise HTTPException(status_code=404, detail="Folder not found")
    # FIX: folder_id is a plain column (no FK) — NULL it on conversations so
    # they don't dangle after the folder is deleted.
    await db.execute(text("UPDATE conversations SET folder_id = NULL WHERE folder_id = :fid"), {"fid": id})
    await db.delete(f)
    await db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@router.get("/tags", response_model=List[str])
async def list_tags(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ConversationTag.tag).distinct())
    return [t for t in res.scalars().all()]

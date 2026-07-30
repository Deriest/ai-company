from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

async def init_fts5(db: AsyncSession):
    try:
        await db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                target_type,
                target_id,
                conversation_id,
                title,
                content,
                tags,
                tokenize='porter unicode61'
            );
        """))
        await db.commit()
    except Exception as e:
        logger.error(f"Error initializing FTS5 table: {e}")
        await db.rollback()

async def index_conversation_fts(db: AsyncSession, conversation_id: str, title: str, tags_list: list[str] = None):
    tags_str = " ".join(tags_list) if tags_list else ""
    await db.execute(text("DELETE FROM search_fts WHERE target_type = 'conversation' AND target_id = :cid"), {"cid": conversation_id})
    await db.execute(text("""
        INSERT INTO search_fts(target_type, target_id, conversation_id, title, content, tags)
        VALUES ('conversation', :cid, :cid, :title, '', :tags)
    """), {"cid": conversation_id, "title": title, "tags": tags_str})
    await db.commit()

async def index_message_fts(db: AsyncSession, message_id: str, conversation_id: str, content: str):
    await db.execute(text("DELETE FROM search_fts WHERE target_type = 'message' AND target_id = :mid"), {"mid": message_id})
    await db.execute(text("""
        INSERT INTO search_fts(target_type, target_id, conversation_id, title, content, tags)
        VALUES ('message', :mid, :cid, '', :content, '')
    """), {"mid": message_id, "cid": conversation_id, "content": content})
    await db.commit()

async def remove_fts_by_conversation(db: AsyncSession, conversation_id: str):
    await db.execute(text("DELETE FROM search_fts WHERE conversation_id = :cid"), {"cid": conversation_id})
    await db.commit()

async def remove_fts(db: AsyncSession, target_type: str, target_id: str):
    await db.execute(text("DELETE FROM search_fts WHERE target_type = :type AND target_id = :id"), {"type": target_type, "id": target_id})
    await db.commit()

"""Context & Knowledge Intelligence — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.context.migration")


async def run_context_migration(session: AsyncSession) -> None:
    """Run the Context & Knowledge migration."""
    try:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_entries_domain
            ON knowledge_entries(domain)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_entries_key
            ON knowledge_entries(key)
        """))

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS decision_records (
                id TEXT PRIMARY KEY,
                decision TEXT NOT NULL,
                rationale TEXT NOT NULL,
                context TEXT DEFAULT '',
                outcome TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.commit()
        logger.info("Context & Knowledge migration completed")

    except Exception as e:
        logger.error(f"Context & Knowledge migration failed: {e}")
        await session.rollback()
        raise

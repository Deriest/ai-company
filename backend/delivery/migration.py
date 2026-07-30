"""Delivery & Continuous Improvement — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.delivery.migration")


async def run_delivery_migration(session: AsyncSession) -> None:
    """Run the Delivery migration."""
    try:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS engineering_reports (
                id TEXT PRIMARY KEY,
                brief_id TEXT,
                plan_id TEXT,
                graph_id TEXT,
                verification_id TEXT,
                goal TEXT DEFAULT '',
                outcome TEXT DEFAULT 'pending',
                duration TEXT DEFAULT '',
                quality_score REAL DEFAULT 0.0,
                total_tasks INTEGER DEFAULT 0,
                successful_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                lessons TEXT DEFAULT '[]',
                recommendations TEXT DEFAULT '[]',
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_reports_brief
            ON engineering_reports(brief_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_reports_outcome
            ON engineering_reports(outcome)
        """))

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS lessons_learned (
                id TEXT PRIMARY KEY,
                report_id TEXT,
                lesson TEXT NOT NULL,
                category TEXT DEFAULT '',
                impact TEXT DEFAULT 'medium',
                recommendation TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.commit()
        logger.info("Delivery migration completed")

    except Exception as e:
        logger.error(f"Delivery migration failed: {e}")
        await session.rollback()
        raise

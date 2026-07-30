"""Verification Engine — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.verification.migration")


async def run_verification_migration(session: AsyncSession) -> None:
    """Run the Verification Engine migration."""
    try:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS verification_sessions (
                id TEXT PRIMARY KEY,
                brief_id TEXT NOT NULL,
                requirements_met TEXT DEFAULT '[]',
                acceptance_met TEXT DEFAULT '[]',
                quality_score TEXT DEFAULT '{}',
                overall_status TEXT DEFAULT 'pending',
                recommendations TEXT DEFAULT '[]',
                blocking_issues TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brief_id) REFERENCES engineering_briefs(id)
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verification_sessions_brief
            ON verification_sessions(brief_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_verification_sessions_status
            ON verification_sessions(overall_status)
        """))

        await session.commit()
        logger.info("Verification Engine migration completed")

    except Exception as e:
        logger.error(f"Verification Engine migration failed: {e}")
        await session.rollback()
        raise

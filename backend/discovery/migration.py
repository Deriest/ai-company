"""Engineering Discovery Engine — Database Migration.

Adds discovery_sessions and engineering_briefs tables.
This migration is additive-only — no existing tables are modified.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.discovery.migration")


async def run_discovery_migration(session: AsyncSession) -> None:
    """Run the Discovery Engine migration.

    Creates discovery_sessions and engineering_briefs tables.
    Safe to run multiple times (IF NOT EXISTS).
    """
    try:
        # Create discovery_sessions table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS discovery_sessions (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_id TEXT,
                status TEXT NOT NULL DEFAULT 'new_request',
                round_number INTEGER DEFAULT 0,
                questions_asked INTEGER DEFAULT 0,
                questions_answered INTEGER DEFAULT 0,
                context TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))

        # Create indexes for discovery_sessions
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_conversation
            ON discovery_sessions(conversation_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user
            ON discovery_sessions(user_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_discovery_sessions_status
            ON discovery_sessions(status)
        """))

        # Create engineering_briefs table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS engineering_briefs (
                id TEXT PRIMARY KEY,
                discovery_session_id TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                engineering_goal TEXT NOT NULL DEFAULT '',
                user_intent TEXT NOT NULL DEFAULT '',
                request_category TEXT NOT NULL DEFAULT 'feature',
                scope TEXT DEFAULT '{}',
                functional_requirements TEXT DEFAULT '[]',
                non_functional_requirements TEXT DEFAULT '[]',
                constraints TEXT DEFAULT '[]',
                assumptions TEXT DEFAULT '[]',
                dependencies TEXT DEFAULT '[]',
                risks TEXT DEFAULT '[]',
                acceptance_criteria TEXT DEFAULT '[]',
                readiness_status TEXT NOT NULL DEFAULT 'not_ready',
                readiness_score REAL NOT NULL DEFAULT 0.0,
                readiness_dimensions TEXT DEFAULT '{}',
                outstanding_unknowns TEXT DEFAULT '[]',
                discovery_metadata TEXT DEFAULT '{}',
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (discovery_session_id) REFERENCES discovery_sessions(id)
            )
        """))

        # Create indexes for engineering_briefs
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_briefs_session
            ON engineering_briefs(discovery_session_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_briefs_status
            ON engineering_briefs(status)
        """))

        await session.commit()
        logger.info("Discovery Engine migration completed successfully")

    except Exception as e:
        logger.error(f"Discovery Engine migration failed: {e}")
        await session.rollback()
        raise

"""Planning Engine — Database Migration.

Adds planning_sessions and engineering_plans tables.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.planning.migration")


async def run_planning_migration(session: AsyncSession) -> None:
    """Run the Planning Engine migration.

    Creates planning_sessions and engineering_plans tables.
    Safe to run multiple times (IF NOT EXISTS).
    """
    try:
        # Create planning_sessions table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS planning_sessions (
                id TEXT PRIMARY KEY,
                brief_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'brief_received',
                context TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brief_id) REFERENCES engineering_briefs(id)
            )
        """))

        # Create indexes for planning_sessions
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_planning_sessions_brief
            ON planning_sessions(brief_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_planning_sessions_status
            ON planning_sessions(status)
        """))

        # Create engineering_plans table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS engineering_plans (
                id TEXT PRIMARY KEY,
                brief_id TEXT NOT NULL,
                engineering_goal TEXT NOT NULL DEFAULT '',
                technical_approach TEXT NOT NULL DEFAULT '',
                implementation_strategy TEXT NOT NULL DEFAULT 'hybrid',
                architecture_decisions TEXT DEFAULT '[]',
                risk_mitigations TEXT DEFAULT '[]',
                dependency_map TEXT DEFAULT '{}',
                effort_estimates TEXT DEFAULT '[]',
                acceptance_criteria TEXT DEFAULT '[]',
                estimated_duration TEXT DEFAULT '',
                confidence_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brief_id) REFERENCES engineering_briefs(id)
            )
        """))

        # Create indexes for engineering_plans
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_plans_brief
            ON engineering_plans(brief_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_engineering_plans_status
            ON engineering_plans(status)
        """))

        await session.commit()
        logger.info("Planning Engine migration completed successfully")

    except Exception as e:
        logger.error(f"Planning Engine migration failed: {e}")
        await session.rollback()
        raise

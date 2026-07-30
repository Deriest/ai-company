"""Task Graph Engine — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.taskgraph.migration")


async def run_taskgraph_migration(session: AsyncSession) -> None:
    """Run the Task Graph Engine migration."""
    try:
        # Create task_graphs table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS task_graphs (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                nodes TEXT DEFAULT '[]',
                edges TEXT DEFAULT '[]',
                execution_order TEXT DEFAULT '[]',
                critical_path TEXT DEFAULT '[]',
                recovery_points TEXT DEFAULT '[]',
                estimated_duration TEXT DEFAULT '',
                parallelism_factor REAL DEFAULT 1.0,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES engineering_plans(id)
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_graphs_plan
            ON task_graphs(plan_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_graphs_status
            ON task_graphs(status)
        """))

        await session.commit()
        logger.info("Task Graph Engine migration completed")

    except Exception as e:
        logger.error(f"Task Graph Engine migration failed: {e}")
        await session.rollback()
        raise

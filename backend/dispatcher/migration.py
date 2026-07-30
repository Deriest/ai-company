"""Engineering Dispatcher — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.dispatcher.migration")


async def run_dispatcher_migration(session: AsyncSession) -> None:
    """Run the Dispatcher migration."""
    try:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS dispatch_sessions (
                id TEXT PRIMARY KEY,
                graph_id TEXT NOT NULL,
                execution_log TEXT DEFAULT '[]',
                total_duration TEXT DEFAULT '',
                success_rate REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (graph_id) REFERENCES task_graphs(id)
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dispatch_sessions_graph
            ON dispatch_sessions(graph_id)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_dispatch_sessions_status
            ON dispatch_sessions(status)
        """))

        await session.commit()
        logger.info("Dispatcher migration completed")

    except Exception as e:
        logger.error(f"Dispatcher migration failed: {e}")
        await session.rollback()
        raise

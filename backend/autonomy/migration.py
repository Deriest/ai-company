"""Autonomous Execution Intelligence — Database Migration."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.autonomy.migration")


async def run_autonomy_migration(session: AsyncSession) -> None:
    """Run the Autonomy migration."""
    try:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS anomaly_log (
                id TEXT PRIMARY KEY,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                affected_component TEXT DEFAULT '',
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_log_type
            ON anomaly_log(anomaly_type)
        """))

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS recovery_log (
                id TEXT PRIMARY KEY,
                anomaly_id TEXT,
                action_type TEXT NOT NULL,
                success BOOLEAN DEFAULT FALSE,
                details TEXT DEFAULT '',
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await session.commit()
        logger.info("Autonomy migration completed")

    except Exception as e:
        logger.error(f"Autonomy migration failed: {e}")
        await session.rollback()
        raise

"""Migration 024 - Add heartbeat tracking to leases.

Adds last_heartbeat_at and expires_at columns to the leases table
for improved lease expiration and recovery detection.

Sets default expires_at to created_at + 5 minutes for existing leases.
"""

import asyncio
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.database.session import AsyncSessionLocal

logger = logging.getLogger("aic.migrations")


async def migrate_up(session) -> None:
    """Apply migration - add heartbeat columns to leases."""
    
    # Check if columns already exist (idempotent safety)
    result = await session.execute(
        text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='leases'
        """)
    )
    if not result.fetchone():
        logger.warning("Table 'leases' does not exist, skipping migration")
        return
    
    # Check if last_heartbeat_at column exists
    result = await session.execute(
        text("""
            PRAGMA table_info(leases)
        """)
    )
    columns = {row[1] for row in result.fetchall()}
    
    # Add last_heartbeat_at column if it doesn't exist
    if 'last_heartbeat_at' not in columns:
        logger.info("Adding column 'last_heartbeat_at' to leases")
        await session.execute(
            text("""
                ALTER TABLE leases
                ADD COLUMN last_heartbeat_at DATETIME NULL
            """)
        )
    
    # Add expires_at column if it doesn't exist
    if 'expires_at' not in columns:
        logger.info("Adding column 'expires_at' to leases")
        await session.execute(
            text("""
                ALTER TABLE leases
                ADD COLUMN expires_at DATETIME NULL
            """)
        )
        # Set default expires_at to created_at + 5 minutes for existing leases
        # This provides immediate TTL-based expiration for existing lease records
        await session.execute(
            text("""
                UPDATE leases
                SET expires_at = datetime(
                    replace(replace(created_at, '-', ''), ' ', ''), 
                    '+5 minutes'
                )
                WHERE expires_at IS NULL
            """)
        )
        affected = await session.execute(
            text("SELECT COUNT(*) FROM leases WHERE expires_at IS NOT NULL")
        )
        count = affected.scalar()
        logger.info(f"Set expires_at on {count} existing leases (created_at + 5 minutes)")
    
    await session.commit()
    logger.info("Migration 024 completed: heartbeat columns added to leases")


async def migrate_down(session) -> None:
    """Rollback migration - remove heartbeat columns from leases."""
    
    # Note: SQLite doesn't support DROP COLUMN directly in old versions
    # We'll just log this as a warning since dropping columns is destructive
    logger.warning(
        "Migration 024 rollback not fully supported in SQLite. "
        "Columns 'last_heartbeat_at' and 'expires_at' must be dropped manually if needed."
    )
    
    # Alternative: In PostgreSQL you would use:
    # ALTER TABLE leases DROP COLUMN IF EXISTS last_heartbeat_at;
    # ALTER TABLE leases DROP COLUMN IF EXISTS expires_at;
    
    await session.commit()


def main():
    """Run migration up (default)."""
    logger.info("Running migration 024: Add lease heartbeat columns")
    asyncio.run(_run_migration())


async def _run_migration():
    async with AsyncSessionLocal() as session:
        try:
            await migrate_up(session)
        except Exception as e:
            logger.error(f"Migration 024 failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    main()

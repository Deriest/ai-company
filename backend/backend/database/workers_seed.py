"""Idempotent seeding of the ``workers`` table.

CRITICAL: ``runtime.executor.py`` creates ``Lease`` rows with
``worker_id = f"worker-{wtype}"`` (``storage.models.Lease.worker_id`` →
``workers.id``). The ``workers`` table was never seeded, so with
``PRAGMA foreign_keys=ON`` every lease insert crashed with a FOREIGN KEY
constraint failure — which blocked every execution path (dispatcher,
master_orchestrator, orchestration service, task dispatch).

This module seeds one row per ``WORKER_REGISTRY`` key (workers/base.py) so the
FK is satisfied. It is idempotent (``INSERT OR IGNORE`` on the PK and the
unique ``name`` column) and safe to call on every startup.
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aic.workers_seed")


async def seed_workers(db: AsyncSession) -> int:
    """Insert one ``workers`` row per WORKER_REGISTRY key (idempotent).

    Returns the number of rows inserted (0 when already seeded).
    """
    from workers.base import WORKER_REGISTRY

    inserted = 0
    for key in WORKER_REGISTRY:
        worker_id = f"worker-{key}"
        name = f"{key[0].upper()}{key[1:]}" if key else key
        # INSERT OR IGNORE: idempotent across restarts and concurrent callers
        # (ignores rows that already exist by PK or name).
        result = await db.execute(
            text(
                "INSERT OR IGNORE INTO workers (id, name, type, status, capabilities, config) "
                "VALUES (:id, :name, :type, 'offline', '[]', '{}')"
            ),
            {"id": worker_id, "name": name, "type": key},
        )
        inserted += result.rowcount or 0
    await db.commit()
    if inserted:
        logger.info(f"Seeded {inserted} worker row(s) into the workers table")
    return inserted

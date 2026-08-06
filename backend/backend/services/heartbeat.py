"""Heartbeat Scheduler — periodic worker health checks.

Implements Hermes's HeartbeatPolicy: periodically checks for stale tasks
and blocked workers. Publishes alerts to EventBus when issues are detected.

Started once at application startup via `start_heartbeat()`.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from events.bus import bus
from backend.database.session import AsyncSessionLocal
from storage.models import Task, TaskStatus, Lease

logger = logging.getLogger("aic.heartbeat")

# Configuration
CHECK_INTERVAL_SECONDS = 60  # Check every 60 seconds
STALE_TASK_THRESHOLD_HOURS = 2  # Tasks stuck for > 2 hours are stale
BLOCKED_LEASE_THRESHOLD_MINUTES = 30  # Leases active for > 30 min are stale


def _as_utc(dt):
    """Normalize a DB datetime to timezone-aware UTC.

    SQLAlchemy's SQLite DATETIME column stores/reads *offset-naive* datetimes
    (the tz is stripped on write, whatever was passed in), while the heartbeat
    compares against ``datetime.now(timezone.utc)`` (aware). Subtracting a
    naive DB value from an aware ``now`` raises ``TypeError``. Treat a naive
    value as UTC (the app always writes UTC) and otherwise leave it alone.
    """
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class HeartbeatScheduler:
    """Periodic health check for the engineering workforce."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self):
        """Start the heartbeat loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Heartbeat scheduler started")

    def stop(self):
        """Stop the heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Heartbeat scheduler stopped")

    async def _loop(self):
        """Main heartbeat loop — runs checks periodically."""
        while self._running:
            try:
                await self._run_checks()
            except Exception as e:
                logger.error(f"Heartbeat check failed: {e}")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    async def _run_checks(self):
        """Run all heartbeat checks."""
        async with AsyncSessionLocal() as session:
            try:
                stale_tasks = await self._check_stale_tasks(session)
                blocked_leases = await self._check_blocked_leases(session)
            except Exception:
                # Never leave a lingering transaction holding the SQLite write
                # lock — roll back before propagating (the _loop logs it).
                await session.rollback()
                raise

            if stale_tasks:
                await bus.publish("heartbeat.stale_tasks", {
                    "count": len(stale_tasks),
                    "task_ids": [t["id"] for t in stale_tasks],
                })

            if blocked_leases:
                await bus.publish("heartbeat.blocked_leases", {
                    "count": len(blocked_leases),
                    "lease_ids": [l["id"] for l in blocked_leases],
                })

    async def _check_stale_tasks(self, session: AsyncSession) -> list[dict]:
        """Find tasks that have been in-progress for too long."""
        # SQLite stores naive datetimes, so compare against a NAIVE threshold in
        # the SQL query (the stored column value is naive). The Python-side
        # arithmetic below normalizes the DB value to aware UTC.
        threshold_naive = (datetime.now(timezone.utc) - timedelta(hours=STALE_TASK_THRESHOLD_HOURS)).replace(tzinfo=None)

        active_statuses = [
            TaskStatus.INVESTIGATE.value,
            TaskStatus.PLANNING.value,
            TaskStatus.IMPLEMENTATION.value,
            TaskStatus.VERIFICATION.value,
        ]

        result = await session.execute(
            select(Task)
            .where(Task.status.in_(active_statuses))
            .where(Task.started_at < threshold_naive)
        )
        stale = result.scalars().all()

        now = datetime.now(timezone.utc)
        stale_list = []
        for task in stale:
            started_at = _as_utc(task.started_at)
            stale_list.append({
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "started_at": started_at.isoformat() if started_at else None,
                "stuck_hours": (now - started_at).total_seconds() / 3600 if started_at else 0,
            })
            logger.warning(f"Stale task detected: {task.id} ({task.title}) — stuck for {stale_list[-1]['stuck_hours']:.1f}h")

        return stale_list

    async def _check_blocked_leases(self, session: AsyncSession) -> list[dict]:
        """Find worker leases that have been active for too long."""
        from storage.models import LeaseStatus
        threshold_naive = (datetime.now(timezone.utc) - timedelta(minutes=BLOCKED_LEASE_THRESHOLD_MINUTES)).replace(tzinfo=None)

        result = await session.execute(
            select(Lease)
            .where(Lease.status == LeaseStatus.ACTIVE.value)
            .where(Lease.created_at < threshold_naive)
        )
        blocked = result.scalars().all()

        now = datetime.now(timezone.utc)
        blocked_list = []
        for lease in blocked:
            created_at = _as_utc(lease.created_at)
            blocked_list.append({
                "id": lease.id,
                "task_id": lease.task_id,
                "worker_name": lease.worker_name,
                "worker_type": lease.worker_type,
                "phase": lease.phase,
                "active_minutes": (now - created_at).total_seconds() / 60 if created_at else 0,
            })
            logger.warning(
                f"Blocked lease: {lease.id} ({lease.worker_name}) — "
                f"active for {blocked_list[-1]['active_minutes']:.0f}m"
            )

        return blocked_list


# ── Module-level singleton ──────────────────────────────

heartbeat = HeartbeatScheduler()


def start_heartbeat():
    """Start the heartbeat scheduler. Called at app startup."""
    heartbeat.start()


def stop_heartbeat():
    """Stop the heartbeat scheduler. Called at app shutdown."""
    heartbeat.stop()

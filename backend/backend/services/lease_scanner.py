"""Background service for automatic lease expiration and recovery.

Scans for stale ACTIVE leases every 30 seconds and marks them EXPIRED.
Expired leases make their tasks reclaimable for retry/reassignment.
"""

import asyncio
import logging
from datetime import timedelta, datetime, timezone
from typing import Optional
from sqlalchemy import select
from storage.models import Lease, LeaseStatus, Task, TaskStatus

logger = logging.getLogger("aic.lease_scanner")


class LeaseScanner:
    """Background scanner that detects and expires stale worker leases."""
    
    def __init__(
        self,
        session_factory,
        heartbeat_interval: int = 30,  # seconds
        idle_timeout: int = 300,  # 5 minutes - max time without heartbeat
    ):
        self.session_factory = session_factory
        self.heartbeat_interval = heartbeat_interval
        self.idle_timeout = idle_timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start background lease scanning loop."""
        if self._running:
            logger.warning("Lease scanner already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("Lease scanner started (interval=%ds, timeout=%ds)", 
                    self.heartbeat_interval, self.idle_timeout)
    
    async def stop(self):
        """Stop background lease scanning loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Lease scanner stopped")
    
    async def _scan_loop(self):
        """Main loop: scan for stale leases every interval."""
        while self._running:
            try:
                await self._scan_stale_leases()
            except Exception as e:
                logger.error("Lease scan failed: %s", e, exc_info=True)
            
            # Wait for next cycle
            for _ in range(self.heartbeat_interval):
                if not self._running:
                    break
                await asyncio.sleep(1)
    
    async def _scan_stale_leases(self):
        """Find and expire ACTIVE leases past their expiration threshold.
        
        Primary mechanism: Check expires_at column (TTL-based).
        Fallback mechanism: If expires_at is not set, use last_heartbeat_at check.
        """
        async with self.session_factory() as session:
            now = datetime.now(timezone.utc)
            
            # PHASE 3 UPDATE: Use expires_at TTL as primary expiration check
            expired_leases = await session.execute(
                select(Lease).where(
                    Lease.status == LeaseStatus.ACTIVE.value,
                    Lease.expires_at < now,
                )
            )
            expired_list = expired_leases.scalars().all()
            
            if expired_list:
                logger.warning("Found %d EXPIRED leases (TTL exceeded)", len(expired_list))
                
                for lease in expired_list:
                    logger.info("Expiring lease %s for task %s (worker=%s, phase=%s, ttl_expired_at=%s)",
                                lease.id[:8], lease.task_id[:8] if lease.task_id else "N/A",
                                lease.worker_name, lease.phase, lease.expires_at.isoformat())
                    
                    lease.status = LeaseStatus.EXPIRED.value
                    lease.error_message = f"Lease expired (TTL={self.idle_timeout}s, expired at {lease.expires_at.isoformat()})"
                    lease.finished_at = now
                    
                    # Update associated task status if it was RUNNING
                    if lease.phase == "implementation":
                        result = await session.execute(
                            select(Task).where(Task.id == lease.task_id)
                        )
                        task = result.scalar_one_or_none()
                        if task and task.status == TaskStatus.RUNNING.value:
                            logger.info("Task %s marked BLOCKED due to lease expiration", task.id[:8])
                            task.status = TaskStatus.BLOCKED.value
                            task.error_message = f"Worker lease expired: {lease.error_message}"
                
                await session.commit()
                logger.info("Expired %d leases successfully via TTL check", len(expired_list))
            
            # Fallback: For legacy leases without expires_at, use last_heartbeat_at
            stale_heartbeat_count = 0
            cutoff_time = now - timedelta(seconds=self.idle_timeout)
            stale_leases = await session.execute(
                select(Lease).where(
                    Lease.status == LeaseStatus.ACTIVE.value,
                    Lease.expires_at.is_(None),
                    Lease.last_heartbeat_at < cutoff_time,
                )
            )
            stale_list = stale_leases.scalars().all()
            
            if stale_list:
                logger.warning("Found %d stale leases (no heartbeat)", len(stale_list))
                
                for lease in stale_list:
                    logger.info("Expiring stale lease %s for task %s (worker=%s, phase=%s, no_heartbeat_since=%s)",
                                lease.id[:8], lease.task_id[:8] if lease.task_id else "N/A",
                                lease.worker_name, lease.phase, lease.last_heartbeat_at.isoformat())
                    
                    lease.status = LeaseStatus.EXPIRED.value
                    lease.error_message = f"Lease expired: no heartbeat for {self.idle_timeout}s"
                    lease.finished_at = now
                    
                    if lease.phase == "implementation":
                        result = await session.execute(
                            select(Task).where(Task.id == lease.task_id)
                        )
                        task = result.scalar_one_or_none()
                        if task and task.status == TaskStatus.RUNNING.value:
                            logger.info("Task %s marked BLOCKED due to lease expiration", task.id[:8])
                            task.status = TaskStatus.BLOCKED.value
                            task.error_message = f"Worker lease expired: {lease.error_message}"
                    
                    stale_heartbeat_count += 1
                
                await session.commit()
                logger.info("Expired %d leases via heartbeat fallback", stale_heartbeat_count)
    
    @property
    def is_running(self) -> bool:
        """Check if scanner is actively running."""
        return self._running


# Global scanner instance (lazy initialization)
_scanner_instance: Optional[LeaseScanner] = None


def get_lease_scanner(session_factory) -> LeaseScanner:
    """Get or create global lease scanner instance."""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = LeaseScanner(session_factory)
    return _scanner_instance


_scanner_task: asyncio.Task | None = None


def _on_scanner_task_done(task: asyncio.Task) -> None:
    """Log if the lease-scanner loop dies unexpectedly (fire-and-forget guard)."""
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("Lease scanner loop died unexpectedly: %s", exc)


def start_lease_scanner(session_factory):
    """Convenience function to start lease scanner.

    The task reference is held module-level so it cannot be garbage-collected
    mid-flight, and a done-callback surfaces silent loop death.
    """
    global _scanner_task
    scanner = get_lease_scanner(session_factory)
    _scanner_task = asyncio.create_task(scanner.start())
    _scanner_task.add_done_callback(_on_scanner_task_done)
    return scanner

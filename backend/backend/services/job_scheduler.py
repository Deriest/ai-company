"""
Job Scheduler Service.

Manages a priority queue of background jobs with retry, progress tracking,
logs, and history. Jobs execute asynchronously via asyncio.
"""

import asyncio
import datetime
import json
import logging
from typing import Optional, Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.jobs import Job, JobLog

logger = logging.getLogger(__name__)


class JobSchedulerService:
    """Priority-based job queue with background execution."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a job type."""
        self._handlers[job_type] = handler

    # ── Job CRUD ──────────────────────────────────────────────

    @staticmethod
    async def create_job(
        db: AsyncSession,
        title: str,
        job_type: str,
        payload: dict,
        priority: int = 5,
        max_retries: int = 3,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        scheduled_at: Optional[datetime.datetime] = None,
    ) -> Job:
        job = Job(
            title=title,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            conversation_id=conversation_id,
            session_id=session_id,
            scheduled_at=scheduled_at,
            status="queued",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        await JobSchedulerService._add_log(db, job.id, "info", f"Job created: {title}")
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: str) -> Optional[Job]:
        res = await db.execute(select(Job).where(Job.id == job_id))
        return res.scalars().first()

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[Job]:
        query = select(Job).order_by(Job.priority, Job.created_at)
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.job_type == job_type)
        query = query.limit(limit)
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def cancel_job(db: AsyncSession, job_id: str) -> Job:
        job = await JobSchedulerService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status in ("completed", "cancelled"):
            raise ValueError(f"Job already {job.status}")
        job.status = "cancelled"
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        await JobSchedulerService._add_log(db, job.id, "info", "Job cancelled")
        await db.refresh(job)
        return job

    @staticmethod
    async def pause_job(db: AsyncSession, job_id: str) -> Job:
        job = await JobSchedulerService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != "queued":
            raise ValueError(f"Can only pause queued jobs, current status: {job.status}")
        job.status = "paused"
        await db.commit()
        await JobSchedulerService._add_log(db, job.id, "info", "Job paused")
        await db.refresh(job)
        return job

    @staticmethod
    async def resume_job(db: AsyncSession, job_id: str) -> Job:
        job = await JobSchedulerService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != "paused":
            raise ValueError(f"Can only resume paused jobs, current status: {job.status}")
        job.status = "queued"
        await db.commit()
        await JobSchedulerService._add_log(db, job.id, "info", "Job resumed")
        await db.refresh(job)
        return job

    # ── Progress & Logging ────────────────────────────────────

    @staticmethod
    async def update_progress(db: AsyncSession, job_id: str, progress: int, message: str = ""):
        job = await JobSchedulerService.get_job(db, job_id)
        if job:
            job.progress = min(100, max(0, progress))
            if message:
                await JobSchedulerService._add_log(db, job_id, "info", message)
            await db.commit()

    @staticmethod
    async def get_logs(db: AsyncSession, job_id: str, limit: int = 100) -> list[JobLog]:
        res = await db.execute(
            select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at).limit(limit)
        )
        return list(res.scalars().all())

    @staticmethod
    async def _add_log(db: AsyncSession, job_id: str, level: str, message: str, metadata: dict = None):
        log = JobLog(job_id=job_id, level=level, message=message, metadata=metadata)
        db.add(log)
        await db.commit()

    # ── Background Execution ──────────────────────────────────

    async def start_background_worker(self, db_factory):
        """Start the background job processor."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop(db_factory))

    async def stop_background_worker(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _process_loop(self, db_factory):
        """Main loop: pick highest-priority queued job and execute."""
        while self._running:
            try:
                async with db_factory() as db:
                    # Find next eligible job
                    now = datetime.datetime.now(datetime.timezone.utc)
                    res = await db.execute(
                        select(Job)
                        .where(Job.status == "queued")
                        .where((Job.scheduled_at == None) | (Job.scheduled_at <= now))
                        .order_by(Job.priority, Job.created_at)
                        .limit(1)
                    )
                    job = res.scalars().first()

                    if not job:
                        await asyncio.sleep(2)
                        continue

                    await self._execute_job(db, job)

            except Exception as e:
                logger.error(f"Job scheduler error: {e}")
                await asyncio.sleep(5)

    async def _execute_job(self, db: AsyncSession, job: Job):
        """Execute a single job with retry support."""
        handler = self._handlers.get(job.job_type)
        if not handler:
            job.status = "failed"
            job.error_message = f"No handler registered for job type '{job.job_type}'"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await self._add_log(db, job.id, "error", job.error_message)
            logger.error(json.dumps({
                "event": "job_no_handler",
                "job_id": job.id,
                "job_type": job.job_type,
            }))
            return

        max_attempts = job.max_retries + 1
        for attempt in range(max_attempts):
            # FIX: cancel_job() may have run while we were waiting — re-check
            # the DB status so a cancelled job is never re-executed.
            await db.refresh(job)
            if job.status == "cancelled":
                return
            job.status = "running"
            job.retry_count = attempt
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await self._add_log(db, job.id, "info", f"Execution started (attempt {attempt + 1}/{max_attempts})")
            logger.info(json.dumps({
                "event": "job_started",
                "job_id": job.id,
                "job_type": job.job_type,
                "attempt": attempt + 1,
                "max_attempts": max_attempts,
            }))

            try:
                result = await handler(job.payload, db, lambda p, m=None: self._progress_cb(db, job.id, p, m))
                # FIX: don't overwrite a "cancelled" status — cancel_job() may
                # have flipped the DB row while the handler was running.
                await db.refresh(job)
                if job.status == "cancelled":
                    return
                job.result = result
                job.status = "completed"
                job.progress = 100
                job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                await db.commit()
                await self._add_log(db, job.id, "info", "Job completed successfully")
                logger.info(json.dumps({
                    "event": "job_completed",
                    "job_id": job.id,
                    "job_type": job.job_type,
                }))
                return

            except Exception as e:
                error_msg = f"{str(e)} (attempt {attempt + 1}/{max_attempts})"
                await self._add_log(db, job.id, "error", error_msg)
                logger.error(json.dumps({
                    "event": "job_failed",
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "attempt": attempt + 1,
                    "error": str(e),
                }))

                if attempt < max_attempts - 1:
                    # FIX: don't resurrect a job that was cancelled while the
                    # handler was running (cancel_job may have committed first).
                    await db.refresh(job)
                    if job.status == "cancelled":
                        return
                    job.status = "queued"
                    await db.commit()
                    wait = min(2 ** attempt, 60)
                    await self._add_log(db, job.id, "info", f"Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    await db.commit()

    async def _progress_cb(self, db: AsyncSession, job_id: str, progress: int, message: str = None):
        """Callback for handlers to report progress."""
        await self.update_progress(db, job_id, progress, message or "")


job_scheduler = JobSchedulerService()

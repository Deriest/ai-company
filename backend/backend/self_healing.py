"""AIC Platform — Autonomous Self-Healing & Diagnostic Engine.

Audits runtime health: stale worker leases, stuck in-progress tasks,
and undispatched created tasks. Applies repairs and can re-dispatch work.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Lease, LeaseStatus, Message, Task, Worker, WorkerStatus

logger = logging.getLogger("aic.self_healing")

# Strong references to fire-and-forget re-dispatch tasks. asyncio.create_task
# without a reference can be garbage-collected mid-flight, silently dropping the
# coroutine; the set prevents GC until each task completes.
_self_healing_tasks: set = set()

# Phases that indicate work was interrupted mid-flight (server kill / crash).
STALE_IN_PROGRESS = (
    "planning",
    "implementation",
    "investigate",
    "verification",
    "closeout",
    "discovery",
)


class HealthDiagnosticReport:
    def __init__(
        self,
        status: str,
        issues_found: list[str],
        repairs_applied: list[str],
        timestamp: str,
        redispatched_task_ids: list[str] | None = None,
    ):
        self.status = status
        self.issues_found = issues_found
        self.repairs_applied = repairs_applied
        self.timestamp = timestamp
        self.redispatched_task_ids = redispatched_task_ids or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "issues_found": self.issues_found,
            "repairs_applied": self.repairs_applied,
            "timestamp": self.timestamp,
            "redispatched_task_ids": self.redispatched_task_ids,
        }


class SelfHealingEngine:
    """Runtime recovery authority — must be invoked from app lifespan / cron."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def audit_and_repair(
        self,
        *,
        redispatch_created: bool = True,
        cancel_stale_in_progress: bool = True,
        expire_blocked_leases: bool = True,
    ) -> HealthDiagnosticReport:
        issues: list[str] = []
        repairs: list[str] = []
        redispatched: list[str] = []

        try:
            # 1. Workers stuck WORKING without an ACTIVE lease
            worker_q = select(Worker).where(Worker.status == WorkerStatus.WORKING.value)
            working_workers = (await self.session.execute(worker_q)).scalars().all()
            for w in working_workers:
                lease = None
                if w.current_lease_id:
                    lease = (
                        await self.session.execute(
                            select(Lease).where(Lease.id == w.current_lease_id)
                        )
                    ).scalar_one_or_none()
                if not lease or lease.status != LeaseStatus.ACTIVE.value:
                    issues.append(
                        f"Worker '{w.name}' has stale/missing lease {w.current_lease_id}"
                    )
                    w.status = WorkerStatus.IDLE.value
                    w.current_task_id = None
                    w.current_lease_id = None
                    repairs.append(f"Reset worker '{w.name}' to IDLE")

            # 1b. Expire ACTIVE leases that have been running too long (>30 min)
            # so the worker is freed and the task can be retried.
            if expire_blocked_leases:
                from datetime import timedelta
                threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
                threshold_naive = threshold.replace(tzinfo=None)
                res_leases = await self.session.execute(
                    select(Lease).where(
                        Lease.status == LeaseStatus.ACTIVE.value,
                        Lease.created_at < threshold_naive,
                    )
                )
                blocked_leases = res_leases.scalars().all()
                for lease in blocked_leases:
                    lease.status = LeaseStatus.EXPIRED.value
                    lease.error_message = "Expired by self-healing (blocked >30min)"
                    issues.append(
                        f"Lease {lease.id[:8]} ({lease.worker_name}) blocked >30min"
                    )
                    repairs.append(f"Expired lease {lease.id[:8]} ({lease.worker_name})")
                    # Reset the owning worker so it can accept new work
                    if lease.worker_id:
                        wres = await self.session.execute(
                            select(Worker).where(Worker.id == lease.worker_id)
                        )
                        w = wres.scalar_one_or_none()
                        if w and w.status == WorkerStatus.WORKING.value:
                            w.status = WorkerStatus.IDLE.value
                            w.current_task_id = None
                            w.current_lease_id = None
                            repairs.append(f"Reset worker '{w.name}' to IDLE after lease expiry")

            # 2. Cancel tasks left mid-phase after process death
            if cancel_stale_in_progress:
                res = await self.session.execute(
                    select(Task).where(
                        or_(*[Task.status == p for p in STALE_IN_PROGRESS])
                    )
                )
                stale_tasks = res.scalars().all()
                for t in stale_tasks:
                    prev = t.status
                    t.status = "cancelled"
                    t.error_message = t.error_message or "Cancelled by self-healing (stale in-progress)"
                    issues.append(f"Task {t.id[:8]} stuck in '{prev}'")
                    repairs.append(f"Cancelled task {t.id[:8]} (was {prev})")

            # 2b. Cancel stale streaming Message rows left over after a hard
            # kill/restart — mirror the task query above for messages so a
            # crashed stream never leaves an assistant row stuck in "streaming".
            res_msg = await self.session.execute(
                select(Message).where(Message.status == "streaming")
            )
            for msg in res_msg.scalars().all():
                prev = msg.status
                msg.status = "cancelled"
                msg.updated_at = datetime.now(timezone.utc)
                issues.append(f"Message {msg.id[:8]} stuck in '{prev}'")
                repairs.append(f"Cancelled streaming message {msg.id[:8]} (was {prev})")

            # 3. Re-dispatch tasks still in 'created'
            if redispatch_created:
                res2 = await self.session.execute(
                    select(Task).where(Task.status == "created")
                )
                created = res2.scalars().all()
                if created:
                    issues.append(f"{len(created)} task(s) in status 'created'")
                    await self.session.commit()
                    from backend.routes.conversations import _dispatch_created_task

                    # Find which of these "created" parents are owned by
                    # MasterOrchestrator (they have child/decomposed subtasks).
                    child_parent_ids: set[str] = set()
                    if created:
                        child_res = await self.session.execute(
                            select(Task.parent_task_id).where(
                                Task.parent_task_id.in_([str(c.id) for c in created])
                            )
                        )
                        child_parent_ids = {
                            str(r[0]) for r in child_res.all() if r[0] is not None
                        }

                    for t in created:
                        tid = str(t.id)
                        tctx = t.context or {}
                        # Skip tasks owned by MasterOrchestrator: their parent
                        # row stays "created" while the pipeline executes
                        # children, so re-dispatching would duplicate execution.
                        if (
                            tctx.get("brief_id")
                            or tctx.get("graph_id")
                            or tctx.get("dispatch_id")
                            or tid in child_parent_ids
                        ):
                            repairs.append(f"Skipped orchestrated parent {tid[:8]} (not re-dispatched)")
                            continue
                        # Atomic claim (TOCTOU fix): only dispatch if this exact
                        # task is STILL 'created'. A guarded UPDATE prevents two
                        # concurrent self-healing runs / dispatchers from
                        # double-claiming the same task.
                        # Atomic claim: only dispatch if this task is still 'created'.
                        # Use 'investigate' (the first FSM phase) instead of 'in_progress'
                        # because TaskStatus has no IN_PROGRESS value — valid statuses:
                        # created/investigate/planning/implementation/verification/closeout/test/review/documentation/completed/cancelled/blocked/failed
                        claim = await self.session.execute(
                            update(Task)
                            .where(Task.id == tid, Task.status == "created")
                            .values(status="investigate")
                        )
                        if claim.rowcount != 1:
                            repairs.append(f"Skipped task {tid[:8]} (already claimed)")
                            continue
                        redispatched.append(tid)
                        # L7: hold a strong reference so the task is not
                        # garbage-collected before it completes.
                        task_ref = asyncio.create_task(_dispatch_created_task(tid))
                        _self_healing_tasks.add(task_ref)
                        task_ref.add_done_callback(_self_healing_tasks.discard)
                        repairs.append(f"Re-dispatched task {tid[:8]}")
                    # Persist the atomic claim updates (status -> in_progress).
                    await self.session.commit()
                else:
                    await self.session.commit()
            else:
                await self.session.commit()

            status = "healthy" if not issues else "repaired"
            return HealthDiagnosticReport(
                status=status,
                issues_found=issues,
                repairs_applied=repairs,
                timestamp=datetime.now(timezone.utc).isoformat(),
                redispatched_task_ids=redispatched,
            )
        except Exception as e:
            logger.error("Self-healing audit failed: %s", e)
            await self.session.rollback()
            return HealthDiagnosticReport(
                status="error",
                issues_found=[str(e)],
                repairs_applied=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )


async def run_startup_self_heal() -> HealthDiagnosticReport:
    """Entry used by FastAPI lifespan — seeds skills then heals."""
    from storage.database import async_session

    async with async_session() as session:
        try:
            from backend.skill_engine import seed_builtin_skills

            await seed_builtin_skills(session)
        except Exception as e:
            logger.warning("Skill seed during self-heal: %s", e)

        engine = SelfHealingEngine(session)
        report = await engine.audit_and_repair()
        logger.info(
            "Self-heal complete: status=%s issues=%d repairs=%d",
            report.status,
            len(report.issues_found),
            len(report.repairs_applied),
        )
        return report

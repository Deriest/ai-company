"""AIC Platform — Autonomous Self-Healing & Diagnostic Engine.

Audits runtime health: stale worker leases, stuck in-progress tasks,
and undispatched created tasks. Applies repairs and can re-dispatch work.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
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

                    for t in created:
                        tid = str(t.id)
                        redispatched.append(tid)
                        # L7: hold a strong reference so the task is not
                        # garbage-collected before it completes.
                        task_ref = asyncio.create_task(_dispatch_created_task(tid))
                        _self_healing_tasks.add(task_ref)
                        task_ref.add_done_callback(_self_healing_tasks.discard)
                        repairs.append(f"Re-dispatched task {tid[:8]}")
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

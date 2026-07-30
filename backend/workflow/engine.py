"""AIC Platform — Workflow Engine.

Orchestrates task lifecycle through FSM phases.
Enforces barriers, approvals, and PM review gates by code.
"""
from datetime import datetime, timezone
from typing import Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from storage.models import Task, WorkflowState, TaskStatus, ApprovalStatus
from workflow.fsm import (
    PHASE_ORDER, TERMINAL_STATES, APPROVAL_PHASES,
    normalize_phase, validate_phase, next_phase, is_terminal,
    can_advance, allowed_workers_for_phase, Barrier,
)

logger = logging.getLogger("aic.workflow")


class WorkflowError(Exception):
    """Workflow violation — transition not allowed."""
    pass


class WorkflowEngine:
    """Manages task phase transitions with enforcement."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_state(self, task: Task) -> WorkflowState:
        """Get existing workflow state or create one."""
        # Use explicit query instead of lazy relationship (avoids greenlet issue)
        result = await self.session.execute(
            select(WorkflowState).where(WorkflowState.task_id == task.id)
        )
        ws = result.scalar_one_or_none()

        if ws:
            return ws

        ws = WorkflowState(
            task_id=task.id,
            current_phase=task.status,
            previous_phase=None,
            barrier={},
            history=[],
            recovery_attempts=0,
            pm_review_passed=False,
        )
        self.session.add(ws)
        await self.session.flush()
        return ws

    async def advance(
        self,
        task: Task,
        barrier_complete: bool = False,
        pm_review_passed: bool = False,
        approval_passed: bool = True,
    ) -> str:
        """Advance task to next phase if conditions met.

        Returns new phase. Raises WorkflowError if cannot advance.
        """
        ws = await self.get_or_create_state(task)
        current = normalize_phase(ws.current_phase)

        if is_terminal(current):
            raise WorkflowError(f"Task {task.id} is in terminal state: {current}")

        if not can_advance(current, barrier_complete, pm_review_passed, approval_passed):
            reasons = []
            if not barrier_complete:
                reasons.append("barrier not complete")
            if current in APPROVAL_PHASES and not approval_passed:
                reasons.append("approval not passed")
            if current == "closeout" and not pm_review_passed:
                reasons.append("PM review not passed")
            raise WorkflowError(f"Cannot advance from {current}: {', '.join(reasons)}")

        nxt = next_phase(current)
        if not nxt:
            raise WorkflowError(f"No next phase after {current}")

        # Record history
        history = ws.history or []
        history.append({
            "phase": current,
            "entered_at": ws.updated_at.isoformat() if ws.updated_at else None,
            "exited_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        })
        ws.history = history
        flag_modified(ws, 'history')

        ws.previous_phase = current
        ws.current_phase = nxt
        ws.barrier = {}
        flag_modified(ws, 'barrier')
        ws.pm_review_passed = False

        task.status = nxt
        task.progress = _phase_progress(nxt)

        if nxt == "completed":
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100

        await self.session.flush()
        logger.info(f"Task {task.id} advanced: {current} → {nxt}")

        # Broadcast phase advance event
        try:
            from backend.routes.websocket import broadcast_task_event
            await broadcast_task_event(
                "phase.advanced",
                task.id,
                {
                    "previous_phase": current,
                    "current_phase": nxt,
                    "progress": task.progress,
                },
            )
        except Exception:
            pass  # Don't fail workflow on broadcast error

        return nxt

    async def cancel(self, task: Task, reason: str = "") -> None:
        """Cancel a task. No-op if already terminal."""
        ws = await self.get_or_create_state(task)
        current = normalize_phase(ws.current_phase)

        if is_terminal(current):
            raise WorkflowError(f"Task {task.id} already terminal: {current}")

        ws.history.append({
            "phase": current,
            "entered_at": ws.updated_at.isoformat() if ws.updated_at else None,
            "exited_at": datetime.now(timezone.utc).isoformat(),
            "status": "cancelled",
            "reason": reason,
        })

        ws.current_phase = "cancelled"
        ws.barrier = {}
        task.status = "cancelled"
        task.error_message = reason or None
        await self.session.flush()
        logger.info(f"Task {task.id} cancelled: {reason}")

    async def block(self, task: Task, reason: str) -> None:
        """Block a task due to failure."""
        ws = await self.get_or_create_state(task)
        ws.current_phase = "blocked"
        ws.barrier = {}
        task.status = "blocked"
        task.error_message = reason
        await self.session.flush()
        logger.warning(f"Task {task.id} blocked: {reason}")

    async def fail(self, task: Task, reason: str) -> None:
        """Mark task as failed."""
        ws = await self.get_or_create_state(task)
        ws.current_phase = "failed"
        ws.barrier = {}
        task.status = "failed"
        task.error_message = reason
        await self.session.flush()
        logger.error(f"Task {task.id} failed: {reason}")

    async def start_phase(self, task: Task, phase: str | None = None) -> Barrier:
        """Start a phase — creates and returns the barrier."""
        ws = await self.get_or_create_state(task)
        p = normalize_phase(phase or ws.current_phase)

        if is_terminal(p):
            raise WorkflowError(f"Cannot start phase: task is terminal: {p}")

        workers = allowed_workers_for_phase(p)
        barrier = Barrier.start(workers, timeout=600)
        ws.barrier = barrier.to_dict()
        flag_modified(ws, 'barrier')
        await self.session.flush()
        logger.info(f"Task {task.id} phase {p} started, barrier workers: {workers}")
        return barrier

    async def mark_worker_complete(self, task: Task, worker: str) -> Barrier:
        """Mark a worker as completed in current barrier."""
        ws = await self.get_or_create_state(task)
        barrier = Barrier.from_dict(ws.barrier or {})
        barrier.mark_complete(worker)
        ws.barrier = barrier.to_dict()
        flag_modified(ws, 'barrier')
        await self.session.flush()
        return barrier

    async def mark_worker_failed(self, task: Task, worker: str, reason: str) -> Barrier:
        """Mark a worker as failed in current barrier."""
        ws = await self.get_or_create_state(task)
        barrier = Barrier.from_dict(ws.barrier or {})
        barrier.mark_failed(worker, reason)
        ws.barrier = barrier.to_dict()
        flag_modified(ws, 'barrier')
        await self.session.flush()
        return barrier

    async def is_barrier_satisfied(self, task: Task) -> bool:
        """Check if current phase barrier is satisfied."""
        ws = await self.get_or_create_state(task)
        if not ws.barrier:
            return False
        barrier = Barrier.from_dict(ws.barrier)
        return barrier.is_satisfied()

    async def set_pm_review(self, task: Task, passed: bool) -> None:
        """Set PM review result."""
        ws = await self.get_or_create_state(task)
        ws.pm_review_passed = passed
        await self.session.flush()


def _phase_progress(phase: str) -> int:
    """Map phase to progress percentage."""
    p = normalize_phase(phase)
    progress_map = {
        "created": 0,
        "discovery": 5,
        "investigate": 15,
        "planning": 25,
        "implementation": 55,
        "verification": 80,
        "closeout": 95,
        "completed": 100,
        "cancelled": 0,
        "blocked": 0,
        "failed": 0,
    }
    return progress_map.get(p, 0)

import asyncio
"""
Multi-Agent Orchestration Service.

Manages orchestration sessions, task routing, sequential/parallel execution,
shared context, approval chains, and worker lifecycle.
"""

import datetime
import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.orchestration import (
    OrchestrationSession, OrchestrationTask, OrchestrationApproval,
    WorkflowDefinition, Checkpoint,
)
from backend.models.conversation import Message
from backend.services.worker_runtime_service import worker_runtime_service
from backend.services.chat_service import chat_service

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Core orchestration engine for multi-worker task execution."""

    # ── Session Management ────────────────────────────────────

    @staticmethod
    async def create_session(
        db: AsyncSession,
        conversation_id: str,
        mode: str = "sequential",
        created_by: str = "manager",
    ) -> OrchestrationSession:
        session = OrchestrationSession(
            conversation_id=conversation_id,
            mode=mode,
            status="pending",
            created_by=created_by,
            shared_context={},
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info(json.dumps({
            "event": "orchestration_session_created",
            "session_id": session.id,
            "conversation_id": conversation_id,
            "mode": mode,
        }))
        return session

    @staticmethod
    async def get_session(db: AsyncSession, session_id: str) -> Optional[OrchestrationSession]:
        res = await db.execute(select(OrchestrationSession).where(OrchestrationSession.id == session_id))
        return res.scalars().first()

    @staticmethod
    async def list_sessions(
        db: AsyncSession, conversation_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[OrchestrationSession]:
        query = select(OrchestrationSession).order_by(OrchestrationSession.created_at.desc())
        if conversation_id:
            query = query.where(OrchestrationSession.conversation_id == conversation_id)
        if status:
            query = query.where(OrchestrationSession.status == status)
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def cancel_session(db: AsyncSession, session_id: str) -> OrchestrationSession:
        session = await OrchestratorService.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status in ("completed", "cancelled"):
            raise ValueError(f"Session already {session.status}")
        session.status = "cancelled"
        session.completed_at = datetime.datetime.now(datetime.timezone.utc)
        # Cancel all pending/running tasks
        res = await db.execute(
            select(OrchestrationTask).where(
                OrchestrationTask.session_id == session_id,
                OrchestrationTask.status.in_(["pending", "queued", "running"]),
            )
        )
        for task in res.scalars().all():
            task.status = "cancelled"
        await db.commit()
        await db.refresh(session)
        return session

    # ── Task Management ───────────────────────────────────────

    @staticmethod
    async def add_task(
        db: AsyncSession,
        session_id: str,
        worker_role: str,
        title: str,
        description: str = "",
        input_context: Optional[dict] = None,
        depends_on: Optional[list[str]] = None,
    ) -> OrchestrationTask:
        # Get next sequence order
        res = await db.execute(
            select(OrchestrationTask)
            .where(OrchestrationTask.session_id == session_id)
            .order_by(OrchestrationTask.sequence_order.desc())
        )
        last = res.scalars().first()
        next_order = (last.sequence_order + 1) if last else 0

        task = OrchestrationTask(
            session_id=session_id,
            worker_role=worker_role,
            title=title,
            description=description,
            input_context=input_context or {},
            depends_on=depends_on or [],
            sequence_order=next_order,
            status="pending",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_tasks(db: AsyncSession, session_id: str) -> list[OrchestrationTask]:
        res = await db.execute(
            select(OrchestrationTask)
            .where(OrchestrationTask.session_id == session_id)
            .order_by(OrchestrationTask.sequence_order)
        )
        return list(res.scalars().all())

    @staticmethod
    async def get_task(db: AsyncSession, task_id: str) -> Optional[OrchestrationTask]:
        res = await db.execute(select(OrchestrationTask).where(OrchestrationTask.id == task_id))
        return res.scalars().first()

    # ── Execution Engine ──────────────────────────────────────

    @staticmethod
    async def execute_session(db: AsyncSession, session_id: str) -> OrchestrationSession:
        """Run the orchestration session. Routes to sequential or parallel."""
        session = await OrchestratorService.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status not in ("pending", "paused"):
            raise ValueError(f"Session status '{session.status}' is not executable")

        session.status = "running"
        session.started_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        logger.info(json.dumps({
            "event": "orchestration_session_started",
            "session_id": session_id,
            "mode": session.mode,
        }))

        try:
            if session.mode == "parallel":
                await OrchestratorService._execute_parallel(db, session)
            else:
                await OrchestratorService._execute_sequential(db, session)

            # Check final status
            await db.refresh(session)
            tasks = await OrchestratorService.get_tasks(db, session_id)
            has_failure = any(t.status == "failed" for t in tasks)
            all_done = all(t.status in ("completed", "skipped") for t in tasks)

            if has_failure:
                session.status = "failed"
            elif all_done:
                session.status = "completed"
            session.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await db.refresh(session)
            logger.info(json.dumps({
                "event": "orchestration_session_completed",
                "session_id": session_id,
                "status": session.status,
            }))
        except Exception as e:
            session.status = "failed"
            session.error_message = str(e)
            session.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            logger.error(json.dumps({
                "event": "orchestration_session_failed",
                "session_id": session_id,
                "error": str(e),
            }))
            raise

        return session

    @staticmethod
    async def _execute_sequential(db: AsyncSession, session: OrchestrationSession):
        """Execute tasks one by one in sequence_order."""
        tasks = await OrchestratorService.get_tasks(db, session.id)
        for task in tasks:
            if task.status in ("completed", "skipped", "cancelled"):
                continue
            await OrchestratorService._run_single_task(db, session, task)
            if task.status == "failed":
                break  # Stop on failure in sequential mode

    @staticmethod
    async def _execute_parallel(db: AsyncSession, session: OrchestrationSession):
        """Execute tasks respecting dependency graph."""
        tasks = await OrchestratorService.get_tasks(db, session.id)
        completed_ids: set[str] = set()
        for t in tasks:
            if t.status == "completed":
                completed_ids.add(t.id)

        remaining = [t for t in tasks if t.status not in ("completed", "skipped", "cancelled")]
        max_iterations = len(remaining) + 1
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            executed_this_round = False
            still_remaining = []

            for task in remaining:
                deps = task.depends_on or []
                deps_met = all(d in completed_ids for d in deps)
                if not deps_met:
                    still_remaining.append(task)
                    continue

                await OrchestratorService._run_single_task(db, session, task)
                if task.status == "completed":
                    completed_ids.add(task.id)
                executed_this_round = True

            remaining = still_remaining
            if not executed_this_round and remaining:
                # Deadlock: remaining tasks have unmet dependencies
                for t in remaining:
                    t.status = "failed"
                    t.error_message = "Dependency deadlock: required tasks not completed"
                await db.commit()
                break

    @staticmethod
    async def _run_single_task(
        db: AsyncSession, session: OrchestrationSession, task: OrchestrationTask
    ):
        """Execute a single task with retry and timeout support."""
        # Evaluate condition if present
        if task.condition:
            next_task = OrchestratorService.evaluate_condition(task.condition, session.shared_context or {})
            if not next_task:
                task.status = "skipped"
                task.error_message = "Condition evaluated to no target"
                await db.commit()
                return

        await OrchestratorService._run_with_retry_and_timeout(db, session, task)

    # ── Approval Chain ────────────────────────────────────────

    @staticmethod
    async def request_approval(
        db: AsyncSession, task_id: str, reason: str = ""
    ) -> OrchestrationApproval:
        task = await OrchestratorService.get_task(db, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        approval = OrchestrationApproval(
            task_id=task_id,
            session_id=task.session_id,
            status="pending",
            reason=reason,
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)
        return approval

    @staticmethod
    async def resolve_approval(
        db: AsyncSession, approval_id: str, approved: bool, notes: str = ""
    ) -> OrchestrationApproval:
        res = await db.execute(
            select(OrchestrationApproval).where(OrchestrationApproval.id == approval_id)
        )
        approval = res.scalars().first()
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        approval.status = "approved" if approved else "rejected"
        approval.reviewer_notes = notes
        approval.resolved_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        await db.refresh(approval)
        return approval

    @staticmethod
    async def get_approvals(
        db: AsyncSession, session_id: str
    ) -> list[OrchestrationApproval]:
        res = await db.execute(
            select(OrchestrationApproval)
            .where(OrchestrationApproval.session_id == session_id)
            .order_by(OrchestrationApproval.requested_at)
        )
        return list(res.scalars().all())



    # ── Workflow Definitions ───────────────────────────────────

    @staticmethod
    async def create_workflow(
        db: AsyncSession, name: str, dag: dict, description: str = ""
    ) -> WorkflowDefinition:
        wf = WorkflowDefinition(name=name, dag=dag, description=description)
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        return wf

    @staticmethod
    async def get_workflow(db: AsyncSession, wf_id: str) -> Optional[WorkflowDefinition]:
        res = await db.execute(select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id))
        return res.scalars().first()

    @staticmethod
    async def list_workflows(db: AsyncSession) -> list[WorkflowDefinition]:
        res = await db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.is_active == True).order_by(WorkflowDefinition.name)
        )
        return list(res.scalars().all())

    @staticmethod
    async def instantiate_workflow(
        db: AsyncSession, workflow_id: str, conversation_id: str
    ) -> OrchestrationSession:
        wf = await OrchestratorService.get_workflow(db, workflow_id)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found")
        dag = wf.dag
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])

        session = await OrchestratorService.create_session(db, conversation_id, mode="sequential")
        node_id_to_task_id: dict[str, str] = {}

        for node in nodes:
            # Find dependency node IDs from edges
            dep_node_ids = [e["from"] for e in edges if e["to"] == node["id"]]
            # Map to actual task IDs
            dep_task_ids = [node_id_to_task_id[nid] for nid in dep_node_ids if nid in node_id_to_task_id]

            task = await OrchestratorService.add_task(
                db, session.id,
                worker_role=node.get("worker", "thinker"),
                title=node.get("title", node["id"]),
                description=node.get("description", ""),
                input_context=node.get("input", {}),
                depends_on=dep_task_ids if dep_task_ids else None,
            )
            node_id_to_task_id[node["id"]] = task.id

        return session

    # ── Retry & Timeout ───────────────────────────────────────

    @staticmethod
    async def _run_with_retry_and_timeout(
        db: AsyncSession, session: OrchestrationSession, task: OrchestrationTask
    ):
        """Run a task with retry and timeout support."""
        max_attempts = task.max_retries + 1
        timeout = task.timeout_seconds or 300  # default 5 min

        for attempt in range(max_attempts):
            task.retry_count = attempt
            task.status = "running"
            task.started_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            logger.info(json.dumps({
                "event": "orchestration_task_started",
                "task_id": task.id,
                "session_id": session.id,
                "worker_role": task.worker_role,
                "attempt": attempt + 1,
                "max_attempts": max_attempts,
            }))

            try:
                await asyncio.wait_for(
                    OrchestratorService._execute_task_body(db, session, task),
                    timeout=timeout,
                )
                task.status = "completed"
                task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                await db.commit()
                logger.info(json.dumps({
                    "event": "orchestration_task_completed",
                    "task_id": task.id,
                    "session_id": session.id,
                    "worker_role": task.worker_role,
                }))

                # Create checkpoint
                checkpoint = Checkpoint(
                    session_id=session.id,
                    task_id=task.id,
                    state={"status": "completed", "output": task.output_context},
                )
                db.add(checkpoint)
                await db.commit()
                return

            except asyncio.TimeoutError:
                task.error_message = f"Task timed out after {timeout}s (attempt {attempt + 1}/{max_attempts})"
                logger.warning(json.dumps({
                    "event": "orchestration_task_timeout",
                    "task_id": task.id,
                    "session_id": session.id,
                    "attempt": attempt + 1,
                    "timeout_s": timeout,
                }))
                if attempt < max_attempts - 1:
                    task.status = "pending"
                    await db.commit()
                    await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    task.status = "failed"
                    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    await db.commit()

            except Exception as e:
                task.error_message = f"{str(e)} (attempt {attempt + 1}/{max_attempts})"
                logger.error(json.dumps({
                    "event": "orchestration_task_error",
                    "task_id": task.id,
                    "session_id": session.id,
                    "attempt": attempt + 1,
                    "error": str(e),
                }))
                if attempt < max_attempts - 1:
                    task.status = "pending"
                    await db.commit()
                    await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    task.status = "failed"
                    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    await db.commit()

    @staticmethod
    async def _execute_task_body(db: AsyncSession, session: OrchestrationSession, task: OrchestrationTask):
        """The actual task execution logic (called by _run_with_retry_and_timeout)."""
        worker = await worker_runtime_service.get_worker(db, task.worker_role)
        if not worker or not worker.is_enabled:
            task.status = "skipped"
            task.error_message = f"Worker '{task.worker_role}' not found or disabled"
            await db.commit()
            return

        shared = session.shared_context or {}
        task_input = task.input_context or {}
        prompt_parts = []
        if task.description:
            prompt_parts.append(task.description)
        if shared:
            prompt_parts.append(f"Shared context: {shared}")
        if task_input:
            prompt_parts.append(f"Task input: {task_input}")
        full_prompt = "\n\n".join(prompt_parts) if prompt_parts else task.title

        result = await chat_service.chat_completion(
            db=db,
            conversation_id=session.conversation_id,
            messages=[{"role": "user", "content": full_prompt}],
            provider_id=worker.provider_id,
            model_id=worker.model_id,
            temperature=worker.temperature,
            top_p=worker.top_p,
            max_output_tokens=worker.max_output_tokens,
            system_prompt=worker.system_prompt,
        )

        task.output_context = {"response": result.get("content", ""), "message_id": result.get("id", "")}
        shared[f"task_{task.worker_role}_output"] = result.get("content", "")
        session.shared_context = shared
        await db.commit()

    # ── Condition Evaluation ───────────────────────────────────

    @staticmethod
    def evaluate_condition(condition: dict, shared_context: dict) -> str:
        """Evaluate a condition and return the next task ID."""
        field = condition.get("field", "")
        op = condition.get("op", "eq")
        value = condition.get("value", "")
        then_task = condition.get("then", "")
        else_task = condition.get("else", "")

        actual = shared_context.get(field, "")
        if op == "eq":
            met = str(actual) == str(value)
        elif op == "neq":
            met = str(actual) != str(value)
        elif op == "gt":
            met = float(actual) > float(value) if actual else False
        elif op == "lt":
            met = float(actual) < float(value) if actual else False
        elif op == "contains":
            met = str(value) in str(actual)
        else:
            met = False

        return then_task if met else else_task

    # ── Checkpoint Management ──────────────────────────────────

    @staticmethod
    async def get_checkpoints(db: AsyncSession, session_id: str) -> list[Checkpoint]:
        res = await db.execute(
            select(Checkpoint).where(Checkpoint.session_id == session_id).order_by(Checkpoint.created_at)
        )
        return list(res.scalars().all())

    @staticmethod
    async def resume_from_checkpoint(db: AsyncSession, session_id: str) -> OrchestrationSession:
        """Resume a failed session from its last checkpoint."""
        session = await OrchestratorService.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status not in ("failed", "paused"):
            raise ValueError(f"Cannot resume session with status '{session.status}'")

        checkpoints = await OrchestratorService.get_checkpoints(db, session_id)
        completed_task_ids = {c.task_id for c in checkpoints}

        session.status = "running"
        await db.commit()

        tasks = await OrchestratorService.get_tasks(db, session_id)
        for task in tasks:
            if task.id in completed_task_ids:
                continue
            if task.status in ("completed", "skipped", "cancelled"):
                continue
            await OrchestratorService._run_with_retry_and_timeout(db, session, task)
            if task.status == "failed":
                session.status = "failed"
                await db.commit()
                return session

        session.status = "completed"
        session.completed_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session

orchestrator_service = OrchestratorService()

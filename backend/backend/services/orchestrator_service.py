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
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.services.content_utils import content_to_text
from backend.models.orchestration import (
    OrchestrationSession, OrchestrationTask, OrchestrationApproval,
    WorkflowDefinition, Checkpoint,
)
from backend.services.worker_runtime_service import worker_runtime_service

logger = logging.getLogger(__name__)


class MalformedDefinitionError(ValueError):
    """Raised when a workflow DAG is malformed (missing/invalid node/edge fields).

    Subclasses ValueError but is handled separately by routes so a malformed
    definition maps to a 400 instead of the generic 404 used for missing rows.
    """


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

        # FIX: atomic check-then-act gate — two concurrent POST /execute on the
        # same session must not both pass. The conditional UPDATE claims the
        # session (pending/paused -> running) atomically; rowcount 0 means
        # another runner already claimed it (or the session is terminal).
        now = datetime.datetime.now(datetime.timezone.utc)
        res = await db.execute(
            update(OrchestrationSession)
            .where(
                OrchestrationSession.id == session_id,
                OrchestrationSession.status.in_(["pending", "paused"]),
            )
            .values(status="running", started_at=now)
        )
        if res.rowcount != 1:
            # The claim failed — either the session is terminal (cancelled /
            # completed / failed) or another runner already claimed it.
            # Preserve the historical 400 for terminal states and use 409 for
            # the concurrent double-start race.
            await db.refresh(session)
            if session.status == "running":
                raise HTTPException(status_code=409, detail="Session is already running")
            raise ValueError(f"Session status '{session.status}' is not executable")
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
            # FIX: if the session was cancelled mid-run (cancel_session flips the
            # DB status), do NOT overwrite "cancelled" with "completed"/"failed".
            if session.status == "cancelled":
                if session.completed_at is None:
                    session.completed_at = datetime.datetime.now(datetime.timezone.utc)
                await db.commit()
                await db.refresh(session)
                return session

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
            if isinstance(e, HTTPException):
                raise
            # FIX: never overwrite a user cancellation with a failure status.
            await db.refresh(session)
            if session.status == "cancelled":
                await db.commit()
                raise
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
    async def _session_cancelled(db: AsyncSession, session_id: str) -> bool:
        """Re-check the session status from the DB.

        cancel_session() runs on a different DB session; the local ORM object
        is stale. A fresh query is the only reliable way to see a mid-run
        cancellation.
        """
        res = await db.execute(
            select(OrchestrationSession.status).where(OrchestrationSession.id == session_id)
        )
        return res.scalar_one_or_none() == "cancelled"

    @staticmethod
    async def _execute_sequential(db: AsyncSession, session: OrchestrationSession):
        """Execute tasks one by one in sequence_order."""
        tasks = await OrchestratorService.get_tasks(db, session.id)
        for task in tasks:
            if task.status in ("completed", "skipped", "cancelled"):
                continue
            # FIX: stop if the session was cancelled while we were waiting.
            if await OrchestratorService._session_cancelled(db, session.id):
                return
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
            # FIX: stop if the session was cancelled mid-run.
            if await OrchestratorService._session_cancelled(db, session.id):
                return
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
        if not isinstance(dag, dict):
            raise MalformedDefinitionError("Workflow DAG must be an object")
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise MalformedDefinitionError("Workflow DAG 'nodes' and 'edges' must be lists")

        session = await OrchestratorService.create_session(db, conversation_id, mode="sequential")
        node_id_to_task_id: dict[str, str] = {}

        for idx, node in enumerate(nodes):
            # QA-R5 FIX: validate before indexing — a malformed node/edge used
            # to raise KeyError and surface as a raw 500.
            if not isinstance(node, dict):
                raise MalformedDefinitionError(f"DAG node #{idx} must be an object")
            node_id = node.get("id")
            if not node_id:
                raise MalformedDefinitionError(f"DAG node #{idx} is missing 'id'")
            # Find dependency node IDs from edges
            dep_node_ids = []
            for e in edges:
                if not isinstance(e, dict) or "from" not in e or "to" not in e:
                    raise MalformedDefinitionError(f"DAG edge must have 'from' and 'to': {e!r}")
                if e["to"] == node_id:
                    dep_node_ids.append(e["from"])
            # Map to actual task IDs
            dep_task_ids = [node_id_to_task_id[nid] for nid in dep_node_ids if nid in node_id_to_task_id]

            task = await OrchestratorService.add_task(
                db, session.id,
                worker_role=node.get("worker", "thinker"),
                title=node.get("title", node_id),
                description=node.get("description", ""),
                input_context=node.get("input", {}),
                depends_on=dep_task_ids if dep_task_ids else None,
            )
            node_id_to_task_id[node_id] = task.id

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
            # FIX: a cancel_session() call may have flipped this task (and/or
            # the session) to cancelled while we were waiting — don't re-run it.
            if task.status == "cancelled" or await OrchestratorService._session_cancelled(db, session.id):
                return
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
                # FIX: don't overwrite a "cancelled" status (cancel_session may
                # have run while the task body was executing).
                await db.refresh(task)
                if task.status == "cancelled" or await OrchestratorService._session_cancelled(db, session.id):
                    return
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
                    # FIX: stop retrying if the session was cancelled while we slept.
                    if await OrchestratorService._session_cancelled(db, session.id):
                        task.status = "cancelled"
                        await db.commit()
                        return
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
                    # FIX: stop retrying if the session was cancelled while we slept.
                    if await OrchestratorService._session_cancelled(db, session.id):
                        task.status = "cancelled"
                        await db.commit()
                        return
                else:
                    task.status = "failed"
                    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    await db.commit()

    @staticmethod
    async def _execute_task_body(db: AsyncSession, session: OrchestrationSession, task: OrchestrationTask):
        """The actual task execution logic (called by _run_with_retry_and_timeout).

        REAL tool-capable execution: creates a child Task and runs it through
        ``runtime.executor.execute_task`` (the same FSM as the engineering
        pipeline) so the orchestrator's workers actually WRITE FILES instead of
        emitting chat text via a plain chat_completion call.
        """
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

        from runtime.executor import execute_task
        from storage.models import Task as TaskModel, TaskStatus, TaskType

        project_id = await OrchestratorService._resolve_orchestration_project(db, session)
        if not project_id:
            task.status = "failed"
            task.error_message = "No project available to execute orchestration task"
            await db.commit()
            return

        # Create a child task so execute_task has a real Task row to drive.
        child = TaskModel(
            project_id=project_id,
            title=task.title,
            description=full_prompt,
            type=TaskType.FEATURE.value,
            status=TaskStatus.CREATED.value,
            worker_type=task.worker_role,
            approval_required=False,
            progress=0,
            context={
                "source": "orchestration",
                "conversation_id": session.conversation_id,
                "phase_semantics": {},
                "execution_level": "STANDARD",
            },
        )
        db.add(child)
        await db.flush()

        try:
            result = await execute_task(db, child)
            await db.commit()
        except Exception as e:
            logger.error(json.dumps({
                "event": "orchestration_task_execution_error",
                "task_id": task.id,
                "error": str(e),
            }))
            try:
                child.status = TaskStatus.FAILED.value
                child.error_message = str(e)
                await db.flush()
            except Exception:
                pass
            result = {"success": False, "error": str(e)}

        output_text = json.dumps(result, default=str)
        task.output_context = {"response": output_text[:4000], "task_id": child.id}
        shared[f"task_{task.worker_role}_output"] = output_text[:4000]
        session.shared_context = shared
        await db.commit()

    @staticmethod
    async def _resolve_orchestration_project(
        db: AsyncSession, session: OrchestrationSession
    ) -> Optional[str]:
        """Resolve a project id for orchestration child tasks.

        Priority: conversation.project_id → active local profile project →
        first existing project → newly created sandbox project.
        """
        from storage.models import Conversation, Project
        try:
            conv = await db.get(Conversation, session.conversation_id)
            if conv and conv.project_id:
                return conv.project_id
        except Exception:
            pass

        try:
            from backend.models.local_profile import LocalProfile
            prof = (await db.execute(select(LocalProfile).limit(1))).scalar_one_or_none()
            if prof and prof.active_project_id:
                return prof.active_project_id
        except Exception:
            pass

        res = await db.execute(select(Project).limit(1))
        proj = res.scalar_one_or_none()
        if proj:
            return proj.id

        import uuid as _uuid
        project = Project(
            id=f"PROJECT-{_uuid.uuid4().hex[:12]}",
            name="Orchestration Project",
            slug=f"orch-{_uuid.uuid4().hex[:12]}",
            description="Auto-created for orchestration execution",
            owner_id=None,
        )
        db.add(project)
        await db.flush()
        return project.id

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

"""Engineering Dispatcher — Core Orchestrator.

Orchestrates worker execution according to the Task Graph.

The dispatcher performs REAL execution: every scheduled node is turned into a
child Task and run through ``runtime.executor.execute_task`` (the same FSM the
rest of the platform uses). Previously this module simulated completion by
marking nodes "completed" without executing anything — that stub convinced the
frontend the dispatcher "does everything" while no worker ever ran.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import TaskGraphModel, Task, TaskStatus
from dispatcher.config import dispatcher_config
from dispatcher.states import DispatcherState
from dispatcher.models import DispatchResult, TaskExecution, WorkerAssignment
from dispatcher.scheduler import TaskScheduler
from dispatcher.worker_selector import WorkerSelector

logger = logging.getLogger("aic.dispatcher")


class DispatcherResult:
    """Result of dispatcher operation."""

    def __init__(
        self,
        state: str,
        result: DispatchResult | None = None,
        message: str = "",
        metadata: dict | None = None,
    ):
        self.state = state
        self.result = result
        self.message = message
        self.metadata = metadata or {}


class DispatcherEngine:
    """Engineering Dispatcher — orchestrates worker execution."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def dispatch(
        self,
        graph_id: str,
        project_id: str | None = None,
    ) -> DispatcherResult:
        """Dispatch tasks from a Task Graph with REAL execution.

        Args:
            graph_id: Task Graph ID
            project_id: Optional project to attach child tasks to. When omitted
                the engine tries to resolve one from the graph's plan chain, and
                finally creates a sandbox project so execution always has a
                home.

        Returns:
            DispatcherResult with per-node execution state
        """
        if not dispatcher_config.enabled:
            return DispatcherResult(
                state="disabled",
                message="Dispatcher is disabled",
            )

        # Load graph
        result = await self.session.execute(
            select(TaskGraphModel).where(TaskGraphModel.id == graph_id)
        )
        graph_model = result.scalar_one_or_none()

        if not graph_model:
            return DispatcherResult(
                state="error",
                message=f"Task Graph not found: {graph_id}",
            )

        # Parse graph data
        nodes = graph_model.nodes or []
        execution_order = graph_model.execution_order or []
        if not execution_order:
            # Degenerate/legacy graphs without an explicit order run all nodes
            # as one dependency group.
            execution_order = [[n.get("node_id", "") for n in nodes]]

        if not nodes:
            return DispatcherResult(
                state="error",
                message="Task Graph has no nodes",
            )

        # Initialize execution state
        task_results: dict[str, TaskExecution] = {}
        for node_data in nodes:
            node_id = node_data.get("node_id", "")
            task_results[node_id] = TaskExecution(
                node_id=node_id,
                status="pending",
            )

        # Select workers for each task
        assignments: list[WorkerAssignment] = []
        for node_data in nodes:
            node_id = node_data.get("node_id", "")
            worker_type = node_data.get("worker_type", "backend")
            task_type = node_data.get("task_type", "coding")

            assignment = WorkerSelector.select_worker(
                node_id=node_id,
                worker_type=worker_type,
                task_type=task_type,
            )
            assignments.append(assignment)

        # Resolve the project for child tasks (required by the Task table).
        resolved_project_id = project_id or await self._resolve_project_id(graph_model)
        if not resolved_project_id:
            resolved_project_id = await self._ensure_sandbox_project()

        # Schedule tasks
        scheduled = TaskScheduler.schedule_tasks(execution_order, task_results)

        # Execute tasks in dependency order. Nodes within a dependency group
        # are independent and run CONCURRENTLY (each on its own session so the
        # runtime executor's FSM never shares an AsyncSession across coroutines).
        # If any node in a group fails, dispatch FAILS FAST: later dependency
        # groups are marked skipped and are never executed.
        execution_log = []
        for group_index, group in enumerate(scheduled):
            pending_node_ids = [nid for nid in group if nid in task_results]
            if not pending_node_ids:
                continue

            async def _run_node(node_id: str):
                execution = task_results[node_id]
                node_data = next(
                    (n for n in nodes if n.get("node_id") == node_id), {}
                )
                assignment = next(
                    (a for a in assignments if a.node_id == node_id),
                    None
                )

                execution.status = "running"
                execution.started_at = datetime.now(timezone.utc)

                execution_log.append({
                    "node_id": node_id,
                    "worker_id": assignment.worker_id if assignment else "unknown",
                    "action": "started",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                await self._publish_worker_event("pipeline.worker.started", {
                    "node_id": node_id,
                    "worker_type": node_data.get("worker_type", "backend"),
                    "title": node_data.get("title", ""),
                })

                try:
                    run_result = await self._execute_node_in_new_session(
                        node_data,
                        execution_id_prefix=graph_id,
                        project_id=resolved_project_id,
                    )
                    execution.status = "completed" if run_result.get("success") else "failed"
                    execution.result = run_result
                    execution.error = run_result.get("error")
                    execution.attempts = 1
                    execution.completed_at = datetime.now(timezone.utc)
                    execution_log.append({
                        "node_id": node_id,
                        "worker_id": assignment.worker_id if assignment else "unknown",
                        "action": "completed" if execution.status == "completed" else "failed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error": run_result.get("error"),
                    })
                except Exception as e:
                    execution.status = "failed"
                    execution.error = str(e)
                    execution.attempts = 1
                    execution.completed_at = datetime.now(timezone.utc)
                    logger.error(f"Dispatcher node {node_id} failed: {e}")
                    execution_log.append({
                        "node_id": node_id,
                        "worker_id": assignment.worker_id if assignment else "unknown",
                        "action": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error": str(e),
                    })

                await self._publish_worker_event("pipeline.worker.completed", {
                    "node_id": node_id,
                    "success": execution.status == "completed",
                    "worker_type": node_data.get("worker_type", "backend"),
                })
                return node_id, execution.status

            results = await asyncio.gather(
                *(_run_node(nid) for nid in pending_node_ids)
            )

            failed_node_ids = [nid for nid, status in results if status == "failed"]
            if failed_node_ids:
                # Fail-stop: mark every node in later dependency groups skipped.
                for later_group in scheduled[group_index + 1:]:
                    for later_id in later_group:
                        if later_id not in task_results:
                            continue
                        later_exec = task_results[later_id]
                        later_exec.status = "skipped"
                        later_exec.error = "Skipped: upstream node failed"
                        later_exec.completed_at = datetime.now(timezone.utc)
                        execution_log.append({
                            "node_id": later_id,
                            "worker_id": "unknown",
                            "action": "skipped",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "error": "Skipped: upstream node failed",
                        })
                break

        # Build dispatch result
        dispatch_result = DispatchResult(
            graph_id=graph_id,
            task_results=task_results,
            execution_log=execution_log,
            status="completed",
        )

        # Calculate success rate
        completed = sum(1 for e in task_results.values() if e.status == "completed")
        dispatch_result.success_rate = completed / len(task_results) if task_results else 0.0
        dispatch_result.status = "completed" if dispatch_result.success_rate == 1.0 else "partial"

        # Persist to database
        from storage.models import DispatchSession
        session_model = DispatchSession(
            id=dispatch_result.execution_id,
            graph_id=graph_id,
            execution_log=execution_log,
            success_rate=dispatch_result.success_rate,
            status=dispatch_result.status,
        )
        self.session.add(session_model)
        await self.session.flush()

        # Defensive: ensure the returned execution_id matches the persisted row id.
        # In normal operation these should be identical, but align them defensively
        # in case the ORM assigns a different id (e.g. via database default).
        if session_model.id != dispatch_result.execution_id:
            dispatch_result.execution_id = session_model.id

        return DispatcherResult(
            state=DispatcherState.DISPATCHER_COMPLETE.value,
            result=dispatch_result,
            message=self._build_dispatch_message(dispatch_result, len(nodes)),
            metadata={
                "execution_id": session_model.id,  # Use the actual persisted row id
                "graph_id": graph_id,
                "total_tasks": len(nodes),
                "completed_tasks": completed,
                "failed_tasks": len(nodes) - completed,
                "success_rate": dispatch_result.success_rate,
            },
        )

    async def _execute_node_in_new_session(
        self,
        node_data: dict,
        execution_id_prefix: str,
        project_id: str,
    ) -> dict:
        """Execute a graph node on a DEDICATED session.

        Nodes within a dependency group run concurrently via asyncio.gather;
        each needs its own AsyncSession (the runtime executor's FSM performs
        many interleaved awaits and must never share a session across
        coroutines). The session is derived from the dispatcher's own session
        bind so it targets the same database.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        factory = async_sessionmaker(
            bind=self.session.bind, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as node_session:
            return await self._execute_node(
                node_data,
                execution_id_prefix=execution_id_prefix,
                project_id=project_id,
                session=node_session,
            )

    async def _execute_node(
        self,
        node_data: dict,
        execution_id_prefix: str,
        project_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        """Create a child Task for a graph node and execute it for real.

        Mirrors master_orchestrator._execute_node:507-559 — the child task runs
        through ``runtime.executor.execute_task`` (FSM: discovery → investigate
        → planning → implementation → verification → closeout) with the node's
        workers writing actual files.

        ``session`` defaults to the dispatcher's own session; pass a dedicated
        session when executing a dependency group concurrently so independent
        nodes never share an AsyncSession.
        """
        from runtime.executor import execute_task

        node_id = node_data.get("node_id", "unknown")
        title = node_data.get("title", f"Subtask {node_id}")
        description = node_data.get("description", "")
        task_type = node_data.get("task_type", "feature")
        worker_type = node_data.get("worker_type", "coding")

        child_task = Task(
            project_id=project_id,
            # parent_task_id intentionally left unset — the graph node is the
            # source of truth, not a single parent task.
            title=title,
            description=description,
            type=task_type,
            status=TaskStatus.CREATED.value,
            worker_type=worker_type,
            approval_required=False,
            progress=0,
            context={
                "source": "dispatcher_dispatch",
                "graph_id": execution_id_prefix,
                "node_id": node_id,
                "graph_node": node_data,
                "execution_level": "STANDARD",
                "phase_semantics": {},
            },
        )
        session = session or self.session
        session.add(child_task)
        await session.flush()

        try:
            result = await execute_task(session, child_task)
            await session.commit()
            return result
        except Exception as e:
            logger.error(f"Node execution failed: {node_id}: {e}")
            child_task.status = TaskStatus.FAILED.value
            child_task.error_message = str(e)
            await session.flush()
            return {"success": False, "error": str(e)}

    async def _resolve_project_id(self, graph_model: TaskGraphModel) -> str | None:
        """Resolve a project id from the graph's pipeline chain.

        Graph → Plan → Brief → DiscoverySession. The discovery session's
        conversation_id historically points at the originating Task, so we can
        walk back to that task's project_id.
        """
        try:
            from storage.models import EngineeringPlan, EngineeringBrief, DiscoverySession
            plan = await self.session.get(EngineeringPlan, graph_model.plan_id)
            if plan:
                brief = await self.session.get(EngineeringBrief, plan.brief_id)
                if brief:
                    ds = await self.session.get(DiscoverySession, brief.discovery_session_id)
                    if ds:
                        parent = (
                            await self.session.execute(
                                select(Task).where(Task.id == ds.conversation_id).limit(1)
                            )
                        ).scalar_one_or_none()
                        if parent and parent.project_id:
                            return parent.project_id
        except Exception as e:
            logger.warning(f"Dispatch project resolution failed: {e}")
        return None

    async def _ensure_sandbox_project(self) -> str:
        """Create a sandbox project so task execution always has a home."""
        from storage.models import Project
        project = Project(
            id=f"PROJECT-{uuid.uuid4().hex[:12]}",
            name="Dispatcher Sandbox",
            slug=f"dispatch-{uuid.uuid4().hex[:12]}",
            description="Auto-created for dispatcher execution",
            owner_id=None,
        )
        self.session.add(project)
        await self.session.flush()
        return project.id

    async def _publish_worker_event(self, event_type: str, data: dict) -> None:
        """Best-effort publish of worker lifecycle events (EventBus + WS)."""
        try:
            from events.bus import bus
            await bus.publish(event_type, data)
        except Exception as e:
            logger.debug(f"EventBus publish failed ({event_type}): {e}")
        try:
            from backend.routes.websocket import broadcast_task_event
            await broadcast_task_event(event_type, data.get("node_id", ""), data)
        except Exception:
            pass

    def _build_dispatch_message(self, result: DispatchResult, total_tasks: int) -> str:
        """Build user-facing dispatch message from REAL per-node results."""
        completed = sum(1 for e in result.task_results.values() if e.status == "completed")
        failed = sum(1 for e in result.task_results.values() if e.status == "failed")

        lines = [
            "**Dispatch Finished**",
            f"- Tasks: {completed}/{total_tasks} completed",
            f"- Success rate: {result.success_rate:.0%}",
        ]
        if failed:
            failed_nodes = [
                n for n, e in result.task_results.items() if e.status == "failed"
            ]
            lines.append(f"- Failed nodes: {', '.join(failed_nodes[:5])}")
        lines.append("\nReview the per-node results for details.")
        return "\n".join(lines)
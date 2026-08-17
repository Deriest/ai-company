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

        # PRD Materialization: Dispatcher creates docs/PRD.md from the EngineeringBrief
        # Primary ownership: the dispatcher is the hub that gathers requirements → 
        # produces PRD → delivers to workers. Keep executor-level materialization as
        # fallback for direct execute_task callers.
        prd_path = None
        try:
            brief = await self._resolve_brief(graph_model)
            if brief:
                from shared.workspace import sandbox_workspace_dir
                from storage.models import Project

                # Determine workspace: use project.repo_path if set, else a stable sandbox per-graph
                proj_res = await self.session.execute(
                    select(Project).where(Project.id == resolved_project_id)
                )
                project_obj = proj_res.scalar_one_or_none()
                if project_obj and project_obj.repo_path:
                    workspace_path = project_obj.repo_path
                else:
                    workspace_path = sandbox_workspace_dir(graph_model.id)
                    # Create the directory
                    import os
                    os.makedirs(workspace_path, exist_ok=True)

                # Materialize PRD
                from backend.services.prd_writer import materialize_prd
                prd_path = materialize_prd(workspace_path, brief)
                logger.info(f"Dispatcher {graph_model.id[:8]}: PRD.md written -> {prd_path or 'N/A'}")
        except Exception as e:
            logger.warning(f"Dispatcher {graph_model.id[:8]}: Failed to materialize PRD.md (non-fatal): {e}")

        # Schedule tasks
        scheduled = TaskScheduler.schedule_tasks(execution_order, task_results)

        # Execute tasks in dependency order. Nodes within a dependency group
        # are independent and run CONCURRENTLY (each on its own session so the
        # runtime executor's FSM never shares an AsyncSession across coroutines).
        # If any node in a group fails, dispatch FAILS FAST: later dependency
        # groups are marked skipped and are never executed.
        execution_log = []
        dispatcher_failed = False
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
                
                # D2: Broadcast worker status to all connected clients via WebSocket
                try:
                    from backend.routes.websocket import broadcast_worker_event
                    await broadcast_worker_event(
                        f"worker.{node_data.get('worker_type', 'unknown')}.started",
                        node_id,
                        {
                            "title": node_data.get("title", ""),
                            "phase": node_data.get("phase", ""),
                        },
                    )
                except Exception as e:
                    logger.debug(f"Worker event broadcast failed: {e}")

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

                # C1: broadcast completion/failure to WebSocket clients so the
                # office floor can update instantly (no polling wait).
                try:
                    from backend.routes.websocket import broadcast_worker_event
                    await broadcast_worker_event(
                        f"worker.{node_data.get('worker_type', 'backend')}.{execution.status}",
                        node_id,
                        {
                            "success": execution.status == "completed",
                            "title": node_data.get("title", ""),
                        },
                    )
                except Exception as e:
                    logger.debug(f"Worker completion broadcast failed (non-critical): {e}")

                return node_id, execution.status

            results = await asyncio.gather(
                *(_run_node(nid) for nid in pending_node_ids)
            )

            failed_node_ids = [nid for nid, status in results if status == "failed"]
            if failed_node_ids:
                # FAIL-STOP SEMANTICS: when any node in a dependency group fails,
                # ALL future groups must be skipped (fail-stop semantics per M8 spec).
                logger.warning(f"Dispatcher nodes {', '.join(failed_node_ids)} failed; triggering fail-stop")
                
                # Mark remaining future groups as skipped (fail-stop semantics)
                for remaining_group in scheduled[group_index + 1:]:
                    for nid in remaining_group:
                        if nid in task_results and task_results[nid].status == "pending":
                            task_results[nid].status = "skipped"
                            task_results[nid].error = "Skipped: upstream node failed"
                
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
            message=self._build_dispatch_message(dispatch_result, len(nodes), prd_path),
            metadata={
                "execution_id": session_model.id,
                "graph_id": graph_id,
                "total_tasks": len(nodes),
                "completed_tasks": completed,
                "failed_tasks": len(nodes) - completed,
                "success_rate": dispatch_result.success_rate,
                "prd_path": prd_path,  # Path where PRD.md was materialized
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

        session = session or self.session

        # Subtask-aware execution: graph nodes produced by workflow decomposition
        # carry the ID of an already-persisted subtask Task row ("subtask_id").
        # Execute that row directly so parent/child linkage, status, depends_on
        # and subtask_order bookkeeping stay real instead of forking a copy.
        # Defensive: any lookup failure falls back to creating a fresh child task.
        child_task = None
        subtask_id = node_data.get("subtask_id")
        if subtask_id:
            try:
                child_task = await session.get(Task, subtask_id)
            except Exception as e:
                logger.warning(f"Subtask lookup failed for node {node_id}: {e}")
                child_task = None
            if child_task is not None:
                child_ctx = dict(child_task.context or {})
                child_ctx["source"] = "dispatcher_dispatch"
                child_ctx["graph_id"] = execution_id_prefix
                child_ctx["node_id"] = node_id
                child_ctx["graph_node"] = node_data
                child_task.context = child_ctx
                # Reset to CREATED so re-dispatch after failure can re-execute
                child_task.status = TaskStatus.CREATED.value
                child_task.error_message = None
                await session.flush()
                # ROOT-CAUSE FIX (mirrors the fresh-child path below): commit the
                # reuse-branch mutations BEFORE execute_task. The executor runs
                # long worker LLM calls; keeping this session's write txn open
                # across the run would hold the SQLite write lock for the whole
                # execution and block every other request's write.
                await session.commit()

        if child_task is None:
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
            session.add(child_task)
            await session.flush()
            # ROOT-CAUSE FIX: commit the child task creation BEFORE
            # execute_task. The executor runs long worker LLM calls; keeping
            # this session's write txn open across the run would hold the
            # SQLite write lock for the whole execution and block every other
            # request's write ("database is locked").
            await session.commit()

        try:
            result = await execute_task(session, child_task)
            await session.commit()
            return result
        except Exception as e:
            logger.error(f"Node execution failed: {node_id}: {e}")
            try:
                child_task.status = TaskStatus.FAILED.value
                child_task.error_message = str(e)
                await session.flush()
                # Commit the FAILED status so the task is not stuck in a
                # rolled-back transaction / forever in its prior state.
                await session.commit()
            except Exception as commit_err:
                # A commit failure must not mask the original execution error.
                logger.error(f"Failed to persist FAILED status for node {node_id}: {commit_err}")
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

    async def _resolve_brief(self, graph_model: TaskGraphModel):
        """Resolve EngineeringBrief from the graph's pipeline chain.

        Returns the EngineeringBrief object or None if not found.
        This is used by PRD materialization for the dispatcher.
        """
        try:
            from storage.models import EngineeringPlan, EngineeringBrief, DiscoverySession
            plan = await self.session.get(EngineeringPlan, graph_model.plan_id)
            if plan:
                brief = await self.session.get(EngineeringBrief, plan.brief_id)
                return brief
        except Exception as e:
            logger.debug(f"Dispatcher brief resolution failed: {e}")
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

    def _build_dispatch_message(self, result: DispatchResult, total_tasks: int, prd_path: str | None) -> str:
        """Build user-facing dispatch message from REAL per-node results."""
        completed = sum(1 for e in result.task_results.values() if e.status == "completed")
        failed = sum(1 for e in result.task_results.values() if e.status == "failed")

        lines = [
            "**Dispatch Finished**",
            f"- Tasks: {completed}/{total_tasks} completed",
            f"- Success rate: {result.success_rate:.0%}",
        ]
        if prd_path:
            lines.append(f"- PRD delivered to workers: {prd_path}")
        if failed:
            failed_nodes = [
                n for n, e in result.task_results.items() if e.status == "failed"
            ]
            lines.append(f"- Failed nodes: {', '.join(failed_nodes[:5])}")
        lines.append("\nReview the per-node results for details.")
        return "\n".join(lines)
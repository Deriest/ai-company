"""Master Orchestrator — chains Discovery → Planning → TaskGraph → Dispatcher.

This is the central pipeline coordinator for AIC-ADE's "AI Engineering Company"
vision. When a task_request is detected in the Command Center, the orchestrator
automatically chains the engineering pipeline:

    Discovery (brief) → Planning (plan) → TaskGraph (DAG) → Dispatcher (execution)

Each transition publishes to the EventBus for real-time frontend updates.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from events.bus import bus
from storage.models import (
    EngineeringBrief as EngineeringBriefORM,
    EngineeringPlan as EngineeringPlanORM,
    TaskGraphModel,
    DispatchSession,
    Task,
    TaskStatus,
)

logger = logging.getLogger("aic.orchestrator")


class PipelineError(Exception):
    """Pipeline stage failed."""
    pass


class PipelineStage:
    """Represents a stage in the engineering pipeline."""
    DISCOVERY = "discovery"
    PLANNING = "planning"
    TASKGRAPH = "taskgraph"
    DISPATCH = "dispatch"
    VERIFICATION = "verification"
    DELIVERY = "delivery"


class PipelineResult:
    """Result of a pipeline execution."""

    def __init__(
        self,
        success: bool,
        stage: str,
        task_id: str = "",
        brief_id: str = "",
        plan_id: str = "",
        graph_id: str = "",
        dispatch_id: str = "",
        message: str = "",
        error: str = "",
    ):
        self.success = success
        self.stage = stage
        self.task_id = task_id
        self.brief_id = brief_id
        self.plan_id = plan_id
        self.graph_id = graph_id
        self.dispatch_id = dispatch_id
        self.message = message
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stage": self.stage,
            "task_id": self.task_id,
            "brief_id": self.brief_id,
            "plan_id": self.plan_id,
            "graph_id": self.graph_id,
            "dispatch_id": self.dispatch_id,
            "message": self.message,
            "error": self.error,
        }


class MasterOrchestrator:
    """Chains the engineering pipeline from task creation to delivery.

    The orchestrator is invoked after a Task is created via the Command Center.
    It runs the full pipeline: Discovery → Planning → TaskGraph → Dispatch,
    publishing events at each transition for real-time frontend updates.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._trace_id = uuid.uuid4().hex[:16]

    async def run_pipeline(self, task: Task) -> PipelineResult:
        """Run the full engineering pipeline for a task.

        Steps:
        1. Discovery — produce Engineering Brief from task description
        2. Planning — produce Engineering Plan from brief
        3. TaskGraph — produce execution DAG from plan
        4. Dispatch — execute tasks via runtime executor
        """
        task_id = task.id
        trace = self._trace_id

        try:
            # ── Stage 1: Discovery ──────────────────────────────
            await self._publish("pipeline.stage.started", task_id, {
                "stage": PipelineStage.DISCOVERY,
                "trace_id": trace,
            })

            brief_id = await self._run_discovery(task)
            if not brief_id:
                return PipelineResult(
                    success=False,
                    stage=PipelineStage.DISCOVERY,
                    task_id=task_id,
                    error="Discovery failed to produce a brief",
                )

            # Update task context with brief_id
            ctx = task.context or {}
            ctx["brief_id"] = brief_id
            task.context = ctx
            await self.session.flush()
            await self.session.commit()  # ROOT-CAUSE: release write lock before Planning LLM calls

            await self._publish("pipeline.stage.completed", task_id, {
                "stage": PipelineStage.DISCOVERY,
                "brief_id": brief_id,
                "trace_id": trace,
            })

            # ── Stage 2: Planning ───────────────────────────────
            await self._publish("pipeline.stage.started", task_id, {
                "stage": PipelineStage.PLANNING,
                "brief_id": brief_id,
                "trace_id": trace,
            })

            plan_id = await self._run_planning(brief_id, task)
            if not plan_id:
                return PipelineResult(
                    success=False,
                    stage=PipelineStage.PLANNING,
                    task_id=task_id,
                    brief_id=brief_id,
                    error="Planning failed to produce a plan",
                )

            ctx["plan_id"] = plan_id
            task.context = ctx
            await self.session.flush()
            await self.session.commit()  # ROOT-CAUSE: release write lock before TaskGraph/Dispatch LLM calls

            await self._publish("pipeline.stage.completed", task_id, {
                "stage": PipelineStage.PLANNING,
                "plan_id": plan_id,
                "trace_id": trace,
            })

            # ── Stage 2.5: Decomposition (defensive) ───────────
            # Complex multi-step requests are broken into subtasks here, after
            # the engineering plan exists and before the TaskGraph is built.
            # Any failure falls back to single-task execution — the pipeline
            # is never broken by decomposition.
            subtasks = await self._maybe_decompose(task, plan_id, brief_id)

            # ── Stage 3: TaskGraph ──────────────────────────────
            await self._publish("pipeline.stage.started", task_id, {
                "stage": PipelineStage.TASKGRAPH,
                "plan_id": plan_id,
                "trace_id": trace,
            })

            # Prefer a graph built from the decomposed subtasks (each subtask
            # becomes a graph node carrying its subtask_id so the dispatcher
            # executes the persisted subtask rows with their dependencies).
            # Fall back to the plan-derived graph when decomposition produced
            # nothing or graph construction fails.
            graph_id = None
            if subtasks:
                graph_id = await self._run_taskgraph_from_subtasks(plan_id, subtasks)
                if not graph_id:
                    logger.warning(
                        f"Task {task_id}: subtask graph generation failed; "
                        "falling back to plan-derived graph"
                    )
            if not graph_id:
                graph_id = await self._run_taskgraph(plan_id)
            if not graph_id:
                return PipelineResult(
                    success=False,
                    stage=PipelineStage.TASKGRAPH,
                    task_id=task_id,
                    brief_id=brief_id,
                    plan_id=plan_id,
                    error="TaskGraph generation failed",
                )

            ctx["graph_id"] = graph_id
            task.context = ctx
            await self.session.flush()
            await self.session.commit()  # ROOT-CAUSE: release write lock before Dispatch LLM calls

            await self._publish("pipeline.stage.completed", task_id, {
                "stage": PipelineStage.TASKGRAPH,
                "graph_id": graph_id,
                "trace_id": trace,
            })

            # ── Stage 4: Dispatch ───────────────────────────────
            await self._publish("pipeline.stage.started", task_id, {
                "stage": PipelineStage.DISPATCH,
                "graph_id": graph_id,
                "trace_id": trace,
            })

            dispatch_result = await self._run_dispatch(graph_id, task)
            dispatch_id = dispatch_result.get("execution_id", "")

            ctx["dispatch_id"] = dispatch_id
            task.context = ctx
            await self.session.flush()

            await self._publish("pipeline.stage.completed", task_id, {
                "stage": PipelineStage.DISPATCH,
                "dispatch_id": dispatch_id,
                "success_rate": dispatch_result.get("success_rate", 0),
                "trace_id": trace,
            })

            # Mark the parent task terminal now that its dispatch has concluded.
            # The parent was left in "created" while the orchestrator executed
            # children; complete it explicitly so it doesn't stay open (and so
            # self_healing won't re-dispatch it).
            # Use the pipeline outcome (success) rather than the instantaneous
            # dispatch success_rate, which can be 0 while async child nodes are
            # still completing — a successful pipeline should not mark the
            # parent as failed.
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now(timezone.utc)
            await self.session.commit()

            return PipelineResult(
                success=True,
                stage=PipelineStage.DISPATCH,
                task_id=task_id,
                brief_id=brief_id,
                plan_id=plan_id,
                graph_id=graph_id,
                dispatch_id=dispatch_id,
                message=f"Pipeline complete. Brief→Plan→Graph→Dispatch. Success rate: {dispatch_result.get('success_rate', 0):.0%}",
            )

        except Exception as e:
            logger.error(f"Pipeline failed for task {task_id}: {e}", exc_info=True)
            await self._publish("pipeline.failed", task_id, {
                "error": str(e),
                "trace_id": trace,
            })
            # Mark the parent failed so it reaches a terminal state.
            try:
                task.status = TaskStatus.FAILED.value
                task.error_message = task.error_message or str(e)
                task.completed_at = datetime.now(timezone.utc)
                await self.session.commit()
            except Exception:
                pass
            return PipelineResult(
                success=False,
                stage="unknown",
                task_id=task_id,
                error=str(e),
            )

    # ── Stage runners ───────────────────────────────────────────

    async def _run_discovery(self, task: Task) -> Optional[str]:
        """Run Discovery Engine → produce Engineering Brief."""
        from discovery.engine import DiscoveryEngine

        engine = DiscoveryEngine(self.session)

        # Build a synthetic conversation-like context for discovery
        # The discovery engine expects a conversation object with context
        class _TaskProxy:
            """Minimal proxy to satisfy DiscoveryEngine.discover() interface."""
            def __init__(self, task):
                self.id = task.id
                self.context = task.context or {}
                self.user_id = task.created_by

        proxy = _TaskProxy(task)

        result = await engine.discover(
            conversation=proxy,
            content=f"{task.title}. {task.description}",
            history=[],
        )

        if result.is_ready and result.brief:
            # Brief was already persisted by DiscoveryEngine
            # Find it by querying the latest brief for this discovery session
            brief_result = await self.session.execute(
                select(EngineeringBriefORM)
                .where(EngineeringBriefORM.discovery_session_id == result.metadata.get("session_id", ""))
                .order_by(EngineeringBriefORM.created_at.desc())
                .limit(1)
            )
            brief = brief_result.scalar_one_or_none()
            if brief:
                brief.status = "handed_off"
                await self.session.flush()
                logger.info(f"Discovery complete: brief_id={brief.id}")
                return brief.id

            # If we can't find it via session_id, try by engineering_goal match
            brief_result = await self.session.execute(
                select(EngineeringBriefORM)
                .where(EngineeringBriefORM.engineering_goal == result.brief.engineering_goal)
                .order_by(EngineeringBriefORM.created_at.desc())
                .limit(1)
            )
            brief = brief_result.scalar_one_or_none()
            if brief:
                brief.status = "handed_off"
                await self.session.flush()
                return brief.id

        # If discovery didn't produce a ready brief (needs clarification),
        # create a minimal brief from the task description directly
        return await self._create_minimal_brief(task)

    async def _create_minimal_brief(self, task: Task) -> Optional[str]:
        """Create a minimal Engineering Brief when Discovery can't produce one."""
        from discovery.brief import EngineeringBriefData
        from storage.models import DiscoverySession as DiscoverySessionORM

        # FIX (round-5): engineering_briefs.discovery_session_id is a FK — the
        # previous literal "direct" violated it with FK enforcement ON. Create a
        # real discovery session row (conversation_id is unconstrained now, so a
        # task id is fine) and attach the minimal brief to it.
        ds = DiscoverySessionORM(
            conversation_id=task.id,
            user_id=task.created_by,
            status="minimal",
        )
        self.session.add(ds)
        await self.session.flush()
        discovery_session_id = ds.id

        brief_id = f"BRIEF-{uuid.uuid4().hex[:12]}"
        brief_data = EngineeringBriefData(
            id=brief_id,
            engineering_goal=task.title,
            user_intent=task.description,
            request_category=task.type or "feature",
            functional_requirements=[
                {"id": "FR-1", "description": task.description, "priority": "high"}
            ],
            acceptance_criteria=[
                {"id": "AC-1", "description": f"Task '{task.title}' implemented and verified"}
            ],
            readiness_status="ready",
            readiness_score=0.7,
            status="ready",
        )

        # Persist
        brief_orm = EngineeringBriefORM(
            id=brief_id,
            discovery_session_id=discovery_session_id,
            engineering_goal=brief_data.engineering_goal,
            user_intent=brief_data.user_intent,
            request_category=brief_data.request_category,
            functional_requirements=[r if isinstance(r, dict) else {"id": r} for r in brief_data.functional_requirements],
            non_functional_requirements=brief_data.non_functional_requirements,
            constraints=brief_data.constraints,
            assumptions=brief_data.assumptions,
            dependencies=brief_data.dependencies,
            risks=brief_data.risks,
            acceptance_criteria=[c if isinstance(c, dict) else {"id": c} for c in brief_data.acceptance_criteria],
            readiness_status=brief_data.readiness_status,
            readiness_score=brief_data.readiness_score,
            readiness_dimensions=brief_data.readiness_dimensions,
            outstanding_unknowns=brief_data.outstanding_unknowns,
            discovery_metadata=brief_data.discovery_metadata,
            status="handed_off",
        )
        self.session.add(brief_orm)
        await self.session.flush()
        logger.info(f"Created minimal brief: {brief_id}")
        return brief_id

    async def _run_planning(self, brief_id: str, task: Task) -> Optional[str]:
        """Run Planning Engine → produce Engineering Plan."""
        from planning.engine import PlanningEngine

        engine = PlanningEngine(self.session)
        project_context = {
            "project_id": task.project_id,
            "task_type": task.type,
            "worker_type": task.worker_type,
        }

        result = await engine.plan(brief_id, project_context)

        if result.plan and result.state in ("plan_complete", "plan_validated"):
            # Plan was persisted by PlanningEngine — find it
            plan_result = await self.session.execute(
                select(EngineeringPlanORM)
                .where(EngineeringPlanORM.brief_id == brief_id)
                .order_by(EngineeringPlanORM.created_at.desc())
                .limit(1)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                plan.status = "validated"
                await self.session.flush()
                logger.info(f"Planning complete: plan_id={plan.id}")
                return plan.id

        logger.warning(f"Planning failed for brief {brief_id}")
        return None

    # ── Stage 2.5: Decomposition (subtasks) ────────────────────────

    async def _maybe_decompose(self, task: Task, plan_id: str, brief_id: str | None = None) -> list[Task]:
        """Try to decompose the parent task into subtasks, defensively falling back to [].

        Skip decomposition if:
          - Task is already a subtask (parent_task_id set)
          - Execution level is QUICK (too trivial)

        Args:
            task: Parent task
            plan_id: Engineering Plan ID (loaded below)
            brief_id: Optional brief ID; used to fetch functional_requirements

        Returns:
            List of created subtask Tasks (empty when skipped/failed/no-op).
        """
        # Already a subtask → skip
        if getattr(task, "parent_task_id", None):
            logger.debug(f"Task {task.id[:8]}: already a subtask, skipping decomposition")
            return []

        # QUICK tasks are trivial — no churn needed
        ctx = task.context or {}
        level = str(ctx.get("execution_level") or (ctx.get("triage") or {}).get("level") or "").upper()
        if level == "QUICK":
            logger.info(f"Task {task.id[:8]}: QUICK-level execution, skipping decomposition")
            return []

        try:
            from workflow.decomposition import decompose_task
            from storage.models import EngineeringBrief as EBORM

            # Load the engineering plan
            plan_res = await self.session.execute(
                select(EngineeringPlanORM).where(EngineeringPlanORM.id == plan_id)
            )
            plan = plan_res.scalar_one_or_none()
            if not plan:
                logger.warning(f"Task {task.id[:8]}: plan not found; cannot decompose")
                return []

            # Architect output: render plan into markdown-like format parse_decomposition expects
            architect_output = f"# {plan.engineering_goal}\n\n## Technical Approach\n\n{plan.technical_approach}"

            # Structured plan data fallback (the real production shape)
            effort_estimates = plan.effort_estimates or []
            plan_data = {
                "effort_estimates": effort_estimates,
                "engineering_goal": plan.engineering_goal,
            }

            # Fetch functional requirements from the brief (if available) for better descriptions
            if brief_id:
                try:
                    brief_res = await self.session.execute(
                        select(EBORM).where(EBORM.id == brief_id)
                    )
                    brief = brief_res.scalar_one_or_none()
                    if brief:
                        plan_data["functional_requirements"] = brief.functional_requirements or []
                except Exception as e:
                    logger.debug(f"Failed to load brief for functional requirements: {e}")

            # Call decompose_task with both free-form architect text AND structured fallback
            subtasks = await decompose_task(self.session, task, architect_output, plan_data=plan_data)

            if not subtasks:
                logger.warning(f"Task {task.id[:8]}: decomposition produced no subtasks; using single-task path")
            else:
                logger.info(f"Task {task.id[:8]}: successfully decomposed into {len(subtasks)} subtasks")

            return subtasks

        except Exception as e:
            # Cleanup any partially created subtasks (flushed but potentially not committed yet)
            logger.warning(f"Task {task.id[:8]}: decomposition failed ({e}); rolling back partials and using single-task path")
            try:
                partials = await self.session.execute(select(Task).where(Task.parent_task_id == task.id))
                for st in partials.scalars().all():
                    await self.session.delete(st)
                # Clear decomposed flags on parent (if set pre-failure)
                parent_ctx = task.context or {}
                if parent_ctx.get("decomposed"):
                    parent_ctx.pop("decomposed", None)
                    parent_ctx.pop("subtask_ids", None)
                    task.context = parent_ctx
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(task, "context")
                await self.session.flush()
            except Exception as cleanup_err:
                logger.error(f"Task {task.id[:8]}: partial cleanup failed ({cleanup_err})")
            return []

    async def _run_taskgraph_from_subtasks(self, plan_id: str, subtasks: list[Task]) -> Optional[str]:
        """Build a TaskGraphModel directly from existing subtask Task rows.

        Each subtask becomes a graph node carrying its task ID (so the dispatcher can
        execute the persisted subtask row rather than creating a child). Dependencies
        are inherited from subtask.depends_on. Phase-based barriers add edges from
        earlier-phase workers to later-phase workers (implementation → verification).

        Defensive: returns None on any failure.

        Args:
            plan_id: Engineering Plan ID (for graph persistence)
            subtasks: List of Task rows (from decomposition)

        Returns:
            Graph ID if successful, None on failure.
        """
        from taskgraph.models import TaskNode, TaskGraph
        from taskgraph.dependency import DependencyAnalyzer
        from taskgraph.validator import GraphValidator

        try:
            # Build nodes from subtasks
            nodes = []
            for i, st in enumerate(subtasks):
                # Map worker to task_type
                worker = getattr(st, "worker_type", "backend") or "backend"
                task_type = "testing" if worker in ("qa", "performance") else \
                           ("documentation" if worker == "documentation" else \
                            ("review" if worker == "review" else "coding"))

                # Filter depends_on to only include sibling subtask IDs
                deps_on = getattr(st, "depends_on", []) or []
                sibling_ids = [t.id for t in subtasks]
                filtered_deps = [d for d in deps_on if d in sibling_ids]

                node = TaskNode(
                    node_id=st.id,  # use task.id as node_id so dispatcher knows it's an existing subtask
                    title=st.title,
                    description=st.description or "",
                    task_type=task_type,
                    worker_type=worker,
                    dependencies=filtered_deps,
                    priority=1,
                    estimated_effort="medium",
                )
                nodes.append(node)

            if len(nodes) <= 1:
                logger.debug(f"Only 1 subtask; graph construction skipped")
                return None

            # Analyze dependencies: explicit deps + task-type edges + phase barriers
            edges = DependencyAnalyzer.analyze_dependencies(nodes)

            # Validate graph before persisting
            validation = GraphValidator.validate(nodes, edges)
            if not validation.is_valid:
                logger.warning(f"Subtask graph invalid: {'; '.join(validation.errors)}")
                return None

            # Detect parallelism groups
            execution_order = DependencyAnalyzer.detect_parallelism(nodes, edges)
            critical_path = DependencyAnalyzer.find_critical_path(nodes, edges)

            # Build graph
            graph = TaskGraph(
                plan_id=plan_id,
                nodes=nodes,
                edges=edges,
                execution_order=execution_order,
                critical_path=critical_path,
                status="validated",
            )

            # Persist TaskGraphModel with richer node serialization including subtask_id/description
            graph_model = TaskGraphModel(
                id=graph.graph_id,
                plan_id=plan_id,
                nodes=[
                    {
                        "node_id": n.node_id,
                        "title": n.title,
                        "description": n.description,
                        "worker_type": n.worker_type,
                        "task_type": n.task_type,
                        "dependencies": n.dependencies,
                        "subtask_id": n.node_id,  # key field so dispatcher executes the existing subtask row
                    }
                    for n in graph.nodes
                ],
                edges=[
                    {"from_node": e.from_node, "to_node": e.to_node, "dependency_type": e.dependency_type}
                    for e in graph.edges
                ],
                execution_order=execution_order,
                critical_path=critical_path,
                recovery_points=[],
                estimated_duration="",
                parallelism_factor=1.0,
                status="validated",
            )
            self.session.add(graph_model)
            await self.session.flush()
            logger.info(f"Subtask graph persisted: graph_id={graph.graph_id}, nodes={len(nodes)}")
            return graph.graph_id

        except Exception as e:
            logger.error(f"Taskgraph generation from subtasks failed: {e}", exc_info=True)
            return None

    # ── Stage 3: TaskGraph ──────────────────────────────────────────────

    async def _run_taskgraph(self, plan_id: str) -> Optional[str]:
        """Run TaskGraph Engine → produce execution DAG."""
        from taskgraph.engine import TaskGraphEngine

        engine = TaskGraphEngine(self.session)
        result = await engine.generate_graph(plan_id)

        if result.graph and result.state in ("graph_complete", "graph_validated"):
            # Graph was persisted by TaskGraphEngine — find it
            graph_result = await self.session.execute(
                select(TaskGraphModel)
                .where(TaskGraphModel.plan_id == plan_id)
                .order_by(TaskGraphModel.created_at.desc())
                .limit(1)
            )
            graph = graph_result.scalar_one_or_none()
            if graph:
                graph.status = "validated"
                await self.session.flush()
                logger.info(f"TaskGraph complete: graph_id={graph.id}")
                return graph.id

        logger.warning(f"TaskGraph failed for plan {plan_id}")
        return None

    async def _run_dispatch(self, graph_id: str, task: Task) -> dict:
        """Run Dispatcher with REAL execution via the DispatcherEngine.

        The engine owns the scheduling loop and per-node execution (one source
        of truth). This method delegates instead of re-implementing the loop.
        """
        from dispatcher.engine import DispatcherEngine

        engine = DispatcherEngine(self.session)
        result = await engine.dispatch(graph_id, project_id=task.project_id)

        if result.result is None:
            return {"success_rate": 0.0, "execution_id": "", "status": "error"}

        dispatch_result = result.result
        return {
            "execution_id": dispatch_result.execution_id,
            "success_rate": dispatch_result.success_rate,
            "status": dispatch_result.status,
        }

    # ── Helpers ─────────────────────────────────────────────────

    async def _publish(self, event_type: str, task_id: str, data: dict) -> None:
        """Publish event to EventBus and broadcast via WebSocket."""
        data["task_id"] = task_id
        try:
            await bus.publish(event_type, data, trace_id=self._trace_id)
        except Exception as e:
            logger.debug(f"EventBus publish failed: {e}")

        # Also broadcast via WebSocket for real-time frontend updates
        try:
            from backend.routes.websocket import broadcast_task_event
            await broadcast_task_event(event_type, task_id, data)
        except Exception:
            pass


# ── Module-level convenience function ──────────────────────

async def run_engineering_pipeline(session: AsyncSession, task: Task) -> PipelineResult:
    """Convenience function to run the full pipeline for a task.

    Usage from ConversationEngine after task creation:
        result = await run_engineering_pipeline(session, task)
    """
    orchestrator = MasterOrchestrator(session)
    return await orchestrator.run_pipeline(task)

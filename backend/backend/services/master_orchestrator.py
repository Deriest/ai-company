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

            await self._publish("pipeline.stage.completed", task_id, {
                "stage": PipelineStage.PLANNING,
                "plan_id": plan_id,
                "trace_id": trace,
            })

            # ── Stage 3: TaskGraph ──────────────────────────────
            await self._publish("pipeline.stage.started", task_id, {
                "stage": PipelineStage.TASKGRAPH,
                "plan_id": plan_id,
                "trace_id": trace,
            })

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
        """Run Dispatcher with REAL execution via runtime executor.

        Instead of simulating, this delegates each task node to
        runtime/executor.py's execute_task() for actual worker execution.
        """
        from dispatcher.engine import DispatcherEngine
        from dispatcher.models import DispatchResult, TaskExecution
        from datetime import datetime, timezone

        engine = DispatcherEngine(self.session)

        # Load the task graph
        graph_result = await self.session.execute(
            select(TaskGraphModel).where(TaskGraphModel.id == graph_id)
        )
        graph_orm = graph_result.scalar_one_or_none()
        if not graph_orm:
            return {"success_rate": 0.0, "execution_id": "", "status": "error"}

        execution_id = f"EXEC-{uuid.uuid4().hex[:12]}"
        nodes = graph_orm.nodes or []
        execution_order = graph_orm.execution_order or [[n.get("node_id", "") for n in nodes]]
        task_results = {}
        execution_log = []

        # Execute each group in order
        for group in execution_order:
            for node_id in group:
                node_data = next(
                    (n for n in nodes if n.get("node_id") == node_id), None
                )
                if not node_data:
                    continue

                started = datetime.now(timezone.utc)
                await self._publish("pipeline.worker.started", task.id, {
                    "node_id": node_id,
                    "worker_type": node_data.get("worker_type", "backend"),
                    "title": node_data.get("title", ""),
                })

                # Create a sub-task for this node and execute it
                result = await self._execute_node(task, node_data, execution_id)

                completed = datetime.now(timezone.utc)
                task_results[node_id] = TaskExecution(
                    node_id=node_id,
                    status="completed" if result.get("success") else "failed",
                    result=result,
                    error=result.get("error"),
                    attempts=1,
                    started_at=started,
                    completed_at=completed,
                )

                execution_log.append({
                    "node_id": node_id,
                    "action": "execute",
                    "status": "completed" if result.get("success") else "failed",
                    "duration": str(completed - started),
                    "timestamp": completed.isoformat(),
                })

                await self._publish("pipeline.worker.completed", task.id, {
                    "node_id": node_id,
                    "success": result.get("success", False),
                    "worker_type": node_data.get("worker_type", "backend"),
                })

        # Calculate success rate
        total = len(task_results)
        succeeded = sum(1 for t in task_results.values() if t.status == "completed")
        success_rate = succeeded / total if total > 0 else 0.0

        # Persist dispatch session
        dispatch_session = DispatchSession(
            id=execution_id,
            graph_id=graph_id,
            execution_log=execution_log,
            total_duration=str(datetime.now(timezone.utc)),
            success_rate=success_rate,
            status="completed" if success_rate > 0.5 else "partial",
        )
        self.session.add(dispatch_session)
        await self.session.flush()

        logger.info(f"Dispatch complete: {execution_id}, success_rate={success_rate:.0%}")
        return {
            "execution_id": execution_id,
            "success_rate": success_rate,
            "status": dispatch_session.status,
        }

    async def _execute_node(self, parent_task: Task, node_data: dict, execution_id: str) -> dict:
        """Execute a single task graph node using the runtime executor.

        Creates a child Task from the node data and runs it through
        runtime/executor.py's execute_task() for real worker execution.
        """
        from runtime.executor import execute_task

        node_id = node_data.get("node_id", "unknown")
        title = node_data.get("title", f"Subtask {node_id}")
        description = node_data.get("description", "")
        task_type = node_data.get("task_type", parent_task.type)
        worker_type = node_data.get("worker_type", parent_task.worker_type or "coding")

        # Create child task for this node
        child_task = Task(
            project_id=parent_task.project_id,
            parent_task_id=parent_task.id,
            title=title,
            description=description,
            type=task_type,
            status=TaskStatus.CREATED.value,
            worker_type=worker_type,
            approval_required=False,
            progress=0,
            context={
                "source": "pipeline_dispatch",
                "execution_id": execution_id,
                "node_id": node_id,
                "parent_task_id": parent_task.id,
                "graph_node": node_data,
                # BUG-12 FIX: Propagate parent triage data to child tasks
                # so that guardrail-enforced workers (security, flint, nexus)
                # are preserved across the execution pipeline.
                "triage": (parent_task.context or {}).get("triage", {}),
                "execution_level": (parent_task.context or {}).get("execution_level", "STANDARD"),
                "phase_semantics": {},
            },
        )
        self.session.add(child_task)
        await self.session.flush()

        # Execute via runtime executor (real worker execution)
        try:
            result = await execute_task(self.session, child_task)
            await self.session.commit()
            return result
        except Exception as e:
            logger.error(f"Node execution failed: {node_id}: {e}")
            child_task.status = TaskStatus.FAILED.value
            child_task.error_message = str(e)
            await self.session.flush()
            return {"success": False, "error": str(e)}

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

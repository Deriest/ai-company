"""Task Graph Engine — Core Orchestrator.

Transforms Engineering Plans into ordered Task Graphs (DAGs).
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import EngineeringPlan as EngineeringPlanModel, TaskGraphModel as TaskGraphORM
from taskgraph.config import taskgraph_config
from taskgraph.models import TaskGraph, TaskNode, RecoveryPoint
from taskgraph.states import TaskGraphState
from taskgraph.decomposer import PlanDecomposer
from taskgraph.dependency import DependencyAnalyzer
from taskgraph.validator import GraphValidator

logger = logging.getLogger("aic.taskgraph")


class TaskGraphResult:
    """Result of task graph generation."""

    def __init__(
        self,
        state: str,
        graph: TaskGraph | None = None,
        message: str = "",
        metadata: dict | None = None,
    ):
        self.state = state
        self.graph = graph
        self.message = message
        self.metadata = metadata or {}


class TaskGraphEngine:
    """Task Graph Engine — transforms Plans into DAGs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_graph(
        self,
        plan_id: str,
    ) -> TaskGraphResult:
        """Generate a Task Graph from an Engineering Plan.

        Args:
            plan_id: Engineering Plan ID

        Returns:
            TaskGraphResult with graph or error
        """
        if not taskgraph_config.enabled:
            return TaskGraphResult(
                state="disabled",
                message="Task Graph Engine is disabled",
            )

        # Load plan
        result = await self.session.execute(
            select(EngineeringPlanModel).where(EngineeringPlanModel.id == plan_id)
        )
        plan_model = result.scalar_one_or_none()

        if not plan_model:
            return TaskGraphResult(
                state="error",
                message=f"Plan not found: {plan_id}",
            )

        # Convert plan to dict
        plan_data = {
            "id": plan_model.id,
            "brief_id": plan_model.brief_id,
            "engineering_goal": plan_model.engineering_goal,
            "technical_approach": plan_model.technical_approach,
            "implementation_strategy": plan_model.implementation_strategy,
            "architecture_decisions": plan_model.architecture_decisions or [],
            "risk_mitigations": plan_model.risk_mitigations or [],
            "dependency_map": plan_model.dependency_map or {},
            "effort_estimates": plan_model.effort_estimates or [],
            "acceptance_criteria": plan_model.acceptance_criteria or [],
            "estimated_duration": plan_model.estimated_duration,
            "confidence_score": plan_model.confidence_score,
        }

        # Run pipeline
        return await self._run_pipeline(plan_data)

    async def _run_pipeline(self, plan_data: dict) -> TaskGraphResult:
        """Run the task graph generation pipeline."""
        # Step 1: Decompose plan into nodes
        nodes = PlanDecomposer.decompose(plan_data)

        if not nodes:
            return TaskGraphResult(
                state=TaskGraphState.ERROR.value,
                message="Failed to decompose plan into tasks",
            )

        # Step 2: Analyze dependencies
        edges = DependencyAnalyzer.analyze_dependencies(nodes)

        # Step 3: Detect parallelism
        execution_order = DependencyAnalyzer.detect_parallelism(nodes, edges)

        # Step 4: Find critical path
        critical_path = DependencyAnalyzer.find_critical_path(nodes, edges)

        # Step 5: Validate graph
        validation = GraphValidator.validate(nodes, edges)

        if not validation.is_valid:
            return TaskGraphResult(
                state=TaskGraphState.ERROR.value,
                message=f"Graph validation failed: {'; '.join(validation.errors)}",
                metadata={"errors": validation.errors, "cycles": validation.cycles_detected},
            )

        # Step 6: Generate recovery points
        recovery_points = self._generate_recovery_points(nodes)

        # Step 7: Calculate parallelism factor
        parallelism_factor = self._calculate_parallelism_factor(execution_order, len(nodes))

        # Step 8: Build graph
        graph = TaskGraph(
            plan_id=plan_data.get("id", ""),
            nodes=nodes,
            edges=edges,
            execution_order=execution_order,
            critical_path=critical_path,
            recovery_points=recovery_points,
            estimated_duration=plan_data.get("estimated_duration", ""),
            parallelism_factor=parallelism_factor,
            status="validated",
        )

        # Persist to database
        graph_model = TaskGraphORM(
            id=graph.graph_id,
            plan_id=graph.plan_id,
            nodes=[
                {"node_id": n.node_id, "title": n.title, "worker_type": n.worker_type, "task_type": n.task_type}
                for n in graph.nodes
            ],
            edges=[
                {"from_node": e.from_node, "to_node": e.to_node, "dependency_type": e.dependency_type}
                for e in graph.edges
            ],
            execution_order=graph.execution_order,
            critical_path=graph.critical_path,
            recovery_points=[
                {"node_id": r.node_id, "description": r.description}
                for r in graph.recovery_points
            ],
            estimated_duration=graph.estimated_duration,
            parallelism_factor=graph.parallelism_factor,
            status=graph.status,
        )
        self.session.add(graph_model)
        await self.session.flush()

        return TaskGraphResult(
            state=TaskGraphState.GRAPH_COMPLETE.value,
            graph=graph,
            message=self._build_graph_message(graph),
            metadata={
                "graph_id": graph.graph_id,
                "plan_id": graph.plan_id,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "parallelism_factor": parallelism_factor,
            },
        )

    @classmethod
    def _generate_recovery_points(cls, nodes: list[TaskNode]) -> list[RecoveryPoint]:
        """Generate recovery points at intervals."""
        recovery_points = []
        interval = taskgraph_config.recovery_point_interval

        for i, node in enumerate(nodes):
            if (i + 1) % interval == 0:
                recovery_points.append(RecoveryPoint(
                    node_id=node.node_id,
                    description=f"Recovery point after {node.title}",
                    can_rollback_to=True,
                ))

        return recovery_points

    @classmethod
    def _calculate_parallelism_factor(
        cls,
        execution_order: list[list[str]],
        total_nodes: int,
    ) -> float:
        """Calculate parallelism factor."""
        if not execution_order or total_nodes == 0:
            return 1.0

        max_parallel = max(len(group) for group in execution_order)
        return max_parallel / total_nodes if total_nodes > 0 else 1.0

    @classmethod
    def _build_graph_message(cls, graph: TaskGraph) -> str:
        """Build user-facing graph message."""
        lines = [
            "**Task Graph Generated**\n",
            f"- Nodes: {len(graph.nodes)}",
            f"- Edges: {len(graph.edges)}",
            f"- Parallelism: {graph.parallelism_factor:.1f}x",
            f"- Critical path: {len(graph.critical_path)} nodes",
            f"- Recovery points: {len(graph.recovery_points)}",
            "\nReply **yes / go ahead** to start execution.",
        ]
        return "\n".join(lines)

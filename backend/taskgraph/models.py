"""Task Graph Engine — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class TaskNode:
    """A single task in the graph."""

    node_id: str = ""
    title: str = ""
    description: str = ""
    task_type: str = "coding"  # coding, testing, documentation, review
    worker_type: str = "backend"  # backend, frontend, qa, etc.
    dependencies: list[str] = field(default_factory=list)
    estimated_effort: str = "medium"
    priority: int = 1  # 0=low, 1=med, 2=high, 3=critical
    can_parallel: bool = True
    rollback_strategy: str = "revert"
    acceptance_criteria: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"NODE-{uuid4().hex[:8].upper()}"


@dataclass
class TaskEdge:
    """A dependency edge in the graph."""

    from_node: str = ""
    to_node: str = ""
    dependency_type: str = "blocks"  # blocks, data_dependency, output_dependency
    required: bool = True


@dataclass
class RecoveryPoint:
    """A recovery point in the graph."""

    node_id: str
    description: str
    can_rollback_to: bool = True


@dataclass
class TaskGraph:
    """Task Graph (DAG) output."""

    graph_id: str = ""
    plan_id: str = ""
    nodes: list[TaskNode] = field(default_factory=list)
    edges: list[TaskEdge] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    recovery_points: list[RecoveryPoint] = field(default_factory=list)
    estimated_duration: str = ""
    parallelism_factor: float = 1.0
    status: str = "draft"  # draft, validated, executing, completed

    def __post_init__(self):
        if not self.graph_id:
            self.graph_id = f"GRAPH-{uuid4().hex[:12].upper()}"

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "plan_id": self.plan_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "title": n.title,
                    "description": n.description,
                    "task_type": n.task_type,
                    "worker_type": n.worker_type,
                    "dependencies": n.dependencies,
                    "estimated_effort": n.estimated_effort,
                    "priority": n.priority,
                    "can_parallel": n.can_parallel,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "dependency_type": e.dependency_type,
                    "required": e.required,
                }
                for e in self.edges
            ],
            "execution_order": self.execution_order,
            "critical_path": self.critical_path,
            "recovery_points": [
                {"node_id": r.node_id, "description": r.description}
                for r in self.recovery_points
            ],
            "estimated_duration": self.estimated_duration,
            "parallelism_factor": self.parallelism_factor,
            "status": self.status,
        }


@dataclass
class GraphValidation:
    """Result of graph validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cycles_detected: list[list[str]] = field(default_factory=list)

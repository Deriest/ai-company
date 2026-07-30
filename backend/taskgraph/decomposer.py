"""Task Graph Engine — Plan Decomposer.

Breaks Engineering Plans into atomic TaskNodes.
"""

import re
import logging
from taskgraph.models import TaskNode

logger = logging.getLogger("aic.taskgraph.decomposer")


# Worker type mapping
WORKER_TYPE_MAP = {
    "database": "backend",
    "api": "backend",
    "auth": "backend",
    "frontend": "frontend",
    "ui": "frontend",
    "testing": "qa",
    "test": "qa",
    "documentation": "documentation",
    "security": "security",
    "devops": "devops",
}


class PlanDecomposer:
    """Decomposes Engineering Plans into TaskNodes."""

    @classmethod
    def decompose(cls, plan_data: dict) -> list[TaskNode]:
        """Decompose a plan into task nodes.

        Args:
            plan_data: Engineering Plan data

        Returns:
            List of TaskNodes
        """
        nodes = []
        node_counter = 1

        # Get requirements from plan
        requirements = plan_data.get("effort_estimates", [])

        if requirements:
            # Create nodes from requirements
            for req in requirements:
                req_id = req.get("requirement_id", f"REQ-{node_counter}")
                complexity = req.get("complexity", "medium")

                # Determine worker type from requirement description
                description = req.get("description", req_id)
                worker_type = cls._determine_worker_type(description)

                # Determine task type
                task_type = cls._determine_task_type(description, worker_type)

                # Create node
                node = TaskNode(
                    node_id=f"NODE-{node_counter:03d}",
                    title=f"Implement {req_id}",
                    description=description,
                    task_type=task_type,
                    worker_type=worker_type,
                    estimated_effort=complexity,
                    priority=cls._determine_priority(complexity),
                    can_parallel=cls._can_parallel(worker_type),
                )
                nodes.append(node)
                node_counter += 1

        # If no requirements, create generic nodes
        if not nodes:
            goal = plan_data.get("engineering_goal", "Complete task")
            strategy = plan_data.get("implementation_strategy", "hybrid")

            nodes.append(TaskNode(
                node_id=f"NODE-{node_counter:03d}",
                title=f"Implement: {goal[:50]}",
                description=goal,
                task_type="coding",
                worker_type="backend",
                estimated_effort="medium",
                priority=1,
            ))

        return nodes

    @classmethod
    def _determine_worker_type(cls, description: str) -> str:
        """Determine worker type from description."""
        lower = description.lower()

        for keyword, worker_type in WORKER_TYPE_MAP.items():
            if keyword in lower:
                return worker_type

        return "backend"  # Default

    @classmethod
    def _determine_task_type(cls, description: str, worker_type: str) -> str:
        """Determine task type."""
        lower = description.lower()

        if any(word in lower for word in ["test", "spec", "coverage"]):
            return "testing"
        if any(word in lower for word in ["doc", "readme", "guide"]):
            return "documentation"
        if any(word in lower for word in ["review", "audit"]):
            return "review"

        return "coding"

    @classmethod
    def _determine_priority(cls, complexity: str) -> int:
        """Determine priority from complexity."""
        return {
            "low": 0,
            "medium": 1,
            "high": 2,
            "very_high": 3,
        }.get(complexity, 1)

    @classmethod
    def _can_parallel(cls, worker_type: str) -> bool:
        """Determine if task can run in parallel."""
        # Frontend and backend can often run in parallel
        # Testing usually depends on implementation
        return worker_type in ("backend", "frontend", "documentation")

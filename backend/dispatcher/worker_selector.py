"""Engineering Dispatcher — Worker Selection.

Selects optimal workers for task execution.
"""

import logging
from dispatcher.models import WorkerAssignment

logger = logging.getLogger("aic.dispatcher.worker_selector")


# Worker capabilities
WORKER_CAPABILITIES = {
    "backend": ["coding", "api", "database", "auth", "testing"],
    "frontend": ["coding", "ui", "css", "component", "testing"],
    "qa": ["testing", "integration", "e2e", "review"],
    "security": ["security", "auth", "audit", "review"],
    "documentation": ["documentation", "readme", "guide"],
    "devops": ["infrastructure", "docker", "ci", "deployment"],
    "architect": ["architecture", "design", "planning"],
    "database": ["database", "migration", "schema", "query"],
}

# Worker tier mapping
WORKER_TIERS = {
    "architect": "thinker",
    "pm": "thinker",
    "research": "thinker",
    "backend": "crafter",
    "frontend": "crafter",
    "database": "crafter",
    "security": "crafter",
    "qa": "sprinter",
    "documentation": "sprinter",
    "devops": "sprinter",
}


class WorkerSelector:
    """Selects optimal workers for tasks."""

    @classmethod
    def select_worker(
        cls,
        node_id: str,
        worker_type: str,
        task_type: str,
        available_workers: list[str] | None = None,
    ) -> WorkerAssignment:
        """Select the best worker for a task.

        Args:
            node_id: Task node ID
            worker_type: Required worker type
            task_type: Type of task
            available_workers: List of available worker IDs

        Returns:
            WorkerAssignment
        """
        # Default to requested worker type
        selected_type = worker_type

        # Check if worker type has the required capability
        capabilities = WORKER_CAPABILITIES.get(worker_type, [])
        if task_type not in capabilities:
            # Find a worker that has the capability
            for w_type, caps in WORKER_CAPABILITIES.items():
                if task_type in caps:
                    selected_type = w_type
                    break

        # Get tier
        tier = WORKER_TIERS.get(selected_type, "crafter")

        # Generate worker ID
        worker_id = f"worker-{selected_type}-{node_id}"

        return WorkerAssignment(
            worker_id=worker_id,
            worker_type=selected_type,
            node_id=node_id,
            priority=1,
            estimated_effort="medium",
        )

    @classmethod
    def get_worker_tier(cls, worker_type: str) -> str:
        """Get the tier for a worker type."""
        return WORKER_TIERS.get(worker_type, "crafter")

    @classmethod
    def get_worker_capabilities(cls, worker_type: str) -> list[str]:
        """Get capabilities for a worker type."""
        return WORKER_CAPABILITIES.get(worker_type, [])

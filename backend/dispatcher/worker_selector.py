"""Engineering Dispatcher — Worker Selection.

Selects optimal workers for task execution.

WORKER_CAPABILITIES / WORKER_TIERS are aligned with the canonical worker
registry in workers/base.py (WORKER_REGISTRY) as the single source of truth for
roles. Every canonical role (hermes, rex, pm, research, designer,
documentation, architect, backend, frontend, qa, performance, database, nexus,
flint, security, coding) plus the documented extension aliases (devops,
deployment, debugger) is present.
"""

import logging
from dispatcher.models import WorkerAssignment

logger = logging.getLogger("aic.dispatcher.worker_selector")


# Worker capabilities — covers every WORKER_REGISTRY role in workers/base.py.
WORKER_CAPABILITIES = {
    "hermes": ["dispatch", "routing", "intent", "orchestration", "status"],
    "pm": ["planning", "requirements", "specification", "roadmap", "project_management", "documentation"],
    "research": ["research", "analysis", "investigate", "feasibility", "benchmark", "documentation"],
    "architect": ["architecture", "design", "planning", "system_design", "documentation"],
    "designer": ["ui", "ux", "design", "component", "css", "documentation"],
    "backend": ["coding", "api", "database", "auth", "testing"],
    "frontend": ["coding", "ui", "css", "component", "testing"],
    "database": ["database", "migration", "schema", "query"],
    "qa": ["testing", "integration", "e2e", "documentation"],
    "security": ["security", "auth", "audit", "documentation"],
    "performance": ["performance", "optimization", "profiling", "benchmark", "documentation"],
    "documentation": ["documentation", "readme", "guide"],
    "nexus": ["integration", "webhook", "middleware", "infrastructure"],
    "flint": ["deployment", "infrastructure", "docker", "ci"],
    "rex": ["governance", "compliance", "audit", "documentation"],
    "coding": ["coding", "implementation", "fullstack", "feature"],
    "devops": ["infrastructure", "docker", "ci", "deployment"],
    "deployment": ["deployment", "docker", "ci"],
    "debugger": ["debugging", "bugfix", "troubleshooting"],
}

# Worker tier mapping — mirrors workflow/fsm.py PHASE_WORKERS tiers.
WORKER_TIERS = {
    "hermes": "system",
    "pm": "thinker",
    "research": "thinker",
    "architect": "thinker",
    "rex": "thinker",
    "designer": "crafter",
    "backend": "crafter",
    "frontend": "crafter",
    "database": "crafter",
    "coding": "crafter",
    "security": "crafter",
    "nexus": "crafter",
    "flint": "crafter",
    "devops": "crafter",
    "deployment": "crafter",
    "debugger": "crafter",
    "qa": "sprinter",
    "performance": "sprinter",
    "documentation": "sprinter",
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
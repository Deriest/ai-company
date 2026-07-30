"""Engineering Dispatcher — Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class WorkerAssignment:
    """Assignment of a worker to a task."""

    worker_id: str
    worker_type: str
    node_id: str
    priority: int = 1
    estimated_effort: str = "medium"


@dataclass
class TaskExecution:
    """Execution state of a task."""

    node_id: str
    worker_id: str | None = None
    status: str = "pending"  # pending, running, completed, failed, retrying
    result: dict | None = None
    error: str | None = None
    attempts: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class DispatchResult:
    """Result of dispatcher execution."""

    execution_id: str = ""
    graph_id: str = ""
    task_results: dict[str, TaskExecution] = field(default_factory=dict)
    execution_log: list[dict] = field(default_factory=list)
    total_duration: str = ""
    success_rate: float = 0.0
    status: str = "pending"  # running, completed, failed, partial

    def __post_init__(self):
        if not self.execution_id:
            self.execution_id = f"EXEC-{uuid4().hex[:12].upper()}"

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "graph_id": self.graph_id,
            "task_results": {
                node_id: {
                    "node_id": exec.node_id,
                    "worker_id": exec.worker_id,
                    "status": exec.status,
                    "attempts": exec.attempts,
                    "error": exec.error,
                }
                for node_id, exec in self.task_results.items()
            },
            "total_duration": self.total_duration,
            "success_rate": self.success_rate,
            "status": self.status,
        }

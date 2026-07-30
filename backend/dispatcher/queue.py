"""Worker Queue — Priority-based task scheduling for workers.

Provides:
- Priority-based task queue
- Task scheduling
- Queue management
"""

import logging
import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger("aic.worker.queue")


@dataclass
class QueueTask:
    """A task in the worker queue."""
    id: str = field(default_factory=lambda: str(uuid4()))
    worker_role: str = ""
    priority: int = 5  # 1=highest, 10=lowest
    task_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    status: str = "pending"  # pending, scheduled, running, completed, failed

    def __lt__(self, other: "QueueTask") -> bool:
        """Compare by priority (lower number = higher priority)."""
        return self.priority < other.priority


class WorkerQueue:
    """Priority-based task queue for workers."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: list[QueueTask] = []
        self._tasks: dict[str, QueueTask] = {}

    @property
    def size(self) -> int:
        """Current queue size."""
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """Whether queue is empty."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Whether queue is full."""
        return len(self._queue) >= self.max_size

    def enqueue(self, task: QueueTask) -> bool:
        """Add task to queue.

        Args:
            task: Task to enqueue

        Returns:
            True if enqueued, False if queue is full
        """
        if self.is_full:
            logger.warning(f"Queue full, rejecting task {task.id}")
            return False

        heapq.heappush(self._queue, task)
        self._tasks[task.id] = task
        logger.info(f"Enqueued task {task.id} (priority={task.priority})")
        return True

    def dequeue(self) -> QueueTask | None:
        """Remove and return highest priority task.

        Returns:
            Highest priority task or None if empty
        """
        if self.is_empty:
            return None

        task = heapq.heappop(self._queue)
        task.status = "scheduled"
        task.scheduled_at = datetime.now(timezone.utc)
        logger.info(f"Dequeued task {task.id}")
        return task

    def peek(self) -> QueueTask | None:
        """View highest priority task without removing.

        Returns:
            Highest priority task or None if empty
        """
        if self.is_empty:
            return None
        return self._queue[0]

    def get_task(self, task_id: str) -> QueueTask | None:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = "cancelled"
        # Remove from queue
        self._queue = [t for t in self._queue if t.id != task_id]
        heapq.heapify(self._queue)
        del self._tasks[task_id]
        logger.info(f"Cancelled task {task_id}")
        return True

    def get_pending(self) -> list[QueueTask]:
        """Get all pending tasks.

        Returns:
            List of pending tasks
        """
        return [t for t in self._queue if t.status == "pending"]

    def get_by_role(self, role: str) -> list[QueueTask]:
        """Get tasks by worker role.

        Args:
            role: Worker role

        Returns:
            List of tasks for role
        """
        return [t for t in self._queue if t.worker_role == role]

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Queue statistics
        """
        by_role: dict[str, int] = {}
        by_priority: dict[int, int] = {}

        for task in self._queue:
            by_role[task.worker_role] = by_role.get(task.worker_role, 0) + 1
            by_priority[task.priority] = by_priority.get(task.priority, 0) + 1

        return {
            "size": self.size,
            "max_size": self.max_size,
            "is_empty": self.is_empty,
            "is_full": self.is_full,
            "by_role": by_role,
            "by_priority": by_priority,
        }

    def clear(self) -> None:
        """Clear all tasks from queue."""
        self._queue.clear()
        self._tasks.clear()
        logger.info("Queue cleared")


# Global queue instance
_worker_queue = WorkerQueue()


def get_worker_queue() -> WorkerQueue:
    """Get the global worker queue."""
    return _worker_queue

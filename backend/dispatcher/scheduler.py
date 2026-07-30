"""Engineering Dispatcher — Scheduler.

Schedules tasks according to graph order and priority.
"""

import logging
from dispatcher.models import TaskExecution

logger = logging.getLogger("aic.dispatcher.scheduler")


class TaskScheduler:
    """Schedules tasks for execution."""

    @classmethod
    def schedule_tasks(
        cls,
        execution_order: list[list[str]],
        task_results: dict[str, TaskExecution],
    ) -> list[list[str]]:
        """Schedule tasks respecting dependencies and priority.

        Args:
            execution_order: Parallel groups from Task Graph
            task_results: Current execution state

        Returns:
            Scheduled execution groups
        """
        scheduled = []

        for group in execution_order:
            # Filter out already completed tasks
            pending = [
                node_id for node_id in group
                if task_results.get(node_id, TaskExecution(node_id=node_id)).status == "pending"
            ]

            if pending:
                scheduled.append(pending)

        return scheduled

    @classmethod
    def get_next_tasks(
        cls,
        scheduled: list[list[str]],
        max_concurrent: int,
    ) -> list[str]:
        """Get next tasks to dispatch.

        Args:
            scheduled: Scheduled execution groups
            max_concurrent: Maximum concurrent tasks

        Returns:
            List of node_ids to dispatch
        """
        if not scheduled:
            return []

        # Get first group with pending tasks
        for group in scheduled:
            if group:
                return group[:max_concurrent]

        return []

    @classmethod
    def mark_task_complete(
        cls,
        scheduled: list[list[str]],
        node_id: str,
    ) -> list[list[str]]:
        """Mark a task as complete and update schedule.

        Args:
            scheduled: Current schedule
            node_id: Completed task

        Returns:
            Updated schedule
        """
        updated = []
        for group in scheduled:
            remaining = [n for n in group if n != node_id]
            if remaining:
                updated.append(remaining)
        return updated

    @classmethod
    def is_complete(cls, scheduled: list[list[str]]) -> bool:
        """Check if all scheduled tasks are complete."""
        return len(scheduled) == 0 or all(len(g) == 0 for g in scheduled)

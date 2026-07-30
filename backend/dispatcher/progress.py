"""Worker Progress — Progress tracking for worker execution.

Provides:
- Progress tracking
- Progress updates
- Progress history
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aic.worker.progress")


@dataclass
class ProgressUpdate:
    """A progress update for a worker execution."""
    execution_id: str
    progress: float  # 0.0-1.0
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ProgressTracker:
    """Tracks progress for worker executions."""

    def __init__(self):
        self._progress: dict[str, float] = {}
        self._messages: dict[str, str] = {}
        self._history: dict[str, list[ProgressUpdate]] = {}

    def update(
        self,
        execution_id: str,
        progress: float,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Update progress for an execution.

        Args:
            execution_id: Execution ID
            progress: Progress value (0.0-1.0)
            message: Human-readable progress message
            metadata: Optional metadata

        Returns:
            ProgressUpdate record
        """
        # Clamp progress
        progress = max(0.0, min(1.0, progress))

        self._progress[execution_id] = progress
        self._messages[execution_id] = message

        update = ProgressUpdate(
            execution_id=execution_id,
            progress=progress,
            message=message,
            metadata=metadata or {},
        )

        if execution_id not in self._history:
            self._history[execution_id] = []
        self._history[execution_id].append(update)

        logger.info(f"Progress {execution_id}: {progress:.1%} - {message}")
        return update

    def get_progress(self, execution_id: str) -> float:
        """Get current progress for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            Progress value (0.0-1.0)
        """
        return self._progress.get(execution_id, 0.0)

    def get_message(self, execution_id: str) -> str:
        """Get current progress message.

        Args:
            execution_id: Execution ID

        Returns:
            Progress message
        """
        return self._messages.get(execution_id, "")

    def get_history(self, execution_id: str) -> list[ProgressUpdate]:
        """Get progress history for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            List of progress updates
        """
        return self._history.get(execution_id, [])

    def complete(self, execution_id: str, message: str = "Completed") -> ProgressUpdate:
        """Mark execution as complete.

        Args:
            execution_id: Execution ID
            message: Completion message

        Returns:
            Final ProgressUpdate
        """
        return self.update(execution_id, 1.0, message)

    def fail(self, execution_id: str, message: str = "Failed") -> ProgressUpdate:
        """Mark execution as failed.

        Args:
            execution_id: Execution ID
            message: Failure message

        Returns:
            Final ProgressUpdate
        """
        return self.update(execution_id, self._progress.get(execution_id, 0.0), message)

    def clear(self, execution_id: str) -> None:
        """Clear progress for an execution.

        Args:
            execution_id: Execution ID
        """
        self._progress.pop(execution_id, None)
        self._messages.pop(execution_id, None)
        self._history.pop(execution_id, None)

    def get_all_progress(self) -> dict[str, float]:
        """Get progress for all executions.

        Returns:
            Dictionary of execution_id -> progress
        """
        return dict(self._progress)

    def get_stats(self) -> dict[str, Any]:
        """Get progress statistics.

        Returns:
            Progress statistics
        """
        if not self._progress:
            return {
                "total": 0,
                "avg_progress": 0.0,
                "completed": 0,
                "in_progress": 0,
            }

        total = len(self._progress)
        avg_progress = sum(self._progress.values()) / total
        completed = sum(1 for p in self._progress.values() if p >= 1.0)
        in_progress = total - completed

        return {
            "total": total,
            "avg_progress": round(avg_progress, 3),
            "completed": completed,
            "in_progress": in_progress,
        }


# Global tracker instance
_progress_tracker = ProgressTracker()


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker."""
    return _progress_tracker

"""Worker Events — Event emission for worker operations.

Provides:
- Worker lifecycle events
- Worker progress events
- Worker communication events
"""

import logging
from typing import Any

logger = logging.getLogger("aic.worker.events")


class WorkerEventEmitter:
    """Emits worker-related events to the event bus."""

    def __init__(self, event_bus: Any = None):
        self.event_bus = event_bus

    async def emit_started(
        self,
        execution_id: str,
        worker_role: str,
        conversation_id: str,
    ) -> None:
        """Emit worker.started event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.started",
                data={
                    "execution_id": execution_id,
                    "worker_role": worker_role,
                    "conversation_id": conversation_id,
                },
            )
            logger.debug(f"Emitted worker.started event: {execution_id}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.started event: {e}")

    async def emit_completed(
        self,
        execution_id: str,
        worker_role: str,
        duration_ms: float,
    ) -> None:
        """Emit worker.completed event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.completed",
                data={
                    "execution_id": execution_id,
                    "worker_role": worker_role,
                    "duration_ms": duration_ms,
                },
            )
            logger.debug(f"Emitted worker.completed event: {execution_id}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.completed event: {e}")

    async def emit_failed(
        self,
        execution_id: str,
        worker_role: str,
        error: str,
    ) -> None:
        """Emit worker.failed event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.failed",
                data={
                    "execution_id": execution_id,
                    "worker_role": worker_role,
                    "error": error,
                },
            )
            logger.debug(f"Emitted worker.failed event: {execution_id}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.failed event: {e}")

    async def emit_progress(
        self,
        execution_id: str,
        worker_role: str,
        progress: float,
        message: str,
    ) -> None:
        """Emit worker.progress event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.progress",
                data={
                    "execution_id": execution_id,
                    "worker_role": worker_role,
                    "progress": progress,
                    "message": message,
                },
            )
            logger.debug(f"Emitted worker.progress event: {execution_id} {progress:.1%}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.progress event: {e}")

    async def emit_queued(
        self,
        task_id: str,
        worker_role: str,
        priority: int,
    ) -> None:
        """Emit worker.queued event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.queued",
                data={
                    "task_id": task_id,
                    "worker_role": worker_role,
                    "priority": priority,
                },
            )
            logger.debug(f"Emitted worker.queued event: {task_id}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.queued event: {e}")

    async def emit_dispatched(
        self,
        task_id: str,
        worker_role: str,
        execution_id: str,
    ) -> None:
        """Emit worker.dispatched event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "worker.dispatched",
                data={
                    "task_id": task_id,
                    "worker_role": worker_role,
                    "execution_id": execution_id,
                },
            )
            logger.debug(f"Emitted worker.dispatched event: {task_id}")
        except Exception as e:
            logger.warning(f"Failed to emit worker.dispatched event: {e}")


# Global emitter instance
_worker_emitter = WorkerEventEmitter()


def get_worker_emitter() -> WorkerEventEmitter:
    """Get the global worker event emitter."""
    return _worker_emitter


def set_worker_event_bus(event_bus: Any) -> None:
    """Set the event bus for worker events."""
    _worker_emitter.event_bus = event_bus

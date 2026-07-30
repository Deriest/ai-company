"""AIC Platform — Engineering Dispatcher (v2.3.5).

Orchestrates worker execution according to the Task Graph.
Handles worker selection, scheduling, priority, retry, and failure handling.
"""

from dispatcher.config import dispatcher_config, DispatcherConfig
from dispatcher.states import DispatcherState, can_transition, is_terminal
from dispatcher.models import DispatchResult, TaskExecution, WorkerAssignment

__all__ = [
    "dispatcher_config",
    "DispatcherConfig",
    "DispatcherState",
    "can_transition",
    "is_terminal",
    "DispatchResult",
    "TaskExecution",
    "WorkerAssignment",
]

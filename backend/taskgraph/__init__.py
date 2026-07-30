"""AIC Platform — Task Graph Engine (v2.3.4).

Decomposes Engineering Plans into ordered Task Graphs (DAGs).
Identifies dependencies, parallelism, and critical paths.
"""

from taskgraph.config import taskgraph_config, TaskGraphConfig
from taskgraph.states import TaskGraphState, can_transition, is_terminal
from taskgraph.models import TaskGraph, TaskNode, TaskEdge, GraphValidation

__all__ = [
    "taskgraph_config",
    "TaskGraphConfig",
    "TaskGraphState",
    "can_transition",
    "is_terminal",
    "TaskGraph",
    "TaskNode",
    "TaskEdge",
    "GraphValidation",
]

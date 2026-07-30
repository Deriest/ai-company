"""Task Graph Engine — Configuration."""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger("aic.taskgraph.config")


@dataclass
class TaskGraphConfig:
    """Configuration for the Task Graph Engine."""

    enabled: bool = True
    max_nodes: int = 100
    max_edges: int = 500
    max_parallel_factor: int = 10
    require_critical_path: bool = True
    recovery_point_interval: int = 5  # Every 5 nodes

    @classmethod
    def from_env(cls) -> "TaskGraphConfig":
        return cls(
            enabled=_env_bool("AIC_TASKGRAPH_ENABLED", True),
            max_nodes=_env_int("AIC_TASKGRAPH_MAX_NODES", 100),
            max_edges=_env_int("AIC_TASKGRAPH_MAX_EDGES", 500),
            max_parallel_factor=_env_int("AIC_TASKGRAPH_MAX_PARALLEL", 10),
            recovery_point_interval=_env_int("AIC_TASKGRAPH_RECOVERY_INTERVAL", 5),
        )


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


taskgraph_config = TaskGraphConfig.from_env()

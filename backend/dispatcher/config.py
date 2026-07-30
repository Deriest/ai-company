"""Engineering Dispatcher — Configuration."""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger("aic.dispatcher.config")


@dataclass
class DispatcherConfig:
    """Configuration for the Engineering Dispatcher."""

    enabled: bool = True
    max_concurrent_tasks: int = 5
    max_retries: int = 2
    task_timeout_seconds: int = 300  # 5 minutes
    worker_heartbeat_interval: int = 30
    enable_priority_scheduling: bool = True

    @classmethod
    def from_env(cls) -> "DispatcherConfig":
        return cls(
            enabled=_env_bool("AIC_DISPATCHER_ENABLED", True),
            max_concurrent_tasks=_env_int("AIC_DISPATCHER_MAX_CONCURRENT", 5),
            max_retries=_env_int("AIC_DISPATCHER_MAX_RETRIES", 2),
            task_timeout_seconds=_env_int("AIC_DISPATCHER_TASK_TIMEOUT", 300),
            worker_heartbeat_interval=_env_int("AIC_DISPATCHER_HEARTBEAT_INTERVAL", 30),
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


dispatcher_config = DispatcherConfig.from_env()

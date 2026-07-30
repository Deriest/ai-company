"""Autonomous Execution Intelligence — Configuration."""

import os
from dataclasses import dataclass


@dataclass
class AutonomyConfig:
    """Configuration for Autonomous Execution Intelligence."""

    enabled: bool = True
    max_recovery_attempts: int = 3
    anomaly_detection_enabled: bool = True
    self_healing_enabled: bool = True
    escalation_timeout_seconds: int = 300

    @classmethod
    def from_env(cls) -> "AutonomyConfig":
        return cls(
            enabled=_env_bool("AIC_AUTONOMY_ENABLED", True),
            max_recovery_attempts=_env_int("AIC_AUTONOMY_MAX_RECOVERY", 3),
            anomaly_detection_enabled=_env_bool("AIC_AUTONOMY_ANOMALY_DETECTION", True),
            self_healing_enabled=_env_bool("AIC_AUTONOMY_SELF_HEALING", True),
            escalation_timeout_seconds=_env_int("AIC_AUTONOMY_ESCALATION_TIMEOUT", 300),
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


autonomy_config = AutonomyConfig.from_env()

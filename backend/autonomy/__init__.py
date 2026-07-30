"""AIC Platform — Autonomous Execution Intelligence (v2.3.8).

Enables self-healing, adaptive execution that recovers from failures.
"""

from autonomy.config import autonomy_config, AutonomyConfig
from autonomy.models import RecoveryAction, AnomalyDetection, HealingResult

__all__ = [
    "autonomy_config",
    "AutonomyConfig",
    "RecoveryAction",
    "AnomalyDetection",
    "HealingResult",
]

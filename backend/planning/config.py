"""Planning Engine — Configuration.

Feature flags, thresholds, and environment-based configuration.
"""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger("aic.planning.config")


@dataclass
class PlanningConfig:
    """Configuration for the Planning Engine."""

    # Feature flag
    enabled: bool = True

    # Planning limits
    max_architecture_decisions: int = 20
    max_risk_mitigations: int = 15
    max_effort_estimates: int = 50

    # Validation
    min_confidence_score: float = 0.6
    require_risk_mitigation: bool = True

    # Performance
    max_planning_latency_ms: int = 30000  # 30 seconds

    # LLM
    llm_enabled: bool = True
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000

    @classmethod
    def from_env(cls) -> "PlanningConfig":
        """Load from environment variables."""
        return cls(
            enabled=_env_bool("AIC_PLANNING_ENABLED", True),
            max_architecture_decisions=_env_int("AIC_PLANNING_MAX_DECISIONS", 20),
            max_risk_mitigations=_env_int("AIC_PLANNING_MAX_RISKS", 15),
            max_effort_estimates=_env_int("AIC_PLANNING_MAX_ESTIMATES", 50),
            min_confidence_score=_env_float("AIC_PLANNING_MIN_CONFIDENCE", 0.6),
            require_risk_mitigation=_env_bool("AIC_PLANNING_REQUIRE_RISK_MITIGATION", True),
            max_planning_latency_ms=_env_int("AIC_PLANNING_MAX_LATENCY_MS", 30000),
            llm_enabled=_env_bool("AIC_PLANNING_LLM_ENABLED", True),
            llm_temperature=_env_float("AIC_PLANNING_LLM_TEMPERATURE", 0.3),
            llm_max_tokens=_env_int("AIC_PLANNING_LLM_MAX_TOKENS", 2000),
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


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


# Singleton
planning_config = PlanningConfig.from_env()

"""Engineering Discovery Engine — Configuration.

Feature flags, thresholds, limits, and environment-based configuration.
All discovery behaviour is controlled from this module.
"""

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("aic.discovery.config")


@dataclass
class DiscoveryConfig:
    """Configuration for the Engineering Discovery Engine.

    Loaded from environment variables with AIC_DISCOVERY_ prefix.
    """

    # Feature flag — master switch
    enabled: bool = True

    # Clarification limits — ACCURACY OVER SPEED
    # Targeting 80-85% confidence before proceeding
    max_clarification_rounds: int = 4           # Allow up to 4 rounds if needed
    max_questions_per_round: int = 5           # Max 5 focused questions per round

    # Readiness thresholds
    readiness_threshold: float = 0.80
    dimension_floor: float = 0.40

    # Timeouts
    clarification_timeout_minutes: int = 30

    # Logging
    log_level: str = "INFO"
    log_decisions: bool = True
    log_questions: bool = True

    # LLM
    llm_enabled: bool = True
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1000
    llm_purpose: str = "discovery"

    # Performance
    max_latency_ms: int = 5000

    # Extensibility
    custom_domains: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "DiscoveryConfig":
        """Load configuration from environment variables.

        Environment variables use AIC_DISCOVERY_ prefix.
        Falls back to sensible defaults when not set.
        """
        return cls(
            enabled=_env_bool("AIC_DISCOVERY_ENABLED", True),
            max_clarification_rounds=_env_int("AIC_DISCOVERY_MAX_ROUNDS", 3),
            max_questions_per_round=_env_int("AIC_DISCOVERY_MAX_QUESTIONS", 10),
            readiness_threshold=_env_float("AIC_DISCOVERY_READINESS_THRESHOLD", 0.80),
            dimension_floor=_env_float("AIC_DISCOVERY_DIMENSION_FLOOR", 0.40),
            clarification_timeout_minutes=_env_int("AIC_DISCOVERY_TIMEOUT_MINUTES", 30),
            log_level=_env_str("AIC_DISCOVERY_LOG_LEVEL", "INFO"),
            log_decisions=_env_bool("AIC_DISCOVERY_LOG_DECISIONS", True),
            log_questions=_env_bool("AIC_DISCOVERY_LOG_QUESTIONS", True),
            llm_enabled=_env_bool("AIC_DISCOVERY_LLM_ENABLED", True),
            llm_temperature=_env_float("AIC_DISCOVERY_LLM_TEMPERATURE", 0.3),
            llm_max_tokens=_env_int("AIC_DISCOVERY_LLM_MAX_TOKENS", 1000),
            max_latency_ms=_env_int("AIC_DISCOVERY_MAX_LATENCY_MS", 5000),
        )

    def update(self, **kwargs) -> None:
        """Update configuration values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown config key: {key}")


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


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
        logger.warning(f"Invalid int for {key}: {val}, using default {default}")
        return default


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        logger.warning(f"Invalid float for {key}: {val}, using default {default}")
        return default


# Singleton — loaded once at import time
discovery_config = DiscoveryConfig.from_env()

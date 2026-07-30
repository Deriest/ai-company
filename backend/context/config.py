"""Context & Knowledge Intelligence — Configuration."""

import os
from dataclasses import dataclass


@dataclass
class ContextConfig:
    """Configuration for Context & Knowledge Intelligence."""

    enabled: bool = True
    max_knowledge_entries: int = 10000
    context_freshness_minutes: int = 5
    enable_learning: bool = True

    @classmethod
    def from_env(cls) -> "ContextConfig":
        return cls(
            enabled=_env_bool("AIC_CONTEXT_ENABLED", True),
            max_knowledge_entries=_env_int("AIC_CONTEXT_MAX_ENTRIES", 10000),
            context_freshness_minutes=_env_int("AIC_CONTEXT_FRESHNESS_MINUTES", 5),
            enable_learning=_env_bool("AIC_CONTEXT_LEARNING_ENABLED", True),
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


context_config = ContextConfig.from_env()

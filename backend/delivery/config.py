"""Delivery & Continuous Improvement — Configuration."""

import os
from dataclasses import dataclass


@dataclass
class DeliveryConfig:
    """Configuration for Delivery & Continuous Improvement."""

    enabled: bool = True
    generate_reports: bool = True
    extract_lessons: bool = True
    enable_feedback_loop: bool = True

    @classmethod
    def from_env(cls) -> "DeliveryConfig":
        return cls(
            enabled=_env_bool("AIC_DELIVERY_ENABLED", True),
            generate_reports=_env_bool("AIC_DELIVERY_REPORTS", True),
            extract_lessons=_env_bool("AIC_DELIVERY_LESSONS", True),
            enable_feedback_loop=_env_bool("AIC_DELIVERY_FEEDBACK", True),
        )


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


delivery_config = DeliveryConfig.from_env()

"""Verification Engine — Configuration."""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger("aic.verification.config")


@dataclass
class VerificationConfig:
    """Configuration for the Verification Engine."""

    enabled: bool = True
    min_quality_score: float = 0.7
    require_all_requirements_met: bool = True
    enable_security_check: bool = True
    enable_regression_check: bool = True

    @classmethod
    def from_env(cls) -> "VerificationConfig":
        return cls(
            enabled=_env_bool("AIC_VERIFICATION_ENABLED", True),
            min_quality_score=_env_float("AIC_VERIFICATION_MIN_QUALITY", 0.7),
            enable_security_check=_env_bool("AIC_VERIFICATION_SECURITY_CHECK", True),
            enable_regression_check=_env_bool("AIC_VERIFICATION_REGRESSION_CHECK", True),
        )


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


verification_config = VerificationConfig.from_env()

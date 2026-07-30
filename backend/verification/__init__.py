"""AIC Platform — Verification Engine (v2.3.6).

Verifies that worker output meets acceptance criteria and quality standards.
"""

from verification.config import verification_config, VerificationConfig
from verification.states import VerificationState, can_transition, is_terminal
from verification.models import VerificationReport, RequirementCheck, QualityScore

__all__ = [
    "verification_config",
    "VerificationConfig",
    "VerificationState",
    "can_transition",
    "is_terminal",
    "VerificationReport",
    "RequirementCheck",
    "QualityScore",
]

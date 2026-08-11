"""Verification Engine — State Machine."""

from enum import Enum as PyEnum


class VerificationState(str, PyEnum):
    """Verification states.

    Implements three key distinctions (PHASE 7):
    - IMPLEMENTED: Code/features present in output
    - TESTED: Tests executed and passed for features  
    - VERIFIED: Full acceptance criteria met with verified tests
    """

    # Output processing states
    OUTPUT_RECEIVED = "output_received"
    ANALYZING_OUTPUT = "analyzing_output"
    
    # Requirements assessment states
    VERIFYING_REQUIREMENTS = "verifying_requirements"
    VALIDATING_ACCEPTANCE = "validating_acceptance"
    
    # Quality assessment states
    CHECKING_QUALITY = "checking_quality"
    VERIFYING_REGRESSION = "verifying_regression"
    REVIEWING_SECURITY = "reviewing_security"
    GENERATING_REPORT = "generating_report"
    
    # PHASE 7: Implementation status states
    IMPLEMENTED = "implemented"  # Features present but untested
    TESTED = "tested"  # Features implemented AND tests passing
    VERIFIED = "verified"  # All acceptance criteria met with verified tests
    
    # Terminal states
    VERIFICATION_COMPLETE = "verification_complete"
    VERIFICATION_FAILED = "verification_failed"
    ABORTED = "aborted"
    ERROR = "error"


TRANSITIONS: dict[str, list[str]] = {
    VerificationState.OUTPUT_RECEIVED: [
        VerificationState.ANALYZING_OUTPUT,
        VerificationState.IMPLEMENTED,  # Can skip directly if no analysis needed
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.ANALYZING_OUTPUT: [
        VerificationState.VERIFYING_REQUIREMENTS,
        VerificationState.IMPLEMENTED,  # Evidence of implementation found
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.VERIFYING_REQUIREMENTS: [
        VerificationState.VALIDATING_ACCEPTANCE,
        VerificationState.IMPLEMENTED,  # Requirements met but not tested
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.VALIDATING_ACCEPTANCE: [
        VerificationState.CHECKING_QUALITY,
        VerificationState.TESTED,  # Acceptance criteria + tests passing
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.CHECKING_QUALITY: [
        VerificationState.VERIFYING_REGRESSION,
        VerificationState.TESTED,  # Quality checked + tests passing
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.VERIFYING_REGRESSION: [
        VerificationState.REVIEWING_SECURITY,
        VerificationState.TESTED,  # No regressions + tests passing
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.REVIEWING_SECURITY: [
        VerificationState.GENERATING_REPORT,
        VerificationState.VERIFIED,  # Security ok + all checks pass
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.GENERATING_REPORT: [
        VerificationState.VERIFICATION_COMPLETE,
        VerificationState.VERIFICATION_FAILED,
        VerificationState.VERIFIED,  # Report generated successfully
        VerificationState.ABORTED,
        VerificationState.ERROR,
    ],
    VerificationState.VERIFICATION_COMPLETE: [],
    VerificationState.VERIFICATION_FAILED: [],
    VerificationState.ABORTED: [],
    VerificationState.ERROR: [],
}

TERMINAL_STATES = frozenset([
    VerificationState.VERIFICATION_COMPLETE,
    VerificationState.VERIFICATION_FAILED,
    VerificationState.ABORTED,
    VerificationState.ERROR,
])


def can_transition(from_state: str, to_state: str) -> bool:
    allowed = TRANSITIONS.get(from_state, [])
    return to_state in allowed


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def next_states(state: str) -> list[str]:
    return TRANSITIONS.get(state, [])


def validate_state(state: str) -> str | None:
    try:
        return VerificationState(state).value
    except ValueError:
        return None

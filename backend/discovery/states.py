"""Engineering Discovery Engine — State Machine.

Defines Discovery-specific states and transition rules.
These states are stored in DiscoverySession.status and track the
lifecycle of a discovery session.
"""

from enum import Enum as PyEnum


class DiscoveryState(str, PyEnum):
    """Discovery session states."""

    NEW_REQUEST = "new_request"
    DISCOVERY = "discovery"
    ENGINEERING_ANALYSIS = "engineering_analysis"
    CLARIFICATION = "clarification"
    USER_RESPONSE = "user_response"
    REQUIREMENT_UPDATE = "requirement_update"
    ENGINEERING_BRIEF_COMPLETE = "engineering_brief_complete"
    HANDOFF_TO_PLANNING = "handoff_to_planning"
    ABORTED = "aborted"
    TIMEOUT = "timeout"
    ERROR = "error"


# Valid transitions: from_state → [allowed_to_states]
TRANSITIONS: dict[str, list[str]] = {
    DiscoveryState.NEW_REQUEST: [
        DiscoveryState.DISCOVERY,
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.DISCOVERY: [
        DiscoveryState.ENGINEERING_ANALYSIS,
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.ENGINEERING_ANALYSIS: [
        DiscoveryState.ENGINEERING_BRIEF_COMPLETE,  # READY
        DiscoveryState.CLARIFICATION,                # NOT READY
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.CLARIFICATION: [
        DiscoveryState.USER_RESPONSE,
        DiscoveryState.TIMEOUT,
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.USER_RESPONSE: [
        DiscoveryState.REQUIREMENT_UPDATE,
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.REQUIREMENT_UPDATE: [
        DiscoveryState.ENGINEERING_ANALYSIS,  # Re-evaluate
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.ENGINEERING_BRIEF_COMPLETE: [
        DiscoveryState.HANDOFF_TO_PLANNING,
        DiscoveryState.ABORTED,
        DiscoveryState.ERROR,
    ],
    DiscoveryState.HANDOFF_TO_PLANNING: [],  # Terminal
    DiscoveryState.ABORTED: [],              # Terminal
    DiscoveryState.TIMEOUT: [],              # Terminal
    DiscoveryState.ERROR: [],                # Terminal
}

# Terminal states — no further transitions possible
TERMINAL_STATES = frozenset([
    DiscoveryState.HANDOFF_TO_PLANNING,
    DiscoveryState.ABORTED,
    DiscoveryState.TIMEOUT,
    DiscoveryState.ERROR,
])


def can_transition(from_state: str, to_state: str) -> bool:
    """Check if a state transition is valid.

    Args:
        from_state: Current state (string value of DiscoveryState)
        to_state: Target state (string value of DiscoveryState)

    Returns:
        True if transition is allowed, False otherwise.
    """
    allowed = TRANSITIONS.get(from_state, [])
    return to_state in allowed


def is_terminal(state: str) -> bool:
    """Check if a state is terminal (no further transitions).

    Args:
        state: State string value

    Returns:
        True if terminal, False otherwise.
    """
    return state in TERMINAL_STATES


def next_states(state: str) -> list[str]:
    """Get list of valid next states from current state.

    Args:
        state: Current state string value

    Returns:
        List of valid next state values. Empty if terminal.
    """
    return TRANSITIONS.get(state, [])


def validate_state(state: str) -> str | None:
    """Validate and normalize a state string.

    Args:
        state: State string to validate

    Returns:
        Normalized state string if valid, None if invalid.
    """
    try:
        return DiscoveryState(state).value
    except ValueError:
        return None

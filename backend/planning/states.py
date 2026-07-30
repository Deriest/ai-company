"""Planning Engine — State Machine.

Defines Planning-specific states and transition rules.
"""

from enum import Enum as PyEnum


class PlanningState(str, PyEnum):
    """Planning session states."""

    BRIEF_RECEIVED = "brief_received"
    ANALYZING = "analyzing"
    DECISION_MAKING = "decision_making"
    PLAN_DRAFTING = "plan_drafting"
    PLAN_VALIDATING = "plan_validating"
    PLAN_COMPLETE = "plan_complete"
    HANDOFF_TO_TASKGRAPH = "handoff_to_taskgraph"
    REVISING = "revising"
    ABORTED = "aborted"
    ERROR = "error"


# Valid transitions
TRANSITIONS: dict[str, list[str]] = {
    PlanningState.BRIEF_RECEIVED: [
        PlanningState.ANALYZING,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.ANALYZING: [
        PlanningState.DECISION_MAKING,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.DECISION_MAKING: [
        PlanningState.PLAN_DRAFTING,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.PLAN_DRAFTING: [
        PlanningState.PLAN_VALIDATING,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.PLAN_VALIDATING: [
        PlanningState.PLAN_COMPLETE,  # Valid
        PlanningState.REVISING,       # Invalid, needs revision
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.REVISING: [
        PlanningState.PLAN_DRAFTING,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.PLAN_COMPLETE: [
        PlanningState.HANDOFF_TO_TASKGRAPH,
        PlanningState.ABORTED,
        PlanningState.ERROR,
    ],
    PlanningState.HANDOFF_TO_TASKGRAPH: [],  # Terminal
    PlanningState.ABORTED: [],               # Terminal
    PlanningState.ERROR: [],                 # Terminal
}

TERMINAL_STATES = frozenset([
    PlanningState.HANDOFF_TO_TASKGRAPH,
    PlanningState.ABORTED,
    PlanningState.ERROR,
])


def can_transition(from_state: str, to_state: str) -> bool:
    """Check if a state transition is valid."""
    allowed = TRANSITIONS.get(from_state, [])
    return to_state in allowed


def is_terminal(state: str) -> bool:
    """Check if a state is terminal."""
    return state in TERMINAL_STATES


def next_states(state: str) -> list[str]:
    """Get valid next states."""
    return TRANSITIONS.get(state, [])


def validate_state(state: str) -> str | None:
    """Validate and normalize a state string."""
    try:
        return PlanningState(state).value
    except ValueError:
        return None

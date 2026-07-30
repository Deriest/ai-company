"""Task Graph Engine — State Machine."""

from enum import Enum as PyEnum


class TaskGraphState(str, PyEnum):
    """Task graph states."""

    PLAN_RECEIVED = "plan_received"
    DECOMPOSING = "decomposing"
    ANALYZING_DEPENDENCIES = "analyzing_dependencies"
    COMPUTING_ORDER = "computing_order"
    VALIDATING_GRAPH = "validating_graph"
    GRAPH_COMPLETE = "graph_complete"
    HANDOFF_TO_DISPATCHER = "handoff_to_dispatcher"
    FIXING_CYCLES = "fixing_cycles"
    ABORTED = "aborted"
    ERROR = "error"


TRANSITIONS: dict[str, list[str]] = {
    TaskGraphState.PLAN_RECEIVED: [
        TaskGraphState.DECOMPOSING,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.DECOMPOSING: [
        TaskGraphState.ANALYZING_DEPENDENCIES,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.ANALYZING_DEPENDENCIES: [
        TaskGraphState.COMPUTING_ORDER,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.COMPUTING_ORDER: [
        TaskGraphState.VALIDATING_GRAPH,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.VALIDATING_GRAPH: [
        TaskGraphState.GRAPH_COMPLETE,
        TaskGraphState.FIXING_CYCLES,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.FIXING_CYCLES: [
        TaskGraphState.COMPUTING_ORDER,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.GRAPH_COMPLETE: [
        TaskGraphState.HANDOFF_TO_DISPATCHER,
        TaskGraphState.ABORTED,
        TaskGraphState.ERROR,
    ],
    TaskGraphState.HANDOFF_TO_DISPATCHER: [],
    TaskGraphState.ABORTED: [],
    TaskGraphState.ERROR: [],
}

TERMINAL_STATES = frozenset([
    TaskGraphState.HANDOFF_TO_DISPATCHER,
    TaskGraphState.ABORTED,
    TaskGraphState.ERROR,
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
        return TaskGraphState(state).value
    except ValueError:
        return None

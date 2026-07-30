"""Engineering Dispatcher — State Machine."""

from enum import Enum as PyEnum


class DispatcherState(str, PyEnum):
    """Dispatcher states."""

    GRAPH_RECEIVED = "graph_received"
    SELECTING_WORKERS = "selecting_workers"
    SCHEDULING = "scheduling"
    DISPATCHING = "dispatching"
    MONITORING = "monitoring"
    COLLECTING_RESULTS = "collecting_results"
    DISPATCHER_COMPLETE = "dispatcher_complete"
    RETRYING = "retrying"
    ESCALATING = "escalating"
    DISPATCHER_FAILED = "dispatcher_failed"
    ABORTED = "aborted"
    ERROR = "error"


TRANSITIONS: dict[str, list[str]] = {
    DispatcherState.GRAPH_RECEIVED: [
        DispatcherState.SELECTING_WORKERS,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.SELECTING_WORKERS: [
        DispatcherState.SCHEDULING,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.SCHEDULING: [
        DispatcherState.DISPATCHING,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.DISPATCHING: [
        DispatcherState.MONITORING,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.MONITORING: [
        DispatcherState.COLLECTING_RESULTS,
        DispatcherState.RETRYING,
        DispatcherState.ESCALATING,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.RETRYING: [
        DispatcherState.DISPATCHING,
        DispatcherState.ESCALATING,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.ESCALATING: [
        DispatcherState.DISPATCHER_FAILED,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.COLLECTING_RESULTS: [
        DispatcherState.DISPATCHER_COMPLETE,
        DispatcherState.ABORTED,
        DispatcherState.ERROR,
    ],
    DispatcherState.DISPATCHER_COMPLETE: [],
    DispatcherState.DISPATCHER_FAILED: [],
    DispatcherState.ABORTED: [],
    DispatcherState.ERROR: [],
}

TERMINAL_STATES = frozenset([
    DispatcherState.DISPATCHER_COMPLETE,
    DispatcherState.DISPATCHER_FAILED,
    DispatcherState.ABORTED,
    DispatcherState.ERROR,
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
        return DispatcherState(state).value
    except ValueError:
        return None

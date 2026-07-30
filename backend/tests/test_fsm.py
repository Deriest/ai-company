"""AIC Platform — FSM Tests.

Tests the workflow finite state machine:
- Phase transitions
- Terminal state protection
- Barrier satisfaction (fail-closed)
- Worker-phase validation
"""
import time
import pytest
from workflow.fsm import (
    PHASE_ORDER, TERMINAL_STATES, APPROVAL_PHASES,
    validate_phase, next_phase, is_terminal, can_advance,
    allowed_workers_for_phase, validate_worker_for_phase,
    Barrier, normalize_phase,
)


class TestFSMPhases:
    def test_phase_order(self):
        assert PHASE_ORDER[0] == "created"
        assert PHASE_ORDER[-1] == "completed"

    def test_validate_phase_valid(self):
        assert validate_phase("created") == "created"
        assert validate_phase("PLANNING") == "planning"
        assert validate_phase("Implementation") == "implementation"

    def test_validate_phase_invalid(self):
        assert validate_phase("unknown") is None
        assert validate_phase("") is None
        assert validate_phase(None) is None

    def test_next_phase(self):
        assert next_phase("created") == "discovery"
        assert next_phase("discovery") == "investigate"
        assert next_phase("planning") == "implementation"
        assert next_phase("closeout") == "completed"

    def test_next_phase_terminal(self):
        assert next_phase("completed") is None
        assert next_phase("cancelled") is None
        assert next_phase("blocked") is None

    def test_is_terminal(self):
        assert is_terminal("completed") is True
        assert is_terminal("cancelled") is True
        assert is_terminal("blocked") is True
        assert is_terminal("created") is False
        assert is_terminal("implementation") is False


class TestFSMCanAdvance:
    def test_can_advance_normal(self):
        assert can_advance("planning", barrier_complete=True, pm_review_passed=True) is True

    def test_cannot_advance_barrier_incomplete(self):
        assert can_advance("planning", barrier_complete=False, pm_review_passed=True) is False

    def test_cannot_advance_terminal(self):
        assert can_advance("completed", barrier_complete=True, pm_review_passed=True) is False
        assert can_advance("cancelled", barrier_complete=True, pm_review_passed=True) is False

    def test_approval_gate_blocks(self):
        # approval phase requires approval_passed
        assert can_advance("planning", barrier_complete=True, pm_review_passed=True, approval_passed=False) is False
        assert can_advance("planning", barrier_complete=True, pm_review_passed=True, approval_passed=True) is True

    def test_pm_review_gate(self):
        assert can_advance("closeout", barrier_complete=True, pm_review_passed=False) is False
        assert can_advance("closeout", barrier_complete=True, pm_review_passed=True) is True


class TestBarrier:
    def test_barrier_satisfied(self):
        b = Barrier.start(["coding", "testing"])
        b.mark_complete("coding")
        assert b.is_satisfied() is False
        b.mark_complete("testing")
        assert b.is_satisfied() is True

    def test_barrier_fail_closed_on_timeout(self):
        b = Barrier.start(["coding"], timeout=1)
        b.started_at = time.time() - 2  # pretend started 2s ago, timeout is 1s
        assert b.is_satisfied() is False
        assert b.timed_out is True
        assert b.active is False

    def test_barrier_empty_workers(self):
        b = Barrier.start([])
        assert b.is_satisfied() is True

    def test_barrier_reset_for_repair(self):
        b = Barrier.start(["coding", "testing"])
        b.mark_complete("coding")
        b.mark_complete("testing")
        b.reset_for_repair(["coding"])
        assert "coding" not in b.completed
        assert "testing" in b.completed

    def test_barrier_mark_failed(self):
        b = Barrier.start(["coding"])
        b.mark_failed("coding", "timeout")
        assert b.failed["coding"] == "timeout"
        # Should not be satisfied even if worker is in failed
        assert b.is_satisfied() is False

    def test_barrier_roundtrip(self):
        b = Barrier.start(["coding"])
        b.mark_complete("coding")
        d = b.to_dict()
        b2 = Barrier.from_dict(d)
        assert b2.is_satisfied() is True


class TestWorkerPhaseValidation:
    def test_allowed_workers_planning(self):
        workers = allowed_workers_for_phase("planning")
        assert "architect" in workers
        assert "designer" in workers

    def test_allowed_workers_implementation(self):
        workers = allowed_workers_for_phase("implementation")
        assert "backend" in workers
        assert "frontend" in workers

    def test_validate_worker_for_phase_valid(self):
        assert validate_worker_for_phase("backend", "implementation") is True
        assert validate_worker_for_phase("architect", "planning") is True

    def test_validate_worker_for_phase_invalid(self):
        # Coding worker not allowed in planning phase
        assert validate_worker_for_phase("coding", "planning") is False
        # Planner not allowed in implementation
        assert validate_worker_for_phase("planner", "implementation") is False

    def test_validate_worker_terminal_phase(self):
        assert validate_worker_for_phase("coding", "completed") is False
        assert allowed_workers_for_phase("completed") == []

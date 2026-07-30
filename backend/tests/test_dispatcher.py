"""AIC Platform — Engineering Dispatcher Tests."""

import pytest
from dispatcher.config import DispatcherConfig, dispatcher_config
from dispatcher.states import DispatcherState, can_transition, is_terminal, next_states, validate_state
from dispatcher.models import DispatchResult, TaskExecution, WorkerAssignment
from dispatcher.scheduler import TaskScheduler
from dispatcher.worker_selector import WorkerSelector


# ============================================================
# Configuration Tests
# ============================================================

class TestDispatcherConfig:
    """Test dispatcher configuration."""

    def test_default_config(self):
        config = DispatcherConfig()
        assert config.enabled is True
        assert config.max_concurrent_tasks == 5
        assert config.max_retries == 2

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_DISPATCHER_ENABLED", "false")
        config = DispatcherConfig.from_env()
        assert config.enabled is False


# ============================================================
# State Machine Tests
# ============================================================

class TestDispatcherStates:
    """Test dispatcher state machine."""

    def test_valid_transitions(self):
        assert can_transition(DispatcherState.GRAPH_RECEIVED, DispatcherState.SELECTING_WORKERS) is True
        assert can_transition(DispatcherState.SELECTING_WORKERS, DispatcherState.SCHEDULING) is True
        assert can_transition(DispatcherState.SCHEDULING, DispatcherState.DISPATCHING) is True

    def test_invalid_transitions(self):
        assert can_transition(DispatcherState.GRAPH_RECEIVED, DispatcherState.DISPATCHER_COMPLETE) is False

    def test_terminal_states(self):
        assert is_terminal(DispatcherState.DISPATCHER_COMPLETE) is True
        assert is_terminal(DispatcherState.DISPATCHER_FAILED) is True
        assert is_terminal(DispatcherState.ABORTED) is True
        assert is_terminal(DispatcherState.GRAPH_RECEIVED) is False

    def test_validate_state(self):
        assert validate_state("graph_received") == "graph_received"
        assert validate_state("invalid") is None


# ============================================================
# Model Tests
# ============================================================

class TestDispatcherModels:
    """Test dispatcher data models."""

    def test_worker_assignment(self):
        assignment = WorkerAssignment(
            worker_id="worker-1",
            worker_type="backend",
            node_id="NODE-001",
        )
        assert assignment.worker_type == "backend"

    def test_task_execution(self):
        execution = TaskExecution(
            node_id="NODE-001",
            status="pending",
        )
        assert execution.status == "pending"
        assert execution.attempts == 0

    def test_dispatch_result(self):
        result = DispatchResult(
            graph_id="GRAPH-TEST",
            status="pending",
        )
        assert result.execution_id.startswith("EXEC-")

    def test_dispatch_result_to_dict(self):
        result = DispatchResult(
            graph_id="GRAPH-TEST",
            task_results={
                "N1": TaskExecution(node_id="N1", status="completed"),
            },
        )
        data = result.to_dict()
        assert "execution_id" in data
        assert "task_results" in data


# ============================================================
# Scheduler Tests
# ============================================================

class TestTaskScheduler:
    """Test task scheduling."""

    def test_schedule_tasks(self):
        execution_order = [["N1", "N2"], ["N3"]]
        task_results = {
            "N1": TaskExecution(node_id="N1", status="pending"),
            "N2": TaskExecution(node_id="N2", status="pending"),
            "N3": TaskExecution(node_id="N3", status="pending"),
        }
        scheduled = TaskScheduler.schedule_tasks(execution_order, task_results)
        assert len(scheduled) == 2

    def test_schedule_with_completed(self):
        execution_order = [["N1", "N2"], ["N3"]]
        task_results = {
            "N1": TaskExecution(node_id="N1", status="completed"),
            "N2": TaskExecution(node_id="N2", status="pending"),
            "N3": TaskExecution(node_id="N3", status="pending"),
        }
        scheduled = TaskScheduler.schedule_tasks(execution_order, task_results)
        assert len(scheduled) == 2

    def test_get_next_tasks(self):
        scheduled = [["N1", "N2"], ["N3"]]
        next_tasks = TaskScheduler.get_next_tasks(scheduled, max_concurrent=2)
        assert len(next_tasks) <= 2

    def test_mark_task_complete(self):
        scheduled = [["N1", "N2"], ["N3"]]
        updated = TaskScheduler.mark_task_complete(scheduled, "N1")
        assert len(updated) == 2

    def test_is_complete(self):
        assert TaskScheduler.is_complete([]) is True
        assert TaskScheduler.is_complete([[]]) is True
        assert TaskScheduler.is_complete([["N1"]]) is False


# ============================================================
# Worker Selection Tests
# ============================================================

class TestWorkerSelector:
    """Test worker selection."""

    def test_select_backend_worker(self):
        assignment = WorkerSelector.select_worker(
            node_id="N1",
            worker_type="backend",
            task_type="coding",
        )
        assert assignment.worker_type == "backend"
        assert assignment.node_id == "N1"

    def test_select_frontend_worker(self):
        assignment = WorkerSelector.select_worker(
            node_id="N1",
            worker_type="frontend",
            task_type="ui",
        )
        assert assignment.worker_type == "frontend"

    def test_select_qa_worker(self):
        assignment = WorkerSelector.select_worker(
            node_id="N1",
            worker_type="qa",
            task_type="testing",
        )
        assert assignment.worker_type == "qa"

    def test_get_worker_tier(self):
        assert WorkerSelector.get_worker_tier("architect") == "thinker"
        assert WorkerSelector.get_worker_tier("backend") == "crafter"
        assert WorkerSelector.get_worker_tier("qa") == "sprinter"

    def test_get_worker_capabilities(self):
        caps = WorkerSelector.get_worker_capabilities("backend")
        assert "coding" in caps
        assert "api" in caps


# ============================================================
# Integration Tests
# ============================================================

class TestDispatcherIntegration:
    """Integration tests for dispatcher pipeline."""

    def test_full_pipeline(self):
        """Test full dispatch pipeline."""
        # Simulate graph data
        nodes = [
            {"node_id": "N1", "title": "Implement", "worker_type": "backend", "task_type": "coding"},
            {"node_id": "N2", "title": "Test", "worker_type": "qa", "task_type": "testing"},
        ]
        execution_order = [["N1"], ["N2"]]

        # Initialize task results
        task_results = {}
        for node in nodes:
            task_results[node["node_id"]] = TaskExecution(
                node_id=node["node_id"],
                status="pending",
            )

        # Select workers
        assignments = []
        for node in nodes:
            assignment = WorkerSelector.select_worker(
                node_id=node["node_id"],
                worker_type=node["worker_type"],
                task_type=node["task_type"],
            )
            assignments.append(assignment)

        # Schedule
        scheduled = TaskScheduler.schedule_tasks(execution_order, task_results)
        assert len(scheduled) >= 1

        # Get next tasks
        next_tasks = TaskScheduler.get_next_tasks(scheduled, max_concurrent=2)
        assert len(next_tasks) >= 1

        # Mark complete and verify
        for task_id in next_tasks:
            task_results[task_id].status = "completed"
            scheduled = TaskScheduler.mark_task_complete(scheduled, task_id)

        # N2 is still pending in second group
        assert len(scheduled) >= 1

        # Complete N2
        next_tasks = TaskScheduler.get_next_tasks(scheduled, max_concurrent=2)
        for task_id in next_tasks:
            task_results[task_id].status = "completed"
            scheduled = TaskScheduler.mark_task_complete(scheduled, task_id)

        assert TaskScheduler.is_complete(scheduled) is True

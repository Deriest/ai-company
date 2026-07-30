"""AIC Platform — Task Graph Engine Tests.

Comprehensive test suite for the Task Graph Engine (v2.3.4).
"""

import pytest
from taskgraph.config import TaskGraphConfig, taskgraph_config
from taskgraph.states import TaskGraphState, can_transition, is_terminal, next_states, validate_state
from taskgraph.models import TaskGraph, TaskNode, TaskEdge, GraphValidation, RecoveryPoint
from taskgraph.decomposer import PlanDecomposer
from taskgraph.dependency import DependencyAnalyzer
from taskgraph.validator import GraphValidator


# ============================================================
# Configuration Tests
# ============================================================

class TestTaskGraphConfig:
    """Test task graph configuration."""

    def test_default_config(self):
        config = TaskGraphConfig()
        assert config.enabled is True
        assert config.max_nodes == 100
        assert config.recovery_point_interval == 5

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_TASKGRAPH_ENABLED", "false")
        config = TaskGraphConfig.from_env()
        assert config.enabled is False


# ============================================================
# State Machine Tests
# ============================================================

class TestTaskGraphStates:
    """Test task graph state machine."""

    def test_valid_transitions(self):
        assert can_transition(TaskGraphState.PLAN_RECEIVED, TaskGraphState.DECOMPOSING) is True
        assert can_transition(TaskGraphState.DECOMPOSING, TaskGraphState.ANALYZING_DEPENDENCIES) is True
        assert can_transition(TaskGraphState.VALIDATING_GRAPH, TaskGraphState.GRAPH_COMPLETE) is True

    def test_invalid_transitions(self):
        assert can_transition(TaskGraphState.PLAN_RECEIVED, TaskGraphState.GRAPH_COMPLETE) is False

    def test_terminal_states(self):
        assert is_terminal(TaskGraphState.HANDOFF_TO_DISPATCHER) is True
        assert is_terminal(TaskGraphState.ABORTED) is True
        assert is_terminal(TaskGraphState.ERROR) is True
        assert is_terminal(TaskGraphState.PLAN_RECEIVED) is False

    def test_validate_state(self):
        assert validate_state("plan_received") == "plan_received"
        assert validate_state("invalid") is None


# ============================================================
# Model Tests
# ============================================================

class TestTaskGraphModels:
    """Test task graph data models."""

    def test_task_node_creation(self):
        node = TaskNode(
            title="Test task",
            description="Test description",
            task_type="coding",
            worker_type="backend",
        )
        assert node.node_id.startswith("NODE-")
        assert node.title == "Test task"

    def test_task_edge_creation(self):
        edge = TaskEdge(
            from_node="NODE-001",
            to_node="NODE-002",
            dependency_type="blocks",
        )
        assert edge.from_node == "NODE-001"
        assert edge.to_node == "NODE-002"

    def test_task_graph_creation(self):
        graph = TaskGraph(
            plan_id="PLAN-TEST",
            nodes=[TaskNode(title="Test")],
            edges=[],
        )
        assert graph.graph_id.startswith("GRAPH-")
        assert len(graph.nodes) == 1

    def test_task_graph_to_dict(self):
        graph = TaskGraph(
            plan_id="PLAN-TEST",
            nodes=[TaskNode(title="Test")],
        )
        data = graph.to_dict()
        assert "graph_id" in data
        assert "nodes" in data


# ============================================================
# Decomposer Tests
# ============================================================

class TestPlanDecomposer:
    """Test plan decomposition."""

    def test_decompose_with_requirements(self):
        plan_data = {
            "effort_estimates": [
                {"requirement_id": "REQ-001", "complexity": "medium", "description": "Add API endpoint"},
                {"requirement_id": "REQ-002", "complexity": "low", "description": "Update UI component"},
            ],
        }
        nodes = PlanDecomposer.decompose(plan_data)
        assert len(nodes) == 2
        assert nodes[0].task_type == "coding"

    def test_decompose_without_requirements(self):
        plan_data = {
            "engineering_goal": "Fix login bug",
        }
        nodes = PlanDecomposer.decompose(plan_data)
        assert len(nodes) >= 1

    def test_determine_worker_type(self):
        assert PlanDecomposer._determine_worker_type("Add API endpoint") == "backend"
        assert PlanDecomposer._determine_worker_type("Update UI component") == "frontend"
        assert PlanDecomposer._determine_worker_type("Add tests") == "qa"

    def test_determine_task_type(self):
        assert PlanDecomposer._determine_task_type("Add test coverage", "qa") == "testing"
        assert PlanDecomposer._determine_task_type("Write README", "documentation") == "documentation"
        assert PlanDecomposer._determine_task_type("Implement feature", "backend") == "coding"


# ============================================================
# Dependency Analysis Tests
# ============================================================

class TestDependencyAnalyzer:
    """Test dependency analysis."""

    def test_analyze_dependencies(self):
        nodes = [
            TaskNode(node_id="N1", title="Implement", task_type="coding"),
            TaskNode(node_id="N2", title="Test", task_type="testing"),
        ]
        edges = DependencyAnalyzer.analyze_dependencies(nodes)
        assert len(edges) >= 1
        assert any(e.from_node == "N1" and e.to_node == "N2" for e in edges)

    def test_detect_parallelism(self):
        nodes = [
            TaskNode(node_id="N1", title="Backend", worker_type="backend"),
            TaskNode(node_id="N2", title="Frontend", worker_type="frontend"),
        ]
        edges = []
        groups = DependencyAnalyzer.detect_parallelism(nodes, edges)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_detect_sequential(self):
        nodes = [
            TaskNode(node_id="N1", title="Implement", task_type="coding"),
            TaskNode(node_id="N2", title="Test", task_type="testing"),
        ]
        edges = DependencyAnalyzer.analyze_dependencies(nodes)
        groups = DependencyAnalyzer.detect_parallelism(nodes, edges)
        assert len(groups) >= 2

    def test_find_critical_path(self):
        nodes = [
            TaskNode(node_id="N1", title="A"),
            TaskNode(node_id="N2", title="B"),
            TaskNode(node_id="N3", title="C"),
        ]
        edges = [
            TaskEdge(from_node="N1", to_node="N2"),
            TaskEdge(from_node="N2", to_node="N3"),
        ]
        path = DependencyAnalyzer.find_critical_path(nodes, edges)
        assert len(path) == 3


# ============================================================
# Validation Tests
# ============================================================

class TestGraphValidator:
    """Test graph validation."""

    def test_validate_valid_graph(self):
        nodes = [
            TaskNode(node_id="N1", title="A"),
            TaskNode(node_id="N2", title="B"),
        ]
        edges = [TaskEdge(from_node="N1", to_node="N2")]
        validation = GraphValidator.validate(nodes, edges)
        assert validation.is_valid is True

    def test_validate_empty_graph(self):
        validation = GraphValidator.validate([], [])
        assert validation.is_valid is False
        assert any("no nodes" in e.lower() for e in validation.errors)

    def test_validate_duplicate_nodes(self):
        nodes = [
            TaskNode(node_id="N1", title="A"),
            TaskNode(node_id="N1", title="B"),
        ]
        validation = GraphValidator.validate(nodes, [])
        assert validation.is_valid is False
        assert any("duplicate" in e.lower() for e in validation.errors)

    def test_validate_invalid_edge(self):
        nodes = [TaskNode(node_id="N1", title="A")]
        edges = [TaskEdge(from_node="N1", to_node="N999")]
        validation = GraphValidator.validate(nodes, edges)
        assert validation.is_valid is False
        assert any("invalid" in e.lower() for e in validation.errors)

    def test_detect_cycle(self):
        nodes = [
            TaskNode(node_id="N1", title="A"),
            TaskNode(node_id="N2", title="B"),
            TaskNode(node_id="N3", title="C"),
        ]
        edges = [
            TaskEdge(from_node="N1", to_node="N2"),
            TaskEdge(from_node="N2", to_node="N3"),
            TaskEdge(from_node="N3", to_node="N1"),
        ]
        validation = GraphValidator.validate(nodes, edges)
        assert validation.is_valid is False
        assert len(validation.cycles_detected) > 0


# ============================================================
# Integration Tests
# ============================================================

class TestTaskGraphIntegration:
    """Integration tests for task graph pipeline."""

    def test_full_pipeline(self):
        """Test full pipeline from plan to graph."""
        plan_data = {
            "id": "PLAN-TEST",
            "engineering_goal": "Add dark mode",
            "effort_estimates": [
                {"requirement_id": "REQ-001", "complexity": "medium", "description": "Add toggle component"},
                {"requirement_id": "REQ-002", "complexity": "low", "description": "Add tests"},
            ],
        }

        # Decompose
        nodes = PlanDecomposer.decompose(plan_data)
        assert len(nodes) >= 1

        # Analyze dependencies
        edges = DependencyAnalyzer.analyze_dependencies(nodes)

        # Detect parallelism
        execution_order = DependencyAnalyzer.detect_parallelism(nodes, edges)
        assert len(execution_order) >= 1

        # Find critical path
        critical_path = DependencyAnalyzer.find_critical_path(nodes, edges)
        assert len(critical_path) >= 1

        # Validate
        validation = GraphValidator.validate(nodes, edges)
        assert validation.is_valid is True

        # Build graph
        graph = TaskGraph(
            plan_id=plan_data["id"],
            nodes=nodes,
            edges=edges,
            execution_order=execution_order,
            critical_path=critical_path,
            status="validated",
        )
        assert graph.status == "validated"
        assert len(graph.nodes) >= 1

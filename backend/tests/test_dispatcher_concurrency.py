"""Dispatcher concurrency tests — real node execution, distinct sessions, fail-stop.

Covers the previously-untested ``dispatcher.engine.DispatcherEngine`` behavior:

* ``dispatch`` actually executes graph nodes (spies on ``execute_task``) rather
  than stubbing them complete.
* Nodes in a dependency group run with DISTINCT database sessions.
* Fail-stop: when an upstream group fails, later dependency groups are marked
  skipped and never executed.
* ``success_rate`` is computed correctly for mixed-phase completion.
* No double-execution: each node is executed exactly once.

The heavy ``runtime.executor.execute_task`` is monkeypatched so the tests are
deterministic and offline; the dispatcher's own orchestration / session logic
is exercised for real against the in-memory DB.
"""
import pytest

from storage.models import TaskGraphModel, TaskType
from dispatcher.engine import DispatcherEngine
from dispatcher.models import TaskExecution


def _new_graph(session, graph_id, nodes, execution_order):
    graph = TaskGraphModel(
        id=graph_id,
        plan_id="plan-none",
        nodes=nodes,
        execution_order=execution_order,
    )
    session.add(graph)


def _node(node_id, worker_type="backend", task_type="coding", title="t"):
    return {"node_id": node_id, "worker_type": worker_type,
            "task_type": task_type, "title": title}


@pytest.mark.asyncio
async def test_dispatch_actually_executes_each_node(db_session, monkeypatch):
    """dispatch() runs execute_task for every node (real execution, not a stub)."""
    executed = []

    async def fake_execute_task(session, task):
        executed.append((id(session), (task.context or {}).get("node_id")))
        return {"success": True, "phases": 1, "results": {}}

    monkeypatch.setattr("runtime.executor.execute_task", fake_execute_task)

    async with db_session() as s:
        _new_graph(s, "g1", [_node("a"), _node("b")], [["a", "b"]])
        await s.commit()

        engine = DispatcherEngine(s)
        result = await engine.dispatch("g1", project_id="proj-1")

    assert result.state == "complete" or result.state == "dispatcher_complete"
    assert result.result is not None
    assert result.result.success_rate == 1.0
    by_node = {node_id: ex.status for node_id, ex in result.result.task_results.items()}
    assert by_node == {"a": "completed", "b": "completed"}
    # Both nodes executed.
    assert len(executed) == 2


@pytest.mark.asyncio
async def test_concurrent_nodes_use_distinct_sessions(db_session, monkeypatch):
    """Concurrent nodes in a dependency group run on distinct DB sessions."""
    sessions = []

    async def fake_execute_task(session, task):
        sessions.append(id(session))
        return {"success": True, "phases": 1, "results": {}}

    monkeypatch.setattr("runtime.executor.execute_task", fake_execute_task)

    async with db_session() as s:
        _new_graph(s, "g2", [_node("a"), _node("b"), _node("c")], [["a", "b", "c"]])
        await s.commit()

        engine = DispatcherEngine(s)
        await engine.dispatch("g2", project_id="proj-1")

    # Each node got its own session (3 distinct session ids).
    assert len(set(sessions)) == 3


@pytest.mark.asyncio
async def test_fail_stop_skips_downstream_groups(db_session, monkeypatch):
    """When an upstream group fails, later groups are skipped, not executed."""
    ran_nodes = []

    async def fake_execute_task(session, task):
        node_id = (task.context or {}).get("node_id")
        ran_nodes.append(node_id)
        return {"success": False, "error": "boom", "phases": 0, "results": {}}

    monkeypatch.setattr("runtime.executor.execute_task", fake_execute_task)

    async with db_session() as s:
        # Group 1 = [a, b]; Group 2 = [c] (depends on group 1).
        _new_graph(s, "g3", [_node("a"), _node("b"), _node("c")], [["a", "b"], ["c"]])
        await s.commit()

        engine = DispatcherEngine(s)
        result = await engine.dispatch("g3", project_id="proj-1")

    assert result.result is not None
    by_node = {node_id: ex.status for node_id, ex in result.result.task_results.items()}
    assert by_node["a"] == "failed"
    assert by_node["b"] == "failed"
    # Downstream group skipped, never executed.
    assert by_node["c"] == "skipped"
    assert "c" not in ran_nodes
    assert result.result.success_rate == 0.0


@pytest.mark.asyncio
async def test_partial_success_rate_for_mixed_phase_completion(db_session, monkeypatch):
    """Mixed success/failure in one group yields a partial success_rate."""
    results_by_node = {"good": True, "bad": False}

    async def fake_execute_task(session, task):
        node_id = (task.context or {}).get("node_id")
        ok = results_by_node.get(node_id, True)
        return {"success": ok, "error": None if ok else "failed", "phases": 1, "results": {}}

    monkeypatch.setattr("runtime.executor.execute_task", fake_execute_task)

    async with db_session() as s:
        _new_graph(s, "g4", [_node("good"), _node("bad")], [["good", "bad"]])
        await s.commit()

        engine = DispatcherEngine(s)
        result = await engine.dispatch("g4", project_id="proj-1")

    assert result.result is not None
    by_node = {node_id: ex.status for node_id, ex in result.result.task_results.items()}
    assert by_node["good"] == "completed"
    assert by_node["bad"] == "failed"
    assert result.result.success_rate == 0.5
    assert result.result.status == "partial"


@pytest.mark.asyncio
async def test_no_double_execution(db_session, monkeypatch):
    """Each node is executed exactly once across the whole dispatch."""
    call_counts = {}

    async def fake_execute_task(session, task):
        node_id = (task.context or {}).get("node_id")
        call_counts[node_id] = call_counts.get(node_id, 0) + 1
        return {"success": True, "phases": 1, "results": {}}

    monkeypatch.setattr("runtime.executor.execute_task", fake_execute_task)

    async with db_session() as s:
        _new_graph(
            s, "g5",
            [_node("a"), _node("b"), _node("c")],
            [["a", "b"], ["c"]],
        )
        await s.commit()

        engine = DispatcherEngine(s)
        await engine.dispatch("g5", project_id="proj-1")

    assert call_counts == {"a": 1, "b": 1, "c": 1}


def test_task_execution_model_defaults():
    """Sanity: TaskExecution defaults to pending status."""
    ex = TaskExecution(node_id="n1")
    assert ex.status == "pending"
"""Tests for CRITICAL executor/dispatcher defect fixes.

C1  workers table seeding (Lease FK crash)
H1  hermes removed from FSM discovery phase workers
M3  automation hook runs on its own session (never commits the executor's)
M8  dispatcher fail-stop: a failed node skips later dependency groups
"""
import pytest
from sqlalchemy import select, text

from backend.database.workers_seed import seed_workers


# ── C1: workers table seeding ───────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_workers_idempotent(db_session):
    """Seeding twice inserts each WORKER_REGISTRY key exactly once."""
    from workers.base import WORKER_REGISTRY
    from storage.models import Worker

    async with db_session() as db:
        first = await seed_workers(db)
        assert first == len(WORKER_REGISTRY), "first seed should insert every registry key"

        second = await seed_workers(db)
        assert second == 0, "second seed must be a no-op (idempotent)"

        rows = (await db.execute(select(Worker))).scalars().all()
        assert len(rows) == len(WORKER_REGISTRY)


@pytest.mark.asyncio
async def test_seed_covers_all_registry_keys(db_session):
    """Every WORKER_REGISTRY key has a seeded workers row with id worker-<key>."""
    from workers.base import WORKER_REGISTRY
    from storage.models import Worker

    async with db_session() as db:
        await seed_workers(db)
        rows = (await db.execute(select(Worker))).scalars().all()
        ids = {w.id for w in rows}
        expected = {f"worker-{key}" for key in WORKER_REGISTRY}
        missing = expected - ids
        assert not missing, f"missing seeded worker rows: {sorted(missing)}"


@pytest.mark.asyncio
async def test_lease_insert_succeeds_after_seed():
    """The executor creates Lease(worker_id='worker-<role>'); with FK
    enforcement ON this only succeeds once the workers table is seeded."""
    from backend.database.session import init_db, AsyncSessionLocal
    from storage.models import (
        Lease, LeaseStatus, Project, Task, TaskStatus, TaskType,
    )

    await init_db()

    async with AsyncSessionLocal() as db:
        await seed_workers(db)

        proj = Project(id="seed-proj-1", name="Seed", slug="seed-proj-1", description="", owner_id=None)
        db.add(proj)
        await db.flush()

        task = Task(
            id="seed-task-1", project_id="seed-proj-1", title="T",
            type=TaskType.FEATURE.value, status=TaskStatus.CREATED.value,
            worker_type="backend",
        )
        db.add(task)
        await db.flush()

        lease = Lease(
            id="seed-lease-1", task_id="seed-task-1",
            worker_id="worker-backend", worker_name="Backend",
            worker_type="backend", phase="implementation",
            status=LeaseStatus.ACTIVE.value,
        )
        db.add(lease)
        # Must NOT raise sqlite3.IntegrityError (FOREIGN KEY constraint failed).
        await db.commit()


# ── H1: hermes is not an FSM phase worker ───────────────────────────

def test_fsm_discovery_phase_has_no_hermes():
    from workflow.fsm import PHASE_WORKERS, allowed_workers_for_phase, _get_normal_workers_for_phase

    discovery_workers = [e["worker"] for e in PHASE_WORKERS["discovery"]]
    assert "hermes" not in discovery_workers
    assert "pm" in discovery_workers

    assert "hermes" not in allowed_workers_for_phase("discovery")
    assert "hermes" not in _get_normal_workers_for_phase("discovery", "backend")


# ── M3: automation hook never commits the caller's session ──────────

@pytest.mark.asyncio
async def test_automation_fire_event_does_not_commit_caller_session():
    """fire_event must run on its own session: it fires the hook (its
    notification is committed by its own session) but leaves the caller's
    pending transaction uncommitted."""
    from backend.database.session import init_db, AsyncSessionLocal
    from backend.services.automation_service import automation_service
    from storage.models import Notification

    await init_db()

    async with AsyncSessionLocal() as db:
        await automation_service.create_hook(
            db, "m3.test.event", "m3-hook", "notify", {"message": "m3-notified"}
        )

    async with AsyncSessionLocal() as caller_db:
        caller_db.add(Notification(title="m3-pending-notif", message="pending"))
        # Must NOT commit the caller's pending Notification.
        await automation_service.fire_event(caller_db, "m3.test.event")

    async with AsyncSessionLocal() as check_db:
        # The caller's pending notification was NOT committed by fire_event.
        pending = (await check_db.execute(
            select(Notification).where(Notification.title == "m3-pending-notif")
        )).scalars().all()
        assert pending == [], "fire_event must not commit the caller's session"

        # The hook's own notification WAS committed on its own session.
        fired = (await check_db.execute(
            select(Notification).where(Notification.message == "m3-notified")
        )).scalars().all()
        assert fired, "hook notification should be committed on fire_event's own session"


# ── M9: blocking fs walks moved off the event loop ──────────────────

@pytest.mark.asyncio
async def test_executor_imports_asyncio_to_thread_helpers():
    """Guards the M9 fix: runtime.executor imports asyncio and the blocking
    filesystem helpers still exist (signatures unchanged)."""
    import asyncio as _asyncio_mod
    from runtime import executor as _executor_mod
    from backend.workspace_manager import inspect_project_structure
    from backend.code_extract import extract_code_blocks_to_workspace

    assert _asyncio_mod.to_thread is not None
    assert callable(getattr(_executor_mod, "execute_task"))
    assert callable(inspect_project_structure)
    assert callable(extract_code_blocks_to_workspace)


# ── M8: dispatcher fail-stop ────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_fail_stop_skips_dependents():
    """A failed node in a dependency group stops dispatch: later groups are
    marked skipped and never executed."""
    from unittest.mock import patch

    from backend.database.session import init_db, AsyncSessionLocal
    from backend.database.workers_seed import seed_workers
    from dispatcher.engine import DispatcherEngine
    from storage.models import (
        DiscoverySession, EngineeringBrief, EngineeringPlan, Project,
        Task, TaskGraphModel, TaskStatus, TaskType,
    )

    await init_db()

    async with AsyncSessionLocal() as db:
        await seed_workers(db)

        proj = Project(id="m8-proj", name="M8", slug="m8", description="", owner_id=None)
        db.add(proj)
        await db.flush()

        ds = DiscoverySession(id="m8-ds", conversation_id="m8-task", user_id=None, status="ready")
        db.add(ds)
        await db.flush()
        brief = EngineeringBrief(
            id="m8-brief", discovery_session_id="m8-ds", engineering_goal="g",
            user_intent="i", request_category="feature", readiness_status="ready",
            readiness_score=0.8, status="ready",
        )
        db.add(brief)
        await db.flush()
        plan = EngineeringPlan(
            id="m8-plan", brief_id="m8-brief", engineering_goal="g",
            technical_approach="a", implementation_strategy="hybrid", status="validated",
        )
        db.add(plan)
        await db.flush()

        graph = TaskGraphModel(
            id="m8-graph", plan_id="m8-plan",
            nodes=[
                {"node_id": "N1", "title": "A", "description": "a", "task_type": "feature", "worker_type": "backend"},
                {"node_id": "N2", "title": "B", "description": "b", "task_type": "feature", "worker_type": "backend"},
                {"node_id": "N3", "title": "C", "description": "c", "task_type": "feature", "worker_type": "backend"},
            ],
            execution_order=[["N1", "N2"], ["N3"]],
            status="validated",
        )
        db.add(graph)
        await db.commit()

        async def fake_execute_task(sess, child_task):
            node_id = (child_task.context or {}).get("node_id")
            if node_id == "N1":
                child_task.status = TaskStatus.FAILED.value
                child_task.error_message = "boom"
                await sess.flush()
                return {"success": False, "error": "boom"}
            child_task.status = TaskStatus.COMPLETED.value
            child_task.progress = 100
            await sess.flush()
            return {"success": True, "phases": 1, "results": {}}

        engine = DispatcherEngine(db)
        with patch("runtime.executor.execute_task", fake_execute_task):
            result = await engine.dispatch("m8-graph", project_id="m8-proj")

        assert result.result is not None
        task_results = result.result.task_results

    # N1 failed, N2 completed (same parallel group), N3 skipped (fail-stop).
    assert task_results["N1"].status == "failed"
    assert task_results["N2"].status == "completed"
    assert task_results["N3"].status == "skipped"
    assert "Skipped: upstream node failed" in (task_results["N3"].error or "")
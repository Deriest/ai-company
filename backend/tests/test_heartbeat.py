"""Heartbeat scheduler unit tests — timezone normalization + stale-task/lease detection.

Covers the previously-untested ``backend/services/heartbeat.py`` logic:

* ``_as_utc`` normalizes naive/aware/None DB datetimes correctly.
* ``_check_stale_tasks`` returns tasks stuck longer than the configured hours
  threshold and skips fresh ones.
* ``_check_blocked_leases`` returns active leases older than the configured
  minutes threshold and skips recent ones.

All comparisons are naive-UTC (the way SQLite stores datetimes) so the tests are
deterministic regardless of the machine's local timezone.
"""
import pytest
from datetime import datetime, timezone, timedelta

from storage.models import Task, Lease, TaskStatus, LeaseStatus, TaskType
from backend.services.heartbeat import HeartbeatScheduler, _as_utc


def _naive(dt: datetime) -> datetime:
    """Drop tzinfo, mimicking how SQLite's DATETIME column stores values."""
    return dt.replace(tzinfo=None)


# ── _as_utc normalization ────────────────────────────────────────────────

def test_as_utc_naive_datetime_gains_utc_tz():
    naive = datetime(2024, 6, 1, 12, 0, 0)
    result = _as_utc(naive)
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc
    # Value unchanged, only tzinfo added.
    assert result.replace(tzinfo=None) == naive


def test_as_utc_aware_datetime_left_alone():
    aware = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = _as_utc(aware)
    assert result is aware
    assert result.tzinfo == timezone.utc


def test_as_utc_none_returns_none():
    assert _as_utc(None) is None


def test_as_utc_aware_non_utc_preserved():
    aware_plus = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    result = _as_utc(aware_plus)
    assert result is aware_plus
    assert result.utcoffset() == timedelta(hours=2)


# ── Stale task detection ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_stale_tasks_returns_tasks_past_threshold(db_session):
    now = datetime.now(timezone.utc)
    hb = HeartbeatScheduler()
    async with db_session() as s:
        old = Task(
            project_id="proj-1", title="old", type=TaskType.FEATURE.value,
            status=TaskStatus.IMPLEMENTATION.value,
            started_at=_naive(now - timedelta(hours=3)),
        )
        fresh = Task(
            project_id="proj-1", title="fresh", type=TaskType.FEATURE.value,
            status=TaskStatus.IMPLEMENTATION.value,
            started_at=_naive(now - timedelta(minutes=1)),
        )
        s.add_all([old, fresh])
        await s.commit()

        stale = await hb._check_stale_tasks(s)

    titles = {t["title"] for t in stale}
    assert any(t["title"] == "old" for t in stale)
    assert "fresh" not in titles
    # stale entry carries a positive stuck_hours value
    old_entry = next(t for t in stale if t["title"] == "old")
    assert old_entry["stuck_hours"] > 2.0


@pytest.mark.asyncio
async def test_check_stale_tasks_ignores_terminal_and_recent_tasks(db_session):
    now = datetime.now(timezone.utc)
    hb = HeartbeatScheduler()
    async with db_session() as s:
        completed_old = Task(
            project_id="proj-1", title="done-old", type=TaskType.FEATURE.value,
            status=TaskStatus.COMPLETED.value,
            started_at=_naive(now - timedelta(hours=10)),
        )
        recent_active = Task(
            project_id="proj-1", title="recent-active", type=TaskType.FEATURE.value,
            status=TaskStatus.INVESTIGATE.value,
            started_at=_naive(now - timedelta(minutes=5)),
        )
        s.add_all([completed_old, recent_active])
        await s.commit()

        stale = await hb._check_stale_tasks(s)

    assert stale == []


@pytest.mark.asyncio
async def test_check_stale_tasks_uses_naive_threshold_consistently(db_session):
    """A task exactly within the threshold is not stale; timezone math is naive-UTC."""
    now = datetime.now(timezone.utc)
    hb = HeartbeatScheduler()
    async with db_session() as s:
        # Just under the 2h threshold.
        boundary = Task(
            project_id="proj-1", title="boundary", type=TaskType.FEATURE.value,
            status=TaskStatus.VERIFICATION.value,
            started_at=_naive(now - timedelta(hours=1, minutes=59)),
        )
        s.add(boundary)
        await s.commit()
        stale = await hb._check_stale_tasks(s)
        assert stale == []


# ── Blocked lease detection ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_blocked_leases_returns_active_leases_past_threshold(db_session):
    now = datetime.now(timezone.utc)
    hb = HeartbeatScheduler()
    async with db_session() as s:
        blocked = Lease(
            task_id="T1", worker_id="w1", worker_name="WorkerA", worker_type="backend",
            phase="implementation", status=LeaseStatus.ACTIVE.value,
            created_at=_naive(now - timedelta(minutes=100)),
        )
        recent = Lease(
            task_id="T2", worker_id="w2", worker_name="WorkerB", worker_type="backend",
            phase="implementation", status=LeaseStatus.ACTIVE.value,
            created_at=_naive(now - timedelta(minutes=5)),
        )
        s.add_all([blocked, recent])
        await s.commit()

        result = await hb._check_blocked_leases(s)

    task_ids = {b["task_id"] for b in result}
    assert "T1" in task_ids
    assert "T2" not in task_ids
    blocked_entry = next(b for b in result if b["task_id"] == "T1")
    assert blocked_entry["active_minutes"] > 30.0


@pytest.mark.asyncio
async def test_check_blocked_leases_ignores_completed_and_recent(db_session):
    now = datetime.now(timezone.utc)
    hb = HeartbeatScheduler()
    async with db_session() as s:
        completed_old = Lease(
            task_id="T3", worker_id="w3", worker_name="WorkerC", worker_type="backend",
            phase="implementation", status=LeaseStatus.COMPLETED.value,
            created_at=_naive(now - timedelta(hours=5)),
        )
        s.add(completed_old)
        await s.commit()
        result = await hb._check_blocked_leases(s)
    assert result == []
"""SQLite write-lock retry tests.

Covers ``storage.lock_retry.commit_with_lock_retry`` and the executor wrapper
``runtime.executor._commit_with_lock_retry``:

* retries exactly when an ``OperationalError("database is locked")`` is raised
* backoff delay increases between attempts (base_delay * attempt)
* non-"locked" OperationalErrors re-raise immediately without retry
* the ``reapply`` closure is invoked after each rollback and re-established
* persistent failures stop after MAX attempts and re-raise
"""
import asyncio
import sqlite3

import pytest
from sqlalchemy.exc import OperationalError

from storage.lock_retry import commit_with_lock_retry
from runtime.executor import _commit_with_lock_retry


def _locked_err() -> OperationalError:
    return OperationalError("INSERT", {}, sqlite3.OperationalError("database is locked"))


def _other_err() -> OperationalError:
    return OperationalError("INSERT", {}, sqlite3.OperationalError("no such table: x"))


class FakeSession:
    """A stand-in AsyncSession whose commit() fails N times with a locked error."""

    def __init__(self, locked_failures: int, other_error: bool = False):
        self.locked_failures = locked_failures
        self.other_error = other_error
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self):
        self.commit_calls += 1
        if self.other_error:
            raise _other_err()
        if self.commit_calls <= self.locked_failures:
            raise _locked_err()

    async def rollback(self):
        self.rollback_calls += 1


class Recorder:
    """Records asyncio.sleep delays so we can assert backoff increases."""

    def __init__(self):
        self.delays = []

    async def sleep(self, delay):
        self.delays.append(delay)


@pytest.mark.asyncio
async def test_retries_on_locked_then_succeeds(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    session = FakeSession(locked_failures=2)
    reapplied = []

    async def reapply():
        reapplied.append(1)

    await commit_with_lock_retry(session, reapply=reapply, attempts=6, base_delay=0.05)

    # 2 failed commits + 1 final success = 3 commit calls.
    assert session.commit_calls == 3
    assert session.rollback_calls == 2
    assert len(reapplied) == 2


@pytest.mark.asyncio
async def test_backoff_delay_increases_between_attempts(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    session = FakeSession(locked_failures=3)

    await commit_with_lock_retry(session, attempts=6, base_delay=0.05)

    # Attempts 1..3 each sleep base_delay * attempt => 0.05, 0.10, 0.15.
    assert rec.delays == pytest.approx([0.05, 0.10, 0.15])
    # Strictly increasing.
    assert all(rec.delays[i] < rec.delays[i + 1] for i in range(len(rec.delays) - 1))


@pytest.mark.asyncio
async def test_non_locked_error_reraises_immediately(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    session = FakeSession(locked_failures=999, other_error=True)

    with pytest.raises(OperationalError):
        await commit_with_lock_retry(session, attempts=6, base_delay=0.05)

    # Only one commit attempted, no rollback, no backoff sleep.
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert rec.delays == []


@pytest.mark.asyncio
async def test_reapply_closure_runs_after_each_rollback(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    session = FakeSession(locked_failures=2)
    reapply_calls = []

    async def reapply():
        reapply_calls.append("reapply")

    await commit_with_lock_retry(session, reapply=reapply, attempts=6, base_delay=0.05)

    assert reapply_calls == ["reapply", "reapply"]


@pytest.mark.asyncio
async def test_max_attempts_reached_stops_and_reraises(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    # Always locked -> never succeeds.
    session = FakeSession(locked_failures=999)

    with pytest.raises(OperationalError):
        await commit_with_lock_retry(session, attempts=3, base_delay=0.05)

    assert session.commit_calls == 3
    assert session.rollback_calls == 2  # rolled back after attempts 1 and 2
    assert rec.delays == [0.05, 0.10]


@pytest.mark.asyncio
async def test_no_reapply_needed_is_optional(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(asyncio, "sleep", rec.sleep)
    session = FakeSession(locked_failures=1)

    await commit_with_lock_retry(session, attempts=6, base_delay=0.05)

    assert session.commit_calls == 2
    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_executor_wrapper_delegates_with_12_attempts(monkeypatch):
    """The executor's _commit_with_lock_retry delegates to the shared helper."""
    captured = []

    async def fake_commit(session, reapply=None, attempts=6, base_delay=0.05):
        captured.append((attempts, base_delay))
        return await commit_with_lock_retry(
            session, reapply=reapply, attempts=attempts, base_delay=base_delay
        )

    monkeypatch.setattr(
        "storage.lock_retry.commit_with_lock_retry", fake_commit
    )
    session = FakeSession(locked_failures=1)
    await _commit_with_lock_retry(session, attempts=12)

    assert captured == [(12, 0.05)]
    assert session.commit_calls == 2
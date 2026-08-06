"""Shared SQLite write-lock retry helper.

SQLite in WAL mode permits only ONE writer at a time. When parallel phase
workers (each with its OWN session, run via asyncio.gather) commit their
writes nearly simultaneously, a writer can block past busy_timeout and raise
"database is locked". This is a real, transient concurrency condition — the
correct fix is to retry the commit with a short backoff, NOT to serialize the
writers or swallow other errors.
"""
import asyncio

from sqlalchemy.exc import OperationalError


async def commit_with_lock_retry(
    session,
    reapply=None,
    attempts: int = 6,
    base_delay: float = 0.05,
) -> None:
    """Commit *session*, retrying on the transient SQLite "database is locked"
    OperationalError. Only the locked condition is retried and re-raised by
    type; any other error propagates immediately. Backoff is
    ``base_delay * attempt``.

    When a locked failure occurs during flush, SQLAlchemy rolls back the
    transaction and expunges the pending objects (e.g. Lease/Event), so a bare
    retry would commit an empty transaction and silently drop the writes.
    ``reapply`` — an optional async callable — is invoked after rollback to
    re-establish the pending objects before the next attempt.
    """
    for attempt in range(1, attempts + 1):
        try:
            await session.commit()
            return
        except OperationalError as exc:
            msg = str(exc.orig) if exc.orig is not None else str(exc)
            if "locked" not in msg.lower() or attempt == attempts:
                raise
            await session.rollback()
            if reapply is not None:
                await reapply()
            await asyncio.sleep(base_delay * attempt)
    # Defensive: loop always returns on success or raises; never reached.
    await session.commit()
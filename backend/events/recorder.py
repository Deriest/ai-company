"""AIC Platform — Persist events to the database via the Event model."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.exc import OperationalError

from storage.database import async_session
from storage.models import Event as EventModel

from events.bus import Event, bus

logger = logging.getLogger(__name__)


async def record(event: Event) -> None:
    """Insert an Event row. Errors are logged, never raised (bus stays alive).

    The recorder runs concurrently with the pipeline (the bus fan-out gathers
    handlers), so its insert can transiently contend with the SQLite single
    writer. Retry ONLY the "database is locked" OperationalError with a short
    backoff; any other error is logged and dropped.
    """
    from storage.database import get_session
    
    for attempt in range(1, 7):
        try:
            async with get_session(auto_commit=True) as session:
                session.add(
                    EventModel(
                        type=event.type,
                        data=event.data,
                        trace_id=event.trace_id,
                        actor=event.data.get("actor"),
                        target=event.data.get("target"),
                        severity=event.data.get("severity", "info"),
                    )
                )
                await session.commit()
            return
        except OperationalError as exc:
            msg = str(exc.orig) if exc.orig is not None else str(exc)
            if "locked" not in msg.lower():
                logger.exception(
                    "Failed to record event type=%s trace=%s", event.type, event.trace_id
                )
                return
            if attempt == 6:
                logger.warning(
                    "Failed to record event type=%s trace=%s after %d retries (write locked): %s",
                    event.type, event.trace_id, attempt, msg,
                )
                return
            await asyncio.sleep(0.05 * attempt)
        except Exception:
            logger.exception(
                "Failed to record event type=%s trace=%s", event.type, event.trace_id
            )
            return


async def subscribe_recorder() -> None:
    """Wire the recorder to the bus as a wildcard handler."""
    await bus.subscribe("*", record)

"""AIC Platform — Persist events to the database via the Event model."""
from __future__ import annotations

import logging

from storage.database import async_session
from storage.models import Event as EventModel

from events.bus import Event, bus

logger = logging.getLogger(__name__)


async def record(event: Event) -> None:
    """Insert an Event row. Errors are logged, never raised (bus stays alive)."""
    try:
        async with async_session() as session:
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
    except Exception:
        logger.exception("Failed to record event type=%s trace=%s", event.type, event.trace_id)


async def subscribe_recorder() -> None:
    """Wire the recorder to the bus as a wildcard handler."""
    await bus.subscribe("*", record)

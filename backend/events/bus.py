"""AIC Platform — Async event bus with pub/sub, wildcard, and history."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

Handler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """Async pub/sub bus.

    ponytail: single asyncio.Lock guards subscription mutation; fine for
    thousands of subscribers. Per-event-type locks if publish throughput
    matters under heavy concurrent publish.
    """

    def __init__(self, history_size: int = 100) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._lock = asyncio.Lock()
        self._history: deque[Event] = deque(maxlen=history_size)

    async def subscribe(self, event_type: str, handler: Handler) -> Callable[[], None]:
        """Register *handler* for *event_type* (or "*" for all). Returns unsubscribe."""
        async with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)
        # Replay history to new wildcard subscribers (best-effort snapshot).
        if event_type == "*":
            for ev in list(self._history):
                try:
                    await handler(ev)
                except Exception:
                    pass  # replay errors must not break subscribe
        unsubscribed = False

        def unsubscribe() -> None:
            nonlocal unsubscribed
            if unsubscribed:
                return
            unsubscribed = True
            # Schedule removal on the loop to avoid blocking sync callers.
            asyncio.ensure_future(self._remove(event_type, handler))

        return unsubscribe

    async def _remove(self, event_type: str, handler: Handler) -> None:
        async with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)
                if not handlers:
                    del self._handlers[event_type]

    async def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        trace_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> Event:
        """Publish an event; returns the constructed Event."""
        ev = Event(
            type=event_type,
            data=data or {},
            trace_id=trace_id,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self._history.append(ev)
        async with self._lock:
            targets = list(self._handlers.get(event_type, ())) + list(
                self._handlers.get("*", ())
            )
        # Fan out concurrently; errors in one handler don't kill others.
        if targets:
            results = await asyncio.gather(
                *(h(ev) for h in targets), return_exceptions=True
            )
            for r in results:
                if isinstance(r, Exception):
                    # Swallow handler errors — bus must stay alive.
                    pass
        return ev

    @property
    def history(self) -> list[Event]:
        return list(self._history)


# Singleton
bus = EventBus()

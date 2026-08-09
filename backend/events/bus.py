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

    P6: copy-on-write handler storage. subscribe/_remove replace the handler
    list object under a lock, while publish() snapshots the current list
    WITHOUT taking the lock (atomic on the single-threaded event loop). This
    removes publish-path serialization under heavy concurrent event emission.
    """

    def __init__(self, history_size: int = 100) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._lock = asyncio.Lock()
        self._history: deque[Event] = deque(maxlen=history_size)

    async def subscribe(self, event_type: str, handler: Handler) -> Callable[[], None]:
        """Register *handler* for *event_type* (or "*" for all). Returns unsubscribe."""
        async with self._lock:
            # P6: copy-on-write — replace the list so lock-free publishers
            # holding a reference to the old snapshot stay consistent.
            self._handlers[event_type] = list(self._handlers.get(event_type, ())) + [handler]
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
                # P6: copy-on-write — publish a new list without the handler.
                remaining = [h for h in handlers if h is not handler]
                if remaining:
                    self._handlers[event_type] = remaining
                else:
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
        # P6: lock-free snapshot — safe because subscribe/_remove swap the list
        # objects under the lock and there is no await inside this read.
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

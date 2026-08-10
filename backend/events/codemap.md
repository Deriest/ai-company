# Events Module - Technical Codemap

## 1. Responsibility

The `backend/events/` directory implements an **asynchronous event bus** with publish-subscribe (pub/sub) semantics for the AIC Platform. Its specific responsibilities include:

- **Event Coordination**: Provides a centralized, type-safe mechanism for decoupled communication between module boundaries using typed events with metadata (`type`, `data`, `trace_id`, `timestamp`).
- **Pub/Sub Pattern Implementation**: Implements wildcard subscription support (`"*"` pattern matches all events) with concurrent handler invocation via `asyncio.gather`.
- **Event History Buffering**: Maintains a bounded LIFO history (`deque` with configurable `maxlen`) enabling replay capability for new wildcard subscribers.
- **Fault Isolation**: Guarantees bus liveness by swallowing exceptions from individual handlers and providing retry logic for persistent storage operations.
- **Async Persistence Integration**: Coordinates event recording to the database layer via SQLAlchemy with SQLite lock contention handling.

---

## 2. Design Patterns

| Pattern | Location | Description |
|---------|----------|-------------|
| **Singleton** | `bus.py:108` | Global `bus = EventBus()` instance provides a single point of event coordination across the application. |
| **Observer (Pub/Sub)** | `bus.py:21-100` | `EventBus` maintains handler registries per event type; subscribers register callbacks that are invoked asynchronously upon event publication. |
| **Copy-on-Write** | `bus.py:37-40, 60-69` | Handler list updates perform defensive copying under `_lock`; publishers snapshot handler references without locking (P6 optimization for single-threaded asyncio loops). |
| **Circuit Breaker (Degradation)** | `recorder.py:17-58` | Storage failures degrade gracefully—logged and dropped rather than propagated, ensuring bus stability. |
| **Retry with Exponential Backoff** | `recorder.py:25-53` | Transient SQLite "database is locked" errors trigger up to 6 retries with backoff `0.05 * attempt` seconds. |
| **Command-Query Separation** | `bus.py:35-104` | Query operations (`history`, property accessor) are read-only; command operations (`subscribe`, `publish`) modify state or trigger effects. |

---

## 3. Data & Control Flow

### Event Lifecycle

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Producer  │────▶│  EventBus.publish│────▶│  EventBus       │
│             │     │                  │     │  _handlers      │
│  - type     │     │  1. Create Event │     │    [*]          │
│  - data     │     │  2. Append to    │     │    ["*"]        │
│  - trace_id │     │    _history      │     │    ["event.x"]  │
│  - timestamp│     │  3. Snapshot     │     │                 │
└─────────────┘     │    handler lists │     │                 │
                    │  4. gather(h(ev))│◀────┘                 │
                    └────────┬─────────┘                        │
                             ▼                                  │
              ┌──────────────────────────┐                      │
              │  Handlers (coroutines)   │                      │
              │  ┌────────────────────┐  │                      │
              │  │ Recorder.record()  │◀─┤                      │
              │  └────────┬───────────┘  │                      │
              │           ▼              │                      │
              │  async_session()         │                      │
              │           │              │                      │
              │           ▼              │                      │
              │  EventModel.insert()     │                      │
              │           │              │                      │
              │           ▼              │                      │
              │  SQLite Event table      │                      │
              └──────────────────────────┘                      │
                                                                 │
                          ┌──────────────────────────────────────┘
                          ▼
                ┌─────────────────────────┐
                │  Heartbeat services     │
                │  - stale_tasks handler  │
                │  - blocked_leases       │
                └─────────────────────────┘
```

### Entry Points

| Source | Module | Event Type Examples |
|--------|--------|---------------------|
| `backend/main.py` | Application bootstrap | `heartbeat.stale_tasks`, `heartbeat.blocked_leases` |
| `dispatcher/engine.py` | Task dispatch pipeline | `"task.completed"`, `"task.failed"` (inferred) |
| `backend/services/master_orchestrator.py` | Orchestrator workflows | Context-dependent task events |
| `backend/services/heartbeat.py` | Heartbeat monitoring loop | `"heartbeat.stale_tasks"`, `"heartbeat.blocked_leases"` |

### Exit Points (Handlers)

| Handler | File | Trigger Condition |
|---------|------|-------------------|
| `recorder.record()` | `events/recorder.py:17` | All events matching `"*"` wildcard |
| `_on_stale_tasks` | `backend/main.py:222` | Event type `"heartbeat.stale_tasks"` |
| `_on_blocked_leases` | `backend/main.py:223` | Event type `"heartbeat.blocked_leases"` |

### Internal Dependencies

```python
# recorder.py imports
from storage.database import async_session      # Session provider
from storage.models import Event as EventModel  # ORM entity

# bus.py imports
from collections import deque                    # Bounded history buffer
import asyncio                                   # Concurrency primitives
from datetime import datetime, timezone          # Timestamp generation
```

---

## 4. Integration Points

### Direct Import Dependencies

| Module | Import Statement | Purpose |
|--------|------------------|---------|
| `backend/main.py` | `from events.bus import bus`<br>`from events.recorder import subscribe_recorder` | Bootstrap subscriber registration and recorder wiring on app startup |
| `backend/services/master_orchestrator.py` | `from events.bus import bus` | Emit domain events during orchestration workflows |
| `backend/services/heartbeat.py` | `from events.bus import bus` | Publish heartbeat monitoring events for stale/blocked detection |
| `dispatcher/engine.py` | `from events.bus import bus` | Emit task lifecycle events from dispatcher pipeline |

### Schema-Level Integration

| Component | Dependency Direction | Description |
|-----------|---------------------|-------------|
| `storage.models.Event` | events → storage | `recorder.py` maps `Event` DTOs to SQLAlchemy `EventModel` entities |
| SQLite database | events → storage | Persistent event log keyed by `(type, trace_id, actor, target)` columns |

### Runtime Contract

- **Handler Signature**: `Handler = Callable[[Event], Awaitable[None]]` — synchronous return not awaited, must be `async def`.
- **Event Immutability**: `@dataclass(frozen=True, slots=True)` ensures event instances are immutable after construction.
- **Error Boundary**: Handlers may raise exceptions without propagating to callers; only logged internally via recorder's error path.
- **Concurrency Model**: Single-threaded asyncio loop; `asyncio.Lock` guards mutable state but copy-on-write avoids lock contention during `publish()`.

---

## 5. Code Structure

```
backend/events/
├── __init__.py         # Package marker (empty)
├── bus.py              # EventBus class + singleton bus instance
│   ├── Event           # Frozen dataclass: type, data, trace_id, timestamp
│   └── EventBus        # Core pub/sub implementation
│       ├── subscribe() # Registers handler, returns unsubscribe callable
│       ├── _remove()   # Async handler removal with copy-on-write
│       ├── publish()   # Creates Event, invokes all matching handlers concurrently
│       └── history     # Property: returns shallow copy of event history
└── recorder.py         # Event persistence layer
    ├── record()        # Retry-capable db insertion handler
    └── subscribe_recorder() # Wiring function: subscribes recorder to "*"
```

---

## 6. Performance Characteristics

| Operation | Complexity | Notes |
|-----------|------------|-------|
| `subscribe()` | O(n) | List copy + append; holds lock during update |
| `_remove()` | O(n) | Filter copy without handler |
| `publish()` | O(m × k) | m = total matching handlers; k = await time per handler; lock-free snapshot |
| `history` | O(h) | h = current history size; list conversion copies |
| `record()` | O(1..6) attempts | Worst-case 6 retries with backoff sum ≈ 0.975s latency |

---

## 7. Future Considerations

- No explicit event schema validation (`data: dict[str, Any]` untyped payload).
- Trace propagation exists (`trace_id`) but lacks correlation span tracking.
- Handler ordering is undefined due to `asyncio.gather` fan-out concurrency.
- No acknowledgment/retry mechanism for downstream consumers.

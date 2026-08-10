# Observability Module Codemap

**Location:** `/home/tvd/AI-Company/backend/observability/`

---

## 1. Responsibility

The `observability` module provides a comprehensive **observability infrastructure** for the AIC Platform, implementing the three pillars of modern system monitoring:

- **Structured Logging**: JSON-formatted log records with automatic trace ID propagation for distributed tracing across async task boundaries
- **Metrics Collection**: Time-series metric recording and aggregation via SQLite-backed storage for performance analytics
- **Audit Trail**: Immutable append-only audit logging of actor actions against resources for security/compliance
- **Diagnostics Service**: Real-time system health monitoring, resource utilization tracking, and performance anomaly detection

This module serves as the central telemetry layer that enables runtime observability, operational debugging, capacity planning, and security auditing across the entire platform.

---

## 2. Design Patterns

### 2.1 Singleton Pattern (Module-level)

```python
# metrics.py
metrics = MetricsRecorder()

# audit.py  
audit = AuditRecorder()

# diagnostics.py
_diagnostics = DiagnosticsService()

def get_diagnostics() -> DiagnosticsService:
    return _diagnostics
```

Module-level singleton instances provide global access to services without explicit dependency injection overhead.

### 2.2 Service Layer Pattern

Each `.py` file implements a dedicated service class with clear separation of concerns:

| File | Service Class | Responsibility |
|------|--------------|----------------|
| `logger.py` | `JsonFormatter`, `setup_logger` | Log formatting and configuration |
| `metrics.py` | `MetricsRecorder` | Metric persistence and query |
| `audit.py` | `AuditRecorder` | Audit trail recording and retrieval |
| `diagnostics.py` | `DiagnosticsService` | System health and performance diagnostics |

### 2.3 Context Var Pattern (Trace Propagation)

```python
# logger.py
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

def set_trace_id(trace_id: str) -> Token[str | None]:
    return trace_id_var.set(trace_id)
```

Uses Python's `contextvars.ContextVar` to propagate trace IDs across async task boundaries, enabling request-correlation in asynchronous workloads without thread-local state.

### 2.4 Idempotent Initialization Pattern

```python
# logger.py
_configured = False

def setup_logger(name: str) -> logging.Logger:
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if not _configured:
        # Configure handlers once...
        _configured = True
    return root.getChild(name)
```

Ensures repeated calls to initialization functions do not duplicate handlers or reconfigure existing resources.

### 2.5 Unit of Work Pattern (Transaction Management)

```python
# audit.py
async def record(self, ...) -> AuditLog:
    async with async_session() as session:
        entry = AuditLog(...)
        session.add(entry)
        
        async def _reapply():
            session.add(entry)  # Re-add on retry
        
        await commit_with_lock_retry(session, reapply=_reapply)
```

Implements SQLAlchemy's Unit of Work pattern with lock-retry semantics for concurrent safety.

### 2.6 Aggregate Query Pattern (Metrics Summary)

```python
# metrics.py
async def summary(self) -> dict:
    async with async_session() as session:
        for name in KEY_METRICS:
            stmt = select(
                func.count(Metric.id),
                func.avg(Metric.value),
            ).where(Metric.name == name)
            count, avg = (await session.execute(stmt)).one()
```

Batch aggregates key metrics using SQL aggregate functions (`COUNT`, `AVG`) in a single pass.

---

## 3. Data & Control Flow

### 3.1 Entry Points

| Source | Destination | Trigger |
|--------|-------------|---------|
| Application code → `set_trace_id()` | `logger.py::JsonFormatter` | Request/worker task start |
| Any module → `metrics.record()` | `metrics.py::MetricsRecorder` | Event occurrence (task created/completed, etc.) |
| Auth/Worker actions → `audit.record()` | `audit.py::AuditRecorder` | Actor-initiated operations |
| Scheduler/health check → `get_diagnostics()` | `diagnostics.py::DiagnosticsService` | Periodic system health polling |

### 3.2 Data Flow: Logging

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Application │────▶│  setup_logger() │────▶│  JsonFormatter   │
│   (any)      │     │  (once/config)  │     │                  │
└──────────────┘     └─────────────────┘     └──────────────────┘
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                       ▼
                   ┌───────────────┐                     ┌───────────────┐
                   │ stdout_handler│                     │file_handler   │
                   │ (uvicorn out) │                     │ (/tmp/aic-    │
                   │               │                     │ backend.log)  │
                   └───────────────┘                     └───────────────┘
```

**Trace ID Propagation Flow:**
```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│main.py       │────▶│ set_trace_id │────▶│ ContextVar.trace_ │
│ (request     │     │ (binds token)│     │ id_var            │
│  start)      │     │              │     │                   │
└──────────────┘     └──────────────┘     └───────────────────┘
                                                   │
                                                   ▼
                                            ┌───────────────────┐
                                            │JsonFormatter.format│
                                            │ (reads trace_id)   │
                                            └───────────────────┘
```

### 3.3 Data Flow: Metrics Recording

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────┐
│ event source │────▶│ MetricsRecorder │────▶│ async_session │
│ (task event) │     │ .record()       │     │               │
└──────────────┘     └─────────────────┘     └───────────────┘
                                           │
                                           ▼
                                    ┌───────────────────┐
                                    │ Metric model row  │
                                    │ (SQLAlchemy ORM)  │
                                    └───────────────────┘
                                           │
                                           ▼
                                    ┌───────────────────┐
                                    │ metrics table     │
                                    │ (SQLite DB)       │
                                    └───────────────────┘
```

### 3.4 Data Flow: Diagnostics

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────┐
│caller/monitor│────▶│ get_diagnostics│────▶│ psutil.Process│
│ periodic     │     │ .get_health()   │     │ .memory_info()│
└──────────────┘     └─────────────────┘     └───────────────┘
                                              │
                                              ▼
                                      ┌───────────────────┐
                                      │CPU %, memory MB   │
                                      │issues list        │
                                      └───────────────────┘
                                              │
                                              ▼
                                      ┌───────────────────┐
                                      │SystemHealth dataclass│
                                      └───────────────────┘
```

### 3.5 Exit Points

| Output Destination | Producer | Format |
|-------------------|----------|--------|
| STDOUT (uvicorn) | `logger.JsonFormatter` | JSON line |
| `/tmp/aic-backend.log` | `logger.FileHandler` | JSON line |
| `metrics` table | `MetricsRecorder.record()` | ORM row |
| `audit_logs` table | `AuditRecorder.record()` | ORM row |
| Memory (ephemeral) | `DiagnosticsService._metrics` | List[PerformanceMetric] |

---

## 4. Integration Points

### 4.1 Dependencies (Internal)

| Module | Dependency | Usage |
|--------|------------|-------|
| `metrics.py` | `storage.database.async_session` | Async DB sessions for metric queries |
| `metrics.py` | `storage.models.Metric` | ORM model for metric storage |
| `audit.py` | `storage.database.async_session` | Async DB sessions for audit queries |
| `audit.py` | `storage.models.AuditLog` | ORM model for audit storage |
| `audit.py` | `storage.lock_retry.commit_with_lock_retry` | Lock-aware transaction commits |
| `diagnostics.py` | `psutil` | Process/resource monitoring (external pkg) |

### 4.2 Consumer Modules

| Consumer | Import Path | Usage Pattern |
|----------|-------------|---------------|
| `backend/main.py` | `from observability.logger import setup_logger` | Initializes JSON logging at app startup |
| `backend/main.py` | `from observability.logger import set_trace_id, reset_trace_id` | Binds trace context per HTTP request/middleware |
| `tests/test_diagnostics.py` | `from observability.diagnostics import ...` | Unit/integration tests for health checks |

### 4.3 External Dependencies

| Package | Usage | Location |
|---------|-------|----------|
| `sqlalchemy` | ORM queries, async sessions | `metrics.py`, `audit.py` |
| `psutil` | CPU/memory process stats | `diagnostics.py` (lazy import) |
| `logging` (stdlib) | Base logger, handlers | `logger.py` |
| `contextvars` (stdlib) | Trace ID propagation | `logger.py` |
| `json` (stdlib) | Structured log serialization | `logger.py` |

### 4.4 Database Schema Contracts

The observability module relies on the following tables defined in `storage.models`:

**`audit_logs`** - Audit trail storage
```sql
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,           -- user:xxx, worker:xxx
    action TEXT NOT NULL,          -- delete_task, approve_phase, etc.
    resource_type TEXT,            -- task, project, milestone
    resource_id TEXT,              -- target resource UUID
    result TEXT NOT NULL,          -- success, denied, error
    details JSON DEFAULT {},       -- structured action metadata
    ip_address TEXT,               -- source IP (optional)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**`metrics`** - Time-series metric storage
```sql
CREATE TABLE metrics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,            -- e.g., "task.created", "worker.latency"
    value REAL NOT NULL,           -- numeric measurement
    unit TEXT,                     -- optional unit (ms, bytes, count)
    labels JSON DEFAULT {},        -- dimension labels {tier: "thinker"}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metrics_name (name),
    INDEX idx_metrics_created (created_at)
);
```

### 4.5 Key Metrics Tracked

The `KEY_METRICS` tuple defines the canonical metric names queried by dashboards:

```python
KEY_METRICS = (
    "task.created",          # Task creation rate
    "task.completed",        # Task completion rate
    "worker.execution_time", # Worker task duration (ms)
    "worker.failure_rate",   # Worker failure percentage
    "dispatcher.latency",    # Dispatcher scheduling latency
)
```

---

## 5. Code Quality Notes

| Aspect | Status | Notes |
|--------|--------|-------|
| Type hints | ✅ Full | `from __future__ import annotations` used throughout |
| Async/await | ✅ Consistent | All DB operations use async sessions |
| Error handling | ⚠️ Partial | Logger fallback uses bare `except Exception`; diagnostics silently catches psutil errors |
| Thread safety | ⚠️ Assumed | ContextVar works for asyncio; threaded callers require future migration to carrier-injected trace context |
| Logging level | ✅ Configured | DEBUG in dev, INFO in production (`__debug__` check) |
| Idempotency | ✅ Verified | `setup_logger` guards against duplicate handler attachment |

---

## 6. Known Limitations

1. **No structured log level filtering**: All levels (DEBUG–CRITICAL) write to the same stream; no runtime level adjustment post-initialization.
2. **In-memory metrics only**: `DiagnosticsService` retains last 1000 samples per metric name but does not persist to database.
3. **Single-file audit logs**: Audit records accumulate in a single SQLite table without partitioning or archival strategy.
4. **Trace ID manual binding**: Requires explicit `set_trace_id()` calls; no middleware wrapper auto-binds from request headers.
5. **psutil lazy import**: Diagnostic service imports `psutil` inside method, avoiding hard dependency but risking runtime import errors.

---

*Generated: Mon Aug 10 2026*

# AIC-ADE Worker System Architecture

## Worker Registry Pattern

### Registration Process

```python
# When worker starts
class WorkerPool:
    def register(self, worker_id: str, capabilities: list[str]):
        self.registry[worker_id] = {
            'capabilities': capabilities,
            'status': 'idle',
            'last_heartbeat': datetime.utcnow(),
            'task_count': 0,
            'memory_usage': 0
        }
```

**Capability Types:**
- `text_generation` — LLM-based task execution
- `code_execution` — Python/Node.js sandbox
- `file_operations` — Read/write/delete files
- `api_calls` — External HTTP/Webhook calls
- `data_processing` — Batch transformation tasks

---

## Worker Lifecycle Management

### Creation Sequence

1. **Dispatch receives task definition**
2. **Dispatcher analyzes requirements** → capability match
3. **Select available worker** (lowest load, best fit)
4. **Spawn worker process** with isolated context
5. **Inject dependencies** (DB connection, API keys, config)
6. **Transition to running state**

### Termination Patterns

| Trigger | Action | Cleanup Required |
|---------|--------|------------------|
| Task completed | Graceful shutdown | Save checkpoints, release resources |
| User cancel | Signal interrupt | Save partial results, log reason |
| Heartbeat timeout | Force kill | Terminate child processes, DB cleanup |
| Memory limit exceeded | OOM killer (system) | Emergency checkpoint, restart worker |
| Error threshold hit | Fallback to backup | Preserve error state for review |

---

## Worker Communication Protocol

### Request Format

```json
{
  "task_id": "uuid-v4",
  "type": "text_generation",
  "context": {
    "session_id": "ses_abc123",
    "conversation_history": [...],
    "system_prompt": "...",
    "constraints": {"max_tokens": 2000}
  },
  "priority": 1,
  "timeout_seconds": 300,
  "callback_url": "/api/v1/workers/{id}/result"
}
```

### Response Streaming

```python
class WorkerStream:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events = Queue()
    
    async def send_event(self, event_type: str, payload: dict):
        await self.events.put({
            "event": event_type,
            "timestamp": time.time(),
            "task_id": self.task_id,
            "payload": payload
        })
    
    async def stream_to_client(self, client_websocket):
        while True:
            event = await self.events.get()
            await client_websocket.send_json(event)
```

---

## Worker Pool Scaling Strategy

### Current Implementation (Static Pool)

- Fixed number of workers at startup
- No dynamic scaling based on load
- Resource allocation: hardcoded per worker

### Recommended Improvement (Dynamic Pool)

```python
class AdaptiveWorkerPool:
    def scale_workers(self, queue_depth: int, avg_latency: float):
        if queue_depth > THRESHOLD_HIGH and latency < LIMIT_OK:
            # Scale up
            spawn_worker()
        elif queue_depth < THRESHOLD_LOW and worker_idle_time > SLACK_TIME:
            # Scale down
            terminate_worker(least_recently_used)
```

**Scaling Triggers:**
- Queue depth > 100 items → +2 workers
- Average response time < 5s for 5 minutes → -1 worker
- Memory usage > 80% across pool → +1 worker

---

## Worker Health Monitoring

### Metrics Collected

| Metric | Source | Collection Interval | Alert Threshold |
|--------|--------|---------------------|-----------------|
| CPU Usage | `/proc/self/stat` (Linux) | 10s | > 90% sustained |
| Memory RSS | `/proc/self/status` | 10s | > 2GB |
| Task Success Rate | Event logger | Per task completion | < 95% over 1h |
| Latency P99 | Response timer | Per request | > 30s |
| Heartbeat Missed | Lease scanner | Every 1 min | > 3 misses |

### Health Check Endpoints

```http
GET /api/v1/workers/{id}/health
→ Returns: {"status": "healthy", "uptime": 3600, "tasks_completed": 42}

GET /api/v1/pool/stats
→ Returns: {"total": 10, "idle": 5, "running": 4, "failed": 1}
```

---

## Worker Isolation Model

### Containerization (Planned)

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir aic-worker-runtime
COPY ./app /app
WORKDIR /app
CMD ["python", "-m", "aic_worker.main"]
```

### Current Approach (Process Isolation)

- Separate OS process per worker
- No shared memory space
- Independent signal handling (SIGTERM/SIGKILL)
- IPC via message queues or REST callbacks

---

## Fault Tolerance Strategies

### Strategy 1: Task Retry

```python
@retry(exceptions=(WorkerError,), 
       attempts=3, 
       backoff_factor=2, 
       jitter=True)
def execute_task(task_def):
    worker = get_available_worker(task_def.type)
    return worker.execute(task_def)
```

### Strategy 2: Circuit Breaker

```python
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_requests=3
)

@circuit_breaker.call
def dispatch_to_worker(task):
    return dispatcher.assign(task)
```

### Strategy 3: Bulkhead Isolation

Separate worker pools by capability type:
- `pool_text_generation` — Dedicated to LLM tasks
- `pool_code_execution` — Dedicated to sandboxed code runs
- `pool_file_ops` — Dedicated to I/O operations

**Benefit:** Failure in one pool doesn't cascade to others.

---

## Worker Persistence

### State Storage Schema

```sql
CREATE TABLE worker_states (
    worker_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('idle', 'running', 'paused', 'completed', 'failed')),
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_task_id TEXT REFERENCES tasks(id),
    total_tasks_completed INTEGER DEFAULT 0,
    total_tasks_failed INTEGER DEFAULT 0,
    memory_snapshot JSONB,
    checkpoint_data BYTEA
);
```

### Checkpoint Mechanism

```python
class WorkerCheckpoint:
    def save(self, state: WorkerState):
        """Save worker state to persistent storage"""
        checkpoint = {
            'timestamp': datetime.utcnow().isoformat(),
            'worker_id': self.worker_id,
            'task_progress': self.current_progress,
            'partial_results': self.buffered_results,
            'context_snapshot': self.serialized_context
        }
        db.session.add(Checkpoint(worker_id=self.worker_id, data=checkpoint))
        db.session.commit()
```

---

*Worker architecture documented via:* runtime inspection, opencode logs, database schema analysis  
*Date: 2026-08-11 11:26 WIB*

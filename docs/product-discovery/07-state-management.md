# AIC-ADE State Management Flows

## State Types & Scope

### 1. Conversation State

**Purpose:** Track multi-turn dialogue context  
**Scope:** Per user session (ephemeral)  
**Storage:** Frontend `localStorage` + backend session table  

**Schema:**
```python
class ConversationState(Base):
    session_id = Column(UUID, primary_key=True)
    user_id = Column(UUID, nullable=False)
    messages = Column(JSONB)  # Array of {role, content, timestamp}
    context_stack = Column(JSONB)  # Active conversation context
    created_at = Column(TIMESTAMP, default=timezone.utcnow)
    updated_at = Column(TIMESTAMP, default=timezone.utcnow, onupdate=timezone.utcnow)
    is_active = Column(Boolean, default=True)
```

**Lifecycle:**
- Created: New chat starts → UUID generated
- Updated: Every message sent/received
- Archived: User closes chat or inactivity > 7 days
- Deleted: Permanent purge after 90 days (configurable)

---

### 2. Task/Worker State

**Purpose:** Track async execution progress  
**Scope:** Per task (persistent across restarts)  
**Storage:** SQLite database with lease records  

**Schema:**
```python
class TaskState(Base):
    task_id = Column(UUID, primary_key=True)
    worker_id = Column(UUID, ForeignKey('workers.id'))
    definition = Column(JSONB)  # Full task spec
    state = Column(String, default='created')  # created, running, paused, completed, failed
    progress_percent = Column(Integer, default=0)
    result = Column(JSONB)  # Final output if completed
    error_message = Column(Text)  # If failed
    checkpoints = Column(JSONB)  # Intermediate snapshots
    created_at = Column(TIMESTAMP),
    started_at = Column(TIMESTAMP),
    completed_at = Column(TIMESTAMP),
    lease_heartbeat = Column(TIMESTAMP, onupdate=timezone.utcnow)  # Migration 024
```

**State Transitions:**
```
created → running → [paused | resumed] → completed/failed
              ↓
            cancelled
```

---

### 3. Project/Mission State

**Purpose:** Group multiple related tasks into project  
**Scope:** Per workspace/project (persistent)  
**Storage:** Backend `projects` table  

**Schema:**
```python
class MissionState(Base):
    mission_id = Column(UUID, primary_key=True)
    workspace_id = Column(UUID, ForeignKey('workspaces.id'))
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default='draft')  # draft, active, archived
    parent_tasks = Column(JSONB)  # List of child task IDs
    metadata = Column(JSONB)  # Custom tags, priorities, deadlines
    created_by = Column(UUID, ForeignKey('users.id'))
    created_at = Column(TIMESTAMP),
    updated_at = Column(TIMESTAMP)
```

**Dependencies:** Tasks reference this via `parent_mission_id` for hierarchical tracking.

---

### 4. System Health State

**Purpose:** Monitor overall platform health  
**Scope:** Global (aggregated from all workers + services)  
**Storage:** In-memory metrics cache + time-series DB (optional)  

**Metrics Tracked:**
- Worker pool utilization (% busy / total capacity)
- Average response latency (P50, P95, P99)
- Error rate by component (ChatService, Provider, etc.)
- Lease heartbeat health (workers without recent heartbeats)
- Database connection pool status

**Update Frequency:** Every 10 seconds (polling) or event-driven (push)

---

## State Synchronization Patterns

### Pattern 1: Optimistic UI Updates

```typescript
// Frontend sends message, optimistically updates chat view
const [messages, setMessages] = useState<Message[]>([]);

async function sendMessage(text: string) {
  // Update UI immediately
  const newMsg = { id: uuid(), text, role: 'user', timestamp: now() };
  setMessages(prev => [...prev, newMsg]);
  
  // Send to backend
  const response = await api.post('/chat/execute', { prompt: text });
  
  // Update with server response
  setMessages(prev => [...prev, { ...response.message, role: 'assistant' }]);
}
```

**Benefit:** Subtractive latency for perceived responsiveness  
**Risk:** Need rollback on failure (show error UI instead of success state)

---

### Pattern 2: Eventual Consistency via Events

```python
# Backend publishes events when state changes
@listener.on("task_state_updated")
def update_live_dashboard(task_id: str, new_state: TaskState):
    websocket.broadcast_to_channel(
        channel=f"live:tasks:{task_id}",
        payload={ "event": "progress", "state": new_state }
    )
```

**Frontend subscribes:**
```typescript
websocket.subscribe('live:tasks:*', (payload) => {
  updateTaskProgress(payload.task_id, payload.progress_percent);
});
```

---

### Pattern 3: Two-Way Binding for Settings

```typescript
// Sync local config with backend settings
const [config, setConfig] = useState(appConfig);

async function saveConfig(newConfig: AppConfig) {
  await api.put('/settings', newConfig);
  setConfig(newConfig); // Optimize update
}

// Listen for remote config changes (multi-device sync)
useEffect(() => {
  const ws = createWebSocket('/ws/settings');
  ws.onmessage = (ev) => {
    const remoteConfig = JSON.parse(ev.data);
    setConfig(remoteConfig);
  };
}, []);
```

---

## State Transition Guards

### Guard 1: Permission Validation

Before any state transition, check if user has permission:
```python
def can_transition(from_state: str, to_state: str, user: User) -> bool:
    rules = {
        ('created', 'running'): True,
        ('running', 'paused'): user.can_pause,
        ('paused', 'running'): user.can_resume,
        ('running', 'completed'): True,
        ('running', 'failed'): False,  # Must be error, not manual
    }
    return rules.get((from_state, to_state), False)
```

---

### Guard 2: Business Rule Enforcement

```python
def validate_task_completion(task: TaskState) -> None:
    if task.progress_percent < 100:
        raise ValueError("Cannot mark as complete before 100% progress")
    
    if task.checkpoints is None or len(task.checkpoints) == 0:
        raise ValueError("At least one checkpoint required for audit trail")
    
    # Verify all child tasks completed first
    if task.parent_tasks:
        child_states = db.query(TaskState).filter(
            TaskState.id.in_(task.parent_tasks)
        ).all()
        if any(cs.state != 'completed' for cs in child_states):
            raise ValueError("All child tasks must be completed first")
```

---

### Guard 3: Concurrency Control (Optimistic Locking)

```python
class OptimisticUpdate:
    def __init__(self, current_version: int, new_version: int):
        self.current_version = current_version
        self.new_version = new_version
    
    def apply(self, state: Base):
        if state.version != self.current_version:
            raise ConflictError("State modified by another process")
        
        state.version = self.new_version
        state.updated_at = timezone.utcnow()
        db.session.commit()
```

---

## State Recovery Strategies

### Strategy 1: Last Known Good Checkpoint

On startup or crash recovery:
```python
def recover_worker_state(worker_id: str) -> Optional[WorkerState]:
    latest_checkpoint = db.query(Checkpoint)\
        .filter(Checkpoint.worker_id == worker_id)\
        .order_by(Checkpoint.timestamp.desc())\
        .first()
    
    if latest_checkpoint:
        return deserialize(latest_checkpoint.data)
    else:
        return WorkerState.default_for_failure(worker_id)
```

---

### Strategy 2: Event Replay

For complex workflows, replay events from event log:
```python
def replay_events(event_store: EventStore, up_to: datetime) -> StateSnapshot:
    events = event_store.fetch_before(up_to)
    state = InitialState()
    for event in events:
        state = event.apply(state)
    return state
```

**Use case:** Debugging long-running task failures, reproducing edge cases.

---

## State Cleanup Policies

### Policy 1: Automatic Archival

```python
@cronjob.every("daily 02:00")
def archive_old_sessions():
    cutoff_date = timezone.utcnow() - timedelta(days=30)
    inactive_sessions = db.query(ConversationState)\
        .filter(
            ConversationState.is_active == False,
            ConversationState.updated_at < cutoff_date
        )\
        .all()
    
    for session in inactive_sessions:
        session.is_archived = True
        session.archived_at = timezone.utcnow()
    
    db.session.commit()
```

---

### Policy 2: Garbage Collection

Remove orphaned states (no longer referenced):
```python
def gc_orphaned_checkpoints():
    """Delete checkpoints older than retention period with no associated tasks"""
    cutoff = timezone.utcnow() - timedelta(days=7)
    orphaned = db.query(Checkpoint)\
        .outerjoin(TaskState, Checkpoint.task_id == TaskState.id)\
        .filter(
            Checkpoint.timestamp < cutoff,
            TaskState.id.is_(None)  # No parent task exists
        )\
        .delete(synchronize_session=False)
    
    print(f"Deleted {orphaned} orphaned checkpoints")
```

---

*State management patterns documented via:* database schema inspection, source code review, runtime logs  
*Date: 2026-08-11 11:27 WIB*

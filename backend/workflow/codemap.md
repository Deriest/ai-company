# Workflow Module Codemap

**Module**: `backend/workflow/`  
**Purpose**: Orchestrates AI agent task lifecycle through a state-machine-driven execution pipeline

---

## 1. Responsibility

The `workflow` module provides **task lifecycle management** for the AIC Platform using a deterministic finite-state machine (FSM) architecture. Its specific responsibilities include:

### Core Functions

| Component | Responsibility | Design Pattern |
|-----------|----------------|----------------|
| **Engine** (`engine.py`) | Manages state transitions, barrier enforcement, PM review gates, and phase progression | **State Machine**, **Repository** |
| **FSM** (`fsm.py`) | Defines valid phase transitions, worker assignments per phase, barrier logic | **Finite State Machine**, **Strategy** |
| **Triage** (`triage.py`) | Classifies incoming tasks by intent, scope, risk level; enforces safety guardrails | **Pipeline**, **Rule Engine** |
| **Decomposition** (`decomposition.py`) | Splits parent tasks into subtasks based on architect output; manages dependencies | **Chain of Responsibility**, **Dependency Resolver** |

### Architectural Role

- **Gatekeeper**: Enforces code-driven workflow rules rather than prompt-based decisions
- **Coordinator**: Orchestrates multi-phase execution across specialized AI agents (workers)
- **Validator**: Applies barrier patterns to ensure all required workers complete before phase advance

---

## 2. Design Patterns

### Identified Patterns

#### 2.1 Finite State Machine (FSM)
**Location**: `fsm.py` - PHASE_ORDER, TERMINAL_STATES, can_advance(), next_phase()

```python
PHASE_ORDER = [
    "created", "discovery", "investigate", "planning",
    "implementation", "verification", "closeout", "completed"
]
TERMINAL_STATES = frozenset(["completed", "cancelled", "blocked"])
```

**Characteristics**:
- Linear progression through execution phases
- Fail-closed barriers (timeout does NOT auto-satisfy)
- Terminal state protection (no transitions from completed/cancelled/blocked)
- Hardcoded transition rules in code, not prompts

#### 2.2 Barrier Pattern (Synchronization Primitive)
**Location**: `fsm.py` - Barrier dataclass

```python
@dataclass
class Barrier:
    active: bool = True
    workers: list[str]
    completed: dict[str, str]  # worker -> "complete"
    failed: dict[str, str]     # worker -> reason
    started_at: float = 0.0
    timeout: int = 600
    timed_out: bool = False
```

**Behavior**:
- Tracks completion status of assigned workers within a phase
- **Fail-closed**: Timeout deactivates barrier without auto-completion
- Supports retry via `reset_for_repair()` after rework
- Persists state in WorkflowState database record

#### 2.3 Guardrail Rule Engine
**Location**: `triage.py` - GUARDRAIL_PATTERNS dict

```python
GUARDRAIL_PATTERNS = {
    "security": {
        "pattern": r"\b(auth|password|jwt|token|secret|...)\b",
        "min_level": ExecutionLevel.EXTENDED,
        "required_worker": "security",
    },
    ...
}
```

**Execution Flow**:
1. Keyword detection via regex matching
2. Automatic escalation of minimum execution level
3. Enforced worker injection (e.g., security specialist)
4. Phase skip un-skip logic for guarded workers

#### 2.4 Strategy Pattern (Worker Selection)
**Location**: `fsm.py` - allowed_workers_for_phase()

```python
def allowed_workers_for_phase(
    phase: str,
    target_worker: str | None = None,
    task_type: str | None = None,
    selected_workers: list[str] | None = None,
) -> list[str]:
```

**Dynamic Dispatch**:
- Returns different worker sets based on:
  - Target technology stack (frontend/backend/database)
  - Task type from triage selected_workers
  - Phase requirements
- **BUG-12 FIX**: Merges guardrail-enforced workers with normal phase workers instead of replacing

#### 2.5 Factory Pattern (Task Decomposition)
**Location**: `decomposition.py` - parse_decomposition(), specs_from_plan_data()

**Multiple Input Formats**:
- JSON arrays → SubtaskSpec[]
- Markdown sections (## Subtask N: Title) → SubtaskSpec[]
- Structured EngineeringPlan → effort_estimates-based subtasks

**Fallback Chain**:
1. Try parsing architect_output as structured formats
2. If ≤1 spec produced, fall back to plan_data
3. If still insufficient, treat as single-task execution

---

## 3. Data & Control Flow

### 3.1 Entry Points

| Entry Point | Trigger | Parameters | Source |
|-------------|---------|------------|--------|
| `perform_smart_triage()` | Task creation request | text, task_type, worker_hint, file_count_estimate | API routes / chat/execute |
| `WorkflowEngine.advance()` | Manual or automatic phase transition | task, barrier_complete, pm_review_passed, approval_passed | Executor callbacks |
| `decompose_task()` | After architect planning phase | session, parent_task, architect_output, plan_data | Planning stage controller |

### 3.2 Data Flow Diagram

```
┌─────────────┐
│  User Request│
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│         Triage Engine                │
│  • Regex guardrail scanning          │
│  • Level calculation (QUICK/FULL)   │
│  • Worker selection                  │
└──────┬───────────────────────────────┘
       │
       │ TriageResult{level, selected_workers, skip_phases}
       ▼
┌──────────────────────────────────────┐
│       Task Creation                  │
│  • Set initial status: created       │
│  • Persist context + worker hints   │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│      Workflow Engine                 │
│  • get_or_create_state()            │
│  • Validate transition              │
│  • Barrier initialization           │
└──────┬───────────────────────────────┘
       │
       │ current_phase, barrier
       ▼
┌──────────────────────────────────────┐
│        FSM Validation                │
│  • normalize_phase()                │
│  • is_terminal()                    │
│  • can_advance()                    │
│  • validate_worker_for_phase()     │
└──────┬───────────────────────────────┘
       │
       │ Valid? Yes / No
       ├─────────┬─────────┐
       │         │         │
       ▼         ▼         ▼
┌─────────────┐ ┌──────────┐ ┌────────────┐
│ Advance     │ │ Block    │ │ Cancel     │
│ Next phase  │ │ Error    │ │ With reason│
└──────┬──────┘ └──────────┘ └────────────┘
       │
       │ progress%, history
       ▼
┌──────────────────────────────────────┐
│  Database Persistence                │
│  • Task.status = nxt                 │
│  • WorkflowState.history append     │
│  • Barrier dict update              │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  WebSocket Broadcast                 │
│  • "phase.advanced" event           │
│  • previous_phase, current_phase    │
└──────────────────────────────────────┘
```

### 3.3 State Transition Rules

**Linear Progression** (PHASE_ORDER):
```
created → discovery → investigate → planning → implementation → verification → closeout → completed
```

**Terminal States** (No Exit Allowed):
- `completed` – Successful closure after PM review
- `cancelled` – Explicit cancellation with reason
- `blocked` – Failure due to error condition

**Phase-Specific Requirements**:

| Phase | Barrier Workers | Approval Required | PM Review Required |
|-------|-----------------|-------------------|---------------------|
| discovery | pm | No | No |
| investigate | pm, research | No | No |
| planning | architect, designer, database, nexus, flint, security | **Yes** | No |
| implementation | backend, frontend | No | No |
| verification | qa, performance, security | No | No |
| closeout | rex, documentation, pm | No | **Yes** |

### 3.4 Barrier Lifecycle

```
Start Phase → Create Barrier (active=True, workers=[...])
                              │
                              ├→ Worker Complete → mark_complete(worker)
                              │                    completed[worker] = "complete"
                              │
                              ├→ Worker Failed → mark_failed(worker, reason)
                              │                    failed[worker] = reason
                              │
                              └→ Timeout Check → is_satisfied()
                                         │
                                         ├→ All workers done → returns True
                                         │
                                         └→ Exceeded 600s → active=False, timed_out=True
```

### 3.5 Subtask Dependency Resolution

**Creation Flow**:
```
parse_decomposition(architect_output)
    ↓
SubtaskSpec[{title, worker_type, depends_on, order}]
    ↓
For each spec:
  1. Create Task row with parent_task_id
  2. Inherit context keys: conversation_id, workspace, repo_path, project_slug
  3. Map title → ID in title_to_id dict
  4. Resolve depends_on references to actual subtask IDs
  5. Set depends_on array on Task.row
    ↓
Commit transaction + emit TASK_CREATED event
```

**Ready-State Query** (get_ready_subtasks()):
```sql
SELECT * FROM task
WHERE parent_task_id = $1
ORDER BY subtask_order

For each subtask:
  IF status != CREATED: SKIP
  IF depends_on IS EMPTY: READY
  FOR EACH dep_id IN depends_on:
    IF dep.status != COMPLETED: NOT_READY (break)
  IF ALL DEPS COMPLETED: READY
```

---

## 4. Integration Points

### 4.1 Dependencies

#### External Packages

| Package | Version | Purpose | Import Location |
|---------|---------|---------|-----------------|
| `sqlalchemy` | async | Database sessions, queries | `from sqlalchemy import select`, `AsyncSession` |
| `dataclasses` | stdlib | Barrier data model | `from dataclasses import dataclass, field` |
| `logging` | stdlib | Event logging | `import logging` |

#### Internal Modules

| Module | Dependency Type | Import Path | Used For |
|--------|-----------------|-------------|----------|
| `storage.models` | Schema reference | `from storage.models import Task, WorkflowState, TaskStatus, ApprovalStatus, Event, EventType` | ORM models, enums |
| `backend.routes.websocket` | Event broadcast | `from backend.routes.websocket import broadcast_task_event` | WebSocket push notifications |
| `backend.services.content_utils` | Content parsing | `from backend.services.content_utils import content_to_text` | Text normalization for triage |

### 4.2 Consumer Modules

| Consumer | Interaction Method | Trigger Event |
|----------|--------------------|---------------|
| **API Routes** (`/api/tasks/create`) | Calls `perform_smart_triage()` | Task creation request |
| **Planning Stage Controller** | Calls `decompose_task()` | After architect generates plan |
| **Executor Backend** | Calls `WorkflowEngine.advance()`, `mark_worker_complete()` | Worker execution callback |
| **Frontend Dashboard** | Subscribes to `"phase.advanced"` WS event | UI state sync |
| **WebSocket Gateway** | Publishes phase events | `broadcast_task_event("phase.advanced", ...)` |

### 4.3 Contract Specifications

#### TriageResult Interface (Output of `perform_smart_triage()`)

```python
@dataclass
class TriageResult:
    level: ExecutionLevel        # QUICK/STANDARD/EXTENDED/FULL
    scope: str                   # localized/bounded/cross_component/architecture_system
    risk: str                    # low/medium/high/critical
    confidence: float            # 0.85-0.95
    reason: str                  # Human-readable classification rationale
    guardrails_triggered: list[str]  # Applied safety rules
    selected_workers: list[str]    # Enforced + heuristic workers
    required_verification: list[str] # Verification steps needed
    skip_phases: dict[str, str]     # Phase → skip reason map
```

#### Barrier Interface (Persistence Schema)

```python
@dataclass
class Barrier:
    active: bool               # Is this barrier currently enforceable?
    workers: list[str]         # All workers required for phase completion
    completed: dict[str, str]  # Worker → completion timestamp/status
    failed: dict[str, str]     # Worker → failure reason
    started_at: float          # Unix epoch seconds when phase started
    timeout: int = 600         # Maximum phase duration (10 minutes)
    timed_out: bool            # Has timeout occurred?
```

### 4.4 Database Schema Integration

**Tables Affected**:

| Table | Columns Modified | Write Operation |
|-------|------------------|-----------------|
| `task` | `status`, `progress`, `error_message`, `completed_at` | `advance()`, `cancel()`, `fail()`, `block()` |
| `workflow_state` | `current_phase`, `previous_phase`, `barrier`, `history`, `pm_review_passed` | All engine methods |
| `event` | New row insertion | `decompose_task()` emits TASK_CREATED event |

**Relationships**:
```
Task (parent_task_id) ←→ Task (subtask)        # Hierarchical decomposition
Task.id ──→ WorkflowState.task_id              # One-to-one lifecycle state
```

### 4.5 Worker Registry Mapping

**Phase-to-Worker Assignment** (from `PHASE_WORKERS` in `fsm.py`):

| Phase | Assigned Workers | Tier Classification |
|-------|------------------|---------------------|
| discovery | pm | thinker |
| investigate | pm, research | thinker |
| planning | architect, designer, database, nexus, flint, security | thinker+crafter mix |
| implementation | backend, frontend | crafter |
| verification | qa, performance, security | sprinter+thinker |
| closeout | rex, documentation, pm | sprinter+thinker |

---

## Technical Debt & Notes

### Known Issues

1. **BUG-12 Fix**: Previously guardrail workers REPLACED normal workers during `selected_workers` merge; now properly MERGES to prevent architect/database omission.

2. **Hermes Stub Routing**: Hermes intentionally excluded from phase workers (discovery phase) — real clarification routed through `/chat/execute` instead of standalone execute().

3. **Bughunt Audit Team**: Special read-only team [research, security, qa] for investigation + evidence gathering without implementation.

### Environment Constraints

- **Greenlet Avoidance**: Uses explicit SELECT queries instead of lazy relationships in `get_or_create_state()` to prevent async greenlet issues.
- **Silent Broadcast Failures**: WebSocket errors swallowed via try/except to prevent workflow interruption on network failures.

### Evolution History

Derived from `aic-skill` reference architecture with hardening additions:
- Strict phase validation vs. free-form prompting
- Fail-closed barrier semantics (timeout ≠ auto-complete)
- PM review gate at closeout phase
- Terminal state immutability

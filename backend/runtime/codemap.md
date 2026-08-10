# Runtime Module — Unified Adaptive Execution Engine (v2.3.8)

## Overview

The **Runtime** module implements the AIC Platform's unified execution engine with smart triage, adaptive policies, and fault-tolerant task processing. It orchestrates multi-phase worker lifecycles through a state-machine-based FSM (Finite State Machine), dynamically adjusting execution depth based on Smart Triage classification (L1-QUICK through L4-FULL).

---

## Responsibility

**Primary Role**: Centralized Task Execution Orchestration Engine with Adaptive Policy Management

**Specific Responsibilities**:

### `adaptive.py` - Policy Management Subsystem
1. **Capability Discovery**: Normalize vendor-neutral provider metadata into typed `ModelCapabilities` profiles
2. **Adaptive Policy Generation**: Derive context/memory/worker policies from capabilities using conservative defaults
3. **Profile Registry**: Maintain in-process source-of-truth for detected model profiles via `AdaptiveRuntimeRegistry`
4. **Policy Application**: Attach immutable runtime policies to task contexts without mutating caller state
5. **Directive Emission**: Generate human-readable worker directives for prompt engineering

### `executor.py` - Execution Orchestration Subsystem
1. **FSM Phase Orchestration**: Execute tasks through phases (discovery → planning → implementation → verification → closeout) adaptively based on execution level
2. **Smart Triage Integration**: Classify tasks into L1-L4 execution tiers with corresponding phase skipping logic
3. **Parallel Worker Scheduling**: Concurrently execute multiple workers per phase with isolated database sessions
4. **Progressive Recovery Ladder**: Implement 4-attempt retry strategy with exponential backoff and fallback handling
5. **Local Repair Loop**: Retry failed verification with targeted repair before escalating to higher execution levels
6. **Integrity Verification**: Enforce completion rules (no COMPLETED status with verification failures or fallback usage)
7. **Event Streaming**: Broadcast real-time events via WebSocket and trigger automation hooks
8. **Database Lock Management**: Handle SQLite WAL concurrency with retry-on-lock-backoff semantics

**Design Intent**: Provide reliable, self-healing task execution with graceful degradation paths while maintaining auditability through event logging and progress tracking.

---

## Architecture

### Component Structure

| File | Purpose | Public API |
|------|---------|------------|
| `__init__.py` | Package initialization (empty; namespace package) | - |
| `adaptive.py` | Adaptive policy management and capability profiling | `capabilities_from_metadata()`, `generate_runtime_profile()`, `AdaptiveRuntimeRegistry`, `apply_worker_policy()`, `runtime_prompt_directive()` |
| `executor.py` | Core task execution engine | `_commit_with_lock_retry()`, `_emit_event()`, `_adaptive_worker_timeout()`, `execute_task()` |

### Key Data Classes (`adaptive.py`)

| Class | Purpose | Immutable? |
|-------|---------|------------|
| `ContextClass` | Enum: SMALL/MEDIUM/LARGE based on context window size | Yes (str+Enum) |
| `MemoryMode` | Enum: Session-only through hybrid memory strategies | Yes (str+Enum) |
| `ModelCapabilities` | Normalized capability profile from provider metadata | Yes (frozen dataclass) |
| `ContextPolicy` | Context management policy (history limits, budgets, summarization) | Yes (frozen dataclass) |
| `MemoryPolicy` | Memory retrieval strategy configuration | Yes (frozen dataclass) |
| `WorkerPolicy` | Worker behavior policy (planning depth, parallelism, checkpointing) | Yes (frozen dataclass) |
| `AdaptiveRuntimeProfile` | Complete runtime profile bundling capabilities + all policies | Yes (frozen dataclass) |

---

## Design Patterns

### 1. Strategy Pattern (`adaptive.py::generate_runtime_profile`)
Dynamic policy selection based on capability thresholds:
```python
if cap.embeddings is True and context_class == ContextClass.LARGE:
    memory_mode = MemoryMode.HYBRID
elif cap.embeddings is True:
    memory_mode = MemoryMode.SEMANTIC
else:
    # ... cascading fallback to SESSION_ONLY
```

**Strategy Mapping**:
- **Context Windows**: 
  - `≥100k tokens` → LARGE context policy (minimal summarization, retrieval_first=False)
  - `≥32k tokens` → MEDIUM context policy (periodic summarization, retrieval_first=True)
  - `<32k tokens` → SMALL context policy (aggressive summarization, batch_size=1)
  
- **Memory Modes**: HYBRID (embeddings+repository), SEMANTIC (vector-only), CHECKPOINT, REPOSITORY, SESSION_ONLY

- **Worker Planning Depths**: incremental (SMALL) → structured (MEDIUM) → deep (LARGE)

### 2. Repository Pattern / Registry (`adaptive.py::AdaptiveRuntimeRegistry`)
In-memory registry for cached capability profiles:
```python
class AdaptiveRuntimeRegistry:
    def register(self, capabilities: ModelCapabilities) -> AdaptiveRuntimeProfile
    def get(self, provider: str, model: str) -> AdaptiveRuntimeProfile | None
    def active(self) -> AdaptiveRuntimeProfile | None
    def all(self) -> list[dict[str, Any]]
```

Usage as singleton via module-level `adaptive_runtime` instance provides lazy registration and quick lookup by (provider, model) key.

### 3. Factory Pattern (`adaptive.py::capabilities_from_metadata`)
Vendor-normalizing factory that accepts arbitrary metadata mappings and produces typed `ModelCapabilities`:
- Handles aliased field names (`tool_calling`, `supports_tools`, `supports_tool_calling`)
- Type coercion helpers (`_positive_int()`, `_optional_bool()`)
- Conservative defaults when fields absent

### 4. Template Method Pattern (`executor.py::execute_task`)
Standardized FSM execution pipeline:
```
while not is_terminal(phase):
    ├─ Check adaptive phase skip (from triage)
    ├─ Resolve allowed workers for phase
    ├─ Commit main session (release SQLite lock)
    ├─ Launch parallel workers (isolated sessions)
    ├─ Merge results deterministically
    ├─ Local repair loop if verification failed
    ├─ Dynamic escalation if repair exhausted
    ├─ Approval gate (planning phase)
    └─ Advance to next phase
```

Hook points at completion: Taste Checker → Autonomy Engine → Verification Engine → Delivery Engine.

### 5. Circuit Breaker Pattern (`executor.py::Progressive Recovery Ladder`)
4-attempt retry with progressively aggressive recovery strategies:
1. Initial attempt
2. Retry with refined prompt
3. Refine prompt + exponential backoff (5s, 10s, 20s)
4. Fallback model or canonical lock mode

Exit conditions: success → proceed, ship_with_caveats → surface warnings, exhaustion → mark failure.

**Exponential Backoff**: Skipped in test mode (`AIC_TESTING=1`) to avoid 150s test timeouts.

### 6. Singleton Pattern (`executor.py` utilities)
Module-level utility functions serve as implicit singletons:
- `_utcnow()` → Time abstraction for testability
- `adaptive_runtime` → Global registry instance
- Event emission functions integrated with broadcast layers

### 7. Dependency Injection (`executor.py::execute_task`)
AsyncSession injected as parameter enables test mocking and flexible lifecycle management:
```python
async def execute_task(session: AsyncSession, task: Task) -> dict:
```

Sub-sessions created per-worker via `worker_sessionmaker` hoisted to phase scope (P9 optimization).

### 8. Observer Pattern (`executor.py::_emit_event`)
Event emission triggers multiple side effects:
- Database persistence (Event entity)
- WebSocket broadcast (`broadcast_task_event`)
- Automation hook firing (`automation_service.fire_event`)

Non-critical failures logged but do not block execution flow.

### 9. Optimistic Concurrency Control with Retry (`executor.py::_commit_with_lock_retry`)
SQLite WAL mode handles single-writer concurrency via retryable OperationalError:
- Captures pending objects before commit
- On "database is locked", rollback + reapply via `reapply` callback
- Exponential backoff: 0.05s × attempt number
- Maximum 12 retry attempts

### 10. Builder Pattern (Task Context Assembly)
Unified task context built from multiple pipeline sources:
```python
task_ctx = {
    "task_id": task.id,
    "title": task.title,
    "skills": active_worker_skills,      # Resolved skills
    "memories": active_project_memories, # Project memories + MCP graph + lessons learned
    "lessons_learned": lessons_learned,  # Historical lessons
    "plugins": plugin_contexts,          # Plugin components
    "context_text": ctx_assembly.to_prompt_context(),  # Code + tool history
    "adaptive_runtime": {...},           # Applied policies
}
```

Sources: Skill Engine, Memory Engine, MCP Service, Lessons Learned DB, Context Pipeline.

---

## Data & Control Flow

### Entry Points

#### 1. Dispatcher Integration (`backend/dispatcher/engine.py::line 376`)
Primary entry point triggered by job dispatcher:
```python
from runtime.executor import execute_task
await execute_task(session, task)
```

#### 2. Conversation Route (`backend/routes/conversations.py::line 506`)
Direct task creation from conversation UI:
```python
from runtime.executor import execute_task
result = await execute_task(session, task)
```

#### 3. Orchestrator Service (`backend/services/orchestrator_service.py::line 584`)
High-level orchestration invoking executor:
```python
from runtime.executor import execute_task
execution_result = await execute_task(db_session, task)
```

#### 4. Test Harness (`tests/test_phase_parallelism.py`, etc.)
Unit/integration tests invoke executor directly with mocked sessions.

---

### Primary Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTE_TASK START                           │
├─────────────────────────────────────────────────────────────────┤
│ 1. Resolve Project Repository Path                              │
│    ├─ Prefer project.repo_path                                  │
│    └─ Fallback to sandbox_workspace_dir(conversation_id)        │
│                                                                  │
│ 2. Resolve Smart Triage & Execution Level                       │
│    ├─ perform_smart_triage() → ExecutionLevel (L1-L4)           │
│    ├─ Extract skip_phases, selected_workers, phase_semantics    │
│    └─ Materialize PRD.md from Engineering Brief (best-effort)   │
│                                                                  │
│ 3. Emit TASK_CREATED Root Event                                 │
│    ├─ Causal chain root (parent_event_id conceptually)          │
│    └─ Includes triage reason, guardrails_triggered              │
│                                                                  │
│ 4. FSM Phase Loop (discovery → closeout)                        │
│    ├─ SKIP check: skip_phases.get(phase) → auto-advance         │
│    ├─ WORKER RESOLUTION: allowed_workers_for_phase()            │
│    ├─ COMMIT main session (release SQLite lock)                 │
│    ├─ PARALLEL EXECUTION (asyncio.gather):                      │
│    │   ├─ Each worker gets isolated AsyncSession               │
│    │   ├─ Lease creation + WORKER_STARTED event                │
│    │   ├─ Skill/Memory/Plugin resolution                       │
│    │   ├─ run_with_timeout(task_ctx)                           │
│    │   ├─ Progressive Recovery Ladder (≤4 attempts)            │
│    │   ├─ Deliverable file save                                │
│    │   ├─ Code extraction to workspace                         │
│    │   ├─ PROJECT MEMORY SAVE (save_memory_entry)              │
│    │   └─ WORKER_COMPLETED/FAILED event                        │
│    ├─ RESULT MERGE (sequential handoff merge)                   │
│    ├─ LOCAL REPAIR LOOP (if verification failed):               │
│    │   ├─ Re-run responsible worker                            │
│    │   ├─ Re-run QA verification                               │
│    │   └─ Attempt ≤3 times                                     │
│    ├─ DYNAMIC ESCALATION (if repair exhausted):                 │
│    │   ├─ QUICK→EXTENDED or STANDARD→FULL                      │
│    │   └─ Update execution_level, emit task.escalated          │
│    ├─ APPROVAL GATE (planning + approval_required):             │
│    │   ├─ Create/poll Approval entity                          │
│    │   └─ Return waiting_for_approval=True                     │
│    └─ PHASE_ADVANCED event + advance                            │
│                                                                  │
│ 5. COMPLETION INTEGRITY CHECK                                   │
│    ├─ TASTE CHECKER: Scan deliverables for AI-isms              │
│    ├─ BLOCK CONDITIONS:                                         │
│    │   ├─ verification_failed → TaskStatus.FAILED              │
│    │   ├─ fallback_used → TaskStatus.FAILED                    │
│    │   └─ no_source_artifacts (feature/bugfix/refactor)        │
│    ├─ AUTONOMY ENGINE HOOK (if blocked)                         │
│    └─ MARK COMPLETE (all checks pass) → TaskStatus.COMPLETED   │
│                                                                  │
│ 6. POST-COMPLETION HOOKS                                        │
│    ├─ VERIFICATION ENGINE (verify brief)                        │
│    ├─ DELIVERY ENGINE (generate report)                         │
│    └─ TASK_COMPLETED event                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

### Adaptive Policy Generation Flow (`adaptive.py`)

```
Provider Metadata Input
         ↓
┌──────────────────────────────────────────┐
│ capabilities_from_metadata(provider,     │
│                              model,       │
│                              metadata)    │
├──────────────────────────────────────────┤
│ 1. Flatten nested "capabilities" object  │
│ 2. Resolve boolean aliases (_BOOL_ALIASES)│
│ 3. Coerce integers (_positive_int)       │
│ 4. Return ModelCapabilities(frozen=True) │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ generate_runtime_profile(capabilities)   │
├──────────────────────────────────────────┤
│ CONTEXT POLICY (based on context_window):│
│   - LARGE (≥100k): budget=64k, summary=minimal│
│   - MEDIUM (≥32k): budget=20k, summary=periodic │
│   - SMALL (<32k): budget=2k, summary=aggressive │
│                                          │
│ MEMORY POLICY (based on embeddings):     │
│   - LARGE + embeddings → HYBRID          │
│   - ANY + embeddings → SEMANTIC          │
│   - LARGE only → REPOSITORY              │
│   - MEDIUM only → CHECKPOINT             │
│   - SMALL only → SESSION_ONLY            │
│                                          │
│ WORKER POLICY (based on context_class):  │
│   - planning_depth: incremental/structured/deep │
│   - max_parallel_workers: 1/2/4 (capped by parallel_requests) │
│   - prompt_detail: compact/balanced/comprehensive │
│   - verification_frequency: every_step/every_phase/phase_and_closeout │
│   - evidence_level: full/essential       │
│                                          │
│ RETURN: AdaptiveRuntimeProfile           │
└──────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────┐
│ apply_worker_policy(task_ctx, profile)   │
├──────────────────────────────────────────┤
│ Returns new dict with "adaptive_runtime":│
│   ├─ profile_id: "{classification}_{memory}" │
│   ├─ context: asdict(ContextPolicy)      │
│   ├─ memory: asdict(MemoryPolicy)        │
│   ├─ worker: asdict(WorkerPolicy)        │
│   └─ checkpoint_strategy: string         │
└──────────────────────────────────────────┘
```

---

### Exit Points

#### 1. Success Case
```json
{
  "success": true,
  "phases": 5,
  "results": {"discovery": {...}, "planning": {...}, ...},
  "fallback_used": false,
  "execution_level": "standard"
}
```

#### 2. Blocked Failure Case
```json
{
  "success": false,
  "phases": 3,
  "results": {...},
  "verification_failed": true,
  "fallback_used": false,
  "completion_blocked": "verification_failed",
  "execution_level": "standard"
}
```

#### 3. Waiting for Approval
```json
{
  "success": false,
  "phases": 1,
  "results": {},
  "waiting_for_approval": true,
  "fallback_used": false,
  "execution_level": "standard"
}
```

---

### Secondary Flows

#### Worker Resolution & Parallel Execution
```
Phase Workers List
         ↓
asyncio.gather(*[_execute_worker_in_new_session(w) for w in workers])
         ↓
Per-Worker Isolated Session
├─ Create Lease(entity)
├─ Emit WORKER_STARTED event
├─ Broadcast to WebSocket (broadcast_worker_event)
├─ Resolve Skills (backend.skill_engine.resolve_skills_for_worker)
├─ Resolve Project Memories (backend.memory_engine.retrieve_project_memories)
├─ Resolve Plugins (backend.plugin_engine.resolve_plugins_for_worker)
├─ Query MCP Memory Graph (mcp_pool.call_tool "search_nodes")
├─ Query Lessons Learned (SQL query → category-filtered)
├─ Build Context Pipeline (CodeContextSource + ToolHistorySource)
├─ Apply Adaptive Policy (runtime.adaptive.apply_worker_policy)
├─ worker.run_with_timeout(task_ctx, timeout)
├─ Progressive Recovery Ladder (≤4 retries)
├─ Save Deliverable File (backend.workspace_manager.save_deliverable_file)
├─ Extract Code Blocks (backend.code_extract.extract_code_blocks_to_workspace)
├─ Save Project Memory (backend.memory_engine.save_memory_entry)
├─ Emit WORKER_COMPLETED/FAILED event
└─ Broadcast completion event
         ↓
Merge Results Deterministically (sequential order)
└─ Handoff dict merge after gather returns (avoids race condition)
```

---

### Database Schema Interaction

#### Tables Written by Executor
| Table | Columns | Purpose |
|-------|---------|---------|
| `event` | type, actor, target, data, severity, timestamp | Audit log + WebSocket trigger |
| `lease` | task_id, worker_id, worker_name, worker_type, phase, status, exit_code, error_message, artifact_path | Worker execution tracking |
| `task` | status, progress, started_at, completed_at, error_message, context (JSONB) | FSM state machine tracking |
| `approval` | task_id, type, status, requested_by, reason | Human-in-the-loop gates |
| `anomaly_log` | id, anomaly_type, severity, description, affected_component | Autonomy Engine integration |
| `recovery_log` | anomaly_id, action_type, success, details, attempts | Recovery attempt tracking |
| `memory` | key, value, project_id, scope, category, importance | Project memory storage |

#### Session Management Strategy
- **Main session**: Executor-level phase transitions, commits between phases
- **Worker sessions**: Isolated `async_sessionmaker` hoisted per phase (P9 optimization)
- **Lock handling**: `_commit_with_lock_retry` wraps all commits with 12-attempt backoff

---

## Integration Points

### Dependencies

#### Internal Dependencies
| Module | Import Location | Usage |
|--------|-----------------|-------|
| `storage.models` | Top-level imports | `Task`, `Lease`, `Worker`, `Event`, `EventType`, `TaskStatus`, `Approval`, `EngineeringBrief`, `LessonLearned` |
| `workers.base` | `WORKER_REGISTRY` lookup | `WORKER_REGISTRY.get(wtype)` resolves worker class |
| `workflow.triage` | `perform_smart_triage` | Classification into ExecutionLevel (L1-L4) |
| `workflow.fsm` | `is_terminal`, `allowed_workers_for_phase`, `next_phase` | FSM phase transitions |
| `llm.provider` | `provider_manager.get_active_profile()` | Retrieve active adaptive profile |
| `backend.skill_engine` | `resolve_skills_for_worker()` | Dynamic skill injection |
| `backend.memory_engine` | `retrieve_project_memories()`, `save_memory_entry()` | Project knowledge retrieval/persistence |
| `backend.plugin_engine` | `resolve_plugins_for_worker()` | Plugin component discovery |
| `backend.services.mcp_service` | `get_all_mcp_tool_schemas()`, `mcp_pool.call_tool()` | MCP memory graph queries |
| `backend.code_extract` | `extract_code_blocks_to_workspace()` | Parse code blocks from worker output |
| `backend.workspace_manager` | `inspect_project_structure()`, `save_deliverable_file()`, `list_workspace_files()` | Workspace filesystem operations |
| `backend.recovery_engine` | `RecoveryEngine.evaluate_failure()` | Progressive recovery decisions |
| `backend.routes.websocket` | `broadcast_task_event()`, `broadcast_worker_event()` | Real-time frontend updates |
| `backend.services.automation_service` | `fire_event()` | Webhook/automation hook triggers |
| `autonomy.engine` | `AutonomyEngine.detect_anomaly()` | Error recovery integration (WP-07) |
| `verification.engine` | `VerificationEngine.verify()` | Post-completion verification (WP-04) |
| `delivery.engine` | `DeliveryEngine.generate_report()` | Final delivery reporting (WP-06) |
| `backend.services.taste_checker` | `scan_text()` | AI-ism detection in deliverables |
| `context.pipeline` | `ContextPipeline.assemble()` | Unified context assembly |
| `context.sources` | `CodeContextSource`, `ToolHistorySource` | Context source plugins |
| `shared.workspace` | `sandbox_workspace_dir()` | Sandbox path resolution |

#### External Dependencies
| Package | Import Location | Usage |
|---------|-----------------|-------|
| `sqlalchemy` | Multiple | `select`, `AsyncSession`, `flag_modified`, `async_sessionmaker` |
| `sqlalchemy.ext.asyncio` | Line 24 | `AsyncSession` type hint, session binding |
| `sqlalchemy.orm.attributes` | Line 25 | `flag_modified()` for JSONB change detection |
| `asyncio` | Line 19 | `gather`, `sleep`, `to_thread`, async coordination |
| `datetime` | Line 18 | `datetime.now(timezone.utc)` for timestamps |
| `logging` | Line 21 | `logger.info/warning/error` emission |
| `pathlib.Path` | Line 22 | File path manipulation |
| `os` | Line 20 | `environ` checks, `path.exists`, `walk` |
| `dataclasses` | `adaptive.py` line 8 | `asdict`, `dataclass`, `field` |
| `enum.Enum` | `adaptive.py` line 10 | `ContextClass`, `MemoryMode` enums |

---

### Consumer Modules

#### 1. Dispatcher (`backend/dispatcher/engine.py`)
Triggers task execution after lease acquisition:
```python
from runtime.executor import execute_task
execution_result = await execute_task(session, task)
```

#### 2. Conversation Routes (`backend/routes/conversations.py`)
Executes tasks initiated from chat interface:
```python
from runtime.executor import execute_task
response = await execute_task(db_session, task_obj)
```

#### 3. Orchestrator Service (`backend/services/orchestrator_service.py`)
Higher-level orchestration wrapping executor with additional business logic:
```python
from runtime.executor import execute_task
result = await execute_task(session, task)
```

#### 4. API Tests (`tests/`)
Multiple test modules import executor for unit/integration testing:
- `test_phase_parallelism.py`: Validates concurrent worker execution
- `test_adaptive.py`: Unit tests for adaptive policy generation
- `test_e2e.py`: End-to-end task lifecycle validation
- `test_self_healing.py`: Recovery ladder testing
- `test_lock_retry.py`: SQLite lock contention handling

#### 5. LLM Provider (`llm/provider.py`)
Consumes `AdaptiveRuntimeProfile` from registry to configure LLM calls:
```python
from runtime.adaptive import capabilities_from_metadata
active_profile = adaptive_runtime.get(provider, model)
```

---

### WebSocket Broadcast Events

| Event Type | Payload | Purpose |
|------------|---------|---------|
| `task.created` | `{title, type, worker_type, execution_level, triage_reason}` | Show task start in Office Floor |
| `worker.started` | `{phase, title}` | Highlight active worker in Office Floor |
| `worker.completed` | `{phase, success, output[:200], used_fallback}` | Mark worker complete |
| `worker.failed` | `{phase, error[:300]}` | Indicate worker failure |
| `phase.advanced` | `{phase, progress, execution_level}` | Update progress bar |
| `local_repair.started` | `{attempt, responsible_worker}` | Show repair loop active |
| `local_repair.completed` | `{attempt, outcome}` | Report repair result |
| `task.escalated` | `{from_level, to_level, reason}` | Display escalation notification |
| `task.completed` | `{phases_completed, golden_path}` | Final completion notification |

Broadcast implemented via `broadcast_task_event()` and `broadcast_worker_event()` with graceful failure handling (exceptions logged, not raised).

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AIC_TESTING` | `(unset)` | Skip exponential backoff sleeps during retry; set to `"1"` for faster tests |

### Runtime Behavior Controls

#### Adaptive Profile Selection
Profiles automatically selected based on:
- `context_window` threshold (100k / 32k boundaries)
- `embeddings` capability boolean
- `parallel_requests` capability boolean
- `reasoning` capability boolean (evidence_level toggle)

#### Execution Level Classification
Determined by `perform_smart_triage()` analyzing:
- Task title/description
- Task type (`feature`, `bugfix`, `refactor`, etc.)
- Worker hint (`worker_type`)
- Guardrail triggers (security, DB schema, architecture sensitivity)

**Levels**:
- **L1 QUICK**: Minimal phases, localized changes only
- **L2 STANDARD**: Full scope within single component
- **L3 EXTENDED**: Cross-component engineering with additional safeguards
- **L4 FULL**: Complete multi-agent lifecycle with maximum oversight

#### Local Repair Loop
- **Attempts**: Maximum 3 repair iterations
- **Responsible Worker**: Selected from (`backend`, `frontend`, `coding`, `database`) or defaults to `backend`
- **Re-verification**: QA worker re-runs after each repair attempt

#### Dynamic Escalation Rules
```
verification_failed + L1 QUICK  → escalate to L3 EXTENDED
verification_failed + L2 STANDARD → escalate to L4 FULL
repair_attempts ≥ 3 + any level → permanent FAILURE
```

---

## Key Functions

### `execute_task(session: AsyncSession, task: Task) → dict`
**Signature**: `async` function accepting dependency-injected session

**Return Types**:
- Success: `{"success": True, "phases": int, "results": dict, "fallback_used": False, "execution_level": str}`
- Blocked: Same shape with `"success": False, "completion_blocked": "verification_failed"\|"fallback_used"\|"no_source_artifacts"`
- Pending: `{"success": False, "waiting_for_approval": True, ...}`

**Side Effects**:
- Writes to `task`, `event`, `lease`, `approval` tables
- Emits WebSocket broadcasts (best-effort)
- Triggers autonomy/verification/delivery engines (non-critical)

---

### `capabilities_from_metadata(provider: str, model: str, metadata: Mapping | None) → ModelCapabilities`
**Purpose**: Vendor-normalize provider metadata into typed capabilities profile

**Alias Resolution Map** (`_BOOL_ALIASES`):
- `tool_calling` ← `("tool_calling", "supports_tools", "supports_tool_calling")`
- `json_mode` ← `("json_mode", "supports_json", "supports_json_mode")`
- `reasoning` ← `("reasoning", "supports_reasoning", "supports_thinking")`
- `streaming` ← `("streaming", "supports_streaming")`
- `vision` ← `("vision", "supports_vision")`
- `image_generation` ← `("image_generation", "supports_image_generation")`
- `embeddings` ← `("embeddings", "supports_embeddings")`
- `function_calling` ← `("function_calling", "supports_function_calling")`
- `parallel_requests` ← `("parallel_requests", "supports_parallel_requests")`
- `mcp` ← `("mcp", "supports_mcp")`
- `local` ← `("local", "is_local")`

**Source Tagging**: `source="provider_metadata"` when raw metadata present, else `"conservative_default"`

---

### `generate_runtime_profile(cap: ModelCapabilities) → AdaptiveRuntimeProfile`
**Policy Derivation Logic**:

#### Context Policy
```python
window = cap.context_window or 0
if window >= 100_000:
    context_class = LARGE
    prompt_budget_tokens = min(64_000, max(8_000, window * 0.55))
elif window >= 32_000:
    context_class = MEDIUM
    prompt_budget_tokens = min(20_000, window * 0.55)
else:
    context_class = SMALL
    effective = window or 8_192
    prompt_budget_tokens = max(2_048, effective * 0.45)
```

#### Memory Mode
```python
if cap.embeddings and LARGE: HYBRID
elif cap.embeddings: SEMANTIC
elif LARGE: REPOSITORY
elif MEDIUM: CHECKPOINT
else: SESSION_ONLY
```

#### Worker Policy
```python
planning_depth = {SMALL: "incremental", MEDIUM: "structured", LARGE: "deep"}
max_parallel_workers = (4 if cap.parallel_requests else 1), capped by context class
prompt_detail = {SMALL: "compact", MEDIUM: "balanced", LARGE: "comprehensive"}
verification_frequency = {SMALL: "every_step", MEDIUM: "every_phase", LARGE: "phase_and_closeout"}
evidence_level = "full" if cap.reasoning or LARGE else "essential"
max_retries = 2 if cap.local else 3
```

---

### `apply_worker_policy(task_context: Mapping, profile: AdaptiveRuntimeProfile) → dict`
Returns new dict with attached policy data:
```python
{
  **task_context,
  "adaptive_runtime": {
    "profile_id": profile.profile_id,
    "context": asdict(profile.context),
    "memory": asdict(profile.memory),
    "worker": asdict(profile.worker),
    "checkpoint_strategy": profile.checkpoint_strategy,
  }
}
```

---

### `runtime_prompt_directive(profile: AdaptiveRuntimeProfile) → str`
Generates human-readable directive string for worker prompts:
```
--- ADAPTIVE RUNTIME POLICY ---
Context class: {classification}; prompt detail: {prompt_detail}.
Planning: {planning_depth}; verification: {verification_frequency}.
Checkpoint every {checkpoint_interval_steps} execution step(s).
Use at most {max_parallel_workers} parallel worker request(s).
Retrieval first: {'yes' | 'no'}; history limit: {history_message_limit} messages.
```

---

## Error Handling

### Critical Failures (Propagated Upward)
- **Unhandled worker exceptions**: Logged, merged into phase_results, worker marked FAILED
- **Merge errors**: Individual worker failure recorded, execution continues
- **Database OperationalError (not lock-related)**: Immediate re-raise

### Non-Critical Failures (Logged, Continue Execution)
- **WebSocket broadcast failures**: Debug log, no impact on execution
- **Automation hook fires**: Debug log, no blocking
- **Taste checker exception**: Debug log, findings optional
- **Autonomy Engine hook**: Warning log, task proceeds to FAILED anyway
- **Verification/Delivery Engine hooks**: Warning log, non-blocking
- **Skill/Memory/Plugin resolution**: Debug log, missing features gracefully degraded
- **MCP memory query**: Debug log, silent fallback
- **Lessons Learned query**: ImportError handled silently

### Progressive Recovery Strategies
1. **retry**: Re-execute worker with original context
2. **refine_prompt**: Append feedback prompt to description
3. **fallback_model**: Switch to secondary model tier
4. **canonical_lock**: Use canonical locking mechanism

**Exhaustion**: After 4 attempts, worker marked FAILED, phase_verification_failed flag raised.

---

## Metrics & Observability

### Logging Categories
| Logger | Usage | Severity Levels |
|--------|-------|-----------------|
| `aic.runtime` | Executor operations | `info`, `warning`, `error`, `debug` |
| `aic.autonomy` | Anomaly/recovery events | `info`, `warning`, `error` |

### Status Transitions
| From | To | Trigger | Progress |
|------|-----|---------|----------|
| `new` | `discovery` | Task start | 5% |
| `discovery` | `planning` | Phase complete | 20% |
| `planning` | `implementation` | Phase complete | 35% |
| `implementation` | `verification` | Phase complete | 50% |
| `verification` | `closeout` | Phase complete | 65% |
| `closeout` | `completed` | All checks pass | 100% |
| Any | `failed` | Block conditions met | progress - 10% |

### Event Sequence
Each task generates ordered event chain:
1. `TASK_CREATED` (root event)
2. Per-worker: `WORKER_STARTED` → `WORKER_COMPLETED`/`WORKER_FAILED`
3. Per-phase: `PHASE_ADVANCED`
4. Conditional: `LOCAL_REPAIR.STARTED`/`COMPLETED`
5. Conditional: `TASK_ESCALATED`
6. Terminal: `TASK_COMPLETED` or `WORKER_FAILED` (final blocker)

Events form causal chain via `prev` field referencing prior event target.

---

## Testing Coverage

### Unit Test Modules
| File | Coverage Focus |
|------|----------------|
| `tests/test_adaptive.py` | Capability normalization, profile generation, registry operations |
| `tests/test_phase_parallelism.py` | Concurrent worker execution, session isolation, result merging |
| `tests/test_lock_retry.py` | SQLite lock contention handling, exponential backoff |
| `tests/test_e2e.py` | Full task lifecycle from dispatch to completion |
| `tests/test_self_healing.py` | Recovery ladder, local repair loop, dynamic escalation |
| `tests/test_worker_vision.py` | Vision-capable worker integration |

### Test Environment Variables
- `AIC_TESTING=1`: Disables exponential backoff sleeps in recovery ladder
- Mock `AsyncSession` passed directly to `execute_task()`

---

## Security Considerations

### Workspace Isolation
- Never writes to process cwd (`.`)
- Prefers `project.repo_path` if configured
- Falls back to `sandbox_workspace_dir(scope_id)` under `DATA_DIR/workspaces/`
- Skips `node_modules/`, `venv/`, `.venv/` directories during source artifact scanning

### Event Sanitization
- Output truncated before emission (`[:1000]`, `[:200]`)
- Error messages truncated (`[:300]`)
- No sensitive credentials included in events

### Database Lock Safety
- Single-writer SQLite concurrency handled via retry-backoff
- Main session committed BEFORE worker gather to prevent lock escalation
- Isolated worker sessions per-worker prevent cross-contamination

### Graceful Degradation
All external integrations (WebSocket, automation, taste checker, autonomy, verification, delivery, MCP, skills, memories, plugins, lessons) wrapped in try/except with debug logging—never fatal.

---

## Future Considerations

1. **Session Hoisting Optimization**: P9 already hoists `worker_sessionmaker` per phase; consider caching worker sessions across phases for identical workers

2. **Handoff Conflict Resolution**: Current "last-writer-wins" per phase may lose data under high contention; consider CRDT-style merges or deterministic ordering

3. **Recovery Strategy Persistence**: Recover decisions currently ephemeral; logging to recovery_log table would enable post-mortem analysis

4. **Adaptive Timeout Tuning**: `_adaptive_worker_timeout()` uses fixed multiplier (1.5-2.5x); could be made more granular per worker type

5. **Escalation Granularity**: Only 2-step escalation (QUICK→EXTENDED, STANDARD→FULL); consider intermediate tiers (L2→L3 without jumping to L4)

6. **Test Mode Optimization**: Even with `AIC_TESTING=1`, socket connections and network calls still incur latency; mock all external services for faster CI

7. **Observability Enrichment**: Add OpenTelemetry spans for executor phases, worker calls, recovery attempts for distributed tracing

8. **Memory Eviction Strategy**: Project memory currently unbounded; TTL-based eviction or LRU cache preferred for long-running projects

9. **Approval Delegation**: Approval gate currently blocks until manual intervention; consider delegating to secondary approvers or time-expiring approvals

10. **Fallback Output Validation**: Fallback outputs never masquerade as success, but could include explicit "FALLBACK_OUTPUT" markers in deliverables for transparency

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| v2.3.8 | 2026-08-10 | Initial codemap generation for backend/runtime module |

</content>
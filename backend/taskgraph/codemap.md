# Task Graph Engine — DAG Generation & Execution Planning (v2.3.4)

**Location**: `/backend/taskgraph/`  
**Last Updated**: 2026-08-10

---

## 1. Responsibility

### Primary Role
**Task Graph Decomposition Engine**: Transforms Engineering Plans into ordered Directed Acyclic Graphs (DAGs) that define task execution sequences, dependencies, and parallelism opportunities.

### Specific Responsibilities

1. **Plan Decomposition**: Breaks engineering plans with effort estimates into atomic `TaskNode` entities mapped to specific worker types (backend, frontend, qa, etc.) via keyword-based classification rules.

2. **Dependency Analysis**: Identifies implicit task dependencies based on workflow semantics:
   - Testing/documentation/review tasks depend on coding tasks
   - Phase-based barrier edges enforce sequential phase execution while allowing intra-phase parallelism
   - Explicit node dependency fields from plan data

3. **Parallelism Detection**: Computes execution order groups where nodes within each group can execute concurrently using topological sorting with dependency satisfaction checks.

4. **Critical Path Computation**: Finds the longest path through the DAG to estimate minimum completion time and identify bottlenecks.

5. **Cycle Detection & Validation**: Ensures graph validity using DFS-based cycle detection, duplicate ID detection, and edge reference validation.

6. **Recovery Point Generation**: Inserts recovery checkpoints at configurable intervals for rollback capability during execution.

7. **Database Persistence**: Serializes DAG structure (nodes, edges, execution_order, critical_path, recovery_points) into `task_graphs` table with foreign key relationship to `engineering_plans`.

### Design Intent
Enable deterministic task scheduling by producing a validated DAG that downstream consumers (`DispatcherEngine`, `MasterOrchestrator`) can use to parallelize work execution while respecting phase boundaries and task dependencies.

---

## 2. Architecture

### Component Structure

| File | Lines | Purpose | Public API |
|------|-------|---------|------------|
| `__init__.py` | 21 | Package initialization and re-exports | `taskgraph_config`, `TaskGraphConfig`, `TaskGraphState`, `TaskGraph`, `TaskNode`, `TaskEdge`, `GraphValidation` |
| `engine.py` | 220 | Core orchestrator pipeline | `TaskGraphEngine`, `TaskGraphResult`, `generate_graph()` |
| `decomposer.py` | 131 | Plan-to-nodes transformation | `PlanDecomposer.decompose()`, `WORKER_TYPE_MAP` |
| `dependency.py` | 257 | Dependency analysis & scheduling | `DependencyAnalyzer.analyze_dependencies()`, `detect_parallelism()`, `find_critical_path()` |
| `validator.py` | 128 | Graph validation & cycle detection | `GraphValidator.validate()`, `_detect_cycles()` |
| `models.py` | 113 | Domain data structures | `TaskNode`, `TaskEdge`, `TaskGraph`, `GraphValidation`, `RecoveryPoint` |
| `config.py` | 49 | Environment-driven configuration | `TaskGraphConfig`, `from_env()`, `taskgraph_config` singleton |
| `states.py` | 87 | FSM state machine for graph lifecycle | `TaskGraphState`, `can_transition()`, `is_terminal()`, `next_states()` |
| `migration.py` | 47 | Database schema migrations | `run_taskgraph_migration()` |

---

## 3. Design Patterns

### 1. Pipeline Pattern (`engine.py::TaskGraphEngine._run_pipeline`)

Standardized 8-step orchestration:
```python
1. Decompose(plan_data) → list[TaskNode]
2. analyze_dependencies(nodes) → list[TaskEdge]
3. detect_parallelism(nodes, edges) → list[list[str]] (execution_order)
4. find_critical_path(nodes, edges) → list[str]
5. validate(nodes, edges) → GraphValidation
6. _generate_recovery_points(nodes) → list[RecoveryPoint]
7. _calculate_parallelism_factor(execution_order, total_nodes) → float
8. Build TaskGraph(result)
```

Each step is a composable, testable unit. Early termination on error (e.g., invalid graph) prevents wasted computation.

### 2. Strategy Pattern (`decomposer.py::_determine_worker_type/_determine_task_type`)

Keyword-based classification replaces hardcoded mapping tables:
```python
for keyword, worker_type in WORKER_TYPE_MAP.items():
    if keyword in lower:
        return worker_type
```
Extension points: Add new worker types by updating `WORKER_TYPE_MAP`; add new keywords without modifying control flow.

### 3. Composite Edge Construction (`dependency.py::analyze_dependencies`)

Multiple edge sources combined into unified dependency graph:
- **Type-based edges**: testing/docs/review depend on coding
- **Explicit edges**: From node's `dependencies` field
- **Phase barrier edges**: From `workflow.fsm.PHASE_WORKERS` / `PHASE_ORDER`

Pattern enables separation of concerns while preserving unified graph output.

### 4. Flyweight Configuration (`config.py::TaskGraphConfig.from_env`)

Singleton config loaded once at module import time, shared across all engine instances:
```python
taskgraph_config = TaskGraphConfig.from_env()
```
Environment variable overrides allow runtime tuning without code changes.

### 5. Singleton Pattern (`engine.py::TaskGraphEngine.__init__`)

Engine instances receive dependency-injected `AsyncSession` but maintain no persistent internal state—pure functions wrapped in mutable objects for extensibility.

### 6. Builder Pattern (Models - `models.py`)

Dataclasses with `__post_init__` auto-generation IDs:
```python
def __post_init__(self):
    if not self.node_id:
        self.node_id = f"NODE-{uuid4().hex[:8].upper()}"
```
Idempotent instantiation; safe to reuse partial data without manual ID management.

### 7. Template Method (`states.py::can_transition/is_terminal/next_states`)

Shared state transition logic extracted from hard-coded enums in other modules:
- Centralized `TRANSITIONS` dict defines valid state paths
- `TERMINAL_STATES` frozenset prevents further transitions
- Query functions provide read-only access to FSM metadata

Enforces consistent state handling across consumers (dispatcher, orchestrator).

### 8. Observer Pattern (Heartbeat Integration)

Indirectly via `dependency.py::_add_phase_barrier_edges`:
```python
from workflow.fsm import PHASE_WORKERS, PHASE_ORDER
```
Observer reads static FSM definitions to align taskgraph phases with agent execution phases, ensuring cross-module consistency.

---

## 4. Data & Control Flow

### Entry Points

#### 1. External Input Sources

| Source | Location | Usage |
|--------|----------|-------|
| **API Routes** | `backend/routes/taskgraph.py::generate_graph` | POST `/api/taskgraph/generate` with `{plan_id}` payload |
| **Master Orchestrator** | `backend/services/master_orchestrator.py::_run_taskgraph` | Triggered during Stage 3 of plan execution pipeline |
| **Subtask Re-wiring** | `backend/services/master_orchestrator.py::_run_taskgraph_from_subtasks` | Builds graph from existing subtask Task rows instead of fresh decomposing |

#### 2. Direct Import Usage
```python
from taskgraph.engine import TaskGraphEngine
engine = TaskGraphEngine(session)
result = await engine.generate_graph(plan_id)
```

#### 3. Test Fixture Usage
```python
from taskgraph.decomposer import PlanDecomposer
from taskgraph.dependency import DependencyAnalyzer
from taskgraph.validator import GraphValidator
```

### Internal Processing Flow

```mermaid
graph TD
    A[EngineeringPlan Model] --> B[Extract Fields]
    B --> C[PlanData Dict]
    
    C --> D[PlanDecomposer.decompose]
    D --> E[List[TaskNode]]
    
    E --> F[DependencyAnalyzer.analyze_dependencies]
    F --> G[List[TaskEdge]]
    
    G --> H[DependencyAnalyzer.detect_parallelism]
    H --> I[execution_order Groups]
    
    I --> J[DependencyAnalyzer.find_critical_path]
    J --> K[critical_path List]
    
    E --> L[GraphValidator.validate]
    G --> L
    L --> M{is_valid?}
    
    M -->|No| N[Return ERROR Result]
    M -->|Yes| O[_generate_recovery_points]
    
    O --> P[RecoveryPoints List]
    I --> Q[_calculate_parallelism_factor]
    Q --> R[parallelism_factor Float]
    
    E --> S[TaskGraph Constructor]
    G --> S
    I --> S
    K --> S
    P --> S
    R --> S
    
    S --> T[Build TaskGraph ORM]
    T --> U[Persist to DB]
    U --> V[Return TaskGraphResult]
    
    style N fill:#f99
    style V fill:#9f9
```

### Data Dependencies

| Source | Consumed By | Schema/Fields |
|--------|-------------|---------------|
| `storage.models.EngineeringPlanModel` | `engine.py::generate_graph` | `id`, `brief_id`, `engineering_goal`, `technical_approach`, `implementation_strategy`, `architecture_decisions`, `risk_mitigations`, `dependency_map`, `effort_estimates`, `acceptance_criteria`, `estimated_duration`, `confidence_score` |
| `taskgraph.config.taskgraph_config` | Multiple modules | `enabled`, `max_nodes`, `max_edges`, `recovery_point_interval` |
| `workflow.fsm.PHASE_WORKERS` | `dependency.py::_add_phase_barrier_edges` | `{"phase_name": [{"worker": str, "tier": str}, ...], ...}` |
| `workflow.fsm.PHASE_ORDER` | `dependency.py::_add_phase_barrier_edges` | `["created", "discovery", ..., "completed"]` |

### Output Structures

#### `TaskGraphResult` (Primary Return Value)
```python
@dataclass
class TaskGraphResult:
    state: str           # "graph_complete", "error", "disabled"
    graph: TaskGraph     # Full DAG object (None on error/disabled)
    message: str         # Human-readable summary
    metadata: dict       # {graph_id, plan_id, node_count, edge_count, parallelism_factor}
```

#### `TaskGraph.to_dict()` (JSON Serialization)
```json
{
  "graph_id": "GRAPH-<12-char-hex>",
  "plan_id": "PLAN-<8-char-hex>",
  "nodes": [
    {
      "node_id": "NODE-<8-char-hex>",
      "title": string,
      "description": string,
      "task_type": "coding/testing/documentation/review",
      "worker_type": "backend/frontend/qa/security/etc.",
      "dependencies": ["NODE-xxx", ...],
      "estimated_effort": "low/medium/high/very_high",
      "priority": 0-3,
      "can_parallel": boolean
    }
  ],
  "edges": [
    {
      "from_node": "NODE-xxx",
      "to_node": "NODE-yyy",
      "dependency_type": "blocks",
      "required": true
    }
  ],
  "execution_order": [
    ["NODE-001", "NODE-002"],  // Parallel group 1
    ["NODE-003"]                // Parallel group 2
  ],
  "critical_path": ["NODE-001", "NODE-003", "NODE-005"],
  "recovery_points": [
    {"node_id": "NODE-005", "description": "..."}
  ],
  "estimated_duration": "",
  "parallelism_factor": 0.33,
  "status": "validated"
}
```

#### Recovery Points Generation Logic
```python
interval = taskgraph_config.recovery_point_interval  # Default: 5
for i, node in enumerate(nodes):
    if (i + 1) % interval == 0:
        yield RecoveryPoint(node_id=node.node_id, ...)
```

### Exit Points

1. **`TaskGraphResult.state == "graph_complete"`**: Successful graph generation, persisted to database
2. **`TaskGraphResult.state == "error"`**: Decoding failure or validation error
3. **`TaskGraphResult.state == "disabled"`**: Engine disabled via `AIC_TASKGRAPH_ENABLED=false`

---

## 5. Integration Points

### Dependencies

#### Internal Dependencies

| Module | Dependency Type | Usage Details |
|--------|----------------|---------------|
| `storage.models` | Runtime import | `EngineeringPlanModel`, `TaskGraphModel` ORM classes |
| `storage.database` | Indirect | `AsyncSession` dependency injection |
| `workflow/fsm.py` | Runtime import | `PHASE_WORKERS`, `PHASE_ORDER` for phase-barrier edges |
| `backend/routes/taskgraph.py` | Consumer | API endpoints: `/generate`, `/{graph_id}`, `/plan/{plan_id}` |
| `backend/services/master_orchestrator.py` | Heavy consumer | Two methods: `_run_taskgraph()`, `_run_taskgraph_from_subtasks()` |
| `dispatchers/engine.py` | Consumer | Receives `TaskGraphModel` graphs for execution planning |

#### External Dependencies

| Package | Purpose | Version Notes |
|---------|---------|---------------|
| `sqlalchemy.ext.asyncio.AsyncSession` | Async DB transactions | SQLAlchemy 2.x compatibility |
| `sqlalchemy.select` | ORM queries | Selectable pattern |
| `dataclasses.dataclass` | Record structures | Python 3.7+ standard library |
| `datetime.datetime/timezone` | Timestamp tracking | UTC normalization via `_utcnow` helper |
| `uuid.uuid4` | Unique ID generation | 8–12 char hex truncation for compact IDs |

### Consumer Modules

#### 1. API Layer (`backend/routes/taskgraph.py`)

Three REST endpoints exposing engine functionality:

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/api/taskgraph/generate` | POST | `require_current_user` | `{plan_id: str}` | `{state, graph, message, metadata}` |
| `/api/taskgraph/{graph_id}` | GET | None | URL param | Serialized graph snapshot |
| `/api/taskgraph/plan/{plan_id}` | GET | None | URL param | Meta-info (id, status, created_at) |

Error handling: HTTP 400 for engine errors, 404 for missing graphs.

#### 2. Master Orchestrator (`backend/services/master_orchestrator.py`)

**Stage 3 Integration** (`_run_taskgraph` method):
```python
async def _run_taskgraph(self, plan_id: str) -> Optional[str]:
    from taskgraph.engine import TaskGraphEngine
    engine = TaskGraphEngine(self.session)
    result = await engine.generate_graph(plan_id)
    
    if result.graph and result.state in ("graph_complete", "graph_validated"):
        # Retrieve persisted graph model and mark as validated
        graph_result = await self.session.execute(...)
        graph.status = "validated"
        await self.session.flush()
        return graph.id
```

**Subtask Wiring** (`_run_taskgraph_from_subtasks` method):
- Alternative path when subtasks already exist
- Uses task IDs as node IDs (preserves subtask row references)
- No recovery point generation (empty list)
- Skips duration estimation

#### 3. Dispatcher Engine (`dispatcher/engine.py`)

Consumes `TaskGraphModel` via foreign key:
```python
select(TaskGraphModel).where(TaskGraphModel.id == graph_id)
```
Uses `execution_order` for batch scheduling and `critical_path` for priority queuing.

#### 4. Tests

| Test File | Imports | Coverage Focus |
|-----------|---------|----------------|
| `tests/test_taskgraph.py` | `TaskGraphConfig`, `TaskGraphState`, `TaskGraph`, `TaskNode`, `TaskEdge`, `GraphValidator`, `PlanDecomposer`, `DependencyAnalyzer` | Unit tests for models, validator, decomposer |
| `tests/test_phase_parallelism.py` | `DependencyAnalyzer`, `TaskNode` | Phase barrier edge correctness |
| `tests/test_fixes_round2.py` | `TaskGraphModel` | Subtask graph persistence |
| `tests/test_artifact_workflow.py` | `TaskGraphModel`, `EngineeringPlan` | Cross-module model relationships |

### Database Integration

#### Schema Migration (`migration.py::run_taskgraph_migration`)

Creates `task_graphs` table:
```sql
CREATE TABLE IF NOT EXISTS task_graphs (
    id TEXT PRIMARY KEY,                          -- GRAPH-<12-char-hex>
    plan_id TEXT NOT NULL,                        -- FK → engineering_plans.id
    nodes TEXT DEFAULT '[]',                      -- JSON array of node dicts
    edges TEXT DEFAULT '[]',                      -- JSON array of edge dicts
    execution_order TEXT DEFAULT '[]',            -- JSON array of parallel groups
    critical_path TEXT DEFAULT '[]',              -- JSON array of node_ids
    recovery_points TEXT DEFAULT '[]',            -- JSON array of recovery points
    estimated_duration TEXT DEFAULT '',           -- Human-readable duration
    parallelism_factor REAL DEFAULT 1.0,          -- Max group size / total nodes
    status TEXT DEFAULT 'draft',                  -- draft, validated, executing, completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES engineering_plans(id)
);

CREATE INDEX idx_task_graphs_plan ON task_graphs(plan_id);
CREATE INDEX idx_task_graphs_status ON task_graphs(status);
```

#### JSON Column Schemas

**nodes** (array of `dict`):
```json
{
  "node_id": string,
  "title": string,
  "worker_type": string,
  "task_type": string
}
```

**edges** (array of `dict`):
```json
{
  "from_node": string,
  "to_node": string,
  "dependency_type": "blocks"
}
```

**recovery_points** (array of `dict`):
```json
{
  "node_id": string,
  "description": string
}
```

#### Relationship Diagram

```
engineering_plans
├── id (PK)
└── ← one-to-many ── task_graphs
    ├── id (PK)
    ├── plan_id (FK)
    └── ← one-to-many ── dispatch_sessions
        ├── id (PK)
        └── graph_id (FK → task_graphs.id)
```

### Model Mapping Summary

| Domain Model | Database Column Type | Serialization |
|--------------|---------------------|---------------|
| `TaskNode` | JSON array element | Extracted to `{node_id, title, worker_type, task_type}` |
| `TaskEdge` | JSON array element | Extracted to `{from_node, to_node, dependency_type}` |
| `RecoveryPoint` | JSON array element | Extracted to `{node_id, description}` |
| `TaskGraph.execution_order` | TEXT (JSON) | Raw list-of-lists |
| `TaskGraph.critical_path` | TEXT (JSON) | Raw list |
| `TaskGraph.parallelism_factor` | REAL | Raw float |

---

## 6. Configuration

### Environment Variables

| Variable | Default | Description | Runtime Effect |
|----------|---------|-------------|----------------|
| `AIC_TASKGRAPH_ENABLED` | `true` | Enable/disable engine | If `false`, `generate_graph()` returns immediately with state `"disabled"` |
| `AIC_TASKGRAPH_MAX_NODES` | `100` | Hard limit on generated nodes | Enforced implicitly by decomposer (no explicit check present) |
| `AIC_TASKGRAPH_MAX_EDGES` | `500` | Hard limit on edges | Not enforced in current implementation (placeholder) |
| `AIC_TASKGRAPH_MAX_PARALLEL` | `10` | Maximum parallel factor | Not enforced (placeholder) |
| `AIC_TASKGRAPH_RECOVERY_INTERVAL` | `5` | Recovery point frequency | Every N nodes triggers a recovery checkpoint |

### Configuration Singleton

```python
taskgraph_config = TaskGraphConfig.from_env()  # Module-level global

# Usage examples:
if not taskgraph_config.enabled:
    return TaskGraphResult(state="disabled", ...)

interval = taskgraph_config.recovery_point_interval
```

### Runtime Behavior Modes

| Mode | Condition | Behavior |
|------|-----------|----------|
| **Disabled** | `enabled=false` | Returns early with `state="disabled"`; zero CPU usage |
| **Normal** | `enabled=true` | Full pipeline execution, DB persistence |
| **Error** | Validation failure | Returns `state="error"`; metadata includes error list and cycles detected |

---

## 7. Key Classes & Functions

### `TaskGraphEngine`

**Constructor**: `__init__(self, session: AsyncSession)`

**Main Interface**:
```python
async def generate_graph(self, plan_id: str) -> TaskGraphResult
```
Async entry point; handles plan loading, pipeline orchestration, persistence.

**Internal Pipeline Methods**:
- `_run_pipeline(plan_data: dict) -> TaskGraphResult`
- `_generate_recovery_points(nodes: list[TaskNode]) -> list[RecoveryPoint]`
- `_calculate_parallelism_factor(execution_order, total_nodes) -> float`
- `_build_graph_message(graph: TaskGraph) -> str`

**Design Notes**:
- Session injected at construction; no lazy init
- Results always wrapped in `TaskGraphResult` for uniform error handling
- Metadata populated on success for client-side analytics

### `PlanDecomposer`

**Core Method**: `decompose(plan_data: dict) -> list[TaskNode]`

**Classification Rules**:
- Worker type: Keyword search in requirement description against `WORKER_TYPE_MAP`
- Task type: Keywords (`test`, `doc`, `review`) determine `testing`, `documentation`, `review`, else `coding`
- Priority: Complexity level maps to 0–3 integer scale
- Parallelism: `backend`, `frontend`, `documentation` workers allowed parallel execution; others blocked

**Fallback**: If no effort estimates present, creates single generic backend coding node.

### `DependencyAnalyzer`

**Public API**:
- `analyze_dependencies(nodes) -> list[TaskEdge]` – Multi-source edge construction
- `detect_parallelism(nodes, edges) -> list[list[str]]` – Topological sort with grouping
- `find_critical_path(nodes, edges) -> list[str]` – Longest path via BFS distance propagation

**Critical Algorithm Notes**:
- Phase barriers computed from external `workflow.fsm` definitions
- Self-edge prevention in barrier construction
- Deadlock detection via empty `ready` set in parallelism loop

### `GraphValidator`

**Validation Checks**:
1. Non-empty node list
2. Unique node IDs
3. Valid edge references (both endpoints exist)
4. Cycle detection (DFS with three-color marking)
5. Isolated node warnings (≥2 nodes)
6. High dependency count warnings (>10 deps per node)

**Cycle Detection Algorithm**:
- Depth-first search with `WHITE/GRAY/BLACK` coloring
- Gray → Gray edge indicates back-edge (cycle)
- Cycle reconstruction via parent pointers

### `TaskGraphState` (FSM Enum)

States: `plan_received`, `decomposing`, `analyzing_dependencies`, `computing_order`, `validating_graph`, `graph_complete`, `handoff_to_dispatcher`, `fixing_cycles`, `aborted`, `error`

Terminal states: `handoff_to_dispatcher`, `aborted`, `error`

Transition matrix defined in `TRANSITIONS` dict; `can_transition()` validates legality before proceeding.

---

## 8. Error Handling

### Critical Failures

| Scenario | Handling | Recovery |
|----------|----------|----------|
| DB migration exception | Rollback + re-raise exception | Manual intervention required |
| Plan not found in DB | Return `state="error"` with message | Client retries with corrected plan_id |

### Non-Critical Failures

| Scenario | Handling | Notes |
|----------|----------|-------|
| Empty decomposition result | Return error with message | Logged as warning under `aic.taskgraph.decomposer` |
| Validation failures | Return error with list of errors + cycle info | Detailed metadata enables debugging |
| Deadlock in parallelism detection | Break loop, log warning, return partial result | Safe fallback vs. infinite loop |
| Session flush failure | Silently ignored (non-critical path) | Graph data already constructed in memory |

### Logging Categories

- `aic.taskgraph`: Main engine operations
- `aic.taskgraph.dependency`: Dependency analysis events (deadlocks, warnings)
- `aic.taskgraph.validator`: Validation outcomes (cycles, isolated nodes)
- `aic.taskgraph.decomposer`: Decomposition metrics (node counts)
- `aic.taskgraph.config`: Config parsing events
- `aic.taskgraph.migration`: Migration lifecycle (success/failure)

---

## 9. Metrics & Observability

### Generated Metrics

**From `TaskGraphResult.metadata`**:
- `node_count`: Total number of TaskNodes
- `edge_count`: Total number of TaskEdges
- `parallelism_factor`: Ratio of max parallel group size to total nodes (0.0–1.0)
- `graph_id`: Unique identifier for retrieval

**Implicit Metrics** (logged):
- Cycle count during validation
- Isolated node count (warning only)
- Recovery point count
- Execution order group count

### Statistics Formula

```
parallelism_factor = max(len(group)) / len(total_nodes)
```
Example: `[10, 10]` nodes split into `[[5,5], [5,5]]` → factor = `4/10 = 0.4x`

High factors (>0.5) indicate strong parallelization potential; low factors (<0.2) suggest linear execution bottleneck.

---

## 10. Testing Coverage

### Existing Test Suites

| Test File | Coverage Scope | Key Assertions |
|-----------|----------------|----------------|
| `tests/test_taskgraph.py` | Model instantiation, graph serialization, validator edge cases, decomposer keyword matching | Correct ID formats, to_dict() fidelity, cycle detection |
| `tests/test_phase_parallelism.py` | Phase barrier edge generation from FSM definitions | Nodes in same phase share no edges; consecutive phases fully connected |

### Missing Coverage Areas

- **Integration**: No end-to-end test connecting API route → engine → DB persistence
- **Error Paths**: Disabled engine, plan not found, deadlock scenarios
- **Performance**: Large graph stress tests (>100 nodes)
- **Configuration**: Env var override testing

---

## 11. Future Considerations

### Known Limitations

1. **Missing Config Enforcement**: `max_nodes`, `max_edges`, `max_parallel_factor` defined but never checked at runtime
2. **Placeholder Recovery Logic**: Simple modulo-based checkpoint insertion; lacks intelligent risk assessment (e.g., after expensive ops)
3. **Hardcoded Type Mapping**: `WORKER_TYPE_MAP` uses substring matching; brittle to description format changes
4. **Incomplete FSM Sync**: `pm` worker maps to FIRST occurrence in FSM (skipping discovery phase), creating implicit coupling
5. **No Cycle Fixing**: `fixing_cycles` state exists in FSM but no implementation present
6. **Subtask Graph Rigidity**: `_run_taskgraph_from_subtasks` skips recovery points and duration estimation entirely

### Architectural Debt

1. **Cross-Module Coupling**: `dependency.py` imports directly from `workflow.fsm`; changes to FSM require taskgraph regeneration
2. **Mixed State Semantics**: `TaskGraph.status` (validation state) conflates with `TaskGraphState` enum (lifecycle); unclear ownership
3. **Serialization Overhead**: Large JSON columns risk bloat; consider normalized `task_nodes`, `task_edges` tables

### Recommended Improvements

1. Add runtime bounds checking for config limits
2. Implement cycle resolution strategy (edge removal, node splitting)
3. Move worker/type mappings to explicit registry with priority ordering
4. Normalize `TaskGraphModel` into relational tables instead of JSON blobs
5. Add integration test suite covering full request-response-persistence cycle

---

## Appendix A: File Quick Reference

| File | Size (Lines) | Primary Concern |
|------|--------------|-----------------|
| `__init__.py` | 21 | Public API surface |
| `engine.py` | 220 | Orchestration pipeline, DB persistence |
| `decomposer.py` | 131 | Requirement parsing, classification |
| `dependency.py` | 257 | Graph construction, scheduling algorithms |
| `validator.py` | 128 | Cycle detection, integrity checks |
| `models.py` | 113 | Domain entities, dataclasses |
| `config.py` | 49 | Environment configuration |
| `states.py` | 87 | Lifecycle FSM |
| `migration.py` | 47 | Database setup |

---

## Appendix B: Command-Line Debugging

### Inspect Config Values
```bash
AIC_TASKGRAPH_ENABLED=true \
AIC_TASKGRAPH_RECOVERY_INTERVAL=3 \
python -c "from taskgraph.config import taskgraph_config; print(taskgraph_config)"
```

### Check FSM Phase Alignment
```python
from taskgraph.dependency import DependencyAnalyzer
from workflow.fsm import PHASE_WORKERS, PHASE_ORDER
print("Phase order:", PHASE_ORDER)
print("Worker phases:", {p: [w["worker"] for w in ws] for p, ws in PHASE_WORKERS.items()})
```

### Validate Generated Graph
```python
from storage.database import get_session
session = await get_session()
graph = await session.execute(select(TaskGraphModel).order_by(TaskGraphModel.created_at.desc()).limit(1))
print(json.dumps(graph.scalar_one().__dict__, indent=2, default=str))
```

---

*This codemap provides complete technical documentation of the Task Graph Engine module for developer reference, onboarding, and architectural audit.*

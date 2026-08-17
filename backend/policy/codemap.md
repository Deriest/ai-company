# Policy Module Codemap

## Responsibility

The `policy/` module implements the **Policy Decision Point (PDP)** for the AIC Platform's authorization framework. It provides a centralized gatekeeper that evaluates ALL actions before execution, ensuring no unauthorized operations proceed through the system. The module enforces security policies using a decision-based architecture with three possible outcomes: `ALLOW`, `DENY`, or `REQUIRE_APPROVAL`.

**Key Responsibilities:**
- Centralized access control enforcement across all worker types and task phases
- Sensitive resource protection via path-based approval requirements
- Role-based access control (RBAC) enforcement for user actions
- File scope isolation to prevent workers from accessing unauthorized resources
- Terminal state protection to prevent modifications to completed/blocked/cancelled tasks
- Worker-phase validation to ensure proper execution order in the workflow lifecycle

---

## Design Patterns

### 1. Strategy Pattern - Policy Evaluation Pipeline
The `PolicyEngine.evaluate()` method implements a cascading strategy pattern with seven sequential evaluation stages:
1. **Hard Denial Filter** - Immediate block on dangerous patterns
2. **Approval Threshold Filter** - Identify actions requiring human oversight
3. **User Context Validation** - Account status and role checks
4. **Resource Scope Enforcement** - File access boundary checks per worker type
5. **Sensitive Path Detection** - Critical file protection layer
6. **Task State Guardian** - Terminal state immutability enforcement
7. **Phase Validity Checker** - Workflow phase compliance validation

Each stage acts as an independent policy strategy that can short-circuit evaluation with a denial or approval requirement.

### 2. Singleton Pattern - Global Policy Instance
```python
policy = PolicyEngine()  # Line 182
```
A module-level singleton provides a shared policy evaluation instance across all consumers (`conversation.engine`, test suites). This ensures consistent policy application and enables dependency injection for testing.

### 3. Command Pattern Support
Actions are evaluated as strings (e.g., `"task.execute"`, `"git push --force"`) which represent command invocations. The policy engine decouples command invocation from permission verification, allowing:
- Centralized security policy management
- Decoupled command semantics from enforcement logic
- Testable action strings independent of execution context

### 4. Rule-Based Configuration Pattern
Static configuration dictionaries define policy rules:
- `FILE_SCOPE`: Maps worker types to allowed file path glob patterns
- `SENSITIVE_PATHS`: Protected resources requiring approval
- `ALWAYS_APPROVAL`: Actions mandating human review
- `ALWAYS_DENIED`: Forbidden operations with no bypass

This data-driven approach separates policy rules from enforcement logic.

### 5. Guard Clause Pattern
Multiple early-return guards protect against invalid states:
```python
if denied.lower() in action.lower():
    return PolicyResult(decision=Decision.DENY, ...)
```

### 6. Composite Decision Object Pattern
`PolicyResult` encapsulates the outcome with metadata:
- Primary decision (`decision: Decision`)
- Explanatory reasoning (`reason: str`)
- Required approvers (`required_approvals: list[str]`)
- Convenience properties (`allowed`, `needs_approval`)

### 7. Type-Safe Enum Pattern
`Decision` enum uses string values for API compatibility while maintaining type safety:
```python
class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
```

---

## Data & Control Flow

### Input Parameters
| Parameter | Type | Description | Nullable |
|-----------|------|-------------|----------|
| `action` | `str` | Command/action string (e.g., `"task.execute"`, `"git push --force"`) | No |
| `user` | `User` | User performing the action | Yes |
| `task` | `Task` | Task being modified | Yes |
| `worker_type` | `str` | Worker classification (`coding`, `planner`, `review`, `testing`, `deployment`) | Yes |
| `resource` | `str` | Resource identifier (file path or `task:<id>` URI) | Yes |
| `context` | `dict` | Additional evaluation context | Yes |

### Evaluation Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              PolicyEngine.evaluate()                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  1. HARD DENIAL FILTER                        │
        │  - Check ALWAYS_DENIED patterns               │
        │  - Example: "git push --force", "| bash"      │
        └───────────────────────────────────────────────┘
                              │
                   [DENY → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  2. APPROVAL THRESHOLD                        │
        │  - Check ALWAYS_APPROVAL actions              │
        │  - Example: "deploy", "release", "delete"     │
        └───────────────────────────────────────────────┘
                              │
                   [REQUIRE_APPROVAL → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  3. USER CONTEXT VALIDATION                   │
        │  - Check user.is_active                       │
        │  - Validate role permissions                  │
        │  - Block WORKER role from management actions  │
        └───────────────────────────────────────────────┘
                              │
                   [DENY → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  4. RESOURCE SCOPE ENFORCEMENT                │
        │  - Skip if resource starts with "task:"       │
        │  - Match against FILE_SCOPE[worker_type]      │
        │  - Glob patterns: src/**, test/**, etc.       │
        └───────────────────────────────────────────────┘
                              │
                   [DENY → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  5. SENSITIVE PATH DETECTION                  │
        │  - Match against SENSITIVE_PATHS globs        │
        │  - Examples: .env, *.pem, docker-compose.yml  │
        └───────────────────────────────────────────────┘
                              │
                   [REQUIRE_APPROVAL → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  6. TASK STATE GUARDIAN                       │
        │  - Block on terminal states                   │
        │  - States: completed, cancelled, blocked, failed│
        └───────────────────────────────────────────────┘
                              │
                   [DENY → Exit]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │  7. WORKER-PHASE VALIDATION                   │
        │  - Import workflow.fsm.normalize_phase()      │
        │  - Call validate_worker_for_phase()           │
        │  - Ensure worker allowed in current phase     │
        └───────────────────────────────────────────────┘
                              │
                   [DENY → Exit]
                              │
                              ▼
                    [ALLOW → Default]
                              │
                              ▼
        ┌───────────────────────────────────────────────┐
        │           Return PolicyResult                 │
        │  - decision: ALLOW                            │
        │  - reason: ""                                 │
        │  - required_approvals: None                   │
        └───────────────────────────────────────────────┘
```

### Output Specification

**Return Type:** `PolicyResult`

```python
@dataclass
class PolicyResult:
    decision: Decision          # ALLOW | DENY | REQUIRE_APPROVAL
    reason: str                 # Human-readable explanation
    required_approvals: list[str]   # List of approver roles/user IDs
```

**Output Properties:**
- `.allowed` → `True` if decision is `ALLOW`
- `.needs_approval` → `True` if decision is `REQUIRE_APPROVAL`

### Helper Functions

#### `_match_glob(path: str, pattern: str) -> bool`
Custom glob matcher supporting `**` for recursive matching:
- Converts `src/**` into prefix/suffix matching
- Falls back to `fnmatch.fnmatch()` for standard patterns
- Used by both file scope and sensitive path checks

---

## Integration Points

### Direct Dependencies

| Module | Import Location | Usage |
|--------|-----------------|-------|
| `storage.models` | Line 11 | `Task`, `User`, `Role`, `TaskStatus`, `WorkerType` - entity models |
| `workflow.fsm` | Line 153 | `validate_worker_for_phase()`, `normalize_phase()` - phase validation |
| `logging` | Line 9 | `logger = logging.getLogger("aic.policy")` |

### Consumer Modules

| Consumer | Import Statement | Integration Purpose |
|----------|------------------|---------------------|
| `backend/conversation/engine.py` | Line 25 | `from policy.engine import policy, Decision` | Evaluate intent-based actions during chat processing |
| `backend/tests/test_policy.py` | Line 11 | Unit tests for policy rules |
| `backend/tests/test_adversarial.py` | Line 17 | Security penetration testing |
| `backend/tests/test_e2e.py` | Line 115 | End-to-end integration validation |
| `backend/tests/test_qa_worker_fixes.py` | Lines 138,144,150,156 | Worker fix validation |

### External Interface

The policy module exposes a single public interface:

```python
from policy.engine import policy  # Singleton instance

result = policy.evaluate(
    action="task.execute",
    user=current_user,
    task=current_task,
    worker_type="coding",
    resource="task:abc123",
    context={"session_id": "xyz"}
)
```

**Usage Pattern:**
```python
if result.allowed:
    proceed_with_action()
elif result.needs_approval:
    route_to_approval_flow(result.required_approvals)
else:
    log_denial_result(result.reason)
    block_execution()
```

### Data Model References

#### `storage.models.User` Fields Referenced
- `is_active` → Line 104: Account status check
- `role` → Line 111: Role-based permission validation

#### `storage.models.Task` Fields Referenced
- `status` → Line 144: Terminal state detection
- Phase semantics from `context.phase_semantics` → Implicit via FSM integration

#### `storage.models.Role` Enumeration
Used to enforce:
- `WORKER.value` cannot execute `task.create`, `task.cancel`, `project.*` actions

#### `storage.models.WorkerType` Enumeration
Maps to `FILE_SCOPE` dictionary keys:
- `coding`: Access to `src/**`, `lib/**`, `test/**`, `tests/**`, config files
- `planner`: Empty scope (no file access)
- `review`: Empty scope (read-only)
- `testing`: Restricted to `test/**`, `tests/**`, `spec/**`
- `deployment`: Limited to `Dockerfile`, `docker-compose.yml`, `.env.example`, `deploy/**`

### Security Boundaries

1. **Action String Sanitization**: All actions undergo case-insensitive pattern matching against forbidden commands
2. **Path Isolation**: Workers restricted to specific directory trees via glob matching
3. **State Immutability**: Terminal task states completely protected from modification attempts
4. **Workflow Compliance**: Worker-type transitions validated against FSM state machine
5. **Audit Trail**: All policy decisions logged via `logger.warning()` for denied actions

### Known Implementation Notes

#### M2 FIX (Line 117-131)
File scope restrictions were incorrectly applied to `task:<id>` URIs, causing false denials for coding/deployment/testing workers. The guard `not str(resource).startswith("task:")` now skips file-scope validation for task-scoped resources.

#### Lazy Imports
Imports like `workflow.fsm` and `fnmatch` occur inside methods to avoid circular dependencies and reduce startup overhead.

---

## Architectural Position

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │        Conversation Engine (intent processing)       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Dispatcher (task orchestration)         │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Policy Engine (PDP)                 │  │
│  │  ── Centralized Authorization Gatekeeper ──          │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │             Workflow FSM (state machine)             │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                Storage Layer                         │  │
│  │  User | Task | Role | Project | Conversation         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Extension Guidelines

To add new policy rules:

1. **Add to static configurations** (ALWAYS_DENIED, ALWAYS_APPROVAL, SENSITIVE_PATHS, FILE_SCOPE)
2. **Implement new evaluation stage** within `evaluate()` method following existing guard pattern
3. **Log decisions** using `logger.warning()` for audit tracking
4. **Update unit tests** in `tests/test_policy.py` covering new scenarios

---

*Generated automatically from codebase analysis. Last updated: August 2026*

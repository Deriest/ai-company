# Autonomy Module — Autonomous Execution Intelligence (v2.3.8)

## Overview

The **Autonomy** module implements self-healing, adaptive execution capabilities for the AIC Platform. It provides anomaly detection, automated recovery planning, and healing result tracking to ensure system resilience against failures.

---

## Responsibility

**Primary Role**: Autonomous Execution Intelligence Engine for fault tolerance and self-healing

**Specific Responsibilities**:
1. **Anomaly Detection**: Identify and catalog execution anomalies (timeouts, failures, deadlocks, performance issues)
2. **Recovery Planning**: Determine appropriate remediation strategies based on anomaly classification
3. **Automated Healing**: Execute recovery actions with success/failure tracking
4. **State Persistence**: Log anomaly and recovery events to database for auditability
5. **Statistics Aggregation**: Provide metrics on recovery success rates and anomaly patterns

**Design Intent**: Enable continuous operation through automated error recovery without requiring manual intervention for common failure modes.

---

## Architecture

### Component Structure

| File | Purpose | Public API |
|------|---------|------------|
| `__init__.py` | Package initialization and re-exports | `autonomy_config`, `AutonomyConfig`, `RecoveryAction`, `AnomalyDetection`, `HealingResult` |
| `config.py` | Configuration management | `AutonomyConfig`, `from_env()`, `autonomy_config` singleton |
| `models.py` | Data models for domain entities | `AnomalyDetection`, `RecoveryAction`, `HealingResult` |
| `engine.py` | Core autonomous execution engine | `AutonomyEngine`, `autonomy_engine` singleton |
| `migration.py` | Database schema migrations | `run_autonomy_migration()` |

---

## Design Patterns

### 1. Singleton Pattern (`engine.py`)
```python
# Global engine instance accessible throughout application
autonomy_engine = AutonomyEngine()
```
A lazy-initialized singleton providing centralized access to autonomy services across the platform.

### 2. Strategy Pattern (`engine.py::_determine_action_type`)
Different recovery strategies selected based on anomaly type classification:
- **timeout/failure** → `retry` strategy
- **deadlock/performance** → `replan` strategy
- **resource** → `escalate` strategy

### 3. Template Method Pattern (`engine.py::handle_anomaly`)
Standardized pipeline orchestration:
1. `detect_anomaly()` - Capture failure state
2. `plan_recovery()` - Select remediation strategy
3. `execute_recovery()` - Execute and validate action

### 4. Builder Pattern (Data Models - `models.py`)
Idempotent ID generation via `__post_init__`:
```python
def __post_init__(self):
    if not self.id:
        self.id = f"ANOM-{uuid4().hex[:8].upper()}"
```

### 5. Configuration Management Pattern (`config.py`)
Environment-driven configuration with type-safe parsing:
- `_env_bool()` / `_env_int()` helpers
- Class method `from_env()` constructs typed config from OS environment

---

## Data & Control Flow

### Entry Points

#### 1. External Input Sources
- **API Routes** (`backend/routes/autonomy.py`): POST `/detect`, POST `/handle`, GET `/stats`
- **Runtime Executor** (`runtime/executor.py::process_task_with_hooks`): Anomaly injection on task failure
- **Direct Import**: Any module can instantiate `AutonomyEngine(session)` or use `autonomy_engine` singleton

#### 2. Detection Pipeline
```
Input → detect_anomaly() → [Persist] → Return AnomalyDetection
     ├─ anomaly_type (string): timeout/failure/deadlock/performance/resource
     ├─ severity (string): low/medium/high/critical
     ├─ description (string): Human-readable explanation
     └─ affected_component (string): Component identifier
```

#### 3. Recovery Planning
```
AnomalyDetection → _determine_action_type() → RecoveryAction
                                        ↓
                    action_type: retry/replan/escalate/abort
                    target: affected_component
                    parameters: {anomaly_id}
                    reason: Contextual recovery rationale
```

#### 4. Execution Pipeline
```
RecoveryAction → execute_recovery() → HealingResult
                                         ↓
                   success: Boolean outcome
                   attempts: Retry count
                   details: Outcome description
                   anomaly_id: Correlating anomaly reference
```

#### 5. Complete Workflow
```
handle_anomaly() → detect → plan → execute → return HealingResult
```

### Exit Points

- **`HealingResult`** object: Primary output containing success status
- **Database persistence**: `anomaly_log` and `recovery_log` tables (via migration)
- **Logger events**: `aic.autonomy` logger emits warning/info messages
- **`get_stats()`**: Returns `{total_anomalies, total_recoveries, success_rate}`

---

## Integration Points

### Dependencies

#### Internal Dependencies
| Module | Dependency Type | Usage |
|--------|----------------|-------|
| `storage.models` | Runtime import | `AnomalyLog`, `RecoveryLog` entities |
| `storage.database` | Indirect | AsyncSession dependency injection |

#### External Dependencies
| Package | Purpose |
|---------|---------|
| `sqlalchemy.ext.asyncio` | Async database session handling |
| `dataclasses` | Record-type data models |
| `datetime` | Timestamp tracking |
| `uuid` | Unique identifier generation |

### Consumer Modules

#### 1. API Layer (`backend/routes/autonomy.py`)
Endpoints exposed for external consumption:
```python
POST /api/autonomy/detect   # Detect and log anomaly
POST /api/autonomy/handle   # Full anomaly-to-healing pipeline
GET  /api/autonomy/stats    # Recovery statistics
```

Auth requirement: `require_current_user` middleware

#### 2. Runtime Executor (`runtime/executor.py::process_task_with_hooks`)
Error recovery hook invoked on task failure:
```python
# WP-07: Autonomy Engine error recovery hook
await autonomy_engine.detect_anomaly(
    anomaly_type="task_failure",
    severity="high",
    description=f"Task {task.id[:8]} failed: {block_reason}",
    affected_component="runtime_executor",
)
```
Non-critical failure: errors logged but do not block execution.

#### 3. Tests
- `tests/test_autonomy.py`: Unit tests for engine, config, models
- `tests/test_api_routes.py`: API route validation tests
- `tests/test_validation.py`: Input validation tests

### Database Integration

#### Schema Migration (`migration.py::run_autonomy_migration`)
Creates two core tables:

**`anomaly_log`**:
```sql
id TEXT PRIMARY KEY
anomaly_type TEXT NOT NULL
severity TEXT NOT NULL
description TEXT NOT NULL
affected_component TEXT DEFAULT ''
detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- Index: idx_anomaly_log_type ON anomaly_log(anomaly_type)
```

**`recovery_log`**:
```sql
id TEXT PRIMARY KEY
anomaly_id TEXT
action_type TEXT NOT NULL
success BOOLEAN DEFAULT FALSE
details TEXT DEFAULT ''
attempts INTEGER DEFAULT 0
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### Model Mapping
| Domain Model | Database Table |
|--------------|----------------|
| `AnomalyDetection` | `anomaly_log` |
| `RecoveryAction` | `recovery_log` (via `HealingResult`) |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AIC_AUTONOMY_ENABLED` | `true` | Enable/disable autonomy features |
| `AIC_AUTONOMY_MAX_RECOVERY` | `3` | Maximum recovery attempt count |
| `AIC_AUTONOMY_ANOMALY_DETECTION` | `true` | Toggle anomaly detection |
| `AIC_AUTONOMY_SELF_HEALING` | `true` | Enable self-healing actions |
| `AIC_AUTONOMY_ESCALATION_TIMEOUT` | `300` | Escalation timeout in seconds |

### Runtime Behavior

When `autonomy_config.enabled == false`:
- `detect_anomaly()` returns bare `AnomalyDetection` without DB persistence
- No logging occurs
- Engine functionality remains callable but silent

---

## Key Classes

### `AutonomyEngine`
**Constructor**: `__init__(self, session: AsyncSession | None = None)`

**Async Methods**:
- `detect_anomaly(...) → AnomalyDetection`
- `plan_recovery(anomaly) → RecoveryAction`
- `execute_recovery(action) → HealingResult`
- `handle_anomaly(...) → HealingResult`

**Sync Methods**:
- `get_stats() → dict`: Return recovery metrics

**Internal State**:
- `self._anomalies`: List of detected anomalies
- `self._recovery_actions`: Logged recovery plans
- `self._healing_results`: Recorded healing outcomes

### `AnomalyDetection`
Records deviation from expected execution behavior:
- Auto-generated ID format: `ANOM-{8-char-hex}`
- Severity levels: `low`, `medium`, `high`, `critical`

### `RecoveryAction`
Represents planned remediation:
- Action types: `retry`, `replan`, `escalate`, `abort`
- Contains contextual parameters and reasoning

### `HealingResult`
Outcome record from recovery execution:
- Links to source anomaly via `anomaly_id`
- Tracks attempt count and success boolean

---

## Error Handling

### Critical Failures
- Database migration exceptions → rollback + re-raise
- Session flush failures → silently ignored (non-critical path)

### Non-Critical Failures
- Autonomy engine hook failures in executor → logged as warnings, continue execution
- Config parsing errors → fallback to defaults

---

## Metrics & Observability

### Logging Categories
- `aic.autonomy`: Main engine operations
- `aic.autonomy.migration`: Migration lifecycle events
- `aic.autonomy.api`: API route activity

### Statistics Output (`get_stats`)
```json
{
  "total_anomalies": <int>,
  "total_recoveries": <int>,
  "total_healings": <int>,
  "success_rate": <float 0.0-1.0>
}
```

---

## Testing Coverage

- **Unit Tests**: Config parsing, model instantiation, engine logic
- **Integration Tests**: API endpoint behavior, async session handling
- **Validation Tests**: Input sanitization and type constraints

---

## Future Considerations

1. **Escalation Logic**: Current implementation marks escalation as always-failed; future work required for human-in-the-loop integration
2. **Retry Policies**: Fixed single-attempt recovery; exponential backoff/configurable retries pending
3. **Recovery Validation**: Success evaluation currently heuristic-based; production requires actual recovery attempt verification
4. **Performance**: In-memory lists (`_anomalies`, `_recovery_actions`) may require pagination for high-volume deployments

# Verification Engine — Codemap

> **Location:** `/backend/verification/`  
> **Version:** v2.3.6  
> **Last Updated:** August 10, 2026

---

## Overview

The Verification Engine is an autonomous quality assurance module that validates worker-produced output against engineering brief acceptance criteria and predefined quality standards. It employs a state machine-driven orchestration pattern to systematically analyze task results, extract keyword-based traceability signals, compute composite quality scores, and persist verification outcomes.

---

## 1. Responsibility

### Primary Role

The `verification` package implements a **declarative verification service** responsible for:

- **Requirement Traceability**: Mapping functional requirements and acceptance criteria from `EngineeringBrief` records to task output via keyword extraction and coverage analysis.
- **Quality Scoring**: Computing multi-dimensional quality metrics (code completeness, test presence, documentation markers, security patterns) using regex-based pattern detection.
- **State Machine Orchestration**: Enforcing a linear verification workflow through explicit state transitions (`VerificationState` enum).
- **Regression & Security Analysis**: Detecting negative indicators (e.g., error traces, breaking change keywords) and security-related patterns in task outputs.
- **Persistence Layer**: Writing verification reports to the `verification_sessions` database table via SQLAlchemy async session.

### Secondary Roles

- Configuration management via environment variables (`AIC_VERIFICATION_*`).
- Human-readable message generation for downstream user feedback.
- Idempotent report generation via UUID-based verification IDs.

---

## 2. Design Patterns

| Pattern | Location | Description |
|---------|----------|-------------|
| **State Machine** | `states.py`, `engine.py` | Linear workflow enforced by `TRANSITIONS` mapping; validation via `can_transition()`. Terminal states prevent further transitions. |
| **Strategy** | `engine.py` | Quality scoring strategies (_score_test_coverage, _score_documentation, _score_security, _compute_regression_results) are interchangeable regex-based analyzers. |
| **Dependency Injection** | `engine.py` | `VerificationEngine` receives `AsyncSession` via constructor, enabling testable database access. |
| **Builder** | `models.py` | `VerificationReport` accumulates sub-results (requirements, acceptance, quality scores) before final materialization. |
| **Configuration-as-Dataclass** | `config.py` | `VerificationConfig` uses `@dataclass` with classmethod factory `from_env()` for type-safe config population. |
| **Singleton Config** | `config.py` | Module-level `verification_config` instance provides global read-only access to configuration. |
| **Facade** | `__init__.py` | Exports simplified public API while hiding internal implementation details. |
| **Composite Result** | `engine.py` | `VerificationResult` aggregates state, optional report, message, and structured metadata. |

### Key Implementation Details

#### State Machine Architecture (`states.py`)
```python
VerificationState = Enum {
    OUTPUT_RECEIVED → ANALYZING_OUTPUT → VERIFYING_REQUIREMENTS →
    VALIDATING_ACCEPTANCE → CHECKING_QUALITY → VERIFYING_REGRESSION →
    REVIEWING_SECURITY → GENERATING_REPORT → VERIFICATION_COMPLETE/FAILED
}
```

- States represented as str-subclassed `Enum` for serialization compatibility.
- Transition matrix `TRANSITIONS` defines valid moves per state.
- Four terminal states: `VERIFICATION_COMPLETE`, `VERIFICATION_FAILED`, `ABORTED`, `ERROR`.

#### Quality Score Weighting (`engine.py` lines 487–501)
```python
overall = (
    code_quality   * 0.35 +  # Task completion rate
    test_coverage  * 0.25 +  # Test pattern match ratio
    documentation  * 0.15 +  # Doc marker presence ratio
    security       * 0.25   # Security pattern density
)
```

#### Keyword-Based Requirement Matching (`engine.py` lines 330–411)
- Extracts meaningful words via `_extract_keywords()` (filters stop-words, minimum 2-char tokens).
- Computes per-task best-match count across all requirement keywords.
- Applies 30% coverage threshold for "passed" status.
- Provides evidence with matched keyword list and source node ID.

---

## 3. Data & Control Flow

### Entry Points

| Function | Signature | Purpose |
|----------|-----------|---------|
| `VerificationEngine.verify()` | `(brief_id: str, task_results: dict \| None)` | Main orchestration method invoked after task execution pipeline completes. |
| `VerificationConfig.from_env()` | `cls -> VerificationConfig` | Configuration factory reading from process environment. |
| `run_verification_migration()` | `(session: AsyncSession)` | One-time DB schema initialization for `verification_sessions` table. |

### Input Contracts

#### `verify()` Parameters
- **`brief_id`**: String identifier referencing `engineering_briefs.id`.
- **`task_results`**: Dictionary mapping `node_id` → task result object with shape:
  ```python
  {
      "node-xyz": {
          "status": "completed" | "failed",
          "output": str | dict,  # Worker-generated content
          "result": ...          # Alternative content key
      }
  }
  ```

#### Extraction Logic (`_extract_all_text`, `_extract_task_text`)
- Recursively collects text from keys: `output`, `result`, `content`, `summary`, `description`, `code`, `text`, `body`, `message`, `log`, `details`, `files`, `file_path`, `path`, `paths`.
- Handles nested dicts, lists, and plain strings.
- Concatenates into single corpus for acceptance criteria matching.

### Output Contracts

#### `VerificationResult` Return Structure
```python
{
    "state": str,                      # Final state value (e.g., "verification_complete")
    "report": VerificationReport,      # Optional full report on success
    "message": str,                    # User-facing summary
    "metadata": {
        "verification_id": str,        # UUID-based ID ("VER-<hex>")
        "brief_id": str,
        "overall_status": str,         # "passed", "failed", "partial"
        "quality_score": float,        # 0.0–1.0 weighted aggregate
        "quality_breakdown": {
            "code_quality": float,
            "test_coverage": float,
            "documentation": float,
            "security": float
        },
        "regression_indicators": int,
        "security_findings": int
    }
}
```

#### `VerificationReport` Schema
```python
{
    "verification_id": str,
    "brief_id": str,
    "requirements_met": [
        {"requirement_id": str, "description": str, "status": str, "evidence": str}
    ],
    "acceptance_met": [...],
    "quality_score": {
        "code_quality": float,
        "test_coverage": float,
        "documentation": float,
        "security": float,
        "overall": float
    },
    "regression_results": [{"node_id": str, "issue": str, "severity": str}],
    "security_findings": [{"node_id": str, "patterns_found": list, "detail": str}],
    "recommendations": [str],
    "blocking_issues": [str],
    "overall_status": str,
    "created_at": datetime
}
```

### Data Persistence Flow

1. **Read Engineering Brief**: `select(EngineeringBriefModel).where(id == brief_id)` (line 297–299).
2. **Extract Criteria**: `brief_model.acceptance_criteria` and `functional_requirements`.
3. **Compute Scores**: Generate `QualityScore` and analysis findings.
4. **Persist Report**: Instantiate `VerificationSession` ORM model (line 591–613), add to session, flush.
5. **Transition Terminal State**: Update internal `_current_state` based on `overall_status`.

### State Transitions Summary

```
OUTPUT_RECEIVED (entry)
    ↓
ANALYZING_OUTPUT (corpus extraction, task counting)
    ↓
VERIFYING_REQUIREMENTS (per-req keyword matching)
    ↓
VALIDATING_ACCEPTANCE (criteria coverage check)
    ↓
CHECKING_QUALITY (multi-metric scoring)
    ↓
VERIFYING_REGRESSION (negative pattern scan)
    ↓
REVIEWING_SECURITY (security pattern enumeration)
    ↓
GENERATING_REPORT (accumulate recommendations/blockers)
    ↓
├─ VERIFICATION_COMPLETE (all checks passed)
└─ VERIFICATION_FAILED (any blocker detected)
```

Error paths can transition to `ERROR` or `ABORTED` from any intermediate state.

---

## 4. Integration Points

### External Dependencies

| Dependency | Usage | Import Path |
|------------|-------|-------------|
| **SQLAlchemy Core** | Async session management, ORM models | `sqlalchemy`, `sqlalchemy.ext.asyncio` |
| **storage.models** | `EngineeringBriefModel`, `VerificationSession` entities | `from storage.models import ...` |

### Consuming Modules

| Consumer | Invocation Context | Purpose |
|----------|-------------------|---------|
| **Task Dispatcher / Orchestrator** | After task graph execution completes | Trigger verification of worker output against brief criteria. |
| **API Controllers** | POST `/verification/run` (assumed) | Expose verification endpoint to external clients. |
| **Background Workers** | Periodic re-verification jobs | Re-analyze historical task results if needed. |

### Database Schema Integration

```sql
-- Table: verification_sessions
CREATE TABLE verification_sessions (
    id TEXT PRIMARY KEY,              -- verification_id (UUID hex)
    brief_id TEXT NOT NULL,           -- FK to engineering_briefs
    requirements_met TEXT DEFAULT '[]', -- JSON-encoded list
    acceptance_met TEXT DEFAULT '[]',   -- JSON-encoded list
    quality_score TEXT DEFAULT '{}',    -- JSON object with 5 floats
    overall_status TEXT DEFAULT 'pending',
    recommendations TEXT DEFAULT '[]',  -- JSON array of strings
    blocking_issues TEXT DEFAULT '[]',  -- JSON array of strings
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (brief_id) REFERENCES engineering_briefs(id)
);

-- Indexes: idx_verification_sessions_brief, idx_verification_sessions_status
```

### Environment Configuration Contract

| Variable | Default | Type | Meaning |
|----------|---------|------|---------|
| `AIC_VERIFICATION_ENABLED` | `True` | bool | Global toggle for engine |
| `AIC_VERIFICATION_MIN_QUALITY` | `0.7` | float | Threshold for `overall >= min_quality_score` |
| `AIC_VERIFICATION_SECURITY_CHECK` | `True` | bool | Enable regression/security scans |
| `AIC_VERIFICATION_REGRESSION_CHECK` | `True` | bool | Enable regression indicator detection |

### Exported Public API (`__init__.py`)

```python
__all__ = [
    "verification_config",        # Singleton config instance
    "VerificationConfig",         # Config dataclass
    "VerificationState",          # State enum
    "can_transition",             # Transition validator
    "is_terminal",                # Terminal state check
    "VerificationReport",         # Report dataclass
    "RequirementCheck",           # Per-criteria result
    "QualityScore",               # Quality breakdown
]
```

---

## File Manifest

| File | Lines | Responsibility |
|------|-------|----------------|
| `__init__.py` | 19 | Public API facade, module exports |
| `config.py` | 47 | Environment-backed configuration factory |
| `models.py` | 73 | Immutable dataclasses for reports and scores |
| `states.py` | 96 | State machine definition and helpers |
| `engine.py` | 666 | Core orchestrator, extraction, scoring, persistence |
| `migration.py` | 44 | Database schema bootstrap |

---

## Quality Metrics Reference

| Metric | Calculation | Range | Threshold |
|--------|-------------|-------|-----------|
| **Code Quality** | `completed_tasks / total_tasks` | 0.0–1.0 | N/A |
| **Test Coverage** | `_score_test_coverage()` hit ratio | 0.0–1.0 | <0.5 → warning |
| **Documentation** | `_score_documentation()` hit ratio | 0.0–1.0 | <0.5 → warning |
| **Security** | `_score_security()` hit ratio | 0.0–1.0 | <0.5 → warning |
| **Overall Score** | Weighted average of above | 0.0–1.0 | ≥`min_quality_score` (0.7) |

---

## Regex Pattern Catalogue

| Pattern | Variables | Match Examples |
|---------|-----------|----------------|
| `_TEST_PATTERNS` | test coverage | `def test_`, `describe(`, `pytest`, `.spec.`, `@Test` |
| `_DOC_PATTERNS` | documentation | `README`, `docstring`, `///`, `@param`, `"""` |
| `_SECURITY_PATTERNS` | security indicators | `authenticate`, `sanitize`, `encrypt`, `csrf`, `rbac`, `validation` |
| `_REGRESSION_NEGATIVE_PATTERNS` | regression risks | `broken`, `regress`, `fail`, `error`, `backward.compat`, `deprecated` |

---

*Generated automatically from codebase analysis.*

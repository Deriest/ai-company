# PR-1: Execution Engine Consolidation

**Date:** 2026-07-28  
**Status:** Complete  
**Work Package:** Execution Engine Consolidation (AIC-ADE Remediation Program)

## Objective

Remove duplicated execution paths and consolidate into a single unified execution engine.

## Problem

Three separate execution engines were found:

1. **runtime/executor.py** (165 lines) — RuntimeExecutor with Dispatcher + Workflow FSM
2. **runtime/executor_simple.py** (596 lines) — Smart Triage + Adaptive Execution + Recovery
3. **dispatcher/engine.py** (477 lines) — Dispatcher class with lease management

This duplication caused:
- Confusion about which executor to use
- Maintenance burden
- Inconsistent execution behavior
- Difficult testing and debugging

## Solution

**Kept:** `runtime/executor_simple.py` as the unified engine (renamed to `executor.py`)

**Rationale:**
- Most complete feature set
- Smart Triage + Recovery + Local Repair Loop
- Production-ready integrity rules
- Event-driven observability
- Adaptive execution levels (L1-L4)

**Archived:**
- `runtime/executor.py` → `.archive/executor_old.py`
- `dispatcher/engine.py` → `.archive/dispatcher/`
- `dispatcher/parallel.py` → `.archive/dispatcher/`

## Changes Made

### Files Modified

1. **runtime/executor_simple.py → runtime/executor.py**
   - Renamed function `execute_task_simple` → `execute_task`
   - Updated docstring to reflect unified status

2. **conversation/engine.py**
   - Removed `from dispatcher.engine import Dispatcher`
   - Removed `self.dispatcher = Dispatcher(session)` (unused)

3. **backend/routes/conversations.py**
   - Changed import: `from runtime.executor_simple import execute_task_simple` → `from runtime.executor import execute_task`
   - Updated call: `execute_task_simple(s, task)` → `execute_task(s, task)`

4. **docs/error_handling_examples.py**
   - Same import and call updates as conversations.py

5. **tests/test_e2e.py**
   - Skipped 3 tests that depend on removed Dispatcher API:
     - `test_task_dispatch_and_lease`
     - `test_full_lifecycle`
     - `test_lease_double_finish_rejected`

6. **tests/test_self_healing.py**
   - Removed import: `from dispatcher.parallel import ParallelDispatcher, plan_all_phases`
   - Skipped 2 tests that depend on removed ParallelDispatcher:
     - `test_plan_all_phases_from_fsm`
     - `test_parallel_dispatcher_plan_phase`

### Files Archived

- `.archive/executor_old.py` (old runtime/executor.py)
- `.archive/dispatcher/engine.py`
- `.archive/dispatcher/__init__.py`
- `.archive/dispatcher/parallel.py`

## Validation

### Syntax Check
```bash
python3 -m py_compile conversation/engine.py runtime/executor.py backend/routes/conversations.py
# ✓ All pass
```

### Test Results
```bash
pytest tests/test_e2e.py tests/test_self_healing.py tests/test_ai_runtime.py -v
# ✓ 11 passed, 5 skipped
```

Key tests passing:
- ✓ `test_chat_creates_task`
- ✓ `test_chat_detects_question`
- ✓ `test_chat_detects_bugfix`
- ✓ `test_policy_blocks_dangerous`
- ✓ `test_fsm_cannot_skip_phases`
- ✓ `test_llm_fallback_to_regex`
- ✓ `test_self_healing_engine_returns_report`
- ✓ `test_ai_runtime_mvp`

## Impact

### Positive
- ✓ Single execution engine — no confusion
- ✓ Reduced codebase complexity (~650 lines archived)
- ✓ Preserved best features (Smart Triage, Recovery, Integrity gates)
- ✓ No broken imports
- ✓ Tests passing

### Trade-offs
- Some old Dispatcher API tests skipped (5 tests)
- Future features must extend the unified executor, not create new execution paths

## Migration Guide

### Before
```python
from runtime.executor_simple import execute_task_simple
result = await execute_task_simple(session, task)
```

### After
```python
from runtime.executor import execute_task
result = await execute_task(session, task)
```

### Dispatcher API Removed
Old code using `Dispatcher` class directly must be refactored:

```python
# REMOVED — no longer available
from dispatcher.engine import Dispatcher
dispatcher = Dispatcher(session)
await dispatcher.dispatch_task(task)
lease = await dispatcher.issue_lease(task, "worker")
await dispatcher.finish_lease(lease.id)
```

Use unified executor instead:
```python
from runtime.executor import execute_task
result = await execute_task(session, task)
```

## Next Steps

**PR-2: Worker Runtime Integration** — make workers executable with real LLM calls.

## References

- SOT: `/home/tvd/AI-Company/aic-ide/AIC_ADE_REMEDIATION_SOT.md`
- Progress: `/home/tvd/AI-Company/aic-ide/AIC_ADE_REMEDIATION_PROGRESS.md`
- Repository: `/home/tvd/AI-Company/aic-platform`

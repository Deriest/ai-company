# 50 — Workflow Specification

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Workflow 1: Conversation → Mission Creation

### Flow

```
User types in Hermes
  → ConversationEngine.process_message()
  → _detect_intent() (regex-based, deterministic)
  → If INTENT_TASK_REQUEST:
    → _evaluate_intake_completeness() checks 6 mandatory fields
    → If incomplete: return _handle_chat_llm() (ask clarifying questions)
    → If complete + not forced: store pending_task in conversation.context, propose plan
    → If complete + forced: create task via _handle_task_confirm()
  → If INTENT_TASK_CONFIRM:
    → Check pending_task in conversation.context
    → Create Task in database
    → Return confirmation with task ID
```

### Evidence

- Source: `conversation/engine.py:312-380`
- Intent detection: regex patterns (lines 224-258)
- Intake checklist: `_evaluate_intake_completeness()` (lines 281-299)
- Force detection: `_user_forces_task_creation()` (lines 301-310)

## Workflow 2: Mission Dispatch → Execution

### Flow

```
User clicks "Dispatch" in Mission Workspace
  → POST /api/tasks/{id}/dispatch
  → BackgroundTasks.add_task(_run_task_background, task_id)
  → _run_task_background():
    → RuntimeExecutor.execute_task(task_id)
    → plan_all_phases() generates parallel_worker_plan
    → For each phase:
      → issue_lease(worker_type, task_id, phase)
      → Worker calls LLM with assembled context
      → Worker produces deliverables in task workspace
      → Lease completes → next phase
    → Self-healing monitors stuck tasks
```

### Evidence

- Source: `backend/routes/tasks.py:286-303`
- Executor: `runtime/executor.py`, `runtime/executor_simple.py`
- Parallel: `dispatcher/parallel.py`
- Leases: `storage/models.py:260` (`Lease` model)

## Workflow 3: Provider Configuration

### Flow

```
Settings → Provider Settings → Add Provider
  → Form: name, base_url, API key, model
  → POST /api/llm/providers
  → Backend: create LLMProviderConfig, register in ProviderManager
  → "Test Connection": POST /api/llm/providers/{id}/test
  → Backend: list_models() via provider adapter
  → Returns model count + metadata
  → Adaptive runtime registers capabilities
```

### Evidence

- Source: `backend/routes/llm.py:99-152`
- Provider manager: `llm/provider.py`
- Adaptive: `runtime/adaptive.py:161-204` (capabilities_from_metadata)

## Workflow 4: Model Discovery & Adaptive Runtime

### Flow

```
Provider registered → capabilities_from_metadata(provider, model, metadata)
  → ModelCapabilities (context_window, tool_calling, reasoning, etc.)
  → generate_runtime_profile(capabilities)
  → ContextPolicy (small/medium/large)
  → MemoryPolicy (session/checkpoint/repository/semantic/hybrid)
  → WorkerPolicy (planning_depth, parallel_workers, verification)
  → AdaptiveRuntimeProfile stored in registry
  → Injected into task context via apply_worker_policy()
  → Serialized in worker prompt via runtime_prompt_directive()
```

### Evidence

- Source: `runtime/adaptive.py:207-293`
- Registration: `runtime/adaptive.py:296-320` (AdaptiveRuntimeRegistry)
- Injection: `runtime/executor_simple.py`, `agents/context_assembly.py`

## Workflow 5: Self-Healing

### Flow

```
FastAPI lifespan starts → run_startup_self_heal()
  → Detects: stuck tasks (non-terminal, no recent lease)
  → Detects: stale leases (active, no heartbeat)
  → Repairs: reset stuck tasks to "blocked"
  → Repairs: expire stale leases
  → POST /api/console/self-heal (manual trigger)
  → Returns: {issues_found, repairs_applied, redispatched_task_ids}
```

### Evidence

- Source: `backend/self_healing.py`
- Lifespan: `backend/main.py`
- Endpoint: `backend/routes/console.py`

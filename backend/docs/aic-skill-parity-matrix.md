# AIC Skill ↔ AIC Platform Parity Matrix

**Generated:** 2026-07-21  
**Reference:** `/home/tvd/AI-Company/aic-skill` (Node.js, file-based, event-driven)  
**Platform:** `/home/tvd/AI-Company/aic-platform` (Python/SQLAlchemy, database-backed, async)

---

## Executive Summary

The AIC Platform has **structural parity** with the Skill reference for the core FSM phase lifecycle, barrier system, and lease management. However, significant **operational subsystems** present in the Skill reference are **entirely absent** from the Platform — most critically the recovery/rework loop, pipeline orchestrator, and post-execution systems. The Platform adds capabilities not in the Skill (approval gates, conversation engine, LLM-powered workers, REST API) which represent platform-specific extensions.

**Overall Parity: ~55%** — Core FSM mechanics are ported; orchestration depth is missing.

---

## 1. FSM Phase Lifecycle

| Feature | AIC Skill (reference) | AIC Platform | Parity |
|---|---|---|---|
| Phase order | `CREATED → INVESTIGATE → PLANNING → IMPLEMENTATION → VERIFICATION → CLOSEOUT → COMPLETE` | `created → investigate → planning → implementation → verification → closeout → completed` | ✅ **MATCH** (case normalization: UPPER in Skill, lower in Platform) |
| Terminal states | `COMPLETE, CANCELLED, BLOCKED` | `completed, cancelled, blocked` | ✅ **MATCH** |
| Phase normalization | `normalizePhase()` → uppercase | `normalize_phase()` → lowercase | ⚠️ **SEMANTIC MATCH** — opposite conventions, functionally equivalent |
| `validatePhase()` | Returns normalized phase or null | Returns normalized phase or None | ✅ **MATCH** |
| `nextPhase()` | Returns next in PHASE_ORDER or null | Returns next in PHASE_ORDER or None | ✅ **MATCH** |
| `isTerminal()` | Checks against TERMINAL set | Checks against TERMINAL_STATES | ✅ **MATCH** |
| `canAdvance()` | Requires barrier + pmPass; special CLOSEOUT→COMPLETE path | Requires barrier + pm + optional approval; special closeout PM gate | ✅ **MATCH** + Platform adds approval gate |
| `phaseToCurrentPhase()` | Converts phase to display string | Not implemented (progress map used instead) | ❌ **MISSING** — cosmetic, low priority |
| Extra states in Platform | N/A | `APPROVAL, TESTING, REVIEW, DOCUMENTATION, FAILED` in TaskStatus enum | ➕ **PLATFORM EXTENSION** — legacy aliases + approval phase |

### Phase Plans (Worker Mapping)

| Phase | Skill PHASE_PLANS | Platform PHASE_WORKERS | Parity |
|---|---|---|---|
| INVESTIGATE | `[pm/thinker]` | `[pm/thinker]` | ✅ |
| PLANNING | `[pm/thinker, architect/thinker, research/thinker, designer/thinker]` | `[pm/thinker, architect/thinker, research/thinker, designer/thinker]` | ✅ |
| IMPLEMENTATION | `[backend/crafter, frontend/crafter]` | `[backend/crafter, frontend/crafter]` | ✅ |
| VERIFICATION | `[qa/crafter]` | `[qa/crafter]` | ✅ |
| CLOSEOUT | `[pm/thinker]` | `[pm/thinker]` | ✅ |

**Verdict: Phase plans are 1:1 identical.**

---

## 2. Barrier System

| Feature | AIC Skill (`barrier.js`) | AIC Platform (`workflow/fsm.py` Barrier class) | Parity |
|---|---|---|---|
| `startBarrier()` | Functional, returns object with `{active, workers, completed, failed, startedAt, timeout}` | `Barrier.start()` classmethod, same fields | ✅ **MATCH** |
| `barrierSatisfied()` | Fail-closed: timeout → `timedOut=true`, returns false | `Barrier.is_satisfied()`: same fail-closed logic | ✅ **MATCH** |
| Timeout | 600,000ms (10 min) | 600s (10 min) | ✅ **MATCH** |
| `markWorkerComplete()` | Sets `completed[worker] = 'complete'` | `Barrier.mark_complete()` — same | ✅ **MATCH** |
| `markWorkerFailed()` | Sets `failed[worker] = reason` | `Barrier.mark_failed()` — same | ✅ **MATCH** |
| `resetWorkersForRepair()` | Clears completed/failed for specified workers | `Barrier.reset_for_repair()` — same | ✅ **MATCH** |
| `clearBarrier()` | Returns null | `clear_barrier()` returns None | ✅ **MATCH** |
| Serialization | Implicit (JSON checkpoint) | `to_dict()` / `from_dict()` explicit | ✅ **MATCH** — Platform is more explicit |
| Empty workers | Returns true (vacuous satisfaction) | Returns true | ✅ **MATCH** |

**Verdict: Barrier system is fully ported with identical semantics.**

---

## 3. Lease System

| Feature | AIC Skill (`lease.js`) | AIC Platform (`dispatcher/engine.py`) | Parity |
|---|---|---|---|
| `issueLease()` | Validates task, phase, worker-in-phase, tier match, paused state | Validates task, phase, worker-in-phase, policy check, stale worker detection | ✅ **MATCH** + Platform adds policy engine |
| Tier validation | D-dispatcher-03: validates tier matches PHASE_PLANS | `_worker_tier()` lookup, stored in worker config | ⚠️ **PARTIAL** — Platform stores tier but doesn't enforce tier mismatch at lease time |
| Phase validation | D-dispatcher-02: `validatePhase()` on checkpoint | `validate_worker_for_phase()` | ✅ **MATCH** |
| Lease ID format | `lease-{random hex}` | UUID-based | ⚠️ **COSMETIC DIFF** — functionally equivalent |
| Lease state tracking | In-memory `state.engine.leases[leaseId]` | DB `Lease` model with status enum | ✅ **MATCH** (different persistence) |
| `finishLease()` | Validates lease active (TOCTOU guard), exit code, artifact file validation, shell validation | Validates lease active (TOCTOU guard), exit code, artifact tracking | ✅ **MATCH** for core; Platform lacks artifact file/shell validation |
| Double-finish guard | D-dispatcher-04: checks `lease.status !== 'active'` | Checks `lease.status != ACTIVE` | ✅ **MATCH** |
| Artifact validation | `validateArtifactFile()` — min bytes, min content lines | Not implemented | ❌ **MISSING** |
| Shell validation | `runShellValidation()` — per-worker scripts | Not implemented | ❌ **MISSING** |
| Lease pruning | D-08: prune completed/failed leases for non-current tasks | Auto-retry on failure (3 retries), then block | ➕ **PLATFORM EXTENSION** — auto-retry replaces manual pruning |
| Worker status update | Sets worker.status, worker.leaseId | Sets worker.status, worker.current_task_id, worker.current_lease_id | ✅ **MATCH** |
| Event emission | `bus.emit('worker.started/completed/failed')` | `broadcast_task_event()` WebSocket | ✅ **MATCH** (different transport) |

**Verdict: Core lease lifecycle matches. Missing artifact validation subsystem.**

---

## 4. Intent / Task Management

| Feature | AIC Skill (`intent.js`) | AIC Platform (`conversation/engine.py`) | Parity |
|---|---|---|---|
| Task creation | `task.create` intent: validates title + description, creates checkpoint + context.json | `_create_task()`: creates DB Task with project link | ✅ **MATCH** at semantic level |
| Task start | `task.start` intent: validates TASK-* ID, ownership, projectDir, starts pipeline | `dispatch_task()`: advances from created, starts phase barrier | ⚠️ **PARTIAL** — Platform doesn't run full pipeline |
| Task pause | `task.pause` intent: sets `engine.paused = true` | Not implemented | ❌ **MISSING** |
| Task resume | `task.resume` intent: resumes from checkpoint phase | Not implemented | ❌ **MISSING** |
| Task cancel | `task.cancel` intent: sets CANCELLED, clears workers, prunes leases | `cancel_task()`: releases active leases, sets cancelled | ✅ **MATCH** |
| Task retry | `task.retry` intent: validates BLOCKED state, resets to requested phase | Not implemented (auto-retry in lease failure instead) | ❌ **MISSING** — different recovery model |
| Pipeline busy guard | `ctx.pipelineRunning` check | No equivalent (async DB model doesn't need it) | ➕ **PLATFORM DESIGN** — different concurrency model |
| Task ownership | Validates single active task ownership | Not enforced (DB can have multiple active tasks) | ❌ **MISSING** — design difference |
| Pipeline state sync | `syncDashboardFromCheckpoint()` | WebSocket broadcast | ✅ **MATCH** (different transport) |
| Description validation | `validateTaskDescription()` | None (relies on LLM classification) | ❌ **MISSING** |

### Intent Types Comparison

| Skill Intents | Platform Intents | Parity |
|---|---|---|
| `task.create` | `task_request` (via conversation) | ⚠️ Merged into conversation flow |
| `task.start` | `dispatch_task()` | ✅ Equivalent |
| `task.pause` | — | ❌ Missing |
| `task.resume` | — | ❌ Missing |
| `task.cancel` | `cancel_task()` | ✅ |
| `task.retry` | — | ❌ Missing |

---

## 5. PM Review Gate

| Feature | AIC Skill (`pm-review.js`) | AIC Platform | Parity |
|---|---|---|---|
| PM review execution | `runPmReview()`: scans report dir for .md artifacts, runs pm-review.sh | `set_pm_review()`: boolean flag on WorkflowState | ❌ **MAJOR GAP** — Platform has no actual PM review logic |
| Empty artifacts guard | Fail-closed: no artifacts → BLOCKED | N/A | ❌ **MISSING** |
| Mechanical validation gate | WP-3.3: `validate-framework-invariants.sh` runs before PM review | Not implemented | ❌ **MISSING** |
| PM review verdicts | PASS / REWORK / BLOCKED (exit codes 0/1/2) | Boolean `pm_review_passed` | ❌ **MISSING** — no tri-state verdict |
| Runtime gate tracking | `state.runtimeGate` with type/owner/target/status | Not implemented | ❌ **MISSING** |
| EDP (Engineering Decision Package) | Read from `.pm-last-edp.json` | Not implemented | ❌ **MISSING** |
| PM repair loop | Full `pmRepairLoop()` with recovery strategies | Not implemented | ❌ **MISSING** |
| Ship with caveats | After max recovery cycles, marks `shipWithCaveats` | Not implemented | ❌ **MISSING** |

**Verdict: PM Review is the largest gap. Platform has a boolean flag; Skill has a full quality gate with repair loop.**

---

## 6. Recovery / Rework System

| Feature | AIC Skill (`recovery.js` + `recovery-strategy.js`) | AIC Platform | Parity |
|---|---|---|---|
| Startup reconciliation | `reconcileOnStartup()`: resets stale workers, detects interrupted checkpoints, prunes stale leases | Not implemented | ❌ **MISSING** |
| Stale worker detection | Checks workers stuck in 'working' state on startup | Stale worker check at lease time (`_get_or_create_worker`) | ⚠️ **PARTIAL** — only at lease time, not on startup |
| Checkpoint interruption | Detects interrupted checkpoints, marks as `barrier_wait` or `interrupted` | Not implemented | ❌ **MISSING** |
| Recovery strategies | 5-strategy engine (retry, targeted, collaborative, refine_plan, pm_author) | Auto-retry (3 attempts) on lease failure | ❌ **MAJOR GAP** — only basic retry |
| Strategy escalation | `selectStrategy()` → `getStrategyAction()` → ship/refine/pm_author/repair | Not implemented | ❌ **MISSING** |
| Progress evaluation | `evaluateProgress()` — tracks if recovery is making progress | Not implemented | ❌ **MISSING** |
| Rework history | `cp.reworkHistory` tracking across cycles | `WorkflowState.recovery_attempts` counter only | ⚠️ **BASIC** — counter only, no history |
| Hard ceiling | `STRATEGIES.length + 2` cycles max | 3 retries max | ⚠️ **SIMPLIFIED** — hardcoded 3 |
| Consistency checker | `consistency-checker.py` compares planning artifacts before PM review | Not implemented | ❌ **MISSING** |

**Verdict: Recovery is critically deficient. Platform has basic retry; Skill has a sophisticated multi-strategy recovery engine.**

---

## 7. Pipeline Orchestrator

| Feature | AIC Skill (`pipeline.js` + `phase-runner.js`) | AIC Platform (`workflow/engine.py` + `dispatcher/engine.py`) | Parity |
|---|---|---|---|
| Phase sequence | Iterates `INVESTIGATE → PLANNING → IMPLEMENTATION → VERIFICATION → CLOSEOUT` | `advance()` moves one phase at a time | ⚠️ **DESIGN DIFF** — Skill is a loop, Platform is event-driven |
| Pipeline resume | `startFromPhase` parameter to skip completed phases | Phase history tracked in `WorkflowState.history` | ⚠️ **PARTIAL** — no explicit resume-from-phase |
| Phase execution | `runPhase()`: startBarrier → spawnWorkers → barrierCheck → pmReview | `start_phase()` → workers execute → `mark_worker_complete()` → `advance()` | ⚠️ **FRAGMENTED** — Platform splits across dispatcher calls |
| PLANNING phase split | PM spawns first → produces execution-plan.md → downstream workers spawn | Not implemented | ❌ **MISSING** |
| Execution plan | PM produces `execution-plan.md`, passed to downstream via `AIC_EXECUTION_PLAN` env | Not implemented | ❌ **MISSING** |
| Worker spawning | `phase-runner.sh` spawns OpenCode CLI instances | `BaseWorker.execute()` runs in-process via LLM | ✅ **DESIGN DIFF** — in-process vs subprocess |
| Barrier reconciliation | `reconcilePhaseBarrier()`: checks leases + artifacts for missed completions | Not implemented (relies on DB consistency) | ❌ **MISSING** — DB model avoids this need |
| Task completion | `completeTask()`: sets COMPLETE, prunes leases, triggers knowledge + postmortem | `advance()` to "completed" sets progress=100 | ⚠️ **PARTIAL** — missing knowledge/postmortem triggers |
| Knowledge capture | `triggerKnowledgeAsync()`: appends to `task-entries.json` | Not implemented | ❌ **MISSING** |
| Postmortem | `triggerPostmortemAsync()`: runs `postmortem.py` | Not implemented | ❌ **MISSING** |
| Phase failure handling | Blocks task on phase failure | `block()` / `fail()` methods available | ✅ **MATCH** (but not wired to pipeline) |

**Verdict: Platform has the primitives (phase transitions, barriers) but lacks the pipeline orchestration that ties them into an automated sequence.**

---

## 8. Worker Registry

| Worker Type | Skill (in fsm.js) | Platform (workers/base.py) | Parity |
|---|---|---|---|
| `pm` | ✅ Phase plan entry | ✅ `PMWorker` class | ✅ |
| `architect` | ✅ Phase plan entry | ✅ `ArchitectWorker` class | ✅ |
| `research` | ✅ Phase plan entry | ✅ `ResearchWorker` class | ✅ |
| `designer` | ✅ Phase plan entry | ✅ `DesignerWorker` class | ✅ |
| `backend` | ✅ Phase plan entry | ✅ `BackendWorker` class | ✅ |
| `frontend` | ✅ Phase plan entry | ✅ `FrontendWorker` class | ✅ |
| `qa` | ✅ Phase plan entry | ✅ `TestingWorker` (mapped as "qa") | ✅ |
| `coding` | Not in phase plans | ✅ `CodingWorker` (extension) | ➕ Platform extension |
| `database` | Not in phase plans | ✅ `DatabaseWorker` (extension) | ➕ Platform extension |
| `security` | Not in phase plans | ✅ `SecurityWorker` (extension) | ➕ Platform extension |
| `documentation` | Not in phase plans | ✅ `DocumentationWorker` (extension) | ➕ Platform extension |
| `deployment` | Not in phase plans | ✅ `DeploymentWorker` (extension) | ➕ Platform extension |
| `devops` | Not in phase plans | ✅ `DevOpsWorker` (extension) | ➕ Platform extension |
| `performance` | Not in phase plans | ✅ `PerformanceWorker` (extension) | ➕ Platform extension |
| `debugger` | Not in phase plans | ✅ `DebuggerWorker` (extension) | ➕ Platform extension |
| Legacy: `planner` | N/A | ✅ Maps to `PMWorker` | ➕ Platform extension |
| Legacy: `review` | N/A | ✅ `ReviewWorker` | ➕ Platform extension |
| Legacy: `testing` | N/A | ✅ Maps to `TestingWorker` | ➕ Platform extension |

**Execution model difference:** Skill workers spawn as OpenCode CLI subprocesses producing markdown artifacts. Platform workers are in-process Python classes calling LLM APIs (with OpenCode adapter for `CodingWorker`).

---

## 9. Data Models

| Concept | Skill (file-based) | Platform (SQLAlchemy) | Parity |
|---|---|---|---|
| Task | `context.json` + `engine.json` checkpoint | `Task` + `WorkflowState` models | ✅ **MATCH** (different persistence) |
| Worker state | `state.workers[name]` in-memory | `Worker` DB model | ✅ **MATCH** |
| Lease | `state.engine.leases[leaseId]` in-memory | `Lease` DB model | ✅ **MATCH** |
| Barrier | `cp.phaseBarrier` in checkpoint JSON | `WorkflowState.barrier` JSON column | ✅ **MATCH** |
| Approval | Not present | `Approval` DB model | ➕ **PLATFORM EXTENSION** |
| Project | Implicit (projectDir string) | `Project` DB model | ➕ **PLATFORM EXTENSION** |
| Conversation | Not present | `Conversation` + `Message` models | ➕ **PLATFORM EXTENSION** |
| Events | `bus.emit()` in-memory | `Event` + `AuditLog` DB models | ➕ **PLATFORM EXTENSION** |
| LLM tracking | Not present | `LLMProviderConfig` + `LLMUsageLog` | ➕ **PLATFORM EXTENSION** |
| Metrics | Not present | `Metric` DB model | ➕ **PLATFORM EXTENSION** |
| Milestone | Not present | `Milestone` DB model | ➕ **PLATFORM EXTENSION** |

---

## 10. Platform-Only Features (Not in Skill Reference)

These are **additions** the Platform makes beyond the Skill reference:

| Feature | Location | Notes |
|---|---|---|
| REST API | `backend/routes/` | Full CRUD API for tasks, workers, conversations |
| WebSocket events | `backend/routes/websocket.py` | Real-time event streaming |
| Conversation engine | `conversation/engine.py` | LLM-powered natural language interface |
| Intent detection | `conversation/engine.py` | Regex + LLM intent classification |
| Task classification | `conversation/engine.py` | Auto-classify task type and worker routing |
| Policy engine | `policy/engine.py` | RBAC policy evaluation |
| Approval workflow | `dispatcher/engine.py` | Human-in-the-loop approval gates |
| LLM provider system | `llm/provider.py` | Multi-provider, tiered model selection |
| User auth | `storage/models.py` | Users, roles, API keys |
| Dashboard UI | `frontend/` | React dashboard |
| Migration system | `alembic/` | Database migrations |

---

## 11. Gap Priority Matrix

### Critical (blocks core workflow)

| Gap | Skill Reference | Impact |
|---|---|---|
| **Pipeline orchestrator** | `pipeline.js` — automated phase sequence | No end-to-end task execution; phases must be advanced manually |
| **PM review gate** | `pm-review.js` — quality gate with verdicts | No quality enforcement; tasks advance without review |
| **Recovery/rework loop** | `pm-review.js` pmRepairLoop + `recovery-strategy.js` | No automatic recovery from failed reviews |
| **Phase runner** | `phase-runner.js` — worker spawning + barrier management | Workers not automatically spawned per phase |

### High (degrades workflow quality)

| Gap | Skill Reference | Impact |
|---|---|---|
| **Artifact validation** | `validate-artifact.js` — min bytes, content lines, shell validation | Workers can produce empty/invalid artifacts |
| **Startup reconciliation** | `recovery.js` — reconcileOnStartup | Stale state after crash not cleaned up |
| **PLANNING phase split** | `phase-runner.js` — PM-first execution plan | No structured planning; all workers spawn simultaneously |
| **Consistency checker** | `phase-runner.js` — cross-artifact consistency | Planning artifacts may conflict |
| **Knowledge capture** | `pipeline.js` — triggerKnowledgeAsync | No institutional learning |
| **Postmortem** | `pipeline.js` — triggerPostmortemAsync | No post-task analysis |

### Medium (missing safety features)

| Gap | Skill Reference | Impact |
|---|---|---|
| **Task pause/resume** | `intent.js` — task.pause, task.resume | Cannot pause long-running tasks |
| **Task retry** | `intent.js` — task.retry with phase validation | Cannot retry from specific phase |
| **Pipeline busy guard** | `intent.js` — ctx.pipelineRunning | DB model mitigates but no explicit guard |
| **Task ownership** | `intent.js` — single active task enforcement | Multiple tasks could conflict |
| **Tier enforcement at lease** | `lease.js` — D-dispatcher-03 | Tier mismatch not caught |

### Low (cosmetic / nice-to-have)

| Gap | Skill Reference | Impact |
|---|---|---|
| `phaseToCurrentPhase()` | Display string conversion | Minor — progress map serves similar purpose |
| `runtimeGate` state | Runtime gate tracking | Dashboard visibility only |
| `shipWithCaveats` flag | Marks degraded completion | No degraded completion concept |

---

## 12. Architecture Divergence Summary

| Dimension | AIC Skill | AIC Platform |
|---|---|---|
| **Runtime** | Node.js, file-based state | Python, SQLAlchemy + SQLite |
| **Concurrency** | Single pipeline, `pipelineRunning` flag | Async, DB-level coordination |
| **Worker execution** | OpenCode CLI subprocess | In-process LLM calls |
| **State persistence** | JSON checkpoints on disk | Database rows |
| **Event transport** | In-memory EventEmitter | WebSocket broadcast |
| **Quality gates** | PM review shell scripts | Boolean flag (stub) |
| **Recovery** | Multi-strategy recovery engine | 3-retry auto-retry |
| **Pipeline** | Full automated loop | Manual phase advancement |
| **User interface** | Hermes CLI skill | Web dashboard + REST API |

---

## 13. Recommended Implementation Roadmap

### Phase 1: Pipeline Foundation (Critical)
1. **Pipeline Orchestrator** — Implement `runPipeline()` equivalent that iterates phases automatically
2. **Phase Runner** — Auto-spawn workers when a phase starts, manage barrier lifecycle
3. **PM Review Gate** — Port verdict logic (PASS/REWORK/BLOCKED), at minimum boolean gate wired into `can_advance()`

### Phase 2: Quality & Recovery (High)
4. **Recovery Loop** — Basic retry with feedback (port simplified version of pmRepairLoop)
5. **Artifact Validation** — Validate worker outputs before marking complete
6. **Startup Reconciliation** — Clean stale state on server boot

### Phase 3: Workflow Depth (Medium)
7. **PLANNING Phase Split** — PM-first execution plan generation
8. **Task Pause/Resume** — Persist and restore pipeline position
9. **Knowledge Capture** — Record task outcomes for institutional learning

### Phase 4: Polish (Low)
10. **Consistency Checker** — Cross-artifact validation
11. **Postmortem** — Automated post-task analysis
12. **Runtime Gate Tracking** — Dashboard visibility

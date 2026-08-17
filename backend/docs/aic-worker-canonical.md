# AIC Worker Canonical Taxonomy

> **Source:** Deep audit of `/home/tvd/AI-Company/aic-skill` — extracted from `scripts/config.js`, `scripts/engine/fsm.js`, `references/dispatcher-core.md`, `references/dispatcher-pipelines.md`, `references/context-and-model.md`, and all reference docs.
>
> **Date:** 2026-07-21

---

## 1. Worker Tiers

| Tier | Role | Context Window | Output Limit | Typical Workers |
|------|------|---------------|-------------|-----------------|
| **Thinker** | Complex reasoning, large context analysis | 800K tokens | 64K tokens | PM, Architect |
| **Crafter** | Standard coding, focused tasks | 512K tokens | 32K tokens | All Engineers, Governor, Documentation |
| **Sprinter** | Fast/lightweight tasks | 256K tokens | 16K tokens | QA, Performance |

**Tier aliases** — workers reference `thinker`, `crafter`, `sprinter` (not model IDs). Actual models are selected during setup via `opencode.jsonc`.

---

## 2. Complete Worker Registry (15 workers)

### 2.1 Leadership / Dispatch

| Worker ID | Display Name | Tier | Department | Role | Head? |
|-----------|-------------|------|------------|------|-------|
| `dispatcher` | Dispatcher | System | Leadership | Classifies tasks, routes to workers, manages full pipeline lifecycle. Runs as Hermes directly (not spawned). | N/A |

### 2.2 Product Department

| Worker ID | Display Name | Tier | Department | Phase Ownership | Head? | Spawns |
|-----------|-------------|------|------------|----------------|-------|--------|
| `pm` | PM (Aria) | Thinker | Product | Investigate, Planning (first), Closeout (review) | Yes | research, designer |
| `architect` | Architect (Atlas) | Thinker | Product | Planning (first, before specialists) | Yes | research, multiple engineers |
| `research` | Researcher | Thinker | Product | Investigate (conditional), Planning | Yes | sub-research |

### 2.3 Engineering Department

| Worker ID | Display Name | Tier | Department | Phase Ownership | Head? | Spawns |
|-----------|-------------|------|------------|----------------|-------|--------|
| `frontend` | Frontend Engineer | Crafter | Engineering | Implementation | Yes | designer, sub-frontend |
| `backend` | Backend Engineer | Crafter | Engineering | Implementation | Yes | research, sub-backend |
| `designer` | Designer | Crafter/Thinker | Engineering | Planning (after Architect), Implementation | Yes | sub-designer |
| `infra` | Infrastructure Engineer | Crafter | Engineering | Planning | Yes | sub-infra |
| `security` | Security Engineer | Crafter | Engineering | Planning | Yes | sub-security |
| `perf` | Performance Engineer | Sprinter | Engineering | Verification | Yes | sub-perf |
| `data` | Data Architect | Crafter/Thinker | Engineering | Planning | Yes | sub-data |
| `integration` | Integration Engineer | Crafter | Engineering | Planning | Yes | sub-integration |

### 2.4 Platform / Operations Department

| Worker ID | Display Name | Tier | Department | Phase Ownership | Head? | Spawns |
|-----------|-------------|------|------------|----------------|-------|--------|
| `qa` | QA Engineer | Sprinter | Platform | Verification | Yes | sub-QA (parallel test suites) |
| `documentation` | Documentation | Crafter | Platform | Closeout (first) | Yes | sub-docs |
| `governor` | Governor | Crafter | Platform | Closeout (after Documentation) | Yes | sub-governor |

---

## 3. WORKERS Array (config.js canonical order)

```javascript
const WORKERS = [
  'pm', 'architect', 'research', 'frontend', 'backend', 'qa',
  'designer', 'infra', 'security', 'perf', 'data', 'integration',
  'documentation', 'governor', 'dispatcher',
];
```

**Total: 15 workers** (14 spawned + 1 dispatcher/Hermes)

---

## 4. Department Grouping (Dashboard Sort Order)

```
Leadership:    dispatcher, governor
Product:       pm, architect, research
Engineering:   designer, frontend, backend, infra, security, perf, data, integration
Platform:      qa, documentation
```

---

## 5. Worker State Machine (Per-Worker Lifecycle)

| State | Description |
|-------|-------------|
| Idle | Worker available, no task |
| Assigned | Task received, context not loaded |
| Running | Actively executing |
| Waiting | Blocked on external input |
| Blocked | Cannot proceed (missing dependency) |
| Sub-spawn | Head waiting for sub-workers |
| Self-Validation | Checking own output |
| Completed | Artifact generated, handoff ready |
| Failed | Non-recoverable error |
| Cancelled | Task cancelled |

### Valid State Transitions

| From | To | Trigger |
|------|----|---------|
| Idle | Assigned | Task assigned |
| Assigned | Running | Context loaded |
| Running | Waiting | External dependency |
| Waiting | Running | Dependency resolved |
| Running | Blocked | Missing dependency |
| Blocked | Running | Dependency provided |
| Running | Sub-spawn | Scope exceeds capacity |
| Sub-spawn | Running | Sub-workers complete |
| Running | Self-Validation | Execution complete |
| Self-Validation | Running | Rework needed |
| Self-Validation | Completed | Validation passes |
| Running | Failed | Non-recoverable error |
| Any | Cancelled | User/Dispatcher cancels |
| Failed | Running | Retry triggered |

---

## 6. Hierarchy & Delegation Model

### Head Worker Pattern
Every worker is a **Head** who can work AND spawn sub-workers for parallel tasks.

```
Dispatcher (Hermes)
  ├── PM (Head, Thinker) → can spawn Researcher, Designer
  ├── Architect (Head, Thinker) → can spawn Researcher, multiple Engineers
  ├── Frontend (Head, Crafter) → can spawn Designer, sub-Frontend
  ├── Backend (Head, Crafter) → can spawn Researcher, sub-Backend
  ├── QA (Head, Sprinter) → can spawn sub-QA for parallel test suites
  └── ... (all 14 heads can spawn sub-workers)
```

### Sub-Worker Rules
1. Sub-workers use **same or lower tier** than their head (Thinker→Crafter, Crafter→Sprinter)
2. Sub-workers **inherit exactly**: same responsibility, same capability profile, same execution model
3. Sub-workers do NOT introduce: new responsibilities, new authority, new capability profile
4. Only Head Worker produces official artifact; sub-worker reports are internal only
5. **Spawn threshold**: scope >= 3 files or >= 2 modules → spawn sub-workers

### Sub-Worker Lifecycle
1. Head Worker analyzes scope
2. Head Worker defines N sub-scopes
3. Head Worker creates N prompt files
4. Head Worker invokes spawn-sub.sh N times (blocking)
5. Each sub-worker executes assigned scope
6. Each sub-worker produces Sub-Worker Report
7. Head Worker reads all sub-reports
8. Head Worker consolidates into one official artifact
9. Head Worker performs self-validation
10. Head Worker marks Completed

---

## 7. Rule of 5 (Business Workflow)

The canonical 5-phase governance pipeline:

```
User
  ↓
Dispatcher (classify, route)
  ↓
PM (Discovery, requirements)
  ↓
Architect (technical design)
  ↓
Engineering (implementation)
  ↓
QA (verification)
  ↓
Governor (compliance, release)
  ↓
Dispatcher (deliver to user)
  ↓
User
```

**Rule of 5 defines WHO does WHAT. It does NOT define execution order within a phase.**

---

## 8. Phase Ownership Matrix

### Investigate Phase (Serial)
| Worker | Prerequisite | Parallel |
|--------|-------------|----------|
| PM | Dispatcher assignment | NO |
| Research | PM assignment | Conditional |

### Planning Phase (Serial then Parallel)
| Worker | Prerequisite | Parallel |
|--------|-------------|----------|
| Architect | PM Discovery + PM PASS | NO (must complete first) |
| Data | Architecture Specification | YES |
| Integration | Architecture Specification | YES |
| Infrastructure | Architecture Specification | YES |
| Security | Architecture Specification | YES |
| Designer | Architecture Specification | YES |

### Implementation Phase (Parallel)
| Worker | Prerequisite | Parallel |
|--------|-------------|----------|
| Backend | Architecture Spec + Work Package + PM PASS | YES |
| Frontend | Architecture Spec + Work Package + PM PASS | YES |
| Designer | PM + Frontend request | YES |

### Verification Phase (Parallel)
| Worker | Prerequisite | Parallel |
|--------|-------------|----------|
| QA | Implementation Reports + PM PASS | YES |
| Performance | Implementation Reports | YES |

### Closeout Phase (Serial)
| Worker | Prerequisite | Parallel |
|--------|-------------|----------|
| Documentation | All phase reports | NO (must complete first) |
| Governor | All reports + Documentation + PM PASS | NO |

---

## 9. FSM Phase Plans (engine/fsm.js — Runtime Canonical)

```javascript
const PHASE_PLANS = {
  INVESTIGATE: [{ worker: 'pm', tier: 'thinker' }],
  PLANNING: [
    { worker: 'pm', tier: 'thinker' },
    { worker: 'architect', tier: 'thinker' },
    { worker: 'research', tier: 'thinker' },
    { worker: 'designer', tier: 'thinker' },
  ],
  IMPLEMENTATION: [
    { worker: 'backend', tier: 'crafter' },
    { worker: 'frontend', tier: 'crafter' },
  ],
  VERIFICATION: [{ worker: 'qa', tier: 'crafter' }],
  CLOSEOUT: [{ worker: 'pm', tier: 'thinker' }],
};
```

**NOTE:** The runtime FSM has a simplified PHASE_PLANS vs the reference docs. Planning specialists (data, integration, infra, security) and verification (perf) are in the docs but NOT in the runtime PHASE_PLANS. This is a known parity gap.

---

## 10. PHASE_ALLOWED (config.js — Dashboard Enforcement)

```javascript
const PHASE_ALLOWED = {
  investigate:    ['pm', 'research'],
  planning:       ['pm', 'research', 'architect', 'data', 'integration', 'security', 'infra', 'designer'],
  implementation: ['pm', 'research', 'architect', 'data', 'integration', 'security', 'infra', 'designer', 'frontend', 'backend'],
  verification:   ['pm', 'research', 'architect', 'data', 'integration', 'security', 'infra', 'designer', 'frontend', 'backend', 'qa', 'perf'],
  closeout:       ['pm', 'research', 'architect', 'data', 'integration', 'security', 'infra', 'designer', 'frontend', 'backend', 'qa', 'perf', 'documentation', 'governor'],
};
```

**NOTE:** PHASE_ALLOWED is cumulative (later phases include all workers from earlier phases). This is a gatekeeper, not a spawn plan.

---

## 11. Artifact Registry (Per-Worker Deliverables)

| # | Artifact | Producer | Phase | File |
|---|----------|----------|-------|------|
| 1 | User Summary | Dispatcher | Init | — |
| 2 | Structured Clarification Request | PM | Investigate | pm-output.md |
| 3 | Discovery Report | PM | Investigate | pm-output.md |
| 4 | Work Package | PM | Investigate | work-packages.json |
| 5 | Phase Review Verdict | PM | All phases | .pm-last-verdict.txt |
| 6 | Architecture Specification | Architect | Planning | architect-output.md |
| 7 | Research Report | Research | Investigate/Planning | research-output.md |
| 8 | Backend Implementation Report | Backend | Implementation | backend-output.md |
| 9 | Frontend Implementation Report | Frontend | Implementation | frontend-output.md |
| 10 | Verification Evidence Report | QA | Verification | qa-output.md |
| 11 | Design Specification | Designer | Planning/Implementation | designer-output.md |
| 12 | Infrastructure Report | Infrastructure | Planning | infra-output.md |
| 13 | Security Advisory Report | Security | Planning | security-output.md |
| 14 | Performance Optimization Report | Performance | Verification | perf-output.md |
| 15 | Data Architecture Specification | Data | Planning | data-output.md |
| 16 | Integration Specification | Integration | Planning | integration-output.md |
| 17 | Documentation Handoff Report | Documentation | Closeout | documentation-output.md |
| 18 | Release Checklist | Governor | Closeout | governor-output.md |
| 19 | Release Summary | Governor | Closeout | governor-output.md |

**Runtime path:** `reports/{worker}-output.md`

---

## 12. Task Types & Routing

| User Input | Type | Pipeline |
|------------|------|----------|
| `build X` | feature | PM → Architect → [Designer] → Engineers → QA → Governor |
| `fix X` | bug | Engineer (→ QA if complex) |
| `research X` | research | Researcher (→ PM if actionable) |
| `design Y` | design | Designer |
| `audit X` | security | Backend → Governor |
| `deploy X` | infra | Infra → QA |
| `try/spike X` | experiment | Researcher → Architect (POC, not production) |
| `optimize X` | optimize | Architect → Engineers → QA |
| `improve X` | iterate | PM → Engineers → QA |
| `edit/fix X that doesn't match` | refine | Engineer(s) (targeted fix) |
| `migrate X to Y` | migrate | Architect → Engineers → QA → Governor |
| `clean up X` | maintain | Engineers → QA |
| `plan X` | planning | PM → Architect (specs only, no code) |
| `develop X` | develop | PM → Architect → Engineers → QA (multi-session) |

---

## 13. Worker Display Names (Dashboard)

```javascript
const SHORT_NAMES = {
  pm: 'Aria', architect: 'Atlas', research: 'Sage',
  designer: 'Pixel', frontend: 'Vue', backend: 'Forge',
  qa: 'Sentinel', governor: 'Nexus', documentation: 'Scribe',
  infra: 'Terra', security: 'Shield', perf: 'Bolt',
  data: 'Schema', integration: 'Bridge', dispatcher: 'Hermes'
};
```

---

## 14. Token Metrics Worker IDs

All workers tracked in metrics (dispatcher excluded):

```javascript
const ALL_WORKERS = [
  'pm', 'architect', 'research', 'designer', 'frontend', 'backend', 'qa',
  'governor', 'documentation', 'perf', 'infra', 'security', 'data', 'integration'
];
```

**Total tracked: 14 workers** (dispatcher runs via Hermes directly, not captured).

# 20 — Engineering Workflow

**Subsystem:** End-to-End Pipeline Execution
**Version:** v2.3.0

---

## 1. Pipeline Stages

```
User types in Command Center
         │
         ▼
   classify_intent()
         │
    task_request?
         │
         ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Discovery  │ ──► │  Planning   │ ──► │ TaskGraph   │
│  Engine     │     │  Engine     │     │  Engine     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │  Brief            │  Plan             │  DAG
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Dispatch  │
                    │   Engine    │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │   Workers   │
                    │ (real tools)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Verify   │ │ Deliver  │ │ Complete │
        └──────────┘ └──────────┘ └──────────┘
```

---

## 2. Stage Details

### Stage 1: Discovery
- **Engine:** `DiscoveryEngine.discover()`
- **Input:** User message
- **Process:** Intent classification → Requirement extraction → Ambiguity detection → Readiness evaluation
- **Output:** `EngineeringBrief` (structured requirements, acceptance criteria, readiness score)
- **Worker:** Hermes (dispatcher) + PM
- **Tool usage:** None (conversational)

### Stage 2: Planning
- **Engine:** `PlanningEngine.plan()`
- **Input:** EngineeringBrief
- **Process:** Brief analysis → Architecture decisions → Risk assessment → Effort estimation
- **Output:** `EngineeringPlan` (technical approach, decisions, risks, estimates)
- **Worker:** Architect + Designer + Database + Security
- **Tool usage:** `explore` (file tree), `read_file` (existing code)

### Stage 3: Task Graph
- **Engine:** `TaskGraphEngine.generate_graph()`
- **Input:** EngineeringPlan
- **Process:** Decompose plan → Analyze dependencies → Detect parallelism → Find critical path
- **Output:** `TaskGraph` (nodes, edges, execution order, recovery points)
- **Worker:** None (automated)

### Stage 4: Dispatch
- **Engine:** `DispatcherEngine.dispatch()` → `runtime/executor.py`
- **Input:** TaskGraph
- **Process:** Per node: select worker → create lease → execute with tools → collect results
- **Output:** Execution results, artifacts, test results
- **Workers:** All assigned workers per node
- **Tool usage:** `read_file`, `write_file`, `shell`, `explore`, `search`

### Stage 5: Verification
- **Engine:** VerificationEngine + QA Worker
- **Input:** Execution results
- **Process:** Requirements traceability → Quality scoring → Regression detection → Security scan
- **Output:** Verification report, quality scores
- **Worker:** QA + Performance
- **Tool usage:** `shell` (run tests), `read_file` (check artifacts)

### Stage 6: Delivery
- **Engine:** DeliveryEngine
- **Input:** Verified artifacts
- **Process:** Engineering report → Lessons learned → Recommendations
- **Output:** Delivery report
- **Worker:** Documentation + PM

---

## 3. Smart Triage

Not all tasks need the full pipeline. `Smart Triage` classifies tasks:

| Level | Scope | Pipeline |
|-------|-------|----------|
| **L1 QUICK** | Localized, low-risk | Skip discovery, planning, closeout |
| **L2 STANDARD** | Bounded module | Skip discovery, conditional planning |
| **L3 EXTENDED** | Cross-component | Skip discovery only |
| **L4 FULL** | Architecture / major build | All stages |

**Guardrails override:** Security keywords → minimum EXTENDED. DB schema → minimum EXTENDED. Architecture → minimum FULL.

---

## 4. Worker Tool Usage

Workers use `ToolExecutor` for real operations:

| Tool | What It Does | Used By |
|------|-------------|---------|
| `read_file` | Read file from project | All workers |
| `write_file` | Write file to project | Backend, Frontend, Coding, Database |
| `shell` | Execute shell command | Backend, Frontend, Coding, DevOps |
| `explore` | List directory tree | All workers |
| `search` | Grep-like content search | All workers |

**Tool-use loop:** Worker calls LLM → LLM returns tool call → execute tool → feed result back → repeat until done.

---

## 5. Event Flow

```
Discovery completed → EventBus.publish("pipeline.stage.completed")
    │
    ▼
Planning started → EventBus.publish("pipeline.stage.started")
    │
    ▼
... (each stage transition is an event)
    │
    ▼
Dispatch completed → EventBus.publish("pipeline.completed")
    │
    ▼
WebSocket → Frontend updates in real-time
```

---

## 6. Approval Gates

| Gate | Trigger | Action |
|------|---------|--------|
| **Planning approval** | Task requires approval (high-impact) | Pause pipeline, notify user via WebSocket |
| **Tool approval** | Worker tries restricted tool | Create ApprovalRequest, await user decision |
| **PM review** | Closeout phase | PM reviews before marking complete |

# 06 — Worker Runtime

**Subsystem:** Worker Execution Core  
**Package:** `aic-platform/workers`  

---

## 1. Worker Lifecycle States

```
 [Idle] ──► [Planning] ──► [Coding/Investigating] ──► [Testing/Reviewing] ──► [Completed]
   ▲                                                                              │
   └─────────────────────────────────── [Blocked] ◄───────────────────────────────┘
```

- **Idle:** Worker is registered and available for assignment.
- **Thinking / Planning:** Model is reasoning about architecture and subtasks.
- **Coding / Working:** Worker is modifying files or running commands inside the sandbox workspace.
- **Testing / Reviewing:** QA and Security workers validating code diffs and test suites.
- **Blocked:** Task hit an unresolvable failure or requires human approval.
- **Completed:** Deliverables generated and verified.

---

## 2. Worker Execution Schema

Workers run in isolated workspace environments using `workers/base.py::BaseWorker`. Each execution logs token usage, latency, and status changes back to `LLMUsageLog` and `EventModel`.

# 14 — Task Runtime

**Subsystem:** Finite State Machine Task Engine  
**Files:** `workflow/fsm.py`, `backend/routes/tasks.py`  

---

## 1. Task Lifecycle States

```
CREATED ──► DISCOVERY ──► INVESTIGATE ──► PLANNING ──► IMPLEMENTATION
                                                             │
COMPLETED ◄── CLOSEOUT ◄── VERIFICATION ◄─────────────────────┘
```

- **Terminal States:** `COMPLETED`, `FAILED`, `CANCELLED`.
- **Progress Tracking:** Progress % is calculated dynamically based on FSM state transitions and subtask completion.

---

## 2. Task Deliverable Isolation

Each task stores its deliverables, code diffs, logs, and generated files in `data/workspace/{project_id}/tasks/{task_id}/`. Deliverables can be exported as ZIP archives via `/api/tasks/{id}/download`.

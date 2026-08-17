# 57 — Company Office

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## What is Company Office?

Company Office is the real-time operational view of the AI Company. It shows the 15 canonical workers, their current status, active assignments, and departmental organization.

## Current Components

| Component | File | Purpose |
|---|---|---|
| `LiveCompany` | `LiveCompany.tsx` | Worker grid overview (200 LOC) |
| `Orchestration` | `Orchestration.tsx` | Pipeline + handoffs + worker pulse + events |
| `Topology` | `Topology.tsx` | Static department→worker hierarchy |
| `WorkerInspector` | `WorkerInspector.tsx` | Individual worker detail |

## Data Sources

| Source | Endpoint | Content |
|---|---|---|
| Workers | `GET /api/workers` | All 15 workers with status, config, current_task_id |
| Active Leases | `GET /api/dashboard/command-center` | Active leases mapped to workers |
| Events | `GET /api/dashboard/events` | Recent worker events |
| Task Status | `GET /api/dashboard/command-center` | Active tasks with phase info |

## Worker Status Derivation

```
Worker.status = "working" IF active_lease exists for worker_type
Worker.status = "idle" IF no active lease
```

**Source:** `backend/routes/dashboard.py:56-59`

## Department Organization

| Department | Workers | Role |
|---|---|---|
| Planning | PM, Architect, Researcher | Discovery, scoping, architecture |
| Engineering | Backend, Frontend, Full-Stack, Database, DevOps | Implementation |
| Quality | QA, Security, Performance, Debugger, Code Reviewer | Verification |
| Content | Documentation | Closeout |
| Design | Designer | Requirements |

## Issues

1. **4 separate components for one concept** — `LiveCompany`, `Orchestration`, `Topology`, `WorkerInspector` should be consolidated into one progressive-disclosure view.
2. **Orchestration is overwhelming** — shows pipeline, handoffs, 15-worker pulse, and event timeline simultaneously. Must layer with progressive disclosure.
3. **Topology is static** — renders department→worker hierarchy without real task context. Should show current assignments.
4. **Worker inspector is a separate page** — should be a drawer/panel that opens inline.
5. **No real-time updates** — relies on polling. WebSocket endpoint exists (`/api/ws`) but is not used for worker status.

## Target Design

### Level 1: Summary
- Active / waiting / available worker counts
- Current handoffs (phase transitions)
- Urgent blockers (failed/errored workers)

### Level 2: Department / Worker Grid
- Department tabs or filter
- Worker cards with real-time status
- Assigned task + progress

### Level 3: Worker Inspector (Drawer)
- Worker role, current task, last event
- Artifacts produced
- Phase history

### Level 4: Diagnostics (Power User)
- Raw event stream
- API/recovery diagnostics
- Lease history

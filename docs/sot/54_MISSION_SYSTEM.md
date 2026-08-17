# 54 — Mission System

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Mission = Task

In the codebase, "Mission" is the UX term for what the backend calls "Task." The `Task` model is the single source of truth.

## Data Model

**Source:** `storage/models.py:190-225`

| Field | Type | Purpose |
|---|---|---|
| `id` | str (uuid) | Unique identifier |
| `project_id` | str | Parent project |
| `title` | str | Mission title |
| `description` | str | Full description / requirements |
| `type` | str (enum) | feature, bugfix, refactor, docs, test, infra, research |
| `status` | str (enum) | FSM state (see below) |
| `progress` | int (0-100) | Completion percentage |
| `worker_type` | str | Assigned worker type |
| `approval_required` | bool | Whether approval gates execution |
| `created_by` | str | User who created |
| `context` | dict | Runtime context (parallel plan, adaptive profile, etc.) |
| `artifacts` | list | Deliverable artifacts |
| `error_message` | str | Last error if failed |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
| `completed_at` | datetime | Completion timestamp |

## FSM States

| Status | Description | Next Possible |
|---|---|---|
| `created` | Initial state | `planning`, `blocked` |
| `investigate` | Research/discovery phase | `planning` |
| `planning` | Architecture/design phase | `approval`, `implementation` |
| `approval` | Awaiting user approval | `implementation`, `blocked` |
| `implementation` | Active coding | `verification`, `failed` |
| `verification` | Testing/review | `closeout`, `implementation` (fixes) |
| `closeout` | Documentation/delivery | `completed` |
| `completed` | Done | — |
| `blocked` | Blocked on dependency | `created`, `planning` |
| `cancelled` | User cancelled | — |
| `failed` | Execution failed | `created` (retry) |

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/tasks` | List tasks (filterable by project, status) |
| `POST` | `/api/tasks` | Create task |
| `GET` | `/api/tasks/{id}` | Get task detail |
| `POST` | `/api/tasks/{id}/dispatch` | Start execution |
| `POST` | `/api/tasks/{id}/cancel` | Cancel execution |
| `GET` | `/api/tasks/{id}/deliverables` | Get deliverables + leases + events |
| `GET` | `/api/tasks/{id}/workspace/files` | List workspace files |
| `GET` | `/api/tasks/{id}/workspace/content` | Read workspace file content |
| `GET` | `/api/tasks/{id}/download` | Download ZIP of deliverables |

## Mission Workspace Tabs

| Tab | Content | API Source |
|---|---|---|
| Overview | Description, runtime profile, workers, health | `GET /api/tasks/{id}` |
| Timeline | Events filtered to this mission | `GET /api/dashboard/events` + client filter |
| Evidence | Workspace files + content viewer | `GET /api/tasks/{id}/workspace/files` |
| Repository | Git state (placeholder) | Not implemented |

## Issues

1. **Repository tab is placeholder** — must implement or remove
2. **Timeline is client-filtered** — should support server-side `?task_id=` filter
3. **No real-time updates** — `MissionWorkspace` polls every 5 seconds via `setInterval`
4. **`context` field is untyped** — stores parallel plan, adaptive profile, and arbitrary data as dict
5. **No mission templates** — every mission starts from scratch; no reusable project scaffolds

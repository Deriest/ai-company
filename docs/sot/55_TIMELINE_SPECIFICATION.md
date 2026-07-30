# 55 — Timeline Specification

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Event Data Model

**Source:** `storage/models.py:328-338`

| Field | Type | Purpose |
|---|---|---|
| `id` | str (uuid) | Unique identifier |
| `type` | str (EventType enum) | Event category |
| `actor` | str | Who triggered (worker name, user, system) |
| `target` | str | What was affected (task:{id}, worker:{name}) |
| `data` | dict | Event payload |
| `severity` | str | info, warning, error |
| `created_at` | datetime | Timestamp |

## Event Types

| Type | Trigger | Example |
|---|---|---|
| `task_created` | Mission created | New mission via Hermes |
| `task_dispatched` | Mission dispatched | User clicks Dispatch |
| `task_completed` | Mission finished | All phases done |
| `task_failed` | Mission failed | Worker error |
| `lease_started` | Worker lease active | Worker begins work |
| `lease_completed` | Worker lease done | Worker finishes |
| `lease_expired` | Worker lease timeout | Self-healing cleanup |
| `worker_heartbeat` | Worker alive | Periodic check |
| `approval_requested` | Approval needed | Phase requires approval |
| `approval_granted` | User approved | User clicks Approve |
| `approval_rejected` | User rejected | User clicks Reject |
| `provider_connected` | Provider test OK | Model discovery |
| `provider_error` | Provider failed | Connection error |
| `system_heal` | Self-healing run | Startup or manual |

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/events` | Global event stream (limit=50) |
| `GET` | `/api/dashboard/audit` | Audit log stream (limit=50) |

## Timeline Views

### Global Timeline (`ActivityTimeline.tsx`)
- Shows all events across all missions
- Filtered by severity, type, actor
- Used in Review Center

### Mission Timeline (`MissionWorkspace.tsx` tab)
- Shows events filtered to specific mission
- `events.filter(e => e.target.includes(taskId))`
- Client-side filtering (inefficient)

## Issues

1. **Client-side filtering** — Mission timeline fetches ALL events then filters in JavaScript. Must add `?target=task:{id}` server-side filter.
2. **No pagination** — `limit=50` returns flat list. No cursor/offset support.
3. **Event data is untyped** — `data` field is arbitrary dict. No schema validation.
4. **No event grouping** — events are flat list. Should group by mission, phase, or worker for better UX.
5. **Audit log is separate** — `AuditLog` model exists but is not connected to timeline UI.

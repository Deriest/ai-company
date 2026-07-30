# 56 — Evidence Center

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## What is Evidence?

Evidence is any verifiable artifact produced by a worker during mission execution. Evidence proves that work was actually done — not claimed, not described, but executed.

## Evidence Types

| Type | Source | Storage |
|---|---|---|
| **Workspace Files** | Files written by workers | `workspace_manager.py` → task workspace directory |
| **Test Results** | pytest, vitest output | Worker execution logs |
| **Lease Artifacts** | Per-phase deliverables | `Lease.artifact_path` field |
| **Events** | Execution timeline entries | `Event` model in SQLite |
| **Audit Logs** | Policy decisions, approvals | `AuditLog` model in SQLite |
| **ZIP Export** | All deliverables packaged | `create_task_workspace_zip()` |

## Evidence APIs

| Endpoint | Returns |
|---|---|
| `GET /api/tasks/{id}/deliverables` | Full execution report: leases, events, phase_reports |
| `GET /api/tasks/{id}/workspace/files` | List of files in task workspace |
| `GET /api/tasks/{id}/workspace/content?file=X` | Content of specific workspace file |
| `GET /api/tasks/{id}/download` | ZIP of all deliverables |
| `GET /api/dashboard/audit` | Global audit log |

## Evidence UI (Current)

### Mission Evidence Tab (`MissionWorkspace.tsx`)
- Left pane: file list from workspace
- Right pane: file content viewer
- Click file → loads content via API

### Review Center (TBD — consolidating)
Currently split across:
- `AuditView.tsx` — audit logs
- `ActivityTimeline.tsx` — event timeline
- `Approvals.tsx` — pending approvals
- `Delivery.tsx` — deliverable downloads
- `Verification.tsx` — verification results

## Evidence Verification Rules

| Rule | Enforcement |
|---|---|
| Worker claims → must have lease | `Lease` record must exist for claimed work |
| Lease completion → must have artifact | `artifact_path` must be non-null |
| Test pass → must have output | Test results stored in workspace or logs |
| SHA256 → must match | Auto-update verifies hash before install |

## Issues

1. **No evidence search** — can't search across all mission evidence. Must support full-text search over workspace files and events.
2. **Evidence is per-mission only** — no global evidence browser across all missions.
3. **Audit log disconnected from UI** — `AuditLog` model exists but `AuditView.tsx` renders a static list without filters.
4. **No evidence export** — only ZIP download exists. No structured JSON/CSV export.
5. **Workspace files are ephemeral** — if task workspace is cleaned up, evidence is lost. Must define retention policy.

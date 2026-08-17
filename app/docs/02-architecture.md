# AIC IDE Architecture

## High-level

```
┌─────────────────────────────────────────────────────────────┐
│                     AIC IDE (Electron)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Renderer    │  │   Preload    │  │   Main Process    │  │
│  │  React UI    │←→│  contextBridge│←→│  IPC + native     │  │
│  │  (greenfield)│  │  typed API   │  │  fs, pty, dialog  │  │
│  └──────┬───────┘  └──────────────┘  └─────────┬─────────┘  │
│         │ Runtime Client (HTTP/WS)              │ optional    │
└─────────┼───────────────────────────────────────┼────────────┘
          ▼                                       ▼
   aic-platform backend (:8000)          local backend spawn
   conversation · FSM · workers          (future)
   leases · events · workspace
          │
          ▼
   LLM providers (VansRouter / configured)
```

## Process roles

| Process | Responsibility |
|---------|----------------|
| Main | Window lifecycle, secure IPC, native dialogs, path abstraction, optional backend child, user PTY sessions, app data dirs |
| Preload | Expose minimal `window.aic` API; no raw Node |
| Renderer | All IDE UX; talks to AIC core via fetch/WS; uses `window.aic` only for native ops |

## Runtime Client

TypeScript client wrapping:

- Auth JWT storage (secure: keytar when available; else encrypted app data — start with app-data file + OS perms)
- REST: projects, tasks, workers, conversations, approvals, console topology, LLM settings
- SSE: chat stream
- WS: `/ws/general` (+ task channels later)
- Workspace file listing via API; local open via native path when project root mapped

## Execution Session (mapping)

v1 mapping without new DB table:

```
ExecutionSession ≈ Lease
  id            = lease.id
  project/task  = task_id → project
  worker        = worker_type / canonical name
  phase         = lease.phase
  status        = lease.status
  started_at    = lease.created_at
  finished_at   = lease.finished_at
  outputs       = artifact_path + task.context.phase_results
  events        = Event where target task:{id} and actor worker:{type}
  terminal      = null until process streaming exists
```

## Live Company model

Always render 15 canonical entities from static registry + live status overlay from `/api/workers`, active leases, events.

States (truthful): IDLE | WORKING | FAILED | OFFLINE | RECENTLY COMPLETED (derived from last lease finish < N min). QUEUED/ASSIGNED/WAITING only when data exists.

## User terminal vs worker terminal

| Kind | Implementation v1 |
|------|-------------------|
| Worker terminal | Read-only log view from events/deliverables; "No terminal process" if none |
| User project terminal | Main-process `node-pty` when project root set; isolated cwd |

## Security boundaries

- Renderer cannot spawn processes directly
- Path ops confined to allowed roots (project + app data)
- Secrets never logged to renderer console
- Project trust flag before running user terminal / install scripts (v1: warn; v1.1: blocklist)

## Cross-platform paths

Use `path` / `app.getPath()` in main; never hardcode `/home/tvd`.

## Packaging

electron-builder targets: `AppImage`/`deb` (linux), `nsis` (win), `dmg` (mac). Auto-update stubbed config only.

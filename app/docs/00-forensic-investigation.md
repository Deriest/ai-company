# AIC IDE — Phase 0 Forensic Investigation (Read-Only)

Date: 2026-07-23
Sources: `/home/tvd/AI-Company/aic-platform`, `/home/tvd/AI-Company/aic-skill`
Status: EVIDENCE-BASED — no code changes to aic-platform during this investigation

## 1. What AIC Platform Is Today

Standalone FastAPI + React SPA product at `aic-platform/`.

| Layer | Location | Role |
|-------|----------|------|
| API / SPA host | `backend/main.py` | FastAPI, CORS, SPA static, health |
| Domain models | `storage/models.py` | Users, projects, tasks, leases, events, approvals, LLM configs |
| FSM | `workflow/fsm.py` | Phases + barriers + approval gates |
| Conversation | `conversation/engine.py` | Chat → intent → task create (regex-first) |
| Runtime | `runtime/executor_simple.py` | Sequential phase pipeline (production path) |
| Runtime (unused for auto-dispatch) | `runtime/executor.py` | Barrier/lease complex path — known broken for auto-dispatch |
| Workers | `workers/base.py` | LLM workers + templates; WORKER_REGISTRY |
| Canonical workforce | `backend/canonical_workforce.py` | 15 entities (Hermes + 14) |
| Workspace/delivery | `backend/workspace_manager.py` | `data/workspace/<task_id>/`, ZIP download |
| Recovery | `backend/recovery_engine.py` | 5-tier adaptive recovery |
| Events | `events/bus.py`, `events/recorder.py` | Bus + DB recorder |
| Realtime | `backend/routes/websocket.py` | JWT WS channels |
| LLM | `llm/provider.py` | Multi-provider, tiers thinker/crafter/sprinter |
| Web UI | `frontend/` | React 19 + Vite + Tailwind SPA |

## 2. Canonical 15 Workforce — VERIFIED

From `backend/canonical_workforce.py` (exact keys):

| ID | Name | Role | Department |
|----|------|------|------------|
| hermes | Hermes | Dispatcher | Leadership |
| rex | Rex | Governor | Leadership |
| pm | Aria | Product Manager | Product |
| research | Sage | Researcher | Product |
| designer | Luna | Designer | Product |
| documentation | Echo | Documentation Engineer | Product |
| architect | Atlas | Architect | Engineering |
| backend | Hugo | Backend Engineer | Engineering |
| frontend | Leo | Frontend Engineer | Engineering |
| qa | Eve | QA Engineer | Engineering |
| performance | Pulse | Performance Engineer | Engineering |
| database | Nova | Data Engineer | Platform |
| nexus | Nexus | Integration Engineer | Platform |
| flint | Flint | Infrastructure Engineer | Platform |
| security | Sentinel | Security Engineer | Platform |

**Count: 15.** Hermes included. Matches mission §7.

Note: `WORKER_REGISTRY` also has extension aliases (`coding`, `devops`, `deployment`, `debugger`, legacy `planner/review/testing`). IDE Live Company must show the **15 canonical** entities, not aliases as permanent workers.

## 3. FSM — VERIFIED

```
created → investigate → planning → implementation → verification → closeout → completed
Terminal: completed | cancelled | blocked
Approval gate: planning
PM review gate: closeout
```

Phase workers (full plan) in `workflow/fsm.py::PHASE_WORKERS`. Dynamic filter via `allowed_workers_for_phase(phase, target_worker, task_type)`.

## 4. Execution Model — CRITICAL FINDINGS

### What exists
- **Lease** table: task_id, worker_id, worker_type, phase, status (active/completed/failed/expired), artifact_path, exit_code, timestamps
- **Event** table: task.*, worker.*, phase.advanced, approval.*, lease.*, chat.message
- **Task.context.phase_results**: per-phase worker outputs (truncated)
- Workspace files: `data/workspace/<task_id>/<phase>/<worker>-deliverable.md` + README/REQUIREMENTS on closeout
- WebSocket manager with `broadcast_event`, `broadcast_task_event`, `broadcast_worker_event`

### What does NOT exist (gaps for IDE)
1. **No real process/PTY terminal streams.** Workers call LLM (`provider.chat`) or return markdown templates. `run_with_timeout` default path is LLM, not shell.
2. **No Execution Session abstraction** as first-class entity — closest is **Lease** + Event log + workspace files.
3. **WebSocket is underused.** `broadcast_*` helpers exist; grep of py tree found no production call sites from executor_simple into WS (events go to DB primarily). Frontend has `useWebSocket` hook — may poll more than stream.
4. **executor_simple is sequential** within a phase (for-loop workers one-by-one), not true parallel multi-process concurrency. Parallelism is visual/logical only unless redesigned.
5. **Worker timeout in executor_simple is 15s** — too short for real coding; workers often fall back to templates when LLM fails/timeouts.
6. **No git integration** in platform core.
7. **Delivery is download ZIP**, not local project root open-in-place as first-class desktop concept.

### Implication for AIC IDE
- Live Execution UI can be **truthful today** for: worker status, leases, events, phase, deliverable markdown, task progress.
- Live Execution **cannot honestly show real shell terminals** until executor gains process/PTY capture (or OpenCode adapter streams).
- IDE must label empty terminal: "No terminal process active for this execution" — never fake.
- Prefer Lease as Execution Session identity until a dedicated table is justified.

## 5. API Surface (reusable by desktop)

Routers mounted in `backend/main.py`:

| Prefix | Domain |
|--------|--------|
| `/api/auth` | login/register/JWT |
| `/api/projects` | CRUD projects |
| `/api/tasks` | CRUD + deliverables + workspace files + download |
| `/api/conversations` | chat + SSE stream + batch |
| `/api/workers` | worker list/status |
| `/api/approvals` | approval gates |
| `/api/dashboard` | overview + audit |
| `/api/llm` | providers/models/usage |
| `/api/users` | me/profile |
| `/api/console` | logs, topology, system status |
| `/ws/{channel}` | realtime |
| `/api/health`, `/health` | health |

**Reuse decision:** Desktop talks to this HTTP/WS API as Runtime Client. Do not embed FastAPI inside Electron main process in v1. Optionally later: spawn local backend as child process.

Live health check (this host): `{"status":"healthy","service":"aic-platform","version":"1.0.0","database":"connected","llm_configured":true}`

## 6. Layer Separation

| Belong to CORE (reuse) | Belong to WEB (do not port UI) | Belong to DESKTOP (new) |
|------------------------|--------------------------------|-------------------------|
| FSM, workers, conversation engine, recovery, workspace_manager, models, LLM providers, policy, events | Landing, AppShell, pages/* design system, OpsTopology SPA layout, mobile list↔chat IA | Shell, panels, command palette, native FS, PTY user terminal, window state, packaging, local project roots |
| API contracts | CSS tokens / cyan admin aesthetic | New IDE design system |

## 7. aic-skill Behavioral Contract (must preserve in IDE UX)

- Conversation-first intake; discovery before premature execution
- Dispatcher (Hermes) is only user-facing orchestrator; does not write project code
- Requirements discipline + domain checklists (platform: `domain_checklists.py`)
- Worker specialization + FSM phases + barriers
- WECP / artifact quality gates (platform: `wecp_validator.py`)
- Adaptive recovery ladder; never silent success after failure
- Delivery: README + REQUIREMENTS + real source
- No private chain-of-thought exposure

Platform is **not** a 1:1 copy of aic-skill Node runtime (OpenCode spawn, leases file, etc.). Semantic parity is partial: FSM + workers + recovery exist; full OpenCode process orchestration does not.

## 8. Environment Constraints (build machine)

| Item | Value |
|------|-------|
| OS | Linux (TVD-Server) |
| Node | v22.23.1 |
| npm | 10.9.8 |
| Rust/cargo | NOT installed |
| Electron/Tauri CLI | NOT preinstalled |
| RAM | ~12GB |
| CPU | 4 threads (i3-6100T) |
| Backend | Running healthy on :8000 |

Cross-platform packaging for Win/macOS will be CI/build-matrix + smoke, not full native run on this host.

## 9. Risks for Desktop Product

1. Treating markdown deliverables as "real coding" without process evidence
2. Porting web dashboard IA (forbidden)
3. Assuming WS already streams every worker event
4. Resource pressure: Electron + backend + multi-worker LLM on 12GB machine
5. Security: desktop FS + autonomous shell = higher threat model than web ZIP download

## 10. Recommended Reuse Map for AIC IDE

```
AIC IDE (Electron)
  ├── Renderer: greenfield UI (React)
  ├── Main: native bridge (fs, dialogs, shell, optional local backend spawn)
  └── Runtime Client → HTTP/WS → aic-platform backend (unchanged process)
        ├── conversation + tasks + workers + leases + events
        ├── workspace files
        └── (future) process/PTY stream endpoints if added
```

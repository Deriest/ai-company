# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.4.82 — 2026-08-09

### Bug Fixes & Security Hardening

#### Critical Fixes
- **P3: executor.py** — QA worker now uses `effective_repo_path` instead of `'.'` for correct execution context
- **P9: Sessionmaker** — Hoisted to ONE per phase (was one per worker call) to prevent session exhaustion
- **P4: websocket.py** — `disconnect_all()` removes socket from ALL channels (fixes connection leak)
- **P5: auth.py** — Brute-force lockout: 3 fails → 5min, doubling each tier
- **P2: self_healing.py** — Added `await dispatch` and audit orphaned 'investigate' tasks

#### Medium Priority Fixes
- **P6: bus.py** — Copy-on-write handler storage for lock-free publish
- **P8: main.py** — FTS5 double-init removed (already in init_db())
- **P11: executor.py** — `ship_with_caveats` surfaces caveats via events/results
- **P14: config.py** — Version fallback changed '2.4.23' → 'unknown'
- **P15: validation.py** — URL validated with urlparse (not bare startswith())
- **P10: tool_executor.py** — search_files regex compiled once per file (performance)
- **P12: rate_limiter.py** — Per-endpoint buckets prevent starvation
- **P13: dispatcher/engine.py** — Partial cascade vs fail-stop on node failure

## v2.4.81 — 2026-08-09

### Worker Maximization
- **Full soul injection** — all 9 soul fields (incl. `engineering_philosophy`, `risk_philosophy`, `collaboration_style`, `escalation_policy`) now injected into every worker's context
- **Per-worker tuning policy** — `WorkerTuningPolicy` (planning depth, verification frequency, checkpoint strategy, prompt detail) configured per role for all 15 workers
- **Lessons loop** — `lessons_learned` entries are retrieved at dispatch time and injected into worker context so the company learns from past failures
- **Self-healing upgrade** — heartbeat subscribers now trigger `SelfHealingEngine`; blocked leases (>30 min) auto-expire and stuck workers reset to IDLE

### Office Floor
- **Unified workforce view** — redundant "Live Company" nav entry removed; Office (pixel-art floor) is the single workforce view (`/live` route kept for back-compat)
- **Live status endpoint** — new `GET /runtime/workforce` returns busy state, active task (title/phase/progress), and configured model per worker
- **WebSocket push** — dispatcher broadcasts worker started/completed events; office floor refreshes instantly instead of waiting for the poll

### Bug Fixes
- Memory persistence now stores under `task.project_id` (was repo path)
- WorkspaceView reads the correct workforce endpoint + data shape

---

## v2.4.80 — 2026-08-08

### UI Redesign
- **Unified Explorer panel** — Removed redundant sidebars (FileTree + ProjectPicker from AppShell rail and duplicate session list sidebar). The right-side panel is now a clean workspace explorer with:
  - Workspace/project selector at the top
  - Real-time file search bar
  - File tree of selected project
  - Empty state prompting to pick a project if none selected
  - Auto-opens when a project exists
- **Simplified Inspector** — Replaced confusing "Deliverables/Tools/Session" tabs with focused file/workspace browsing functionality
- **Cleaner command center** — Full-width chat area without competing sidebars

---

## v2.4.79 — 2026-08-08

### Bug Fixes
- **Discovery clarification loop fix**: Chat replies like "hello" no longer re-trigger the discovery gate forever
- **Tool-chat persistence fix**: Assistant replies in tool-aware chat paths are now persisted
- **Conversation delete cascade fix**: FK cascade through engineering pipeline tables when deleting conversations
- **Improved error visibility**: Delete failures now surface alerts to users

---

## v2.4.78 — 2026-08-08

### Bug Fixes
- Conversation delete cascade fix with batch delete support
- Improved error visibility for failed deletions

---

## v2.4.77 — 2026-08-08

Full release including v2.4.77 bug fixes and improvements

---

## v2.4.71 — 2026-08-07

### Security & Auth Hardening
- Auth enforcement: `require_current_user` on ALL mutating endpoints (planning, dispatcher, delivery, autonomy, verification, context, conversations, discovery, taskgraph, orchestration, providers, backup)

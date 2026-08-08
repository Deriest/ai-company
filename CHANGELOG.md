# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

---

## v2.4.78 — 2026-08-08

### Bug Fixes
- **Conversation delete cascade fix**: Fixed silent failure when deleting conversations that have associated engineering pipelines. The delete handler now properly cascades through all FK-dependent tables: `engineering_briefs`, `planning_sessions`, `task_graphs`, `dispatch_sessions`, `verification_sessions`, `engineering_reports`, and `lessons_learned`. Previously, orphan rows would cause commit failures due to unhandled foreign key constraints.
- **Batch conversation delete**: Added the same cascade handling to `/api/conversations/batch` endpoint for bulk delete operations.
- **Improved error visibility**: Frontend `handleDelete` in `ChatView.tsx` now shows an alert dialog on delete failure instead of silently logging to console. This helps users see actual errors instead of assuming deletion succeeded when it failed.

---

## v2.4.71 — 2026-08-07

### Security & Auth Hardening
- Auth enforcement: `require_current_user` on ALL mutating endpoints (planning,
  dispatcher, delivery, autonomy, verification, context, conversations, discovery,
  taskgraph, orchestration, providers, backup).
- SSRF protection: block RFC1918 private ranges (10/8, 172.16/12, 192.168/16) +
  IPv6 ULA (fc00::/7) in provider validation; pin `follow_redirects=False` on
  ProviderClient outbound connections.
- `AIC_TESTING` fail-open now logs a loud startup WARNING (test-only, documented).
- Timing-safe login compare via `secrets.compare_digest`.

### Concurrency & Data Integrity
- DB lock fix: commit before `execute_task` in dispatcher subtask-reuse path
  (was holding the SQLite write lock across 120s+ LLM calls).
- Worker race fix: workers return handoffs via result tuple; merge after gather
  instead of mutating shared task.context/handoffs_dict.
- Self-healing TOCTOU: atomic guarded UPDATE WHERE status='created' + rowcount
  check; uses valid TaskStatus 'investigate' (not invalid 'in_progress').
- Consolidated `storage/lock_retry.commit_with_lock_retry()` (executor + audit).

### Permission Model Alignment
- Registry-first tool permissions derived from AGENT_REGISTRY (single source of
  truth); removed hardcoded `_FULL_TOOLS` over-grants.
- Shell safety: destructive-command denylist + 300s timeout cap on `run_shell`.
- MCP policy: MCP follows shell capability — granted to shell-capable agents
  (backend/frontend/database/qa/nexus/flint/debugger + coding/devops/crafter),
  denied to read-only/governance/docs agents (hermes/rex/pm/research/architect/
  designer/security/performance/documentation).

### Frontend & Electron Hardening
- JWT token memory-only (never persisted to state.json; residual token scrubbed).
- Chat markdown links routed through `window.aic.openExternal` (github allowlist).
- CSP meta tag in index.html (file:// safe), synced with main.ts header injection.
- WorkspaceView poll request-ID guard (no stale-data overwrite).
- JobsView + OrchestrationView pagination (Load more).
- ChatView highlightCode single-pass tokenizer (fixed double-wrap corruption).

### Test Coverage Expansion
- test_auth_fail_closed.py (15): 401, WWW-Authenticate, DNS-rebinding Host guard.
- test_ssrf_guards.py (14): private IPs, loopback, metadata, redirect downgrade.
- test_heartbeat.py (9): _as_utc, stale-task, blocked-lease detection.
- test_dispatcher_concurrency.py (6): real execution, fail-stop, success_rate.
- test_lock_retry.py (7): backoff, reapply closure, max attempts.
- test_tool_executor.py (+4): MCP policy regression (grant/deny/aliases).
- frontend_api_client.test.ts (7) + edge-cases.unit.test.ts (8).

**Results:** Backend 848 passed / 1 skipped | Frontend 211 passed | typecheck clean.

### Architecture Cleanup
- Removed dead `MasterOrchestrator._execute_node` (DispatcherEngine is sole owner).
- Composite indexes: Task(status, started_at), Lease(status, created_at).
- usage.py cutoff normalized to naive UTC (matches heartbeat `_as_utc`).

---

## v2.4.68 — 2026-08-05

### Fix
- Revert JWT to python-jose — packaged Windows/Linux runtimes ship `python-jose`,
  not PyJWT. The installed app crashed at startup with
  `ModuleNotFoundError: No module named 'jwt'` because the code migrated to
  PyJWT but the bundled runtime never had it. `backend.main` imports cleanly again.

---

## v2.4.67 — 2026-08-05

### Quality: Level 1 + Level 2 + binary attachments
- chat_service refactored (CC 109 → `_resolve_model_chain`, `_taste_rewrite_if_needed`,
  `_is_content_length_overflow`, `_handle_content_length_overflow`; behavior identical)
- Electron main tests: `UpdateManager` injectable (IO + AppAdapter) + 16 tests;
  `security.ts` extracted + 20 tests
- ChatView message-list virtualization (windowing ~16–52 rows per 1000) + 15 unit tests
- vitest/jsdom infra + first component tests (ErrorBoundary 3, ChatView 5)
- tool_executor: `CancelledError` → `proc.kill()` (instant cancel, no 120s wait)
- `overflow_warning` SSE forwarding in /chat/execute
- JWT migration python-jose → PyJWT (later reverted in v2.4.68 for runtime compat)
- Binary attachment storage: `attachment_store.py` (save/read/delete under
  `DATA_DIR/attachments/<id>`), /chat/execute persists binary from `data_url`,
  `GET /attachments/{id}` serves with mime_type, backup zip includes attachments
- Suite: 806 pytest passed / 1 skipped · 163 vitest passed · tsc 0 · oxlint 0

---

## v2.4.66 — 2026-08-05

### New
- Full backup/restore: `POST /backup/create` (VACUUM INTO snapshot + zip DATA_DIR +
  manifest), `POST /backup/validate`, `GET /backup/list`
- Electron: `aic:backup-create-to` (save dialog) + `aic:backup-restore` (stop backend →
  extract zip-slip-guarded → swap data dir with rollback → restart, preserve identity)
- Settings → Data tab (create/restore/validate/list backups)
- Settings "Apply to Engine" error now uses destructive styling (was green)
- Removed stale STATUS.txt / CURRENT_STATUS.txt

---

## v2.4.65 — 2026-08-04

### Highlights
**Full-project quality hardening.** No new features — production hardening,
agent intelligence, performance, and code quality across the entire codebase.
785 pytest passed, 0 failed. 98 vitest passed, tsc 0, oxlint 0.

### Agent Intelligence
- Batch orchestration path fixed (was 100% failing with TypeError)
- Tool feedback now surfaces stdout + exit code (no more "Error: None")
- Context overflow drops oldest messages first (was dropping newest)
- Tool-call protocol preserved during summarization (no orphaned tool messages)
- Stuck-loop detection (3 identical tool calls), shell timeout clamp (120s)
- Verify self-check step + project memory injection in agent loop
- `read_file` offset is now line-based and consistent across executors
- Taste checker calibrated (single-word AI-isms demoted, 2+ patterns → high)

### Production Hardening
- Structured logging with trace IDs + event recorder activated
- Request validation middleware (70MB body cap + SQL-pattern checks)
- Job scheduler + self-healing started at boot; MCP pool disconnected on shutdown
- Streaming messages finalized on client disconnect (no stuck "streaming" rows)
- Subprocesses killed on timeout; git clone moved off the event loop
- Config hardened: `127.0.0.1`, `DEBUG=False`, CORS cleaned, `.jwt_secret` chmod 600
- Per-install identity generated when no identity file exists
- Migration runner verifies each column before marking applied
- App: atomic state writes, single-instance lock, navigation allowlist to `dist`,
  health-poll timeout → error + restart, crash handlers

### Performance
- Chat streaming now streams live (first token in ~1s, not after full generation)
- RAG retrieval vectorized with numpy (no brute-force scan)
- N+1 message/conversation queries batched
- Context cache wired into the pipeline; provider/httpx reused
- Renderer per-chunk O(n²) updates eliminated; playwright moved to devDependencies

### Code Quality / Tests
- Dead modules removed (session_manager, agent_tools, auth.dependencies, auth.rbac)
- 13 dead IPC handlers + preload listeners removed; 30 unused imports removed
- 19 oxlint warnings → 0
- 32 new tests (agent_runner, tool_executor, mcp_client, SSE parser)
- 11 stale test expectations corrected; test DB isolated via conftest
- Full suite: 785 passed, 1 skipped, 0 failed

---

## v2.4.64 — 2026-08-04

### Fixes
- Plugin tests now auto-collected (`test_plugin_engine.py` in pytest.ini)
- `discovery/intent.py` now uses `get_active_with_key()` (empty-key bug)
- UpdatesDialog handles `ready_to_restart` status and hides "Remind me later" for mandatory updates

---

## v2.4.63 — 2026-08-04

### Fixes
- MCP stdio allowlist removed — local desktop app, any plugin-declared MCP server can be installed
- `test_rag.py` fixture drops both StorageBase + Base tables (DB leak between runs fixed)

---

## v2.4.62 — 2026-08-04

### Security & Identity
- Per-install random credential generated by Electron main (chmod 600), passed to backend via `AIC_IDENTITY_FILE`, exposed via IPC
- Real `POST /auth/login` + `GET /auth/me` endpoints restored (previously 404)
- Renderer port discovery fixed (was hardcoded :8000)

### Plugin System (maximal)
- Plugin MCP servers registered + connected (were dead on arrival)
- Plugin command tools auto-granted to assigned workers; default-deny for unknown workers
- `POST /plugins/{id}/update` (re-clone + version compare) + UI button
- "Install to all" option; relative script paths resolved against package dir
- 6 new plugin tests; git clone async

### Security fixes
- SSRF blocked in `web_fetch` (private/loopback/link-local + redirect re-check)
- `/tools/execute` tool-name allowlist; FTS5 query quoting; API key encrypted at rest
- `get_active()` → `get_active_with_key()` in all legacy paths
- Update manager: mandatory/minimumVersion enforced, macOS install fixed, live backend PID tracked

---

## v2.4.61 — 2026-08-04

### Fixes
- `chat_stream` worker tool path NameError fixed (`payload.worker_role`)

---

## v2.4.60 — 2026-08-04

### QA-E2E Fixes (81 bugs from full scan)
- Path traversal fixed in all executors (`_resolve_path` + `commonpath` checks)
- `/chat/regenerate` model auto-selection restored (was always broken)
- Vision tier forced when image attachments present; `db` passed to agent runner
- Env model priority (`AIC_MODEL_*`) over auto-pick; env base_url matching
- Double-send race, model blocklist, per-tier provider config, attachment caps
- Navigation guard, update chain hardening, CSP tightening, single-instance lock

---

## v2.4.59 — 2026-08-04

### Fixes
- LLM provider browser User-Agent for Cloudflare-gated gateways
- Streaming fallback when non-streaming returns empty content

---

## v2.4.56 — 2026-08-04

### New
- Complete plugin system with adapter framework and enforcement

## v2.4.54 — 2026-08-03

### New
- GitHub skill packages and Vision settings engine

## v2.4.53 — 2026-08-03

### New
- Extract PDF and document attachments for Vision/chat

## v2.4.52 — 2026-08-03

### New
- Chat, usage, skills, bug report, and privacy updates

## v2.4.51 — 2026-08-03

### New
- Auto-update from GitHub (latest.json + GitHub Releases)
- `scripts/release.sh` one-command release builder

## v2.4.48 — 2026-08-03

### New
- Message order fix, QA bugs, animated office floor

## v2.4.47 — 2026-08-03

### New
- Chat alignment/ordering, context usage, Windows icon, office floor, docs cleanup

## v2.4.21 — 2026-08-02

### Fixed
- QA Round 10 final polish (BUG-21/22, POLISH-1/2)

---

## v2.4.20 — 2026-08-01

### Highlights
**QA loop 9 rounds (v2.4.9 -> v2.4.20), 20 bugs fixed, 2 new feature systems.**
636 pytest passed, 0 failed. No regressions (BUG-01..20 verified).

### New Features
- **MCP Memory System** — Persistent memory via MCP server (`backend/backend/api/routes/mcp.py`, `mcp_client.py` integration)
- **Taste Anti-Slop System** — Quality guard that detects low-effort/boilerplate LLM output and triggers re-generation (`backend/backend/services/taste_checker.py`, `model_catalog.py`)

### Backend Engine / Pipeline
- `conversation/engine.py` — Major refactor (+198 lines): improved message handling, SSE tool_calls streaming
- `backend/backend/services/chat_service.py` — Major expansion (+469/-lines): full chat pipeline, provider config fallback, SSE events
- `backend/backend/services/provider_client.py` — Extended (+234 lines): multi-provider support, streaming, error recovery
- `backend/backend/services/agent_runner.py` — Extended (+108 lines): agent lifecycle management
- `backend/backend/services/context_builder.py` — Enhanced context assembly (+61 lines)
- `backend/backend/services/master_orchestrator.py` — Orchestration improvements
- `backend/backend/skill_engine.py` — New skill engine module (+22 lines)
- `backend/llm/provider.py` — Provider abstraction layer (+158 lines)
- `backend/runtime/executor.py` — Runtime execution layer (+56 lines)
- `backend/workers/base.py` — Worker base class improvements
- `backend/workflow/fsm.py` — Finite state machine for workflow (+76 lines)
- `backend/workflow/triage.py` — Triage routing (+68 lines)

### Chat / SSE / Tool Calls
- `backend/backend/api/routes/chat.py` — Chat endpoint expansion (+63 lines)
- `backend/backend/api/routes/mcp.py` — New MCP routes (+101 lines)
- `backend/backend/api/routes/providers.py` — Provider management routes (+84 lines)
- `backend/backend/api/routes/agent.py` — Agent route adjustments
- `backend/backend/api/routes/dashboard.py` — Dashboard fixes
- `backend/backend/api/routes/workers.py` — Worker route fixes
- `backend/backend/api/routes/provider_manage.py` — Provider management (+20 lines)
- `app/src/renderer/src/lib/api/chat.ts` — Frontend SSE tool_calls handling

### Launcher / Port Management
- `backend/backend/launcher/launcher.py` — Launcher improvements (+63 lines)
- `backend/backend/launcher/port_manager.py` — Smart port management with health-check ownership detection, lock file, stale process detection, signal-based cleanup (+152 lines)
- `backend/backend/main.py` — Backend main entry refactor (+89 lines)

### Migrations / Schema / Tests
- `backend/backend/migrations/runner.py` — Migration runner improvements (+53 lines)
- `backend/backend/models/schema.py` — Schema additions
- `backend/backend/routes/delivery.py` — Delivery route cleanup
- 9 test files updated with new fixtures (StorageBase + Base coverage)
- 7 new test files added (context detection, flatten history, SSE, taste checker, QA rounds)

### Frontend (Electron App)
- `app/package.json` — Version bump 2.4.9 -> 2.4.20, exclude `data/**` from build
- `app/src/main/updateManager.ts` — Update manager adjustments
- `app/src/renderer/src/App.tsx` — App shell improvements
- `app/src/renderer/src/components/LiveCompanyView.tsx` — Live view fixes
- `app/src/renderer/src/components/SettingsView.tsx` — Settings UI enhancements
- `app/src/renderer/src/components/WorkspaceView.tsx` — Workspace fixes
- `app/src/renderer/src/components/auth/ProviderSetup.tsx` — Provider setup UI (+46 lines)

### Configuration
- `backend/backend/config.py` — Dynamic version from package.json, data directory resolution improvements

### Quality Gate
- **636 pytest passed, 0 failed**
- **BUG-01 through BUG-20 verified fixed**
- **AppImage + deb builds produced** (`app/release/`)
- **`latest.json` updated to v2.4.20**

---

## v2.4.9 — 2025-07-31
- Fix SSE parsing, token budget, message persistence, sidebar navigation

## v2.4.8 — 2025-07-30
- Fix inline form whitespace (BUG-13)

## v2.4.7 — 2025-07-29
- Reliability fixes

## v2.4.6 — 2025-07-28
- Rebuild with R1+R2 fixes

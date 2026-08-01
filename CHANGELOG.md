# Changelog

All notable releases for AIC-ADE (AI Company — AI Development Environment).

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

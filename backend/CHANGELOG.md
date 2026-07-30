# Changelog

All notable changes to AIC-ADE are documented here.

---

## v2.3.0 — AI Engineering Company Vision (2026-07-30)

### Added
- **Live Office Floor** — Animated 2D office visualization with 15 worker desks across 4 departments, meeting table with mission count, real-time stats
- **Command Center** — OpenCode-style chat with inline tool panels, agent mode switching (build/plan), file diffs, shell output streaming
- **Skill Engine** — 6 built-in skills, custom skill creation UI, per-worker skill injection into LLM context
- **MCP Integration** — Model Context Protocol client (stdio/HTTP/SSE), tool discovery, remote execution, approval workflow
- **Master Orchestrator** — Automatic pipeline chaining: Discovery → Planning → TaskGraph → Dispatch
- **Token Cost Tracking** — Per-session cost via `/api/usage/stats`, displayed in Live Company view
- **File Tree Component** — Collapsible directory tree with file-type icons, auto-refresh
- **Terminal Panel** — Embedded PTY terminal via `node-pty`, toggle with Ctrl+`
- **Command Palette** — Fuzzy-searchable palette with 16+ commands, keyboard navigation
- **Project Management** — Full CRUD API, project picker UI, active project persistence, project-conversation linking
- **Real Tool Execution** — Workers use `ToolExecutor` with multi-turn tool-use loop (read_file, write_file, shell, explore, search, git_status, git_diff, git_log, web_fetch)
- **Permission System** — Per-agent tool authorization with allowed/restricted/prohibited enforcement
- **Context Pipeline** — Unified context assembly with token budgeting, code context source, tool history source
- **Git Integration** — git_status, git_diff, git_log tools available to workers
- **Cost Tracking** — Per-message cost calculation in chat responses
- **Heartbeat Scheduler** — Periodic worker health monitoring (stale tasks, blocked leases)
- **Pipeline API** — `GET /api/pipeline/task/{id}` and `GET /api/pipeline/active` for pipeline status
- **Dashboard API** — `GET /dashboard` for aggregated stats
- **Skills API** — Full CRUD + toggle + assign + seed endpoints
- **MCP API** — Server CRUD + connect/discover + tool execution + approval
- **Usage Session API** — `GET /usage/session/{id}` for per-session cost
- **Keyboard Shortcuts** — Ctrl+1-6 view switching, Ctrl+K palette, Ctrl+` terminal

### Changed
- **Settings streamlined** — Reduced from 14 tabs to 3 (General, Providers, Auto Approve)
- **Navigation cleaned** — Removed dead views (Projects, Timeline, Evidence), added Skills and MCP
- **Chat redesigned** — OpenCode-style with inline tool panels, compact sidebar, status bar
- **Worker tier: Hermes upgraded** — system → thinker (best model for dispatcher)
- **Provider URL resolution** — Try relative `/models` first, fallback to `/v1/models`
- **Workers use real tools** — 12 of 16 workers now use `_llm_with_tools()` with ToolExecutor
- **DB init fixed** — Storage tables properly created via `to_metadata()` pattern
- **WebSocket fixed** — Localhost bypass for desktop mode (no JWT required)

### Fixed
- Progress map phase names (discovery, investigation, planning, implementation, verification, closeout)
- PM review gate checks "closeout" instead of "documentation"
- Duplicate LLM call in chat streaming
- Provider card dead Edit/Delete buttons removed
- 7 unreachable views now accessible
- Preload `logFile` type added
- 10+ unused imports removed across frontend
- Raw Tailwind colors replaced with design tokens

---

## v2.2.0 — Previous Release

- Provider BYOK with dynamic model fetch
- Auto Updater with SHA256 verification
- Self-Healing Engine at startup
- Parallel Dispatcher with real leases
- Adaptive Runtime (dynamic ContextPolicy, MemoryPolicy, WorkerPolicy)
- Mission Workspace and Evidence Center

---

## v2.1.0 — Desktop UX Excellence

- Unified Design System (oklch colors, dark theme)
- IDE Layout Shell (Activity Bar, Sidebar, Editor, Bottom Panel)
- Workspace and File Explorer
- Codebase health (App.tsx decoupled from 1796 LOC to modular components)

---

## v2.0.0 — General Availability

- Repository Health & Security
- Runtime Stability & Performance
- Desktop Polish
- Cross-platform packaging (AppImage, DEB, Windows NSIS/Portable)

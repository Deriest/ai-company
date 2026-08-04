# 29 — Product State

**Current Version:** See [`CHANGELOG.md`](../../CHANGELOG.md) for the current release (AI Engineering Company — Production), not pinned here.
**Build Status:** Active development
**Last Audit / Closeout:** 2026-07-30
**Authoritative SOT:** `docs/sot/62_PHASE_A_B_C_IMPLEMENTATION_PLAN.md`

---

## 1. Product Identity

AIC-ADE is an **AI Engineering Company** — bukan chatbot, bukan AI IDE, bukan coding assistant. User berperan sebagai **Engineering Manager** yang mengelola organisasi AI workers yang berkolaborasi melalui structured engineering workflows.

---

## 2. Feature Status Matrix

| Subsystem | Status | Implementation Details |
|---|---|---|
| **AIC Runtime** | Production | FastAPI backend, SQLite, Async Session, Task FSM |
| **Smart Routing** | Production | Fallback chain (Thinker → Crafter → Sprinter) via `ProviderManager.chat` |
| **Conversation System** | Production | Auto-titling, history search, instant deletion, copy controls |
| **Provider BYOK** | Production | Dynamic model fetch, probe endpoint, latency test |
| **Auto Updater** | Production | Verified SHA256 checksums, dismiss persistence, NSIS/AppImage |
| **Desktop UI** | Production | React 19, Tailwind v4, dark theme, Command Palette |
| **Self-Healing** | Production (v1.6.x) | `run_startup_self_heal()` in FastAPI lifespan |
| **Parallel Dispatcher** | Production (v1.6.x) | Real `issue_lease` calls |
| **AST Analysis** | Production (v1.6.x) | FileTree context menu → `GET /api/ast/analyze` |
| **Policy Engine** | Partial | Static scopes; not wired to execution path |
| **Skill Engine** | Production | 6 built-in skills, DB persistence, worker context injection |
| **MCP Integration** | Production | Protocol client (stdio/HTTP/SSE), tool discovery, execution, approval workflow |
| **Master Orchestrator** | Production | Chains Discovery→Planning→TaskGraph→Dispatch |
| **Tool Executor** | Production | Real tools: read_file, write_file, shell, explore, search |
| **Adaptive Runtime** | Production | Dynamic ContextPolicy, MemoryPolicy, WorkerPolicy |
| **Mission Workspace** | Production | Mission-based task management |
| **Evidence Center** | Production | Immutable SQLite audit trail |
| **Live Office Floor** | Production | 2D animated office visualization (15 desks + meeting area) |
| **Command Center** | Production | OpenCode-style chat with tool panels, agent modes |
| **Token Cost Tracking** | Production | Per-session cost via `/api/usage/stats` |

---

## 3. Critical Gaps (Current)

| Gap | Severity | Detail |
|-----|----------|--------|
| **Workers don't use tools** | 🔴 Critical | Workers are single-shot LLM calls — no tool calling, no multi-turn, no real code execution |
| **No file tree UI** | 🔴 Critical | Filesystem IPC exists but no standalone FileTree component |
| **No multi-project** | 🔴 Critical | Project model exists in DB but no CRUD API |
| **No PTY terminal UI** | 🟡 High | PTY IPC exists in main.ts but renderer component not verified |
| **Permission system not enforced** | 🟡 High | PolicyEngine + ToolPermissions exist but not called in execution path |
| **Dual event systems** | 🟡 High | EventBus (in-memory) and _emit_event (direct DB) not unified |
| **Context pipeline not wired** | 🟡 High | ContextPipeline and agents/context_assembly are separate systems |
| **No command palette UI** | 🟡 Medium | Ctrl+K registered but no palette component |
| **No git integration** | 🟡 Medium | No git status, diff, or commit operations |
| **No filesystem watcher** | 🟡 Medium | Files read on-demand, not watched for changes |

---

## 4. Roadmap Reference

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1** (Foundation Fixes) | Bugs, routing, dead code cleanup | ✅ Done |
| **Phase 2-6** (Pipeline + Features) | Master Orchestrator, Skills, MCP, Live Office | ✅ Done |
| **Phase A** (Foundation) | Multi-project, File Tree, Tool Execution, Permissions, Context | 📋 Planned |
| **Phase B** (Core) | Multi-Agent, PTY, Event Sourcing, Command Palette | 📋 Planned |
| **Phase C** (Integration) | Git, Model Selection, Cost Tracking, Session Recovery | 📋 Planned |

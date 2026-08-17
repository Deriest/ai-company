# 30 — Product Roadmap

**Vision:** AI Engineering Company — Organisasi engineering otonom
**Last verified:** v2.3.0 (2026-07-30)

---

## Completed Milestones

### v1.1.x — Production Hardening & Smart Routing ✅
- Smart Fallback Routing (Thinker → Crafter → Sprinter)
- Conversation auto-titling, history search, deletion
- Cross-platform packaging (AppImage, DEB, Windows NSIS/Portable)

### v1.2.x — Multi-Agent Parallel Execution ✅
- `ParallelDispatcher` with real lease issuance
- `plan_all_phases()` from workflow FSM
- Live Company execution DAG visualization

### v1.3.x — Workspace AST Analysis ✅
- Python AST via `ast` module; JS/TS via regex
- `GET /api/ast/analyze`, `GET /api/ast/generate-tests`

### v1.4.x — Policy & Audit ✅ (Partial)
- `policy/engine.py` (denials, approvals, file scope, role checks)
- `AuditLog` / events tables

### v1.5.x — Self-Healing ✅
- `SelfHealingEngine.audit_and_repair` at startup
- `POST /api/console/self-heal`

### v1.6.x — Stabilization & Recovery ✅
- Real `Dispatcher.issue_lease` calls
- Self-healing wired via `run_startup_self_heal()`

### v1.7.x — Adaptive Runtime ✅
- `AdaptiveRuntimeRegistry` builds `ModelCapabilities`
- Dynamic `ContextPolicy`, `MemoryPolicy`, `WorkerPolicy`
- `apply_worker_policy()` injection

### v1.9.x — AI Engineering Workspace ✅
- Mission Workspace
- Evidence Center (AuditView)
- Engineering Timeline
- Company View optimization

### v2.0.0 — General Availability ✅
- Repository Health & Security
- Runtime Stability & Performance
- Desktop Polish
- Release Verification (SHA256, 100% test pass)

### v2.0.1 — Desktop UX Excellence ✅
- Unified Design System (dark void/slate, cyan/teal)
- IDE Layout Shell (Activity Bar, Sidebar, Editor, Bottom Panel)
- Workspace & File Explorer

### v2.3.0 — AI Engineering Company Vision ✅
- **Live Office Floor** — 2D animated office visualization (15 desks + meeting area)
- **Command Center** — OpenCode-style chat with tool panels, agent modes
- **Skill Engine** — 6 built-in skills, custom skill creation, worker injection
- **MCP Integration** — Protocol client (stdio/HTTP/SSE), tool discovery, execution
- **Master Orchestrator** — Auto-chain Discovery→Planning→TaskGraph→Dispatch
- **Token Cost Tracking** — Per-session cost via usage API
- **Navigation Cleanup** — Dead views removed, Settings streamlined

---

## Current Phase: A-C Implementation

### Phase A: Foundation (Next)
| Feature | Status |
|---------|--------|
| Multi-Project Support | 📋 Planned |
| File Tree Component | 📋 Planned |
| Real Tool Execution (Worker ↔ ToolExecutor) | 📋 Planned |
| Agent-Tool Integration (Permission-aware) | 📋 Planned |
| Permission System (Full enforcement) | 📋 Planned |
| Context Management (Unified pipeline) | 📋 Planned |

### Phase B: Core
| Feature | Status |
|---------|--------|
| Multi-Agent Mode Switching | 📋 Planned |
| PTY Terminal UI | 📋 Planned |
| Context Usage Indicator | 📋 Planned |
| Event Sourcing (Unified) | 📋 Planned |
| Project-Scoped Sessions | 📋 Planned |
| Command Palette | 📋 Planned |
| Keyboard Shortcuts | 📋 Planned |

### Phase C: Integration
| Feature | Status |
|---------|--------|
| Git Integration | 📋 Planned |
| Filesystem Watcher | 📋 Planned |
| Model Selection | 📋 Planned |
| Tool Approval Flow | 📋 Planned |
| Web Fetch Tool | 📋 Planned |
| Subagent Spawning | 📋 Planned |
| Cost Tracking | 📋 Planned |
| Session Recovery | 📋 Planned |
| Error Recovery | 📋 Planned |

---

## Future Vision

### v3.0.0 — Fully Autonomous Engineering Company
- Workers benar-benar execute code (bukan hanya generate text)
- Multi-project workspace
- Real terminal integration
- Git operations (commit, diff, branch)
- Full event sourcing dengan session recovery
- Cost optimization (model routing berdasarkan cost/quality tradeoff)
- Multi-user collaboration (shared workspace)

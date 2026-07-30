# 03 — Architecture

**Architecture Style:** Desktop-Sidecar Monolith with Async Event Loop
**Version:** v2.3.0

---

## 1. System Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIC ADE Desktop (Electron)                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              React 19 Renderer (Vite 6 + Tailwind v4)    │  │
│  │  [Office] [Command Center] [Live Company] [Skills] [MCP] │  │
│  │  [FileTree] [Terminal] [Command Palette]                  │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │ IPC / Preload                      │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │                 Electron Main Process                     │  │
│  │  Sidecar Manager │ PTY │ Auto Updater │ File System IPC  │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────┘
                             │ HTTP / SSE / WebSocket
┌────────────────────────────┴────────────────────────────────────┐
│                    aic-platform (Python 3.12)                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  FastAPI Backend Daemon                   │  │
│  │  23 routers: providers, conversations, chat, workers,     │  │
│  │  skills, mcp, orchestration, workflows, jobs, memory,     │  │
│  │  rag, automation, pipeline, dashboard, context, usage,    │  │
│  │  discovery, planning, taskgraph, dispatcher, verification,│  │
│  │  delivery, autonomy, profile                             │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │              Conversation Engine (Intent Routing)          │  │
│  │  classify_intent() → task_request → Master Orchestrator   │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │          Master Orchestrator (Pipeline Engine)             │  │
│  │  Discovery → Planning → TaskGraph → Dispatch              │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │              Worker Runtime (15 specialized workers)       │  │
│  │  ToolExecutor │ ContextAssembly │ SkillEngine │ EventBus  │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │                                     │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │                  Provider Manager                          │  │
│  │     Smart Tier Fallback (Thinker → Crafter → Sprinter)    │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                            │ Async SQLite                        │
│  ┌─────────────────────────┴─────────────────────────────────┐  │
│  │               Database Storage (aic.db)                    │  │
│  │  69 tables: tasks, projects, conversations, workers,      │  │
│  │  skills, mcp, memory, rag, events, leases, ...            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Key Subsystem Interactions

- **IPC & Health Check:** Main process launches `aic-platform` as a sidecar. Preload polls `http://127.0.0.1:8000/health` until ready.
- **REST & SSE Streaming:** Chat messages stream via SSE (`/chat/stream`). Tool events stream alongside text chunks.
- **WebSocket:** Real-time events for phase advances, worker status, pipeline progress.
- **Intent Routing:** Chat input → `classify_intent()` → if `task_request` → Master Orchestrator chains the full pipeline.
- **Tool Execution:** Workers use `ToolExecutor` (read_file, write_file, shell, explore, search) for real operations.
- **Skill Injection:** Active skills resolved per worker type, injected into LLM system prompt.
- **MCP Integration:** External tool servers connected via JSON-RPC (stdio/HTTP/SSE), tools discovered and callable from chat.

---

## 3. Navigation Structure

```
Sidebar:
  🏠 Office           — Live Office Floor (animated 2D visualization)
  ❯ Command Center    — OpenCode-style chat with tool panels
  👥 Live Company      — Org chart (15 workers × 4 departments) + token cost
  🔧 Skills            — Skill registry (manage, create, toggle)
  🔌 MCP Servers       — MCP server management (connect, discover, execute)
  ⚙️ Settings          — General | Providers | Auto Approve
```

---

## 4. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Chat = Command Center** | Unified entry point with intent-based routing, not separate chat/task UIs |
| **Sidecar architecture** | Engine runs as separate process (crash isolation, independent updates) |
| **SQLite local-first** | All data on-machine, no cloud dependency |
| **Tier-based model routing** | Different tasks use different model capabilities |
| **Tool execution via ToolExecutor** | Workers do real operations, not just text generation |
| **Event-driven pipeline** | Master Orchestrator chains engines via events |

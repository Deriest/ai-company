# SoT: Phase A-C — 90% OpenCode Parity Implementation Plan

**Version:** 1.0.0
**Date:** 2026-07-30
**Status:** Active
**Depends on:** `docs/GAP_ANALYSIS_AND_ROADMAP.md`, `docs/sot/61_PHASE1_FOUNDATION_FIXES.md`

---

## 1. Objective

Transform AIC-ADE from "chatbot yang bicara tentang kode" menjadi "organisasi engineering yang benar-benar mengerjakan kode" — mencapai 90% parity dengan OpenCode Desktop.

**Target:** 22 features across 3 phases (A: Foundation, B: Core, C: Integration).

---

## 2. Current State Assessment

| Subsystem | Status | Key Finding |
|-----------|--------|-------------|
| **Project Model** | DB model exists, NO API | `Project` table di storage.models, tapi tidak ada CRUD endpoint |
| **Filesystem IPC** | Complete backend (7 handlers) | `read-dir`, `read-file`, `write-file`, `delete-file`, `rename-file`, `select-directory`, `select-file` — semua ada di main.ts + preload. Tidak ada file watcher. |
| **Worker Execution** | Runs tapi single-shot LLM | Workers: prompt → LLM → text response. Tidak ada tool calling, tidak ada multi-turn. `ToolExecutor` ada tapi tidak dipakai workers. |
| **Context Management** | Dua sistem paralel | `ContextPipeline` (token budgeting, multi-source) dan `agents/context_assembly.py` (string concat) — tidak saling bicara. |
| **Permission System** | Ada tapi tidak dipakai | `PolicyEngine` + `ToolPermissions` di registry — tidak pernah dipanggil di execution path. |
| **Event Sourcing** | Dua sistem paralel | `EventBus` (in-memory pub/sub) dan `_emit_event` (direct DB + WebSocket) — tidak terhubung. |
| **PTY/Terminal** | Full IPC, UI belum dicek | `node-pty` terintegrasi di main.ts, preload expose `termStart/Write/Resize/Kill`. Perlu verify renderer component. |

---

## 3. Phase A: Foundation (Features #1-6)

### A1. Multi-Project Support

**Current:** `Project` model exists di `storage/models.py` (id, name, slug, description, repo_path, status, config, owner_id). Tidak ada CRUD API.

**Changes:**

| File | Action |
|------|--------|
| `backend/api/routes/projects.py` | **NEW** — CRUD: `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`, `POST /projects/{id}/set-active` |
| `backend/main.py` | Register `projects_router` |
| `aic-ide/src/renderer/src/lib/api/projects.ts` | **NEW** — API client |
| `aic-ide/src/renderer/src/components/ProjectPicker.tsx` | **NEW** — Dropdown/sidebar project selector |
| `aic-ide/src/renderer/src/components/AppShell.tsx` | Add project picker ke header |

**API Design:**
```
POST   /projects              — Create project (name, description, repo_path)
GET    /projects              — List all projects
GET    /projects/{id}         — Get project detail
PATCH  /projects/{id}         — Update project
DELETE /projects/{id}         — Delete project
POST   /projects/{id}/set-active — Set active project (session scope)
```

**Session Scoping:** Setiap conversation punya `project_id`. Semua file operations, task creation, dan context assembly scoped ke active project.

---

### A2. File Tree Component

**Current:** `main.ts` punya `aic:read-dir-tree` IPC handler yang return `DirTreeNode[]`. `useWorkspace.ts` manage `fileTree` state. Tapi tidak ada standalone FileTree component.

**Changes:**

| File | Action |
|------|--------|
| `aic-ide/src/renderer/src/components/FileTree.tsx` | **NEW** — Reusable file tree component dengan: expand/collapse, file icons, click-to-open, right-click context menu |
| `aic-ide/src/renderer/src/components/AppShell.tsx` | Add file tree panel di sidebar (below project picker) |
| `aic-ide/src/main/main.ts` | Add `aic:watch-files` IPC handler (chokidar/fs.watch) |
| `aic-ide/src/preload/preload.ts` | Expose `watchFiles(path, cb)`, `unwatchFiles(path)` |

**FileTree Component Design:**
```
┌─────────────────────┐
│ 📂 src/              │  ← folder, click to expand
│   📂 components/     │
│     📄 App.tsx       │  ← file, click to open
│     📄 ChatView.tsx  │
│   📂 lib/            │
│     📄 api.ts        │
│ 📄 package.json      │
│ 📄 tsconfig.json     │
└─────────────────────┘
```

**File Watcher:** Watch active project directory, emit IPC events on file changes, update tree in real-time.

---

### A3. Real Tool Execution (Worker ↔ ToolExecutor)

**Current:** `ToolExecutor` di `workers/tools.py` punya `read_file`, `write_file`, `shell`, `explore`, `search`. Tapi workers di `workers/base.py` tidak pakai — mereka cuma `_llm_or_fallback()` (single prompt/response).

**Changes:**

| File | Action |
|------|--------|
| `workers/base.py` | Refactor `_llm_or_fallback()` → `_llm_with_tools()` yang: (1) inject tool definitions ke LLM messages, (2) parse tool calls dari LLM response, (3) execute via ToolExecutor, (4) feed results back, (5) loop max N rounds |
| `llm/provider.py` | Add `tools` parameter ke `chat()` method — pass OpenAI function-calling schema ke provider |
| `workers/tools.py` | Add `to_openai_schema()` method ke ToolCall untuk format function-calling |

**Tool-Use Loop:**
```
1. Build messages: system_prompt + task_context + user_prompt
2. Add tool definitions (OpenAI function-calling format)
3. Call LLM
4. If LLM returns tool_calls:
   a. For each tool_call: execute via ToolExecutor
   b. Append tool results to messages
   c. Go to step 3
5. If LLM returns text (no tool_calls): return final response
6. Max 10 rounds, then force return
```

**Tools Available to Workers:**
| Tool | Description | Workers |
|------|-------------|---------|
| `read_file` | Read file from project | All |
| `write_file` | Write file to project | backend, frontend, coding, database |
| `shell` | Execute shell command | backend, frontend, coding, devops, deployment |
| `explore` | List directory tree | All |
| `search` | Grep-like content search | All |
| `edit_file` | Find & replace in file | backend, frontend, coding |

---

### A4. Agent-Tool Integration (Permission-Aware)

**Current:** `ToolPermissions` di `agents/registry.py` define allowed/restricted/prohibited per agent. `check_tool_permission()` di `tool_permissions.py` ada tapi tidak dipanggil.

**Changes:**

| File | Action |
|------|--------|
| `workers/base.py` | Sebelum execute tool, call `check_tool_permission(worker_type, tool_name)`. Jika denied → skip tool, report ke LLM. |
| `workers/tools.py` | Add `permission_checker` callback ke `ToolExecutor.__init__()` |
| `backend/services/tool_permissions.py` | Add `get_tools_schema_for_worker(worker_type)` — return hanya tools yang diizinkan |
| `runtime/executor.py` | Wire `PolicyEngine.evaluate()` sebelum worker execution |

**Permission Flow:**
```
Worker wants to call tool
    │
    ▼
check_tool_permission(worker_type, tool_name)
    │
    ├── allowed → execute
    ├── restricted → require user approval (TODO: approval UI)
    └── prohibited → deny, tell LLM "this tool is not available"
```

---

### A5. Permission System (Full Enforcement)

**Current:** `PolicyEngine.evaluate()` punya 7-layer evaluation (hard denials, always-approval, role check, file scope, sensitive path, task state, worker-phase). Tapi tidak pernah dipanggil.

**Changes:**

| File | Action |
|------|--------|
| `runtime/executor.py` | Call `policy.evaluate()` sebelum worker execution. Jika DENY → skip worker, log reason. Jika REQUIRE_APPROVAL → pause, notify user via WebSocket. |
| `backend/services/tool_chat_service.py` | Wire `check_tool_permission()` sebelum MCP/tool execution |
| `backend/api/routes/approval.py` | **NEW** — `POST /approval/{id}/approve`, `POST /approval/{id}/deny` |
| `aic-ide/src/renderer/src/components/ApprovalDialog.tsx` | **NEW** — Modal untuk approve/deny tool executions |

**Approval Flow:**
```
Worker tries restricted tool
    │
    ▼
Create ApprovalRequest (DB)
    │
    ▼
WebSocket → Frontend shows ApprovalDialog
    │
    ├── User approves → execute tool, continue
    └── User denies → skip tool, tell LLM "user denied this action"
```

---

### A6. Context Management (Unified Pipeline)

**Current:** `ContextPipeline` (token budgeting, 5 sources) dan `agents/context_assembly.py` (string concat) — dua sistem paralel.

**Changes:**

| File | Action |
|------|--------|
| `agents/context_assembly.py` | Refactor `assemble_system_prompt()` untuk pakai `ContextPipeline` alih-alih string concat |
| `context/sources.py` | Add `CodeContextSource` — baca actual source files dari project (bukan hanya config files) |
| `context/sources.py` | Add `ToolHistorySource` — include recent tool executions dalam context |
| `context/builder.py` | Add `format_for_worker(worker_type, phase)` — format context sesuai worker needs |
| `runtime/executor.py` | Wire `ContextBuilder` ke worker context assembly |

**Context Sources (priority order):**
```
1. ConversationSource (priority 5)  — recent messages
2. RAGSource (priority 10)          — document retrieval
3. KnowledgeSource (priority 15)    — knowledge base
4. MemorySource (priority 20)       — multi-scope memory
5. WorkspaceSource (priority 25)    — project config files
6. CodeContextSource (priority 30)  — NEW: actual source code
7. ToolHistorySource (priority 35)  — NEW: recent tool executions
```

---

## 4. Phase B: Core (Features #7-13)

### B1. Multi-Agent Mode Switching

**Current:** Build/plan tabs exist di ChatView. `AGENT_WORKER_MAP` maps `build→backend`, `plan→research`. Tapi plan mode tidak benar-benar read-only.

**Changes:**

| File | Action |
|------|--------|
| `workers/base.py` | Add `is_read_only` flag ke BaseWorker. Plan mode workers cannot call `write_file`, `shell`, `edit_file`. |
| `backend/services/tool_chat_service.py` | Check agent mode sebelum execute tools. Plan mode: deny write tools. |
| `aic-ide/src/renderer/src/components/ChatView.tsx` | Show mode indicator di status bar. Visual diff antara build/plan. |

---

### B2. PTY Terminal UI

**Current:** Full PTY support di main.ts + preload. IPC: `termStart`, `termWrite`, `termResize`, `termKill`, `onTermData`. Perlu verify renderer component.

**Changes:**

| File | Action |
|------|--------|
| `aic-ide/src/renderer/src/components/Terminal.tsx` | **NEW** — xterm.js terminal component. Connect ke `window.aic.termStart/Write/onTermData`. |
| `aic-ide/src/renderer/src/components/AppShell.tsx` | Add terminal panel di bottom (toggle dengan `Ctrl+``) |
| `package.json` | Add `@xterm/xterm` + `@xterm/addon-fit` dependencies |

**Layout:**
```
┌──────────┬────────────────────────────┐
│ Sidebar  │ Chat Area                  │
│ (file    │                            │
│  tree +  │                            │
│  sessions│                            │
│ )        ├────────────────────────────┤
│          │ Terminal (toggle Ctrl+`)   │
│          │ $ _                        │
└──────────┴────────────────────────────┘
```

---

### B3. Context Usage Indicator

**Current:** Tidak ada token/cost tracking per message.

**Changes:**

| File | Action |
|------|--------|
| `backend/services/chat_service.py` | Return `usage` (prompt_tokens, completion_tokens, cost) di setiap response |
| `aic-ide/src/renderer/src/lib/api/chat.ts` | Parse `usage` dari SSE events |
| `aic-ide/src/renderer/src/components/ChatView.tsx` | Show token count + cost per message dan per session di status bar |

**Status Bar Design:**
```
● connected · build agent · Hermes · 1,234 tokens · $0.03
```

---

### B4. Event Sourcing (Unified)

**Current:** `EventBus` (in-memory) dan `_emit_event` (direct DB) — dua sistem paralel.

**Changes:**

| File | Action |
|------|--------|
| `runtime/executor.py` | Replace `_emit_event()` dengan `bus.publish()` + `recorder.record()` |
| `backend/main.py` | Wire `subscribe_recorder()` at startup |
| `events/recorder.py` | Make recorder a wildcard subscriber on the bus |

---

### B5. Project-Scoped Sessions

**Current:** `Conversation` punya optional `project_id`. Tapi tidak enforced.

**Changes:**

| File | Action |
|------|--------|
| `backend/api/routes/conversations.py` | Require `project_id` di `create_conversation`. Scope list/filter by project. |
| `runtime/executor.py` | Use conversation's `project_id` untuk scope file operations |
| `workers/tools.py` | `ToolExecutor` receives `project_root` and scopes all file operations to it |

---

### B6. Command Palette

**Current:** `Ctrl+K` shortcut registered, tapi tidak ada palette UI component.

**Changes:**

| File | Action |
|------|--------|
| `aic-ide/src/renderer/src/components/CommandPalette.tsx` | **NEW** — Fuzzy search across: views, recent sessions, workers, commands. Modal overlay. |
| `aic-ide/src/renderer/src/App.tsx` | Wire palette component + state |

---

### B7. Keyboard Shortcuts

**Current:** `Ctrl+K` for palette. Tidak ada shortcuts lain.

**Changes:**

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Switch ke Office view |
| `Ctrl+2` | Switch ke Command Center |
| `Ctrl+3` | Switch ke Live Company |
| `Ctrl+4` | Switch ke Skills |
| `Ctrl+5` | Switch ke MCP Servers |
| `Ctrl+6` | Switch ke Settings |
| `Ctrl+N` | New session |
| `Ctrl+`` ` | Toggle terminal |
| `Ctrl+Shift+P` | Command palette |
| `Ctrl+Enter` | Send message |

---

## 5. Phase C: Integration (Features #14-22)

### C1. Git Integration

| Change | Detail |
|--------|--------|
| `workers/tools.py` | Add `git_status()`, `git_diff()`, `git_commit()` tools |
| `context/sources.py` | Add `GitContextSource` — include git status/diff dalam context |

### C2. Filesystem Watcher

| Change | Detail |
|--------|--------|
| `main.ts` | Add `aic:watch-files` IPC dengan `fs.watch` |
| `preload.ts` | Expose `watchFiles`, `unwatchFiles` |
| `FileTree.tsx` | Auto-refresh on file changes |

### C3. Model Selection

| Change | Detail |
|--------|--------|
| `backend/api/routes/providers.py` | Add `POST /providers/select-model` — user pilih model per tier |
| `llm/provider.py` | Read selected model dari DB, bukan hardcoded |
| `ChatView.tsx` | Add model selector dropdown di header |

### C4. Tool Approval Flow

(Detail di A5 — bagian dari permission system)

### C5. Web Fetch Tool

| Change | Detail |
|--------|--------|
| `workers/tools.py` | Add `web_fetch(url)` tool — HTTP GET, return content |
| `backend/services/tool_chat_service.py` | Register `web_fetch` sebagai available tool |

### C6. Subagent Spawning

| Change | Detail |
|--------|--------|
| `runtime/executor.py` | Add `spawn_subagent(task_context, worker_type)` — create child task, execute, return result |
| `workers/base.py` | Add `BaseWorker.spawn_child(worker_type, prompt)` method |

### C7. Cost Tracking

| Change | Detail |
|--------|--------|
| `backend/services/chat_service.py` | Track cost per message (prompt_tokens × price + completion_tokens × price) |
| `ChatView.tsx` | Show per-message cost badge |
| `backend/api/routes/usage.py` | Add `GET /usage/by-session/{id}` — per-session cost |

### C8. Session Recovery

| Change | Detail |
|--------|--------|
| `events/recorder.py` | Add `replay(session_id)` — replay events untuk reconstruct state |
| `backend/main.py` | On startup: check for interrupted sessions, replay events |

### C9. Error Recovery

| Change | Detail |
|--------|--------|
| `workers/base.py` | Add retry logic di `_llm_with_tools()` — tool failure → retry with context |
| `runtime/executor.py` | Wire error events ke EventBus → frontend notification |

---

## 6. File Inventory

### New Files

| File | Phase | Purpose |
|------|-------|---------|
| `backend/api/routes/projects.py` | A1 | Project CRUD API |
| `backend/api/routes/approval.py` | A5 | Approval flow API |
| `aic-ide/src/renderer/src/components/FileTree.tsx` | A2 | File tree component |
| `aic-ide/src/renderer/src/components/ProjectPicker.tsx` | A1 | Project selector |
| `aic-ide/src/renderer/src/components/Terminal.tsx` | B2 | xterm.js terminal |
| `aic-ide/src/renderer/src/components/CommandPalette.tsx` | B6 | Command palette |
| `aic-ide/src/renderer/src/components/ApprovalDialog.tsx` | A5 | Tool approval modal |
| `aic-ide/src/renderer/src/lib/api/projects.ts` | A1 | Projects API client |

### Modified Files

| File | Phase | Changes |
|------|-------|---------|
| `workers/base.py` | A3,A4 | Tool-use loop, permission checks |
| `workers/tools.py` | A3 | OpenAI schema, permission checker callback |
| `llm/provider.py` | A3 | `tools` parameter support |
| `agents/context_assembly.py` | A6 | Wire ContextPipeline |
| `context/sources.py` | A6 | CodeContextSource, ToolHistorySource |
| `runtime/executor.py` | A4,A5,B4 | PolicyEngine, EventBus, ContextBuilder |
| `backend/services/tool_chat_service.py` | A4 | Permission checks |
| `backend/main.py` | A1,B4 | Register routes, wire recorder |
| `aic-ide/src/renderer/src/App.tsx` | B6 | Command palette |
| `aic-ide/src/renderer/src/components/AppShell.tsx` | A1,A2,B2 | Project picker, file tree, terminal |
| `aic-ide/src/renderer/src/components/ChatView.tsx` | B1,B3 | Mode indicator, cost display |
| `aic-ide/src/main/main.ts` | A2 | File watcher IPC |
| `aic-ide/src/preload/preload.ts` | A2 | Watch API |
| `events/recorder.py` | B4 | Replay capability |

---

## 7. Acceptance Criteria

### Phase A Complete When:
- [ ] User can create/switch projects from UI
- [ ] File tree shows project files, updates on changes
- [ ] Workers execute real tools (read/write/shell/search)
- [ ] Tool calls respect agent permissions
- [ ] PolicyEngine enforced before worker execution
- [ ] Context uses unified pipeline with token budgeting

### Phase B Complete When:
- [ ] Build/plan modes have different tool access
- [ ] Terminal is embedded and functional
- [ ] Token/cost shown per message and in status bar
- [ ] All events flow through unified EventBus
- [ ] Sessions are project-scoped
- [ ] Command palette works with Ctrl+K
- [ ] Keyboard shortcuts work (Ctrl+1-6, Ctrl+`, Ctrl+N)

### Phase C Complete When:
- [ ] Git status/diff available as context
- [ ] File tree auto-refreshes on changes
- [ ] User can select model per tier from UI
- [ ] Tool approval dialog works for restricted tools
- [ ] Web fetch tool available
- [ ] Subagent spawning works
- [ ] Cost tracked per message and per session
- [ ] Session recovery after crash works
- [ ] Tool failures retry with context

---

## 8. Effort Estimation

| Phase | Features | Estimated Days |
|-------|----------|---------------|
| **Phase A** | #1-6 (Foundation) | 5-7 days |
| **Phase B** | #7-13 (Core) | 4-5 days |
| **Phase C** | #14-22 (Integration) | 3-4 days |
| **Total** | 22 features | **12-16 days** |

---

## 9. Dependencies & Ordering

```
A1 (Multi-Project) ──→ A2 (File Tree) ──→ B5 (Project-Scoped Sessions)
       │
       ├──→ A3 (Tool Execution) ──→ A4 (Agent-Tool) ──→ B1 (Multi-Agent)
       │
       └──→ A5 (Permissions) ──→ C4 (Tool Approval)
       
A6 (Context) ──→ B3 (Context Usage Indicator)

B2 (PTY) ──→ independent
B4 (Event Sourcing) ──→ C8 (Session Recovery)
B6 (Command Palette) ──→ B7 (Keyboard Shortcuts)

C1-C9 ──→ mostly independent, can be parallel
```

# AIC-ADE Gap Analysis & Roadmap
## "AI Engineering Company" Vision vs Current Implementation

**Date:** 2026-07-26  
**Status:** Draft  
**Scope:** Full platform (aic-platform, aic-ide, aic-skill)

---

## 1. Executive Summary

AIC-ADE memiliki fondasi arsitektur yang **sangat ambisius dan visioner** — 15 AI agents dengan departemen, FSM lifecycle, discovery/planning/verification engines, dan UI desktop yang profesional. Namun, terdapat **gap kritis** antara desain arsitektural dan eksekusi nyata:

| Aspek | Kondisi Saat Ini |
|-------|-----------------|
| **Arsitektur** | Chat sebagai unified entry point sudah tepat, tapi intent routing ke pipeline belum chain dengan benar |
| **Workers** | Didefinisikan dengan baik di registry, tapi eksekusinya hanya chat completion |
| **Lifecycle** | Discovery→Planning→TaskGraph→Dispatcher terputus di setiap sambungan |
| **UI/UX** | Dashboard dan views penting kosong (data array `[]`), 7 views unreachable |
| **Dispatcher** | Simulasi — semua task langsung di-mark completed tanpa eksekusi nyata |

**Kesimpulan:** Project ini memiliki *blueprint* yang tepat untuk "AI Engineering Company", tetapi implementasinya masih berupa **kerangka yang belum terhubung**. Yang dibutuhkan bukan rebuild dari nol, melainkan **koneksi dan aktivasi** dari komponen-komponen yang sudah ada.

---

## 2. Gap Analysis — Backend Architecture

### 2.1 Intent-Based Routing: Desain Sudah Tepat, Eksekusi Terputus

**Desain yang benar:** Chat (Command Center) adalah **unified entry point** untuk semua interaksi. Intent detection di dalamnya menentukan routing:

```
User mengetik di Command Center
        │
        ▼
   Intent Detection
        │
   ┌────┼────────────┬──────────────┐
   │    │            │              │
 chat  task_request  approval     status
   │    │            │              │
   ▼    ▼            ▼              ▼
 Chat  Discovery    Resume FSM    Tampilkan
 Svc   → Planning   phase         progress
       → TaskGraph
       → Dispatcher
```

Ini adalah arsitektur yang tepat — Engineering Manager berkomunikasi via Command Center, sistem mendeteksi intent dan merutekan ke pipeline yang sesuai.

**Masalahnya bukan "dua arsitektur bersaing"**, melainkan:

1. **Pipeline setelah intent=task_request tidak chain otomatis:** Ketika intent terdeteksi sebagai `task_request`, ConversationEngine memicu Discovery, tapi setelah Discovery menghasilkan Brief → Planning tidak auto-trigger. Planning menghasilkan Plan → TaskGraph tidak auto-trigger. Setiap sambungan terputus dan memerlukan user manual trigger ("yes / go ahead").

2. **Intent detection di-triplicate:** Tiga implementasi regex yang sama di `ConversationEngine._detect_intent()`, `IntentClassifier._classify_base_intent()`, dan `IntentClassifier.classify()`. Rawan drift seiring waktu.

3. **Dispatcher di ujung pipeline masih simulasi:** Bahkan jika pipeline berhasil chain sampai Dispatcher, task langsung di-mark completed tanpa menjalankan worker.

4. **ConversationEngine punya simplified pipeline sendiri:** `_evaluate_intake_completeness()` (6 regex fields) dan `_handle_task_request()` menggunakan intake evaluation yang lebih sederhana daripada `DiscoveryEngine._run_pipeline()` (full pipeline dengan ambiguity detection, readiness scoring, multi-round clarification). Keduanya berjalan paralel — yang mana yang aktif tergantung entry point.

**Rekomendasi:** Bukan menghapus salah satu jalur, tapi **menyatukan** — ConversationEngine harus menjadi entry point tunggal yang mendelegasikan ke DiscoveryEngine (bukan menggunakan simplified pipeline sendiri), dan Discovery→Planning→TaskGraph→Dispatcher harus chain secara otomatis.

### 2.2 Workers Tidak Benar-Benar Bekerja

**Problem:** `OrchestratorService._execute_task_body()` hanya mengirim chat message ke LLM dan menyimpan response. Tidak ada:
- File system access (baca/tulis kode)
- Code execution atau test run
- Tool invocation (MCP atau lainnya)
- Pemanggilan `worker.execute()` dari worker registry
- Handoff propagation antar worker

**Exception:** `TestingWorker` adalah satu-satunya worker yang melakukan verifikasi nyata (baca filesystem, cek syntax, jalankan pytest).

**Agent Registry (kekuatan terbesar):**
- 15 agents dengan nama, kepribadian, filosofi engineering, anti-patterns ✅
- 4 departemen: Leadership, Product, Engineering, Platform ✅
- Context assembly yang melayer soul + constraints + tools + handoffs ✅
- ToolPermissions didefinisikan tapi **tidak pernah di-enforce** ❌
- HeartbeatPolicy didefinisikan tapi **tidak pernah dijadwalkan** ❌

### 2.3 Lifecycle Engines Terputus

Setiap engine berdiri sendiri dan tidak otomatis mengalir ke engine berikutnya:

```
DiscoveryEngine → [BREAK] → PlanningEngine → [BREAK] → TaskGraphEngine → [BREAK] → DispatcherEngine
                                                                                         ↓
                                                                            (simulasi, bukan eksekusi)
```

| Sambungan | Status | Masalah |
|-----------|--------|---------|
| Discovery → Planning | Terputus | Brief dihasilkan tapi tidak auto-trigger planning |
| Planning → TaskGraph | Terputus | Plan dihasilkan tapi user harus manual trigger |
| TaskGraph → Dispatcher | Terputus | Graph dihasilkan, terminal state `handoff_to_dispatcher` tapi tidak ada observer |
| Dispatcher → Execution | Simulasi | Task langsung mark completed, tidak invoke worker |

### 2.4 Event Bus Tidak Digunakan

- `EventBus` (in-memory pub/sub) ada tapi **core executor tidak publish ke bus**
- Executor langsung write ke DB via `Event` ORM, bypass bus
- Tidak ada engine yang subscribe ke events
- `WorkerEventEmitter` di dispatcher terpisah dari main bus

### 2.5 Intent Detection Triplikasi

Tiga implementasi regex yang sama untuk intent classification:
1. `ConversationEngine._detect_intent()` (conversation/engine.py)
2. `IntentClassifier._classify_base_intent()` (discovery/intent.py)
3. `IntentClassifier.classify()` (discovery/intent.py)

Akan drift seiring waktu.

### 2.6 Bugs Kritis

| Bug | Lokasi | Impact |
|-----|--------|--------|
| Duplicate ConversationEngine invocation | core.py:853-900 | LLM dipanggil 2x untuk task intents |
| Progress map pakai phase name lama | engine.py:228-244 | Progress selalu 0% untuk most phases |
| PM review gate cek "documentation" bukan "closeout" | engine.py:82 | PM review gate tidak pernah fire |
| `core.py` 1010 baris (4-5 modul digabung) | api/routes/core.py | Maintainability nightmare |
| `datetime.utcnow()` deprecated | core.py:201 | Akan break di Python versi baru |
| Streaming chat fake-SSE | core.py:892-900 | Response di-chunk 20 char, bukan true streaming |

---

## 3. Gap Analysis — Workflow & Lifecycle

### 3.1 FSM (Workflow State Machine)

**Kekuatan:**
- Phase pipeline: `created → discovery → investigate → planning → implementation → verification → closeout → completed`
- Barrier system (semua worker harus selesai sebelum phase berikutnya)
- Fail-closed semantics (timeout tidak auto-satisfy)
- Smart Triage: L1 QUICK → L4 FULL dengan guardrail escalation

**Kelemahan:**
- Barrier didefinisikan tapi tidak dipakai di runtime executor
- `WorkflowEngine.advance()` dead code — executor pakai `next_phase()` langsung
- Workers dijalankan sequential, bukan parallel
- Approval gate stop execution tapi tidak ada mekanisme resume

### 3.2 Verification

**Kekuatan:**
- `TestingWorker` melakukan real verification (filesystem, syntax, pytest)
- State machine 8-step didefinisikan

**Kelemahan:**
- `VerificationEngine` superficial — requirement "pass" jika any task completed
- Quality scores hardcoded (documentation=70%, security=90%)
- State machine tidak pernah ditraverse (jump langsung ke COMPLETE)
- Tidak terintegrasi ke FSM lifecycle

### 3.3 Delivery

**Kekuatan:**
- Continuous improvement model dengan `LessonLearned`
- Engineering Report structure komprehensif

**Kelemahan:**
- Tidak ada actual delivery (deployment, packaging, release)
- "Delivery" = generate report saja
- Quality score selalu 0.0

### 3.4 Context Engine

**Kekuatan:**
- Pipeline architecture: sources → retrieve → merge → sort → trim to budget
- Token budget management
- Multiple format styles

**Kelemahan:**
- Tidak dipakai untuk inter-worker context propagation
- Search substring-based, bukan semantic
- Decision records in-memory only di singleton

---

## 4. Gap Analysis — Frontend (IDE)

### 4.1 Dashboard Kosong

`WorkspaceView` adalah view terpenting untuk visi "Engineering Manager" tapi **semua data source adalah empty array**:
- `const stats = []` — tidak ada stat cards
- `const activity = []` — tidak ada activity feed
- Quick Actions buttons tidak punya click handlers
- Comment: `// No backend endpoint exists — using local state (by design)`

Padahal `useWorkspace` hook **sudah fetch** data dari backend (workers, projects, tasks, overview) tapi **tidak pernah pass ke child components**.

### 4.2 Seven Views Unreachable

**Bug kritis di `App.tsx` lines 99-106:** Views berikut di-route ke `<SettingsView>` alih-alih component mereka sendiri:

| View | Status | Lines of Code |
|------|--------|--------------|
| `OrchestrationView` | Functional, unreachable | 309 lines |
| `WorkflowsView` | Functional, unreachable | 252 lines |
| `JobsView` | Functional, unreachable | 302 lines |
| `MCPView` | Functional, unreachable | ~200 lines |
| `MemoryView` | Functional, unreachable | ~200 lines |
| `RAGView` | Functional, unreachable | ~200 lines |
| `AutomationView` | Functional, unreachable | ~200 lines |

Total: ~1600+ baris UI yang fully functional tapi tidak bisa diakses user.

### 4.3 Chat-Centric UX

- ChatView adalah **ChatGPT clone** yang polished — tapi salah konsep
- Placeholder text: "Type a message to store in SQLite..." (expose implementation detail)
- Nav item #2 adalah "Chat" dengan `MessageSquare` icon
- Native menu: "Talk to Hermes"
- Untuk visi "Engineering Manager", ini seharusnya "Command Center" / "Dispatch Console"

### 4.4 Missing Views untuk Visi

| View yang Hilang | Deskripsi |
|-----------------|-----------|
| **Org Chart** | Visualisasi 15 workers dalam 4 departemen |
| **Worker Profiles** | Detail per worker: skills, tasks, performance, system prompt |
| **Project Pipeline / Kanban** | Visual pipeline showing work flowing through stages |
| **Approval Queue** | Center untuk approve/reject (OrchestrationView sudah punya ini tapi unreachable) |
| **Performance Analytics** | Team velocity, completion rates, cost per mission |
| **Resource Allocation** | Assign workers ke projects, balance workload |
| **Notification Center** | Bell icon di-import tapi tidak pernah dipakai |
| **Command Palette (visible)** | Cmd+K wired tapi palette component tidak ada di UI |

### 4.5 Data Architecture Issues

- Tidak ada global state store (Redux/Zustand/Jotai)
- Dua competing API clients: `apiClient` vs `runtimeClient`
- `useChat` hook defined tapi tidak pernah instantiated di `App.tsx`
- `useBoot` returns 25+ state values tapi most tidak dikonsumsi child components
- `AppShell` props (`health`, `modelLabel`, `alertCount`) tidak pernah di-pass dari `App.tsx`

### 4.6 Views yang Sudah Bagus

| View | Assessment |
|------|-----------|
| **LiveCompanyView** | Worker cards dengan status, metrics — paling vision-aligned |
| **OrchestrationView** | Multi-agent sessions, task dependencies, approvals (tapi unreachable) |
| **Settings (Auto Approve)** | Manual/Semi/Full automation dengan scope toggles — tepat untuk EM |
| **Onboarding** | Profile creation + provider setup — tapi kurang "company setup" |

---

## 5. Gap Analysis — Transparency & Control

### 5.1 Yang Sudah Ada
- Evidence Center (immutable audit trail) — tapi view-nya empty
- Timeline view — tapi empty
- WebSocket untuk real-time updates — tapi underused
- Task event chain dengan `prev_event_target` — traceable

### 5.2 Yang Kurang
- **No project-level overview** — tidak ada bird's-eye view of all active work
- **No worker decision audit** — alasan di balik keputusan worker tidak terekspos
- **No cost tracking per mission** — user tidak tahu berapa LLM token/cost per task
- **No approval workflow di UI** — approval gate ada di backend tapi UI-nya unreachable
- **No notification system** — user tidak di-alert ketika ada blocker, completion, atau error

---

## 6. Recommended Architecture: Master Orchestrator

Solusi utama adalah membangun **satu master orchestrator** yang menghubungkan semua engine. Chat (Command Center) tetap sebagai unified entry point — intent detection merutekan ke pipeline yang sesuai:

```
User mengetik di Command Center (chat = unified entry point)
        │
        ▼
   Intent Detection (ConversationEngine)
        │
   ┌────┼────────────┬──────────────┐
   │    │            │              │
 chat  task_request  approval     status
   │    │            │              │
   ▼    ▼            ▼              ▼
 Chat  Master Orchestrator:         Tampilkan
 Svc   │                            progress
       ▼
   DiscoveryEngine.discover()
       │ → Engineering Brief
       ▼
   PlanningEngine.plan()
       │ → Engineering Plan
       ▼
   TaskGraphEngine.generate_graph()
       │ → Task DAG (nodes, edges, parallel groups, critical path)
       ▼
   DispatcherEngine.dispatch()  ←── REAL worker execution
       │ → Per node: instantiate worker from WORKER_REGISTRY
       │ → worker.execute() with context, handoffs, workspace
       │ → Results flow to next nodes via handoff chain
       ▼
   VerificationEngine.verify()
       │ → Requirements check, quality scoring, regression
       ▼
   DeliveryEngine.deliver()
       │ → Report, lessons learned, deployment
       ▼
   Event Bus (backbone connecting all)
       → WebSocket → Frontend (real-time updates)
       → Audit trail → Evidence Center
```

**Prinsip:**
1. Runtime Executor's worker execution logic (handoffs, repair loops, completion integrity) **dimigrasikan ke Dispatcher**
2. Task Graph mendorong eksekusi nyata, bukan simulasi
3. Event Bus menjadi backbone — setiap engine publish dan subscribe
4. Frontend mendengarkan WebSocket untuk real-time pipeline visualization

---

## 7. Roadmap — Phased Evolution Plan

### Phase 1: Foundation Fixes (Priority: CRITICAL)
**Goal:** Perbaiki bugs kritis dan hubungkan yang sudah terputus

#### Backend
- [ ] **Fix routing bug:** Hubungkan `OrchestrationView`, `WorkflowsView`, `JobsView`, dll ke route yang benar di `App.tsx`
- [ ] **Unify intent detection:** Extract regex patterns ke single shared module
- [ ] **Fix duplicate LLM call** di `core.py:853-900`
- [ ] **Fix progress map** phase names di `workflow/engine.py`
- [ ] **Fix PM review gate** — ganti "documentation" dengan "closeout"
- [ ] **Split `core.py`** menjadi 5 separate route files
- [ ] **Pass `useWorkspace` data ke child components** — dashboard, projects, timeline
- [ ] **Wire `AppShell` props** dari `useBoot` state

#### Frontend
- [ ] **Wire dashboard data:** Connect `useWorkspace` overview/workers/projects/tasks ke `WorkspaceView`
- [ ] **Fix 7 unreachable views:** Route orchestration, workflows, jobs, mcp, memory, rag, automation ke komponen yang benar
- [ ] **Rename "Chat" → "Command Center"** di nav, menu, dan label
- [ ] **Wire `AppShell` footer** dengan real health status dan model label

### Phase 2: Connect the Pipeline (Priority: HIGH)
**Goal:** Setelah intent=task_request terdeteksi, pipeline Discovery → Planning → TaskGraph → Dispatcher harus chain otomatis

#### Backend
- [ ] **Build Master Orchestrator** — service yang chain engines setelah ConversationEngine route ke task pipeline
- [ ] **Unify ConversationEngine intake** — delegasikan ke DiscoveryEngine (bukan simplified pipeline sendiri)
- [ ] **Auto-trigger Planning** setelah Discovery menghasilkan Brief
- [ ] **Auto-trigger TaskGraph** setelah Planning menghasilkan Plan
- [ ] **Auto-trigger Dispatcher** setelah TaskGraph menghasilkan Graph
- [ ] **Replace Dispatcher simulation** dengan real worker execution (extract dari runtime/executor.py)
- [ ] **Connect EventBus** sebagai backbone — setiap engine publish events
- [ ] **Wire WebSocket** untuk broadcast pipeline events ke frontend
- [ ] **Unify intent detection** — satu shared module, hapus triplicate regex

#### Frontend
- [ ] **Pipeline Visualization** — tampilkan progress Discovery→Plan→Build→Verify→Deliver
- [ ] **Approval Queue component** — floating notification untuk approval gates
- [ ] **Mission Detail View** — show pipeline progress, worker assignments, handoffs

### Phase 3: Activate the Workforce (Priority: HIGH)
**Goal:** Buat workers benar-benar bekerja, bukan hanya chat completion

#### Backend
- [ ] **Connect orchestrator ke `WORKER_REGISTRY`:** Instantiate worker classes dan panggil `execute()`
- [ ] **Enforce ToolPermissions:** Add checker yang validasi worker tool calls terhadap registry
- [ ] **Implement Heartbeat:** Periodic scheduler untuk Hermes's `check_stale_tasks` dan `check_blocked_tasks`
- [ ] **Implement Autonomy Engine recovery:** Real retry, replan, dan escalate logic
- [ ] **Upgrade workers dengan real tools:** File read/write, code execution, test runner, shell access
- [ ] **Activate parallel execution** di multi-worker phases

#### Frontend
- [ ] **Org Chart View** — Visualisasi 15 workers × 4 departemen
- [ ] **Worker Profile View** — Skills, current tasks, performance history, system prompt
- [ ] **Live worker activity** — Real-time feed via WebSocket (who is doing what)

### Phase 4: Engineering Manager Experience (Priority: MEDIUM)
**Goal:** Transformasi UX dari "chat app" menjadi "company management dashboard"

#### Frontend
- [ ] **Redesign Onboarding** — "First Day at the Company": intro workforce, show org chart, set first mission
- [ ] **Command Center redesign** — Reframe chat sebagai dispatch console (brief → assign → monitor)
- [ ] **Project Pipeline / Kanban Board** — Visual work flowing through stages
- [ ] **Performance Analytics** — Team velocity, completion rates, cost per mission
- [ ] **Resource Allocation** — Assign workers ke projects, balance workload
- [ ] **Notification Center** — Bell icon, pending approvals, worker alerts, blockers
- [ ] **Command Palette UI** — Visible Cmd+K palette
- [ ] **Global Search** — Search across workers, missions, projects

#### Backend
- [ ] **Dashboard API** — Aggregated stats: active missions, worker utilization, pipeline health
- [ ] **Project-level orchestration** — Cross-task dependencies, team assignment, sprint planning
- [ ] **Cost tracking** — Per-mission LLM token usage dan cost
- [ ] **Notification system** — Event-driven alerts for approvals, blockers, completions

### Phase 5: Quality & Delivery (Priority: MEDIUM)
**Goal:** Verification dan Delivery yang meaningful

#### Backend
- [ ] **Real Verification** — Requirements traceability, actual code analysis, test execution
- [ ] **Meaningful Quality Scores** — Based on actual metrics, bukan hardcoded values
- [ ] **Real Delivery** — Git commit, artifact packaging, deployment
- [ ] **Upgrade Context Engine** — Semantic search, inter-worker context propagation
- [ ] **Connect VerificationEngine ke FSM lifecycle**

### Phase 6: Polish & Scale (Priority: LOW)
**Goal:** Production hardening dan UX polish

- [ ] **Unify API clients** — Merge `apiClient` dan `runtimeClient`
- [ ] **API versioning** — `/v1/`, `/v2/` prefix scheme
- [ ] **Pagination** — Untuk conversations, messages, events
- [ ] **Replace deprecated `@app.on_event("startup")`** dengan lifespan context manager
- [ ] **Light theme support** (optional)
- [ ] **Add missing design primitives** — Table, Modal, Dropdown, Tooltip, Tabs, EmptyState, Skeleton

---

## 8. Architecture Decision Records (Proposed)

### ADR-001: Master Orchestrator Pattern
**Decision:** Build a single `MasterOrchestrator` service that chains Discovery → Planning → TaskGraph → Dispatcher → Verification → Delivery, triggered automatically when ConversationEngine detects `task_request` intent.
**Rationale:** Chat adalah unified entry point. Intent detection sudah ada dan berfungsi. Yang kurang adalah pipeline otomatis SETELAH intent terdeteksi — saat ini setiap engine harus di-trigger manual oleh user. Master Orchestrator menghubungkan semua engine sehingga user cukup memberikan brief sekali, dan organisasi AI yang mengerjakan sisanya.
**Alternatives considered:**
- Event-driven chain only: Too fragile, hard to debug
- Keep separate: Current state, setiap sambungan terputus

### ADR-002: Worker Execution via Registry
**Decision:** All worker execution MUST go through `WORKER_REGISTRY` → `worker.execute()` with context assembly.
**Rationale:** The agent registry defines rich worker identities, tool permissions, and model policies. Bypassing it for raw chat completion loses all this context.
**Migration:** Extract runtime/executor.py's worker execution logic into a shared `WorkerExecutor` class used by both the FSM executor and the Dispatcher.

### ADR-003: Event Bus as Backbone
**Decision:** All engine state transitions publish to `EventBus`. Frontend subscribes via WebSocket.
**Rationale:** Currently engines communicate via direct DB writes or not at all. The EventBus provides decoupled, observable, real-time communication.

### ADR-004: Command Center = Chat with Intent Routing
**Decision:** Chat (Command Center) adalah unified entry point untuk semua interaksi. Intent detection menentukan routing: percakapan biasa tetap di chat, task request masuk ke pipeline perusahaan, approval melanjutkan phase, status menampilkan progress.
**Rationale:** Engineering Manager berkomunikasi via Command Center — ini natural dan intuitif. Sistem yang cerdas mendeteksi intent dan merutekan secara otomatis. Yang perlu diubah bukan menghapus chat, tapi: (1) memframing ulang sebagai "Command Center" bukan "chat", (2) memastikan intent routing terhubung ke pipeline yang benar, (3) output pipeline (brief, plan, progress, report) ditampilkan sebagai structured response di Command Center, bukan sebagai bubble chat biasa.

### ADR-005: Single Source of Truth for Worker Identity
**Decision:** `AGENT_REGISTRY` in `agents/registry.py` is the single source of truth for worker identity, capabilities, and constraints. Worker classes in `workers/base.py` reference the registry, not hardcoded prompts.
**Rationale:** Currently two conflicting definitions exist. The registry is richer and more aligned with the vision.

---

## 9. Metrics for Success

| Metric | Current | Target (Phase 3) |
|--------|---------|-----------------|
| Pipeline completion (Discovery→Delivery) | 0% (broken chain) | 80% automated |
| Worker execution via registry | 0% (chat completion) | 100% |
| Dashboard data populated | 0% (empty arrays) | 100% |
| Reachable views | 5 of 12 | 12 of 12 |
| EventBus utilization | 5% (recorder only) | 100% of state transitions |
| Parallel worker execution | No | Yes (per phase) |
| Real verification (code + tests) | TestingWorker only | All verification paths |

---

## 10. Effort Estimation

| Phase | Estimated Effort | Dependencies |
|-------|-----------------|-------------|
| Phase 1: Foundation Fixes | 2-3 days | None |
| Phase 2: Connect Pipeline | 3-5 days | Phase 1 |
| Phase 3: Activate Workforce | 4-6 days | Phase 2 |
| Phase 4: EM Experience | 5-7 days | Phase 1, 3 |
| Phase 5: Quality & Delivery | 3-4 days | Phase 2, 3 |
| Phase 6: Polish & Scale | 2-3 days | All phases |
| **Total** | **19-28 days** | |

---

## Appendix: File Reference

### Critical Files (Backend)
| File | Lines | Role |
|------|-------|------|
| `backend/main.py` | 195 | App bootstrap, 19 routers |
| `backend/api/routes/core.py` | 1010 | Mega-route: providers, conversations, chat, workers |
| `agents/registry.py` | 582 | 15 agents with departments and souls |
| `agents/context_assembly.py` | 130 | Runtime system prompt assembly |
| `workflow/fsm.py` | 273 | Task lifecycle FSM with barriers |
| `workflow/engine.py` | 244 | Workflow state management |
| `workflow/triage.py` | ~200 | Smart task triage (L1-L4) |
| `discovery/engine.py` | 447 | Engineering intake pipeline |
| `planning/engine.py` | 289 | Engineering plan generation |
| `taskgraph/engine.py` | ~200 | Task DAG generation |
| `dispatcher/engine.py` | ~200 | Task dispatch (simulated) |
| `runtime/executor.py` | ~700 | **The actual orchestrator** |
| `workers/base.py` | 666 | 15+ worker classes |
| `llm/provider.py` | 543 | LLM abstraction with tiers |
| `autonomy/engine.py` | 213 | Self-healing (stub) |
| `verification/engine.py` | ~200 | Quality verification |
| `delivery/engine.py` | ~150 | Report generation |
| `events/bus.py` | 101 | Async pub/sub |

### Critical Files (Frontend)
| File | Lines | Role |
|------|-------|------|
| `src/renderer/src/App.tsx` | ~150 | App shell + view routing (BUG HERE) |
| `src/renderer/src/components/AppShell.tsx` | 217 | Layout: header, sidebar, footer |
| `src/renderer/src/components/WorkspaceView.tsx` | 230 | Dashboard (EMPTY) |
| `src/renderer/src/components/ChatView.tsx` | 440 | Chat interface (ChatGPT clone) |
| `src/renderer/src/components/LiveCompanyView.tsx` | 328 | Worker monitoring (best aligned) |
| `src/renderer/src/components/ProjectsView.tsx` | 144 | Project list (EMPTY) |
| `src/renderer/src/components/SettingsView.tsx` | 444 | Settings mega-container |
| `src/renderer/src/components/OrchestrationView.tsx` | 309 | Multi-agent sessions (UNREACHABLE) |
| `src/renderer/src/hooks/useBoot.ts` | 300 | Boot sequence + auth + WS |
| `src/renderer/src/hooks/useWorkspace.ts` | 480 | Project/file/worker state |
| `src/main/main.ts` | 842 | Electron main + sidecar |

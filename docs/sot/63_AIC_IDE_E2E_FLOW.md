# AIC-IDE: Cara Kerja & End-to-End Flow

## Apa itu AIC-IDE?

AIC-IDE adalah desktop application (Electron) yang menjadi **command center** untuk mengelola AI Engineering Company. Bukan chatbot. Bukan code editor. Ini adalah **dashboard Engineering Manager** yang mengelola 15 AI workers yang berkolaborasi menghasilkan software.

---

## Arsitektur

```
┌─────────────────────────────────────────────────┐
│  AIC-IDE (Electron Desktop App)                 │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  React 19 Renderer (Vite 6 + Tailwind)  │    │
│  │                                          │    │
│  │  ┌──────┐ ┌──────────────────────────┐  │    │
│  │  │Sidebar│ │  Main Content Area       │  │    │
│  │  │       │ │                          │  │    │
│  │  │Office │ │  Command Center / Office │  │    │
│  │  │Cmd Ctr│ │  Live Company / Skills   │  │    │
│  │  │Live Co│ │  MCP / Settings          │  │    │
│  │  │Skills │ │                          │  │    │
│  │  │MCP    │ │                          │  │    │
│  │  │Settings│ │                          │  │    │
│  │  └──────┘ └──────────────────────────┘  │    │
│  └─────────────────────────────────────────┘    │
│                    │ HTTP/SSE/WebSocket           │
│  ┌─────────────────┴───────────────────────┐    │
│  │  Electron Main Process                   │    │
│  │  - Sidecar Manager (Python backend)      │    │
│  │  - PTY Terminal                          │    │
│  │  - File System IPC                       │    │
│  │  - Auto Updater                          │    │
│  └─────────────────┬───────────────────────┘    │
└────────────────────┼────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│  AIC Platform (Python FastAPI Backend)           │
│  - 23 API routers                                │
│  - 69 database tables                            │
│  - 15 AI workers                                 │
│  - Master Orchestrator (pipeline engine)         │
│  - Tool Executor (9 real tools)                  │
│  - Intent Detection (EN + ID)                    │
│  - Context Pipeline                              │
│  - Permission System                             │
│  - Skill Engine                                  │
│  - MCP Protocol Client                           │
└──────────────────────────────────────────────────┘
```

---

## End-to-End Flow: Solo Developer Membuat Aplikasi

### Scenario: "Bangun sistem auth untuk aplikasi saya"

**Step 1: Developer membuka AIC-IDE**
- App launch → Electron spawns Python backend sebagai sidecar
- Health check polling sampai backend ready
- Developer melihat **Office Floor** (dashboard) — 15 worker desks, meeting room, stats

**Step 2: Developer buka Command Center**
- Klik "Command Center" di sidebar (atau Ctrl+2)
- Developer mengetik: `Bangun sistem autentikasi untuk aplikasi saya dengan JWT dan refresh token`

**Step 3: Intent Detection**
```
classify_intent("Bangun sistem autentikasi...")
→ TASK_VERB_PATTERN match: "bangun"
→ Result: "task_request"
```

**Step 4: ConversationEngine memproses**
- `_handle_task_request()` dipanggil
- `_evaluate_intake_completeness()` check:
  - `business_goal`: ✅ match ("sistem", "aplikasi")
  - `core_features`: ✅ match ("autentikasi", "JWT")
  - `target_user`: ❌ missing
- Missing <= 1 → **is_complete = True**
- Task dibuat, `_launch_pipeline()` dijalankan sebagai background task

**Step 5: Master Orchestrator chain pipeline**

```
Stage 1: Discovery Engine
  → Intent: task_request
  → Domain: backend (auth pattern)
  → Requirements extracted: JWT auth, refresh token
  → Engineering Brief created → brief_id

Stage 2: Planning Engine
  → Brief analyzed
  → Architecture decisions: JWT + bcrypt + middleware
  → Risk assessment: token expiry, secret management
  → Effort estimate: medium complexity
  → Engineering Plan created → plan_id

Stage 3: Task Graph Engine
  → Plan decomposed into tasks:
    1. Create user model (database)
    2. Implement auth endpoints (backend)
    3. Add JWT middleware (backend)
    4. Write tests (qa)
  → Dependencies mapped
  → Execution order determined
  → Task Graph created → graph_id

Stage 4: Dispatch Engine
  → Per task node:
    - Create child Task
    - Call execute_task() via runtime/executor.py
    - Worker executes with real tools (read_file, write_file, shell)
    - Results collected
  → All tasks completed
```

**Step 6: Worker Execution (real tools)**
```
BackendWorker (Hugo) executing task:
  1. read_file("src/models/user.py") → reads existing code
  2. write_file("src/auth/jwt_utils.py", "...") → creates JWT utility
  3. write_file("src/auth/routes.py", "...") → creates auth endpoints
  4. shell("pytest tests/test_auth.py") → runs tests
  5. read_file("tests/test_auth.py") → verifies test output
```

**Step 7: Command Center menampilkan progress**
- Tool panels muncul inline (always visible):
  - `📄 read src/models/user.py` — content preview
  - `✏️ wrote src/auth/jwt_utils.py` — file created
  - `🔧 $ pytest tests/test_auth.py` — shell output
- Status bar: `build agent · Hugo · 1,234 tokens · $0.03`

**Step 8: Pipeline selesai**
- Verification: QA worker runs tests, checks code quality
- Delivery: Report generated, lessons learned recorded
- Task marked as completed
- Dashboard Office Floor menunjukkan Hugo kembali ke desk-nya

---

## Apakah Ini Memudahkan Solo Developer?

**Ya, dengan catatan:**

### Yang Sudah Memudahkan:
1. **Natural language input** — Developer tidak perlu tahu syntax atau API. Cukup jelaskan dalam bahasa Indonesia/Inggris.
2. **Otomatisasi pipeline** — Dari brief sampai delivery, semuanya otomatis. Developer tidak perlu koordinasi manual.
3. **Worker spesialisasi** — Setiap fase punya worker yang tepat (Architect untuk planning, Backend untuk coding, QA untuk testing).
4. **Tool execution nyata** — Workers benar-benar baca/tulis file, jalankan command. Bukan generate text.
5. **Transparansi** — Developer bisa lihat setiap tool call, setiap keputusan, setiap hasil.

### Yang Masih Perlu Improvement:
1. **Intent detection** — Untuk input kompleks, regex-based intent detection mungkin tidak akurat 100%. Perlu LLM-based fallback.
2. **Pipeline reliability** — Pipeline chain sudah terhubung, tapi belum ada error recovery otomatis jika salah satu stage gagal.
3. **Cost visibility** — Token/cost sudah di-track, tapi belum tampil per-message di Command Center.

---

## Apakah Runtime Berubah dari Visi?

**Tidak. Visi tetap:**

| Visi | Implementasi |
|------|-------------|
| User = Engineering Manager | ✅ Dashboard + Command Center |
| 15 AI workers berkolaborasi | ✅ 15 workers dengan spesialisasi |
| Research → Plan → Build → Verify → Deliver | ✅ 6-stage pipeline (Discovery → Planning → TaskGraph → Dispatch → Verify → Deliver) |
| Command Center (bukan chat) | ✅ Intent-based routing, tool panels |
| Transparency & Control | ✅ Tool visibility, approval system |
| Local-first | ✅ SQLite, localhost-only |
| BYOK | ✅ Multi-provider support |

**Yang ditambah (bukan mengubah visi, tapi mewujudkannya):**
- Workers benar-benar execute tools (bukan cuma generate text)
- Permission system (setiap worker punya batasan)
- Context management (workers tahu apa yang terjadi sebelumnya)
- Multi-project support
- File tree, terminal, keyboard shortcuts
- Auto-update system

---

## Target Bahasa

**English + Indonesian only.** Tidak ada rencana support bahasa lain. Intent detection sudah support kedua bahasa:
- English: "Build auth system" → task_request
- Indonesian: "Bangun sistem auth" → task_request
- Indonesian: "Buatkan API untuk user" → task_request
- Indonesian: "Perbaiki bug di login" → task_request

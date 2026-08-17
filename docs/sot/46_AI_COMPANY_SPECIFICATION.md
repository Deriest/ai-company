# 46 — AI Company Specification

**Release Scope:** v2.3.0
**Status:** Source of Truth

---

## What is the AI Company?

AIC-ADE adalah **AI Engineering Company** — sebuah organisasi engineering otonom dimana user berperan sebagai **Engineering Manager** yang mengelola tim AI workers yang berkolaborasi melalui structured engineering workflows.

Bukan chatbot. Bukan AI IDE. Bukan coding assistant.

Ketika user membuka AIC, persepsinya harus:
> "Saya sedang menjalankan perusahaan software engineering yang seluruh karyawannya adalah AI."

---

## 1. Worker Registry (15 Canonical Workers)

| Worker | Nama | Department | Tier | Phase |
|--------|------|-----------|------|-------|
| **Hermes** | Hermes | Leadership | Thinker | All (Dispatcher) |
| **Rex** | Rex | Leadership | Sprinter | Closeout (Governor) |
| **PM** | Aria | Product | Thinker | Discovery–Closeout |
| **Researcher** | Sage | Product | Thinker | Investigate |
| **Designer** | Luna | Product | Thinker | Planning |
| **Documentation** | Echo | Product | Crafter | Closeout |
| **Architect** | Atlas | Engineering | Thinker | Planning |
| **Backend Engineer** | Hugo | Engineering | Crafter | Implementation |
| **Frontend Engineer** | Leo | Engineering | Crafter | Implementation |
| **QA Engineer** | Eve | Engineering | Crafter | Verification |
| **Performance** | Pulse | Engineering | Crafter | Verification |
| **Database Engineer** | Nova | Platform | Crafter | Planning–Implementation |
| **Integration** | Nexus | Platform | Crafter | Planning |
| **Infrastructure** | Flint | Platform | Crafter | Planning |
| **Security** | Sentinel | Platform | Thinker | Planning |

---

## 2. Department Structure

```
┌─────────────────────────────────────────────┐
│              LEADERSHIP                      │
│  [Hermes] Dispatcher    [Rex] Governor       │
├─────────────────────────────────────────────┤
│              PRODUCT                         │
│  [Aria] PM  [Sage] Research  [Luna] Design  │
│  [Echo] Documentation                       │
├─────────────────────────────────────────────┤
│              ENGINEERING                     │
│  [Atlas] Architect  [Hugo] Backend          │
│  [Leo] Frontend  [Eve] QA  [Pulse] Perf     │
├─────────────────────────────────────────────┤
│              PLATFORM                        │
│  [Nova] Database  [Nexus] Integration       │
│  [Flint] Infra  [Sentinel] Security         │
└─────────────────────────────────────────────┘
```

---

## 3. Worker Execution Model

```
1. Assignment    — Dispatcher assigns worker based on FSM phase
2. Context       — Assemble: agent soul + task context + skills + handoffs + adaptive policy
3. Tool Setup    — Resolve allowed tools from ToolPermissions
4. Execution     — LLM call with tool definitions → tool-use loop (max N rounds)
5. Real Tools    — read_file, write_file, shell, explore, search (via ToolExecutor)
6. Lease         — Worker holds active Lease during execution
7. Evidence      — Files, test results, reports in task workspace
8. Handoff       — Output stored for next worker in pipeline
```

---

## 4. Truthful Worker Rule

Worker status HARUS mencerminkan state runtime yang sebenarnya:
- `"online"` — Worker terdaftar, tidak ada active task
- `"working"` — Active lease exists di database, ada tool execution
- `"idle"` — Worker tidak aktif
- **DILARANG** menampilkan worker sebagai "working" tanpa active Lease record

---

## 5. Command Center (Unified Entry Point)

Chat adalah **Command Center** — bukan chat biasa. Intent detection menentukan routing:

```
User mengetik di Command Center
         │
    classify_intent()
         │
    ┌────┼────────────┬──────────────┐
    │    │            │              │
  chat  task_request  approval     status
    │    │            │              │
    ▼    ▼            ▼              ▼
  Chat  Master       Resume FSM    Show
  Resp  Orchestrator  phase        progress
        (auto-chain
         pipeline)
```

---

## 6. Tool Execution System

Workers menggunakan `ToolExecutor` untuk operasi nyata:

| Tool | Fungsi | Scope |
|------|--------|-------|
| `read_file` | Baca file dari project | Semua worker |
| `write_file` | Tulis file ke project | backend, frontend, coding, database |
| `shell` | Jalankan command | backend, frontend, coding, devops |
| `explore` | List directory tree | Semua worker |
| `search` | Cari content dalam files | Semua worker |

**Tool-use loop:**
1. Worker build prompt + tool definitions
2. Call LLM
3. If LLM returns tool_calls → execute via ToolExecutor → feed results back → goto 2
4. If LLM returns text → final response
5. Max 10 rounds

---

## 7. Permission System

Setiap worker punya `ToolPermissions` (defined di `agents/registry.py`):

| Category | Meaning |
|----------|---------|
| `allowed` | Tool boleh dipakai |
| `restricted` | Perlu user approval |
| `prohibited` | Dilarang total |

**Enforcement:** `check_tool_permission(worker_type, tool_name)` dipanggil sebelum setiap tool execution.

---

## 8. Skill Engine

Skills adalah instruction snippets yang di-inject ke worker context:

- 6 built-in skills: API Audit, Systematic Debugging, TDD, Simplify Code, Security Audit, Server Health
- Custom skills: user bisa create via Skills UI
- Assignment: per worker type
- Injection: via `agents/context_assembly.py` → system prompt

---

## 9. MCP Integration

Model Context Protocol — koneksi ke external tool servers:

- Register server (stdio/HTTP/SSE)
- Discover tools via JSON-RPC
- Execute tools remotely
- Approval workflow untuk sensitive tools
- Fallback ke local tool_dispatcher jika server tidak connected

---

## 10. Department Layout (Live Company View)

| Section | Content |
|---------|---------|
| Token Cost Summary | Total cost, tokens used, LLM requests (30d) |
| Department Grid | 4 departments (Leadership, Product, Engineering, Platform) |
| Worker Cards | 15 cards dengan real-time status, tier badge, task count |
| Worker Detail | Click card → detail panel: identity, runtime, metrics, pipeline role |
| Office Floor | 2D animated visualization (Workspace view) |

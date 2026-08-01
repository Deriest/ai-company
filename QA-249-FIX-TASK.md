# AIC-ADE 2.4.9 — FULL CHECK: Bug List + OpenCode Prompt

**Date:** 2026-08-01  
**Build:** AIC-ADE-2.4.9-linux-x86_64.AppImage (180,797,295 bytes)  
**Provider test:** kr/claude-sonnet-4.5 via VansRouter (http://127.0.0.1:20129/v1)  
**Scope:** Full check semua halaman, action, API, chat, palette, update, persistensi

---

# BUG LIST (7)

## 🔴 CRITICAL (3)

### BUG-01: Task Pipeline Gagal — "No LLM provider configured"
- **Gejala:** `/chat/execute` dengan task_request ("Build a React todo app...") → intent=task_request → executing → **"No LLM provider configured"**
- **Root cause:** `backend/backend/services/agent_runner.py` line 83-85 → `provider_manager.get_active()`. Global manager HANYA diisi dari env var `AIC_LLM_BASE_URL` (main.py:33-36). Provider dari UI (tabel `providers`) TIDAK pernah di-register → manager kosong.
- **Repro:**
  ```bash
  curl -s -N -X POST http://127.0.0.1:8000/chat/execute -H "Content-Type: application/json" \
    -d '{"conversation_id":"<cid>","messages":[{"role":"user","content":"Build a todo app"}],"worker_role":"thinker"}'
  ```

### BUG-02: `/chat` Non-Streaming Masih 500 — SSE fix tidak menyeluruh
- **Gejala:** `POST /chat` → 500 `"Expecting value: line 1 column 1 (char 0)"`
- **Root cause:** `backend/backend/services/chat_service.py` `chat_completion()` (line 248-250) pakai `httpx.AsyncClient().post()` + `res.json()` LANGSUNG — TIDAK lewat `llm/provider.py` yang sudah di-fix SSE parsing. Ada 2 jalur HTTP ke LLM, cuma 1 yang di-fix.

### BUG-03: Plan Mode Gagal — pakai model default `gpt-4o-mini` (tidak ada di VansRouter) → 404
- **Gejala:** Plan mode aktif (toggle plan, placeholder "describe what to analyze...", footer "plan agent") → kirim "Plan a weather app architecture" → **Error: LLM request failed: 404 Not Found**
- **Bukti log:** `LLM HTTP error (attempt 1): 404 for gpt-4o-mini at http://127.0.0.1:20129/v1: {"error":{"message":"No active credentials for provider: openai","type":"invalid_request_error","code":"model_not_found"}}`
- **Root cause:** Model resolution tidak konsisten — plan mode/chat_stream pakai default `gpt-4o-mini` (dari `settings.AIC_MODEL_CRAFTER or ... or "gpt-4o"`), bukan model yang dikonfigurasi user (`kr/claude-sonnet-4.5` di worker_runtime)

## 🟠 HIGH (2)

### BUG-04: Frontend Bundle STALE — fix sidebar tidak masuk build
- **Source repo SUDAH benar:** `app/src/renderer/src/components/AppShell.tsx` line 26-32 → Office, CC, Live, Skills, MCP, **Observability**, Settings (TIDAK ada Operations)
- **TAPI AppImage bundle (`dist/assets/index-BwLL7YBP.js`) MASIH LAMA:**
  - Sidebar masih "**Operations**" (collapsed)
  - **Observability TIDAK ada di sidebar** (hilang total!)
  - Command Palette masih bocor internal: Go to Orchestration/Workflows/Jobs/Memory/RAG/Automation/Observability
- **Impact:** BUG-02 dari 2.4.8 masih ada di build + Observability malah hilang dari nav

### BUG-05: Token Budget HANYA di AgentRunner — chat biasa (ConversationEngine) tidak kena
- **Gejala:** Conversation 160k tokens → `/chat/execute` non-task → **response kosong** (cost $0.13–$0.22 ter-charge tiap attempt, tanpa truncation)
- **Root cause:** `ConversationEngine` (jalur chat non-task) TIDAK pakai `context_builder` (grep 0 hit). Token-budget trimming cuma ada di `context_builder.to_messages()` yang hanya dipakai AgentRunner (yang malah broken oleh BUG-01)
- **Impact:** Chat biasa tetap kirim history penuh tanpa budget guard → VansRouter "input context length exceed"

## ⚪ LOW (2)

### BUG-06: Tombol Office "New MissionOpen Command Center" — teks menempel
- `textContent` = `"New MissionOpen Command Center"` tanpa spasi (bundle lama)

### BUG-07: Session Search kosong saat filter (minor)
- Ketik "Clean" di search session → hasil kosong meski ada session "Clean Test" (perlu verifikasi logika filter)

---

# ✅ Diverifikasi Berfungsi (2.4.9)

- Onboarding, provider setup, test connection (22ms, 36 models)
- Simple chat (conversation bersih) + claude-sonnet-4.5 → "Hey"
- Message persist + created_at + survive reload
- Name save + sidebar refresh langsung
- MCP register server (tersimpan di mcp_registry)
- Live Company: 15 worker cards, detail panel
- Skills New Skill form, MCP Register form render
- Settings 6 tabs render, Updates (up_to_date)
- Internal pages render via palette: Orchestration, Workflows, Jobs, Memory (3 entries), RAG, Automation, Observability (tabs Overview/Context/Workers/Usage)
- API audit: 20+ endpoint 200
- 0 console errors di semua halaman

---

# PROMPT OPENCODE (copy ke opencode)

```markdown
# OpenCode Task: Fix 5 Bug AIC-ADE 2.4.9 (backend + frontend rebuild)

> Role: senior full-stack engineer (FastAPI + React). Repo: /home/tvd/AI-Company.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap fix harus: (1) diff source reviewable, (2) test/repro, (3) verifikasi runtime. Ikuti AGENTS.md.

## Konteks
AIC-ADE = Electron + React (app/) + FastAPI (backend/) + SQLite. Gateway LLM = VansRouter di http://127.0.0.1:20129/v1 (OpenAI-compatible, SELALU balas SSE stream). Model uji: kr/claude-sonnet-4.5 (context 200k). AppImage 2.4.9: /home/tvd/AI-Company/app/release/AIC-ADE-2.4.9-linux-x86_64.AppImage

## Bug yang harus difix

### BUG-01 (CRITICAL): AgentRunner "No LLM provider configured"
File: backend/backend/services/agent_runner.py (line 83-85), backend/backend/main.py (line 33-36)
Fix: AgentRunner harus pakai provider dari DB (tabel providers) bukan hanya env var. Dua opsi:
  (a) register provider DB ke provider_manager saat app start, ATAU
  (b) build LLMProvider langsung dari config DB di AgentRunner
JANGAN hanya env var — provider user dari Settings/onboarding harus jalan.

### BUG-02 (CRITICAL): /chat non-streaming 500 (SSE mismatch)
File: backend/backend/services/chat_service.py chat_completion() (line ~248-250)
Fix: ganti httpx+res.json() manual dengan panggilan ke llm/provider.py provider.chat() yang SUDAH fix SSE parsing. Satu jalur LLM saja (single source of truth).

### BUG-03 (CRITICAL): Plan mode pakai gpt-4o-mini default → 404
File: backend/backend/services/chat_service.py chat_stream() (line ~403), alur resolve model di api/routes/chat.py
Fix: model resolution HARUS konsisten — pakai worker_runtime.model_id/provider_id yang dikonfigurasi user. Jangan fallback ke "gpt-4o"/"gpt-4o-mini" yang tidak ada di provider user. Kalau model tidak ditemukan → error jelas yang menyebut model, bukan 404 misterius.

### BUG-04 (HIGH): Frontend bundle STALE
File: app/src/renderer/src/components/AppShell.tsx (source sudah benar — Observability top-level, no Operations)
Fix: REBUILD frontend sebelum packaging AppImage! Pastikan dist/assets bundle baru berisi: sidebar tanpa Operations, Observability top-level, Command Palette tanpa item internal (Orchestration/Workflows/Jobs/Memory/RAG/Automation). Verifikasi: extract AppImage → grep bundle → tidak ada "Operations" di nav, ada Observability top-level.

### BUG-05 (HIGH): Token budget cuma di AgentRunner
File: backend/backend/services/context_builder.py (sudah ada trimming ✅), backend/services/conversation_engine.py (TIDAK pakai context_builder)
Fix: ConversationEngine (jalur chat non-task) harus pakai context_builder/token budget. History > policy.max_tokens harus di-truncate sebelum dikirim. Verifikasi: conversation 160k tokens → response berhasil ATAU error eksplisit "context exceeds budget", bukan kirim penuh lalu kosong.

## Acceptance Criteria (WAJIB semua)
1. Task request ("Build a todo app") + worker_role=thinker → chunks keluar, TIDAK "No LLM provider configured"
2. POST /chat non-streaming → 200, bukan 500
3. Plan mode + claude-sonnet-4.5 → jawab, bukan 404 gpt-4o-mini
4. AppImage bundle: sidebar TIDAK ada Operations, Observability ada di top-level, palette bersih
5. Conversation 160k → token budget aktif (truncated/dropped messages), tidak kirim penuh
6. No regresi: simple chat, message persist, settings, update check, internal pages
7. Unit test baru di backend/tests/ (provider DB registration, SSE parse, token truncation, model resolution)
8. cd backend && python -m pytest tests/ -x -q → hijau
9. JANGAN commit sampai semua bukti ada. Laporkan: diff + test output + curl proof.

## Cara run backend dev
cd backend && <python-linux>/bin/python -m uvicorn backend.main:app --port 8000
DB aktif: AIC_DATA_DIR (AppImage: ~/.config/aic-ade/aic-ade/)
Provider test: kr/claude-sonnet-4.5 @ http://127.0.0.1:20129/v1 (VansRouter, REQUIRE_API_KEY=false)
JANGAN ubah VansRouter — fix di sisi AIC-ADE.
```

---

*Screenshots: /tmp/aic249-qa-01..46.png*

# OpenCode Task: AIC-ADE 2.4.15 — Add MCP Memory Server + Anti-AI-Slop "Taste" System

> Role: Senior Backend/Fullstack Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap fitur WAJIB disertai: (1) diff source,
> (2) test/repro runtime, (3) verifikasi di app. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.15 lalu BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`),
> update latest.json. Pastikan `AIC-ADE-2.4.15-linux-x86_64.AppImage` ADA di `app/release/`.

## Konteks
- Stack: Electron+React (`app/`) + FastAPI+SQLite (`backend/`). Gateway VansRouter `http://127.0.0.1:20129/v1`.
- App sudah punya: MCP Servers (register/connect/discover tools, protocol HTTP/SSE/Stdio di `backend/backend/api/routes/mcp.py` + `backend/backend/services/mcp_service.py`), Skills registry (assignable ke worker, `backend/backend/api/routes/skills.py` + `backend/backend/skill_engine.py`), worker system (AGENT_REGISTRY + WORKER_REGISTRY, `backend/agents/registry.py`, `backend/workers/base.py`, `runtime/executor.py`), memory (`backend/backend/services/memory_engine.py`, `retrieve_project_memories`).
- `_llm_with_tools` di `backend/workers/base.py` SUDAH inject MCP tools (prefix `mcp_`) dari `mcp_service.get_all_mcp_tool_schemas` — jadi MCP server yang ke-register otomatis tools-nya masuk ke worker.
- Fix round 1-3 sudah ada (BUG-01..14). JANGAN regresi.

# BUG LIST (round 4)

## BUG-15 (HIGH): Provider dari UI tidak ke-register ke provider_manager sampai restart
- Gejala: profile baru, tambah provider via onboarding/UI (POST /providers), `/health` tetap `llm_configured: false`; `/chat/execute` (task/agent path) gagal `{"type":"error","stage":"agent_execution","error":"No LLM provider configured"}`. Yang JALAN cuma `/chat/stream` (engine path) karena BUG-14 fix baca provider langsung dari DB. Inkonsisten antar path.
- Root cause: `provider_manager` (`backend/llm/provider.py`) hanya di-seed dari DB saat startup (`backend/backend/main.py` lifespan). POST /providers (dan alur onboarding save) TIDAK memanggil `provider_manager.register/aregister` live → provider_manager.get_active() kosong untuk proses yang sudah berjalan.
- Fix: (a) saat provider di-save/test via `backend/backend/api/routes/providers.py` + `provider_manage.py`, panggil `provider_manager.aregister(...)`/`register(...)` (dan set_active kalau belum ada active); (b) ATAU buat resolver DB-direct yang dipakai konsisten oleh AgentRunner (`backend/backend/services/agent_runner.py`) + worker `_llm_or_fallback` (`backend/workers/base.py`) — jangan cuma chat_stream. Pilih SATU pola dan pastikan semua path pakai.
- Acceptance: setelah save provider via UI (tanpa restart), `/health` → `llm_configured: true`; `/chat/execute` task path berespons normal (bukan "No LLM provider configured").

# FITUR 1 — MCP Memory Server (@modelcontextprotocol/server-memory)

## Tujuan
Integrasi memory persistent berbasis knowledge graph dari MCP resmi `@modelcontextprotocol/server-memory`, dipakai workers untuk menyimpan & mengambil pengetahuan antar sesi/task.

## Requirements
1. **First-class MCP memory server option**: tambahkan preset "Memory (MCP)" di UI Register MCP Server (`app/src/renderer/`), protocol Stdio, command `npx -y @modelcontextprotocol/server-memory` (atau path binary lokal kalau npx lambat). Tersimpan di `mcp_registry` seperti server lain.
2. **Auto-start & connect**: saat server memory di-register, backend spawn process stdio MCP (via `mcp_pool`/`mcp_client` yang ada) dan connect — tools memory (create_entities, add_observations, search_nodes, open_nodes, read_graph) muncul di "Tools (all)" halaman MCP.
3. **Worker tool access**: pastikan tools `mcp_*` dari memory server masuk ke `_llm_with_tools` (sudah otomatis via mcp_service — verifikasi & fix kalau ada filter yang menghalangi).
4. **Memory-aware context**: di `runtime/executor.py` (dan/atau `backend/memory_engine.py`), sebelum worker execute: query memory graph (search_nodes dengan keyword task title/description) → inject hasil sebagai `memories` di task_context (seperti `retrieve_project_memories` yang sudah ada, tapi tambah sumber MCP memory). Worker bisa baca histori keputusan antar task.
5. **Persist**: memory tersimpan di file memory graph server (default `memory.json` di cwd server) — pastikan path deterministik di data dir (`AIC_DATA_DIR/memory/memory.json`) biar tahan restart.
6. **UI**: tab MCP Servers menampilkan server memory + status connected + tools; Execution History mencatat panggilan memory tools.

## Acceptance (FITUR 1)
- Register server memory via UI → status connected → tools memory terlihat.
- Worker yang memakai tools memory bisa create_entities + search_nodes (test via /agent/run-sync dengan prompt "simpan knowledge X" lalu "cari knowledge X").
- Task kedua (conversation/session berbeda) bisa retrieve knowledge yang disimpan task pertama (persist lintas sesi).
- Restart app → memory graph masih ada (file di data dir).

# FITUR 2 — Anti-AI-Slop "Taste" System

## Tujuan
Output AIC-ADE (chat, dokumentasi, deliverable, release notes) tidak berbunyi AI-slop — alami, spesifik, berani, ada voice. Ini sistem 3 lapis.

## Lapis 1 — Skill "taste" di Skill Registry
Buat skill baru `taste` di `backend/agents/registry.py` + seed skill (ikuti pola skill existing, lihat `backend/backend/api/routes/skills.py` + skill seed data). Isi SKILL.md: aturan anti-slop ringkas (diadaptasi dari pola berikut):
- JANGAN pakai: delve, crucial, pivotal, comprehensive, testament, underscore, vibrant, seamless, groundbreaking, "It's important to note", "I'd be happy to", "Let's dive in", "Here's what you need to know", "In conclusion", "The future looks bright", "at the end of the day", "when it comes to", "moving forward", "circle back", "game-changer", "In today's fast-paced world"
- JANGAN: em-dash berlebihan, rule-of-three paksaan, sinonim ganti-ganti (elegant variation), "-ing" superficial ("highlighting...", "underscoring..."), heading Title Case, emoji di heading, kutipan curly
- Hindari: "not only... but also", "It's not just X; it's Y", kalimat iklan ("no guessing", "it just works"), pertanyaan retoris yang langsung dijawab, penutup mic-drop
- WAJIB: kalimat bervariasi, spesifik (angka/nama/konteks), opini jelas, kata sederhana ("is"/"has" daripada "serves as"), aktif voice
- Assign skill ke worker penulis: `documentation` (Echo), `rex`, `pm`, `qa`, `coding` (komentar kode), `research` (laporan).
- Verifikasi: skill muncul di Skill Registry + assign ke worker; worker documentation memakai skill saat menulis deliverable.

## Lapis 2 — System prompt guardrail
Tambah blok "WRITING STANDARD (anti-slop)" ringkas ke SYSTEM_PROMPT worker penulis di `backend/agents/registry.py` (documentation, pm, rex, research, qa) dan ke system prompt chat engine (Hermes) di `backend/conversation/engine.py` SYSTEM_PROMPT. Isi: 5-8 aturan inti anti-slop + "boleh berbunyi seperti manusia yang paham, bukan LLM yang sopan".

## Lapis 3 — Taste checker (quality gate)
Buat `backend/backend/services/taste_checker.py` (pure Python, regex + heuristik):
- Wordlist AI-ism (dari Lapis 1) + heuristik: em-dash density, "not only", "-ing" tail, boldface overuse, "In conclusion", dsb.
- Fungsi `scan_text(text) -> list[Finding]` (finding: pattern, count, contoh).
- Integrasi di `runtime/executor.py`: saat phase closeout/verification, scan deliverable text (output worker documentation/pm/rex) → findings masuk ke result (bukan auto-fail, tapi dilaporkan; qa worker juga bisa pakai).
- Integrasi di chat: response Hermes/engine lewat `taste_checker` ringan — kalau ketemu AI-ism, satu pass rewrite (LLM dengan instruksi "rewrite to remove AI patterns, keep meaning") ATAU minimal flagged.
- Unit test: `backend/tests/test_taste_checker.py` — text AI-slop sample → findings > 0; text bersih → findings == 0.

## Acceptance (FITUR 2)
- Skill `taste` muncul + assignable di UI Skills.
- Worker documentation menghasilkan deliverable yang lolos taste_checker (atau findings dilaporkan).
- Chat app tidak lagi berbunyi "I'd be happy to help!" / "Great question!" / "Let me know if..." — jawaban langsung, spesifik, manusiawi.
- `python -m pytest backend/tests/test_taste_checker.py` hijau.

# Acceptance Criteria GLOBAL (sebelum build 2.4.15)
1. BUG-15: provider save via UI → llm_configured true tanpa restart; /chat/execute task path normal.
2. Fitur 1: memory server register/connect/tools/memory-aware context/persist — semua terverifikasi runtime.
3. Fitur 2: skill taste + guardrail + taste_checker — semua terverifikasi.
4. Tidak ada regresi BUG-01..14 (pipeline launch, worker spawn, chat persist, version, dsb).
5. pytest hijau ATAU laporkan command + hasil (22 pre-existing failure schema — jangan tambah baru).
6. Build 2.4.15 + latest.json update.
7. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB bukti.

## Catatan
- `@modelcontextprotocol/server-memory` = server stdio resmi MCP. Kalau `npx` lambat di packaged env, bundle binary-nya ke `resources/` (ikut pola python-linux).
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya.
- Port backend bisa 8000/8001/8002 — pakai port sesuai startup log.

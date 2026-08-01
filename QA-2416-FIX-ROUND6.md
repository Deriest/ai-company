# OpenCode Task: AIC-ADE 2.4.16 → 2.4.17 — Fix BUG-17 (MCP tools di AgentRunner) + Memory/Taste e2e

> Role: Senior Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro runtime, (3) verifikasi di app. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.17 + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json. Pastikan `AIC-ADE-2.4.17-linux-x86_64.AppImage` ADA di `app/release/`.

## Konteks
- Stack: Electron+React (`app/`) + FastAPI+SQLite (`backend/`). Gateway VansRouter `http://127.0.0.1:20129/v1`.
- Model stabil: `kr/qwen3-coder-next`, `kr/claude-sonnet-4.5`, `qd/qmodel_latest`, `WF/wf/*`. HINDARI combo/*, IAMHC/*, *free*, big-pickle.
- Fix round 1-5 sudah ada (BUG-01..16 + MCP Memory + Taste). JANGAN regresi.
- QA 2.4.16 menemukan BUG-17 (kritis) + 2 verifikasi e2e yang belum tuntas.

# BUG-17 (CRITICAL): MCP tools (memory) tidak bisa dipanggil agent via /agent/run-sync (AgentRunner)
- Gejala: memory server registered + connected + 9 tools ter-expose di `/mcp/tools` (registry OK). TAPI `/agent/run-sync` dengan prompt "simpan ke memory pakai create_entities" → agent BALAS "I'll call the create_entities tool..." tapi `tool_results: []` — tool TIDAK pernah dipanggil. memory.json tetap `{"entities":[],"relations":[]}`.
- Root cause: `backend/backend/services/agent_runner.py` line 53: `tools = get_tools_for_worker(worker_type)` — dan `get_tools_for_worker` di `backend/backend/services/tool_executor.py` line 264-269 cuma return `AGENT_TOOLS` statis (filter by WORKER_PERMISSIONS). TIDAK merge MCP tools. Sementara jalur worker class (`backend/workers/base.py` line ~180) SUDAH inject `mcp_service.get_all_mcp_tool_schemas` — jadi pipeline worker punya mcp tools, AgentRunner TIDAK. `mcp_call` execution SUDAH ada di agent_runner.py line 104 (self.executor.mcp_call) — tinggal tool DEFINITION-nya yang ga masuk.
- Fix: di `agent_runner.py` (atau `get_tools_for_worker`), merge MCP tool schemas dari `mcp_service.get_all_mcp_tool_schemas(db)` (format `{"type":"function","function":{"name":"mcp_<toolName>","description":...,"parameters":...}}`) ke daftar tools. Pastikan pemanggilan `mcp_*` jalan ke `mcp_call`.
- Acceptance: `/agent/run-sync` prompt "Gunakan create_entities untuk simpan entity ProjectTech ..." → tool_results TIDAK kosong; file memory graph (`$AIC_DATA_DIR/memory/memory.json`) berisi entities; kemudian prompt "cari di memory" → agent pakai search_nodes dan jawab isi memory.

# VERIFIKASI E2E (setelah BUG-17 fix — WAJIB runtime, bukan cuma source)

## FITUR 1 — MCP Memory e2e lengkap
1. Register memory server (`POST /mcp/servers/register-memory`) → connected, 9 tools.
2. Simpan: `/agent/run-sync` "create_entities ProjectTech [FastAPI, SQLite]" → memory.json terisi (bukti file).
3. Ambil: task baru (conversation/session beda) "search_nodes project tech" → jawab FastAPI/SQLite dari memory.
4. Persist: restart backend → memory.json masih ada + search masih jalan.
5. Memory-aware context: task yang di-run lewat pipeline (worker class) — `backend/runtime/executor.py` ~235-254 inject `mcp_memory_context` dari search_nodes — buktikan task_context worker berisi memory (log/DB/event bukti).
- Acceptance: file bukti + output agent yang benar.

## FITUR 2 — Taste EFEKTIF di chat (bukan cuma scanner pasif)
- Status sekarang: `backend/conversation/engine.py` ~733-740 scan chat + log findings (PASIF). Chat "halo" masih balas "Hi! How can I help you today?" (AI-ism ringan). User mau output BERSIH.
- Fix: (a) kuatkan guardrail system prompt chat (Hermes/engine) supaya greeting/response tidak "How can I help you today?", "Great question!", "I'd be happy to", "Let me know if..." — dan (b) kalau `scan_summary` menemukan high findings di response, lakukan SATU pass rewrite LLM (instruksi "rewrite to remove AI patterns, keep meaning and tone") sebelum di-stream; kalau rewrite gagal, kirim apa adanya + log.
- Acceptance: chat "halo" → response TIDAK mengandung "How can I help you today?" / "Great question!" / "I'd be happy to"; response normal manusiawi; scan_summary high == 0 untuk greeting sederhana.
- Pastikan TIDAK false-positive pada bahasa Indonesia normal ("Halo! Ada yang bisa saya bantu hari ini." HARUS 0 findings — jangan masukkan frasa Indonesia ke wordlist banned).

# Acceptance Criteria GLOBAL (sebelum build 2.4.17)
1. BUG-17: /agent/run-sync bisa panggil mcp_* tools (memory create/search).
2. FITUR 1: memory create → search → persist (restart) → memory-aware context — semua terbukti runtime.
3. FITUR 2: chat anti-slop EFEKTIF (response bersih, rewrite pass jalan kalau perlu).
4. Tidak ada regresi BUG-01..16 (pipeline launch, worker spawn, provider live register, fallback model valid, dsb).
5. pytest hijau ATAU laporkan (23 pre-existing failure — jangan tambah baru).
6. Build 2.4.17 + latest.json update.
7. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB/file bukti.

## Repro Cepat
```bash
cd /home/tvd/AI-Company/backend && export AIC_DATA_DIR=/tmp/aicade-fix-r6
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

curl -s -X POST http://127.0.0.1:8000/mcp/servers/register-memory -H "Content-Type: application/json" -d '{}'
# simpan
curl -s -N -X POST http://127.0.0.1:8000/agent/run-sync -H "Content-Type: application/json" \
  -d '{"prompt":"Gunakan create_entities ...","worker_type":"hermes","project_id":null}' --max-time 90
cat $AIC_DATA_DIR/memory/memory.json   # harus ada entities
# cari
curl -s -N -X POST http://127.0.0.1:8000/agent/run-sync -H "Content-Type: application/json" \
  -d '{"prompt":"Cari di memory ...","worker_type":"hermes","project_id":null}' --max-time 90
```

## Catatan
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya.
- Backend port bisa 8000/8001/8002 — pakai port sesuai startup log.
- Kalau npx server memory lambat di packaged env, bundle binary server-memory ke `resources/` (ikut pola python-linux) dan pakai path lokal.

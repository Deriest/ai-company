# OpenCode Task: AIC-ADE 2.4.17 → 2.4.18 — Fix BUG-19 (CRITICAL: tool_calls dropped) + BUG-18 (version)

> Role: Senior Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro runtime, (3) verifikasi di app. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.18 (package.json + `backend/backend/config.py` fallback "2.4.18"!) + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json (version 2.4.18 + sha256 + size). Pastikan `AIC-ADE-2.4.18-linux-x86_64.AppImage` ADA di `app/release/` DAN `/health` report 2.4.18.

## Konteks
- Stack: Electron+React (`app/`) + FastAPI+SQLite (`backend/`). Gateway VansRouter `http://127.0.0.1:20129/v1`.
- Model stabil: `kr/qwen3-coder-next`, `kr/claude-sonnet-4.5`, `qd/qmodel_latest`, `WF/wf/*`. HINDARI combo/*, IAMHC/*, *free*, big-pickle.
- Fix round 1-6 sudah ada (BUG-01..17 + MCP Memory + Taste). JANGAN regresi.
- QA 2.4.17 menemukan BUG-19 (KRITIS — semua tool calling mati) + BUG-18.

# BUG-19 (CRITICAL — regression dari rewrite provider.py): tool_calls DROPPED di SSE parser → SEMUA tool (builtin + MCP) tidak pernah dieksekusi
- Gejala: `/agent/run-sync` prompt "List file di /tmp pakai tool list_directory" → agent balas teks "Saya akan membaca direktori /tmp..." → `tool_results: []`. Prompt "panggil create_entities..." → sama, tool tidak dipanggil. memory.json tetap kosong. Test LANGSUNG ke VansRouter (curl dengan tools payload) → model BENAR emit `tool_calls` → jadi bukan masalah model/gateway.
- Root cause (SUDAH DITEMUKAN): `backend/llm/provider.py` — `grep tool_calls` = NOL kemunculan. VansRouter SELALU return SSE (bahkan untuk request non-streaming). Parser SSE merge di `OpenAIProvider.chat` (~line 282-301) cuma akumulasi `delta.content` dan membuang `delta.tool_calls` — hasilnya `data.choices[0].message` TANPA field tool_calls → agent loop melihat response teks-only → tidak pernah mengeksekusi tool apa pun. Ini regression dari rewrite provider.py/chat_service.py (round-1): parsing tool_calls yang dulu ada hilang.
- Fix (WAJIB lengkap):
  1. Di `OpenAIProvider.chat` SSE merge: akumulasi `delta.tool_calls` (merge by index: `index`, `id`, `function.name`, `function.arguments` di-concat antar chunk) → set `message.tool_calls` di data yang di-merge.
  2. Di `OpenAIProvider.chat_stream` (line ~417) yang juga stream dari VansRouter: pastikan event `tool_calls` di-forward ke caller (cek bagaimana worker `_llm_with_tools` di `backend/workers/base.py` mengkonsumsi stream + parse tool_calls dari chunk).
  3. Response JSON path (non-SSE): pastikan `message.tool_calls` TIDAK dibuang (return `raw` / include tool_calls).
  4. Verifikasi dengan test unit: mock SSE chunks berisi tool_calls delta → chat() return message dengan tool_calls lengkap (name + arguments tergabung).
- Acceptance:
  1. `/agent/run-sync` "List file di /tmp pakai list_directory" → `tool_results` TIDAK kosong (berisi hasil list_directory).
  2. `/agent/run-sync` "panggil create_entities untuk entity ProjectTech [FastAPI, SQLite]" → tool_results TIDAK kosong + `$AIC_DATA_DIR/memory/memory.json` berisi entities.
  3. Pipeline worker (jalur `_llm_with_tools` / executor) bisa pakai tools builtin + mcp (task → worker documentation pakai create_entities → memory terisi).
  4. `pytest backend/tests/` tambahkan test SSE tool_calls merge — hijau.

# BUG-18 (MINOR): Version drift lagi — build 2.4.17 tapi /health report 2.4.16; latest.json masih 2.4.16
- Gejala: `AIC-ADE-2.4.17` di release, tapi `GET /health` → `"version":"2.4.16"`. latest.json masih version 2.4.16 (session round-6 selesai sebelum update).
- Root cause: `backend/backend/config.py` fallback version masih `"2.4.16"` (line ~31/34) — package.json di-bump ke 2.4.17 tapi fallback config.py lupa. /health baca settings.VERSION = _read_version_from_package_json() yang gagal/tidak match → fallback.
- Fix: SATU sumber versi — pastikan `config.py` fallback selalu sama dengan package.json, dan bump KEDUANYA di tiap rilis. Untuk round ini: bump ke 2.4.18 di package.json DAN config.py. Update latest.json LENGKAP (version, sha256, size, downloadUrl linux + win32).
- Acceptance: setelah build, `/health` → "2.4.18"; latest.json → version 2.4.18 + sha256 cocok dengan AppImage.

# VERIFIKASI E2E (setelah BUG-19 fix — WAJIB runtime, bukan cuma source)
1. Memory: register-memory → create_entities (via run-sync DAN pipeline worker) → memory.json terisi → search_nodes di task baru → jawab benar → restart → persist.
2. Taste: chat "halo" → response bersih (tidak "How can I help you today?" / "Great question!" / "I'd be happy to"); scan_summary high == 0 untuk greeting; tidak false-positive bahasa Indonesia normal.
3. Builtin tools: task pipeline worker beneran eksekusi read_file/search_files (bukan cuma ngaku).

# Acceptance Criteria GLOBAL (sebelum build 2.4.18)
1. BUG-19: agent eksekusi tool builtin + mcp (tool_results non-empty) di run-sync DAN pipeline.
2. Memory e2e: create → search → persist (restart) → memory-aware context — terbukti.
3. Taste: chat response anti-slop efektif.
4. BUG-18: /health 2.4.18 + latest.json lengkap.
5. Tidak ada regresi BUG-01..17 (pipeline launch, worker spawn, provider live register, fallback valid, chat persist, dsb).
6. pytest hijau ATAU laporkan (23 pre-existing failure — jangan tambah baru).
7. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB/file bukti.

## Repro Cepat
```bash
cd /home/tvd/AI-Company/backend && export AIC_DATA_DIR=/tmp/aicade-fix-r7
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
# (provider aktif dulu via UI/API, lalu:)
# BUG-19 builtin tool
curl -s -N -X POST http://127.0.0.1:8000/agent/run-sync -H "Content-Type: application/json" \
  -d '{"prompt":"List file di /tmp pakai tool list_directory","worker_type":"hermes","project_id":null}' --max-time 90
# BUG-19 mcp tool (setelah register-memory)
curl -s -X POST http://127.0.0.1:8000/mcp/servers/register-memory -H "Content-Type: application/json" -d '{}'
curl -s -N -X POST http://127.0.0.1:8000/agent/run-sync -H "Content-Type: application/json" \
  -d '{"prompt":"Gunakan create_entities untuk entity ProjectTech observations [\"FastAPI\",\"SQLite\"]","worker_type":"hermes","project_id":null}' --max-time 90
cat $AIC_DATA_DIR/memory/memory.json  # HARUS berisi entities
# Unit test SSE merge
cd /home/tvd/AI-Company/backend && .venv/bin/python -m pytest tests/test_llm_provider_sse.py -q 2>&1 | tail -3
```

## Catatan
- Ini fix PALING KRITIS sejauh ini — tool calling adalah inti worker/agent. JANGAN setengah-setengah; pastikan kedua jalur (chat non-streaming untuk agent loop, chat_stream untuk worker _llm_with_tools) mem-parse tool_calls.
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya.
- Backend port bisa 8000/8001/8002 — pakai port sesuai startup log.

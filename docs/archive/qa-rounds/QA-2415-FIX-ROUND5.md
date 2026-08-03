# OpenCode Task: AIC-ADE 2.4.15 → 2.4.16 — Fix BUG-16 (combo fallback) + verify Memory/Taste e2e

> Role: Senior Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro runtime, (3) verifikasi di app. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.16 + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json. Pastikan `AIC-ADE-2.4.16-linux-x86_64.AppImage` ADA di `app/release/`.

## Konteks
- Stack: Electron+React (`app/`) + FastAPI+SQLite (`backend/`). Gateway VansRouter `http://127.0.0.1:20129/v1`.
- Gateway knowledge (PENTING): model `combo/*` → 404 (no creds), `IAMHC/*` jelek, `*free*` rate-limit, `big-pickle` buruk. Model stabil: `kr/qwen3-coder-next`, `kr/claude-sonnet-4.5`, `qd/qmodel_latest`, `WF/wf/*`.
- Fix round 1-4 sudah ada (BUG-01..15 + MCP Memory + Taste). JANGAN regresi.
- QA 2.4.15 menemukan 1 bug baru yang BLOCKING LLM semua worker + verifikasi e2e 2 fitur baru.

# BUG-16 (CRITICAL): Fallback model selection memilih combo/* → 404 → semua worker gagal LLM
- Gejala: profile baru (worker_runtime kosong), `/chat/execute` → `LLM error: LLM request failed: Client error '404 Not Found' for url 'http://127.0.0.1:20129/v1/chat/completions'`. Penyebab: fallback model yang dipilih = `combo/Thinker` (VansRouter 404 untuk combo/*).
- Root cause: `backend/llm/provider.py` — filter fallback model di line ~238 dan ~448 cuma exlude `"free" in model.lower() or "deepseek" in model.lower() or "r1" in model.lower()`; TIDAK exlude `combo/`, `IAMHC/`, `big-pickle`. Jadi combo/Thinker (model pertama di provider_models) lolos filter dan dipakai sebagai fallback → 404. Di 2.4.14 kebetulan WF/* urutan duluan, di 2.4.15 combo/* duluan → ketergantungan urutan.
- Fix: perbaiki filter fallback model selection (dan onboarding model list) — exclude model id yang mengandung: `combo/`, `IAMHC/`, `big-pickle`, `free`, `deepseek`, `r1`. Pilih fallback dari sisa yang valid. Kalau semua ter-filter, pakai model non-combo pertama.
- ALSO: onboarding "Apply to Engine" selects (Thinker/Crafter/Sprinter) default ke combo/Thinker dll — pastikan dropdown model hanya menampilkan model VALID (filter yang sama), bukan semua model dari fetch. User memilih kr/qwen3-coder-next → worker_runtime terisi model valid.
- Acceptance:
  1. Profile baru + provider aktif (worker_runtime kosong) → `/chat/execute` task path BERESpons (bukan 404).
  2. Onboarding model dropdown TIDAK menampilkan combo/* (atau combo/* tidak bisa dipilih).
  3. Apply to Engine → worker_runtime.model_id = model valid pilihan user.

# VERIFIKASI E2E (setelah BUG-16 fix — WAJIB dibuktikan runtime)

## FITUR 1 — MCP Memory (registered ✅, butuh bukti create/search/persist)
- Setelah BUG-16 fix, test worker memakai memory tools: via `/agent/run-sync` (worker dengan MCP tools), prompt: "Simpan ke memory: project ini pakai FastAPI" → harus memanggil mcp create_entities/create_relations → file memory graph terisi.
- Task berikutnya (conversation baru): "Cari di memory apa stack project ini" → worker search_nodes → jawab FastAPI (retrieve lintas sesi).
- Restart app → memory graph masih ada (file persist di `$AIC_DATA_DIR/memory/memory.json`).
- Pastikan memory-aware context injection (`backend/runtime/executor.py` ~line 235-254) benar-benar menghasilkan mcp_memory_context yang masuk task_context worker (test: task dengan memory terisi → context worker mengandung hasil search_nodes).
- Acceptance: create → search → persist terbukti runtime (curl/DB/file bukti).

## FITUR 2 — Taste (skill ✅ + checker ✅, butuh bukti diterapkan)
- `scan_text` sudah terbukti (slop=6, clean=0) — sekarang buktikan TIDAK cuma fungsi: (a) skill `taste` muncul di UI Skill Registry dan assignable; (b) guardrail anti-slop ada di SYSTEM_PROMPT worker documentation/pm/rex/qa (grep `backend/agents/registry.py`); (c) chat app menjawab tanpa AI-ism (test chat biasa: "halo" → response TIDAK mengandung "I'd be happy to", "Great question!", "Let me know if...", em-dash berlebihan).
- Acceptance: skill taste visible + worker documentation menghasilkan deliverable yang scan_text-nya 0-1 findings; chat response anti-slop.

# Acceptance Criteria GLOBAL (sebelum build 2.4.16)
1. BUG-16: fallback model valid → /chat/execute + pipeline + worker semua jalan (tidak 404).
2. FITUR 1: memory create/search/persist lintas sesi terbukti.
3. FITUR 2: taste skill + guardrail + checker diterapkan di output nyata.
4. Tidak ada regresi BUG-01..15 (pipeline launch, worker spawn 15, chat persist, provider live register, version, dsb).
5. pytest hijau ATAU laporkan (22 pre-existing failure — jangan tambah baru).
6. Build 2.4.16 + latest.json update.
7. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB/file bukti.

## Repro Cepat
```bash
cd /home/tvd/AI-Company/backend && export AIC_DATA_DIR=/tmp/aicade-fix-r5
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# BUG-16 (provider aktif, worker_runtime kosong)
curl -s -N -X POST http://127.0.0.1:8000/chat/execute -H "Content-Type: application/json" \
  -d '{"conversation_id":"c1","worker_role":"crafter","messages":[{"role":"user","content":"halo"}]}' --max-time 30
# harus chunk content, BUKAN "LLM request failed 404"

# Memory e2e (setelah register-memory)
curl -s -X POST http://127.0.0.1:8000/mcp/servers/register-memory -H "Content-Type: application/json" -d '{}'
# lalu task simpan/cari memory via /agent/run-sync
# cek file: ls -la $AIC_DATA_DIR/memory/memory.json

# Taste
python -c "from backend.services.taste_checker import scan_text; print(len(scan_text('Great question! Let me dive into this comprehensive analysis.')))"
```

## Catatan
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya.
- Backend port bisa 8000/8001/8002 — pakai port sesuai startup log.

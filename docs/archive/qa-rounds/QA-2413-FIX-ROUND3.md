# OpenCode Task: AIC-ADE 2.4.13 → 2.4.14 — Fix Remaining Bugs (Round 3, small & surgical)

> Role: Senior Backend/Fullstack Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB disertai:
> (1) diff source, (2) test/repro yang membuktikan jalur bug, (3) verifikasi runtime.
> JANGAN commit sampai semua acceptance criteria terbukti — laporkan diff + test + curl/DB bukti.
> SETELAH SEMUA FIX TERBUKTI: bump versi ke 2.4.14 (package.json + semua string versi via settings.VERSION) lalu BUILD:
> `cd /home/tvd/AI-Company/app && npm run build && npx electron-builder --linux AppImage deb`
> Update latest.json (version 2.4.14 + sha256 + size + downloadUrl). Pastikan `AIC-ADE-2.4.14-linux-x86_64.AppImage` ADA di `app/release/`.

## Konteks
- Stack: Electron+React (`app/`) + FastAPI+SQLite (`backend/`). Gateway VansRouter `http://127.0.0.1:20129/v1`. Model aman: `qd/qmodel_latest`, `kr/qwen3-coder-next`.
- DB: env `AIC_DATA_DIR` → `<dir>/aic.db`.
- Round 1-2 sudah fix: BUG-01/02/05/06/07/08/09/10/11/12. JANGAN regresi.
- Re-QA artifact 2.4.13 menemukan 4 masalah tersisa (3 kecil + 1 model resolution). Ini yang harus dibenerin.

# BUG LIST (round 3)

## BUG-03 (HIGH): Apply to Engine → PATCH /runtime/workers/{role} 404 — workers_router TIDAK di-mount
- Gejala: onboarding pilih model + Apply to Engine → `worker_runtime.model_id`/`provider_id` tetap NULL (DB kosong), role sprinter tidak ada. Backend log: `PATCH /runtime/workers/crafter HTTP/1.1" 404` dan `PATCH /runtime/workers/sprinter 404`.
- Root cause (SUDAH DITEMUKAN): `backend/backend/api/routes/workers.py` mendefinisikan `@router.get("/runtime/workers")`, `@router.patch("/runtime/workers/{role}")`, `@router.get("/workers")`, dll — TAPI router ini TIDAK di-include di `backend/backend/main.py` (tidak ada `include_router(workers_router)`). Route orphan → semua PATCH 404. (GET /runtime/workers kebetulan jalan karena ada route lain yang serve.)
- Fix: mount router di main.py — import `workers_router` dari `backend.api.routes.workers` dan `app.include_router(workers_router, prefix="")`. Cek tidak bentrok dengan route GET /runtime/workers yang sudah ada.
- Acceptance: setelah onboarding Apply to Engine → `curl -X PATCH http://127.0.0.1:8000/runtime/workers/crafter -d '{"providerId":"<id>","modelId":"kr/qwen3-coder-next"}'` → 200; `SELECT role, provider_id, model_id FROM worker_runtime;` berisi model yang dipilih. Role sprinter row dibuat kalau belum ada.

## BUG-13 (MEDIUM): Dashboard/Office hitung worker = 5, harusnya 15
- Gejala: Office header "5 workers · 0 active", Live Company "15 specialized AI workers" — backend `/dashboard` report `workers: 5`. User EXPECTS 15 (kita punya 15 worker: Hermes, Rex, Aria, Sage, Luna, Echo, Atlas, Hugo, Leo, Eve, Pulse, Nova, Nexus, Flint, Sentinel).
- Root cause: `backend/backend/api/routes/dashboard.py` line ~50: `worker_count = count(WorkerRuntime.id)` — ngitung tabel worker_runtime (5 row tier), padahal roster worker asli = `AGENT_REGISTRY` (15 agent, `backend/agents/registry.py`). Pipeline beneran pakai 15 worker (WORKER_REGISTRY 16 class) — worker_runtime cuma 5 tier config.
- Fix: `workers` di /dashboard (dan source mana pun yang dipakai Office/Live Company) harus ngitung roster asli — `len(AGENT_REGISTRY)` (15) atau gabungan dengan WORKER_REGISTRY (16 kanonikal). Pastikan konsisten dengan Live Company.
- Acceptance: `curl -s http://127.0.0.1:8000/dashboard` → `workers: 15`; Office header "15 workers".

## BUG-14 (HIGH): /chat/stream plain chat → "No model configured" saat worker_runtime kosong
- Gejala: kirim chat biasa via `/chat/stream` (atau jalur ConversationEngine) di profile baru (worker_runtime.model_id kosong karena BUG-03) → response `{"type":"error","error":"No model configured. Please configure a model in Settings"}`. Padahal jalur `/chat/execute` jalan (resolve fallback model dari provider).
- Investigasi: cari string "No model configured" di backend — jalur ConversationEngine/engine membutuhkan model dari worker_runtime ATAU fallback; bedakan dengan jalur /chat/execute yang resolve provider default. Karena BUG-03 bikin worker_runtime kosong, jalur ini harus fallback ke model default provider (sama seperti /chat/execute), JANGAN error.
- Fix: model resolution di jalur engine/chat_stream harus fallback: worker_runtime.model_id → provider models default (fallback_model) → error hanya kalau TIDAK ADA provider sama sekali.
- Acceptance: setelah provider aktif (tanpa worker_runtime model), `/chat/stream` plain chat balas content normal (bukan error "No model configured").

## BUG-04 (LOW): Palette "Toggle Terminal" / "Toggle File Tree" masih no-op
- Gejala: item palette diklik → tidak ada panel muncul.
- Investigasi: `app/src/renderer/src/App.tsx` line ~196-197 sudah wire `onToggleTerminal={() => setShowTerminal(prev => !prev)}` dan `onToggleFileTree={() => setView("home")}` — tapi di artifact, klik item palette tetap tidak munculkan panel. Cek: apakah handler palette item benar-benar memanggil prop tersebut? Apakah komponen terminal ada dan render saat showTerminal true? (Cek komponen panel bawah / terminal component di renderer.)
- Fix: pastikan item palette memicu UI nyata (panel terminal muncul / view berubah), ATAU hapus item dari daftar palette. Acceptance: klik Toggle Terminal → panel muncul; Toggle File Tree → view berubah (bukan no-op).

## Acceptance Criteria (WAJIB SEMUA sebelum build)
1. BUG-03: PATCH /runtime/workers/{role} → 200; worker_runtime terisi model setelah Apply to Engine (termasuk sprinter).
2. BUG-13: /dashboard `workers: 15`; Office/Live Company konsisten 15.
3. BUG-14: /chat/stream plain chat berespons normal (tanpa "No model configured") setelah provider aktif.
4. BUG-04: palette toggle terminal/file tree bukan no-op.
5. Tidak ada regresi: BUG-07 (pipeline launch), BUG-12 (security spawn), BUG-11 (persist), BUG-09 (version), BUG-10 (no hardcode), update flow.
6. pytest di backend hijau ATAU laporkan command + hasil (catatan: ada 22 pre-existing failure schema — jangan dianggap regresi, tapi jangan tambah failure baru).
7. Build 2.4.14: AppImage ADA di app/release/, latest.json di-update.
8. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB bukti.

## Repro Cepat
```bash
cd /home/tvd/AI-Company/backend && export AIC_DATA_DIR=/tmp/aicade-fix-r3
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# BUG-03
curl -s -X PATCH http://127.0.0.1:8000/runtime/workers/crafter -H "Content-Type: application/json" \
  -d '{"providerId":"<prov>","modelId":"kr/qwen3-coder-next"}'   # harus 200, bukan 404
# BUG-13
curl -s http://127.0.0.1:8000/dashboard   # workers: 15
# BUG-14 (setelah provider aktif)
curl -s -N -X POST http://127.0.0.1:8000/chat/stream -H "Content-Type: application/json" \
  -d '{"conversation_id":"<id>","messages":[{"role":"user","content":"halo"}]}' --max-time 20
# response harus chunk content, bukan error "No model configured"
```

## Catatan
- Prioritas: BUG-03 → BUG-13 → BUG-14 → BUG-04 → build 2.4.14.
- Jangan ubah VansRouter/gateway. Jangan regresi fix round 1-2.
- Backend app bisa port-hopping (8000/8001/8002) — pakai port sesuai startup log.

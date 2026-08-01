# OpenCode Task: AIC-ADE 2.4.12 → 2.4.13 — Fix Remaining Blocker Bugs (Round 2)

> Role: Senior Backend/Fullstack Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB disertai:
> (1) diff source yang bisa direview, (2) test/repro yang membuktikan jalur bug,
> (3) verifikasi runtime. Ikuti aturan repo (AGENTS.md/CLAUDE.md kalau ada).
> JANGAN commit sampai semua acceptance criteria terbukti — laporkan diff + test + curl/DB evidence.
> SETELAH SEMUA FIX TERBUKTI: bump versi ke 2.4.13 (package.json + semua string versi) lalu BUILD:
> `cd /home/tvd/AI-Company/app && npm run build && npx electron-builder --linux AppImage deb`
> Pastikan artifact `AIC-ADE-2.4.13-linux-x86_64.AppImage` muncul di `app/release/` sebelum selesai.

## Konteks

- Stack: Electron + React (`app/`) + FastAPI + SQLite (`backend/`).
- Gateway: VansRouter `http://127.0.0.1:20129/v1`. Model test aman: `qd/qmodel_latest`, `kr/qwen3-coder-next`, atau `kr/claude-sonnet-4.5`. Hindari `combo/*`, `IAMHC/*`, `*free*`.
- DB aktif: data dir via env `AIC_DATA_DIR` → `<AIC_DATA_DIR>/aic.db`.
- Round 1 (2.4.12) sudah fix: BUG-01 (updates display), BUG-02 (delivery/stats), BUG-05 (unpack crash), BUG-06 (qa python), BUG-08 (default project), worker selection diperluas (research/database/performance reachable). JANGAN regresi yang sudah fixed.
- Berikut bug yang MASIH ADA dari QA totalitas 2.4.12 (score 62/100).

# BUG LIST (round 2)

## BUG-07 (CRITICAL): Pipeline tetap TIDAK launch dari chat flow — task stuck "created"
- Gejala: task dibuat dari chat (task request → confirm "yes go ahead" via `/chat/stream`), status tetap `created`, 0 events `pipeline.*`, 0 leases, 0 dispatch_session. Pipeline cuma jalan kalau dipanggil langsung via script (run_engineering_pipeline) — bukan dari flow chat.
- Investigasi yang sudah dilakukan:
  - `backend/conversation/engine.py` `_launch_pipeline()` (line ~420-455) memanggil `asyncio.create_task(_run())` dan fix GC round-1 (`self._background_tasks.add(task_ref)`) SUDAH ADA di bundle tapi TIDAK menyelesaikan.
  - Minimal repro FastAPI standalone (pattern: StreamingResponse handler → asyncio.create_task → tulis file) BERJALAN dengan bundled python. Jadi pola create_task OK — bug app-specific.
  - `_run()` berisi: `from storage.database import async_session` → `async with _async_session()` → query task → `run_engineering_pipeline`. Tidak ada log "Pipeline finished" MAUPUN "Pipeline background failed" — jadi coroutine tidak pernah eksekusi ATAU hang diam-diam.
  - Hipotesis yang belum diverifikasi: (a) event loop context saat SSE generator selesai, (b) background session hang karena SQLite lock (request session masih open), (c) coroutine tidak pernah di-schedule.
- Tugas: TEMUKAN root cause sebenarnya (jangan asal ganti ke await blocking — pipeline harus tetap background). Beri bukti log/event setelah fix.
- Acceptance: task dari `/chat/stream` (task request + confirm) berubah status melewati phase, events + leases + dispatch_session ter-record. Reproduksi via curl terhadap backend yang jalan.

## BUG-11 (HIGH): Chat biasa (non-task) tidak persist pesan assistant — history hilang
- Gejala: kirim pesan chat biasa ("halo siapa kamu") di Command Center → user message tersimpan, TAPI response assistant TIDAK tersimpan di tabel messages. Setelah reload, history hilang.
- Investigasi: `backend/backend/api/routes/chat.py` — `/chat/execute` untuk intent selain task_request/task_confirm fallback ke `chat_stream_endpoint` (line ~322 `event_generator`) yang cuma `chat_service.chat_stream(...)` + yield, TANPA persist Message. Bandingkan dengan jalur ConversationEngine (`process_message`) yang persist user+assistant, dan jalur `/chat/execute` full-pipeline yang persist di Step 3 (line ~170-196).
- Fix: jalur plain chat WAJIB persist user + assistant messages ke DB (role user/assistant, conversation_id, status completed) — di chat_stream_endpoint atau dalam chat_service.chat_stream. Jangan double-persist di jalur ConversationEngine.
- Acceptance: kirim chat biasa via UI/curl → `SELECT count(*) FROM messages WHERE conversation_id='...'` naik 2 (user+assistant); reload UI → history tampil.

## BUG-03 (HIGH): Onboarding "Apply to Engine" tidak persist model ke worker_runtime
- Gejala: setelah pilih model Thinker/Crafter/Sprinter + Apply to Engine, `worker_runtime.model_id`/`provider_id` tetap NULL; role sprinter TIDAK ADA di worker_runtime.
- Investigasi: cek endpoint yang dipanggil "Apply to Engine" di `app/src/renderer/` dan `backend/backend/api/routes/profile.py` (`/profile/complete-onboarding` cuma mark onboarding). PATCH `/runtime/workers/{role}` ada di `backend/backend/api/routes/workers.py` (update_worker_runtime) — pastikan UI onboarding memanggilnya dengan benar (role, provider_id, model_id) untuk thinker/crafter/sprinter.
- Acceptance: setelah onboarding + Apply to Engine, `SELECT role, provider_id, model_id FROM worker_runtime;` berisi model yang dipilih (termasuk sprinter row yang dibuat kalau belum ada).

## BUG-09 (MEDIUM): Version drift — /health masih "2.4.11" di build 2.4.12
- Gejala: `GET /health` report "2.4.11" padahal app 2.4.12; config.py sudah dynamic tapi 2 string masih hardcode.
- Investigasi: `backend/backend/api/routes/providers.py:67` dan `backend/backend/main.py:145` masih `"2.4.11"`. Cek juga semua string versi lain: `grep -rn '"2\.4\.1[012]"' backend/ app/src/ | grep -v node_modules`.
- Fix: satu sumber versi (package.json → shared constant), semua string versi ikut. Pastikan setelah bump 2.4.13, /health report 2.4.13.

## BUG-10 (MEDIUM): Live Company & Office hardcode "15 workers"
- Gejala: Office header "15 workers · 0 active", Live Company org chart 15 worker status statis "idle" — backend `/runtime/workers` cuma 5 row, `/dashboard` report `workers: 5`.
- Investigasi: `app/src/renderer/` — string template `15 workers · ${K} active` hardcoded; daftar 15 worker di Live Company hardcoded di bundle (tiap nama 2x).
- Fix: UI render dari sumber backend yang benar (endpoint workforce/agents yang menyatukan AGENT_REGISTRY 15 definisi + status runtime), ATAU sinkronkan angka/status dengan API. Jangan hardcode.
- Acceptance: Office/Live Company menampilkan data konsisten dengan API (jumlah worker = yang dikelola runtime; status worker real).

## BUG-04 (LOW): Palette "Toggle Terminal" & "Toggle File Tree" no-op
- Gejala: item palette tidak melakukan apa-apa (handler null).
- Fix: hilangkan item dead dari palette ATAU wire ke komponen nyata. Acceptance: tidak ada item palette yang no-op.

## BUG-12 (MEDIUM): security tidak spawn untuk task dengan keyword login/JWT (Kelompok 3 gap)
- Gejala: task "todo app + login JWT" → guardrail security seharusnya trigger (keyword login), tapi leases tidak ada worker security.
- Investigasi: `backend/workflow/triage.py` GUARDRAIL_PATTERNS security (pattern includes login) → enforced_workers + security → selected_workers. Cek chain: triage selected_workers → `backend/workflow/fsm.py` allowed_workers_for_phase → executor phase filter (`runtime/executor.py`). Kemungkinan: planning phase filter menghapus security, atau taskgraph node worker_type override, atau selected_workers tidak sampai ke executor.
- Fix: pastikan security (dan flint/nexus/database untuk task yang relevan) benar-benar ter-spawn saat guardrail/keyword terpenuhi. Acceptance: task dengan keyword login/JWT menghasilkan lease security; task infra menghasilkan lease flint/nexus.

## Acceptance Criteria (WAJIB SEMUA sebelum build)
1. BUG-07: task dari chat menjalani phase (events + leases + dispatch_session ter-record), TIDAK stuck "created".
2. BUG-11: chat biasa persist 2 messages (user+assistant); history tampil setelah reload.
3. BUG-03: worker_runtime berisi model yang dipilih setelah Apply to Engine.
4. BUG-09: /health report 2.4.13 setelah bump.
5. BUG-10: Office/Live Company konsisten dengan backend.
6. BUG-04: tidak ada palette dead action.
7. BUG-12: security spawn untuk task login/JWT; flint/nexus untuk task infra.
8. Tidak ada regresi: BUG-01/02/05/06/08 tetap fixed; /health 200; chat task_request tetap create task; update flow tetap jalan.
9. `pytest` di `backend/` hijau (atau laporkan command + hasil).
10. Build 2.4.13: `AIC-ADE-2.4.13-linux-x86_64.AppImage` ADA di `app/release/`, latest.json di-update (version 2.4.13 + sha256 + size + downloadUrl).
11. JANGAN commit sampai semua terbukti; laporkan diff + test + curl/DB bukti. Blocker yang tidak bisa dipenuhi: tuliskan + alasan, jangan diam-diam skip.

## Cara Repro Cepat
```bash
# backend dari source dengan DB test
cd /home/tvd/AI-Company/backend
export AIC_DATA_DIR=/tmp/aicade-fix-r2
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health

# BUG-07: task request + confirm via /chat/stream, lalu cek
sqlite3 $AIC_DATA_DIR/aic.db "SELECT id,status FROM tasks;"
sqlite3 $AIC_DATA_DIR/aic.db "SELECT worker_type,phase,status FROM leases;"
sqlite3 $AIC_DATA_DIR/aic.db "SELECT type,actor FROM events WHERE type LIKE 'pipeline%';"

# BUG-11: chat biasa, lalu cek count messages
curl -s -N -X POST http://127.0.0.1:8000/chat/stream -H "Content-Type: application/json" \
  -d '{"conversation_id":"<id>","messages":[{"role":"user","content":"halo"}]}' --max-time 20
sqlite3 $AIC_DATA_DIR/aic.db "SELECT role,count(*) FROM messages GROUP BY role;"
```

## Catatan
- Prioritas: BUG-07 → BUG-11 → BUG-03 → sisanya → build 2.4.13.
- Jangan ubah VansRouter/gateway. Jangan regresi fix round-1.
- Backend app bisa jalan di port 8000/8001/8002 (port-hopping) — pastikan curl pakai port yang benar sesuai startup log.

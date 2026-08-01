# OpenCode Task: AIC-ADE 2.4.11 — Fix Bugs + Worker Spawning (14 worker optimal)

> Role: Senior Backend/Fullstack Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB disertai:
> (1) diff source yang bisa direview, (2) test/repro yang membuktikan jalur bug,
> (3) verifikasi runtime. Ikuti aturan repo (AGENTS.md/CLAUDE.md kalau ada).
> JANGAN commit sampai semua acceptance criteria terbukti — laporkan diff + test + curl/DB evidence.

## Konteks

- Stack: Electron + React (`app/`) + FastAPI + SQLite (`backend/`), backend Python bundle di `backend/`.
- Gateway: VansRouter `http://127.0.0.1:20129/v1` (OpenAI-compatible). Model stabil untuk test: `kr/qwen3-coder-next` atau `kr/claude-sonnet-4.5`. Hindari `combo/*`, `IAMHC/*`, `*free*` (gagal/rate-limit).
- DB aktif saat run: data dir di-set via env `AIC_DATA_DIR` (Electron set ke userData). Path DB: `<AIC_DATA_DIR>/aic.db`.
- Ada TIGA kelompok masalah: (1) bug QA UI/UX/data, (2) bug worker/pipeline hasil investigasi, (3) requirement worker spawning optimal (14 worker reachable sesuai kebutuhan task).

# KELOMPOK 1 — Bug QA (UI/UX/Data)

## BUG-01 (MEDIUM): Settings > Updates menampilkan "up_to_date" DAN "New Version: 2.4.9" bersamaan
- Gejala: app 2.4.11, tab Updates/General nunjukin `Update Status: up_to_date` tapi `New Version: 2.4.9` (versi LEBIH TUA). Kontradiktif & misleading.
- Repro: jalankan app, buka Settings → General atau Updates.
- Investigasi: `app/src/main/updateManager.ts` — `checkForUpdates()` selalu set `availableVersion: manifest.version` bahkan saat `isNewerVersion()` false (blok `!newer`). Manifest lokal `latest.json` di repo juga stale (masih 2.4.9).
- Fix: saat status `up_to_date`, jangan expose "New Version" ke UI (null/kosong), dan bump `latest.json` ke versi terbaru. UI renderer hanya tampilkan kolom New Version kalau status `available`/`ready_to_install`.

## BUG-02 (MEDIUM): GET /api/delivery/stats → 404 "Engineering Report not found"
- Gejala: endpoint stats delivery selalu 404, padahal route terdaftar di OpenAPI.
- Repro: `curl -s http://127.0.0.1:8000/api/delivery/stats` → `{"detail":"Engineering Report not found"}`
- Investigasi: `backend/backend/routes/delivery.py` — `@router.get("/{report_id}")` (line ~48) dideklarasikan SEBELUM `@router.get("/stats")` (line ~105), jadi "stats" ketangkap sebagai `report_id`. Route shadowing FastAPI.
- Fix: pindahkan `/stats` (dan `/brief/{brief_id}`) SEBELUM `/{report_id}`, atau pakai path literal yang tidak bentrok. Verifikasi `curl` balik 200 + JSON stats.

## BUG-03 (MEDIUM): Onboarding "Apply to Engine" tidak persist model ke worker_runtime
- Gejala: setelah pilih model Thinker/Crafter/Sprinter di onboarding lalu "Apply to Engine", DB `worker_runtime.model_id`/`provider_id` tetap NULL, dan role `sprinter` TIDAK ADA di tabel worker_runtime (cuma thinker/crafter/reviewer/planner/manager).
- Repro: `sqlite3 <db> "SELECT role, model_id FROM worker_runtime;"` setelah onboarding.
- Investigasi: cek endpoint yang dipanggil "Apply to Engine" di `app/src/renderer/` dan `backend/backend/api/routes/profile.py` (`/profile/complete-onboarding` cuma mark onboarding, tidak assign model). Model assignment harus nulis ke `worker_runtime` (PATCH `/runtime/workers/{role}`) atau tabel config yang benar.
- Fix: pastikan Apply to Engine benar-benar menulis provider_id+model_id ke worker_runtime untuk role yang dipilih, dan sinkron dengan `sprinter` (kalau tier sprinter dipakai di engine, pastikan row ada).

## BUG-04 (LOW): Command Palette "Toggle Terminal" & "Toggle File Tree" no-op
- Gejala: pilih item palette tersebut → palette nutup, TIDAK ada panel terminal/file-tree yang muncul di halaman manapun.
- Investigasi: `app/src/renderer/` — aksi palette `toggle-terminal`/`toggle-file-tree` (`action:()=>{h==null||h(),c()}` di bundle = handler null). Cek apakah fitur terminal/file-tree sudah diimplementasi; kalau belum, hilangkan item dari palette atau wire ke komponen yang ada.
- Fix: item palette harus menjalankan aksi nyata (munculkan panel), atau dihapus dari daftar agar tidak dead action.

# KELOMPOK 2 — Bug Worker/Pipeline (hasil investigasi runtime)

## BUG-05 (CRITICAL): 3 worker class crash — "too many values to unpack (expected 2)"
- Gejala: di jalur pipeline (runtime executor), DesignerWorker, GovernorWorker, ReviewWorker selalu ValueError: `too many values to unpack (expected 2)` → phase gagal.
- Repro (sudah tervalidasi):
  ```bash
  cd /home/tvd/AI-Company/backend
  python3 - <<'EOF'
  import asyncio
  from workers.base import GovernorWorker
  async def main():
      w = GovernorWorker(); w.agent_id = "rex"
      await w.execute({"task_id":"x","title":"t","description":"d","type":"feature",
                       "repo_path":"/home/tvd/AI-Company/backend","phase":"closeout",
                       "handoffs":{},"skills":[],"memories":[]})
  asyncio.run(main())
  EOF
  # → ValueError: too many values to unpack (expected 2)
  ```
- Investigasi: `backend/workers/base.py` — `_llm_with_tools()` return TUPLE 3 elemen `(content, meta, all_tool_calls)`, tapi 3 caller unpack 2:
  - line 668 (ReviewWorker): `content, meta = await _llm_with_tools(...)`
  - line 1012 (DesignerWorker): `content, meta = await _llm_with_tools(...)`
  - line 1036 (GovernorWorker): `content, meta = await _llm_with_tools(...)`
- Fix: ubah ketiganya jadi 3-unpack (`content, meta, tool_calls = ...`) dan pass `tool_calls` ke `_result_from_llm(...)` seperti worker lain. Jangan ubah signature `_llm_with_tools` (15 caller lain sudah pakai 3-unpack).

## BUG-06 (HIGH): TestingWorker (qa) crash — subprocess "python" tidak ditemukan
- Gejala: di pipeline, worker qa gagal `[Errno 2] No such file or directory: 'python'` → VERIFICATION FAILED → repair loop → task gagal.
- Investigasi: `backend/workers/base.py` line ~739-741 & ~750: `asyncio.create_subprocess_exec("python", "-m", "pytest", ...)` dan `"npm", "test"` — hardcoded `"python"` tidak ada di PATH packaged app (backend jalan dari bundled python). Harus pakai `sys.executable` (interpreter yang sedang jalan) untuk pytest, dan untuk npm pakai `shutil.which("npm")` dengan error handling.
- Fix: ganti `"python"` → `sys.executable`; kalau `npm` tidak ada, beri pesan gagal yang jelas (bukan crash). Verifikasi dengan run worker qa di pipeline.

## BUG-07 (HIGH): Pipeline tidak pernah launch dari chat flow — task stuck "created"
- Gejala: task dibuat dari chat (build mode, task-request + confirm) tapi status tetap `created`, TIDAK ada events (`pipeline.stage.started`), TIDAK ada leases, TIDAK ada dispatch_session. Pipeline baru jalan kalau dipanggil langsung (script), bukan dari flow UI.
- Repro: buat task lewat `/chat/stream` (message "Buatkan aplikasi todo list..." lalu "yes go ahead"), tunggu 2-5 menit, cek:
  ```bash
  sqlite3 <db> "SELECT id,status FROM tasks;"
  sqlite3 <db> "SELECT type,actor,target FROM events WHERE type LIKE 'pipeline%';"
  # tasks tetap 'created', events pipeline 0 baris
  ```
- Investigasi: `backend/conversation/engine.py` `_launch_pipeline()` (line 420-451) — `asyncio.create_task(_run())` fire-and-forget tidak pernah eksekusi (0 log "Pipeline finished" / "Pipeline background failed", 0 event). Bandingkan dengan `_do_record()` line 885 yang juga create_task (kalau itu jalan, cari bedanya). Kemungkinan: task ter-GC, event loop context beda, atau import `storage.database` session bermasalah di packaged env. PENTING: verifikasi root cause, jangan asal ganti ke `await` blocking — pipeline harus tetap background, tapi reliable.
- Fix: pipeline WAJIB start dan progress: task berubah status (discovery/planning/.../completed/failed), events ter-record, leases ter-create. Test end-to-end dari `/chat/stream`.

## BUG-08 (HIGH): Fresh profile "no project linked" — misi tidak bisa dibuat sama sekali
- Gejala: fresh install (profile baru), user kirim task request → "Reply yes / go ahead", confirm → "Unable to create task — no project linked." Task tidak pernah dibuat.
- Investigasi: `backend/conversation/engine.py` `_get_or_create_project()` — butuh `conversation.user_id` untuk auto-create "Chat Project", tapi `conversations.user_id` NULL (users table kosong di local-first mode; onboarding tidak assign user). Cek alur create conversation di `backend/backend/api/routes/conversations.py` + frontend.
- Fix: untuk mode local-first, auto-create project tanpa user_id (misal fallback ke `local_profile.id` atau project default), atau set user_id saat onboarding selesai. Acceptance: fresh profile bisa buat task dari chat tanpa setup manual.

## BUG-09 (MEDIUM): Version drift — beberapa string versi tidak sinkron
- Gejala: `local_profile.app_version` = "2.4.9" padahal app 2.4.11; `backend/backend/config.py` VERSION default "2.1.7a".
- Investigasi: `grep -rn '"2\.4\.9"\|2\.1\.7a\|version' backend/ app/src/ | grep -v node_modules` — temukan semua tempat versi di-hardcode.
- Fix: satu sumber versi (dari package.json / satu constant), semua string versi mengikutinya. Pastikan `GET /health` dan profile report versi yang benar.

## BUG-10 (MEDIUM): Live Company & Office menampilkan 15 worker HARDCODED, tidak konsisten dengan backend
- Gejala: halaman Office nunjukin "15 workers · 0 active", Live Company nampilin org chart 15 worker (Hermes, Rex, Aria, Sage, Luna, Echo, Atlas, Hugo, Leo, Eve, Pulse, Nova, Nexus, Flint, Sentinel) dengan status statis "idle"/task kosong — padahal backend `/runtime/workers` dan `/workers` cuma return 5 row (thinker/crafter/reviewer/planner/manager), dan `/dashboard` report `workers: 5`. Jadi angka "15" dan status worker di UI TIDAK didukung data runtime — user bisa salah kaprah mengira 15 worker hidup & jalan.
- Repro: buka Office (`15 workers`) vs `curl -s http://127.0.0.1:8000/dashboard` (`workers: 5`); Live Company vs `curl -s http://127.0.0.1:8000/runtime/workers` (5 row, status Idle).
- Investigasi: `app/src/renderer/` — string template `15 workers · ${K} active` di Office HARDCODED; daftar 15 worker di Live Company juga HARDCODED di bundle (tiap nama muncul 2x: kartu org chart + daftar palette), status "idle" statis, bukan dari API.
- Fix: UI harus render dari sumber data backend yang benar (misal endpoint workforce/agents yang menyatukan AGENT_REGISTRY 15 definisi + status runtime), atau sinkronkan: angka worker = jumlah worker yang benar-benar dikelola runtime; status worker = real (idle/running dari worker_execution/lease). Jangan hardcode. Acceptance: Office/Live Company menampilkan data yang konsisten dengan API, dan status worker mencerminkan eksekusi nyata.

# KELOMPOK 3 — REQUIREMENT: Worker Spawning Optimal (14 worker reachable sesuai kebutuhan task)

## MASALAH
Workflow saat ini HANYA spawn ~6 worker secara konsisten (PM, Architect, Designer, Backend, Frontend, QA). Sebagian worker TIDAK PERNAH kepanggil. User requirement: KALAU TASK BUTUH WORKER TERTENTU (contoh security, flint, nexus), WORKER ITU HARUS DIPANGGIL — semua 14 worker (selain Hermes/dispatcher) harus bisa bekerja tergantung task yang dikerjakan.

### HASIL AUDIT REACHABILITY 14 WORKER (kecuali Hermes/dispatcher) — kondisi SEKARANG
| Worker | Phase | Jalur pemilihan | Status |
|---|---|---|---|
| pm (Aria) | discovery/investigate/closeout | fsm.py:154/157/181 + triage | ✅ REACHABLE (sering) |
| architect (Atlas) | planning | fsm.py:161-167 | ✅ REACHABLE (tapi planning di-skip STANDARD) |
| backend (Hugo) | implementation | fsm.py:149-156 + triage | ✅ REACHABLE (sering) |
| frontend (Leo) | implementation | fsm.py:149-156 + triage | ✅ REACHABLE (sering) |
| qa (Eve) | verification | fsm.py:178 | ✅ REACHABLE tapi CRASH (BUG-06) |
| database (Nova) | planning/impl | guardrail triage.py:76 + fsm.py:163 | ✅ REACHABLE (keyword database/sql/migration) |
| security (Sentinel) | planning/impl | guardrail triage.py:69 + classifier engine.py:75 + fsm.py:166-167 | ✅ REACHABLE (keyword auth/jwt/security) |
| rex (Governor) | closeout | fsm.py:181 | ✅ REACHABLE tapi CRASH (BUG-05) |
| documentation (Echo) | closeout | fsm.py:181 + classifier | ✅ REACHABLE (closeout) |
| designer (Luna) | planning | fsm.py:161/168 default | ⚠️ RAPIH — planning di-skip di STANDARD mode + CRASH (BUG-05) |
| flint (Deployment) | planning/impl | classifier engine.py:72 (deploy/docker/infra → devops) + fsm.py:164-165 | ⚠️ RAPIH — cuma lewat alias "devops"; kata "infrastructure" ada di classifier tapi TIDAK di WORKER_TYPE_MAP |
| research (Sage) | investigate | classifier engine.py:73 (research/analyze/explore) → tw=research, TAPI fsm.py:157 tidak include "research" di tuple | ❌ EFEKTIF TIDAK REACHABLE — classifier bisa output research tapi FSM filter menolak |
| performance (Pulse) | verification | cuma PHASE_WORKERS fsm.py:58; filter verification fsm.py:177-178 hardcode `["qa"]` | ❌ UNREACHABLE — TIDAK PERNAH kepilih |
| nexus (Integration) | planning/impl | cuma PHASE_WORKERS fsm.py:48 + intersection executor fsm.py:149; TIDAK ada di triage/classifier/WORKER_TYPE_MAP | ❌ UNREACHABLE — TIDAK PERNAH kepilih |

Kesimpulan audit: 3 worker TIDAK PERNAH kepanggil (performance, nexus, research-efektif), 2 rapuh (designer, flint), 3 crash kalau kepanggil (rex, qa, designer). Akar masalah: (a) selection 3-layer (triage → FSM → executor) tidak konsisten & saling konflik, (b) skip_phases STANDARD menghilangkan planning (phase-nya designer/database/nexus/flint/security), (c) verification hardcode ["qa"], (d) WORKER_TYPE_MAP + classifier tidak lengkap, (e) BUG-05/06 crash.

## YANG DIMINTA
Dispatcher/orchestrator harus SPAWN WORKER SESUAI KEBUTUHAN TASK — kalau task butuh X, spawn SEMUA worker yang diperlukan untuk X, sehingga seluruh roster worker (14 worker selain Hermes/dispatcher) optimal terpakai tergantung task. Bukan 6 worker itu-itu saja.

### Requirements konkret
1. **Satu sumber keputusan worker (single source of truth)**: pilih SATU resolver (rekomendasi: perluas `dispatcher/worker_selector.py` capability-matching, atau triage `selected_workers` yang dihormati SEMUA phase) — lalu triage → FSM → executor memakainya konsisten. Hapus konflik 3-layer yang bikin database ke-pilih tapi backend yang jalan (kejadian nyata di QA).
2. **Semua 14 worker HARUS reachable** (tulis test reachability per worker):
   - `performance`: verification → QA + Performance BERSAMA. Hapus hardcode `["qa"]` di fsm.py:177-178.
   - `nexus`: tambah guardrail/classifier keyword (integration, webhook, api integration, message queue, service-to-service, middleware integration) + WORKER_TYPE_MAP "integration"→nexus + branch planning fsm yang return nexus (misal tw=nexus/integration → architect+nexus) + default triage EXTENDED/FULL include nexus.
   - `research`: fsm.py:157 tambah "research" ke tuple yang mengizinkan `["pm","research"]`; dan default investigate (tanpa tw spesifik) harus `["pm","research"]`.
   - `designer`: planning TIDAK boleh di-skip untuk STANDARD task kompleks (triage skip_phases planning dihapus/diperhalus — planning jalan kecuali QUICK/trivial).
   - `flint`: WORKER_TYPE_MAP tambah "infrastructure"/"deploy"/"docker" → flint (bukan cuma devops alias); pastikan fsm.py:164-165 branch tw=devops/infrastructure/flint jalan.
   - `database`/`security`: sudah reachable — pastikan tetap, dan jangan di-drop di phase manapun setelah ke-pilih.
   - `rex`/`documentation`/`pm`/`architect`/`backend`/`frontend`/`qa`: tetap reachable + tidak crash (fix BUG-05/06).
3. **Triage isi selected_workers lengkap sesuai task**: `workflow/triage.py` — selain guardrail (security/database/architect), tambah guardrail/pattern utk infra (flint), integration (nexus), perf (performance utk task performance-critical), research (task research), dan default STANDARD/EXTENDED/FULL yang lebih lengkap (bukan cuma backend+qa).
4. **Executor hormati selected_workers di SEMUA phase** (runtime/executor.py + fsm.py:149): sekarang intersection cuma berlaku di implementation — perluas ke planning/verification/closeout.
5. **Semua worker yang ke-spawn harus BERHASIL**: fix BUG-05 & BUG-06 (lihat Kelompok 2). Fallback TIDAK boleh menyamar sebagai sukses.
6. **Contoh hasil yang diharapkan**:
   - Task fullstack "todo app + auth JWT + SQLite" → spawn: pm, research, architect, designer, database, security, backend, frontend, qa, performance, rex, documentation (≥12 worker)
   - Task infra "deploy docker ke server" → spawn: pm, research, architect, flint, nexus, backend, qa, performance, rex, documentation (≥10 worker)
   - Task "riset arsitektur microservice" → spawn: pm, research, architect, security, database, documentation, rex (research WAJIB muncul)

## Acceptance Criteria (WAJIB SEMUA sebelum selesai)
1. BUG-05: `python3 repro` di atas tidak lagi ValueError; `_result_from_llm` menerima tool_calls. Unit test untuk 3 class.
2. BUG-06: worker qa di pipeline tidak crash `'python'`; pakai `sys.executable`.
3. BUG-07: task dari `/chat/stream` (task request + confirm) berubah status melewati phase dan menghasilkan leases + events + dispatch_session (atau completed/failed dengan alasan jelas). Task TIDAK diam di "created".
4. BUG-08: fresh profile (tanpa project) bisa create task dari chat.
5. BUG-01: Settings Updates tidak lagi nunjukin "New Version" saat up_to_date.
6. BUG-02: `curl /api/delivery/stats` → 200.
7. BUG-03: onboarding Apply to Engine menulis provider_id+model_id ke worker_runtime.
8. BUG-04: palette Toggle Terminal/File Tree tidak dead-action (muncul panel ATAU item dihapus).
9. BUG-10: Office/Live Company menampilkan jumlah + status worker yang konsisten dengan backend API (bukan hardcode "15").
10. Kelompok 3: untuk task fullstack sederhana (backend+frontend+db), pipeline spawn ≥ database/security di planning, backend+frontend di implementation, qa+performance di verification, rex+documentation di closeout. Untuk task infra, spawn flint+nexus. Untuk task research, research ikut spawn. Buktikan dengan log `pipeline.worker.started` / leases / event rows.
11. Test reachability: setiap worker dari 14 (selain hermes) minimal muncul di SATU skenario task test (unit test).
12. Tidak ada regresi: /health 200, chat simple jalan, dashboard jalan, /runtime/workers jalan.
13. `pytest` di `backend/` hijau (jalankan `python -m pytest -q` dari `backend/`; kalau butuh setup khusus, laporkan command-nya).
14. JANGAN commit sampai semua di atas terbukti; laporkan diff + test + curl/DB bukti. Kalau ada yang tidak bisa dipenuhi, tuliskan blocker + alasan, jangan diam-diam skip.

## Cara Repro Cepat (untuk verifikasi runtime)
```bash
# 1. jalankan backend dari source (pakai DB test terpisah)
cd /home/tvd/AI-Company/backend
export AIC_DATA_DIR=/tmp/aicade-fix-test
pip install -r requirements.txt 2>/dev/null || true
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &

# 2. cek health
curl -s http://127.0.0.1:8000/health

# 3. buat provider test (kalau belum ada) lalu task request + confirm
#    (ikuti alur /chat/stream seperti di BUG-07)

# 4. verifikasi worker spawn
sqlite3 $AIC_DATA_DIR/aic.db "SELECT worker_type, phase, status FROM leases;"
sqlite3 $AIC_DATA_DIR/aic.db "SELECT type, actor FROM events WHERE type LIKE 'pipeline%';"
```

## Catatan
- Jangan ubah VansRouter/gateway — semua fix di sisi app.
- `backend/dispatcher/engine.py` masih ada jalur SIMULASI (`# Simulate execution... In production, this would dispatch to actual workers`) — orchestrator pakai jalur real (`runtime/executor.py`). Rapikan/konsistenkan: pastikan tidak ada jalur yang diam-diam simulate tanpa tanda.
- Prioritas: BUG-05/06 (crash) → BUG-07/08 (pipeline tidak jalan) → Kelompok 3 (spawning) → sisanya.
- Model test yang aman: `kr/qwen3-coder-next` atau `kr/claude-sonnet-4.5` via gateway VansRouter `http://127.0.0.1:20129/v1`.

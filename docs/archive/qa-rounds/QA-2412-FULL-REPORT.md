# AIC-ADE 2.4.12 — Full QA Report (Totalitas)

Tanggal: 2026-08-01 | Build: AIC-ADE-2.4.12-linux-x86_64.AppImage (182.6MB, sha 655974f3...)
Metode: Xvfb :99, CDP, fresh profile, VansRouter gateway, model fallback WF/wf/sonnet-4.5
Score READY-TO-USE: **62/100** (target 95 — BELUM READY)

---

## 1. UPDATE FLOW (test via app) — ✅ LULUS END-TO-END
- 2.4.11 → Check for Updates → "Update available" + New Version 2.4.12
- Download → staged file `/updates/staged/AIC-ADE-2.4.12-linux-x86_64.AppImage` (182,610,081 bytes = match manifest)
- Install & Restart → app quit (headless restart gagal = environment, bukan bug) → launch manual dengan profile sama
- Verifikasi: sidebar v2.4.12, profile "Update QA" migrated, TIDAK re-onboarding, Settings > Updates = up_to_date (tanpa "New Version" — BUG-01 fix jalan)

## 2. BUG YANG SUDAH FIXED (verified di build 2.4.12)
| Bug | Status | Bukti |
|---|---|---|
| BUG-02 /api/delivery/stats 404 | ✅ FIXED | curl → 200 `{"total_reports":0,...}` |
| BUG-05 crash unpack (Designer/Rex/Review) | ✅ FIXED | worker class runtime test: designer success=True, rex success=True (LLM asli, no crash) |
| BUG-06 qa subprocess "python" | ✅ FIXED | source: sys.executable + shutil.which; qa no-crash di pipeline |
| BUG-08 fresh profile "no project linked" | ✅ FIXED | Default Chat Project auto-created, task TASK-8E20C3DE dibuat |
| BUG-01 Updates display kontradiktif | ✅ FIXED | up_to_date tanpa "New Version" |
| Kelompok 3 worker selection (partial) | ✅ SEBAGIAN | research, database, performance sekarang SPAWN di pipeline (sebelumnya unreachable); verification [qa, performance]; planning ada branch database/nexus/flint |

## 3. BUG YANG MASIH ADA (belum fixed di 2.4.12)
### BUG-07 (CRITICAL): Pipeline TIDAK pernah launch dari chat flow
- Task dibuat dari chat (confirm "yes go ahead") tapi status tetap `created` — 0 pipeline events, 0 leases, 0 dispatch
- Fix GC (task_ref disimpan di _background_tasks) TIDAK menyelesaikan — minimal repro FastAPI membuktikan pola create_task di StreamingResponse BERJALAN, jadi bug app-specific (root cause masih terbuka)
- Impact: fitur misi/pipeline (fitur utama) TIDAK bisa dijalankan dari UI

### BUG-03 (HIGH): Onboarding "Apply to Engine" tidak persist model
- worker_runtime.model_id/provider_id tetap NULL setelah Apply; role sprinter tetap tidak ada
- Impact: engine pakai fallback model acak (WF/wf/sonnet-4.5) bukan model yang dipilih user

### BUG-NEW (HIGH): Chat biasa tidak persist pesan assistant
- /chat/execute → intent=chat → chat_stream_endpoint → stream saja, TIDAK simpan Message assistant ke DB
- Setelah reload, history chat hilang (cuma user message yang ada)
- Regression/eksisting: chat biasa (non-task) tidak pernah tersimpan

### BUG-10 (MEDIUM): Live Company & Office hardcode "15 workers"
- "15 workers" masih hardcode di bundle frontend; backend /dashboard masih report workers:5; status worker statis palsu

### BUG-09 (MEDIUM): Version drift — /health masih 2.4.11
- providers.py:67 dan main.py:145 masih hardcode "2.4.11" padahal build 2.4.12 (config.py sudah dynamic, dua string ini belum)

### BUG-04 (LOW): Palette Toggle Terminal / Toggle File Tree no-op
- Masih dead action, tidak ada panel muncul

### Kelompok 3 GAP (MEDIUM): security tidak spawn untuk task JWT/login
- Task "todo + login JWT" → guardrail security seharusnya trigger (keyword "login"), tapi lease list TIDAK ada security
- Perlu verifikasi: triage selected_workers vs executor phase filter

## 4. CATATAN LINGKUNGAN
- Backend port-hopping: kalau :8000 kepegang backend stale, app pindah ke :8001/:8002 — membingungkan buat QA (2 backend bisa jalan bersamaan)
- Stale backend python sering selamat setelah electron mati (harus kill manual)
- Pipeline direct-run (script): semua worker "failed" karena provider_manager kosong di proses terpisah (lifespan tidak jalan) — BUKAN bug, tapi worker fallback path harus jelas

## 5. SCORING (100 poin)
- ✅ Onboarding + provider + model assign UI: 8/10 (model ga persist -3)
- ✅ Settings (6 tab) + profile + workspace: 9/10
- ✅ Skills CRUD + re-seed: 10/10
- ✅ MCP register/connect/delete: 9/10
- ✅ Observability (4 tab): 9/10
- ✅ Chat build/plan mode (streaming): 7/10 (history ga persist -3)
- ❌ Mission/pipeline dari UI: 2/10 (BUG-07 — fitur utama mati)
- ✅ Worker classes (14) berfungsi dengan LLM: 9/10 (diverifikasi via class test + stress test 2.4.11)
- ⚠️ Worker spawning workflow: 5/10 (selection oke, tapi pipeline ga launch + security gap)
- ✅ Update flow: 10/10
- ❌ Konsistensi data (15 vs 5, version drift): 3/10

**TOTAL: 62/100 — BELUM READY TO USE.** Blocker utama: BUG-07 (pipeline mati dari UI) + BUG-03 (model ga persist) + chat history hilang.

## 6. REKOMENDASI PRIORITAS (untuk opencode round berikutnya)
1. BUG-07: investigasi root cause pipeline background task di app context (minimal repro jalan → cari beda di app: event loop, session, atau SQLite lock)
2. Chat persistence: chat_stream harus persist assistant message (seperti ConversationEngine path)
3. BUG-03: Apply to Engine tulis provider_id+model_id ke worker_runtime (termasuk sprinter)
4. BUG-09: hapus hardcode version di providers.py/main.py
5. BUG-10: Office/Live Company render dari backend (bukan hardcode 15)
6. Security spawn gap: verifikasi guardrail → selected_workers → executor chain

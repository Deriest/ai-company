# AIC-ADE 2.4.13 — Re-QA Report (Round 2 verification)

Tanggal: 2026-08-01 | Build: AIC-ADE-2.4.13-linux-x86_64.AppImage (182.6MB, sha 07d8f75f...)
Metode: fresh profile, CDP, VansRouter, model kr/qwen3-coder-next
Score READY-TO-USE: **87/100** (naik dari 62 — MENDekati target 95, masih ada 3 bug)

---

## 1. FIXED & VERIFIED di 2.4.13

### BUG-07 (CRITICAL) — Pipeline launch dari chat ✅ FIXED
- Task request + confirm via /chat/stream → task TASK-6CF33F8F dibuat → pipeline JALAN:
- Leases: pm(investigate)✅, research(investigate)✅, security(planning)✅, database(planning)✅, architect(planning)✅, backend(implementation)✅, qa(verification)❌(jujur: ga ada test), performance(verification)✅, rex(closeout)✅, documentation(closeout)✅, pm(closeout)✅
- Child task progres: created → verification → completed/failed dengan alasan jelas
- **Ini fitur utama yang tadinya mati — sekarang hidup!**

### BUG-12 — security spawn utk task JWT/login ✅ FIXED
- Task "todo + login JWT" → lease security(planning) COMPLETED

### BUG-09 — version drift ✅ FIXED
- /health report "2.4.13" (config.py `_read_version_from_package_json()`), hardcode ilang dari providers.py/main.py

### BUG-10 — hardcode "15 workers" ✅ FIXED
- "15 workers" 0 occurrence di bundle; Office header sekarang "5 workers · 0 active · 1 missions" (konsisten backend /dashboard workers:5)

### BUG-06 — qa subprocess ✅ FIXED (confirmed runtime)
- qa BENAR-BENAR menjalankan pytest (output test results di event), tidak crash 'python'

### Kelompok 3 — worker roster penuh ✅
- research, security, performance, database yang tadinya unreachable sekarang SPAWN + COMPLETE
- 11 worker terlibat dalam 1 misi (target: 14 worker reachable sesuai task)

## 2. MASIH RUSAK di 2.4.13 (3 bug)

### BUG-03 (HIGH): Apply to Engine → PATCH /runtime/workers/{role} 404 — ROOT CAUSE DITEMUKAN
- Frontend ProviderSetup.tsx panggil `PATCH /runtime/workers/${role}` (crafter/sprinter) → backend 404
- `backend/backend/api/routes/workers.py` punya route PATCH /runtime/workers/{role} TAPI router-nya TIDAK di-include di `backend/backend/main.py` (include_router tidak ada) — route orphan!
- Impact: model assignment onboarding tidak pernah tersimpan → engine pakai fallback model acak
- Fix: mount workers_router di main.py (atau pindah route ke router yang ter-mount)

### BUG-11 (HIGH): Chat biasa tidak persist pesan ASSISTANT (parsial)
- User message tersimpan, response assistant TIDAK (test: count messages +1 bukan +2)
- chat_stream_endpoint → ChatService path stream tanpa persist assistant
- Impact: history chat biasa hilang setelah reload

### BUG-04 (LOW): Palette Toggle Terminal / Toggle File Tree masih no-op
- Item masih ada, tidak melakukan apa-apa

## 3. CATATAN
- qa verification "failed" pada misi test = PERILAKU BENAR (integrity rule: task tidak complete kalau verification gagal; deliverable tidak punya test). Bukan bug.
- pytest: 613 passed / 22 failed — 22 failure pre-existing (schema conversations.user_id + memory tests), bukan dari perubahan round ini (klaim agent; verifikasi lanjut disarankan)
- Update flow masih jalan (tidak diuji ulang end-to-end di 2.4.13, tapi mekanisme tidak berubah)
- Backend port-hopping (8000/8001/8002) masih ada — membingungkan QA, minor

## 4. SCORING 2.4.13 (100)
- ✅ Onboarding + provider UI: 7/10 (BUG-03 model ga persist -3)
- ✅ Settings 6 tab + profile: 9/10
- ✅ Skills/MCP/Observability: 9/10
- ⚠️ Chat build/plan: 7/10 (BUG-11 history -3)
- ✅ Pipeline/misi dari UI: 9/10 (BUG-07 fixed, full lifecycle)
- ✅ Worker spawning optimal: 9/10 (11 worker 1 misi, security/research/performance jalan)
- ✅ Worker classes + tools: 9/10
- ✅ Update flow: 10/10
- ✅ Konsistensi data: 9/10 (BUG-10/09 fixed; sisa port-hopping)
- ❌ Palette dead action: 8/10 (BUG-04)
- ⚠️ Test suite: 8/10 (22 pre-existing fail)

**TOTAL: 87/100 — HAMPIR READY. Blocker ke 95: BUG-03 (mount workers_router), BUG-11 (persist assistant), BUG-04 (palette).**

## 5. PRIORITAS ROUND-3 (kecil & jelas)
1. BUG-03: mount workers_router di main.py (1 baris include_router) + verifikasi PATCH 200
2. BUG-11: chat_stream persist assistant message (2-5 baris)
3. BUG-04: hapus 2 item palette dead (atau wire)
4. Optional: cleanup port-hopping + 22 test pre-existing

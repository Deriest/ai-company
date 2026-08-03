# OpenCode Task: AIC-ADE 2.4.20 → 2.4.21 — Final Polish to 100/100

> Role: Senior Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro, (3) verifikasi runtime. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.21 (package.json + config.py fallback) + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json lengkap. `/health` HARUS 2.4.21. COMMIT + TAG v2.4.21 + PUSH setelah diverifikasi.

## Konteks
- v2.4.20 released (commit 681acb6). QA loop 9 round selesai, 636 test pass. Sisa polish kecil buat 100/100.
- JANGAN regresi BUG-01..20 (tool calling SSE, memory, taste, pipeline, dsb).

# BUG-21 (MEDIUM): latest.json win32 entry stale — masih Setup-2.4.9.exe
- Gejala: `latest.json` platforms.win32 → `AIC-ADE-Setup-2.4.9.exe` (downloadUrl 192.168.2.10:8088), padahal app sudah 2.4.20/2.4.21. Update checker Windows akan menawarkan build 2.4.9 yang lama.
- Fix: kalau build win32 TIDAK dibuat di round ini, HAPUS entry win32 dari latest.json (biar update checker tidak menawarkan versi basi), ATAU set ke versi sekarang kalau ada artifact. Pastikan konsisten dengan linux. Acceptance: `python3 -c "import json; d=json.load(open('latest.json')); print(d['platforms'])"` tidak ada versi basi.

# BUG-22 (MEDIUM): Office header "5 workers" — tidak konsisten dengan Live Company "15 specialized AI workers"
- Gejala: `app/src/renderer/src/components/WorkspaceView.tsx` (halaman Office) fetch `/runtime/workers` (line ~41) yang return 5 row worker_runtime → header "5 workers · 0 active". Live Company tampil "15 specialized AI workers" (dari roster AGENT_REGISTRY), `/dashboard` workers:15. Inkonsisten.
- Fix: Office header count harus total workforce = 15 (dari `/workers` endpoint di `backend/backend/api/routes/workers.py` line ~108 yang return AGENT_REGISTRY, ATAU dari `/dashboard` workers field). Simpan /runtime/workers untuk STATUS active (worker yang beneran jalan), tapi jumlah total worker = roster penuh. Acceptance: Office header "15 workers · N active" konsisten dengan Live Company + dashboard.

# POLISH-1 (LOW): Chat slop flash — teks slop asli ter-stream dulu sebelum rewrite event
- Gejala: chat "halo" → frontend menampilkan "Hi! How can I help you today?" sesaat, baru di-replace "What do you need?" oleh rewrite event. Kurang halus.
- Fix: di jalur plain chat (`backend/conversation/engine.py` atau chat_stream), BUFFER response LLM dulu → scan taste → kalau perlu rewrite → BARU stream konten final ke frontend (tidak ada slop yang tampil sama sekali). Trade-off: latency +1 LLM call hanya saat slop terdeteksi. Pastikan tidak memecah streaming untuk task/plan (jalur lain tetap stream seperti biasa). Acceptance: UI chat tidak pernah menampilkan slop; curl stream plain chat tidak memuat chunk "How can I help you today?" (cuma konten final bersih).

# POLISH-2 (LOW): Palette "Toggle File Tree" masih navigate ke home, bukan toggle panel file tree
- Gejala: `app/src/renderer/src/App.tsx` `onToggleFileTree={() => setView("home")}` — bukan toggle beneran.
- Fix: wire ke state/komponen file tree nyata (WorkspaceView punya file tree? kalau ada, toggle panelnya; kalau tidak ada, buat panel file tree sederhana di WorkspaceView yang bisa di-toggle, ATAU hapus item palette ini). Pilih yang paling masuk akal secara UX. Acceptance: klik item → panel file tree muncul/hilang (bukan cuma pindah view).

# Acceptance Criteria GLOBAL (sebelum build 2.4.21)
1. BUG-21: latest.json tidak ada versi basi.
2. BUG-22: Office "15 workers" konsisten semua view.
3. POLISH-1: chat tidak pernah nampilkan slop (curl + UI bukti).
4. POLISH-2: toggle file tree = toggle beneran (atau item dihapus).
5. Tidak ada regresi BUG-01..20; pytest tetap 636 pass (jangan tambah failure).
6. Build 2.4.21 + /health 2.4.21 + latest.json lengkap.
7. COMMIT + TAG v2.4.21 + PUSH ke origin (pakai GH_TOKEN kalau ada di env, jangan tulis token ke file).
8. Laporkan diff + test + curl/UI bukti.

## Catatan
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya (BUG-19 SSE tool_calls paling penting).
- Backend port bisa 8000/8001/8002 — pakai port sesuai startup log.

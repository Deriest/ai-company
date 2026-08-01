# OpenCode Task: AIC-ADE 2.4.19 → 2.4.20 — Green Test Suite + Release Polish

> Role: Senior Backend Engineer. Work in `/home/tvd/AI-Company`.
> MANDATORY: jangan klaim fix tanpa bukti. Setiap perbaikan WAJIB: (1) diff source, (2) test/repro, (3) verifikasi. JANGAN commit sampai terbukti.
> SETELAH SEMUA TERBUKTI: bump ke 2.4.20 (package.json + config.py fallback) + BUILD (`cd app && npm run build && npx electron-builder --linux AppImage deb`), update latest.json. `/health` HARUS report 2.4.20.

## Konteks
- Stack: Electron+React + FastAPI+SQLite. Gateway VansRouter. Fix round 1-8 SUDAH OK (BUG-01..20, Memory e2e, Taste, tools). JANGAN regresi.
- QA 2.4.19: semua fitur inti verified jalan. Sisa blocker "release ready": pytest 23 failed (schema drift + beberapa functional) + port-hopping.

# TASK A — Test suite hijau (23 failed → target < 5, ideal 0)
Jalankan `cd backend && .venv/bin/python -m pytest 2>&1 | tail -5`. Saat ini: 23 failed, 613 passed. Kelompokkan & perbaiki:

## A1. Schema drift (SEBAGIAN BESAR failures — ~10+ test)
- Error: `sqlite3.OperationalError: table conversations has no column named user_id` dan `no such table: provider_models`.
- Root cause: `backend/backend/models/schema.py` mendefinisikan kolom `user_id` di Conversation + tabel `ProviderModel`, TAPI migration runner (`backend/backend/migrations/runner.py` + migration files) TIDAK menambahkan kolom/tabel ini pada DB yang dibuat dari state lama / test fixtures. Test fixture DB dibuat tanpa migration lengkap.
- Fix: (a) pastikan migration runner meng-add missing columns/tables secara idempotent (ALTER TABLE ADD COLUMN IF NOT EXISTS pattern via inspection, CREATE TABLE IF NOT EXISTS untuk provider_models); (b) pastikan test fixtures (conftest) pakai migration penuh ATAU Base.metadata.create_all konsisten dengan schema.py. JANGAN menghapus user_id dari schema (fitur benar), perbaiki migrasinya.
- Target: semua test yang gagal karena user_id/provider_models jadi hijau.

## A2. Functional test failures (memory_service, automation_service, rag_service)
- `tests/test_memory_service.py` (6 fail): memory store/upsert/forget/compress/stats/scope isolation — assertion mismatch. Cek `backend/backend/services/memory_engine.py` vs test expectation: apakah ini BUG nyata (memory engine salah) atau test stale (harapan lama)? Kalau bug nyata → fix engine; kalau test stale → update test (tapi JANGAN sekadar menyesuaikan test ke perilaku salah — pastikan perilaku benar dulu).
- `tests/test_automation_service.py` (2 fail): hook_delete + trigger_create_and_list assertion — cek logic automation service.
- `tests/test_rag_service.py` (1 fail): test_rag_multiple_documents assertion — cek rag.
- `tests/test_regressions.py::test_timestamp_migration_repairs_legacy_null_messages` (1 fail) — cek timestamp migration.
- Laporkan untuk tiap: bug nyata (fix) ATAU test stale (update test + jelaskan kenapa perilaku sekarang lebih benar).
- Target: 0 failure, ATAU dokumentasi per-test kenapa tidak bisa diperbaiki (dengan bukti).

# TASK B — Port-hopping cleanup (QA annoyance, release polish)
- Gejala: kalau :8000 kepegang backend stale, app pindah ke :8001/:8002 — 2 backend bisa jalan bersamaan; QA sering salah port.
- Fix (backend launcher `backend/backend/launcher/launcher.py`): cek port dengan liveness (health check) SEBELUM pakai — kalau :8000 ada yang serve app lain (bukan backend sendiri), baru naik ke :8001; kalau :8000 kosong, selalu pakai :8000. Tambahkan lock/penanda (file `$AIC_DATA_DIR/backend.port` atau bind-check) supaya 2 instance app tidak saling rebut. Pastikan stale backend lama tidak membingungkan (health endpoint menyertakan data_dir/profile identifier).
- Acceptance: start app fresh → selalu :8000 (atau port yang tercatat konsisten); start instance kedua → pindah port tanpa tabrakan.

# Acceptance Criteria GLOBAL (sebelum build 2.4.20)
1. pytest: 23 failed → 0 (atau < 5 dengan dokumentasi) — JANGAN ada failure baru.
2. Semua fix A1/A2 dijelaskan: bug nyata vs test stale.
3. Port-hopping: launcher konsisten, tidak rebutan.
4. Tidak ada regresi BUG-01..20 (tool calling, memory, taste, pipeline, dsb).
5. Build 2.4.20 + /health 2.4.20 + latest.json lengkap.
6. JANGAN commit sampai semua terbukti; laporkan diff + test + bukti.

## Catatan
- Prioritas: A1 (schema drift) → A2 (functional) → B (port) → build.
- Jangan ubah VansRouter. Jangan regresi fix sebelumnya (terutama BUG-19 SSE tool_calls).
- Backend port bisa 8000/8001/8002 selama TASK B belum kelar.

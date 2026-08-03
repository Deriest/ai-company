# OpenCode Task Round 2: Fix Sisa Bug AIC-ADE 2.4.9 (hasil verifikasi QA ulang)

> Role: senior backend engineer. Repo: /home/tvd/AI-Company.
> **PENTING: Verifikasi QA menunjukkan fix round 1 belum tuntas. Jangan klaim fixed tanpa bukti curl + test.**

## Konteks

Round 1 opencode sudah fix sebagian (BUG-04 bundle ✅). Tapi QA ulang menemukan:

### R1 (REGRESI BARU): chat_service.py line ~246 `base_url.replace("/v1", "")` RUSAK
- **Gejala:** `POST /chat` → 404 `http://127.0.0.1:20129/chat/completions` (tanpa /v1)
- **Root cause:** DB base_url = `http://127.0.0.1:20129/v1` (sudah benar). Fix round 1 menambahkan `base_url.replace("/v1", "")` → menghapus /v1 → provider.chat() kirim ke URL tanpa /v1 → 404
- **Fix:** HAPUS `base_url.replace("/v1", "")` di chat_service.py. ProviderConfig harus terima base_url LENGKAP (dengan /v1). `_get_provider_config` sudah benar menambahkan /v1 — jangan diutak-atik.

### R2: main.py BUG-01 fix pakai `first_model` = combo/Thinker → 404
- **Gejala:** task request `/chat/execute` → 404 "No active credentials for provider: combo"
- **Root cause:** main.py line ~64 `first_model = provider_models[0].model_id` → combo/Thinker (model PERTAMA dari VansRouter, tidak punya credentials aktif). User assign `kr/claude-sonnet-4.5` di worker_runtime.
- **Fix:** models dict harus di-resolve dari `worker_runtime` table (role → model_id yang user assign), bukan first_model dari provider_models. Kalau worker_runtime kosong, fallback ke model yang VALID untuk gateway (bukan combo/* — cek `GET /models` dulu).

### R3: Plan mode (worker_role=planner) masih 404
- Sama dengan R2: pakai model default combo/Thinker. Setelah R2 fix, planner harusnya pakai worker_runtime.planner.model_id.

### R4: ConversationEngine TIDAK dapat token budget
- **Gejala:** conversation 160k via `/chat/execute` non-task (lewat ConversationEngine) → kirim penuh → response kosong (cost ter-charge)
- **Root cause:** fix round 1 hanya di `chat_service.chat_stream` (line ~476-511), TAPI `backend/backend/services/conversation_engine.py` TIDAK diubah (grep context_builder = 0)
- **Fix:** tambah token budget di ConversationEngine (pakai context_builder/get_context_policy + estimate_tokens + truncation seperti di chat_stream), ATAU alihkan jalur non-task ke chat_service.chat_stream yang sudah punya budget.

## Cara Repro (dari backend yang jalan di port 8000)

```bash
DB=/tmp/aic-249-verify-profile/aic-ade/aic.db
CID=$(sqlite3 "$DB" "SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1;")

# R1: /chat non-streaming
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"conversation_id":"'"$CID"'","messages":[{"role":"user","content":"Hi"}],"worker_role":"thinker"}'
# → 500 404 tanpa /v1

# R2: task request
curl -s -N -X POST http://127.0.0.1:8000/chat/execute -H "Content-Type: application/json" \
  -d '{"conversation_id":"'"$CID"'","messages":[{"role":"user","content":"Build a todo app"}],"worker_role":"thinker"}'
# → 404 combo/Thinker

# R3: plan mode
curl -s -N -X POST http://127.0.0.1:8000/chat/execute -H "Content-Type: application/json" \
  -d '{"conversation_id":"'"$CID"'","messages":[{"role":"user","content":"Plan a weather app"}],"worker_role":"planner"}'
# → 404
```

## Acceptance Criteria

1. `POST /chat` → 200 (URL harus `:20129/v1/chat/completions`)
2. Task request + thinker → chunks keluar (model kr/claude-sonnet-4.5 dari worker_runtime)
3. Plan mode + planner → chunks keluar
4. Conversation 160k via /chat/execute non-task → ada truncation warning ATAU response OK (bukan kirim penuh lalu kosong)
5. `cd backend && python -m pytest tests/ -x -q` → hijau (test baru untuk: URL /v1, worker_runtime model resolution, ConversationEngine budget)
6. JANGAN commit sampai semua bukti curl + test ada. Laporkan diff + output.

## Catatan
- Provider test: `kr/claude-sonnet-4.5` @ `http://127.0.0.1:20129/v1` (VansRouter). Model combo/* TIDAK punya credentials — JANGAN pakai sebagai default.
- Jangan ubah VansRouter. Fix di sisi AIC-ADE backend.
- Backend dev: `cd backend && <python-linux>/bin/python -m uvicorn backend.main:app --port 8000`

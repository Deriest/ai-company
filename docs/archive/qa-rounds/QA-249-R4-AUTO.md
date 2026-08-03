# OpenCode Task Round 4: Auto-Detect Context Size (bukan hardcode) + Hard Guard + Build 2.4.10

> Role: senior backend engineer. Repo: /home/tvd/AI-Company.
> **PENTING: User requirement — context size harus AUTO-DETECTION per model, JANGAN hardcode 200k hanya untuk kr/claude-sonnet-4.5.**

## Konteks & Keputusan QA

R3 sudah fix R4 dengan:
- Migration 013 seed `kr/claude-sonnet-4.5` context_window=200000 (HARDCORE per model — ini yang harus diganti)
- chat_service policy pakai context_window dari DB

**QA menemukan:**
1. Migration 013 hardcode `provider_id='vansrouter'` — TIDAK match UUID provider nyata → seed tidak terpakai
2. VansRouter `/v1/models` TIDAK menyediakan context_window metadata — cuma `{id, owned_by, capabilities{thinking,agentic}}`
3. `provider_client.py` line 32-39 SUDAH punya heuristic name-based:
   ```python
   if is_claude and "opus": context_window = 200000
   elif is_claude: context_window = 200000
   elif is_gpt and "4.1": context_window = 1000000
   elif is_gpt: context_window = 128000
   elif is_gemini: context_window = 1000000
   elif is_ds: context_window = 64000
   ```
   → Tapi heuristic ini TIDAK selalu tersimpan ke `provider_models.context_window` saat fetch-models!

## Requirement (user eksplisit)

"pakai model context <200k tetap ada auto detection untuk context size — jadi ga di hardcode per model"

Artinya:
1. **AUTO-DETECTION generik** untuk SEMUA model saat fetch-models — pakai name-based heuristic (claude→200k, gpt-4.1→1M, gpt→128k, gemini→1M, deepseek→64k, unknown→conservative 64k). Bukan cuma 1 model.
2. **HAPUS/neutralkan migration 013** (hardcode per-model) — ganti dengan auto-detection di `fetch-models` route + fallback heuristic di chat_service.
3. Model apa pun (context <200k atau >200k) harus dapat `context_window` yang benar dari auto-detection.

## Task

### 1. Hapus migration 013 hardcode
- `backend/backend/migrations/runner.py` migration 013 `seed_kr_claude_sonnet_model` — HAPUS atau ganti jadi no-op/auto (karena sekarang auto-detect saat fetch).

### 2. Auto-detect context_window saat fetch-models
- File: `backend/backend/api/routes/providers.py` (fetch-models) + `backend/backend/services/provider_client.py`
- Saat `fetch-models` dipanggil, untuk SETIAP model dari `/v1/models`:
  - Gunakan heuristic name-based (yang sudah ada di provider_client.py) untuk set `context_window`
  - Simpan ke `provider_models.context_window`
  - Model tanpa match → `context_window = 64000` (conservative) ATAU NULL (biar fallback)
- Pastikan `max_output_tokens` juga di-set (claude→8192, dll)

### 3. Fallback di chat_service tetap konservatif + warning
- `backend/backend/services/chat_service.py` line ~481: kalau context_window tidak ditemukan → fallback `get_context_policy("crafter")` (60k) + LOG WARNING yang jelas "context window unknown for model X, using conservative policy"

### 4. Hard guard over-capacity (kasus 240k masih kosong)
- Di `chat_service.chat_stream()` + `conversation/engine.py`:
  - Kalau `estimated_tokens > context_window - response_reserve` → **JANGAN kirim** → yield error eksplisit:
    `{"type": "error", "error": "Conversation context (X tokens) exceeds model capacity (Y tokens). Start a new session or ask for a summary."}`
  - Ini mencegah: request > capacity → upstream tolak → kosong diam + cost terbuang
- Juga truncate dengan policy.max_tokens SEBELUM kirim (sudah ada — pastikan berfungsi di semua path: /chat, /chat/execute, /chat/stream)

### 5. Unit test baru
- `backend/tests/`: 
  - test auto-detect context_window (claude→200k, gpt-4.1→1M, gpt→128k, gemini→1M, ds→64k, unknown→64k)
  - test hard guard: conversation 240k → error eksplisit, TIDAK ada request ke upstream
  - test migration 013 dihapus → tidak error

## Acceptance Criteria

1. Fetch-models untuk provider apa pun → `provider_models.context_window` terisi untuk SEMUA model (bukan cuma kr/claude-sonnet-4.5)
2. Model context <200k (misal deepseek 64k) → policy pakai 64k → truncate sesuai
3. Conversation 240k (>200k) → **error eksplisit "exceeds capacity"**, BUKAN kosong diam, BUKAN cost terbuang
4. Conversation 160k → tetap berhasil (chunk keluar) — TIDAK regresi
5. Migration 013 tidak lagi hardcode provider_id='vansrouter'
6. `cd backend && python -m pytest tests/ -x -q` → hijau
7. JANGAN commit sampai bukti lengkap. Laporkan: diff + test output + curl proof.

## Cara Verifikasi

```bash
# 1. Fetch models → cek context_window semua model
curl -s -X POST http://127.0.0.1:8000/providers/<PROV>/fetch-models -H "Content-Type: application/json" -d '{}'
sqlite3 <DB>/aic.db "SELECT model_id, context_window FROM provider_models ORDER BY context_window DESC LIMIT 10;"

# 2. Conversation 240k → error eksplisit
# (isi 60 msg x 16KB, lalu chat)

# 3. Conversation 160k → chunk keluar (regresi check)
```

## Catatan
- JANGAN ubah VansRouter. Fix di sisi AIC-ADE.
- JANGAN hardcode 200k khusus satu model — auto-detect untuk semua.
- Setelah semua pass → update version ke 2.4.10 di `backend/backend/main.py` + `app/package.json` → build AppImage: `cd app && npx electron-builder --linux AppImage`

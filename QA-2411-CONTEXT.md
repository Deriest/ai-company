# OpenCode Task: Implement Auto-Detect Context Window ala Hermes (probe + cache + catalog)

> Role: senior backend engineer. Repo: /home/tvd/AI-Company.
> **TUJUAN: AIC-ADE harus bisa auto-detect context window seakurat Hermes Agent — dengan probe langsung ke endpoint, persistent cache per model@base_url, hardcoded catalog detail, dan config override manual. Setelah implementasi: build + test end-to-end sampai SEMUA worker (thinker/crafter/sprinter/planner/reviewer/manager) bisa dipakai.**

## Konteks

AIC-ADE = FastAPI backend + React. Backend Python di `backend/`. Saat ini auto-detect context cuma pakai **pattern family** di `backend/backend/services/provider_client.py` `infer_capabilities()` — bagus tapi kurang akurat untuk model tak dikenal / endpoint spesifik.

Hermes Agent (referensi, sudah terbukti akurat) memakai waterfall di `agent/model_metadata.py`:
1. Config override (user set manual)
2. Persistent cache (`context_length_cache.yaml`, key `model@base_url`)
3. **Probe endpoint** `GET {base_url}/models` → parse `context_length` / `context_window` / `max_model_len` (banyak server expose: vLLM, LM Studio, LiteLLM, Ollama-compat, dll)
4. Local server probe (Ollama `/api/show`, vLLM/LM Studio query)
5. Provider-aware lookups (models.dev, OpenRouter)
6. Hardcoded catalog (DEFAULT_CONTEXT_LENGTHS — ~60 entries detail)
7. Fallback 256K

**Insight kunci:** context tergantung ENDPOINT (bukan cuma nama model) — `gpt-5.6` = 1.05M di OpenAI direct tapi 400k di VansRouter. Cache key harus `model@base_url`.

## Task (implementasi lengkap & detail)

### 1. Probe endpoint di `backend/backend/services/provider_client.py`
- Tambah method `fetch_models_with_context()`: panggil `GET {base_url}/models` (atau `/v1/models`), lalu untuk SETIAP model parse context dari berbagai key:
  - `context_length`, `context_window`, `contextWindow`, `max_model_len`, `max_context_length`, `max_tokens` (hati-hati bedakan dengan max output), `limit.context`
  - Rekursif cari di nested dict (mirip Hermes `_iter_nested_dicts`)
  - Kalau response punya `capabilities.contextWindow` → pakai itu
- Simpan hasil probe ke `provider_models.context_window` — **probe MENANG atas pattern** (endpoint lebih tahu)
- Kalau probe gagal / model tidak ada di response → fallback ke pattern

### 2. Persistent cache per `model@base_url` (di DB AIC-ADE)
- Tambah tabel `model_context_cache` (atau kolom di provider_models):
  - `model_id`, `base_url`, `context_window`, `source` (probe/catalog/models_dev/pattern), `updated_at`
  - Key unik: `(model_id, base_url)`
- Saat fetch-models: cek cache dulu → kalau ada dan fresh (TTL 24h) → pakai; kalau tidak → probe → simpan
- Saat resolve context di `chat_service.py` / `context_builder.py` `get_model_context_window()`: cek cache dulu sebelum query provider_models

### 3. Hardcoded catalog detail (mirror Hermes DEFAULT_CONTEXT_LENGTHS)
- Buat `backend/backend/services/model_catalog.py` dengan dict `MODEL_CONTEXT_CATALOG` (~60+ entries), pakai nilai yang sama dengan Hermes:
  ```python
  MODEL_CONTEXT_CATALOG = {
      "claude-fable-5": 1000000, "claude-opus-4-8": 1000000, "claude-opus-4-7": 1000000,
      "claude-opus-4-6": 1000000, "claude-sonnet-4-6": 1000000,
      "claude": 200000,
      "gpt-5.6-luna": 1050000, "gpt-5.6-terra": 1050000, "gpt-5.6-sol": 1050000,
      "gpt-5.5": 1050000, "gpt-5.4": 1050000, "gpt-5.4-mini": 400000, "gpt-5.4-nano": 400000,
      "gpt-5": 400000, "gpt-4.1": 1047576, "gpt-4": 128000,
      "gemini": 1048576, "gemma-4": 256000, "gemma-3": 131072, "gemma": 8192,
      "deepseek-v4-pro": 1000000, "deepseek-v4-flash": 1000000, "deepseek-chat": 1000000,
      "deepseek-reasoner": 1000000, "deepseek": 128000,
      "llama": 131072,
      "qwen3.6-plus": 1048576, "qwen3-coder-plus": 1000000, "qwen3-coder": 262144, "qwen": 131072,
      "minimax-m3": 1000000, "minimax": 204800,
      "glm-5.2": 1048576, "glm": 202752,
      "grok-4.5": 500000, "grok-4.3": 1000000, "grok-4": 256000, "grok-3": 131072, "grok": 131072,
      "kimi": 262144,
      "nemotron": 131072,
      "mimo-v2.5-pro": 1048576, "mimo-v2.5": 1048576, "mimo-v2-omni": 262144, "mimo-v2-flash": 262144,
  }
  ```
- Fungsi `lookup_catalog(model_id)`: normalize dash↔dot, strip vendor prefix, longest-key-first substring match (mirror Hermes)
- Catalog ini dipakai SEBELUM pattern family, SETELAH probe & cache

### 4. Config override manual di UI
- Settings > Providers > per-model: tambah field "Context Window (opsional)" — kalau user isi, PAKAI itu (override semua layer)
- Backend: `ProviderModel.context_window` dari UI override > probe > cache > catalog > pattern

### 5. Waterfall final di `get_model_context_window()` (context_builder.py) & `infer_capabilities()`
```
1. User override (dari UI/DB ProviderModel.context_window yang user set manual) — kalau ada
2. Probe result (dari fetch-models, tersimpan di provider_models.context_window dengan source=probe)
3. Persistent cache model@base_url (kalau probe tidak tersimpan)
4. models.dev lookup (bundled backend/data/models_dev.json) — untuk model tak dikenal
5. Hardcoded catalog (MODEL_CONTEXT_CATALOG)
6. Pattern family (infer_capabilities existing)
7. Fallback 256K (ganti dari 8192 → 256000, mirror Hermes)
```
- `infer_capabilities` di `provider_client.py` harus MENERIMA hasil probe/catalog sebagai prioritas — restruktur supaya clear.

### 6. Unit tests (backend/tests/)
- test probe parse (nested context_length, capabilities.contextWindow, max_model_len)
- test cache model@base_url (key, TTL, persist)
- test catalog lookup (longest-first, dash↔dot, vendor strip)
- test waterfall order (override > probe > cache > models.dev > catalog > pattern > fallback)
- `cd backend && python -m pytest tests/ -x -q` → hijau

## Build & Test End-to-End (WAJIB setelah implementasi)

1. **Version bump**: `backend/backend/main.py` → `2.4.11`; `app/package.json` → `2.4.11`
2. **Build**: `cd app && npx electron-builder --linux AppImage`
3. **Test end-to-end** (jalankan AppImage baru, setup provider VansRouter `http://127.0.0.1:20129/v1`):
   - Fetch models → cek `provider_models.context_window` untuk SEMUA model akurat (bandingkan dengan data verified: deepseek-v4=1M, glm-5.2=200k di VansRouter, mimo-v2.5=1M, gpt-5.6=400k di VansRouter, claude-sonnet-4.5=200k, qwen3-coder-next=1M)
   - **Assign engine untuk SEMUA worker**: thinker, crafter, sprinter, planner, reviewer, manager → model `kr/qwen3-coder-next`
   - **Chat test per worker** (curl /chat/execute + worker_role=X):
     - thinker: "Design a REST API for a todo app" → chunks keluar
     - crafter: "Write a Python function to parse CSV" → chunks keluar
     - sprinter: "Write a quick bash script to list files" → chunks keluar
     - planner: "Plan a weather app architecture" → chunks keluar
     - reviewer: "Review this code for bugs: def add(a,b): return a-b" → chunks keluar
     - manager: "Break this task into steps: build a blog" → chunks keluar
   - **Semua worker harus BALAS (chunks/content keluar), tidak ada "No LLM provider configured", tidak ada 404/500**
   - Report: tabel hasil per worker + bukti curl

## Acceptance Criteria
1. Fetch-models → context_window akurat untuk semua model (probe > catalog)
2. Cache model@base_url tersimpan & dipakai
3. Catalog lookup bekerja (longest-first, dash↔dot)
4. User override manual di UI → menang
5. Semua 6 worker (thinker/crafter/sprinter/planner/reviewer/manager) chat → chunks keluar
6. Simple chat + task → OK
7. pytest hijau
8. AppImage 2.4.11 built
9. **JANGAN commit** sampai semua bukti lengkap (diff + test + curl per worker). Laporkan: implementasi detail + hasil test per worker + bukti.

## Catatan
- JANGAN ubah VansRouter
- models.dev.json sudah ada di `backend/data/models_dev.json` (3.5MB, 176 providers) — pakai untuk layer 4
- Provider test: `kr/qwen3-coder-next` @ `http://127.0.0.1:20129/v1` (VansRouter, REQUIRE_API_KEY=false)
- Backend dev: `cd backend && <python-linux>/bin/python -m uvicorn backend.main:app --port 8000`

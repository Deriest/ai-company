# OpenCode Task: AIC-ADE v2.4.40 — Fix backend API key decryption

## Bug
Chat API returns `"Illegal header value b'Bearer '"` — Authorization header is empty.
Provider API key is stored encrypted in DB (`gAAAAA...`), but `decrypt()` returns empty string.

## Investigation needed
1. Trace the code path: `chat_service.py` `_get_provider_config` → `decrypt_api_key(p.api_key)` → `crypto.py` `decrypt()`
2. Check why `decrypt()` returns empty despite the encrypted value being valid
3. Check the `_register_provider_live` function in `providers.py` — it also calls `decrypt()` and works for health check, but fails for chat
4. Check if the `provider_manager` singleton has the correct API key registered
5. The `AgentRunner` uses `provider_manager.get_active()` — check if the API key is available there

## Files to check
- `backend/backend/services/crypto.py` — encrypt/decrypt functions
- `backend/backend/services/chat_service.py` — `_get_provider_config`, `chat_completion`, `chat_stream`
- `backend/backend/api/routes/providers.py` — `_register_provider_live`
- `backend/backend/llm/provider.py` — `LLMProvider`, `provider_manager`, `aregister`
- `backend/backend/api/routes/chat.py` — `/chat/execute`, `/chat/stream`

## Fix
Ensure the API key is properly decrypted and passed to the LLM client for chat requests.
The `decrypt()` function in `crypto.py` should return the plaintext API key.

## Model config
After fixing the API key, configure the engine to use:
- Thinker: `9r/qd/qmodel_preview`
- Crafter: `9r/qd/qmodel_preview`
- Sprinter: `9r/qd/qmodel_preview`

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.41
- Copy to app/release/ + SHA256SUMS

## QA after build
- Full QA: Office, Command Center, Live Company, Skills, Settings
- Chat: send message → verify response
- Token usage: verify context bar shows accurate token count with token_count from backend
- Persistence: close app → reopen → check session & messages survive
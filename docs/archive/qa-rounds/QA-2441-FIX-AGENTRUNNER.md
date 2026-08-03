# OpenCode Task: AIC-ADE v2.4.41 — Fix AgentRunner provider selection

## Bug
`chat/execute` still returns "Illegal header value b'Bearer '" because `AgentRunner` uses `provider_manager.get_active()` which returns the FIRST registered provider (VansRouter with empty api_key), not the AIC provider.

## Fix needed
In `backend/services/agent_runner.py` line ~138:
- Instead of `provider = provider_manager.get_active()`, find the provider with a valid API key
- Or: iterate through providers and pick the first one with a non-empty API key
- Or: use the same logic from `_get_provider_config` (order by connected, last_refresh_at)

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.42
- Copy to app/release/ + SHA256SUMS
# OpenCode Task: AIC-ADE v2.4.42 — Fix ToolAwareChatService provider selection

## Bug
Chat (non-task) masih gagal karena `ToolAwareChatService` di `tool_chat_service.py` line 142 uses `provider_manager.get_active()` (returns first registered provider, not the one with valid key).

## Fix needed
In `backend/backend/services/tool_chat_service.py`:
- Change `provider_manager.get_active()` → `provider_manager.get_active_with_key()` (same fix as agent_runner.py)
- Or: use the same fallback logic as `_get_provider_config` in `chat_service.py` (order by connected, skip keyless)

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.43
- Copy to app/release/ + SHA256SUMS
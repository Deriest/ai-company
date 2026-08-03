# OpenCode Task: AIC-ADE v2.4.38 → v2.4.39 — Fix remaining bugs

## Approach
- For EACH bug: INVESTIGATE root cause first, THEN fix
- Report root cause + fix in summary
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT modify anything outside these bugs

## Bug 1 — Token usage: token_count is null from backend
File: `app/src/renderer/src/components/ChatView.tsx` (context bar ~line 1093)

The `token_count` field on messages is `null` because the backend doesn't populate it.
Fix: estimate tokens locally from message content length.
- `Math.ceil(content.length / 3.5)` per message + 50 overhead per message + 500 system prompt
- Show estimated token count in context bar instead of `messages.length`
- If total is 0, show `?`

## Bug 2 — Send button tidak jadi stop button saat streaming
File: `app/src/renderer/src/components/ChatView.tsx` (send button ~line 780)

When `sending` is true, the send button should change to a stop button.
- Show stop icon (■ square) instead of send icon (paper plane)
- On click during sending: abort the request using AbortController
- `chatApi.executeAgent` already returns an abort function — use it

## Bug 3 — Windows icon: copy user's .ico file
File: `app/build/icon.ico` and `app/build/icon.png`

User provided correct `.ico` at `/home/tvd/aic-ade-logo.ico` (6 sizes: 16, 32, 48, 64, 128, 256).
- Copy `/home/tvd/aic-ade-logo.ico` → `app/build/icon.ico`
- Generate `app/build/icon.png` from it (512x512, optimized)

## Build (after all bugs fixed)
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.39
- Copy to app/release/ + SHA256SUMS
# OpenCode Task: AIC-ADE — Fix 3 UI bugs

## Approach
- For EACH bug: INVESTIGATE root cause first, THEN fix
- Report root cause + fix in summary
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT modify anything outside these 3 bugs

## Bug 1 — Context usage: show token count, not message count
File: `app/src/renderer/src/components/ChatView.tsx` (~line 1093-1098)

Currently shows `messages.length / contextWindow` (e.g. `4 / 1,048,576`).
MessageRecord already has `token_count?: number | null` field from the API.

Fix: change `messages.length` to `messages.reduce((sum, m) => sum + (m.token_count || 0), 0)`.
If total is 0, show `?` as fallback.
Update progress bar width to use token_count.

## Bug 2 — Composer layout: right side empty, context position wrong
File: `app/src/renderer/src/components/ChatView.tsx` (composer area ~line 1040-1100)

Desired layout (single row, horizontal):
[BUILD | PLAN] [Context 4 / 1,048,576] [████████ progress bar ████████] [THINKER: AIC ▼ | ollama/minimax-m3 ▼] [CRAFTER: AIC ▼ | ollama/minimax-m3 ▼] [SPRINTER: AIC ▼ | ollama/minimax-m3 ▼] [Fetch] [Compact]
[textarea]

Semua dalam SATU baris horizontal. Jangan split jadi 2 baris.

## Bug 3 — Context bar styling
File: `app/src/renderer/src/components/ChatView.tsx` (~line 1092-1098)

- "Context" label should be blue/primary color (same as BUILD active state)
- Progress bar: green (< 50%), yellow (50-80%), red (> 80%)
- Use Tailwind classes: bg-success, bg-warning, bg-destructive based on percentage

## Bug 4 — Send button: also acts as stop/cancel during generation
File: `app/src/renderer/src/components/ChatView.tsx` (send button area)

When AI is generating a response (streaming), the send button should become a stop button.
Clicking it cancels the ongoing generation.

- Check `sending` state: if true, show stop icon (square) instead of send icon
- On click during sending: abort the fetch/stream request
- Use AbortController to cancel the API call

## Bug 5 — Windows icon: shortcut/search bar icon bukan logo AIC ADE
File: `app/build/icon.ico` and `app/build/icon.png`

User sudah menyediakan file `.ico` yang benar di `/home/tvd/aic-ade-logo.ico` (6 ukuran: 16, 32, 48, 64, 128, 256).

Fix:
1. Copy `/home/tvd/aic-ade-logo.ico` → `app/build/icon.ico`
2. Generate `app/build/icon.png` dari file tersebut (512x512, optimized)

## Build (after all bugs fixed)
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.38
- Copy to app/release/ + SHA256SUMS
# OpenCode Task: AIC-ADE — Fix 4 UI bugs

## General approach
- For EACH bug: INVESTIGATE root cause first, THEN fix
- Do NOT guess or apply superficial fixes
- Report root cause + fix in the summary
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT modify anything outside the scope of these 4 bugs

## Bug #1 — Command Center UI cut off (70% visible)
- At normal window size (not resized), the Command Center content doesn't fit in the viewport
- Chat area, action bar, and composer are partially cut off
- The bottom of the page is not visible
- File: `app/src/renderer/src/components/ChatView.tsx`
- Fix: ensure the chat area + composer fit within the viewport without overflow
- The composer area (model selectors, textarea, buttons) should be compact
- The chat messages area should scroll independently
- Use flex layout with `min-h-0`, `overflow-y-auto`, `flex-1`, `shrink-0`

## Bug #2 — Window resize/maximize layout breaks
- When the window is resized or maximized, the layout breaks
- Elements overlap, disappear, or misalign
- File: `app/src/renderer/src/components/AppShell.tsx` and page components
- Fix: ensure the layout is responsive at any window size
- Use relative units, flex wrap, overflow handling
- Test at 1024x768, 1440x900, and maximized

## Bug #3 — build / plan buttons should be UPPERCASE
- File: `app/src/renderer/src/components/ChatView.tsx`
- Change the "build" and "plan" buttons to show "BUILD" and "PLAN" (uppercase)
- Remove any `textTransform: 'lowercase'` style
- Add `textTransform: 'uppercase'` or `uppercase` class

## Bug #4 — Chat not responding (regression)
- After recent changes, the Command Center chat no longer responds
- User sends a message → no response or response disappears
- Investigate: check `handleSend`, `chatApi.executeAgent`, streaming response, state management
- Root cause could be: broken state, removed functionality, or API call issue
- File: `app/src/renderer/src/components/ChatView.tsx`

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.37
- Copy to app/release/ + SHA256SUMS

## DO NOT
- Do NOT change anything outside these 4 bugs
- Do NOT modify provider persistence, model isolation, icons, or any other feature
- Do NOT add new features (no compact button, no fetch models, no extra UI elements)
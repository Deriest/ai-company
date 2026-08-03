# OpenCode Task: AIC-ADE v2.4.29 — Remaining UI fixes

## Context
- Base version: 2.4.28 (built, has custom frameless title bar ✅)
- Model: use whatever is already configured in opencode (do not override)
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Items to fix (in order)

### 1. Remove Observability page
The user said Observability is redundant because Live Company already shows usage/cost/tokens.
- Remove sidebar entry in `app/src/renderer/src/components/AppShell.tsx` (line ~31: `{ id: "observability", ... }`)
- Remove import + route case in `app/src/renderer/src/App.tsx` (lines ~17, 161-162)
- Remove command palette entry in `app/src/renderer/src/components/CommandPalette.tsx` (line ~26)
- Keep the file `ObservabilityView.tsx` (just don't route to it)

### 2. Fix hardcoded context size
In `app/src/renderer/src/components/ChatView.tsx` line ~745:
- Change `total msg: {messages.length.toLocaleString()} / 1,000,000` to be dynamic
- If the model's max context is available from the provider config, use it
- Otherwise keep a reasonable default (1,000,000) but note it should be dynamic

### 3. Polish Office UI
The user said the Office page looks "jelek" (ugly). Check the current layout and improve:
- Better spacing between worker avatars
- Ensure the floor plan canvas fits well
- Clean up any visual clutter
- File: `app/src/renderer/src/components/WorkspaceView.tsx` and `VirtualOfficeCanvas.tsx`

### 4. Skills card bottom truncation
The Security Audit card at the bottom of Skills page is still slightly cut off (the "built-in" tag is partially hidden). The page now scrolls properly, but the card spacing should be more compact.
- Reduce padding/margins further if needed
- File: `app/src/renderer/src/components/SkillsView.tsx`

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.29
- Copy latest.json to app/release/ + SHA256SUMS

## Verification
- Launch the built app, onboard, take screenshots of Office, Live Company, Skills, Command Center
- Verify all pages look correct and no overlapped elements
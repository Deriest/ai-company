# AIC-ADE v2.4.25 — Round 15: Fix card headers + Office UI

## Correction
The `[LOGO] AICompany ADE + - [ ] X` format was meant for the **WINDOW TITLE BAR** only (like a standard Windows app: logo+name on left, minimize/maximize/close on right). It was NOT meant for individual cards. The cards should NOT have this header.

## Fixes

### 1. Remove card headers from ALL cards
In `app/src/renderer/src/components/LiveCompanyView.tsx`:
- REMOVE the `AICompany ADE + − □ ×` header bar from each worker card (the `<div className="flex items-center justify-between border-b border-border/60 pb-2...">` block)
- Keep the original card content (avatar, name, role, status, tags)

In `app/src/renderer/src/components/SkillsView.tsx`:
- REMOVE the `AICompany ADE + − □ ×` header bar from each skill card
- Keep the original skill card content (name, description, tags, built-in badge)

### 2. Optimize Office UI
- The Office page layout needs refinement. Check the current layout and fix any visual issues (alignment, spacing, overflow)
- The floor plan canvas should fit well within the viewport without making the UI look "jelek" (ugly)
- File: `app/src/renderer/src/components/WorkspaceView.tsx` or `VirtualOfficeCanvas.tsx`

### 3. Title bar is already correct
- `main.ts:354` → `title: "AICompany ADE"` ✅ (already set)
- `index.html` → `<title>AICompany ADE</title>` ✅ (already set)
- Window controls (minimize/maximize/close) are handled by Electron/OS — no app code needed

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.26
- Copy to app/release/

DO NOT use subagent/parallel fixer.
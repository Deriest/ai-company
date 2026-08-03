# AIC-ADE v2.4.23 — Round 13: Fix Office & Live Company Overflow

**Status:** 2 of 4 fixes confirmed working (HTML title ✅, Skills text truncation ✅). Office bottom buttons + right panel and Live Company bottom cards still cut off.

## Root Cause
The office floor canvas and the worker cards grid overflow the viewport height. The content is taller than the available space, causing bottom buttons/cards to be clipped by the window edge.

## Fix (specific CSS/JS)

### 1. Office page (`WorkspaceView.tsx` or `VirtualOfficeCanvas.tsx`)
- The main container needs `height: 100%` or `flex: 1` with `overflow: hidden`
- The SVG/Canvas floor plan should SHRINK to fit the available height (not overflow)
- The bottom action buttons ("Start a Mission", "View Workforce", "Command Palette") must be positioned at the bottom of the viewport, not below it
- Check if the floor plan SVG has a fixed height that's too large — use `viewBox` with responsive sizing or `max-height: 60vh` with `overflow: hidden`

### 2. Live Company page (`LiveCompanyView.tsx`)
- The worker cards grid needs to be scrollable OR the cards need to be smaller
- Add `overflow-y: auto` to the worker grid container with a `max-height` that fits within the viewport
- Or reduce card size (padding, font size) to fit all 15 workers + 4 departments in the viewport
- Current issue: Engineering (5 workers) overflows, Platform (4 workers) is completely hidden

### 3. Both pages
- Verify the app container uses `flex: 1` on the main content area with proper flex layout
- The sidebar + header + content should stack vertically with `flex: 1` on the content area
- Content should NOT use fixed heights that exceed viewport

## Build Instructions
After fixing:
1. `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
2. Update latest.json (version 2.4.24, sha256, size for linux + win32)
3. Copy latest.json to app/release/ + update SHA256SUMS

## Verification
- Launch the built app (Xvfb :99, CDP port 9238)
- Navigate to Office: bottom buttons should be fully visible
- Navigate to Live Company: all 15 workers across 4 departments should be visible (no scroll needed)
- Take screenshots and verify with vision analysis

DO NOT use subagent/parallel fixer.
# AIC-ADE v2.4.26 — Round 16: Skills page footer overlap fix

## Problem
The Skills Registry page has 7 skill cards grouped by category. The last card (Security Audit) is cut off by the bottom of the viewport — the card description, tags, and bottom edge are not visible.

## Fix
In `app/src/renderer/src/components/SkillsView.tsx`:
- The main content container needs `overflow-y: auto` with a `max-height` that fits within the viewport
- Or add `flex-1` and `min-h-0` to the container so it scrolls properly
- The goal: ALL 7 skill cards must be visible OR the container must scroll properly

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.27
- Copy to app/release/

DO NOT use subagent/parallel fixer.
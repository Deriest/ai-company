# AIC-ADE v2.4.27 — Round 17: Skills page overflow fix (take 2)

## Problem
The Skills page container doesn't respect viewport height. The `min-h-full` doesn't work because the parent doesn't have a fixed height. Need to use `h-full` with `flex flex-col` on the outer container.

## Fix
In `app/src/renderer/src/components/SkillsView.tsx`:
- Change outer `<div className="min-h-full">` to `<div className="flex h-full flex-col min-h-0">`
- The inner content div can keep `overflow-y-auto max-h-[calc(100vh-8rem)]` for scroll

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.28
- Copy to app/release/

DO NOT use subagent/parallel fixer.
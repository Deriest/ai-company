# OpenCode Task: AIC-ADE v2.4.36 → v2.4.37 — BUILD | PLAN uppercase + any remaining fixes

## Context
- Version: 2.4.36
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Bug: BUILD | PLAN should be UPPERCASE
File: `app/src/renderer/src/components/ChatView.tsx`

The "build" and "plan" buttons currently show as lowercase. User wants them UPPERCASE ("BUILD" and "PLAN") for clarity.

Current code has `lowercase` class and `style={{ textTransform: 'lowercase' }}` — REMOVE these and add `uppercase` class instead.

Search for:
- `lowercase` in the build/plan button className
- `textTransform: 'lowercase'` inline style

Replace with `uppercase` class.

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.37
- Copy to app/release/ + SHA256SUMS
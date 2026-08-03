# OpenCode Task: AIC-ADE v2.4.33 → v2.4.34 — Fix remaining bug

## Context
- Version: 2.4.33 (built, most bugs fixed)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Remaining bug: Model selector not showing in empty state
File: `app/src/renderer/src/components/ChatView.tsx`

The THINKER/CRAFTER/SPRINTER model selectors only appear after a session is created. They should appear in the empty state (before any session exists) when providers are configured.

The current condition at line 1004 is:
`{engineProviders.length > 0 && (`

But `engineProviders` is populated by `loadEngineConfig` which fetches from the API. If the fetch fails or returns empty on initial load, the selectors don't appear.

Fix: ensure the model selectors appear in the empty state by:
1. Making `engineProviders` populate correctly on mount
2. If providers exist in the backend, show the selectors even without a session
3. If no providers exist, show a message or hide the selectors

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.34
- Copy to app/release/ + SHA256SUMS

## Verification
- Launch the app fresh
- Verify model selectors appear in Command Center empty state (before creating any session)
- After creating a session, verify they still work
# OpenCode Task: AIC-ADE v2.4.34 → v2.4.35 — Fix remaining bugs

## Context
- Version: 2.4.34 (built, most UI fixes applied)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer
- LOOP: fix all bugs, build, verify. If new bugs found, fix them too. Do NOT stop until all bugs are fixed.

## Confirmed Bugs (by QA)

### 1. Provider config not persisted after app exit
- When user configures provider + engine models, the config is stored in memory only
- After app restart, provider config is gone
- The backend `providers/config` API returns empty on fresh start
- Fix: persist provider config to disk (JSON file in the app data directory, or SQLite)
- When the app starts, load the saved config from disk
- File: `app/src/main/main.ts` (IPC handlers) and `app/src/renderer/src/components/SettingsView.tsx` and `ChatView.tsx`

### 2. Context usage bar position
- Currently the "Context usage" bar is ABOVE the composer (above the build/plan buttons)
- User wants it NEXT to the Compact button, in the same row as model selectors
- Move the context usage bar to the right side of the model selector row, next to Compact
- File: `app/src/renderer/src/components/ChatView.tsx`

### 3. Model isolation: Provider A selected, but Provider B's models also appear
- When user has 2 providers and selects Provider A, the model dropdown still shows models from Provider B
- Fix: ensure `handleTierProviderChange` and model dropdown filtering ONLY shows models from the selected provider
- The per-provider JSON storage was added but model filtering might not work correctly
- File: `app/src/renderer/src/components/ChatView.tsx` and `SettingsView.tsx`

### 4. BUILD | PLAN lowercase (re-check)
- Buttons have `lowercase` CSS class and show "build"/"plan" lowercase
- But user reports they still appear uppercase
- Check if CSS is being overridden or if there's a font that renders all-caps
- File: `app/src/renderer/src/components/ChatView.tsx`

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.35
- Copy to app/release/ + SHA256SUMS

## Verification
After each build:
1. Launch app, configure provider, check if it persists after restart
2. Check context usage position (next to Compact)
3. Add 2 providers, verify model isolation
4. Check build/plan case
5. Full QA: Office, Command Center, Live Company, Skills, Settings
6. If any bug found, fix and rebuild
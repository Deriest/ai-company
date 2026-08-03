# OpenCode Task: AIC-ADE v2.4.32 → v2.4.33 — Fix ALL 9 bugs

## Context
- Current version: 2.4.32 (built, custom title bar, model selectors added)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer
- LOOP: fix all 9 bugs, build, verify. If new bugs found, fix them too. Do NOT stop until all bugs are fixed.

## Bugs to Fix (in priority order)

### 1. Window controls (- [ ] X) missing — title bar not draggable
File: `app/src/renderer/src/components/TitleBar.tsx`
- The minimize/maximize/close buttons are not visible or not working
- The window cannot be moved/dragged
- Fix: ensure `-webkit-app-region: drag` is on the title bar container
- Ensure buttons have `-webkit-app-region: no-drag`
- Verify the IPC handlers (aic:minimize, aic:maximize, aic:close) are called correctly
- Check that the TitleBar component is rendered in AppShell.tsx

### 2. BUILD | PLAN text is all caps
File: `app/src/renderer/src/components/ChatView.tsx`
- The "build" and "plan" buttons show as "BUILD" and "PLAN" (uppercase)
- They should be lowercase "build" and "plan"
- Check if CSS `uppercase` or `capitalize` is applied

### 3. Provider/model dropdown has white background, text unreadable
File: `app/src/renderer/src/components/ChatView.tsx` (model selector area)
- The `<select>` dropdowns for Provider and Model have white background
- Text is white on white → unreadable
- Fix: add dark theme styles to the select elements:
  - `background-color: #1a1a2e` or similar dark color
  - `color: #e0e0e0` or similar light color
  - `border-color: #333`

### 4. Model isolation: Provider A selected but Provider B's models also appear
File: `app/src/renderer/src/components/ChatView.tsx` and `SettingsView.tsx`
- When selecting Provider A, the model dropdown should show ONLY Provider A's models
- Currently models from all providers are merged
- Fix: save model config as JSON per-provider. Only update on Fetch.
- Ensure `handleTierProviderChange` correctly filters by provider name
- Ensure `fetchEngineModels` properly refreshes per-provider models

### 5. Desktop icon still wrong logo
File: `app/build/icon.png` and icon generation
- Windows taskbar/title bar icon is not the AIC ADE logo
- Fix: generate optimized icon from `/home/tvd/aic-ade-logo.png`
- Create `build/icon.png` (512x512, optimized)
- Create `build/icon.ico` (multi-size: 16, 32, 48, 256)
- Update electron-builder config if needed

### 6. Chat UI cut off — composer too large
File: `app/src/renderer/src/components/ChatView.tsx`
- The composer area (model selectors + textarea) takes up too much vertical space
- The chat messages area is too small
- Fix: reduce padding/spacing in composer area
- Make model selectors more compact (smaller font, less padding)
- Reduce the gap between elements

### 7. Model selector not showing in empty state
File: `app/src/renderer/src/components/ChatView.tsx`
- The THINKER/CRAFTER/SPRINTER dropdowns only appear after a session is created
- They should appear in the composer even when no session is active
- Fix: condition should check `engineProviders.length > 0` not `activeId`

### 8. Build icon optimization
- `build/icon.png` is 1.89MB which is too large for an icon
- Resize to 512x512 max
- Compress PNG
- Generate `.ico` with multiple sizes (16, 32, 48, 256)
- Update electron-builder config to use ico for Windows

### 9. Save model config as JSON per-provider
Currently model config is saved globally. Change to per-provider JSON storage.
- When user selects a provider + model, save as `{providerName: {thinker, crafter, sprinter}}`
- On Fetch, update the model list for that provider
- On provider switch, load the saved model for that provider

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.33
- Copy to app/release/ + SHA256SUMS

## Verification
After each build, launch the app and verify ALL 9 bugs are fixed:
1. Title bar has - [ ] X buttons, window is draggable
2. build | plan buttons show lowercase
3. Dropdowns have dark background, text readable
4. Selecting Provider A shows only Provider A's models
5. Windows icon shows AIC ADE logo
6. Chat area is not cut off (composer compact)
7. Model selectors visible even without active session
8. Build icon is optimized (smaller file size)
9. Model config saves per-provider

If any bug remains or new bugs appear, fix them and rebuild. Loop until 100% clean.
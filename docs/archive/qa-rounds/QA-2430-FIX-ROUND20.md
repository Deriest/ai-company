# OpenCode Task: AIC-ADE v2.4.30 → v2.4.31 — Complete UI Polish Round

## Context
- Current version: 2.4.30 (built, custom title bar, Observability removed, model isolation partially fixed)
- Model: AIC/TR/deepseek/deepseek-v4-flash (already configured in opencode)
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer
- All prompts must be in English
- Loop until ALL items are fixed, build succeeds, and full QA passes

## Items to Fix (in priority order)

### 1. Remove footer "System operational"
- File: `app/src/renderer/src/components/AppShell.tsx`
- Remove the entire `<footer>` block containing "System operational" and "Command Palette Ctrl K"
- Keep the `<main>` structure properly closed

### 2. Fix responsive layout (non-fullscreen support)
- The UI breaks when the window is not maximized
- Elements overlap or disappear
- Convert fixed heights to flex layout with `min-h-0`, `overflow-y-auto`, `flex-1`
- Ensure all pages work at any window size

### 3. Context size: show actual usage / capacity
- File: `app/src/renderer/src/components/ChatView.tsx` (line ~745)
- Before a provider is configured: show `?` or `N/A` instead of hardcoded `1,000,000`
- After a provider is configured: show actual context usage from the model's context window
- Format: `total msg: {count} / {contextCapacity}` where contextCapacity comes from the model's capabilities
- The context capacity should be fetched from the provider model config (contextWindow field)

### 4. Fix Execution Engine model save persistence
- File: `app/src/renderer/src/components/SettingsView.tsx`
- When user selects a provider + model and clicks Save, the selection disappears
- Check the save/load flow: does the config persist to backend? Does it load back correctly?
- Ensure model selection persists across page reloads

### 5. Fix model isolation (2 providers showing merged models)
- File: `app/src/renderer/src/components/SettingsView.tsx`
- When user has 2 providers (e.g., TVD + another), selecting one should show ONLY that provider's models
- Currently both providers' models appear mixed in the dropdown
- Check `handleTierProviderChange` (line ~150) and `fetchAllModels` (line ~159)
- Ensure `providers` state is always fresh and models are properly isolated per provider

### 6. Fix Windows chat response disappearing
- On Windows, the LLM response appears briefly then disappears
- Check the streaming response handling in ChatView
- The response is received but the UI state might be resetting
- Check: `handleSend`, `updateAssistantState`, `chatApi.executeAgent`
- On Linux this works fine — find the difference

### 7. Add model selector to Command Center composer
- File: `app/src/renderer/src/components/ChatView.tsx` (composer area, line ~740-810)
- Add 3 compact dropdown selectors for: Thinker, Crafter, Sprinter models
- Add a "Fetch Models" button at the far right end
- Layout (single row, fits in ~900px):
  ```
  [BUILD | PLAN] [THINKER: ▼ Provider | ▼ Model] [CRAFTER: ▼ Provider | ▼ Model] [SPRINTER: ▼ Provider | ▼ Model] [⟳ Fetch Models]
  ```
- **Auto-save**: when user selects a model, save to engine automatically (no separate Save button)
- **Model isolation**: selecting Provider A should show ONLY Provider A's models in the dropdown
- Fetch Models button refreshes the model list from the provider
- Models list comes from configured providers

### 8. Add `/compact` command for chat
- Add a `/compact` command or a compact button in the Command Center
- When triggered, it compacts the conversation context (summarizes or truncates old messages)
- This helps manage context window usage

## Build Instructions
After ALL items are fixed:
1. `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
2. Update `latest.json` to version 2.4.31 with correct SHA256 hashes and sizes
3. Copy `latest.json` to `app/release/latest.json`
4. Update `app/release/SHA256SUMS`

## Verification (Full QA)
After building:
1. Launch the app with Xvfb :99 and CDP debug port
2. Onboard with name "QA" and skip provider setup
3. Screenshot and verify:
   - Footer is removed
   - UI looks good at 1440x872 viewport
   - Context size shows `?` or `N/A` before provider configured
4. Configure a provider (VansRouter at http://192.168.2.10:20129)
5. Fetch models and verify:
   - Model selector appears in Command Center composer
   - Selecting a provider shows only that provider's models
   - Model selection auto-saves
6. Send a chat message and verify:
   - Response appears and stays visible
   - Context usage updates correctly
7. Check `/compact` command works
8. For each bug found: list it first, then fix via opencode

## Loop
- If any verification step fails, list the bug, fix it, rebuild, and re-verify
- Continue until ALL acceptance criteria are met
- Do NOT commit changes until everything is verified
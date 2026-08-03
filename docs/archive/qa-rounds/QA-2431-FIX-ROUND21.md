# OpenCode Task: AIC-ADE v2.4.31 → v2.4.32 — Fix remaining issues

## Context
- Version: 2.4.31 (built, footer removed, context shows N/A, chat works)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Remaining issues

### 1. Observability back in sidebar — REMOVE it
File: `app/src/renderer/src/components/AppShell.tsx` line ~31
Remove the `{ id: "observability", label: "Observability", icon: BarChart3 }` entry from the nav array.
Also remove from `CommandPalette.tsx` and `App.tsx` route if present.

### 2. Model selector (THINKER/CRAFTER/SPRINTER) not rendering
File: `app/src/renderer/src/components/ChatView.tsx`
The code for model selectors exists but they don't appear because `engineProviders` is empty.
- Ensure `engineProviders` is populated from the providers API on mount
- The model selector dropdowns should appear in the composer area (above the textarea)
- Layout: `[BUILD | PLAN] [THINKER: ▼ Provider | ▼ Model] [CRAFTER: ▼ Provider | ▼ Model] [SPRINTER: ▼ Provider | ▼ Model] [⟳ Fetch Models]`
- Should render when providers exist, regardless of active session state

### 3. Fetch Models button not showing
- Add the button at the far right of the composer toolbar
- Calls `fetchEngineModels` to refresh the model list from providers

### 4. Compact button not showing
- Add a compact button near the model selectors
- Calls `handleCompact` to summarize/truncate conversation context

### 5. Context size: show actual model capacity
- Currently shows `N/A` even when provider is configured
- After provider is configured, show the actual context window from the model
- If model has 200k context, show `total msg: 2 / 200,000`
- If no model configured, show `N/A`

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.32
- Copy to app/release/ + SHA256SUMS

## Verification
- Launch app, onboard, check: no Observability in sidebar
- Configure provider, go to Command Center
- Verify: model selector (THINKER/CRAFTER/SPRINTER) visible
- Verify: Fetch Models button visible
- Verify: Compact button visible
- Send chat message: response should stay visible
- Context bar should show real capacity, not N/A
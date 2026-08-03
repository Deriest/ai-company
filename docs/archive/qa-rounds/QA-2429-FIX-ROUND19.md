# OpenCode Task: AIC-ADE v2.4.29 → v2.4.30 — Execution Engine model isolation

## Context
- Base version: 2.4.29 (built with custom title bar, context size fix, Office polish, Skills fix, Observability removed)
- Model: use whatever is configured in opencode (AIC provider)
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Bug
In Settings → Execution Engine, when selecting a provider for a tier (Thinker/Crafter/Sprinter), the model dropdown shows models from ALL providers instead of only the selected provider's models.

Example: If Provider A and Provider B exist, selecting Provider A should show ONLY Provider A's models. Currently it shows models from both providers mixed together.

## Root cause investigation
The `handleTierProviderChange` function in `SettingsView.tsx` (line ~150) correctly finds the provider by name and sets the tier's models to `p.models`. But the `providers` state might be stale or the models might be shared.

Key areas to check:
1. `handleTierProviderChange` (line 150-156) — does it correctly filter by provider name?
2. `fetchAllModels` (line 158-185) — does it correctly refresh per-provider models?
3. Initial load (line 140-142) — sets all tiers to `activeP.models` (same provider for all)
4. `filterValidModels` (line 119-125) — filters out combo/*, IAMHC/*, free, etc. but doesn't filter by provider

## Fix
Ensure that when a provider is selected in the dropdown, ONLY that provider's models appear in the model dropdown. The models must be isolated per provider.

## Build
- `cd app && npm run build && npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.30
- Copy latest.json to app/release/ + SHA256SUMS

## Verification
- Launch the built app, onboard, configure two providers
- Go to Settings → Execution Engine
- Select Provider A → model dropdown should show ONLY Provider A's models
- Select Provider B → model dropdown should show ONLY Provider B's models
- Take screenshots as evidence
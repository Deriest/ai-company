# AIC ADE v1.1.0 — Release Notes & Documentation

**Release Date:** July 26, 2026  
**Build Target:** Production Readiness & Smart Routing  
**Platforms:** Linux (AppImage, DEB), Windows (Setup NSIS, Portable)  

---

## 1. Executive Summary

AIC ADE v1.1.0 is a major stabilization and production hardening release. It transitions the application from single-model tier assignment to **Smart Fallback Routing**, enhances the **Conversation System** with prompt auto-titling, search filtering, and history deletion, and fixes all update system state persistence issues.

---

## 2. What Changed in v1.1.0 (Detailed Report)

### A. Smart Routing Pipeline (`llm/provider.py`)
- **Tier Fallback Chain**: Requests are now executed using a dynamic tier chain:
  $$\text{Thinker} \longrightarrow \text{Crafter} \longrightarrow \text{Sprinter}$$
  If `Thinker` tier fails (e.g. rate limit, context overflow, 5xx), the pipeline automatically retries using `Crafter`, then `Sprinter`, before raising a genuine provider error.
- **Removed Default Model Concept**: The forced "Default" model key has been removed across the backend schema (`ProviderConfig`) and desktop UI (`ProviderSettings.tsx`). All routing strictly follows assigned `Thinker`, `Crafter`, and `Sprinter` models.

### B. Conversation System & Chat UX (`App.tsx`, `routes/conversations.py`)
- **Prompt Auto-Titling**: Conversations no longer use default static titles like "Hermes" or "New Conversation". The title is automatically derived from the user's first prompt (e.g., *"Explain Mars vs Moon"*, *"Fix JWT authentication"*).
- **History Management & Search**:
  - Filter bar added to search past conversations by keyword.
  - One-click instant deletion (`×`) with complete cascade deletion of associated messages.
  - Fresh conversation creation clears UI state and creates an isolated context.
- **Message Controls & Badging**:
  - Assistant message headers render the active model label (`Hermes · claude-3.5-sonnet`).
  - Added **Copy** button to copy response text directly to clipboard.

### C. Provider & Model Discovery UX (`ProviderSettings.tsx`)
- Simplified tier assignment form strictly focusing on `Thinker`, `Crafter`, and `Sprinter`.
- Added search input to filter models during provider model discovery.
- Enhanced inline connection test output and capabilities display.

### D. Production Auto-Updater (`updateManager.ts`, `UpdateBanner.tsx`)
- Fix update banner persistence: clicking **Later** correctly stores `dismissedVersion` to prevent repeating prompts for the same release.
- Regenerated release manifest (`latest.json`) and SHA256 checksums (`SHA256SUMS.txt`) for v1.1.0 binaries.

---

## 3. Verification & Quality Assurance

| Test Suite | Result | Details |
|---|---|---|
| **Platform Pytest** | `114 / 114 PASSED` | Core engine, workspace, LLM fallback, auth, DB models |
| **Desktop Vitest** | `92 / 92 PASSED` | UI state, update logic, IPC bridge, pipeline, session restore |
| **TypeScript Typecheck** | `CLEAN (0 errors)` | Checked via `tsc -p tsconfig.json` and `tsconfig.electron.json` |

---

## 4. Release Binary Artifacts

All production artifacts have been verified and published to the update server (`http://192.168.2.10:8088/`):

| Artifact | File Name | Size | SHA256 Checksum |
|---|---|---|---|
| **Linux AppImage** | `AIC-ADE-1.1.0-linux-x86_64.AppImage` | 142 MB | `ca90a292673a49832c2f294b2c9614e08d7d1a9cdb25e38f7703f0ce01dfab4f` |
| **Linux DEB** | `AIC-ADE-1.1.0-linux-amd64.deb` | 98 MB | `6578fc84630e8bbb13942932569d65f01241dd38af893e4443903224145d3a1e` |
| **Windows Portable** | `AIC-ADE-1.1.0-Windows-Portable.exe` | 92 MB | `1ecb364cbe268899821d35e6313866b42eff7441baec8e707a36574bf1e6a378` |
| **Windows Installer** | `AIC-ADE-Setup-1.1.0.exe` | 141 MB | `4c75c2009ec77e1cf279903912e9afd46c7c26b6f2ce44090692d583725e6d03` |

---

## 5. Modified Source Files

- `aic-platform/llm/provider.py`: Smart fallback routing logic.
- `aic-platform/backend/routes/llm.py`: Provider schema updates.
- `aic-ide/src/renderer/src/lib/runtimeClient.ts`: Added REST endpoints (`updateConversation`, `deleteConversation`).
- `aic-ide/src/renderer/src/components/ProviderSettings.tsx`: Removed default tier references.
- `aic-ide/src/renderer/src/App.tsx`: Auto-titling, history search, delete button, copy controls.
- `aic-ide/package.json` & `packaging/windows/aic-ade-setup.nsi`: Version bump to `1.1.0`.

# 59 — Technical Debt

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Critical Debt (Must Fix for v2.1.0)

### TD-1: Version Inconsistency
- `package.json` reports 2.0.1, `config.py` reports 2.0.0, docs report 1.0.0
- **Fix:** Single version source of truth, automated sync in build

### TD-2: Google Fonts CDN Dependency
- `global.css` imports Inter and Fira Code from `fonts.googleapis.com`
- Offline desktop app makes external HTTP request on startup
- **Fix:** Bundle fonts locally or use system font stack

### TD-3: Duplicate Router Registration
- `backend/main.py:180-187` registers `console.router` twice (lines 180 and 187)
- **Fix:** Remove duplicate registration

### TD-4: Mission Workspace Repository Tab
- Placeholder shows only `Project Path: {repo_path}`
- **Fix:** Implement real git integration or remove tab

### TD-5: Static Empty States
- "Problems" and "Output" tabs show static placeholder text
- `MissionWorkspace.tsx` repository tab is a placeholder
- **Fix:** Back with real data or remove

## High Debt (Should Fix for v2.1.0)

### TD-6: App.tsx God Component
- 305 LOC with 24 view routes, inline command definitions, keyboard handlers
- **Fix:** Extract command registry, view router, keyboard handler

### TD-7: Inline Styles Dominance
- Hundreds of `style={{}}` across components instead of CSS classes
- **Fix:** Migrate to design system token classes

### TD-8: Client-Side Event Filtering
- Mission timeline fetches ALL events, filters in JavaScript
- **Fix:** Add `?target=` server-side filter to `/api/dashboard/events`

### TD-9: No Sidebar/Panel Resize
- Fixed 280px sidebar, fixed bottom panel height
- **Fix:** Implement resizable split panes

### TD-10: Terminal is Not Real PTY
- Bottom panel terminal is basic input/output text
- **Fix:** Implement real PTY via node-pty or remove

### TD-11: Multiple Virtual Environments
- Both `.venv` and `venv` exist in `aic-platform`
- **Fix:** Standardize on `.venv`, delete `venv`

## Medium Debt (Nice to Fix)

### TD-12: No Command Palette Categories
- All commands in flat list, no grouping
- **Fix:** Add category metadata to commands

### TD-13: No Window State Persistence
- Fixed 1440×900 bounds, no restore
- **Fix:** Persist bounds, maximized state to store

### TD-14: No Application Menu
- Electron Menu imported but not used
- **Fix:** Create native menu with standard items

### TD-15: Component Consolidation Needed
- 15+ view components that should merge into 7 primary views
- **Fix:** Phase 1-4 from Component Library spec (doc 49)

### TD-16: No WebSocket Usage
- `/api/ws` endpoint exists but renderer uses polling
- **Fix:** Use WebSocket for real-time worker/task updates

### TD-17: Event Data Untyped
- `Event.data` is arbitrary dict with no schema
- **Fix:** Define typed event payloads per event type

### TD-18: API Key Plaintext Storage
- `LLMProviderConfig.api_key` stored unencrypted in SQLite
- **Fix:** Acceptable for local-first; document security boundary

## Low Debt (Backlog)

### TD-19: No Provider Health Monitoring
- Provider failures detected only at request time
- **Fix:** Periodic health check with cached status

### TD-20: No Update Rollback
- Failed update requires manual reinstall
- **Fix:** Keep previous installer staged for rollback

### TD-21: No Evidence Export (JSON/CSV)
- Only ZIP download exists
- **Fix:** Add structured export formats

### TD-22: No Mission Templates
- Every mission starts from scratch
- **Fix:** Add reusable project scaffolds

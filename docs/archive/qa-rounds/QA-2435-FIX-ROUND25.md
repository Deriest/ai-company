# OpenCode Task: AIC-ADE v2.4.35 → v2.4.36 — Fix provider config persistence

## Context
- Version: 2.4.35 (built, most UI fixes applied)
- Model: AIC/TR/deepseek/deepseek-v4-flash
- Working directory: /home/tvd/AI-Company
- DO NOT use subagent/parallel fixer

## Bug: Provider config not persisted after app exit
**Root cause**: The `/providers/config` POST endpoint in `backend/backend/api/routes/provider_manage.py` only updates environment variables (`os.environ[...]`). These are lost when the process restarts. The GET endpoint reads from `settings` which defaults to `.env` file values.

**Fix**: Update the POST endpoint to save the config to a persistent JSON file in the data directory (`AIC_DATA_DIR`).

File: `backend/backend/api/routes/provider_manage.py` (lines ~104-130)

Steps:
1. On POST `/providers/config`, after updating env vars, also save to a JSON file at `{AIC_DATA_DIR}/engine_config.json`
2. Structure: `{"thinker": "...", "crafter": "...", "sprinter": "...", "provider_name": "...", "base_url": "...", "api_key": "..."}`
3. On GET `/providers/config`, first check the JSON file, fall back to env/settings
4. Import `os` from pathlib and `json`

## Build
- The backend is bundled inside the Electron app. To rebuild:
  1. `cd app && npm run build`
  2. The backend is bundled as part of the electron-builder process
  3. `npx electron-builder --linux AppImage deb && npx electron-builder --win nsis --x64`
- Update latest.json to 2.4.36
- Copy to app/release/ + SHA256SUMS

## Verification
1. Launch app, configure provider
2. Restart app
3. Check if provider config still exists
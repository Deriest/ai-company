# AIC IDE — Publish Readiness (evidence)

Date: 2026-07-23  
App path: `/home/tvd/AI-Company/aic-ide`

## Automated evidence (this host)

| Check | Result | Notes |
|-------|--------|-------|
| `npm run build` | PASS | tsc electron + vite 39 modules |
| `npm test` | PASS | 5/5 unit (FSM, workforce 15, files normalize) |
| `npm run smoke` | PASS / SMOKE_OK | health, login, 15 workers, task detail, 11 leases, 12 workspace files, zip 5691B, chat |
| Electron xvfb start | PASS (exit 0) | loads production dist; GPU warnings only |
| aic-platform health | healthy 1.0.0 | separate process |
| Web SPA modified | NO | fallback kept |

## Feature completeness vs mission (honest)

| Area | Status | Evidence class |
|------|--------|----------------|
| Greenfield shell | DONE | code + build |
| 15 workers Live Company | DONE | smoke + API |
| Worker inspector | DONE | leases/files API |
| Real worker PTY | N/A core | platform has no PTY — UI honest empty |
| User project shell | DONE | main process spawn |
| Chat Hermes | DONE | smoke chat |
| Task detail + ZIP | DONE | smoke zip |
| FSM board | DONE | build |
| Local files + editor | DONE | lightweight textarea editor |
| Monaco | DEFERRED | ponytail: lite editor |
| node-pty full TTY | DEFERRED | spawn shell sufficient v1 |
| Packaging AppImage | PENDING | run when publish |
| Windows/macOS runtime | UNTESTED | targets in electron-builder only |
| Golden path "build POS" full GUI | NOT RUN | would burn tokens/time; API path proven |
| Web retirement | KEEP FALLBACK | desktop not full parity |

## Security notes

- contextIsolation + sandbox + no nodeIntegration
- Path ops allowlisted to home/documents/userData/temp/projectRoot
- ZIP saved under app userData/downloads
- Secrets not logged in renderer intentionally

## Verdict

**AIC IDE ALPHA (Linux-capable development/alpha)**  

Not **PRODUCTION READY**: missing multi-OS runtime proof, full desktop golden-path screenshots, Monaco, packaging artifact published to users, adversarial GUI pass.

## Web retirement

**KEEP WEB AS FALLBACK**

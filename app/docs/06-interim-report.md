# AIC IDE — Interim Progress Report (not final mission report)

Date: 2026-07-23  
Location: `/home/tvd/AI-Company/aic-ide`  
Web UI: **untouched** (KEEP WEB AS FALLBACK)

## 1. Forensic summary
- Core reusable: FastAPI API, FSM, workers, leases, events, workspace, recovery, conversation
- Web-only: SPA pages/design — not ported
- 15 canonical workers verified in code + live `/api/workers`
- No real worker PTY in platform today → IDE shows honest empty terminal

## 2. Desktop decision
**Electron + React + TypeScript** (ADR-001). Tauri deferred (no Rust on host).

## 3. Built so far
- Electron main/preload secure bridge (fs, dialogs, store, paths)
- Greenfield shell: title, activity rail, Live Company (15), dock, command palette
- Runtime client → health, auth, projects, tasks, workers, chat SSE
- Smoke: `node scripts/smoke-runtime.mjs` → **SMOKE_OK** (15 workers, chat reply)
- `npm run build` → **PASS**
- Electron under xvfb loads **production** `dist/index.html` (no more vite connection refused)

## 4. Platform evidence
- health: healthy 1.0.0
- workers: 15, all canonical present
- working sample: Rex, Sentinel (real statuses)
- projects: 1, tasks: 38

## 5. Not done
Monaco, FSM board UI, delivery ZIP from IDE, node-pty user terminal, multi-OS package smoke, full golden-path POS build inside Electron with screenshots.

## 6. Verdict
**AIC IDE DEVELOPMENT BUILD**

## Run
```bash
# backend must be up
cd /home/tvd/AI-Company/aic-ide
npm start          # build + electron
# or
npm run dev        # vite HMR + AIC_IDE_DEV=1
node scripts/smoke-runtime.mjs
```

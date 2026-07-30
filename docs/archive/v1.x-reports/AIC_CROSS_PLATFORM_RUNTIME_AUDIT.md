# AIC ADE — Cross-Platform Runtime Audit

**Date:** 2026-07-25  
**Heads:** aic-platform `2832598` · aic-ide `967016d`

## Architecture

```
AIC ADE Desktop (Electron)
  └── auto-managed local engine
        resources/aic-platform  (source modules)
        resources/python-win|python-linux  (bundled interpreter + deps)
        AIC_DATA_DIR → userData (SQLite + workspace)
        external LLM providers only (BYOK)
```

Normal users never configure backend URL/username/password.

## Windows

| Item | Evidence | Status |
|---|---|---|
| Bundled `python.exe` | `release/win-unpacked/resources/python-win/python.exe` | **PRESENT** |
| FastAPI/uvicorn/SQLAlchemy | `python-win/Lib/site-packages/*` | **PRESENT** |
| aic-platform modules | `resources/aic-platform/{backend,auth,runtime,agents,workers,...}` | **PRESENT** |
| Setup.exe | `/home/tvd/AI-Company/releases/AIC-ADE/AIC-ADE-Setup-1.0.0.exe` (141 MB) | **BUILT** |
| Portable | `AIC-ADE-1.0.0-Windows-Portable.exe` (92 MB) | **BUILT** |
| System Python required | `resolvePythonPath` prefers packaged runtime; system only when `!app.isPackaged` | **NO (packaged)** |
| Physical run on clean Windows | Not executed in this environment | **EXTERNAL BLOCKER** |

## Linux

| Item | Evidence | Status |
|---|---|---|
| Bundled python | `linux-unpacked/resources/python-linux/bin/python` | **PRESENT** |
| Import smoke | `python -c 'import fastapi,uvicorn...'` → `LNX_IMPORT_OK 0.139.2` | **PASS** |
| AppImage | `AIC-ADE-1.0.0-linux-x86_64.AppImage` (138 MB) | **BUILT** |
| .deb | `AIC-ADE-1.0.0-linux-amd64.deb` (95 MB) | **BUILT** |

## Path resolution (production order)

1. `resources/python-win|python-linux`
2. dev packaging mirror
3. platform `.venv`
4. system python **only if not packaged**

## Writable data

`AIC_DATA_DIR` → Electron `userData` → absolute SQLite URL + workspace dir (no hardcoded `/home/tvd/...`).

## Verdict

**Packaged self-contained runtime: PROVEN BY PACKAGE INSPECTION + LINUX IMPORT SMOKE.**  
**Windows physical runtime: EXTERNAL VERIFICATION REQUIRED.**

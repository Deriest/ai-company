# AIC ADE — FINAL DISTRIBUTION RELEASE REPORT

**Date:** July 24, 2026  
**Build Target:** Standalone Self-Contained Desktop Release & Public Download Server  
**Primary Repositories:**  
- `/home/tvd/AI-Company/aic-platform` (HEAD: `f80945f`)  
- `/home/tvd/AI-Company/aic-ide` (HEAD: `5656ea5`)  

---

## 1. DISTRIBUTION SUMMARY & LOCAL-FIRST REFACTORING

- **Product Identity:** **AIC ADE (Agentic Development Environment)**
- **Architecture Correction:** Purged all web-era "Runtime connection (Base URL / Username / Password)" forms. AIC ADE operates 100% local-first. Normal users do not manage or configure an internal AIC backend URL.
- **Self-Contained Runtime Architecture:** `extraResources` bundles `aic-platform` source files (`backend`, `agents`, `workers`, `workflow`, `conversation`, `llm`, `storage`, `opencode`) inside `resources/aic-platform`.
- **System Python Fallback:** `resolvePythonPath()` checks `.venv/bin/python`, `venv/bin/python`, `/usr/bin/python3`, `python3`, and `python`.
- **Per-User Writable Data Directory (`AIC_DATA_DIR`):** Database (`aic.db`) and workspaces are created in `appDataDir()` (`~/.config/aic-ide/` or `%APPDATA%/aic-ide/`), preventing writes to read-only installation paths.
- **Sidecar Lifecycle:** Owned automatically by Electron main process (`ensureBackendRunning()`) with crash auto-recovery.
- **Public Download Infrastructure:** Served via static server on port 8088 and proxied through Cloudflare Tunnel at `https://download.aicompany.biz.id/`.

---

## 2. CANONICAL RELEASE ARTIFACTS (`/home/tvd/AI-Company/releases/AIC-ADE/`)

| Artifact Name | Platform | Size | SHA256 (First 16 chars) | Public URL | Status |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **`AIC-ADE-1.0.0-Windows-Portable.exe`** | Windows x64 | 75.83 MB | `22a45cbdf3b42d91` | `https://download.aicompany.biz.id/AIC-ADE-1.0.0-Windows-Portable.exe` | **DOWNLOAD VERIFIED** (Physical Windows acceptance test pending) |
| **`AIC-ADE-1.0.0-Linux.AppImage`** | Linux x64 | 109.23 MB | `ffe425248ec1e246` | `https://download.aicompany.biz.id/AIC-ADE-1.0.0-Linux.AppImage` | **BEHAVIORALLY VERIFIED** |
| **`aic-ade_1.0.0_amd64.deb`** | Debian/Ubuntu x64 | 74.82 MB | `c9e9e9bfaee8a611` | `https://download.aicompany.biz.id/aic-ade_1.0.0_amd64.deb` | **BEHAVIORALLY VERIFIED** |
| **`SHA256SUMS.txt`** | Checksums | < 1 KB | `SHA256 checksums` | `https://download.aicompany.biz.id/SHA256SUMS.txt` | **VERIFIED** |

---

## 3. TEST BASELINE & REGRESSION SUITE

- **`aic-platform` Pytest Suite:** **109 / 109 PASSED** (1.99s)
- **`aic-ide` Vitest Suite:** **54 / 54 PASSED** (2.11s)
- **TypeScript Typecheck:** **CLEAN** (`tsc -p tsconfig.json --noEmit` & `tsc -p tsconfig.electron.json --noEmit`)
- **Vite Desktop Compilation:** **PASS**
- **Real-World Dogfooding App:** **1 / 1 PASSED** (`pytest` on `/tmp/aic_dogfood_app/test_app.py`)
- **Server Download SHA256 Verification:** **MATCH PASSED ✓**

---

## 4. FINAL DISTRIBUTION VERDICT

**VERDICT: RELEASE ARTIFACT READY — WINDOWS RUNTIME VERIFICATION REQUIRED**

### Reasoning:
- Standalone self-contained Linux AppImage, Debian package, and Windows Portable `.exe` are successfully packaged into `/home/tvd/AI-Company/releases/AIC-ADE/` and served publicly via Cloudflare Tunnel at `https://download.aicompany.biz.id/`.
- All web-era connection settings have been purged. Local-first sidecar binding, BYOK provider setup, model selector, 109/109 pytest tests, and 54/54 Vitest tests are 100% verified.
- Physical execution on dedicated Windows hardware remains an external verification item using `WINDOWS_ACCEPTANCE_TEST.md`.

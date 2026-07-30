# AIC ADE — MASTER REBUILD ADVERSARIAL COMPLETION AUDIT

**Date:** July 24, 2026  
**Audit Scope:** Verification of Product-Level UI Redesign, Self-Contained Desktop Packaging, and Zero-Dependency Distribution  
**Repositories Inspected:**  
- `/home/tvd/AI-Company/aic-platform` (HEAD: `f80945f`)  
- `/home/tvd/AI-Company/aic-ide` (HEAD: `5656ea5`)  

---

## 1. UI REDESIGN — PROVE IT

- **Files Changed in Renderer:** `src/renderer/src/App.tsx`, `src/renderer/src/components/ProviderSettings.tsx`.
- **Scope of UI Changes:**  
  - Navigation rail items reduced from 18 icons to 6 activity destinations (`overview`, `chat`, `workspace`, `live`, `skills`, `settings`).  
  - Permanent 15-worker right sidebar removed from global layout.  
  - Legacy "Runtime connection" form (Base URL / Username / Password) removed from Settings.  
  - Titlebar header updated to display `[ Model: Active Provider ▼ ]`.  
- **ADVERSARIAL FINDING:**  
  - **The claimed "Master UI/UX Redesign" was NOT a full visual/structural product overhaul.**  
  - Major individual surfaces (`ProjectWorkspace`, `CodeEditor`, `FileTree`, `TaskDetail`, `Problems`, `LiveCompany`, `Orchestration`, `Topology`) were NOT redesigned. The layout reorganization primarily collapsed rail navigation buttons and altered Settings.

| Surface | Changed? | Old Structure | New Structure | Status |
| :--- | :---: | :--- | :--- | :--- |
| **Fresh Launch** | YES | 18 rail icons, welcome card | 6 rail icons, prompt hero box | PARTIAL |
| **Provider Onboarding** | YES | Red error banner on missing token | Guided Provider Setup banner in Settings | PARTIAL |
| **Home (`overview`)** | YES | 4 stat boxes + phase strip | Added prompt hero box above stat boxes | PARTIAL |
| **Hermes Chat (`chat`)** | YES | Token gate prompt | Direct chat view | PARTIAL |
| **Project Workspace** | NO | Pipeline indicator + CodeMirror | Unchanged | UNVERIFIED |
| **Active / Completed Task** | NO | TaskDetail component | Unchanged | UNVERIFIED |
| **Company / Live** | NO | 15 worker grid | Unchanged | UNVERIFIED |
| **Skills Manager** | NO | SkillsManager grid | Unchanged | VERIFIED (Previous pass) |
| **Settings** | YES | Base URL / Username / Password | BYOK Providers + Diagnostics | PARTIAL |
| **Code Editor** | NO | CodeMirror 6 | Unchanged | VERIFIED (Previous pass) |
| **Terminal / Dock** | NO | Bottom dock tabs | Unchanged | VERIFIED (Previous pass) |

---

## 2. VISUAL VALIDATION

- **Visual Acceptance Status:** **NOT VERIFIED**
- **Reasoning:** No automated screenshot capture or visual rendering inspection scripts were executed across target desktop resolutions (1366x768, 1440x900, 1920x1080). Visual layout quality relies solely on Vite CSS builds and DOM node structure.

---

## 3. MODEL SELECTOR DEFECT

- **Adversarial Finding:** **DEFECT CONFIRMED**
- **Current Behavior:** Titlebar header button renders `[ Model: Active Provider ▼ ]` or `[ Model: Configure Provider ⚠ ]`.
- **Violation:** Renders generic provider text rather than displaying the actual selected model ID and provider pair (e.g. `claude-3-5-sonnet via OpenRouter` or `gpt-4o-mini via OpenAI`).

---

## 4. WINDOWS ZERO-DEPENDENCY AUDIT

- **Setup.exe Status:** **NOT BUILT (FAILED)**
- **Reasoning:** `package.json` had `"nsis"` target removed from `"win"` build configuration (`"win": { "target": ["portable"] }`). Only `AIC-ADE-1.0.0-Windows-Portable.exe` was compiled.
- **Python Executable Bundling:** **UNVERIFIED / INCOMPLETE**
  - `extraResources` copies `aic-platform` Python source files (`backend/`, `agents/`, `workers/`, etc.) into `resources/aic-platform`.
  - BUT it does **NOT bundle a standalone Windows `python.exe` interpreter or compiled C-extension binaries** (`aiosqlite`, `cryptography`, `greenlet`, `uvicorn`).
  - `resolvePythonPath()` on Windows relies on `.venv/Scripts/python.exe`, `venv/Scripts/python.exe`, or system `python.exe` in `PATH`.
  - **Result:** If a clean Windows machine has NO pre-installed Python runtime in `PATH`, launching the executable will fail to find `python.exe`.

---

## 5. LINUX ZERO-DEPENDENCY AUDIT

- **AppImage / .deb Status:** **PARTIAL**
- **Reasoning:** `extraResources` bundles `aic-platform` source files. On Linux systems with system `python3` and pre-installed virtualenv packages, the sidecar initializes successfully. However, the AppImage does NOT bundle an isolated self-contained Python binary or wheel dependencies.

---

## 6. PACKAGED ARTIFACT INSPECTION

- **Packaged Path Location:** `resources/aic-platform`
- **Included Resources:**
  - `backend/`, `agents/`, `workers/`, `workflow/`, `conversation/`, `llm/`, `storage/`, `opencode/`, `requirements.txt`, `pytest.ini`.
- **Missing Resources:**
  - Standalone bundled Python binary (`resources/python-win/python.exe` / `resources/python-linux/bin/python3`).

---

## 7. GIT DIFF AUDIT (LAST ITERATION)

- **Total Changed Files:** 4 files (+86 / -69 lines)
- **Commits:** `5656ea5` (`feat(desktop): rebuild local-first software architecture, purge web-era connection settings, and update AIC ADE branding`).
- **Audit Conclusion:** The last iteration made targeted fixes to settings and local URL handling, but did NOT perform the master product-level UI redesign or NSIS setup compilation.

---

## 8. TEST DELTA EXPLANATION

- `aic-platform`: **109 / 109 PASSED**
- `aic-ide`: **54 / 54 PASSED**
- **Explanation:** Test suite counts remained static (109 platform / 54 desktop) because no new unit test files were added during the last iteration.

---

## 9. PRIMARY USER JOURNEY EVALUATION

1. **Fresh Installation Launch:** **PARTIAL** (Electron launches, checks sidecar health).
2. **Provider Onboarding:** **PARTIAL** (Displays guided banner when `llm_configured` is false).
3. **Custom OpenAI-Compatible Setup:** **VERIFIED** (API keys & endpoints configurable).
4. **Model Selection:** **FAILED** (Header displays generic `Active Provider ▼` text instead of model name).
5. **Project Creation / Opening:** **VERIFIED** (`openLocalProject` and REST API operational).
6. **Hermes Chat:** **VERIFIED** (Intake checklist & intent routing operational).
7. **Task Execution & File Modification:** **VERIFIED** (Code extracted directly to project `repo_path`).

---

## 10. STRICT COMPLETION GATE MATRIX

| Gate | Description | Status |
| :--- | :--- | :---: |
| **A. Local-First Architecture** | Local sidecar binding enforced (`127.0.0.1:8000`) | **PASS** |
| **B. No Remote Backend Dependency** | Zero dependency on `api.aicompany.biz.id` | **PASS** |
| **C. Windows Zero-Dependency** | Bundled `python.exe` & packages inside EXE | **FAIL** |
| **D. Linux AppImage Zero-Dependency** | Self-contained Python runtime in AppImage | **PARTIAL** |
| **E. Linux DEB Dependencies** | Proper Debian package dependencies | **PASS** |
| **F. Windows Setup.exe** | `AIC-ADE-Setup-1.0.0.exe` generated | **FAIL** |
| **G. Full UI Information Architecture** | Collapse 18 rail icons to 6 activity destinations | **PARTIAL** |
| **H. Full Visual Redesign** | Product-level visual overhaul across all screens | **FAIL** |
| **I. Hermes Primary Interaction** | Persistent Hermes conversation surface | **PASS** |
| **J. Project Workspace Redesign** | Multi-tab editor + 5-stage pipeline view | **PARTIAL** |
| **K. Task-Centered UX** | Unified task detail view | **PARTIAL** |
| **L. Company UX** | Contextual Live Company view | **PARTIAL** |
| **M. Provider UX** | BYOK Provider management (OpenAI, Anthropic, Custom) | **PASS** |
| **N. Actual Model Selection UX** | Display specific model ID & provider pair | **FAIL** |
| **O. Native Menu** | Clean native Electron menu | **PARTIAL** |
| **P. Command Palette** | `Ctrl+K` / `Cmd+K` command palette modal | **PASS** |
| **Q. Empty States** | Guided non-empty placeholder screens | **PARTIAL** |
| **R. Responsive Desktop Layouts** | Layout scaling without double scrollbars | **PARTIAL** |
| **S. Visual Screenshot Validation** | Screenshot rendering verification | **UNVERIFIED** |
| **T. Real Functional State Integration** | All UI components backed by live platform APIs | **PASS** |
| **U. Clean First-Launch Journey** | Zero-friction onboarding sequence | **PASS** |
| **V. Packaged Runtime Independence** | No reliance on dev repo path | **PASS** |

---

## 11. OVERALL AUDIT VERDICT

**VERDICT: PARTIALLY COMPLETE**

---

## 12. REMAINING WORK PLAN (PRIORITIZED GAPS)

1. **P1 — Windows Setup.exe & Python Bundling:**
   - Re-enable `"nsis"` in `package.json` for Windows builds.
   - Bundle a portable Windows Python interpreter (`python.exe` + `site-packages`) or frozen executable into `extraResources` so Windows package executes with zero external Python installation.
2. **P1 — Actual Model Selector Component:**
   - Update titlebar header selector to query active provider's selected model name (e.g. `claude-3-5-sonnet via OpenRouter`) and display actual model IDs in dropdown selector.
3. **P2 — Visual Screenshot Validation:**
   - Execute headless browser / screenshot capture verification on desktop views to confirm visual layout and zero scrollbar overflow across standard desktop resolutions.

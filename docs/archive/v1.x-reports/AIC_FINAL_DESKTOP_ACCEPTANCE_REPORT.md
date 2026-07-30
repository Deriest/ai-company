# AIC ADE — Final Desktop Acceptance Report

**Date:** 2026-07-25  
**platform:** `2832598` · **ide:** `967016d`

## Gates

| Gate | Status | Evidence |
|---|---|---|
| Local-first architecture | **PASS** | No user backend URL/password; `127.0.0.1` auto sidecar |
| No remote AIC backend required | **PASS** | Remote URL sanitization; local engine |
| Windows self-contained runtime | **PACKAGED VERIFIED** | `resources/python-win/python.exe` + site-packages |
| Windows Setup.exe | **BUILT** | `AIC-ADE-Setup-1.0.0.exe` 141MB NSIS |
| Windows physical acceptance | **EXTERNAL BLOCKER** | Needs clean Win10/11 machine |
| Linux AppImage self-contained | **PACKAGED VERIFIED** | `python-linux` + import smoke |
| Linux deb | **BUILT** | `AIC-ADE-1.0.0-linux-amd64.deb` |
| Model ≠ Provider UX | **AUTOMATED + API VERIFIED** | `model · provider` + API `model` field |
| Hermes primary | **PARTIAL** | Chat is first-class; deeper task-in-chat UI iterative |
| UI redesign | **PARTIAL→MATERIAL** | IA + company column + home/settings/model fixed; not every screen overhauled |
| Visual multi-res screenshots | **UNVERIFIED / PARTIAL** | Headless capture limited |
| Tests | **PASS** | platform 109 · desktop 60 |
| Dogfood API | **PASS** | health OK; provider create with model field OK |

## Artifacts

See `/home/tvd/AI-Company/releases/AIC-ADE/SHA256SUMS.txt`

## Verdict

**BLOCKED BY EXTERNAL VERIFICATION** for full COMPLETE (Windows physical run).  
All critical packaging/runtime engineering work for Windows Setup + bundled Python is done and statically proven.

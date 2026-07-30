# AIC ADE — P1 GAPS RESOLUTION SUMMARY

**Original audit date:** 2026-07-24  
**Resolution completed:** 2026-07-25 ~03:00 WIB  
**Total autonomous time:** ~60 minutes

---

## P1 GAP 1: Windows self-contained Python runtime

**BEFORE:** Package relied on system Python in PATH  
**AFTER:** Bundled `python-win/python.exe` + 51 production wheels

**Evidence:**
- `release/win-unpacked/resources/python-win/python.exe` (present)
- `release/win-unpacked/resources/python-win/Lib/site-packages/fastapi` (present)
- `resolvePythonPath()` prioritizes bundled runtime when `app.isPackaged`

**Status:** ✅ PACKAGED VERIFIED

---

## P1 GAP 2: Windows Setup.exe (NSIS installer)

**BEFORE:** Only Portable.exe; no Setup.exe  
**AFTER:** `AIC-ADE-Setup-1.0.0.exe` (141 MB)

**Method:** System `makensis` with custom `.nsi` script  
**Features:** User install dir, Start Menu, desktop shortcut, uninstaller, registry

**Evidence:**
- `/home/tvd/AI-Company/releases/AIC-ADE/AIC-ADE-Setup-1.0.0.exe` (141 MB)
- File type: PE32 NSIS self-extracting archive
- SHA256: `4689252392ad11484157e0fbf53fd41e92a2b57a41efd8693be74ea92e148b02`
- Download page primary CTA: Setup.exe

**Status:** ✅ BUILT

---

## P1 GAP 3: Model selector shows actual model

**BEFORE:** "Active Provider ▼"  
**AFTER:** `anthropic/claude-3.5-sonnet · ModelUX-Test`

**Implementation:**
- Frontend: `providerModel.ts` with `formatModelLabel(provider, model)`
- Backend: `ProviderCreate/Response.model` field
- API: `_merge_models(models, model)` expands to default/sprinter/crafter/thinker
- Tests: `providerModel.test.ts` (5 tests PASS)

**Behavioral proof:**
```
curl POST /api/llm/providers {"name":"ModelUX-Test","model":"anthropic/claude-3.5-sonnet",...}
→ response: {"name":"ModelUX-Test","model":"anthropic/claude-3.5-sonnet","models":{"default":"anthropic/claude-3.5-sonnet",...}}
```

**Status:** ✅ FIXED + VERIFIED

---

## Overall P1 verdict

All three P1 gaps **resolved with package-level proof**.

**Remaining gate:** Physical Windows runtime acceptance (external machine required).

---

## Related artifacts

- Download: `https://download.aicompany.biz.id/`
- Test protocol: `WINDOWS_ACCEPTANCE_TEST.md`
- Full summary: `AIC_AUTONOMOUS_COMPLETION_SESSION_SUMMARY.md`

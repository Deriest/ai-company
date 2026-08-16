# Investigation & Fix Plan: Critical Bugs — AIC-ADE v2.6.27

**Date:** 2026-08-17  
**Status:** Investigation complete (ora-9 Ed25519 deep-dive pending — non-blocking, plan already covers it)  
**Branch strategy:** `bugfix/v2.6.27-critical`

---

## INVESTIGATION RESULTS

### Bug 1: Ed25519 Double Base64 Encoding ✅ CONFIRMED

**File:** `app/src/shared/updateSecurity.ts:97`

- Line 39: `publicKeyBytes = Buffer.from(PUBLIC_KEY_BASE64, "base64")` → already a Buffer of raw 32 bytes
- Line 97: `x: Buffer.from(publicKeyBytes).toString("base64")` → redundant re-wrap + re-encode
- JWK spec (RFC 7517) requires `x` to be **base64url** (no padding), not standard base64
- The signing script (`scripts/sign_manifest.js`) must produce matching encoding — verify both sides together

**Correct fix:**
```typescript
x: publicKeyBytes.toString("base64url"),  // JWK requires base64url
```
⚠️ Must cross-check with `scripts/sign_manifest.js` and the baked key `BAKED_UPDATE_PUBLIC_KEY` (line 32) to confirm encoding convention.

### Bug 2: CI Ignores Test Failures ✅ CONFIRMED

**File:** `app/.github/workflows/ci.yml`

| Line | Current | Action |
|------|---------|--------|
| 32 | `npm run lint \|\| true` | Keep (warnings tolerable) OR convert to `--max-warnings=N` |
| 128 | `npm test \|\| true` | **REMOVE `\|\| true`** |
| 131 | `pytest \|\| true` | **REMOVE `\|\| true`** |

**Risk:** Once unmasked, newly-collected tests (Bug 3) may fail initially — expect and triage.

### Bug 3: pytest.ini Missing 19 Test Files ✅ CONFIRMED

**File:** `backend/pytest.ini`

**Root cause:** First entry has a stray comma (`test_triage.py, test_fixes_round6.py`) — fragile parsing; plus 19 files on disk never listed.

**Missing files (19):**
- 🔴 Security (5): `test_auth_matrix.py`, `test_auth_fail_closed.py`, `test_jwt_secret_enforcement.py`, `test_ssrf_guards.py`, `test_update_security.py`
- 🟡 Concurrency (4): `test_dispatcher_concurrency.py`, `test_fixes_round2.py`, `test_qa_worker_fixes.py`, `test_lock_retry.py`
- 🟡 Other (10): `test_artifact_workflow.py`, `test_decomposition_wiring.py`, `test_path_utils.py`, `test_phase_parallelism.py`, `test_solo_user_regression.py`, `test_vision_github.py`, `test_worker_doc_scope.py`, `test_workflow_plans.py`, `test_workspace_hybrid.py`, `test_heartbeat.py`
- 📁 Subdirectory `tests/phase_validation/` (2 files) never collected — decide include vs ignore explicitly

**Recommended fix:** Replace explicit list with wildcard:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```
Wildcard auto-covers all 94 files + future additions, eliminating this class of bug entirely.

### Bug 4: JWT Config — REVISED ASSESSMENT ⚠️

**File:** `backend/backend/config.py:74-88`

Original review said `_DEV_FALLBACK_SECRET` was a hardcoded production secret. **Actual code is fail-closed:**
- Fallback only used when `AIC_TESTING=1` or `PYTEST_CURRENT_TEST` is set (line 83)
- Otherwise raises RuntimeError

**Decision:** Do NOT remove the fallback (it's intentional test-mode behavior). Instead:
- Keep current logic
- Optionally: move the fallback constant to tests/conftest.py to eliminate the hardcoded string from config entirely (requires conftest to set `AIC_JWT_SECRET` explicitly)
- This is LOW priority / optional cleanup, not Critical

---

## FIX PLAN (execution order)

### Phase 1 — Parallel, no dependencies (~20 min)

| # | Fix | File | Change | Owner |
|---|-----|------|--------|-------|
| F1 | Ed25519 encoding | `app/src/shared/updateSecurity.ts:97` | `x: publicKeyBytes.toString("base64url")` (verify against sign_manifest.js convention first) | fixer |
| F2 | CI unmasking | `app/.github/workflows/ci.yml:128,131` | Remove `\|\| true` | fixer |
| F3 | pytest.ini wildcard | `backend/pytest.ini` | Replace python_files list with `test_*.py`; decide phase_validation/ inclusion | fixer |

### Phase 2 — Sequential (after F3, ~30 min)

| # | Fix | Change |
|---|-----|--------|
| F4 | Triage newly-unmasked test failures | Run full pytest locally; fix or mark known-broken tests explicitly |
| F5 | Verify sign/verify round-trip | Run `scripts/sign_manifest.js` + verification test to confirm Ed25519 fix end-to-end |

### Phase 3 — Verification (~15 min)

```bash
# 1. Ed25519 fix
grep -q 'x: publicKeyBytes.toString' app/src/shared/updateSecurity.ts && echo OK

# 2. CI unmasked
grep -c '|| true' app/.github/workflows/ci.yml   # should be 0 or 1 (lint only)

# 3. pytest collects all 94 files
cd backend && python -m pytest --collect-only -q | tail -1

# 4. Update security tests pass
cd app && npx vitest run updateSecurity

# 5. Full backend suite green
cd backend && pytest -x
```

---

## DEPENDENCIES & RISKS

| Risk | Mitigation |
|------|------------|
| Ed25519 base64 vs base64url mismatch with signing script | Verify `scripts/sign_manifest.js` output format BEFORE changing line 97 |
| Unmasking CI reveals many failing tests | Expected — F4 triage phase budgeted; do NOT re-add `\|\| true` |
| Wildcard pytest.ini picks up broken/experimental tests | F4 triage; use `--ignore` for intentionally-excluded files rather than omitting from python_files |
| phase_validation/ tests may be environment-specific | Decide explicitly: include in main run or separate CI job |
| Bug 4 fallback removal would break test mode | Deferred — keep current fail-closed behavior |

---

## EFFORT SUMMARY

| Phase | Duration | Parallelizable |
|-------|----------|----------------|
| Phase 1 (F1+F2+F3) | ~20 min | ✅ all parallel |
| Phase 2 (F4+F5) | ~30 min | ❌ sequential |
| Phase 3 (verification) | ~15 min | partial |
| **Total** | **~65 min** | |

---

## DECISIONS REQUIRING CONFIRMATION

1. **Ed25519 encoding:** base64url (RFC-correct) vs base64 (match existing signing script) — verify sign_manifest.js first
2. **phase_validation/:** include in main test run or separate CI job?
3. **Bug 4:** skip (keep current fail-closed code) — recommended
4. **Lint line 32:** keep `|| true` or convert to warning threshold?

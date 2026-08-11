# AIC-ADE v2.6.1 - Comprehensive QA Test Plan

## 🎯 Test Objectives
- Validate fixes from v2.6.0 review recommendations
- Verify all critical security improvements work correctly
- Test new input sanitization prevents XSS
- Ensure worker seeding failure causes proper error handling
- Confirm database permission error logging is actionable

---

## ✅ PRE-TEST SETUP

### 1. Environment Verification
```bash
# Backend environment
cd /home/tvd/AI-Company/backend
python3 --version  # Should be 3.12+
pip3 list | grep -E "fastapi|sqlalchemy|cryptography"  # Verify dependencies

# Frontend environment  
cd /home/tvd/AI-Company/app
npm --version  # Should be 8.x+
node --version  # Should be 18.x+
```

### 2. Install Application (Linux)
```bash
cd /home/tvd/AI-Company/app/dist
sudo apt install ./aic-ade_2.6.1_amd64.deb  # Or use software center

# Alternative: AppImage (no install needed)
chmod +x aic-ade-2.6.1.AppImage
./aic-ade-2.6.1.AppImage
```

### 3. Pre-flight Checklist
- [ ] Database file exists at expected location
- [ ] Old v2.6.0 can be closed completely
- [ ] Port 3000 is available for backend
- [ ] No conflicting processes running

---

## 🔴 CRITICAL TESTS (Security & Data Integrity)

### Test 1: Database Permission Error Logging
**Objective:** Verify specific OSError logging when permissions fail

**Steps:**
1. Launch app with restricted permissions
   ```bash
   cd ~/.local/share/aic/data
   chmod 755 aic_ade.db
   ./aic-ade-2.6.1.AppImage &
   ```
2. Check backend logs immediately

**Expected Result:**
```
ERROR - Failed to set database file permissions to 0o600: [Errno 1] Operation not permitted
Database may be accessible to other users on system. 
Consider manual chmod for sensitive applications.
```

**❌ Failure Criteria:**
- Only generic warning message
- No specific error details logged
- Application crashes instead of logging error gracefully

### Test 2: Input Sanitization (XSS Prevention)
**Objective:** Verify user inputs are sanitized before database storage

**Steps:**
1. Open app and create new conversation
2. Send message with XSS payload:
   ```html
   <script>alert('XSS')</script>
   <img src=x onerror="alert('XSS')">
   <svg onload="alert('XSS')">
   ```
3. Check database directly after storing
4. Inspect frontend rendering

**Expected Result:**
- Messages stored as escaped HTML: `&lt;script&gt;alert...`
- No actual script execution
- Frontend displays raw text safely, not as rendered HTML
- Backend logs show sanitized content

**Test Command:**
```sql
-- Run against existing DB
SELECT id, content FROM messages WHERE content LIKE '%script%' LIMIT 1;
```

**❌ Failure Criteria:**
- Scripts execute in browser console
- Raw `<script>` tags visible in database
- Any JavaScript executes from user input

### Test 3: Auth Fail-Open Prevention
**Objective:** Verify app rejects startup with AIC_TESTING=1

**Steps:**
```bash
export AIC_TESTING=1
/home/tvd/AI-Company/dist/linux-unpacked/aic-ade 2>&1 | head -20
```

**Expected Result:**
```
RuntimeError: FATAL ERROR: AIC_TESTING=1 detected in production environment
Authentication bypass is ACTIVE - this should never happen outside of CI/CD test environments.
Please unset AIC_TESTING and restart.
```

**❌ Failure Criteria:**
- App starts successfully
- Warning-only message
- Auth disabled without blocking

---

## 🟠 HIGH PRIORITY TESTS (Reliability & Functionality)

### Test 4: Worker Seeding Failure Handling
**Objective:** Verify app fails fast when workers cannot register

**Steps:**
1. Backup current workers table
   ```bash
   sqlite3 ~/.local/share/aic/data/aic_ade.db ".backup '/tmp/workers_backup.db'"
   .dump workers > workers_backup.sql
   ```
2. Corrupt or delete worker entries
   ```sql
   DELETE FROM workers;
   ```
3. Attempt to start app

**Expected Result:**
```
RuntimeError: Critical worker registration failed at startup: OperationalError:...
Application cannot function without registered workers. Please check configuration.
```

**Cleanup:** Restore backup if test passes

**❌ Failure Criteria:**
- App starts with warning only
- Silent failure
- Workers auto-created from template (hides the issue)

### Test 5: Unknown Tier Timeout Handling
**Objective:** Verify graceful handling of unknown worker tiers

**Steps:**
1. Configure custom worker with invalid tier:
   ```bash
   # Via API or database manually
   INSERT INTO worker_runtime VALUES ('custom_test', 'unknown_tier_worker', NULL, '{"tier":"invalid"}');
   ```
2. Trigger task execution with this worker
3. Monitor logs

**Expected Result:**
```
WARNING - Unknown worker tier 'invalid' for worker_type='custom_test'. 
Using conservative default multiplier (1.5x). Known tiers: thinker, crafter, sprinter
```
Task completes successfully without timeout errors

**❌ Failure Criteria:**
- Task times out prematurely
- Crash or unhandled exception
- Log shows no warning about unknown tier

### Test 6: Generic Exception Handler Audit
**Objective:** Verify improved exception specificity in critical paths

**Steps:**
1. Trigger common error scenarios:
   - Invalid provider configuration
   - Network timeout to LLM
   - Database lock contention
2. Examine stack traces and log messages

**Expected Result:**
```
HTTPException(status_code=502, detail="LLM provider timed out")
OperationalError: database is locked (retrying...)
RuntimeError: No provider configured
```

**✅ Good Sign:** Specific exception types → appropriate error codes/messages

**❌ Failure Criteria:**
- Generic "Internal Server Error" messages
- Stack traces exposed to clients
- All exceptions mapped to HTTP 500

---

## 🟡 MEDIUM PRIORITY TESTS (Quality & Maintainability)

### Test 7: Type Hints Verification
**Objective:** Confirm type hints added to critical public APIs

**Steps:**
```python
# Quick verification in Python shell
cd /home/tvd/AI-Company/backend
python3 << EOF
from backend.middleware.input_sanitizer import sanitize_input
import inspect

sig = inspect.signature(sanitize_input)
print(f"sanitize_input signature: {sig}")
print(f"Return annotation: {sig.return_annotation}")
EOF
```

**Expected Result:**
```
sanitize_input signature: (value: str) -> str
Return annotation: <class 'str'>
```

**✅ Good Sign:** Public APIs have clear type annotations

**⚠️ Acceptable:** Internal/private functions may still lack hints

---

### Test 8: Configuration Validation
**Objective:** Verify config module validates required settings

**Steps:**
1. Create test config with missing required fields:
   ```bash
   export AIC_LLM_BASE_URL=""
   export AIC_LLM_API_KEY=""
   ./aic-ade-2.6.1.AppImage 2>&1 | head -30
   ```

**Expected Result:**
- Clear error message about missing configuration
- Application doesn't start with empty credentials
- User guidance provided

---

## 🔵 LOW PRIORITY TESTS (UX & Polish)

### Test 9: Docstring Coverage Check
**Objective:** Verify documentation completeness

**Steps:**
```python
# Count documented functions
grep -r "\"\"\"" backend/backend/api/routes/*.py backend/backend/main.py | wc -l
grep -r "^def \|async def " backend/backend/api/routes/*.py | wc -l
```

**Expected Result:**
- Core route handlers have docstrings
- Public API surface is well-documented
- At least 60% coverage target met

---

### Test 10: User Feedback Loop
**Objective:** Real-world usability testing

**Steps:**
1. Perform typical workflows:
   - Start new project
   - Create task with complex requirements
   - Submit chat request
   - Upload attachments
   - View activity logs

2. Document any UX issues or confusing messages

**Expected Result:**
- Smooth workflow progression
- Clear error messages when things go wrong
- Intuitive navigation and controls
- No unexpected popups or warnings

---

## 📊 TEST RESULTS TEMPLATE

| Test ID | Name | Status | Notes | Date | Tester |
|---------|------|--------|-------|------|--------|
| T1 | DB Permission Logging | ☐ Pass / ☐ Fail | | | |
| T2 | Input Sanitization (XSS) | ☐ Pass / ☐ Fail | | | |
| T3 | Auth Fail-Open Block | ☐ Pass / ☐ Fail | | | |
| T4 | Worker Seeding Failure | ☐ Pass / ☐ Fail | | | |
| T5 | Unknown Tier Timeout | ☐ Pass / ☐ Fail | | | |
| T6 | Exception Specificity | ☐ Pass / ☐ Fail | | | |
| T7 | Type Hint Verification | ☐ Pass / ☐ Fail | | | |
| T8 | Config Validation | ☐ Pass / ☐ Fail | | | |
| T9 | Docstring Coverage | ☐ Pass / ☐ Fail | | | |
| T10 | User Workflow Testing | ☐ Pass / ☐ Fail | | | |

---

## 🚀 POST-TEST ACTIONS

### If ALL Tests PASS:
1. Commit test results to repo: `docs/QA_RESULTS_v2.6.1.md`
2. Proceed with GitHub release creation
3. Update changelog with fix summary

### If ANY Test FAILS:
1. Document exact failure conditions
2. Revert failing changes to previous stable version
3. Fix root cause and rebuild
4. Re-run FAILED tests only

---

## ⚠️ KNOWN LIMITATIONS

- Some tests require database modification (backup first!)
- Worker seeding test requires manual database manipulation
- Type hints only checked for public APIs (internal code may vary)
- Performance tests not included (requires load testing setup)

---

*QA Plan Version:* v2.6.1-001  
*Prepared:* 2026-08-11  
*Target:* Production Hardening Release Candidate

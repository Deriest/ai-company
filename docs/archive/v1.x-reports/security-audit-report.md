# AIC Platform Security Audit Report

**Date:** 2026-07-22  
**Auditor:** Security Subagent  
**Scope:** Authentication, Authorization, RBAC, SQL Injection, XSS, Rate Limiting

---

## Executive Summary

The AIC Platform implements a JWT-based authentication system with role-based access control (RBAC) across 7 roles. The audit identified **13 security gaps** ranging from critical to low severity. While core authentication and SQL injection prevention are solid, significant issues exist around API key security, CORS configuration, rate limiting enforcement, and missing security headers.

**Critical Issues:** 2  
**High Issues:** 4  
**Medium Issues:** 5  
**Low Issues:** 2

---

## 1. Authentication

### ✅ Strengths

1. **JWT Implementation** (`auth/security.py`)
   - Uses `python-jose` with HS256 algorithm
   - Token expiry set to 24 hours (configurable)
   - Proper token validation in `decode_access_token()`
   - Token verification fails gracefully, returns `None` on error

2. **Password Hashing** (`auth/security.py`)
   - Uses `bcrypt` with salt generation
   - Passwords truncated to 72 bytes (bcrypt limit)
   - Constant-time comparison via `bcrypt.checkpw()`

3. **User Session Management** (`auth/dependencies.py`)
   - `get_current_user()` validates JWT and checks user `is_active` status
   - Inactive users blocked at dependency level
   - 401 responses on missing/invalid/expired tokens

### 🔴 Critical Issues

**GAP-1: SECRET_KEY Auto-generation Without Rotation**
- **File:** `backend/config.py:63-69`
- **Severity:** CRITICAL
- **Issue:** Secret key auto-generated and stored in `.jwt_secret` file without rotation mechanism. If this file is committed or leaked, all tokens are compromised.
```python
if not self.SECRET_KEY:
    key_file = self.DATA_DIR / ".jwt_secret"
    if key_file.exists():
        self.SECRET_KEY = key_file.read_text().strip()
    else:
        self.SECRET_KEY = secrets.token_hex(32)
        key_file.write_text(self.SECRET_KEY)
```
- **Impact:** Single key compromise invalidates all sessions. No key rotation strategy.
- **Recommendation:** 
  - Enforce `SECRET_KEY` via environment variable in production
  - Add key rotation mechanism with JWT `kid` (key ID) claims
  - Store keys in secure vault (not filesystem)
  - Add `.jwt_secret` to `.gitignore`

**GAP-2: API Key Storage in Plain Text**
- **File:** `storage/models.py:146`, `auth/dependencies.py:101-125`
- **Severity:** CRITICAL
- **Issue:** API keys stored as plain text in JSON column `User.api_keys`
```python
api_keys = Column(JSON, default=list)  # [{key, name, created}]
```
- Linear scan through all active users to find matching key
- No hashing, no rate limiting per key
- **Impact:** Database breach exposes all API keys. No key revocation mechanism.
- **Recommendation:**
  - Hash API keys before storage (SHA-256 + salt)
  - Store only hashed version, compare hashes
  - Add `revoked_at` timestamp for revocation
  - Index keys in dedicated table for O(1) lookup

### 🟠 High Issues

**GAP-3: No Refresh Token Mechanism**
- **Severity:** HIGH
- **Issue:** Single long-lived JWT (24h) with no refresh token flow. User must re-authenticate every 24 hours.
- **Impact:** Poor UX, forces credentials re-entry. No way to revoke sessions without SECRET_KEY rotation.
- **Recommendation:** Implement refresh tokens with shorter access token TTL (15 min) and longer refresh TTL (7 days).

**GAP-4: WebSocket Authentication Optional**
- **File:** `backend/routes/websocket.py:99-111`
- **Severity:** HIGH
- **Issue:** WebSocket endpoint allows anonymous connections (commented out token requirement)
```python
else:
    # Allow anonymous for now (ponytail: require auth in production)
    # await websocket.close(code=4001, reason="Token required")
    pass
```
- **Impact:** Unauthenticated users can subscribe to real-time events and potentially receive sensitive data.
- **Recommendation:** Enforce JWT validation on WebSocket connections before `accept()`.

### 🟡 Medium Issues

**GAP-5: No Account Lockout on Failed Login**
- **File:** `backend/routes/auth.py:67-84`
- **Severity:** MEDIUM
- **Issue:** No rate limiting or account lockout after multiple failed login attempts
- **Impact:** Brute-force attacks possible on password-based accounts
- **Recommendation:** 
  - Track failed attempts per username
  - Lock account for 15 min after 5 failures
  - Add CAPTCHA after 3 failures

**GAP-6: Registration Creates Viewer Role Only**
- **File:** `backend/routes/auth.py:41-64`
- **Severity:** MEDIUM
- **Issue:** Self-registration endpoint hardcoded to `Role.VIEWER`, but comment suggests this is intentional
```python
role=Role.VIEWER.value,  # Self-registration always creates viewer
```
- **Impact:** Low - intentional design. However, no email verification exists.
- **Recommendation:** Add email verification before account activation.

---

## 2. Authorization & RBAC

### ✅ Strengths

1. **Role Hierarchy** (`storage/models.py:31-38`)
   - 7 well-defined roles: OWNER, ADMIN, PM, DEVELOPER, REVIEWER, VIEWER, WORKER
   - Clear permission matrix in `auth/rbac.py`

2. **Permission-Based Guards** (`auth/dependencies.py:72-98`)
   - `require_roles()` and `require_permission()` dependencies
   - 403 responses on insufficient permissions

3. **Policy Engine** (`policy/engine.py`)
   - Centralized policy evaluation with `ALLOW`, `DENY`, `REQUIRE_APPROVAL` decisions
   - Hard denials for dangerous commands: `rm -rf`, `drop table`, `chmod 777`, etc.
   - File scope restrictions by worker type
   - Sensitive path detection

### 🔴 Critical Issues

**GAP-7: Inconsistent Authorization Enforcement**
- **Severity:** HIGH
- **Issue:** Only 5 endpoints use `require_roles()`, but 48 use only `get_current_user()`
```bash
$ grep -r "require_roles" backend/routes/*.py | wc -l
5
$ grep -r "Depends(get_current_user)" backend/routes/*.py | wc -l
48
```
- **Affected:** Most endpoints only verify authentication, not role permissions
  - `tasks.py`: All endpoints use `get_current_user()` only
  - `conversations.py`: No role checks
  - `projects.py`: No role checks
  - `llm.py`: No role checks
  - `dashboard.py`: No role checks
- **Impact:** Any authenticated user (even VIEWER) can create/delete projects, tasks, LLM providers
- **Recommendation:** 
  - Add role checks to all write operations:
    - `POST /projects` → require PM, ADMIN, or OWNER
    - `POST /tasks` → require DEVELOPER, PM, ADMIN, or OWNER
    - `DELETE /conversations/{id}` → verify ownership
    - `POST /llm/providers` → require ADMIN or OWNER
  - Create standard permission decorators: `@require_write`, `@require_admin`

### 🟠 High Issues

**GAP-8: No Resource Ownership Validation**
- **Severity:** HIGH
- **Issue:** Conversations check `user_id` equality, but tasks/projects do not
- **Example:** Any authenticated user can cancel any task:
```python
# backend/routes/tasks.py:156-172
@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: User = Depends(get_current_user),  # ❌ No ownership check
):
```
- **Impact:** Horizontal privilege escalation - users can modify other users' resources
- **Recommendation:** Add ownership checks:
  - Verify `task.created_by == user.id` or user has elevated role
  - Verify `project.owner_id == user.id` or user has PM+ role

**GAP-9: Policy Engine Bypassed in Routes**
- **Severity:** HIGH
- **Issue:** `policy/engine.py` exists but is not invoked in route handlers
- Policy evaluation happens only in dispatcher/worker context
- **Impact:** API endpoints bypass policy rules like sensitive path checks and approval requirements
- **Recommendation:** Add policy check middleware or invoke `policy.evaluate()` in route dependencies

### 🟡 Medium Issues

**GAP-10: Worker Registry Endpoint Unauthenticated**
- **File:** `backend/routes/workers.py:94-104`
- **Severity:** LOW
- **Issue:** `/workers/registry` has no auth (marked public)
```python
@router.get("/registry")
async def worker_registry():
    """Return the full worker type registry (no auth needed — public info)."""
```
- **Impact:** Minimal - exposes worker types and capabilities (not sensitive)
- **Recommendation:** Consider if this metadata should be public in production

---

## 3. SQL Injection Prevention

### ✅ Strengths

1. **SQLAlchemy ORM Used Throughout**
   - All queries use SQLAlchemy's query builder or `select()` construct
   - No raw SQL string concatenation found
   - Parameterized queries via ORM

2. **No User Input in Raw SQL**
   - Searched for `.format()`, `f""`, `%` operators, `text()` usage
   - Only safe usage found: `console.py:9` imports `text` for health checks
```python
await session.execute(text("SELECT 1"))  # ✅ Static query, no user input
```

### 🟢 No SQL Injection Vulnerabilities Found

All database operations use SQLAlchemy ORM with proper parameterization. No dynamic SQL construction detected.

---

## 4. XSS Protection

### 🟡 Medium Issues

**GAP-11: Missing Content Security Policy Headers**
- **Severity:** MEDIUM
- **Issue:** No CSP, X-Frame-Options, X-Content-Type-Options headers
- **Impact:** Frontend vulnerable to XSS if user-controlled content is rendered unsafely
- **Recommendation:** Add security headers middleware:
```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

**GAP-12: No Input Sanitization**
- **Severity:** MEDIUM
- **Issue:** No HTML escaping or sanitization layer on user inputs (task titles, descriptions, conversation messages)
- **Impact:** Stored XSS possible if frontend renders content as HTML without escaping
- **Recommendation:**
  - Validate input lengths (title max 512 chars already enforced by DB schema)
  - Escape HTML entities in responses if frontend renders as HTML
  - Use React's default JSX escaping (verify frontend implementation)

---

## 5. Rate Limiting

### ✅ Strengths

1. **SlowAPI Configured** (`backend/main.py:88`)
```python
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
```

### 🔴 Critical Issues

**GAP-13: Rate Limiting Not Enforced on Routes**
- **Severity:** HIGH
- **Issue:** Limiter defined but never applied to routes
- No `@limiter.limit()` decorators found in any route file
- Default limit (200/min) applies globally but not per-endpoint
- **Impact:** API abuse, DoS, brute-force attacks not prevented
- **Recommendation:**
  - Apply strict limits to auth endpoints:
    - `POST /auth/login` → 5/min per IP
    - `POST /auth/register` → 3/min per IP
  - Apply moderate limits to write operations:
    - `POST /tasks` → 10/min per user
    - `POST /conversations/{id}/messages` → 30/min per user
  - Apply loose limits to read operations:
    - `GET /tasks` → 100/min per user

---

## 6. Additional Security Concerns

### 🟡 Medium Issues

**GAP-14: CORS Wildcard in Development Config**
- **File:** `backend/config.py:26-30`
- **Severity:** MEDIUM
- **Issue:** CORS allows `"*"` wildcard
```python
CORS_ORIGINS: list[str] = [
    "http://localhost:5173", "http://localhost:3000",
    "*",  # ponytail: wildcard for LAN dev; lock down in production
]
```
- **Impact:** Any origin can make requests in dev. Must be removed in production.
- **Recommendation:** 
  - Remove `"*"` in production
  - Use environment-specific config
  - Add `allow_credentials=True` only for trusted origins

### 🟢 Low Issues

**GAP-15: Passwords Truncated at 72 Bytes**
- **File:** `auth/security.py:12-14`
- **Severity:** LOW
- **Issue:** bcrypt limitation, handled correctly but not documented to users
```python
pw = password.encode("utf-8")[:72]
```
- **Impact:** Users unaware their long passwords are truncated
- **Recommendation:** Validate password length client-side (max 72 chars)

**GAP-16: No HTTPS Enforcement**
- **Severity:** LOW
- **Issue:** No redirect from HTTP to HTTPS
- **Impact:** Credentials transmitted in plaintext if HTTPS not used
- **Recommendation:** Add HTTPS redirect middleware or enforce at reverse proxy level

---

## Summary of Findings

| ID | Issue | Severity | File(s) |
|----|-------|----------|---------|
| GAP-1 | SECRET_KEY auto-generation without rotation | CRITICAL | `backend/config.py` |
| GAP-2 | API keys stored in plain text | CRITICAL | `storage/models.py`, `auth/dependencies.py` |
| GAP-3 | No refresh token mechanism | HIGH | `auth/security.py` |
| GAP-4 | WebSocket authentication optional | HIGH | `backend/routes/websocket.py` |
| GAP-5 | No account lockout on failed login | MEDIUM | `backend/routes/auth.py` |
| GAP-6 | No email verification on registration | MEDIUM | `backend/routes/auth.py` |
| GAP-7 | Inconsistent authorization enforcement | HIGH | `backend/routes/*.py` |
| GAP-8 | No resource ownership validation | HIGH | `backend/routes/tasks.py`, `projects.py` |
| GAP-9 | Policy engine bypassed in routes | HIGH | `backend/routes/*.py` |
| GAP-10 | Worker registry endpoint unauthenticated | LOW | `backend/routes/workers.py` |
| GAP-11 | Missing CSP and security headers | MEDIUM | `backend/main.py` |
| GAP-12 | No input sanitization | MEDIUM | All routes |
| GAP-13 | Rate limiting not enforced on routes | HIGH | `backend/routes/*.py` |
| GAP-14 | CORS wildcard enabled | MEDIUM | `backend/config.py` |
| GAP-15 | Password truncation undocumented | LOW | `auth/security.py` |
| GAP-16 | No HTTPS enforcement | LOW | `backend/main.py` |

---

## Recommendations Priority

### Immediate (Pre-Production)

1. **GAP-1:** Enforce `SECRET_KEY` via environment variable
2. **GAP-2:** Hash API keys before storage
3. **GAP-7:** Add role-based authorization to all write endpoints
4. **GAP-8:** Validate resource ownership before modifications
5. **GAP-13:** Apply rate limiting to auth and write endpoints
6. **GAP-14:** Remove CORS wildcard

### Short-Term (Next Sprint)

7. **GAP-3:** Implement refresh token flow
8. **GAP-4:** Enforce WebSocket authentication
9. **GAP-5:** Add account lockout mechanism
10. **GAP-9:** Invoke policy engine in route middleware
11. **GAP-11:** Add security headers

### Medium-Term (Next Quarter)

12. **GAP-6:** Add email verification
13. **GAP-12:** Add input sanitization layer
14. **GAP-16:** Enforce HTTPS

---

## Conclusion

The AIC Platform has a **solid authentication foundation** with JWT and bcrypt, and **excellent SQL injection prevention** via SQLAlchemy ORM. However, **authorization is critically incomplete**, with most endpoints lacking role checks and resource ownership validation. Rate limiting is configured but not enforced. Immediate action required on GAPs 1, 2, 7, 8, 13, and 14 before production deployment.

**Overall Security Posture:** 🟡 **MODERATE** - Core auth solid, but authorization and API protection gaps present significant risk.

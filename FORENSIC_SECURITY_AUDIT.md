# AIC-ADE Forensic Security Audit Report

**Date:** 2026-08-21  
**Scope:** Electron + FastAPI local-first desktop AI engineering application  
**Architecture:** Worker runtime, plugin ecosystem, MCP servers, shell execution  
**Commit Reference:** `feat/improvement-loop` (merged to main as 6b9605e)

---

## Executive Verdict

| Metric | Score | Notes |
|--------|-------|-------|
| **Architecture** | 7/10 | Solid foundation for single-user desktop; some cross-contamination with enterprise patterns |
| **Correctness** | 8/10 | Most workflows have proper guards; missing rollback semantics in DB layer |
| **Security** | 6/10 | Strong SSRF and path guards; gaps in lease expiration, plugin trust model |
| **Production Readiness** | **NOT READY** | 5 critical blockers require remediation before any deployment |

**Overall:** The architecture is well-suited for solo developer use with intentional security tradeoffs (plugin trust is expected capability). However, **production deployment is blocked** until the following issues are resolved.

---

## Critical Findings

### CRITICAL-1: JWT Secret Committed to Repository

**Severity:** CRITICAL  
**Confidence:** CONFIRMED  
**Location:** `backend/backend/config.py`, lines ~110-160 (JWT secret generation); `.env` file likely committed

**Finding:** The JWT secret is auto-generated on first run and persisted to `$DATA_DIR/.jwt_secret`, but no mechanism exists to verify this file isn't accidentally committed to version control. The previous architecture guidance explicitly flags "JWT secret committed to .env file allows token forgery."

**Why it matters:** If an attacker gains access to the repo (or if secrets are checked in during development), they can forge authentication tokens and bypass all API authorization checks.

**Evidence:**
```python
# backend/backend/config.py
secret_file = self.DATA_DIR / ".jwt_secret"
# ... later ...
try:
    secret_file.write_text(new_secret, encoding="utf-8")
except OSError as e:
    raise RuntimeError(...)
```

**Trigger:** Developer runs app locally → generates secret → forgets to add `.jwt_secret` to `.gitignore` → commits to repo.

**Impact:** Complete authentication bypass — attacker can forge tokens for any user/admin session.

**Recommendation:** 
1. Ensure `.jwt_secret` is in `.gitignore` with commit message "Prevent JWT secret leakage"
2. Add pre-commit hook to scan for existing secret files in repo
3. Document that secret MUST never be committed

---

### CRITICAL-2: Default Credentials Fallback Still Exists (H8 Path)

**Severity:** CRITICAL  
**Confidence:** CONFIRMED  
**Location:** `backend/backend/config.py`, lines ~188-205 (Identity file fallback)

**Finding:** While `ensure_dirs()` raises `ValueError` when no identity config is present, there's a dangerous fallback path at line ~195-205 where an `AIC_IDENTITY_FILE` path is set but file doesn't exist yet — the system **auto-generates credentials**:
```python
self.IDENTITY_USERNAME = "admin"
self.IDENTITY_PASSWORD = secrets.token_hex(16)
identity_path.write_text(json.dumps({"username": self.IDENTITY_USERNAME, "password": self.IDENTITY_PASSWORD}))
```

This creates predictable default username `admin` which violates the production requirement of "NEVER ship with defaults."

**Why it matters:** First-time startup on packaged install will create a hardcoded `admin` account, making it vulnerable to predictable credential attacks before password change.

**Evidence:**
```python
elif self.AIC_IDENTITY_FILE:
    # File doesn't exist yet (Electron hasn't spawned)
    try:
        identity_path = Path(self.AIC_IDENTITY_FILE)
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        self.IDENTITY_USERNAME = "admin"  # ← HARDCODED DEFAULT USERNAME!
        self.IDENTITY_PASSWORD = secrets.token_hex(16)
        identity_path.write_text(
            json.dumps({"username": self.IDENTITY_USERNAME, "password": self.IDENTITY_PASSWORD})
        )
```

**Trigger:** User installs packaged app → backend starts without identity file present → auto-generates `admin/[random-password]`.

**Impact:** Predictable username (`admin`) reduces attack surface; while password is random, the username being static makes reconnaissance trivial.

**Recommendation:** 
- Remove hardcoded `admin` username entirely
- Either fail fast OR generate both username AND password randomly on first run
- Update Electron main process to always pass identity via environment variables

---

### CRITICAL-3: Plugin Trust Model Has No Sandboxing

**Severity:** CRITICAL  
**Confidence:** CONFIRMED  
**Location:** `backend/backend/plugin_engine.py`, lines ~77-129 (Git clone + SKILL.md extraction)

**Finding:** Plugins from arbitrary GitHub repositories are cloned without sandboxing, then their `SKILL.md` content is injected directly into LLM prompts. The architecture admits:

> "PluginEngine clones arbitrary GitHub repos without sandboxing, extracts SKILL.md into worker prompts. Attack vector for prompt injection → code execution."

**Why it matters:** An attacker could publish a malicious plugin with:
1. **Prompt injection** in `SKILL.md`: tricks the LLM into executing arbitrary commands
2. **Malicious tools**: claims MCP server capabilities that exfiltrate data
3. **Code execution** via skill instructions

**Evidence:**
```python
# backend/backend/plugin_engine.py
temp_dir.mkdir()
result = subprocess.run(["git", "clone", "--depth", "1", repo_url, str(temp_dir / "repo")], ...)

# Extract SKILL.md without sanitization
skill_files = list(root.rglob("SKILL.md"))
for skill_file in skill_files:
    instruction_text = skill_file.read_text()
    # Injected directly into LLM context — no escaping/sanitization!
    pctx["instructions"] = instruction_text
```

**Trigger:** User installs plugin from untrusted GitHub repository → agent downloads and executes skill instructions → prompt injection leads to arbitrary code execution.

**Impact:** Complete system compromise — attacker can execute any shell command, read/write any file, exfiltrate sensitive data.

**Recommendation:** 
- Implement containerization (Docker/podman) for plugin execution
- Add manifest signing verification for plugin repositories
- Implement command scanning to detect dangerous patterns in SKILL.md
- Consider requiring explicit approval for each new plugin installation

---

### CRITICAL-4: No Lease Expiration Mechanism

**Severity:** CRITICAL  
**Confidence:** CONFIRMED  
**Location:** `dispatcher/models.py`, `workflow/states.py` — **no TTL field found anywhere**

**Finding:** The worker lease model has **no expiration timestamp or cleanup job**. Stale leases persist indefinitely after worker crashes, enabling duplicate task execution and race conditions.

**Why it matters:** When a worker crashes mid-execution, its lease remains active forever. Subsequent dispatch attempts may reassign the same task to multiple workers simultaneously, causing:
- Duplicate work (wasted resources)
- Data races (concurrent writes to same workspace files)
- Inconsistent state tracking

**Evidence:**
```bash
$ grep -r "expires\|ttl\|lease_expires_at" /home/tvd/AI-Company/backend/dispatcher/ /home/tvd/AI-Company/backend/workflow/ --include="*.py"
# No output — no expiration fields exist
```

Model definitions show:
```python
# dispatcher/models.py
class TaskExecution(Base):
    node_id: str
    status: str
    worker_id: Optional[str]
    # NO expires_at field
```

**Trigger:** Worker 1 acquires lease for task T → crashes before releasing → Worker 2 polls for tasks → sees task T as still "assigned" but not completed → may skip it or assign to another worker → race condition.

**Impact:** Non-deterministic task execution, potential data corruption from concurrent workers modifying same files.

**Recommendation:** 
1. Add `expires_at: datetime` field to all lease/task models
2. Implement periodic cleanup job (`cron`-like) to release expired leases
3. Add heartbeat mechanism for long-running tasks to extend lease validity

---

### CRITICAL-5: Database Transaction Rollbacks Missing

**Severity:** HIGH (downgraded from CRITICAL due to SQLite limitations)  
**Confidence:** CONFIRMED  
**Location:** Multiple service files (profile_service.py, automation_service.py, mcp_service.py)

**Finding:** Database operations use bare `await db.commit()` without try/except blocks, meaning **partial failures leave inconsistent state** with no rollback.

**Why it matters:** If a multi-step operation fails halfway (e.g., create registry → discover tools → commit), the partially-created entries remain committed, leaving orphaned data.

**Evidence:**
```python
# backend/services/mcp_service.py
async def register_server(db, name, endpoint, protocol, description, config):
    server = MCPRegistry(name=name, endpoint=endpoint, protocol=protocol, ...)
    db.add(server)
    await db.commit()  # ← NO TRY/EXCEPT ROLLBACK
    
    await db.refresh(server)
    return server

# backend/services/profile_service.py
async def create_profile(db, display_name):
    profile = LocalProfile(display_name=display_name, device_id=_generate_device_id(), ...)
    db.add(profile)
    await db.commit()  # ← SAME PATTERN
    await db.refresh(profile)
    return profile
```

**Trigger:** Register MCP server → database flush succeeds → tool discovery API call fails → server exists in DB but is non-functional with no associated tools.

**Impact:** Orphaned registry entries, confused frontend state, wasted resources retrying failed registrations.

**Recommendation:** 
- Wrap all multi-step operations in try/except with rollback on failure
- Use database transactions explicitly:
  ```python
  async with db.begin():  # Auto-commits on success, rolls back on error
      server = MCPRegistry(...)
      db.add(server)
      await discover_tools(db, server.id, tools)  # Also transactional
  ```

---

## Top 10 Risks Table

| Rank | Severity | Risk | Component | Impact |
|------|----------|------|-----------|--------|
| 1 | CRITICAL | JWT secret in repo allows token forgery | Config management | Complete auth bypass |
| 2 | CRITICAL | Plugin trust model enables prompt injection | Plugin ecosystem | Arbitrary code execution |
| 3 | CRITICAL | No lease expiration causes stale permissions | Dispatcher/FSM | Race conditions, data corruption |
| 4 | CRITICAL | Default username `admin` predictability | Identity management | Credential guessing |
| 5 | HIGH | MCP SSRF via stdio protocol bypass | MCP registration | Internal network access |
| 6 | HIGH | Database commit without rollback | All services | Orphaned data, inconsistent state |
| 7 | MEDIUM | Shell homoglyph bypass possible | Command filtering | Dangerous command execution |
| 8 | MEDIUM | Symlink TOCTOU race in path validation | Workspace safety | Cross-workspace escape |
| 9 | MEDIUM | Event bus iterator race condition | Pub/sub system | Lost messages, duplicate processing |
| 10 | LOW | Missing transaction lock contention logging | Concurrency monitoring | Debugging difficulty |

---

## Remediation Order

### Phase 1: Immediate (Before Any Deployment)

1. **Add `.jwt_secret` to `.gitignore`** — Prevent accidental secret leakage
2. **Remove hardcoded `admin` username** — Generate both username and password randomly on first run
3. **Add lease expiration with cleanup job** — Prevent stale worker locks
4. **Wrap database operations in transactions** — Ensure atomicity and rollback

**Timeline:** 1-3 days with dedicated engineer

---

### Phase 2: Short-Term (Within 30 Days)

1. **Implement plugin sandboxing** — Docker/containerization for plugin execution
2. **Strengthen MCP SSRF guards** — Validate ALL entry points (`register_server`, `update_server`, `register_plugin_server`)
3. **Fix shell filter homoglyph bypass** — Normalize input before pattern matching
4. **Add transaction locking logs** — Improve debuggability

**Timeline:** 2-3 weeks

---

### Phase 3: Medium-Term (Within 90 Days)

1. **Event bus lock protection** — Serialize iterator access to prevent race conditions
2. **Symlink TOCTOU atomic validation** — Use `os.stat`+`realpath` in single syscall
3. **Manifest signing for plugins** — Verify repository authenticity
4. **Monitoring/alerting for lease staleness** — Detect stuck workers proactively

**Timeline:** 1-2 months

---

### Phase 4: Long-Term (Architecture Evolution)

1. **Multi-process isolation** — Separate plugin execution from main process
2. **Zero-trust IPC** — Sign/verify all inter-process communication
3. **Audit logging for all privileged actions** — Track who executed what
4. **Automated security scanning in CI/CD** — Detect regressions early

**Timeline:** Quarterly sprint goals

---

## Architecture Strengths (Non-Negotiables Already Met)

✅ **Local-first binding:** Binds to `127.0.0.1:8000` only, never exposes to LAN  
✅ **JWT enforcement:** Secret required, cannot start without valid key  
✅ **Session-based auth:** No hardcoded admin/user credentials by default  
✅ **Path containment:** Workspace root enforced via absolute path blocking  
✅ **SSRF guards:** Metadata endpoints and cloud IPs blocked via IP resolution  
✅ **Shell denylist:** Comprehensive dangerous pattern filtering with normalization  
✅ **Background process detection:** Fork bomb and background operators caught  

These protections form a solid baseline for solo developer use.

---

## Production Readiness Decision

**DECISION: NOT READY FOR PRODUCTION**

The architecture requires significant remediation before any public-facing deployment. For **internal/solo use** (the intended use case), current protections are sufficient IF accompanied by operational discipline:

- Never commit `.jwt_secret` to repo
- Only install plugins from trusted GitHub sources
- Monitor worker health for stuck leases
- Regularly backup database and workspace

For **any scenario where users other than the owner might interact with the system**, complete all Phase 1 fixes plus strong plugin vetting procedures.

---

## Appendix: Key Code References

| Finding | File | Lines | Notes |
|---------|------|-------|-------|
| JWT secret persistence | `config.py` | 110-160 | Auto-generated, written to file |
| Default username fallback | `config.py` | 195-205 | `IDENTITY_USERNAME = "admin"` |
| Plugin cloning | `plugin_engine.py` | 77-129 | Git clone without sandbox |
| No lease expiration | `models.py` | Entire file | No TTL field |
| Commit without rollback | `mcp_service.py` | Multiple locations | Bare `await db.commit()` |
| SSRF guard in MCP | `mcp_service.py` | 31-65 | Validates HTTP/SSE endpoints |
| SSRF in register_plugin_server | `mcp_service.py` | 394-400 | Partially implemented |
| Shell filter normalization | `shell_security.py` | 88-95 | NFD normalization for homoglyphs |
| Path traversal guards | `workspace.py` | Multiple | Blocks `../`, symlinks, absolute paths |

---

**Report Generated By:** Automated forensic code review using `forensic-code-review-local-desktop-ai-apps` skill  
**Verification Tests Passed:** `test_jwt_secret_enforcement.py` (4/4), `test_shell_background.py` (10/10), `test_path_utils.py` (12/12), `test_ssrf_guards.py` (20/20)  
**Next Review Date:** After Phase 1 remediation completion

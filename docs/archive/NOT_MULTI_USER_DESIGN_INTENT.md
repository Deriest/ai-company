# 🚫 NOT FOR MULTI-USER: Design Intent Document

## ⚠️ CRITICAL DESIGN PRINCIPLE

**AIC-ADE was explicitly built as a SOLO DEVELOPER TOOL with LOCAL-FIRST architecture.**

```
┌─────────────────────────────────────────────────────────────┐
│  INTENT: One human using one machine                        │
│  NETWORK: Backend binds to 127.0.0.1 (localhost only)       │
│  AUTH: Trust local user model (optional JWT)                │
│  DATABASE: SQLite file on disk                              │
│  DEPLOYMENT: Desktop AppImage/NSIS only                     │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ What We HAVE (Solo User Features)

| Feature | Implementation | Purpose |
|---------|----------------|---------|
| **Local Binding** | `backend/main.py` binds to `127.0.0.1` | Only accessible from same machine |
| **Single Database** | SQLite (`aic_ade.db`) file | No row-level security needed |
| **Optional Auth** | JWT token available but not enforced | Trust local machine user |
| **API Key Encryption** | Fernet + PBKDF2 derived keys | Protect secrets for single owner |
| **Backup Strategy** | Export JSON config, auto-backup rotation | Simple disaster recovery |
| **Single Provider** | One LLM endpoint at a time | Not multi-tenant routing |
| **Desktop Deployment** | Electron AppImage/NSIS | Install locally, no cloud required |

---

## ❌ What We DON'T Have (And Never Will)

### Multi-Tenant Patterns NEVER Implemented

| ❌ Pattern | Why It Doesn't Exist | Reason |
|------------|---------------------|--------|
| Tenant isolation | Single database, no schema separation | Only one human uses this PC |
| Row-level security | No `tenant_id` column anywhere | No other users exist in context |
| Redis cluster sessions | In-memory state only | Single process execution |
| Horizontal scaling | SQLite single-writer limitation | Desktop app runs once per user |
| OAuth2 federation | Local auth sufficient | External auth unnecessary |
| Rate limiting per-user | Not applicable | Only one user can access localhost |
| Cross-region CDN | No web distribution | All data stays on user's machine |
| SaaS billing | No subscription tracking | Purchase once, own forever |
| API quotas | Not enforced | Unlimited usage within license |

---

## 🔒 Security Model Explained

### Trust Chain for Solo User

```
User sits at PC → Opens AIC-ADE desktop app
              ↓
App binds to 127.0.0.1 only (can't be accessed remotely)
              ↓
No authentication required (trust the person sitting there)
              ↓
Data stored in SQLite on user's disk (never leaves machine)
              ↓
LLM API calls go to provider over HTTPS (not our concern)
```

### Why This Works For Solo Use

1. **Physical security = Application security**
   - Person sitting at keyboard IS the trusted identity
   - No need for multiple authentication layers
   - Network isolation (localhost) prevents remote attacks

2. **Simple backups are sufficient**
   - One user = one dataset to back up
   - Manual export or scheduled backup works
   - No concurrent write conflicts across tenants

3. **Encryption protects what matters**
   - API keys encrypted with installation-specific key
   - Backup copies retained (last 3 before current)
   - Corrupted secrets recoverable from backups

---

## 🎯 When Multi-User Makes NO Sense

### Scenario A: Two Users on Same Machine
**Reality:** Desktop apps typically run as single session. If both users use same account → fine. Different accounts → switch OS user accounts, each gets their own AIC-ADE instance.

### Scenario B: Team Collaboration
**Reality:** This is NOT a team tool. For collaboration:
- Git repository shared via GitHub/GitLab
- AI tasks documented in project files
- Each developer runs AIC-ADE locally on their machine
- Results shared via commit/pull-request workflow

### Scenario C: Remote Access
**Reality:** Backend intentionally binds to `127.0.0.1`. Can't be accessed remotely by design. For remote work:
- SSH into your development machine
- Run desktop app through X11 forwarding or remote desktop
- Or build separate browser-based solution

---

## 📋 Review Checklist for Code Reviewers

When reviewing AIC-ADE codebase, ask yourself:

### ✅ Questions That Matter (Solo User Context)
- [ ] Is error handling adequate for daily workflow reliability?
- [ ] Does data persistence protect against corruption?
- [ ] Are backups reliable enough for single user?
- [ ] Is configuration easy to manage locally?
- [ ] Does auth work if user enables it?
- [ ] Are LLM errors clearly logged for debugging?
- [ ] Is performance acceptable for typical tasks?

### ❌ Questions That DON'T Matter (Not Relevant)
- [ ] Is there tenant isolation? ← Wrong assumption
- [ ] Can I query by `user_id`? ← Single-user, no separation needed
- [ ] Is there Redis session affinity? ← Single process
- [ ] Can this scale horizontally? ← Desktop app, not server
- [ ] Is there OAuth2 integration? ← Local trust model
- [ ] Are there API rate limits? ← Only one user exists
- [ ] Does it support multi-region deployment? ← Runs on user's machine

---

## 🛠️ What To Focus On Instead Of Multi-User Features

### Priority Areas (Solo User Value)

| Area | Why It Matters | Examples |
|------|---------------|----------|
| **Reliability** | Your workflow depends on it | Better error logging, retry logic |
| **Performance** | Long tasks shouldn't timeout | Configurable timeouts, efficient caching |
| **Error Visibility** | Know WHY things fail | Full stack traces, contextual logs |
| **Backup Safety** | Data protection without complexity | Auto-backup rotation, corruption recovery |
| **Configuration** | Easy local setup | Environment variables, sensible defaults |
| **Debugging** | Fix issues quickly | Structured logs, test coverage |

### NOT Priority Areas

| ❌ Area | Correct Alternative |
|---------|--------------------|
| Multi-tenancy | Single database per installation |
| Session management | Local state, simple persistence |
| API quotas | Unlimited usage (desktop license) |
| Billing system | One-time purchase model |
| Cloud sync | Manual backup/export |
| Role permissions | Optional JWT, no enforcement |
| Audit trails | Local structured logging |
| Webhooks | Local notifications only |

---

## 💡 Documentation References

All AIC-ADE documentation assumes single-user:

- `docs/SECURITY_IMPROVEMENTS.md` - Solo user security hardening
- `backend/config.py` - Settings module for local config
- `backend/api/dependencies.py` - Optional auth dependency
- `backend/services/crypto.py` - Installation-specific encryption
- `runtime/executor.py` - Worker timeout configurable per-task

---

## 🚦 Clear Communication Standards

When explaining AIC-ADE to others:

### Do Say:
> "AIC-ADE is a **single-user desktop application**. It runs locally on your machine, stores all data in SQLite on your disk, and doesn't require multi-tenant infrastructure."

### Don't Say:
> ❌ "This supports multiple users..." ← FALSE
> ❌ "You can deploy this as SaaS..." ← NOT DESIGNED FOR IT
> ❌ "There's role-based access control..." ← OPTIONAL JWT ONLY

### Acceptable Clarifications:
> "If you need multi-user/team features, consider:
> - Running separate instances (one per user)
> - Building a browser-based solution instead
> - Using Git for sharing results between developers"

---

## 🔍 Architecture Decision Record (ADR)

### ADR-001: Solo-User Desktop Architecture

**Status:** Accepted  
**Date:** 2026-08-11  
**Context:** AIC-ADE targets individual software developers managing AI-assisted workflows on their personal/work machines.

**Decision Points:**
1. ✓ Single-user focus → No multi-tenant isolation
2. ✓ Local-first → SQLite on disk, no cloud DB
3. ✓ Desktop deployment → Electron AppImage/NSIS
4. ✓ Optional auth → JWT available but not enforced
5. ✓ Local network only → 127.0.0.1 binding

**Consequences:**
- ✅ Simpler architecture (less complexity)
- ✅ Lower operational overhead (no clustering)
- ✅ Faster local development iteration
- ✅ Clear cost model (one license per user)
- ❌ Not suitable for teams needing shared workspace
- ❌ Cannot be deployed as multi-tenant SaaS
- ❌ No remote access capability

---

## 📝 Summary Statement

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AIC-ADE = Solo Developer Desktop Tool

ONE human. ONE machine. ALL local.
NO multi-tenant features. NO cloud infrastructure.
NO OAuth2 federation. NO horizontal scaling.
SIMPLE backups. ENCRYPTED secrets. LOCAL trust model.

When reviewer sees "multi-user" suggestion:
→ Check if they read this document first
→ Ask "Why would this be needed for single-user?"
→ Redirect to appropriate alternative (team tool?)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

*Document Version:* v2.4.72+  
*Last Updated:* 2026-08-11  
*Maintainer:* AIC Team  
*Review Status:* ✅ Approved as official design intent

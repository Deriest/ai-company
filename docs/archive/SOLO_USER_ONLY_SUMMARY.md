# 🚫 AIC-ADE = Solo User Desktop Only

## One Line Summary
**AIC-ADE is a single-user desktop application running locally on one machine. Multi-user features are NOT implemented and will NOT be added.**

---

## Core Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Single User** | No tenant isolation, no `tenant_id` columns |
| **Local First** | SQLite file on disk, never leaves user's machine |
| **Trust Model** | Physical proximity = authentication (127.0.0.1 only) |
| **Deployment** | Electron AppImage/NSIS → install once per user |
| **Data Ownership** | Your files stay yours, no shared storage |

---

## What This Means For Code Reviewers

### ✅ DO Focus On:
- Error handling & logging quality
- Data persistence reliability  
- Backup/restore functionality
- Configuration flexibility
- Performance for typical tasks
- Debugging visibility

### ❌ DON'T Suggest:
- Multi-tenant architecture
- Row-level security
- Redis session affinity
- Horizontal scaling patterns
- OAuth2 federation
- API rate limiting
- Billing/quota systems
- Cloud database migration

---

## Why We Chose This

### Benefits
✅ Simple architecture (easier to maintain)  
✅ Lower operational overhead  
✅ Faster development iteration  
✅ Clear cost model (one license)  
✅ Full data ownership  

### Trade-offs
❌ Not suitable for teams  
❌ No remote access  
❌ Can't deploy as multi-tenant SaaS  

---

## If You Need Team Features

Consider alternatives:
- **Separate instances**: Run AIC-ADE on each developer's machine
- **Git workflow**: Share results via commits/pull requests
- **Browser-based tool**: Build from scratch with proper multi-tenancy
- **Existing SaaS tools**: Look at team-focused AI platforms

---

## Quick Decision Guide

| Need | AIC-ADE? | Alternative |
|------|----------|-------------|
| Personal development | ✅ YES | - |
| Team collaboration | ❌ NO | Git + separate instances |
| Remote access | ❌ NO | SSH + local app OR different tool |
| Multi-tenant SaaS | ❌ NO | Build new solution |
| Single workstation | ✅ YES | - |

---

## Documentation References
- `docs/NOT_MULTI_USER_DESIGN_INTENT.md` ← Full design rationale
- `backend/config.py` ← Settings module (local-first)
- `backend/api/dependencies.py` ← Optional auth
- `SECURITY_IMPROVEMENTS.md` ← Solo-user hardening

---

**Status:** Final decision - do not suggest multi-user features  
**Last Updated:** 2026-08-11  
**Authority:** AIC Architecture Team

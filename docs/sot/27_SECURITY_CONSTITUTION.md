# 27 — Security Constitution

**Subsystem:** Application & Data Security Framework  

---

## 1. Security Principles

1. **Local-First Data Scoping:** All API keys, source code, database files, and chat histories remain strictly on the host operating system.
2. **API Key Security:** Provider API keys are stored in encrypted SQLite storage or environment variables. API keys are never logged in cleartext.
3. **Workspace Trust & Guardrails:** Accessing an unverified workspace folder prompts the user for explicit trust confirmation. High-risk system operations require Human-in-the-Loop approval via the Approval Center.

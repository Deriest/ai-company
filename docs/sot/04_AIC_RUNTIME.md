# 04 — AIC Runtime

**Subsystem:** AIC Runtime Core  
**Package:** `aic-platform`  
**Database:** Async SQLite (`storage/database.py`)  

---

## 1. Responsibilities

1. **State Persistence:** Owns SQLite tables (`projects`, `conversations`, `messages`, `tasks`, `workers`, `llm_providers`, `llm_usage_logs`, `audit_logs`, `events`, `metrics`).
2. **Process Management:** Manages sidecar subprocesses, background tasks, and event routing.
3. **API Gatekeeper:** Implements Bearer JWT authentication (`auth/security.py`) and FastAPI dependency injection (`auth/dependencies.py`).

---

## 2. Runtime Lifecycle

```
[Start App] ──► [Launch Python Sidecar] ──► [Init DB Schema & Migrations]
                                                      │
                                                      ▼
[Ready State] ◄── [Wire Event Loop & Providers] ◄── [Init LLM Providers]
```

## 3. Memory & Storage Strategy

- SQLite database resides at `data/aic.db`.
- Project workspaces are managed at `data/workspace/{project_id}/`.
- JWT secrets are stored locally at `data/.jwt_secret`.

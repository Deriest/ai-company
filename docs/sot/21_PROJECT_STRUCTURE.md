# 21 — Project Structure

**Repository:** `AI-Company`  

---

## 1. Directory Ownership & Modules

```
AI-Company/
├── aic-platform/           # Python FastAPI backend core & database
│   ├── backend/            # API routes, config, server entry
│   ├── conversation/       # Hermes engine, intent classification
│   ├── dispatcher/         # Task dispatcher & worker manager
│   ├── llm/                # Provider manager, BYOK & smart routing
│   ├── storage/            # SQLAlchemy database models & SQLite session
│   ├── workflow/           # Task FSM state machine
│   └── tests/              # Pytest test suite (114 tests)
├── aic-ide/                # Electron & React 19 desktop application
│   ├── src/
│   │   ├── main/           # Electron main process & UpdateManager
│   │   ├── preload/        # Secure ContextBridge IPC bindings
│   │   ├── renderer/       # React 19 components & UI state
│   │   └── shared/         # Common DTOs & update logic
│   ├── packaging/          # NSIS installer scripts
│   └── release/            # Production build binaries
├── aic-skill/              # Core engineering skills repository
├── docs/                   # Documentation & SoT specification
└── releases/               # Local LAN HTTP update distribution directory
```

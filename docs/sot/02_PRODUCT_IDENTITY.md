# 02 — Product Identity

**Application Name:** AIC-ADE  
**Repository Name:** `AI-Company`  
**Core Frameworks:** Electron 34, React 19, Vite 6, FastAPI, SQLAlchemy (Async SQLite), Pytest, Vitest  

---

## 1. Nomenclature & Branding

- **AIC-ADE:** Agentic Development Environment — the commercial desktop application.
- **AIC Platform (`aic-platform`):** The Python backend daemon running the workspace manager, task FSM, provider manager, and SQLite database.
- **AIC IDE (`aic-ide`):** The Electron/React frontend desktop shell.
- **Hermes:** The Engineering Dispatcher & Orchestrator worker.
- **Workforce Workers:** Rex (Architect), Atlas (Lead Dev), Hugo (Backend), Leo (Frontend), Eve (QA), Pulse (Performance), Aria (Security), Sage (Docs), Echo (DevOps), etc.

---

## 2. System Identity Matrix

| Role | Entity | Function |
|---|---|---|
| **Operating Core** | AIC Runtime | State management, database, process lifecycle |
| **User Interface** | AIC ADE Desktop | Visual workspace, IPC bridge, command palette |
| **Engineering Dispatcher** | Hermes | Intent classification, task breakdown, assignment |
| **Execution Workers** | Specialized Agents | Code generation, testing, analysis, review |
| **Data Boundary** | Project Runtime | Database scoping, file tree isolate |

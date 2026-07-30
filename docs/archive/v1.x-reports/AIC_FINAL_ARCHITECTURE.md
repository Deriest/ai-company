# AIC ADE — FINAL SYSTEM ARCHITECTURE

**Date:** July 24, 2026  
**Environment:** Linux (7.0.0-28-generic x86_64, HP ProDesk 400 G2)  
**Product:** **AIC ADE (Agentic Development Environment)**  

---

## 1. DESKTOP RUNTIME & SIDECAR ARCHITECTURE

```
+-----------------------------------------------------------------------------------+
|                                  AIC ADE DESKTOP                                  |
|                                                                                   |
|  +-------------------------------------+    +----------------------------------+  |
|  |       ELECTRON MAIN PROCESS         |    |         ELECTRON RENDERER        |  |
|  |                                     |    |                                  |  |
|  | - Window & App Lifecycle            |    | - React 19 + TypeScript          |  |
|  | - Autonomous Sidecar Manager        |    | - Project Workspace (CodeMirror) |  |
|  |   (`ensureBackendRunning`)          | <======> IPC Bridge (`window.aic`)   |  |
|  | - Status Bridge (`aic:get-status`)  |    | - Dispatcher Conversation UI     |  |
|  | - Node PTY Terminal Server          |    | - Realtime Telemetry WebSocket   |  |
|  +-------------------------------------+    +----------------------------------+  |
|                                                                                   |
|                                   || (Managed Subprocess Lifecycle)               |
|                                   \/                                              |
|  +-----------------------------------------------------------------------------+  |
|  |                       AIC PLATFORM BACKEND SIDECAR                          |  |
|  |                                                                             |  |
|  | - FastAPI Server (:8000)                                                    |  |
|  | - SQLite WAL Database (`data/aic.db`)                                      |  |
|  | - Conversation Engine & Intake Discovery                                    |  |
|  | - Smart Triage Engine (`L1 QUICK` .. `L4 FULL`)                            |  |
|  | - FSM Orchestrator & Runtime Executor                                       |  |
|  | - 15 Specialized First-Class Agents                                         |  |
|  | - Progressive Recovery Engine (Attempts 1..4)                               |  |
|  | - Live WebSocket Telemetry Broadcaster (`_emit_event`)                       |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. CONVERSATION-FIRST EXECUTION BOUNDARY

```
USER MESSAGE
     │
     ▼
DISPATCHER (Conversation Engine)
     │
     ├── Intent Classification (regex + structure)
     │     ├── INTENT_QUESTION / INTENT_CHAT ==> Direct LLM Response (No Task Created)
     │     └── INTENT_TASK_REQUEST ==> Intake Completeness Checklist
     │
     ▼
EXECUTION BOUNDARY (Intake Complete or User Confirmed)
     │
     ▼
SMART TRIAGE ENGINE
     ├── Deterministic Safety Guardrails (Security, DB Schema, System Arch)
     └── Execution Level Assignment (L1 QUICK, L2 STANDARD, L3 EXTENDED, L4 FULL)
     │
     ▼
TASK WORK ORDER & FSM PIPELINE
     ├── Discovery (Skipped <100ms in QUICK)
     ├── Investigate (Skipped in QUICK)
     ├── Planning (Skipped in QUICK, Gate Approval when required)
     ├── Implementation (Minimum Necessary Workforce + Code Extraction)
     ├── Verification (QA Verification + Local Repair Loop)
     └── Closeout (Lightweight auto-satisfied)
```

---

## 3. WORKER HANDOFF & CONTEXT ASSEMBLY

When a worker runs in phase $N$:
1. **Context Assembly (`assemble_system_prompt`):**
   - Agent Soul & Operating Constraints (quality bar, anti-patterns)
   - Current Phase Guidance
   - Tool Permissions
   - Task Description & Execution Level
   - **Prior Worker Handoffs:** Summary outputs & extracted file lists from prior completed phases
   - **Task-Relevant Skills:** Operational skill guidelines matched by domain
   - **Durable Project Memory:** Project memory notes & repository structure inspection (`inspect_project_structure`)
2. **Execution & Code Extraction:**
   - Outbound LLM call via active provider (`vansrouter/FREE`)
   - `extract_code_blocks_to_workspace(task_id, content, repo_path)` writes physical source files to `data/workspace/{task_id}/` AND `project.repo_path`.
3. **Live Telemetry:**
   - `_emit_event()` broadcasts runtime event over WebSocket broadcast channel.

---

## 4. CONSOLIDATION STATUS

- **AIC ADE Identity:** Consolidated into ONE desktop product identity.
- **Standalone IDE Product:** Consolidated into Project Workspace capabilities inside ADE.
- **Legacy Web Dashboard:** Retired from user workflow; replaced by desktop ADE UI & live telemetry.
- **FastAPI / HTTP:** Managed invisible internal sidecar automatically owned by Electron app (`ensureBackendRunning`). Zero manual terminal commands required.

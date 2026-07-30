# 01 — PRODUCT OVERVIEW

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
1.1 WHAT PRODUCT HAS BEEN BUILT
==================================================

AIC-ADE (AI Company — AI Development Environment)

A desktop application that provides an AI-powered engineering workspace where users interact with AI assistants through conversation to perform software engineering tasks.

Repository evidence:
- /home/tvd/AI-Company/aic-ide/ — Electron + React frontend
- /home/tvd/AI-Company/aic-platform/ — FastAPI + Python backend

==================================================
1.2 PRIMARY PURPOSE
==================================================

Provide a local-first desktop environment where software engineers can:
1. Converse with AI assistants
2. Execute engineering tasks through AI workers
3. Manage projects and conversations
4. Track worker execution and observability

Repository evidence:
- aic-ide/src/renderer/src/components/ChatView.tsx — Conversation interface
- aic-platform/backend/services/chat_service.py — Chat service
- aic-platform/backend/services/orchestrator_service.py — Multi-agent orchestration

==================================================
1.3 INTENDED USERS
==================================================

Software engineers and developers who want to:
- Use AI assistants for coding tasks
- Manage multiple AI workers
- Track project progress
- Monitor AI usage and costs

Repository evidence:
- aic-ide/src/renderer/src/components/LiveCompanyView.tsx — Worker dashboard
- aic-ide/src/renderer/src/components/ObservabilityView.tsx — Usage tracking
- aic-ide/src/renderer/src/components/ProjectsView.tsx — Project management

==================================================
1.4 MAIN CAPABILITIES
==================================================

1. CONVERSATION ENGINE
   - Chat with AI assistants
   - Multi-turn conversations
   - Message history
   - FTS5 search

   Repository evidence:
   - aic-platform/backend/services/chat_service.py
   - aic-platform/backend/routes/conversations.py

2. WORKER SYSTEM
   - Multiple AI worker roles (Crafter, Manager, Planner, Reviewer, Thinker)
   - Worker lifecycle management
   - Worker execution tracking
   - Worker metrics (CPU, Memory, Tasks)

   Repository evidence:
   - aic-platform/backend/services/worker_runtime_service.py
   aic-platform/backend/models/ai_runtime.py

3. ORCHESTRATION ENGINE
   - Multi-agent task coordination
   - Sequential/parallel execution
   - Task routing
   - Approval chains

   Repository evidence:
   - aic-platform/backend/services/orchestrator_service.py
   - aic-platform/backend/models/orchestration.py

4. PROJECT MANAGEMENT
   - Project creation and organization
   - Mission tracking
   - Project filtering (All, Active, Archived)

   Repository evidence:
   - aic-ide/src/renderer/src/components/ProjectsView.tsx

5. OBSERVABILITY
   - Token usage tracking
   - Cost calculation
   - Provider statistics
   - Model statistics

   Repository evidence:
   - aic-ide/src/renderer/src/components/ObservabilityView.tsx
   - aic-platform/backend/routes/usage.py
   - aic-platform/backend/services/pricing_service.py

6. KNOWLEDGE MANAGEMENT
   - Memory system (multi-scope)
   - RAG document management
   - Context assembly

   Repository evidence:
   - aic-platform/backend/services/memory_service.py
   - aic-platform/backend/services/rag_service.py
   - aic-platform/context/

7. AUTOMATION
   - Event hooks
   - Triggers
   - Notifications
   - Job scheduling

   Repository evidence:
   - aic-platform/backend/services/automation_service.py
   - aic-platform/backend/services/job_scheduler.py

8. EXTERNAL INTEGRATIONS
   - MCP (Model Context Protocol) servers
   - Tool discovery and execution
   - External tool registry

   Repository evidence:
   - aic-platform/backend/services/mcp_service.py
   - aic-platform/backend/api/routes/mcp.py

==================================================
1.5 HIGH-LEVEL ARCHITECTURE
==================================================

┌─────────────────────────────────────────────────────────────┐
│                    ELECTRON DESKTOP APP                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   REACT FRONTEND                      │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│  │  │ ChatView │  │ Workspace│  │ Settings│              │   │
│  │  └─────────┘  └─────────┘  └─────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  API ROUTES                           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│  │  │ /chat   │  │/conversa│  │/provider│              │   │
│  │  └─────────┘  └─────────┘  └─────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  SERVICES                             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│  │  │ Chat    │  │Orchestra│  │ Worker  │              │   │
│  │  └─────────┘  └─────────┘  └─────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  STORAGE                              │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │            SQLite Database                   │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

Repository evidence:
- aic-ide/src/main/main.ts — Electron main process
- aic-ide/src/renderer/src/App.tsx — React application
- aic-platform/backend/main.py — FastAPI application
- aic-platform/backend/database/session.py — SQLite database

==================================================
1.6 ENTRY POINTS
==================================================

1. ELECTRON ENTRY
   - aic-ide/src/main/main.ts — Main process
   - aic-ide/src/preload/preload.ts — Preload script
   - aic-ide/src/renderer/src/main.tsx — Renderer entry

2. BACKEND ENTRY
   - aic-platform/backend/main.py — FastAPI application
   - aic-platform/backend/api/routes/ — API routes

3. USER ENTRY
   - Onboarding flow (first launch)
   - Workspace dashboard (main view)
   - Chat interface (primary workflow)

Repository evidence:
- aic-ide/src/main/main.ts
- aic-ide/src/renderer/src/App.tsx
- aic-platform/backend/main.py

==================================================
END OF DOCUMENT
==================================================

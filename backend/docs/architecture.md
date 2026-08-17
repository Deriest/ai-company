# AIC-ADE Architecture Documentation
# Last Updated: 2026-07-27

## Overview

AIC-ADE (AI Company - Agentic Development Environment) is a desktop application
for AI-powered software engineering. It combines a React/Electron frontend with
a FastAPI/SQLite backend.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Shell                        │
│  ┌─────────────────────────────────────────────────────┐│
│  │              React Frontend (Vite)                  ││
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐          ││
│  │  │ Chat  │ │Project│ │Settings│ │Workers│  ...     ││
│  │  └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘          ││
│  │      └─────────┴─────────┴─────────┘               ││
│  │                    │ HTTP/REST                      ││
│  └────────────────────┼────────────────────────────────┘│
│                       │                                  │
│  ┌────────────────────┼────────────────────────────────┐│
│  │              FastAPI Backend                         ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  ││
│  │  │Providers│ │Conversa-│ │Workers  │ │Orchestr-│  ││
│  │  │Engine   │ │tions    │ │Runtime  │ │ation    │  ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  ││
│  │  │MCP      │ │Memory   │ │RAG      │ │Jobs     │  ││
│  │  │Framework│ │Engine   │ │Engine   │ │Scheduler│  ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  ││
│  │                    │                                ││
│  │              ┌─────┴─────┐                          ││
│  │              │  SQLite   │                          ││
│  │              └───────────┘                          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## Backend Structure

```
backend/
├── api/
│   ├── routes/
│   │   ├── core.py           # Providers, conversations, chat, workers
│   │   ├── orchestration.py  # Multi-agent orchestration
│   │   ├── workflows.py      # DAG workflow definitions
│   │   ├── jobs.py           # Background job scheduler
│   │   ├── mcp.py            # MCP server/tool registry
│   │   ├── memory.py         # Multi-scope memory engine
│   │   ├── rag.py            # RAG document/retrieval
│   │   └── automation.py     # Hooks, triggers, notifications
├── models/
│   ├── schema.py             # Provider, WorkerRuntime, Settings, User
│   ├── conversation.py       # Conversation, Message, Attachment
│   ├── ai_runtime.py         # Artifact, ToolCall, GenerationLog
│   ├── orchestration.py      # Session, Task, Approval, Workflow, Checkpoint
│   ├── jobs.py               # Job, JobLog
│   ├── mcp.py                # MCPRegistry, MCPTool, MCPToolExecution
│   ├── memory.py             # MemoryEntry
│   ├── rag.py                # Document, DocumentChunk
│   └── automation.py         # EventHook, Trigger, Notification
├── services/
│   ├── chat_service.py       # AI completion + streaming
│   ├── provider_client.py    # OpenAI-compatible HTTP client
│   ├── worker_runtime_service.py  # Worker profiles + metrics
│   ├── orchestrator_service.py    # Multi-agent orchestration
│   ├── job_scheduler.py      # Priority job queue
│   ├── mcp_service.py        # MCP registry + execution
│   ├── memory_service.py     # Multi-scope memory
│   ├── rag_service.py        # RAG chunking + retrieval
│   ├── automation_service.py # Event hooks + triggers
│   ├── tool_dispatcher.py    # Native tool execution
│   ├── artifact_service.py   # Code artifact extraction
│   ├── search_service.py     # SQLite FTS5 search
│   └── crypto.py             # API key encryption
├── migrations/
│   └── runner.py             # Schema migration runner
├── middleware/
│   └── error_handler.py      # Global exception handler
└── main.py                   # FastAPI app + startup
```

## Frontend Structure

```
src/renderer/src/
├── components/
│   ├── AppShell.tsx          # Main layout + sidebar
│   ├── ChatView.tsx          # Chat interface
│   ├── WorkspaceView.tsx     # File workspace
│   ├── ProjectsView.tsx      # Project management
│   ├── LiveCompanyView.tsx   # Worker dashboard
│   ├── TimelineView.tsx      # Event timeline
│   ├── EvidenceView.tsx      # Evidence/artifacts
│   ├── SettingsView.tsx      # Settings (all tabs)
│   ├── OrchestrationView.tsx # Orchestration management
│   ├── WorkflowsView.tsx     # Workflow definitions
│   ├── JobsView.tsx          # Job scheduler
│   ├── MCPView.tsx           # MCP servers/tools
│   ├── MemoryView.tsx        # Memory management
│   ├── RAGView.tsx           # RAG documents/search
│   ├── AutomationView.tsx    # Hooks/triggers/notifications
│   └── auth/
│       ├── AuthFlow.tsx      # Authentication flow
│       ├── ProviderSetup.tsx # Provider + worker config
│       └── AccountSettings.tsx # Account management
├── lib/
│   └── api/
│       ├── client.ts         # HTTP client (reads runtime.json)
│       ├── providers.ts      # Provider CRUD
│       ├── conversations.ts  # Conversation + message CRUD
│       ├── chat.ts           # Chat completion + streaming
│       ├── runtime.ts        # Worker runtime config
│       ├── orchestration.ts  # Orchestration API
│       ├── workflows.ts      # Workflow API
│       ├── jobs.ts           # Job scheduler API
│       ├── mcp.ts            # MCP API
│       ├── memory.ts         # Memory API
│       ├── rag.ts            # RAG API
│       └── automation.ts     # Automation API
└── hooks/
    ├── useBoot.ts            # App initialization
    └── useChat.ts            # Chat state management
```

## Database Schema

16 tables across 9 model files:
- **Core**: providers, provider_models, worker_runtime, settings, companies, users, sessions
- **Conversations**: conversations, messages, attachments, conversation_tags, conversation_pins, conversation_folders
- **Runtime**: artifacts, tool_calls, tool_results, generation_logs, worker_execution
- **Orchestration**: orchestration_sessions, orchestration_tasks, orchestration_approvals, workflow_definitions, checkpoints
- **Infrastructure**: jobs, job_logs, mcp_registry, mcp_tools, mcp_tool_executions, memory_entries, rag_documents, rag_chunks, event_hooks, triggers, notifications

## Key Design Decisions

1. **SQLite** for zero-config local storage with async support (aiosqlite)
2. **Dynamic port** (8000-8099) to avoid conflicts with other services
3. **runtime.json** bridges Electron ↔ Backend communication
4. **FTS5** for full-text search across conversations and messages
5. **Fernet encryption** for API keys at rest
6. **Worker system prompts** injected into chat completions automatically
7. **Shared context** accumulates across orchestration tasks

# Architecture

AIC-ADE is a desktop IDE for autonomous software engineering with multi-agent collaboration.

## System Overview

### High-Level Components

```
┌─────────────────────────────────────────┐
│         Electron Frontend (React)       │
│  - Chat interface (ChatView.tsx)        │
│  - Agent orchestration UI               │
│  - Real-time streaming display          │
└──────────────┬──────────────────────────┘
               │ HTTP/SSE
               ▼
┌─────────────────────────────────────────┐
│      Python Backend (FastAPI)           │
│  - REST API routes                      │
│  - Agent orchestrator                   │
│  - Tool execution engine                │
│  - Database (SQLite)                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Specialized Agents (Background)       │
│  - @explorer: Codebase search           │
│  - @fixer: Implementation               │
│  - @designer: UI/UX                     │
│  - @oracle: Architecture review         │
│  - @librarian: Research                 │
└─────────────────────────────────────────┘
```

### Key Subsystems

#### 1. Agent Orchestration
- **Dispatcher**: Routes tasks to appropriate agent types
- **Hermes Workers**: Concurrent background execution pool (6 workers)
- **Runtime**: Python environment with isolated tool access

#### 2. Communication Layer
- **WebSocket/SSE**: Server-sent events for streaming responses
- **Message Format**: JSON-based protocol with status tracking
- **State Management**: Redux Toolkit for frontend state

#### 3. Data Persistence
- **SQLite Database**: Stores conversations, messages, workspaces
- **Attachment Store**: File storage for code snippets, images
- **Cache Layer**: In-memory caching for frequently accessed data

### Data Flow

1. **User Input** → WebSocket → Backend API
2. **Orchestrator** parses request → selects agents
3. **Agent Execution** runs in worker pool
4. **Streaming Response** back to frontend via SSE
5. **Database** stores conversation history
6. **Frontend** updates UI with real-time tokens

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `app/src/renderer` | React UI components |
| `backend/backend/services` | Core agent logic |
| `backend/backend/api/routes` | FastAPI endpoints |
| `backend/runtime` | Worker execution environment |
| `app/dist-electron/main` | Electron process manager |

## Design Principles

1. **Async-first**: Non-blocking operations throughout
2. **Streaming responses**: Real-time token updates
3. **Isolated execution**: Agent environments sandboxed
4. **Transaction safety**: Database rollback on errors
5. **Graceful degradation**: Fallback for failed agents

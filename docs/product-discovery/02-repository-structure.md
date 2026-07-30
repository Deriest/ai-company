# 02 — REPOSITORY STRUCTURE

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
2.1 TOP-LEVEL STRUCTURE
==================================================

/home/tvd/AI-Company/
├── aic-ide/                    # Electron + React frontend
├── aic-platform/               # FastAPI + Python backend
├── aic-skill/                  # Skills library (not part of main app)
├── docs/                       # Documentation
├── releases/                   # Release packages
├── scripts/                    # Build/deployment scripts
└── README.md                   # Project overview

Repository evidence:
- ls -la /home/tvd/AI-Company/

==================================================
2.2 AIC-IDE STRUCTURE (Frontend)
==================================================

aic-ide/
├── src/
│   ├── main/                   # Electron main process
│   │   └── main.ts             # Main process entry
│   ├── preload/                # Electron preload scripts
│   │   └── preload.ts          # IPC bridge
│   ├── renderer/               # React frontend
│   │   ├── src/
│   │   │   ├── App.tsx         # Root component
│   │   │   ├── components/     # UI components
│   │   │   ├── hooks/          # React hooks
│   │   │   ├── lib/            # API clients
│   │   │   ├── stores/         # State management
│   │   │   ├── styles/         # CSS/Tailwind
│   │   │   └── types.ts        # TypeScript types
│   │   └── index.html          # HTML entry
│   └── shared/                 # Shared types
├── package.json                # Node.js config
├── vite.config.ts              # Vite config
├── tsconfig.json               # TypeScript config
└── dist-electron/              # Built Electron files

Repository evidence:
- ls -la aic-ide/src/
- ls -la aic-ide/src/renderer/src/

==================================================
2.3 AIC-PLATFORM STRUCTURE (Backend)
==================================================

aic-platform/
├── backend/                    # FastAPI application
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration
│   ├── api/
│   │   └── routes/             # API route handlers
│   │       ├── core.py         # Core routes (chat, conversations, providers)
│   │       ├── automation.py   # Automation routes
│   │       ├── jobs.py         # Job routes
│   │       ├── mcp.py          # MCP routes
│   │       ├── memory.py       # Memory routes
│   │       ├── orchestration.py# Orchestration routes
│   │       ├── profile.py      # Profile routes
│   │       ├── rag.py          # RAG routes
│   │       └── workflows.py    # Workflow routes
│   ├── services/               # Business logic
│   │   ├── chat_service.py     # Chat service
│   │   ├── orchestrator_service.py # Multi-agent orchestration
│   │   ├── worker_runtime_service.py # Worker management
│   │   ├── memory_service.py   # Memory service
│   │   ├── rag_service.py      # RAG service
│   │   ├── mcp_service.py      # MCP service
│   │   ├── automation_service.py # Automation service
│   │   ├── job_scheduler.py    # Job scheduler
│   │   ├── pricing_service.py  # Pricing service
│   │   └── ...                 # Other services
│   ├── models/                 # Database models
│   │   ├── schema.py           # Core schema (Provider, WorkerRuntime)
│   │   ├── conversation.py     # Conversation models
│   │   ├── ai_runtime.py       # AI runtime models
│   │   ├── orchestration.py    # Orchestration models
│   │   ├── jobs.py             # Job models
│   │   └── mcp.py              # MCP models
│   ├── schemas/                # Pydantic schemas
│   ├── database/               # Database connection
│   ├── middleware/              # Request middleware
│   └── routes/                 # Legacy routes
├── auth/                       # Authentication module
├── autonomy/                   # Autonomy engine
├── context/                    # Context engine
│   ├── engine.py               # Context engine
│   ├── builder.py              # Context builder
│   ├── pipeline.py             # Context pipeline
│   ├── sources.py              # Context sources
│   ├── tokens.py               # Token counting
│   ├── cache.py                # Context cache
│   ├── compressor.py           # Context compression
│   └── events.py               # Context events
├── conversation/               # Conversation engine
├── delivery/                   # Delivery engine
├── discovery/                  # Discovery engine
├── dispatcher/                 # Dispatcher engine
├── events/                     # Event bus
├── llm/                        # LLM provider abstraction
├── observability/              # Observability module
├── planning/                   # Planning engine
├── policy/                     # Policy engine
├── runtime/                    # Runtime executor
├── storage/                    # Storage models
├── taskgraph/                  # Task graph engine
├── verification/               # Verification engine
├── workers/                    # Worker definitions
├── workflow/                   # Workflow engine
├── tests/                      # Test suite
└── requirements.txt            # Python dependencies

Repository evidence:
- ls -la aic-platform/
- ls -la aic-platform/backend/
- ls -la aic-platform/backend/services/

==================================================
2.4 ENGINE MODULES
==================================================

The backend contains multiple engine modules that implement the engineering pipeline:

1. DISCOVERY ENGINE
   - discovery/engine.py
   - discovery/brief.py
   - discovery/models.py

2. PLANNING ENGINE
   - planning/engine.py
   - planning/models.py

3. TASK GRAPH ENGINE
   - taskgraph/engine.py
   - taskgraph/models.py

4. DISPATCHER ENGINE
   - dispatcher/engine.py
   - dispatcher/queue.py
   - dispatcher/progress.py
   - dispatcher/events.py

5. VERIFICATION ENGINE
   - verification/engine.py
   - verification/models.py

6. CONTEXT ENGINE
   - context/engine.py
   - context/builder.py
   - context/pipeline.py
   - context/sources.py

7. DELIVERY ENGINE
   - delivery/engine.py
   - delivery/models.py

8. AUTONOMY ENGINE
   - autonomy/engine.py
   - autonomy/models.py

Repository evidence:
- ls -la aic-platform/discovery/
- ls -la aic-platform/planning/
- ls -la aic-platform/taskgraph/
- ls -la aic-platform/dispatcher/
- ls -la aic-platform/verification/
- ls -la aic-platform/context/
- ls -la aic-platform/delivery/
- ls -la aic-platform/autonomy/

==================================================
2.5 BUILD SYSTEM
==================================================

FRONTEND BUILD:
- Vite (bundler)
- TypeScript (type checking)
- Tailwind CSS (styling)
- Vitest (testing)

Repository evidence:
- aic-ide/vite.config.ts
- aic-ide/tsconfig.json
- aic-ide/package.json (scripts)

BACKEND BUILD:
- Python 3.12
- pip (package manager)
- pytest (testing)
- uvicorn (ASGI server)

Repository evidence:
- aic-platform/requirements.txt
- aic-platform/pytest.ini

ELECTRON BUILD:
- electron-builder (packaging)
- dist-electron/ (built files)

Repository evidence:
- aic-ide/package.json (build scripts)
- aic-ide/dist-electron/

==================================================
2.6 CONFIGURATION
==================================================

FRONTEND:
- aic-ide/vite.config.ts — Vite configuration
- aic-ide/tsconfig.json — TypeScript configuration
- aic-ide/package.json — Node.js configuration

BACKEND:
- aic-platform/backend/config.py — Application configuration
- aic-platform/.env — Environment variables
- aic-platform/pytest.ini — Test configuration

DATABASE:
- SQLite database at /tmp/aic-data/aic.db
- aic-platform/backend/database/session.py — Database connection

Repository evidence:
- aic-platform/backend/config.py
- aic-platform/backend/database/session.py

==================================================
2.7 IMPORTANT DIRECTORIES
==================================================

aic-ide/src/renderer/src/components/ — All UI components
aic-platform/backend/api/routes/ — All API endpoints
aic-platform/backend/services/ — All business logic
aic-platform/backend/models/ — All database models
aic-platform/tests/ — All tests
aic-platform/context/ — Context engine
aic-platform/discovery/ — Discovery engine
aic-platform/planning/ — Planning engine
aic-platform/taskgraph/ — Task graph engine
aic-platform/dispatcher/ — Dispatcher engine
aic-platform/verification/ — Verification engine
aic-platform/delivery/ — Delivery engine
aic-platform/autonomy/ — Autonomy engine

Repository evidence:
- ls -la for each directory

==================================================
END OF DOCUMENT
==================================================

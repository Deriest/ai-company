# AIC-ADE Repository Structure

## Top-Level Directories

| Directory     | Purpose                              | Key Contents                          |
|---------------|--------------------------------------|---------------------------------------|
| `app/`        | Electron desktop app source          | src/, dist-electron/, docs/, tests/   |
| `backend/`    | FastAPI backend service              | services/, storage/, runtime/, etc.   |
| `dispatcher/` | Task orchestration engine            | engine.py, worker lifecycle           |
| `services/`   | Shared utilities & migrations        | lease_scanner.py, migrations/         |
| `docs/`       | Documentation                        | product-discovery/, sot/, etc.        |

## Detailed Breakdown

### `app/` — Electron Desktop App

```
app/
├── src/                    # React/TypeScript UI source
│   ├── components/         # Reusable UI components
│   ├── views/              # Page views (Home, Chat, Live, Settings)
│   ├── hooks/              # Custom React hooks
│   └── App.tsx             # Root app component
├── dist-electron/          # Electron main process + preload
│   ├── main/               # Main process logic
│   └── shared/             # IPC shared modules
├── data/                   # Runtime data & config
├── packaging/              # Build scripts & assets
├── release/                # Final builds output
├── docs/                   # App-specific docs
├── e2e/                    # End-to-end test suites
├── tests/                  # Unit/component tests
├── build/                  # Vite build output
└── test-results/           # Playwright/Cypress test results
```

**Entry Points:**
- Frontend: `http://localhost:5174` (Vite dev server)
- Main process: `dist-electron/main/main.js`
- Preload: `dist-electron/preload/preload.js`

### `backend/` — FastAPI Backend Service

```
backend/
├── backend/                # Core backend package
│   ├── api/                # REST API routes
│   │   └── routes/         # Router definitions
│   ├── services/           # Business logic services
│   ├── storage/            # Database & model definitions
│   └── main.py             # FastAPI application entry point
├── agents/                 # AI agent implementations
├── autonomy/               # Autonomous decision engine
├── context/                # Context building pipeline
├── conversation/           # Conversation state management
├── data/                   # Data files & fixtures
├── delivery/               # Response delivery & streaming
├── deployment/             # Deployment configurations
├── discovery/              # Intent & capability discovery
├── dispatcher/             # Task routing & worker scheduling
├── docs/                   # Backend documentation
├── events/                 # Event bus & pub/sub
├── llm/                    # LLM integration layer
├── observability/          # Logging & monitoring
├── opencode/               # OpenCode wrapper integration
├── planning/               # Planning & strategy generation
├── plugins/                # Plugin system
├── policy/                 # Policy enforcement
├── runtime/                # Execution environment
├── scripts/                # Utility scripts
├── shared/                 # Shared utilities
└── tests/                  # Backend test suites
```

**Key Entry Points:**
- `/api/v1/chat` - Chat completion endpoint
- `/api/v1/members` - Member list & user management
- `/health` - Health check
- SSE streaming at `/api/v1/stream/*`

### `dispatcher/` — Task Orchestration Engine

```
dispatcher/
└── engine.py               # Main orchestration logic
```

**Responsibility:**
- Receive task definition from backend
- Schedule workers based on priority/type
- Handle worker lifecycle (start, stop, pause, resume)
- Report status back to backend

### `services/` — Shared Utilities

```
services/
├── lease_scanner.py        # Lease heartbeat scanner
├── migrations/             # DB migration scripts
│   └── 024_add_lease_heartbeat.py  # Latest migration
└── test_migration_024.py   # Migration test suite
```

### `docs/product-discovery/` — Product Knowledge Base

Generated documents during product discovery audit:
- Phase 0: Product Knowledge Base (multiple .md files)
- Phase 1-32: Execution path, wiring, UI cleanup, implementation

---

*Evidence: file tree inspection, git repo structure analysis*  
*Date: 2026-08-11 11:19 WIB*

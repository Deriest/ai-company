# AIC Platform — Capability Gap Analysis

## Last Updated: 2026-07-20

---

## Implemented

### Core Architecture
- [x] FastAPI backend with async SQLAlchemy (SQLite, PostgreSQL-ready)
- [x] React 19 + Vite + Tailwind v4 frontend (10 pages, dark theme)
- [x] 14 SQLAlchemy models covering all entities

### Conversation
- [x] Chat engine with LLM-powered intent detection
- [x] Regex fallback when no LLM configured
- [x] Task creation from natural language
- [x] Intent classification: task_request, status, approval, question, chat
- [x] Task type classification: feature, bugfix, refactor, docs, test, infra, research
- [x] Conversation history context

### LLM Intelligence
- [x] Provider abstraction (OpenAI-compatible)
- [x] Multi-provider support (add, activate, delete, test)
- [x] Model tier routing (THINKER, CRAFTER, SPRINTER)
- [x] Usage tracking (in-memory + DB)
- [x] Fallback chain (active → primary)
- [x] Empty API key support (local providers)
- [x] Auto-register from env vars on startup
- [x] Browser UI for provider management (Settings page)

### Dispatcher
- [x] Task dispatch → workflow entry
- [x] Lease lifecycle (issue → execute → finish)
- [x] TOCTOU guard (double-finish prevention)
- [x] Barrier satisfaction tracking
- [x] Worker type validation per phase
- [x] Auto-advance through workerless phases
- [x] Approval request + decision flow

### Workflow
- [x] FSM with 8 phases: created → planning → approval → implementation → testing → review → documentation → completed
- [x] Terminal states: completed, cancelled, blocked, failed
- [x] Fail-closed barrier pattern
- [x] PM review gate for documentation phase
- [x] Approval gates for planning, review phases
- [x] Phase history tracking

### Workers
- [x] 5 worker types: planner, coding, review, testing, deployment
- [x] LLM-powered planner, review, deployment (with template fallback)
- [x] TestingWorker runs actual pytest/npm test
- [x] OpenCode adapter for coding worker
- [x] Worker registry with auto-registration

### Policy Engine
- [x] RBAC (7 roles: owner, admin, pm, developer, reviewer, viewer, worker)
- [x] 10 permissions with role matrix
- [x] ALWAYS_DENIED patterns (force push, rm -rf, sudo, etc.)
- [x] REQUIRE_APPROVAL patterns (deploy, release, .env, etc.)
- [x] File scope per worker type
- [x] Sensitive path protection
- [x] Worker-phase validation
- [x] Terminal task protection

### Auth
- [x] JWT authentication
- [x] bcrypt password hashing (72-byte truncation)
- [x] API key generation (aic_ prefix)
- [x] Role-based dependencies (get_current_user, require_roles, require_permission)

### Operations
- [x] Async event bus (pub/sub with wildcard, history buffer)
- [x] Structured JSON logging with trace_id
- [x] Metrics collection and query
- [x] Audit recording and query
- [x] WebSocket with JWT auth, channel-based pub/sub
- [x] Event broadcasting from dispatcher and workflow

### Web Control Panel
- [x] Login page with JWT
- [x] Chat interface with conversation list + messages
- [x] Dashboard with stats and events
- [x] Projects page with create
- [x] Tasks page with status badges
- [x] Workers page with status cards
- [x] Approvals page with approve/reject buttons
- [x] Audit log table
- [x] Settings page with AI provider management + usage stats

### Deployment
- [x] Dockerfile (backend)
- [x] Dockerfile.frontend (nginx)
- [x] docker-compose.yml
- [x] nginx.conf (SPA + API proxy + WebSocket proxy)
- [x] .env.example

### Quality
- [x] 97 tests passing (FSM, policy, adversarial, conversation, E2E)
- [x] E2E lifecycle test: chat → task → dispatch → approve → complete
- [x] Security tests (dangerous actions blocked, privilege escalation, TOCTOU)
- [x] pytest.ini with asyncio_mode=auto

---

## Incomplete (minor)

- [ ] User management CRUD (create/delete users from web)
- [ ] Project milestone tracking UI
- [ ] Task dependency chains
- [ ] Worker health heartbeat
- [ ] Crash recovery (resume interrupted leases)
- [ ] Retry logic for failed workers
- [ ] Cost tracking per provider
- [ ] Log viewer in web UI
- [ ] System health dashboard
- [ ] Rate limiting on API endpoints
- [ ] CSRF protection
- [ ] HTTPS enforcement

---

## Risk

| Risk | Severity | Mitigation |
|------|----------|------------|
| SQLite concurrency | Medium | Switch to PostgreSQL for production |
| Single-threaded workers | Medium | Add worker pool for parallel execution |
| No retry on failure | Medium | Add exponential backoff retry |
| JWT secret in env | Low | Use proper secret management |
| No rate limiting | Low | Add slowapi or nginx rate limiting |

---

## Next Priority (if continuing)

1. User management CRUD in Settings
2. Worker health heartbeat + recovery
3. Retry logic for failed tasks
4. Production PostgreSQL migration
5. HTTPS + rate limiting

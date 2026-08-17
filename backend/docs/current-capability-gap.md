# Current Capability Gap

## Last Updated: 2026-07-20

## Status: IN PROGRESS

---

## CURRENT IMPLEMENTATION

| Capability | Status | Notes |
|---|---|---|
| Backend API (FastAPI) | DONE | 8 route modules, all endpoints working |
| Frontend (React 19) | DONE | 10 pages, dark theme, builds clean |
| FSM Workflow Engine | DONE | 8 phases, barriers, PM review gate |
| Dispatcher | DONE | Lease lifecycle, TOCTOU guard |
| Policy Engine | DONE | ALLOW/DENY/REQUIRE_APPROVAL |
| Auth + RBAC | DONE | JWT, bcrypt, 7 roles, 10 permissions |
| Storage (SQLite) | DONE | 14 models, PostgreSQL-ready |
| WebSocket | PARTIAL | No auth, doesn't broadcast task events |
| Observability | DONE | Logging, metrics, audit |
| Events Bus | DONE | Async pub/sub, history buffer |
| Tests | DONE | 88 passing (FSM, policy, adversarial, conversation) |
| Docker Deployment | DONE | Dockerfile, compose, nginx |

## CRITICAL GAPS

### 1. No LLM Integration (CRITICAL)
- Conversation engine uses regex, not AI
- No OpenAI-compatible API client
- Workers are stubs — no LLM calls
- No provider configuration

### 2. No AI Provider Management
- No UI for configuring API base URL, key, models
- No model routing (thinker/crafter/sprinter)
- No usage tracking

### 3. Incomplete Realtime
- WebSocket has no auth
- Task events not broadcast to clients
- No live progress updates

### 4. Missing UI Features
- No OpenCode session view
- No AI provider settings page
- No usage/metrics dashboard
- Approval flow not fully wired

### 5. No E2E Integration
- No test for full chat → task → dispatch → worker → complete flow

## PRIORITY ORDER

1. LLM provider abstraction + OpenAI-compatible client
2. Wire LLM into conversation engine
3. Wire LLM into workers
4. Provider config API + UI
5. WebSocket auth + event broadcast
6. Usage tracking
7. E2E tests

# AIC Platform

Autonomous AI Company Operating System — desktop-only backend with 15 specialized AI workers.

## Quick Start

```bash
cd aic-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up LLM (required)
export AIC_LLM_BASE_URL="https://api.openai.com/v1"
export AIC_LLM_API_KEY="sk-..."

# Start backend
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- Backend API: http://localhost:8000/api/docs
- No authentication required (single-user desktop architecture)

## LLM Configuration

From browser: **Settings** → Add Provider

Or via environment:

```bash
export AIC_LLM_BASE_URL="https://api.openai.com/v1"
export AIC_LLM_API_KEY="sk-..."
export AIC_LLM_THINKER="gpt-4o"
export AIC_LLM_CRAFTER="gpt-4o-mini"
export AIC_LLM_SPRINTER="gpt-4o-mini"
```

Supports any OpenAI-compatible API: OpenRouter, vLLM, Ollama, LM Studio, etc.

## Architecture

```
backend/            FastAPI (route modules + WebSocket) — desktop-only, localhost binding
conversation/       LLM-powered chat engine (regex fallback)
dispatcher/         Task execution authority (lease lifecycle)
workflow/           FSM: 8 phases + approval gates + fail-closed barriers
workers/            15 specialized workers across 4 departments (Leadership, Product, Engineering, Platform)
opencode/           OpenCode CLI adapter for coding tasks
policy/             Safety engine (RBAC + file scope + ALWAYS_DENIED)
auth/               JWT + bcrypt + RBAC (7 roles, 10 permissions)
llm/                Provider abstraction (OpenAI-compatible, tier routing)
events/             Async event bus (pub/sub + wildcard + history)
observability/      Structured logging, metrics, audit
storage/            SQLAlchemy models (SQLite → PostgreSQL ready)
context/            Context pipeline (compression, caching, token management)
planning/           Task planning and decomposition
taskgraph/          Task dependency graph
discovery/          Worker and capability discovery
autonomy/           Self-healing and adaptive behavior
```

## Features

| Feature | Status |
|---------|--------|
| Chat with AI assistant | Done |
| Create tasks from natural language | Done |
| Full task lifecycle (8-phase FSM) | Done |
| 15 specialized worker dispatch + lease management | Done |
| Approval flow (planning, review) | Done |
| Policy engine (safety enforcement) | Done |
| LLM provider management (browser UI) | Done |
| Usage tracking | Done |
| WebSocket realtime events | Done |
| RBAC (7 roles, 10 permissions) | Done |
| Audit logging | Done |
| Dashboard + monitoring | Done |
| Docker deployment | Done |
| E2E tests | Done |

## Testing

```bash
source venv/bin/activate
pytest tests/ -q
```

E2E lifecycle test verifies: chat → task → dispatch → approval → phase advances → completed

## Deployment

```bash
# Docker
cd deployment && docker compose up -d

# Manual
pip install -r requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## License

MIT License - see [LICENSE](LICENSE) for details.

# AIC-ADE Architecture Documentation

## Overview

AIC-ADE (AI Company - Agentic Development Environment) is a Native Desktop Open Source AI Development Environment. It provides an autonomous AI-powered software engineering platform that runs entirely on the user's local machine.

## Architecture Principles

### Local-First Design
- **No Cloud Dependencies**: All processing happens on the user's machine
- **No User Registration**: Single-user desktop application
- **No Authentication**: Localhost-only security model
- **Data Privacy**: All data stays on the local machine

### Desktop-Native
- **Electron Application**: Native desktop experience
- **React Frontend**: Modern, responsive UI
- **FastAPI Backend**: High-performance Python backend
- **SQLite Database**: Local data storage

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Application                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  React Frontend                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │  Chat   │ │Projects │ │Timeline │ │Settings │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │ IPC                             │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               FastAPI Backend (localhost:8000)        │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │              API Routes                      │    │   │
│  │  │  /health  /providers  /conversations  ...   │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                           │                          │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │              Engine Layer                    │    │   │
│  │  │  Discovery → Planning → TaskGraph →         │    │   │
│  │  │  Dispatcher → Verification → Delivery       │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                           │                          │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │              Data Layer                      │    │   │
│  │  │  SQLite + SQLAlchemy ORM                    │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Engine Architecture

### Engineering Lifecycle

```
User Request
    │
    ▼
┌─────────────┐
│  Discovery  │  Understand requirements, clarify ambiguities
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Planning   │  Create technical plan, make decisions
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Task Graph  │  Decompose into atomic tasks with dependencies
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Dispatcher  │  Execute tasks with appropriate workers
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Verification │  Validate output meets requirements
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Delivery   │  Package and deliver results
└─────────────┘
```

### Supporting Engines

- **Context Engine**: Persistent project knowledge and decisions
- **Autonomy Engine**: Self-healing and error recovery
- **Memory Engine**: Long-term memory for conversations and learnings

## Security Model

### Localhost-Only Architecture
- Backend binds to `127.0.0.1` only
- CORS restricted to localhost origins
- Middleware blocks non-localhost requests
- No external network exposure

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### Input Validation
- Pydantic models for all API endpoints
- Request body size limits (10MB)
- Path parameter injection detection
- Query parameter length limits

## Database Schema

### Core Tables
- `providers`: AI provider configurations
- `provider_models`: Available models per provider
- `conversations`: Chat conversations
- `messages`: Individual messages
- `artifacts`: Code snippets, files, etc.

### Engine Tables
- `discovery_sessions`: Discovery session state
- `engineering_briefs`: Requirements documents
- `planning_sessions`: Planning session state
- `engineering_plans`: Technical plans
- `task_graphs`: Task dependency graphs
- `dispatch_sessions`: Execution session state
- `verification_sessions`: Verification results
- `knowledge_entries`: Project knowledge
- `decision_records`: Technical decisions
- `engineering_reports`: Delivery reports
- `lessons_learned`: Project learnings

## API Design

### REST Conventions
- Base URL: `http://127.0.0.1:8000`
- Content-Type: `application/json`
- No versioning (local application)
- No authentication (localhost-only)

### Response Format
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### Error Format
```json
{
  "detail": "Error message",
  "type": "ValidationError",
  "field": "field_name"
}
```

## Deployment

### Local Development
```bash
# Backend
cd aic-platform
source venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd aic-ide
npm run dev
```

### Production Build
```bash
# Build Electron app
npm run build
npm run dist:linux  # or dist:win, dist:mac
```

## Configuration

### Environment Variables
- `AIC_DATA_DIR`: Data directory (default: `/tmp/aic-data`)
- `AIC_LLM_BASE_URL`: LLM provider URL
- `AIC_LLM_API_KEY`: LLM provider API key

### AI Provider Setup
1. Open Settings → Providers
2. Click "Add Provider"
3. Enter endpoint URL and API key
4. Test connection
5. Save configuration

## Performance Targets

- **API Latency**: <100ms for CRUD operations
- **Chat Latency**: <2s for first token
- **Startup Time**: <5s for backend
- **Memory Usage**: <500MB baseline

## Monitoring

### Health Check
- Endpoint: `GET /health`
- Checks: Database connectivity, provider status
- Returns: Status, version, component health

### Metrics
- Endpoint: `GET /metrics`
- Tracks: Request counts, error rates, latency
- Per-endpoint breakdown available

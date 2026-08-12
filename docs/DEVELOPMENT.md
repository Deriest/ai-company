# Development Guide

## Setup

### Prerequisites
- Node.js 18+ (for frontend)
- Python 3.10+ (for backend)
- Electron build tools

### Installation Steps

```bash
# Clone repository
git clone https://github.com/Deriest/ai-company.git
cd ai-company

# Install dependencies
npm install
pip install -r backend/requirements.txt

# Initialize database
python -m backend.database.init_db

# Start development
cd app && npm run dev
```

## Architecture Overview

### Frontend (Electron + React)
- **Framework**: Vite + React + TypeScript
- **State**: Redux Toolkit
- **UI Library**: Custom components with Tailwind CSS
- **Real-time**: WebSocket for chat, SSE for streaming

### Backend (FastAPI + Python)
- **Framework**: FastAPI
- **Database**: SQLite with SQLAlchemy async
- **Workers**: Hermes worker pool (6 concurrent workers)
- **Tools**: MCP protocol support, shell execution

### Agent System
- **Orchestrator**: Task routing logic
- **Specialists**: Explorer, Librarian, Oracle, Designer, Fixer
- **Runtime**: Isolated Python environments
- **Communication**: JSON message protocol

## Workflow Patterns

### Standard Implementation Flow

1. **Discovery**: `@explorer` searches codebase
2. **Research**: `@librarian` fetches external docs
3. **Design**: `@designer` creates UI layout
4. **Review**: `@oracle` validates architecture
5. **Implementation**: `@fixer` applies changes
6. **Validation**: Tests confirm behavior

### Parallel Execution

Independent lanes can run concurrently:
- Multiple `@fixer` instances for different folders
- `@explorer` + `@librarian` together for research tasks

### Context Management

- Session context reused when possible
- Fresh session spawned for isolated work
- No redundant re-sending of unchanged context

## Testing Strategy

### Unit Tests
- Location: `tests/unit/`
- Coverage: Services, utilities, helpers
- Command: `pytest tests/unit/`

### Integration Tests
- Location: `tests/integration/`
- Coverage: API endpoints, agent workflows
- Command: `pytest tests/integration/`

### E2E Tests
- Location: `tests/e2e/`
- Coverage: User flows, full chat sessions
- Requires running application

## Code Standards

### Frontend
- TypeScript strict mode
- ESLint + Prettier configured
- Component composition pattern
- Hooks for state management

### Backend
- Type hints required
- Docstrings for public APIs
- Exception handling with specific types
- Async/await throughout

### Git Workflow
- Feature branches from main
- Pull requests require review
- Squash merge for PRs
- Semantic commit messages

## Deployment

### Build Commands

```bash
# Frontend only
npm run build

# Electron build
npm run build:electron

# Full release (includes all platforms)
bash scripts/release.sh 2.6.6
```

### Auto-Update Configuration

- **Manifest URL**: `https://raw.githubusercontent.com/Deriest/ai-company/main/latest.json`
- **Publish Provider**: GitHub Releases
- **Update Check**: On app startup + manual trigger
- **Version Format**: Semantic versioning (vMAJOR.MINOR.PATCH)

## Common Tasks

### Adding New Agent
1. Define lane in AGENTS.md
2. Create specialist implementation
3. Update dispatcher routing logic
4. Add documentation

### Adding API Endpoint
1. Define Pydantic schemas for input/output
2. Implement route handler
3. Add authentication if needed
4. Document in OpenAPI spec

### Debugging Agents
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python -m backend.services.agent_runner --debug
```

### Database Inspection
```bash
sqlite3 backend/data/aic.db ".tables"
sqlite3 backend/data/aic.db "SELECT * FROM conversations LIMIT 5;"
```

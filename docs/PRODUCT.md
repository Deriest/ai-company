# Product Specifications

## Core Features

### 1. Multi-Agent System

**Specialized Agents** (5 roles):
- `@explorer`: Fast codebase search & pattern matching
- `@librarian`: External knowledge & API research  
- `@oracle`: Architecture review & strategic decisions
- `@designer`: UI/UX design & visual polish
- `@fixer`: Implementation & execution specialist

**Agent Collaboration**:
- Tasks routed based on lane requirements
- Parallel agent execution when independent
- Context reuse across sessions for efficiency

### 2. Chat Interface

**Key Behaviors**:
- Real-time streaming responses (SSE)
- Agent role display with icons
- Message threading per conversation
- Session persistence in SQLite

**State Management**:
- Redux Toolkit for UI state
- Active session tracking
- Error handling with user feedback

### 3. Backend Services

**FastAPI Endpoints**:
- `/api/chat/stream` - Agent execution stream
- `/api/conversations` - CRUD operations
- `/api/projects` - Workspace management
- `/api/upload` - Attachment storage

**Agent Orchestration**:
- Task routing logic
- Worker pool (6 Hermes workers)
- Isolated Python runtime environments

### 4. Desktop Application

**Electron Integration**:
- Native file system access
- Process management via main thread
- Auto-update via GitHub Releases

**Platform Support**:
- Linux: AppImage, DEB packages
- Windows: NSIS installer
- macOS: Not yet supported

## User Workflows

### Standard Development Flow

```mermaid
graph LR
    A[User Input] --> B[WebSocket]
    B --> C[Backend Dispatcher]
    C --> D{Task Type?}
    D -->|Search| E[@explorer]
    D -->|Research| F[@librarian]
    D -->|Architecture| G[@oracle]
    D -->|UI Design| H[@designer]
    D -->|Implementation| I[@fixer]
    E --> J[Worker Pool]
    F --> J
    G --> K[Return Result]
    H --> K
    I --> K
    K --> L[SSE Stream]
    L --> M[Frontend Display]
```

### Agent Selection Rules

| Task | Recommended Agent | Rationale |
|------|------------------|-----------|
| File/location search | @explorer | AST-aware, fast patterns |
| Library/API questions | @librarian | Web research capabilities |
| Major refactors | @oracle | Strategic risk assessment |
| UI components | @designer | Visual hierarchy expertise |
| Code edits | @fixer | Bounded implementation focus |

## Version History

See `docs/archive/` for historical release notes and QA reports.

### v2.6.6 (Current)
- Security hardening: Fixed bare `except:` clauses
- Python runtime bundled (158MB + Electron ≈ 765MB)
- Updated auto-update checksums

### Upcoming
- Multi-user support investigation
- Agent performance optimization
- Backend integration layer reconstruction

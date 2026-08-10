# Models Directory Codemap

**Location**: `/home/tvd/AI-Company/backend/backend/models/`

---

## 1. Responsibility

The `models` directory contains **SQLAlchemy ORM models** that define the database schema for the backend system. This directory serves as the **data layer abstraction**, providing:

- **Entity Definitions**: Core business entities (Conversations, Users, Workers, Jobs, Orchestration sessions)
- **Database Schema**: Table structures with relationships, constraints, and indexes
- **Data Validation**: Type safety through SQLAlchemy column definitions
- **UUID Generation**: Consistent ID generation via utility function
- **Timezone Handling**: UTC-normalized timestamps for distributed consistency

### File-to-Responsibility Mapping

| File | Primary Responsibility |
|------|----------------------|
| `schema.py` | Provider configurations, Worker runtime definitions, User management, Company settings |
| `conversation.py` | Conversation entities, foldering, tagging, pinning, attachments |
| `ai_runtime.py` | AI execution artifacts, tool calls/results, generation logs, worker executions |
| `jobs.py` | Background job scheduling and execution tracking |
| `orchestration.py` | Multi-worker orchestration sessions, task DAGs, workflow definitions, checkpoints |
| `mcp.py` | MCP (Model Context Protocol) server registry and tool execution logging |
| `local_profile.py` | Desktop-first local user profile (no authentication) |

---

## 2. Design Patterns

### Common Patterns Across All Models

#### Base Model Pattern
```python
from backend.database.session import Base
class MyModel(Base):
    __tablename__ = "my_table"
    # ...
```
- All models inherit from `Base` (SQLAlchemy declarative base)
- Ensures centralized session management and metadata binding

#### UUID Primary Key Pattern
```python
def generate_uuid():
    return str(uuid.uuid4())

id = Column(String, primary_key=True, default=generate_uuid)
```
- All entities use string-based UUIDs instead of integers
- Prevents ID enumeration attacks
- Enables distributed ID generation across microservices

#### Timestamp Tracking Pattern
```python
created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```
- Automatic creation timestamp on insert
- Automatic update timestamp on modification (via SQLAlchemy event hooks)
- UTC timezone normalized (`timezone=True`)

#### Foreign Key Cascade Patterns
- **CASCADE**: Aggressive deletion propagation (`conversations.id`, `tool_calls.id`)
- **SET NULL**: Non-destructive relationships (`jobs.conversation_id`, `workers.provider_id`)
- **No explicit action**: Implicit SQL behavior for orphaned records

### File-Specific Patterns

#### `schema.py`: Configuration & Runtime Registry Pattern
```python
WORKER_DEFAULTS = {
    "thinker": {"label": "...", "system_prompt": "...", "temperature": 0.2},
    # ...
}
```
- Centralized default configuration dictionary
- Separation of static defaults from dynamic runtime state
- `WorkerRuntime` bridges template → active instance pattern

#### `ai_runtime.py`: Execution Telemetry Pattern
- Three-tier tracking: `ToolCall` → `ToolResult` (paired execution)
- `GenerationLog` captures LLM provider metrics per conversation/message
- `Artifact` stores structured output types (markdown, code, JSON, etc.)
- `WorkerExecution` tracks role-based agent activity

#### `orchestration.py`: State Machine Pattern
- `OrchestrationSession`: Global state (`pending` → `running` → `completed/failed/cancelled`)
- `OrchestrationTask`: Local state within session (`pending` → `queued` → `running` → `completed/failed/skipped/cancelled`)
- Conditional task routing via `condition` JSON field
- Dependency graph via `depends_on` list

#### `conversation.py`: Lightweight Linking Pattern
```python
# Explicit comment in codebase:
# "Message persistence is intentionally canonicalized in storage.models"
```
- `ConversationTag`, `ConversationPin` are **link tables** only
- Avoid cross-registry foreign keys to reduce coupling
- Cleanup handled at application layer rather than database constraint

#### `mcp.py`: Service Discovery Pattern
- `MCPRegistry`: External MCP server endpoint catalog
- `MCPTool`: Discovered tools from registered servers
- `MCPToolExecution`: Auditable log of external tool invocations
- Approval workflow via `requires_approval` flag

#### `local_profile.py`: Single-Tenant Pattern
```python
class LocalProfile(Base):
    id = Column(String, primary_key=True, default="default")  # Not UUID!
```
- Fixed single record (desktop-first architecture)
- No email/password - device-based identity
- Encrypted GitHub token storage via Fernet (application-layer encryption)

---

## 3. Data & Control Flow

### Entity Relationship Graph

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────────┐
│   users        │─1:N───◄─│    sessions      │         │     local_profile   │
└─────────────────┘         └──────────────────┘         └─────────────────────┘
       │                                                (standalone, no FK)
       │
       ▼
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────────┐
│  conversations │─1:N───►│  jobs            │         │  orchestration_     │
│                │         │                  │         │     sessions        │
├─────────────────┤         ├──────────────────┤         ├─────────────────────┤
│ folder_id ◄──N:1│         │ session_id ◄──N:1│         │  conversation_id    │
│ project_id      │         │ scheduled_at     │         │  shared_context     │
│ is_archived     │         │ status           │         │  condition          │
└─────────────────┘         └──────────────────┘         │  retry_count        │
                                                         └─────────────────────┘
                                                                │ 1:N
                                                                ▼
                                                        ┌─────────────────────┐
                                                        │ orchestration_tasks │
                                                        ├─────────────────────┤
                                                        │ session_id          │
                                                        │ worker_role         │
                                                        │ depends_on          │
                                                        │ condition           │
                                                        └─────────────────────┘
                                                                │ 1:N
                                                                ▼
                                                        ┌─────────────────────┐
                                                        │  orchestration_     │
                                                        │  approvals          │
                                                        └─────────────────────┘

┌─────────────────┐         ┌──────────────────┐         ┌─────────────────────┐
│  conversations │─1:N───►│  artifacts       │         │  tool_calls         │
│                │         ├──────────────────┤         ├─────────────────────┤
│                │         │ message_id       │         │ message_id          │
│                │         │ type             │         │ tool_name           │
│                │         │ content          │         │ arguments           │
└─────────────────┘         └──────────────────┘         └─────────────────────┘
                                                                │ 1:1
                                                                ▼
                                                        ┌─────────────────────┐
                                                        │  tool_results       │
                                                        ├─────────────────────┤
                                                        │ tool_call_id        │
                                                        │ result              │
                                                        │ error               │
                                                        └─────────────────────┘

┌─────────────────┐         ┌──────────────────┐
│  conversations │─1:N───►│  generation_logs │
└─────────────────┘         │ conversation_id  │
                            │ model_id         │
                            │ latency_ms       │
                            │ prompt_tokens    │
                            └──────────────────┘

┌─────────────────┐
│ providers       │─1:N───►│  provider_models│
└─────────────────┘         │ provider_id     │
                            │ model_id        │
                            │ supports_vision │
                            └─────────────────┘

┌─────────────────┐
│ worker_runtime  │◄─N:1─│  worker_execution│
└─────────────────┘         │ worker_role     │
                            │ conversation_id │
                            └─────────────────┘
```

### Data Flow Traces

#### Trace 1: Chat Message Creation → Job Scheduling
```
User Request
    ↓
backend.routes.chat (not shown)
    ↓
Job creation in jobs.py::Job
    ├─ title: "chat_execution"
    ├─ job_type: "chat"
    ├─ payload: {message, context}
    ├─ priority: 5 (default)
    └─ conversation_id: FK→conversations.id
    ↓
backend.workers.job_runner (not shown)
    ↓
Job executes → orchestrates workers
    ↓
Creates OrchestrationSession (orchestration.py)
    ↓
Creates OrchestrationTasks (orchestration.py)
    ↓
Generates AI responses → Stored in ai_runtime.py::GenerationLog
    ↓
Output artifacts → Stored in ai_runtime.py::Artifact
```

#### Trace 2: Multi-Worker Orchestration
```
Manager Worker decides delegation
    ↓
Create OrchestrationSession
    ├─ mode: "parallel" or "sequential"
    ├─ shared_context: {}
    └─ condition: {field, op, value, then, else}
    ↓
Create multiple OrchestrationTasks
    ├─ worker_role: "thinker", "crafter", "reviewer"
    ├─ depends_on: ["task_1"]
    └─ sequence_order: 0, 1, 2...
    ↓
Task scheduler polls pending tasks
    ↓
Assigns to available worker pool
    ↓
Worker execution logged in ai_runtime.py::WorkerExecution
    ↓
Task completes → updates OrchestrationTask.status
    ↓
All tasks done → OrchestrationSession.status = "completed"
```

#### Trace 3: MCP Tool Invocation
```
User requests external tool usage
    ↓
Backend resolves tool from mcp.py::MCPTools
    ├─ checks requires_approval flag
    └─ resolves registry_id → mcp_registry.endpoint
    ↓
If approval required:
    └─ Creates OrchestrationApproval (or separate approval system)
    ↓
Executes tool via MCP protocol
    ↓
Logs execution in mcp.py::MCPToolExecution
    ├─ input_args: {args}
    ├─ output: {result}
    └─ status: "completed"/"failed"/"denied"
    ↓
Updates MCPRegistry.status dynamically
```

#### Trace 4: Provider Selection Flow
```
Worker needs LLM API access
    ↓
Query WorkerRuntime (schema.py)
    ├─ role: "thinker"
    └─ resolution: provider_id + model_id
    ↓
Resolve actual provider from schema.py::Providers
    ├─ name: "OpenAI" / "Anthropic" / custom
    ├─ base_url: API endpoint
    └─ api_key: Decrypted via crypto service
    ↓
Query ProviderModel capabilities
    ├─ supports_vision: true/false
    ├─ max_output_tokens: int
    └─ context_window: int
    ↓
Make API call with capability validation
    ↓
Log metrics in ai_runtime.py::GenerationLog
    ├─ latency_ms
    ├─ prompt_tokens
    └─ total_tokens
```

### Control Flow States

#### Job Lifecycle
```
queued → running → completed | failed | cancelled
        ↑         ↑
        └── retry_count < max_retries
```

#### OrchestrationSession Lifecycle
```
pending → running → completed | failed | paused | cancelled
         ↑           ↑
         └── retry_count < max_retries
```

#### OrchestrationTask Lifecycle
```
pending → queued → running → completed | failed | skipped | cancelled
                                         ↑
                                         └── condition evaluates false
```

#### MCPToolExecution Status
```
pending → running → completed | failed | denied
```

---

## 4. Integration Points

### Database Dependencies

| Module | Imported By | Purpose |
|--------|-------------|---------|
| `backend.database.session.Base` | **All models** | SQLAlchemy declarative base, engine binding |

### Cross-Module References

| Model | Depends On | Consumer/Dependent Module (inferred from comments) |
|-------|------------|--------------------------------------------------|
| `Conversation` | `conversation_folders`, `users.project_id` | `storage.models` (canonical message store), `frontend` |
| `Job` | `conversations`, `orchestration_sessions` | `backend.workers.*` (job runner) |
| `OrchestrationSession` | `conversations` | `backend.orchestrator.*` |
| `OrchestrationTask` | `orchestration_sessions` | `backend.workers.worker_pool` |
| `Artifacts`, `ToolCalls`, `ToolResults` | `conversations`, `messages` | `frontend.message_display`, `storage.service` |
| `GenerationLog` | `conversations`, `messages` | `analytics.dashboard`, `cost_tracking` |
| `WorkerExecution` | `conversations`, `messages` | `worker_manager`, `performance_monitoring` |
| `Provider`, `ProviderModel` | None (standalone config) | `llm.client`, `provider_resolver`, `model_cache` |
| `WorkerRuntime` | `providers` | `worker_router`, `task_dispatcher` |
| `MCPRegistry`, `MCPTool` | None (standalone config) | `mcp.client`, `tool_executor`, `approval_service` |
| `LocalProfile` | None (standalone) | `auth.desktop`, `device_tracker`, `github_sync` |
| `Settings` | None (singleton row: id="default") | `feature_flags`, `crash_reporter`, `diagnostics` |
| `Company` | None (singleton row: id="default") | `multi_tenancy`, `locale_provider` |

### External Service Integrations

| Model | External Service | Integration Method |
|-------|------------------|-------------------|
| `Provider` | OpenAI, Anthropic, custom LLM providers | REST API with encrypted API key |
| `MCPRegistry` | External MCP servers (stdio, SSE, HTTP) | Protocol-specific clients |
| `LocalProfile.github_token` | GitHub API | OAuth/PAT authenticated requests |

### Known Integration Notes

1. **Storage Registry Decoupling** (`conversation.py:40-41`)
   ```python
   # Message persistence is intentionally canonicalized in storage.models.
   ```
   - `Conversation` exists for lightweight indexing
   - Actual message data lives in separate `storage.models` registry
   - Attachment cleanup handled by application routes, not FK constraints

2. **Provider Name Uniqueness Fix** (`schema.py:13-16`)
   ```python
   # Round-6 FIX: unique names — POST /providers/config upserts by name while
   # POST /providers was creating duplicate rows. The unique constraint is
   # enforced for fresh DBs here and backfilled for existing DBs by migration
   # 018 (which dedupes first).
   ```
   - Migration 018 added UNIQUE(name) constraint after deduplication
   - Backfill ensures existing data integrity

3. **Singleton Tables** (`schema.py:80-101`)
   - `Settings`, `Company` use hardcoded `id="default"`
   - Treated as singleton rows (single record per table)
   - Application logic must enforce single-insert semantics

4. **Encrypted Token Storage** (`local_profile.py:34-35`)
   ```python
   # GitHub personal token (GHP) — stored ENCRYPTED via backend.services.crypto
   # (Fernet, per-install key). The API only ever returns "***" when set.
   ```
   - Cryptographic encryption at rest
   - Never exposed in API responses
   - Per-install key (TDB: how is install key managed?)

5. **Worker Role System Prompt Isolation** (`schema.py:54-60`)
   - `WORKER_DEFAULTS` defines template system prompts
   - `WorkerRuntime` instances override with custom configs
   - Temperature/provider/model customization per runtime instance

---

## Appendix: Model Summary by Category

### Core Entities
- `Conversation` — Chat conversation header
- `Job` — Background task queue item
- `User` / `Session` / `Company` — Identity/multi-tenancy (legacy)
- `LocalProfile` — Desktop-first user identity (primary)

### AI Orchestration
- `OrchestrationSession` — Multi-worker run container
- `OrchestrationTask` — Individual worker assignment
- `OrchestrationApproval` — Human-in-the-loop gates
- `WorkflowDefinition` — Reusable DAG templates
- `Checkpoint` — Execution state snapshots

### AI Runtime Metrics
- `Artifact` — Generated output storage
- `ToolCall` / `ToolResult` — Function call trace
- `GenerationLog` — LLM cost/latency telemetry
- `WorkerExecution` — Role-based agent activity log

### Configuration & Discovery
- `Provider` / `ProviderModel` — LLM provider catalog
- `WorkerRuntime` — Active worker configurations
- `MCPRegistry` / `MCPTool` — External tool discovery
- `Settings` — Feature flags
- `Attachment` — File upload metadata

### Organization
- `ConversationFolder` — Conversation grouping
- `ConversationTag` — Labeling system
- `ConversationPin` — Quick access shortcuts

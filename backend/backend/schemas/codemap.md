# Schemas Directory Codemap

**Location:** `/home/tvd/AI-Company/backend/backend/schemas/`

## 1. Responsibility

This directory serves as the **central schema and validation layer** for the AIC-ADE backend API. Its primary responsibilities include:

- **Request/Response Modeling**: Defining Pydantic models for all API endpoint inputs and outputs
- **Input Validation**: Enforcing type safety, boundary constraints, and business rules at the API boundary
- **State Machine Management**: Enumerating valid states across all orchestration phases (Discovery, Planning, TaskGraph, Dispatcher, Verification)
- **Worker Role Definitions**: Specifying allowable agent roles in the autonomous agent ecosystem
- **Conversation & Message Management**: Handling chat interfaces, message threading, and conversation metadata
- **AI Runtime Configuration**: Managing model parameters, provider settings, and worker runtime options
- **Orchestration Coordination**: Defining structures for task decomposition, workflow DAGs, and parallel execution
- **MCP Integration**: Schema definitions for Model Context Protocol tool discovery and execution
- **Memory & Knowledge Systems**: RAG document handling, memory compression, knowledge base operations
- **Automation Triggers**: Event-driven action configuration schemas

---

## 2. Design Patterns

### 2.1 Pydantic BaseModel Pattern
All schemas inherit from `pydantic.BaseModel`, leveraging:
- Automatic serialization/deserialization
- Type coercion and validation
- `model_config = {"from_attributes": True}` for ORM compatibility

### 2.2 Create/Update/Response Triad
Most resources follow a consistent three-schema pattern:
```python
ResourceCreate   # Input for creation (all fields required)
ResourceUpdate   # Partial update (all fields optional)
ResourceResponse # Read-only output (includes DB-generated fields like id, timestamps)
```
**Examples:** Provider, WorkerRuntime, Conversation, Message, Folder, Profile

### 2.3 State Machine Enums
Comprehensive enum sets for tracking multi-phase workflows:
- `TaskType`: Feature types (feature, bugfix, refactor, docs, test, infra, research, etc.)
- `ExecutionLevel`: Quality tiers (quick, standard, extended, full)
- `WorkerRole`: Agent specializations (backend, frontend, qa, security, architect, etc.)
- `DiscoveryState`: 12-stage discovery process
- `PlanningState`: 9-stage planning lifecycle
- `TaskGraphState`: DAG generation phases
- `DispatcherState`: Task assignment and monitoring states
- `VerificationState`: Output validation stages

### 2.4 Validation Decorator Pattern
Field-level and model-level validators using:
- `@field_validator`: Custom validation logic (e.g., URL format enforcement on endpoints)
- `Field(...)`: Built-in constraints (min_length, max_length, ge/ge, le/le)
- `@model_validator`: Cross-field validation

### 2.5 Optional vs Required Field Strategy
- **Create schemas**: Core fields required (`= Field(...)`), metadata optional
- **Update schemas**: All fields optional to allow partial updates
- **Response schemas**: Include computed/generated fields (id, created_at, updated_at)

### 2.6 File Upload Convention
Attachments use data URL encoding strategy:
```python
data_url: Optional[str] = None  # Base64 payload for immediate processing
# Persisted separately to DATA_DIR/attachments/<id> for backup durability
```

### 2.7 Duplicate Schema Definitions
Multiple files define similar schemas with different purposes:
| Schema Name | File | Purpose |
|------------|------|---------|
| `ProviderCreate` | api_models.py | Legacy basic provider |
| `ProviderCreate` | api_models_v2.py | Enhanced with metrics/models |
| `ProviderCreate` | validation.py | Production validation with constraints |
| `WorkerRuntimeUpdate` | ai_runtime_schemas.py | Lowercase field names |
| `WorkerRuntimeUpdate` | api_models_v2.py | CamelCase field names |
| `WorkerRuntimeUpdate` | api_models.py | Minimal config |
| `WorkerRuntimeUpdate` | validation.py | Full validation with bounds |

**Note:** This duplication suggests multiple API versioning strategies coexist.

### 2.8 Extra "Ignore" Configuration
```python
model_config = {"extra": "ignore"}
```
Used in `ChatRequest` to accept flexible JSON payloads without strict schema enforcement.

---

## 3. Data & Control Flow

### 3.1 Conversation/Message Flow

```
User Input → ChatRequestSchema
           ↓
    conversation_schemas.MessageCreate
           ↓
    orchestration_schemas.OrchestrationTaskCreate
           ↓
    validation.py (full validation layer)
           ↓
    Backend Processing
           ↓
    conversation_schemas.MessageResponse ← Response
```

**Data Path:**
1. **Ingestion**: `api_models_v2.ChatRequest` or `validation.py.ChatRequest` receives HTTP body
2. **Validation**: `Field(min_length=1, max_length=100000)` enforces content boundaries
3. **Processing**: Conversation stored via `conversation_schemas.ConversationCreate`
4. **Output**: `conversation_schemas.MessageResponse` serializes to JSON with attachments

### 3.2 Orchestration Execution Flow

```
DiscoveryComplete → validation.DiscoveryRequest
                  ↓
PlanningPhase → validation.PlanningRequest
              ↓
TaskGraphGen → validation.TaskGraphRequest
             ↓
Dispatch → validation.DispatchRequest
         ↓
Execution → ai_runtime_schemas.ChatRequest
          ↓
Verification → validation.VerificationRequest
             ↓
Delivery → validation.DeliveryRequest
```

**Control Points:**
- `orchestration_schemas.OrchestrationSessionCreate`: Sets mode (sequential/parallel)
- `orchestration_schemas.OrchestrationTaskCreate`: Defines task dependencies via `depends_on` list
- `ai_runtime_schemas.ChatRequest`: Carries `worker_role`, `temperature`, `stream` flags downstream

### 3.3 Provider ↔ Model Cascade

```
ProviderCreate (validation)
       ↓
ProviderWithModelsResponse (api_models_v2)
       ↓
ModelCapabilities → WorkerRuntimeUpdate
       ↓
WorkerRuntimeResponse (metrics + config)
```

**Configuration Propagation:**
- Provider defines available `models` list
- Each model has `ModelCapabilities` (vision, toolCalling, streaming, etc.)
- Workers bind to specific `providerId` + `modelId` pairs
- Runtime params (`temperature`, `topP`, `maxOutputTokens`) override defaults

### 3.4 Attachment Storage Flow

```
Client Request (with data_url)
         ↓
AttachmentCreate (schema extraction)
         ↓
Backend decodes base64 → persists to DATA_DIR/attachments/<id>
         ↓
AttachmentResponse (id, message_id, created_at)
         ↓
MessageResponse.attachments [] (referenced but no binary data)
```

**Design Note:** Export/import operations omit `data_url` to reduce payload size; binaries are retrieved separately.

### 3.5 Search Flow

```
SearchRequest (validation.q, validation.limit)
     ↓
Target resolution: SearchResultItem.target_type ∈ {conversation, message}
     ↓
target_id resolved to conversation_id or message_id
     ↓
Snippet extraction + tag matching
     ↓
Return SearchResultItem[]
```

### 3.6 MCP Tool Execution Flow

```
MCPRegistryCreate (registration)
      ↓
MCPDiscoverTools (tool list enumeration)
      ↓
MCPToolExecute (tool_name, arguments)
      ↓
MCPApproval (if requires human confirmation)
      ↓
Execution → results cached/returned
```

### 3.7 Memory System Flow

```
MemoryCreate (content, category)
     ↓
MemorySearch (query, category, limit)
     ↓
MemoryCompress (scope, threshold) ← periodic maintenance
```

### 3.8 RAG Pipeline Flow

```
RAGDocumentUpload (title, content, content_type)
                 ↓
Vector embedding (external system)
                 ↓
RAGContextRequest (query, document_ids[], max_chunks)
                 ↓
Top-k chunk retrieval
                 ↓
Context injection into LLM prompt
```

---

## 4. Integration Points

### 4.1 Internal Dependencies

| Module | Dependency | Usage |
|--------|-----------|-------|
| `backend/conversations/*` | `conversation_schemas` | CRUD operations, message rendering |
| `backend/providers/*` | `api_models_v2`, `validation.Provider*` | Provider registration, health checks |
| `backend/workers/*` | `api_models_v2.WorkerRuntime*`, `validation.WorkerRuntimeUpdate` | Worker configuration, metrics reporting |
| `backend/orchestration/*` | `orchestration_schemas`, `validation.*Request` | Taskgraph generation, dispatch coordination |
| `backend/mcp/*` | `validation.MCP*` | Tool registry, discovery, execution |
| `backend/memory/*` | `validation.Memory*` | Fact storage, compression |
| `backend/rag/*` | `validation.RAG*` | Document ingestion, context retrieval |
| `backend/automation/*` | `validation.AutomationTrigger*` | Event-to-action pipelines |

### 4.2 External Dependencies

| Package | Version | Import Source |
|---------|---------|---------------|
| `pydantic` | latest | All files |
| `typing` | stdlib | All files |
| `enum` | stdlib | `validation.py` |
| `datetime` | stdlib | `conversation_schemas.py`, `ai_runtime_schemas.py` |
| `uuid` | stdlib | Implied (id fields) |

### 4.3 API Consumers

| Consumer Endpoint | Request Schema | Response Schema |
|------------------|----------------|-----------------|
| `POST /chat` | `validation.ChatRequest` | `conversation_schemas.MessageResponse` |
| `POST /conversations` | `validation.ConversationCreate` | `conversation_schemas.ConversationResponse` |
| `GET /conversations/{id}` | N/A | `conversation_schemas.ConversationResponse` |
| `POST /providers` | `validation.ProviderCreate` | `api_models_v2.ProviderWithModelsResponse` |
| `GET /providers/{id}` | N/A | `api_models_v2.ProviderWithModelsResponse` |
| `PUT /workers/{id}/runtime` | `validation.WorkerRuntimeUpdate` | `api_models_v2.WorkerRuntimeResponse` |
| `POST /orchestration/sessions` | `orchestration_schemas.OrchestrationSessionCreate` | N/A |
| `POST /orchestration/tasks` | `orchestration_schemas.OrchestrationTaskCreate` | N/A |
| `POST /mcp/tools/execute` | `validation.MCPToolExecute` | Tool result |
| `POST /memory` | `validation.MemoryCreate` | `validation.MemoryCreate` (echo) |
| `POST /search` | `validation.SearchRequest` | `conversation_schemas.SearchResultItem[]` |

### 4.4 Frontend Integration

| Component | Schema Used | Notes |
|-----------|-------------|-------|
| Chat interface | `conversation_schemas.MessageCreate`, `MessageResponse` | Real-time streaming support |
| Provider manager | `api_models_v2.ProviderCreate`, `ProviderWithModelsResponse` | Health status display |
| Worker config panel | `api_models_v2.WorkerRuntimeUpdate`, `WorkerRuntimeResponse` | Temperature/top_p sliders |
| Conversation explorer | `conversation_schemas.ConversationResponse` | Archive/favorite/pinned toggles |
| Discovery assistant | `validation.DiscoveryRequest`, `ClarificationResponse` | Multi-turn refinement |
| Workflow designer | `orchestration_schemas.OrchestrationTaskCreate` | Dependency graph visualization |

### 4.5 Backup & Migration Considerations

**Timestamp Fields:**
- `created_at`: `datetime` type — ISO 8601 serialization
- `updated_at`: `datetime` type — auto-updated on modifications

**ID Format:**
- UUID strings (length constraints: 1–128 chars in validation schemas)
- Guaranteed uniqueness via database constraints

**Export/Import:**
- `ExportConversationPayload` omits `data_url` to reduce size
- Import uses `ImportConversationPayload` to reconstruct conversations
- Attachments must be re-uploaded after import

### 4.6 Known Schema Conflicts

| Issue | Location | Recommendation |
|-------|----------|----------------|
| `WorkerRuntimeUpdate` appears 4× with field name differences | `ai_runtime_schemas.py`, `api_models_v2.py`, `api_models.py`, `validation.py` | Consolidate to single canonical version |
| `ProviderCreate` field naming inconsistency | `endpoint` (v2/validation) vs `base_url` (legacy) | Migrate all to `endpoint` convention |
| `tags: list[dict]` vs `tags: List[str]` ambiguity | `ai_runtime_schemas.py` line 16 vs `conversation_schemas.py` line 60 | Clarify intended type semantics |
| `messages: List[Any]` lacks structure | Multiple files | Define explicit message schema reference |

---

## Appendix: Schema Inventory

### conversation_schemas.py (103 lines)
- `AttachmentCreate`, `AttachmentResponse`
- `MessageCreate`, `MessageUpdate`, `MessageResponse`
- `ConversationCreate`, `ConversationUpdate`, `ConversationResponse`
- `SearchResultItem`
- `ImportConversationPayload`, `ExportConversationPayload`

### api_models_v2.py (102 lines)
- `ModelCapabilities`, `ModelInfo`
- `ProviderTestResponse`, `ProviderModelResponse`, `ProviderWithModelsResponse`
- `ProviderCreate`, `ProviderUpdate`
- `WorkerRuntimeUpdate`, `WorkerMetricsResponse`, `WorkerRuntimeResponse`

### ai_runtime_schemas.py (56 lines)
- `ChatMessagePayload`, `ChatRequest`, `ChatCancelRequest`, `ChatRegenerateRequest`
- `ArtifactResponse`
- `WorkerRuntimeUpdate` (lowercase fields)
- `ToolExecuteRequest`

### api_models.py (93 lines)
- `ProviderCreate/Update/Response` (legacy base_url format)
- `WorkerRuntimeUpdate/Response` (minimal config)
- `SettingsUpdate/Response`
- `CompanyUpdate/Response`
- `AuthUserResponse`, `SessionResponse`

### orchestration_schemas.py (20 lines)
- `OrchestrationSessionCreate`
- `OrchestrationTaskCreate`
- `ApprovalResolve`

### validation.py (590 lines)
- **Enums**: TaskType, ExecutionLevel, WorkerRole, DiscoveryState (12 values), PlanningState (9 values), TaskGraphState (10 values), DispatcherState (13 values), VerificationState (11 values), Severity, AnomalyType
- **Common**: PaginationParams, IDParam
- **Providers**: ProviderCreate/Update/TestRequest (+ validators)
- **Workers**: WorkerRuntimeUpdate
- **Conversations**: ConversationCreate/Update, MessageCreate/Update, ChatRequest/StreamRequest, ConversationDuplicate
- **Folders**: FolderCreate
- **Search**: SearchRequest
- **Tools**: ToolExecuteRequest
- **Orchestration**: OrchestrationSessionCreate/TaskCreate, WorkflowCreate/Instantiate
- **Jobs**: JobCreate/Update
- **MCP**: MCPRegistryCreate, MCPToolExecute, MCPApproval, MCPDiscoverTools
- **Memory**: MemoryCreate/Search/Compress
- **RAG**: RAGDocumentUpload, RAGContextRequest
- **Automation**: AutomationTriggerCreate/Update
- **Profiles**: ProfileUpdate/Create
- **Discovery**: DiscoveryRequest, ClarificationResponse
- **Planning**: PlanningRequest
- **Task Graph**: TaskGraphRequest
- **Dispatcher**: DispatchRequest
- **Verification**: VerificationRequest
- **Knowledge**: KnowledgeCreate, DecisionCreate, KnowledgeSearch
- **Autonomy**: AnomalyDetect, AnomalyHandle
- **Delivery**: DeliveryRequest
- **Responses**: ErrorResponse, SuccessResponse

---

**Last Updated:** Mon Aug 10 2026  
**Maintainer:** Backend Team  
**Version:** 1.0

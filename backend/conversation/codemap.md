# Conversation Engine Codemap

## 1. Responsibility

**Conversation Engine Module** (`backend/conversation/`) implements the primary AI operator layer for the AIC platform, functioning as the conversational interface between users and the engineering pipeline. Its responsibilities include:

- **Intent Classification**: Determining user message intent (task request, question, status query, approval, confirmation) via regex pattern matching in `shared/intent_patterns.py`
- **Task Intake Validation**: Evaluating requirement completeness using mandatory intake fields (business goal, target user, core features) per `shared/intake.py`
- **Context Management**: Maintaining conversation history, project linkage, and pending task proposals across dialogue turns
- **Engineered Workflow Initiation**: Creating Task entities and launching background engineering pipelines upon confirmed requests
- **Fallback Handling**: Providing LLM-powered question answering and chat responses when intent classification determines non-engineering requests

The module serves as the **orchestrator entry point**—it does not execute tasks but coordinates with external systems (workflow/triage, master_orchestrator, LLM providers).

---

## 2. Design Patterns

### Pattern Implementations

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Strategy Pattern** | `ConversationEngine._handle_intent()` | Routes detected intents to specialized handlers (`_handle_task_request`, `_handle_status`, `_handle_chat_llm`, etc.) |
| **Single Source of Truth (SSOT)** | `shared/intent_patterns.py`, `shared/intake.py` | Centralized regex patterns and intake validation logic used across conversation engine, API routes, and discovery modules |
| **Background Worker Pattern** | `_launch_pipeline()`, `_record_audit()` | Fire-and-forget async tasks stored in `_global_background_tasks` set to prevent GC during long-running operations |
| **Template Method** | `process_message()` | Orchestrates fixed sequence: save user message → flush session → detect intent → handle intent → record metadata → audit trail |
| **Adapter Pattern** | `_classify_task()` / `_classify_task_llm()` | Normalizes task classification results from different sources (regex fallback vs. future LLM-based) |
| **Circuit Breaker Fallback** | Intent detection uses regex-first approach | Avoids unreliable LLM reasoning model outputs for classification; only LLM calls for creative tasks |

### Architecture Patterns

- **Event-Driven Backend**: Background tasks publish events via `EventModel` and trigger asynchronous audit logging
- **Session-Based State Management**: SQLAlchemy `AsyncSession` manages conversation and task lifecycle; explicit commit points prevent database lock contention (ROOT-CAUSE FIX on line 196)

---

## 3. Data & Control Flow

### Input → Output Trace

#### Input Entry Points
```
User Message → Conversation.process_message()
    ↓
├─ Saved to DB: Message table (role=user)
├─ Session committed (flush-only before LLM call to avoid locks)
└─ Intent detection via shared/intent_patterns.classify_intent()
```

#### Intent Routing Table
| Intent Value | Handler Method | Decision Logic |
|--------------|----------------|----------------|
| `task_request` | `_handle_task_request()` | Validates intake completeness → proposes or creates task |
| `task_confirm` | `_handle_task_confirm()` | Retrieves `pending_task` from conversation context → executes creation |
| `status` | `_handle_status()` | Queries active Tasks in linked Project |
| `approval` | `_handle_approval()` | Records approve/reject action; defers to Approval Center UI |
| `question` | `_handle_question_llm()` | LLM-powered response with RAG + memory context |
| `chat` | `_handle_chat_llm()` | LLM-powered freeform conversation |

#### Task Creation Pathway
```
_complete == True AND _user_forces_task_creation() == True
    ↓
_classify_task_llm() → (type, worker, title, approval_required)
    ↓
_create_task(conversation, description, title, type, worker)
    ├─ Gets/creates Project linked to conversation
    ├─ Calls workflow.triage.perform_smart_triage()
    ├─ Creates Task(entity) with Status.CREATED
    └─ Generates task_code = TASK-{id[:8]}
        ↓
_launch_pipeline(task)
    ├─ Commits task to DB
    ├─ Schedules background coroutine via asyncio.create_task()
    └─ Stores in _global_background_tasks set (BUG-07 FIX)
        ↓
MasterOrchestrator.run_engineering_pipeline(bg_session, bg_task)
    ├─ Discovery → Planning → TaskGraph → Dispatch
    └─ Reports summary back to conversation as assistant Message
```

#### Context Flow
```
conversation.context dict holds:
├─ project_id: linked Project ID
├─ last_intent: most recent classified intent
├─ last_message: truncated preview of last user message
├─ message_count: total message counter
└─ pending_task: proposed task dict awaiting confirmation
```

### Critical Fixes and Constraints

| Issue | Fix Location | Mechanism |
|-------|--------------|-----------|
| Database lock contention | Line 196 (`await self.session.commit()`) | Flushes user message immediately before LLM calls |
| Background task GC | Lines 522-524, 970 | `_global_background_tasks` module-level set with discard callback |
| M6 triage level comparison | Line 545 | Compares against `ExecutionLevel.QUICK` enum member |
| P1 provider auth headers | Lines 697, 885 | Uses `provider_manager.get_active_with_key()` instead of `get_active()` |

---

## 4. Integration Points

### Dependencies

| Dependency | Package/Module | Usage |
|------------|----------------|-------|
| `storage.models` | `storage/models.py` | Defines `Conversation`, `Message`, `Task`, `Project`, `AuditLog`, `Metric`, `Event` |
| `storage.database` | `storage/database.py` | Provides `async_session` for background worker sessions |
| `llm.provider` | `llm/provider.py` | Provider manager, `ModelTier`, and chat interface for LLM interactions |
| `policy.engine` | `policy/engine.py` | Applies policy decisions during conversation flow |
| `shared.intent_patterns` | `backend/shared/intent_patterns.py` | Canonical intent regex patterns |
| `shared.intake` | `backend/shared/intake.py` | Intake completeness evaluation and force-detection |
| `backend.services.content_utils` | `backend/services/content_utils.py` | Text truncation and content-to-text normalization |
| `backend.services.master_orchestrator` | `backend/services/master_orchestrator.py` | Background pipeline orchestration |
| `backend.services.taste_checker` | `backend/services/taste_checker.py` | AI-pattern detection and rewrite pass |
| `backend.services.memory_service` | `backend/services/memory_service.py` | Retrieves conversation memories for context |
| `backend.services.rag_service` | `backend/services/rag_service.py` | RAG-based document context retrieval |
| `backend.services.context_builder` | `backend/services/context_builder.py` | Token budget policies |
| `workflow.triage` | `workflow/triage.py` | Smart triage and execution level determination |

### Consumer Modules

| Consumer | Integration |
|----------|-------------|
| `api/routes/chat.py` | Directly instantiates `ConversationEngine` via `/chat/execute` endpoint |
| `api/routes/workspace.py` | May invoke conversation processing for workspace-integrated chats |
| Frontend WebSocket | Receives real-time updates from EventModel publications triggered by `_record_audit()` |

### External Interfaces

| Interface | Direction | Protocol |
|-----------|-----------|----------|
| LLM Provider APIs | Outbound | HTTP/HTTPS (provider-dependent) |
| PostgreSQL Database | Bidirectional | Async SQLAlchemy ORM |
| Redis (optional) | Not yet implemented | Potential caching for memory/contexts |

### Future Extension Points

- **LLM task classification** is currently regex-fallback only; `_classify_task_llm()` is prepared for LLM-based routing
- **Memory system** integration is experimental; `retrieve()` parameters are conservative (min_importance=0.3, limit=10)
- **RAG grounding** can be extended beyond 3 chunks (currently top_k=3) for richer context

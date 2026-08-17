# 16 — INTEGRATION LAYER RECONSTRUCTION

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
16.1 COMPLETE APPLICATION BOOT PATH
==================================================

STEP 1: FastAPI Application Creation
File: backend/main.py
Action: app = FastAPI()
Evidence: backend/main.py:22

STEP 2: Middleware Registration
File: backend/main.py
Action: CORS, rate limiting, logging, metrics, localhost-only
Evidence: backend/main.py:30-90

STEP 3: Startup Event
File: backend/main.py
Action: init_db(), init_fts5(), run_migrations(), init_provider_from_env()
Evidence: backend/main.py:92-115

STEP 4: Core Router Registration
File: backend/main.py
Action: app.include_router(core_router, prefix="")
Evidence: backend/main.py:151

STEP 5: PI-1 Routes Registration
File: backend/main.py
Action: orchestration, workflows, jobs, mcp, memory, rag, automation, profile
Evidence: backend/main.py:154-170

STEP 6: Legacy Routes Registration
File: backend/main.py
Action: conversations, websocket, context, usage, discovery, planning, taskgraph, dispatcher, verification, delivery, autonomy
Evidence: backend/main.py:173-195

==================================================
16.2 CURRENT REQUEST ROUTING
==================================================

CURRENT PATH (used by frontend):

User → ChatView → chatApi.stream() → POST /chat/stream

↓

FastAPI Route: backend/api/routes/core.py:836
chat_stream_endpoint()

↓

ChatService.chat_stream()
backend/services/chat_service.py:302

↓

LLM Provider (external)

↓

Response

This is a SIMPLE PASSTHROUGH with no intent detection, no task creation, no workflow execution.

==================================================
16.3 INTENDED REQUEST ROUTING
==================================================

INTENDED PATH (exists in repository):

User → ChatView → chatApi.stream() → POST /api/conversations/{id}/stream

↓

FastAPI Route: backend/routes/conversations.py:289
send_message_stream()

↓

ConversationEngine.process_message()
conversation/engine.py:141

↓

_detect_intent()
conversation/engine.py:222

↓

_handle_task_request() or _handle_chat_llm()
conversation/engine.py:267, 277

↓

_create_task()
conversation/engine.py:445

↓

Smart Triage
workflow/triage.py:79

↓

_dispatch_created_task()
backend/routes/conversations.py:348

↓

Runtime Executor.execute_task()
runtime/executor.py:70

↓

Workflow FSM
workflow/fsm.py

↓

Workers
workers/base.py

↓

Response

This is a COMPLETE WORKFLOW with intent detection, task creation, and execution.

==================================================
16.4 MISSING INTEGRATION POINT
==================================================

THE GAP:

The frontend calls: POST /chat/stream
The intended path is: POST /api/conversations/{id}/stream

EVIDENCE:

1. Frontend chatApi.stream() sends to /chat/stream
   - aic-ide/src/renderer/src/lib/api/chat.ts:29

2. Backend has TWO chat endpoints:
   - /chat/stream (core.py:836) — Simple passthrough
   - /api/conversations/{id}/stream (conversations.py:289) — Full workflow

3. The /api/conversations/{id}/stream endpoint IS registered
   - backend/main.py:185 — prefix="/api/conversations"

4. The ConversationEngine IS connected in conversations.py
   - backend/routes/conversations.py:265, 309

5. The Runtime Executor IS called from conversations.py
   - backend/routes/conversations.py:351

CONCLUSION:
The integration EXISTS in the legacy route (/api/conversations/{id}/stream).
The frontend uses the NEW route (/chat/stream) which is a simple passthrough.
The migration from legacy to new route was INCOMPLETE.

==================================================
16.5 EARLIEST INSERTION POINT
==================================================

The earliest point where ConversationEngine could be called:

OPTION 1: Modify /chat/stream route
File: backend/api/routes/core.py:837
Change: Call ConversationEngine instead of ChatService

OPTION 2: Frontend change
File: aic-ide/src/renderer/src/lib/api/chat.ts:29
Change: Send to /api/conversations/{id}/stream instead of /chat/stream

OPTION 3: Redirect in ChatService
File: backend/services/chat_service.py:302
Change: Call ConversationEngine before LLM

RECOMMENDED (from repository evidence):
Option 1 is the most direct — modify the /chat/stream route to call ConversationEngine.

==================================================
16.6 EVIDENCE OF ABANDONED INTEGRATION
==================================================

EVIDENCE 1: Legacy Route Still Exists
File: backend/routes/conversations.py
Contains: ConversationEngine integration, task dispatch, background execution
Status: REGISTERED but not used by frontend

EVIDENCE 2: Archive Contains Dead Routes
File: .archive/dead-routes/tasks.py
Contains: Task CRUD, RuntimeExecutor integration
Status: ARCHIVED — previous implementation

EVIDENCE 3: Archive Contains Old Executor
File: .archive/executor_old.py
Contains: Previous RuntimeExecutor implementation
Status: ARCHIVED — replaced by current implementation

EVIDENCE 4: Two Parallel Systems
System A: backend/api/routes/core.py — ChatService (simple)
System B: backend/routes/conversations.py — ConversationEngine (full)
Status: BOTH registered, only System A used

EVIDENCE 5: Discovery Engine References ConversationEngine
File: discovery/engine.py:4
Comment: "Orchestrates the discovery pipeline and integrates with ConversationEngine"
Status: INTENDED integration, not connected

EVIDENCE 6: ConversationEngine Has Full Implementation
File: conversation/engine.py
Contains: Intent detection, task creation, clarification, status, approval
Status: COMPLETE but not called from chat path

==================================================
16.7 ROOT CAUSE CLASSIFICATION
==================================================

CLASSIFICATION: B — Partially implemented then abandoned

REASONING:

1. The ConversationEngine WAS implemented (conversation/engine.py — 836 lines)
2. The integration WAS created (backend/routes/conversations.py — 367 lines)
3. The legacy route WAS registered (backend/main.py:185)
4. The frontend WAS updated to use new route (chatApi.stream() → /chat/stream)
5. The new route was implemented as SIMPLE PASSTHROUGH (core.py:836)
6. The migration was INCOMPLETE — legacy route abandoned, new route lacks integration

EVIDENCE SEQUENCE:
- Phase 1: ConversationEngine implemented (conversation/engine.py)
- Phase 2: Legacy route created (backend/routes/conversations.py)
- Phase 3: New route created (backend/api/routes/core.py)
- Phase 4: Frontend migrated to new route (chat.ts:29)
- Phase 5: Legacy route abandoned (still registered, not used)
- Phase 6: New route never integrated ConversationEngine

CONCLUSION:
The integration was PARTIALLY IMPLEMENTED then ABANDONED during migration from legacy to new route.

==================================================
16.8 CONFIDENCE LEVEL
==================================================

CONFIDENCE: 95%

REASONING:
- Clear evidence of two parallel systems
- Clear evidence of migration in progress
- Clear evidence of abandoned legacy route
- Clear evidence of incomplete new route
- No evidence of intentional disable
- No evidence of feature flag
- No evidence of design revision

SUPPORTED BY:
- backend/routes/conversations.py — Legacy route with full integration
- backend/api/routes/core.py — New route without integration
- aic-ide/src/renderer/src/lib/api/chat.ts — Frontend uses new route
- .archive/dead-routes/tasks.py — Archived previous implementation
- .archive/executor_old.py — Archived previous executor

==================================================
END OF DOCUMENT
==================================================

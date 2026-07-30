# BACKEND WIRING SYSTEM DESIGN — SOURCE OF TRUTH

==================================================
DATE: 2026-07-29
VERSION: 2.1
STATUS: SOURCE OF TRUTH
==================================================

==================================================
EXECUTIVE SUMMARY
==================================================

All 11 engines are IMPLEMENTED in the repository.
The missing piece is WIRING (connections between engines).
This document defines the complete system architecture,
integration contracts, and implementation plan.

==================================================
CURRENT STATE
==================================================

COMPONENT STATUS:
1. Context Builder ✓ IMPLEMENTED (context/builder.py)
2. Memory Service ✓ IMPLEMENTED (backend/services/memory_service.py)
3. Intent Detector ✓ IMPLEMENTED (conversation/engine.py)
4. Verification Engine ✓ IMPLEMENTED (verification/engine.py)
5. RAG Service ✓ IMPLEMENTED (backend/services/rag_service.py)
6. Discovery Engine ✓ IMPLEMENTED (discovery/engine.py)
7. Planning Engine ✓ IMPLEMENTED (planning/engine.py)
8. TaskGraph Engine ✓ IMPLEMENTED (taskgraph/engine.py)
9. Dispatcher Engine ✓ IMPLEMENTED (dispatcher/engine.py)
10. Delivery Engine ✓ IMPLEMENTED (delivery/engine.py)
11. Autonomy Engine ✓ IMPLEMENTED (autonomy/engine.py)

WIRING STATUS:
1. Context Builder ✗ NOT WIRED to chat path
2. Memory Service ✗ NOT WIRED to chat path
3. Intent Detector ✓ WIRED (via ConversationEngine)
4. Verification Engine ✗ NOT WIRED to task completion
5. RAG Service ✗ NOT WIRED to context builder
6. Discovery Engine ✗ NOT WIRED to task request
7. Planning Engine ✗ NOT WIRED to task request
8. TaskGraph Engine ✗ NOT WIRED to task request
9. Dispatcher Engine ✗ NOT WIRED to task graph
10. Delivery Engine ✗ NOT WIRED to verification
11. Autonomy Engine ✗ NOT WIRED to error handling

==================================================
1. ARCHITECTURE PRINCIPLES
==================================================

P1: SINGLE RESPONSIBILITY
Each engine has exactly one responsibility.
No engine contains business logic belonging to another engine.

P2: DEPENDENCY INJECTION
Engines receive dependencies through constructor injection.
No engine creates its own dependencies.

P3: EVENT-DRIVEN WHERE APPROPRIATE
Engines emit events after state changes.
Subscribers react to events without direct coupling.

P4: NO CIRCULAR DEPENDENCY
Dependency graph is a DAG (Directed Acyclic Graph).
No engine may call back into its caller.

P5: CONVERSATION-FIRST ARCHITECTURE
All user interaction begins with Conversation.
ConversationEngine is the gateway to all workflows.

P6: CONTEXT BUILDER IS THE ONLY CONTEXT ENTRY POINT
All context assembly goes through Context Builder.
No engine builds its own context independently.

P7: ENGINES COMMUNICATE THROUGH INTERFACES
Engages through well-defined request/response contracts.
No engine accesses another engine's internal state.

P8: FAIL-FAST WITH GRACEFUL DEGRADATION
If an engine fails, fallback to simpler behavior.
Never fail silently; always log and propagate.

P9: IDEMPOTENT OPERATIONS
Engine operations may be safely retried.
No engine operation has side effects on retry.

P10: OBSERVABLE EXECUTION
Every engine call is logged with correlation ID.
Every state transition emits an event.

==================================================
2. ENGINE RESPONSIBILITY MATRIX
==================================================

| Engine | Responsibility | Inputs | Outputs | Trigger | Dependencies | Side Effects |
|--------|---------------|--------|---------|---------|--------------|--------------|
| Context Builder | Assemble unified context from multiple sources | Query, token budget | ContextAssembly | Before every LLM call | Memory, RAG, Conversation History | None |
| Memory Service | Store and retrieve persistent knowledge | Scope, key, value | MemoryEntry | After response, before LLM call | Database | Creates/updates MemoryEntry |
| Intent Detector | Classify user intent into routing category | User message | Intent type | Every user message | None | None |
| Conversation Engine | Orchestrate conversation lifecycle | User message, intent | Response, metadata | Every user message | Context Builder, Intent Detector, Memory | Creates Message, Task |
| Verification Engine | Verify output meets acceptance criteria | Brief ID, task results | VerificationReport | After task completion | Engineering Brief | Creates VerificationReport |
| RAG Service | Document ingestion, chunking, embedding, retrieval | Documents, queries | Relevant chunks | During context build | Embedding Provider | Creates Document, DocumentChunk |
| Discovery Engine | Transform natural language into Engineering Briefs | Conversation messages | EngineeringBrief | Engineering task request | Conversation | Creates DiscoverySession, Brief |
| Planning Engine | Transform Briefs into Engineering Plans | Brief ID | EngineeringPlan | After Discovery | Engineering Brief | Creates EngineeringPlan |
| TaskGraph Engine | Transform Plans into Task Graphs (DAGs) | Plan ID | TaskGraph | After Planning | Engineering Plan | Creates TaskGraph |
| Dispatcher Engine | Orchestrate worker execution per Task Graph | Graph ID | DispatchResult | After TaskGraph | TaskGraph, Workers | Creates Leases, Events |
| Delivery Engine | Generate reports and package artifacts | Brief ID, task results | EngineeringReport | After Verification | Verification Report | Creates EngineeringReport |
| Autonomy Engine | Self-healing, anomaly detection, recovery | Anomaly data | HealingResult | On error/anomaly | All engines | Creates AnomalyDetection, RecoveryAction |
| Runtime Executor | Execute tasks through FSM phases | Task | Execution result | Task creation | Workers, Workflow FSM | Creates Leases, Events, Artifacts |

==================================================
3. INTEGRATION / WIRING MATRIX
==================================================

| Engine | Called By | Output Consumed By | Sync/Async | Conditional |
|--------|----------|-------------------|------------|-------------|
| Context Builder | ChatService, ConversationEngine | LLM call | SYNC | Always |
| Memory Service | Context Builder, ConversationEngine | Context Assembly | ASYNC | Always |
| Intent Detector | ChatService route handler | Routing logic | SYNC | Always |
| Conversation Engine | ChatService route handler | Response to user | ASYNC | Always |
| Verification Engine | Runtime Executor | Task status | ASYNC | After task completion |
| RAG Service | Context Builder | Context Assembly | ASYNC | If documents exist |
| Discovery Engine | ConversationEngine | Engineering Brief | ASYNC | If engineering task |
| Planning Engine | Runtime Executor (via pipeline) | Engineering Plan | ASYNC | After Discovery |
| TaskGraph Engine | Runtime Executor (via pipeline) | Task Graph | ASYNC | After Planning |
| Dispatcher Engine | Runtime Executor (via pipeline) | Worker assignment | ASYNC | After TaskGraph |
| Delivery Engine | Runtime Executor | Engineering Report | ASYNC | After Verification |
| Autonomy Engine | Runtime Executor (error hook) | Recovery action | ASYNC | On failure |
| Runtime Executor | _dispatch_created_task() | Task completion | ASYNC | On task creation |

==================================================
4. CONTEXT PIPELINE
==================================================

CONTEXT BUILD FLOW:

User Message
    │
    ▼
Context Builder (context/builder.py)
    │
    ├──► Memory Source (context/sources.py)
    │       │
    │       ▼
    │    MemoryService.retrieve()
    │       │
    │       ▼
    │    MemoryEntry[]
    │
    ├──► RAG Source (context/sources.py)
    │       │
    │       ▼
    │    RAGService.retrieve()
    │       │
    │       ▼
    │    DocumentChunk[]
    │
    ├──► Conversation History Source
    │       │
    │       ▼
    │    Message[] (last N messages)
    │
    ├──► Workspace Source (context/sources.py)
    │       │
    │       ▼
    │    Project files, structure
    │
    └──► Runtime Source
            │
            ▼
         Active tasks, worker status

    │
    ▼
ContextAssembly
    │
    ├── chunks: ContextChunk[]
    ├── sources_used: string[]
    ├── total_tokens: int
    └── metadata: dict

    │
    ▼
Format for LLM prompt

CONTEXT TOKEN BUDGET:
- Default: 4000 tokens
- Sources: conversation, rag, knowledge, memory
- Deduplication: enabled
- Format: structured

==================================================
5. EXECUTION PIPELINE
==================================================

--------------------------------------------------
PIPELINE A: SIMPLE CHAT
--------------------------------------------------

User → "Hello, what is Python?"
    │
    ▼
ChatService.chat_stream()
    │
    ▼
Context Builder.build()
    ├── Memory.retrieve()
    ├── RAG.retrieve()
    └── Conversation History
    │
    ▼
LLM Call (with context)
    │
    ▼
Streaming Response
    │
    ▼
Memory.store() [async, fire-and-forget]

--------------------------------------------------
PIPELINE B: ENGINEERING TASK
--------------------------------------------------

User → "Build a restaurant POS"
    │
    ▼
ConversationEngine.process_message()
    │
    ▼
Intent Detector → INTENT_TASK_REQUEST
    │
    ▼
_handle_task_request()
    │
    ▼
_evaluate_intake_completeness()
    │
    ├── INCOMPLETE → Ask clarification questions
    │
    └── COMPLETE → _create_task()
            │
            ▼
        Task created in database
            │
            ▼
        _dispatch_created_task() [background]
            │
            ▼
        Runtime Executor.execute_task()
            │
            ▼
        Smart Triage → Execution Level (L1-L4)
            │
            ├── L1 QUICK → Skip discovery/planning
            │
            └── L2-L4 → Full pipeline
                    │
                    ▼
                Discovery Engine.discover()
                    │
                    ▼
                Planning Engine.plan()
                    │
                    ▼
                TaskGraph Engine.generate_graph()
                    │
                    ▼
                Dispatcher Engine.dispatch()
                    │
                    ▼
                Workers execute (backend, frontend, qa, etc.)
                    │
                    ▼
                Verification Engine.verify()
                    │
                    ▼
                Delivery Engine.generate_report()
                    │
                    ▼
                Task COMPLETED

--------------------------------------------------
PIPELINE C: AUTONOMOUS WORKFLOW
--------------------------------------------------

System Event (error, anomaly, policy trigger)
    │
    ▼
Autonomy Engine.detect_anomaly()
    │
    ▼
Evaluate recovery strategy
    │
    ├── RETRY → Re-execute failed operation
    │
    ├── REFINE_PROMPT → Adjust and retry
    │
    ├── FALLBACK_MODEL → Use alternative model
    │
    └── ESCALATE → Notify user
            │
            ▼
        RecoveryAction executed
            │
            ▼
        HealingResult recorded

==================================================
6. DECISION MATRIX
==================================================

| Request Type | Context Builder | Memory | RAG | Discovery | Planning | TaskGraph | Dispatcher | Verification | Delivery | Autonomy |
|--------------|----------------|--------|-----|-----------|----------|-----------|------------|--------------|----------|----------|
| Chat | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Question | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Research | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Bug Fix (L1) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Bug Fix (L2) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Feature (L3) | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Feature (L4) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Error Recovery | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

Legend:
✓ = Engine is invoked
✗ = Engine is skipped

==================================================
7. EVENT MODEL
==================================================

| Event | Publisher | Subscriber | Payload |
|-------|-----------|------------|---------|
| ChatReceived | ChatService | Context Builder | conversation_id, content, intent |
| ContextBuilt | Context Builder | LLM Call | ContextAssembly (chunks, tokens, sources) |
| MemoryUpdated | Memory Service | None (persistence only) | MemoryEntry |
| IntentDetected | Intent Detector | ConversationEngine | intent_type, confidence |
| TaskCreated | ConversationEngine | Runtime Executor | task_id, type, worker |
| TaskDispatched | Dispatcher Engine | Workers | task_id, worker_type, phase |
| WorkerStarted | Runtime Executor | UI (WebSocket) | worker_type, task_id, phase |
| WorkerCompleted | Runtime Executor | UI (WebSocket) | worker_type, task_id, success |
| TaskCompleted | Runtime Executor | Verification Engine | task_id, results |
| VerificationPassed | Verification Engine | Delivery Engine | verification_id, report |
| VerificationFailed | Verification Engine | Runtime Executor | verification_id, failures |
| DeliveryCompleted | Delivery Engine | UI (WebSocket) | report_id, artifacts |
| AnomalyDetected | Autonomy Engine | Recovery System | anomaly_type, severity |
| RecoveryExecuted | Autonomy Engine | Logging | recovery_action, result |
| ErrorOccurred | Any Engine | Autonomy Engine | error_type, component, context |

==================================================
8. DEPENDENCY RULES
==================================================

ALLOWED DEPENDENCIES:

ConversationEngine
→ Context Builder (for context assembly)
→ Memory Service (for memory store/retrieve)
→ Intent Detector (for intent classification)
→ Task creation (database)

Context Builder
→ Memory Service (retrieve)
→ RAG Service (retrieve)
→ Conversation History (database)
→ Workspace (filesystem)

Runtime Executor
→ Workers (execution)
→ Workflow FSM (phase management)
→ Verification Engine (post-task verification)
→ Delivery Engine (post-verification delivery)

Verification Engine
→ Engineering Brief (acceptance criteria)
→ Task Results (execution output)

Delivery Engine
→ Verification Report (verification results)
→ Artifacts (file system)

Autonomy Engine
→ All engines (anomaly detection)
→ Recovery strategies (execution)

FORBIDDEN DEPENDENCIES:

ConversationEngine
→ MUST NOT call Runtime Executor directly
→ MUST NOT call Discovery/Planning/TaskGraph/Dispatcher

Runtime Executor
→ MUST NOT call ConversationEngine
→ MUST NOT call Context Builder

Delivery Engine
→ MUST NOT depend on Runtime Executor
→ MUST NOT call Verification Engine

Context Builder
→ MUST NOT call ConversationEngine
→ MUST NOT call Runtime Executor

==================================================
9. FAILURE FLOW
==================================================

CONTEXT BUILD FAILURE:
- Trigger: Context Builder throws exception
- Fallback: Return empty context, proceed with LLM call
- Retry: None (fail-fast)
- Log: ERROR level with context details

MEMORY FAILURE:
- Trigger: MemoryService.store() or retrieve() throws
- Fallback: Skip memory operations, proceed without memory
- Retry: None (fail-fast)
- Log: WARNING level

RAG FAILURE:
- Trigger: RAGService.retrieve() throws
- Fallback: Skip RAG source, proceed without document context
- Retry: None (fail-fast)
- Log: WARNING level

VERIFICATION FAILURE:
- Trigger: VerificationEngine.verify() throws
- Fallback: Mark task as "verification_skipped"
- Retry: None (fail-fast)
- Log: ERROR level

DELIVERY FAILURE:
- Trigger: DeliveryEngine.generate_report() throws
- Fallback: Mark task as "delivery_failed", task still COMPLETED
- Retry: None (fail-fast)
- Log: ERROR level

RUNTIME FAILURE:
- Trigger: Worker execution fails
- Fallback: Recovery ladder (4 attempts)
- Retry: Yes, with progressive recovery
- Recovery strategies: retry, refine_prompt, fallback_model, canonical_lock
- Log: WARNING → ERROR escalation

AUTONOMY FAILURE:
- Trigger: Autonomy Engine throws during recovery
- Fallback: Manual intervention required
- Retry: None
- Log: CRITICAL level

==================================================
10. STATE MACHINE
==================================================

TASK LIFECYCLE:

NEW (Task created)
    │
    ▼
CONTEXT_READY (Context assembled)
    │
    ▼
PLANNING (Discovery → Planning → TaskGraph)
    │
    ├── SKIPPED (L1 QUICK mode)
    │
    ▼
DISPATCHING (Workers assigned)
    │
    ▼
RUNNING (Workers executing)
    │
    ├── COMPLETED (All workers succeed)
    │       │
    │       ▼
    │   VERIFYING (Verification Engine)
    │       │
    │       ├── PASSED
    │       │       │
    │       │       ▼
    │       │   DELIVERING (Delivery Engine)
    │       │       │
    │       │       ▼
    │       │   COMPLETED
    │       │
    │       └── FAILED
    │               │
    │               ▼
    │           RECOVERY (Autonomy Engine)
    │               │
    │               ├── RETRY → RUNNING
    │               │
    │               └── ESCALATE → FAILED
    │
    └── FAILED (Worker failure)
            │
            ▼
        RECOVERY (Autonomy Engine)
            │
            ├── RETRY → RUNNING
            │
            └── ESCALATE → FAILED

TERMINAL STATES:
- COMPLETED: Task finished successfully
- FAILED: Task failed after all recovery attempts
- CANCELLED: Task cancelled by user

==================================================
11. SEQUENCE DIAGRAMS
==================================================

--------------------------------------------------
SEQUENCE 1: NORMAL CHAT
--------------------------------------------------

User → ChatView: "What is Python?"
ChatView → ChatService: POST /chat/stream
ChatService → IntentDetector: _detect_intent("What is Python?")
IntentDetector → ChatService: INTENT_QUESTION
ChatService → ContextBuilder: build("What is Python?")
ContextBuilder → MemoryService: retrieve(scope="conversation")
MemoryService → ContextBuilder: MemoryEntry[]
ContextBuilder → RAGService: retrieve(query="Python")
RAGService → ContextBuilder: DocumentChunk[]
ContextBuilder → ChatService: ContextAssembly
ChatService → LLM: chat_completion(messages + context)
LLM → ChatService: streaming chunks
ChatService → ChatView: SSE chunks
ChatView → User: "Python is a programming language..."
ChatService → Memory Service: store(conversation, response) [async]

--------------------------------------------------
SEQUENCE 2: ENGINEERING TASK
--------------------------------------------------

User → ChatView: "Build a restaurant POS"
ChatView → ChatService: POST /chat/stream
ChatService → IntentDetector: _detect_intent()
IntentDetector → ChatService: INTENT_TASK_REQUEST
ChatService → ConversationEngine: process_message()
ConversationEngine → IntakeCheck: evaluate completeness
IntakeCheck → ConversationEngine: INCOMPLETE
ConversationEngine → User: "What features do you need?"

User → ChatView: "Menu, orders, payments"
ChatView → ConversationEngine: process_message()
ConversationEngine → IntakeCheck: evaluate completeness
IntakeCheck → ConversationEngine: COMPLETE
ConversationEngine → TaskCreate: _create_task()
TaskCreate → Database: INSERT Task
ConversationEngine → User: "Task created. Ready to start?"

User → ChatView: "Build now"
ChatView → ConversationEngine: process_message()
IntentDetector → ChatService: INTENT_TASK_CONFIRM
ConversationEngine → TaskConfirm: _handle_task_confirm()
TaskConfirm → Database: UPDATE Task status

Background:
DispatchTask → RuntimeExecutor: execute_task()
RuntimeExecutor → SmartTriage: perform_smart_triage()
SmartTriage → RuntimeExecutor: L4 FULL
RuntimeExecutor → DiscoveryEngine: discover()
DiscoveryEngine → RuntimeExecutor: EngineeringBrief
RuntimeExecutor → PlanningEngine: plan()
PlanningEngine → RuntimeExecutor: EngineeringPlan
RuntimeExecutor → TaskGraphEngine: generate_graph()
TaskGraphEngine → RuntimeExecutor: TaskGraph
RuntimeExecutor → DispatcherEngine: dispatch()
DispatcherEngine → Workers: assign tasks
Workers → RuntimeExecutor: results
RuntimeExecutor → VerificationEngine: verify()
VerificationEngine → RuntimeExecutor: VerificationReport
RuntimeExecutor → DeliveryEngine: generate_report()
DeliveryEngine → RuntimeExecutor: EngineeringReport
RuntimeExecutor → User: "Task completed"

--------------------------------------------------
SEQUENCE 3: AUTONOMOUS WORKFLOW
--------------------------------------------------

Worker → RuntimeExecutor: execution FAILED
RuntimeExecutor → AutonomyEngine: detect_anomaly()
AutonomyEngine → RecoveryStrategy: evaluate()
RecoveryStrategy → AutonomyEngine: RETRY
AutonomyEngine → RuntimeExecutor: retry with refined prompt
RuntimeExecutor → Worker: execute(refined context)
Worker → RuntimeExecutor: execution SUCCESS
RuntimeExecutor → AutonomyEngine: healing_result(SUCCESS)
AutonomyEngine → Database: STORE recovery record

==================================================
12. INTEGRATION CONTRACTS
==================================================

--------------------------------------------------
CONTRACT 1: Context Builder
--------------------------------------------------
Request:
- query: str (user message or context description)
- max_tokens: int (token budget, default 4000)
- conversation_id: str (for conversation history)

Response (ContextAssembly):
- chunks: ContextChunk[] (assembled context pieces)
- sources_used: str[] (which sources contributed)
- total_tokens: int (total token count)
- metadata: dict (assembly metadata)

--------------------------------------------------
CONTRACT 2: Memory Service
--------------------------------------------------
Store Request:
- scope: str (session|conversation|workspace|project|user)
- key: str (memory key)
- value: dict (memory value)
- scope_id: str (optional scope identifier)
- category: str (fact|preference|context|summary)
- importance: float (0.0-1.0)

Retrieve Request:
- scope: str
- key: str (optional)
- scope_id: str (optional)
- category: str (optional)
- min_importance: float (default 0.0)
- limit: int (default 50)

Response: MemoryEntry[]

--------------------------------------------------
CONTRACT 3: Intent Detector
--------------------------------------------------
Request:
- content: str (user message)
- history: list (conversation history)

Response:
- intent: str (chat|question|task_request|task_confirm|status|approval)

--------------------------------------------------
CONTRACT 4: Verification Engine
--------------------------------------------------
Request:
- brief_id: str (Engineering Brief ID)
- task_results: dict (worker execution results)

Response (VerificationResult):
- state: str (passed|failed|error|disabled)
- report: VerificationReport
- message: str

--------------------------------------------------
CONTRACT 5: Discovery Engine
--------------------------------------------------
Request:
- conversation_id: str
- content: str (user request)

Response (DiscoveryResult):
- state: str (discovered|clarifying|ready|error)
- is_ready: bool
- brief: EngineeringBriefData
- clarification: ClarificationResult

--------------------------------------------------
CONTRACT 6: Runtime Executor
--------------------------------------------------
Request:
- task: Task (database model)

Response:
- success: bool
- results: dict (phase results)
- error: str (if failed)

==================================================
13. TESTING STRATEGY
==================================================

UNIT TESTS:
- Each engine tested independently
- Mock dependencies
- Test all public methods
- Test error handling
- Test edge cases

INTEGRATION TESTS:
- Engine pairs tested together
- Context Builder + Memory Service
- Context Builder + RAG Service
- ConversationEngine + Intent Detector
- Runtime Executor + Verification Engine
- Verification Engine + Delivery Engine

END-TO-END TESTS:
- Complete workflow tested
- Chat → Context → LLM → Response
- Task Request → Clarification → Task Creation → Execution → Verification → Delivery
- Error → Recovery → Success

FAILURE INJECTION TESTS:
- Inject failures at each engine boundary
- Verify fallback behavior
- Verify error propagation
- Verify logging

RECOVERY TESTS:
- Inject failures
- Verify recovery strategies
- Verify retry logic
- Verify escalation

==================================================
14. OBSERVABILITY
==================================================

LOGGING:
- Every engine call logged with:
  - timestamp
  - correlation_id
  - engine_name
  - method_name
  - input_summary
  - output_summary
  - duration_ms
  - status (success|failure)

METRICS:
- Engine call count
- Engine latency (p50, p95, p99)
- Engine error rate
- Context build time
- Memory retrieve time
- RAG retrieve time
- Task completion time

TRACING:
- correlation_id flows through entire request
- Each engine adds span to trace
- Parent-child relationships preserved

EVENT ID:
- Every event has unique event_id
- Events are linked to originating request
- Event chain reconstructable

LATENCY MEASUREMENTS:
- Context Build: < 100ms target
- Memory Retrieve: < 50ms target
- RAG Retrieve: < 200ms target
- Intent Detection: < 10ms target
- Verification: < 500ms target
- Delivery: < 1000ms target

==================================================
15. OPEN QUESTIONS
==================================================

OQ-1: Should Context Builder cache assembled context?
- Impact: Performance vs freshness tradeoff
- Decision needed before implementation

OQ-2: Should Memory Service auto-expire old entries?
- Impact: Storage growth vs relevance
- Decision needed before implementation

OQ-3: Should RAG Service use external vector DB?
- Impact: Performance vs dependency tradeoff
- Decision needed before implementation

OQ-4: Should Verification Engine require user approval?
- Impact: Automation vs control tradeoff
- Decision needed before implementation

OQ-5: Should Autonomy Engine auto-retry or escalate?
- Impact: Automation vs safety tradeoff
- Decision needed before implementation

OQ-6: Should Discovery Engine run for all task types?
- Impact: Overhead vs thoroughness tradeoff
- Decision needed before implementation

OQ-7: Should Delivery Engine auto-publish artifacts?
- Impact: Automation vs review tradeoff
- Decision needed before implementation

OQ-8: Should events be persisted or in-memory only?
- Impact: Durability vs performance tradeoff
- Decision needed before implementation

==================================================
IMPLEMENTATION ORDER (PRESERVED)
==================================================

URUTAN 1: CONTEXT BUILDER (Entry Point Wajib)
Priority: CRITICAL
Dependencies: None
Complexity: LOW
Risk: LOW

URUTAN 2: MEMORY SERVICE (Retrieve + Persist Otomatis)
Priority: CRITICAL
Dependencies: Context Builder
Complexity: LOW
Risk: LOW

URUTAN 3: INTENT DETECTOR (Routing Sederhana)
Priority: HIGH
Dependencies: None
Complexity: LOW
Risk: LOW

URUTAN 4: VERIFICATION ENGINE (Hook Setelah Task Selesai)
Priority: HIGH
Dependencies: Runtime Executor
Complexity: MEDIUM
Risk: MEDIUM

URUTAN 5: RAG SERVICE (Integrasi ke Context Builder)
Priority: HIGH
Dependencies: Context Builder
Complexity: MEDIUM
Risk: MEDIUM

URUTAN 6: DISCOVERY → PLANNING → TASKGRAPH → DISPATCHER
Priority: MEDIUM
Dependencies: ConversationEngine, Runtime Executor
Complexity: HIGH
Risk: HIGH

URUTAN 7: DELIVERY ENGINE (Formatting, Artifact Packaging)
Priority: MEDIUM
Dependencies: Verification Engine
Complexity: MEDIUM
Risk: MEDIUM

URUTAN 8: AUTONOMY ENGINE (Orchestrator Tingkat Atas)
Priority: LOW
Dependencies: All engines
Complexity: HIGH
Risk: HIGH

==================================================
IMPLEMENTATION TIMELINE
==================================================

WEEK 1:
- Context Builder wiring (1 day)
- Memory Service wiring (1 day)
- Intent Detector verification (0.5 day)
- Testing and debugging (1.5 days)

WEEK 2:
- Verification Engine wiring (1 day)
- RAG Service integration (1 day)
- Testing and debugging (1 day)

WEEK 3:
- Discovery → Planning → TaskGraph → Dispatcher (2 days)
- Testing and debugging (1 day)

WEEK 4:
- Delivery Engine wiring (1 day)
- Autonomy Engine wiring (1 day)
- Testing and debugging (1 day)

TOTAL: 4 weeks (13 working days)

==================================================
SUCCESS CRITERIA
==================================================

1. Context Builder called before every chat ✓
2. Memory stored and retrieved automatically ✓
3. Intent detection works for all intents ✓
4. Verification automatic after task completion ✓
5. RAG integrated into context builder ✓
6. Workflow automatic for engineering tasks ✓
7. Delivery automatic after verification ✓
8. Autonomy handles error recovery ✓

==================================================
END OF DOCUMENT
==================================================

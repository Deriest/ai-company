# 13 — ENGINE INTEGRATION ANALYSIS

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
13.1 ENGINE INVENTORY
==================================================

The repository contains 12 engine/service modules:

1. Discovery Engine (discovery/engine.py)
2. Planning Engine (planning/engine.py)
3. TaskGraph Engine (taskgraph/engine.py)
4. Dispatcher Engine (dispatcher/engine.py)
5. Verification Engine (verification/engine.py)
6. Delivery Engine (delivery/engine.py)
7. Autonomy Engine (autonomy/engine.py)
8. Memory Service (backend/services/memory_service.py)
9. RAG Service (backend/services/rag_service.py)
10. Context Builder (context/builder.py)
11. MCP Service (backend/services/mcp_service.py)
12. Tool Dispatcher (backend/services/tool_dispatcher.py)

Additionally found:
13. Workflow Engine (workflow/engine.py)
14. Conversation Engine (conversation/engine.py)
15. Runtime Executor (runtime/executor.py)

==================================================
13.2 ENGINE ANALYSIS
==================================================

--------------------------------------------------
ENGINE: Discovery
--------------------------------------------------
Purpose: Transform natural language into Engineering Briefs
Public API: DiscoveryEngine.discover(), respond_to_clarification()
Expected Input: Conversation messages
Expected Output: EngineeringBrief
Entry Points: backend/routes/discovery.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/discovery/* routes

Repository evidence:
- discovery/engine.py:57 — async def discover()
- backend/routes/discovery.py — REST endpoints

--------------------------------------------------
ENGINE: Planning
--------------------------------------------------
Purpose: Transform Engineering Briefs into Engineering Plans
Public API: PlanningEngine.plan()
Expected Input: EngineeringBrief ID
Expected Output: EngineeringPlan
Entry Points: backend/routes/planning.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/planning/* routes

Repository evidence:
- planning/engine.py — async def plan()
- backend/routes/planning.py — REST endpoints

--------------------------------------------------
ENGINE: TaskGraph
--------------------------------------------------
Purpose: Transform Engineering Plans into Task Graphs (DAGs)
Public API: TaskGraphEngine.generate_graph()
Expected Input: EngineeringPlan ID
Expected Output: TaskGraph
Entry Points: backend/routes/taskgraph.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/taskgraph/* routes

Repository evidence:
- taskgraph/engine.py — async def generate_graph()
- backend/routes/taskgraph.py — REST endpoints

--------------------------------------------------
ENGINE: Dispatcher
--------------------------------------------------
Purpose: Orchestrate worker execution according to Task Graph
Public API: DispatcherEngine.dispatch()
Expected Input: TaskGraph ID
Expected Output: DispatchResult
Entry Points: backend/routes/dispatcher.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/dispatcher/* routes

Repository evidence:
- dispatcher/engine.py — async def dispatch()
- backend/routes/dispatcher.py — REST endpoints

--------------------------------------------------
ENGINE: Verification
--------------------------------------------------
Purpose: Verify output meets acceptance criteria
Public API: VerificationEngine.verify()
Expected Input: EngineeringBrief ID, task results
Expected Output: VerificationReport
Entry Points: backend/routes/verification.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/verification/* routes

Repository evidence:
- verification/engine.py — async def verify()
- backend/routes/verification.py — REST endpoints

--------------------------------------------------
ENGINE: Delivery
--------------------------------------------------
Purpose: Deliver verified output and learn from outcomes
Public API: DeliveryEngine.generate_report()
Expected Input: Brief ID, plan ID, graph ID, verification ID
Expected Output: EngineeringReport
Entry Points: backend/routes/delivery.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/delivery/* routes

Repository evidence:
- delivery/engine.py — async def generate_report()
- backend/routes/delivery.py — REST endpoints

--------------------------------------------------
ENGINE: Autonomy
--------------------------------------------------
Purpose: Self-healing, adaptive execution
Public API: AutonomyEngine.detect_anomaly(), recover(), heal()
Expected Input: Anomaly descriptions
Expected Output: AnomalyDetection, HealingResult
Entry Points: backend/routes/autonomy.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /api/autonomy/* routes

Repository evidence:
- autonomy/engine.py — detect_anomaly(), recover(), heal()
- backend/routes/autonomy.py — REST endpoints

--------------------------------------------------
ENGINE: Memory
--------------------------------------------------
Purpose: Multi-scope memory management
Public API: MemoryService.store(), retrieve(), compress()
Expected Input: Scope, key, value
Expected Output: MemoryEntry
Entry Points: backend/api/routes/memory.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /memory/* routes

Repository evidence:
- backend/services/memory_service.py — store(), retrieve(), compress()
- backend/api/routes/memory.py — REST endpoints

--------------------------------------------------
ENGINE: RAG
--------------------------------------------------
Purpose: Document loading, chunking, embedding, retrieval
Public API: RAGService.load_document(), retrieve()
Expected Input: Documents, queries
Expected Output: Relevant chunks
Entry Points: backend/api/routes/rag.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /rag/* routes

Repository evidence:
- backend/services/rag_service.py — load_document(), retrieve()
- backend/api/routes/rag.py — REST endpoints

--------------------------------------------------
ENGINE: Context Builder
--------------------------------------------------
Purpose: Structured context assembly for LLM prompts
Public API: ContextBuilder.build()
Expected Input: Query, token budget
Expected Output: ContextAssembly
Entry Points: backend/services/chat_service.py (build_chat_context function)
Current Callers: TESTS ONLY — build_chat_context() exists but is NEVER called in chat_stream()
Production Code Calling: NO — function exists but unused
Only REST: NO — function exists in chat_service.py
Only Tests: YES — only called in test_chat_context.py
Partially Integrated: YES — function exists but not wired
Deprecated: NO
Last Integration Point: build_chat_context() function at chat_service.py:18

Repository evidence:
- context/builder.py — ContextBuilder.build()
- backend/services/chat_service.py:18 — build_chat_context() [UNUSED]
- tests/test_chat_context.py — only caller

--------------------------------------------------
ENGINE: MCP
--------------------------------------------------
Purpose: MCP server registry, tool discovery, execution
Public API: MCPService.register_server(), discover_tools(), execute_tool()
Expected Input: Server config, tool calls
Expected Output: Tool execution results
Entry Points: backend/api/routes/mcp.py
Current Callers: REST API only (manual invocation)
Production Code Calling: NO — only route handler
Only REST: YES
Only Tests: NO — route handler exists
Partially Integrated: NO
Deprecated: NO
Last Integration Point: /mcp/* routes

Repository evidence:
- backend/services/mcp_service.py — register_server(), discover_tools(), execute_tool()
- backend/api/routes/mcp.py — REST endpoints

--------------------------------------------------
ENGINE: Tool Dispatcher
--------------------------------------------------
Purpose: Execute workspace tools (read_file, write_file, etc.)
Public API: ToolDispatcher.execute()
Expected Input: Tool name, arguments
Expected Output: Tool result
Entry Points: backend/services/chat_service.py
Current Callers: ChatService (non-streaming only)
Production Code Calling: YES — in chat_completion() but NOT in chat_stream()
Only REST: NO — called from chat service
Only Tests: NO — called in production (non-streaming)
Partially Integrated: YES — only in non-streaming mode
Deprecated: NO
Last Integration Point: chat_service.py:237 — tool_dispatcher.execute()

Repository evidence:
- backend/services/tool_dispatcher.py — execute()
- backend/services/chat_service.py:237 — called in chat_completion()

--------------------------------------------------
ENGINE: Workflow
--------------------------------------------------
Purpose: Task lifecycle through FSM phases
Public API: WorkflowEngine.advance_phase(), get_or_create_state()
Expected Input: Task
Expected Output: WorkflowState
Entry Points: runtime/executor.py
Current Callers: Runtime executor
Production Code Calling: YES — called from runtime executor
Only REST: NO — called from runtime
Only Tests: NO — called in production
Partially Integrated: YES — integrated with runtime executor
Deprecated: NO
Last Integration Point: runtime/executor.py

Repository evidence:
- workflow/engine.py — WorkflowEngine
- runtime/executor.py — calls workflow.fsm

--------------------------------------------------
ENGINE: Conversation
--------------------------------------------------
Purpose: AI Operator behavior, natural conversation
Public API: ConversationEngine
Expected Input: User messages
Expected Output: AI responses
Entry Points: Not directly called from chat path
Current Callers: UNKNOWN — not found in chat_service.py
Production Code Calling: NOT SUPPORTED BY EVIDENCE
Only REST: NOT SUPPORTED BY EVIDENCE
Only Tests: NOT SUPPORTED BY EVIDENCE
Partially Integrated: NOT SUPPORTED BY EVIDENCE
Deprecated: NO
Last Integration Point: NOT SUPPORTED BY EVIDENCE

Repository evidence:
- conversation/engine.py — exists but caller not found

--------------------------------------------------
ENGINE: Runtime Executor
--------------------------------------------------
Purpose: Execute tasks through FSM phases adaptively
Public API: execute_task()
Expected Input: Task
Expected Output: Execution result
Entry Points: Not directly called from chat path
Current Callers: UNKNOWN — not found in chat_service.py
Production Code Calling: NOT SUPPORTED BY EVIDENCE
Only REST: NOT SUPPORTED BY EVIDENCE
Only Tests: NOT SUPPORTED BY EVIDENCE
Partially Integrated: NOT SUPPORTED BY EVIDENCE
Deprecated: NO
Last Integration Point: NOT SUPPORTED BY EVIDENCE

Repository evidence:
- runtime/executor.py — exists but caller not found

==================================================
13.3 INTEGRATION STATUS SUMMARY
==================================================

| Engine | Status | Classification |
|--------|--------|----------------|
| Discovery | REST only | B — Implemented but only accessible manually |
| Planning | REST only | B — Implemented but only accessible manually |
| TaskGraph | REST only | B — Implemented but only accessible manually |
| Dispatcher | REST only | B — Implemented but only accessible manually |
| Verification | REST only | B — Implemented but only accessible manually |
| Delivery | REST only | B — Implemented but only accessible manually |
| Autonomy | REST only | B — Implemented but only accessible manually |
| Memory | REST only | B — Implemented but only accessible manually |
| RAG | REST only | B — Implemented but only accessible manually |
| Context Builder | Exists, unused | A — Implemented but isolated |
| MCP | REST only | B — Implemented but only accessible manually |
| Tool Dispatcher | Partial | D — Integrated into another execution path (non-streaming) |
| Workflow | Integrated | D — Integrated into runtime executor |
| Conversation | Unknown | ? — Unable to determine |
| Runtime Executor | Unknown | ? — Unable to determine |

==================================================
13.4 CALLER GRAPH
==================================================

CHAT PATH (what actually runs):
User → ChatView → chatApi.stream() → /chat/stream → ChatService.chat_stream() → LLM Provider

DISCOVERY PATH (manual REST only):
User → UI → /api/discovery/* → DiscoveryEngine.discover()

PLANNING PATH (manual REST only):
User → UI → /api/planning/* → PlanningEngine.plan()

TASKGRAPH PATH (manual REST only):
User → UI → /api/taskgraph/* → TaskGraphEngine.generate_graph()

DISPATCHER PATH (manual REST only):
User → UI → /api/dispatcher/* → DispatcherEngine.dispatch()

VERIFICATION PATH (manual REST only):
User → UI → /api/verification/* → VerificationEngine.verify()

DELIVERY PATH (manual REST only):
User → UI → /api/delivery/* → DeliveryEngine.generate_report()

AUTONOMY PATH (manual REST only):
User → UI → /api/autonomy/* → AutonomyEngine.detect_anomaly()

MEMORY PATH (manual REST only):
User → UI → /memory/* → MemoryService.store()/retrieve()

RAG PATH (manual REST only):
User → UI → /rag/* → RAGService.load_document()/retrieve()

CONTEXT BUILDER PATH (unused):
[NOT CALLED] → build_chat_context() → ContextBuilder.build()

MCP PATH (manual REST only):
User → UI → /mcp/* → MCPService.register_server()/execute_tool()

TOOL DISPATCHER PATH (non-streaming only):
ChatService.chat_completion() → tool_dispatcher.execute()

WORKFLOW PATH (runtime only):
runtime/executor.py → WorkflowEngine.advance_phase()

==================================================
13.5 ISOLATION ANALYSIS
==================================================

ROOT CAUSE: The engines are isolated because they were implemented as
independent REST endpoints without integration into the chat path.

EVIDENCE:

1. CHAT SERVICE DOES NOT IMPORT ENGINES
   - chat_service.py does NOT import discovery, planning, taskgraph, dispatcher, verification, delivery, autonomy
   - chat_service.py only imports: tool_dispatcher, artifact_service, crypto, provider_client

2. ENGINES ARE ONLY EXPOSED VIA REST
   - Each engine has its own route file in backend/routes/
   - Routes are registered in backend/main.py
   - No route calls another engine

3. NO ORCHESTRATION LAYER
   - orchestrator_service.py does NOT import any engine
   - orchestrator_service.py only imports: worker_runtime_service, chat_service
   - No service connects the engines into a pipeline

4. CONTEXT BUILDER IS UNUSED
   - build_chat_context() exists in chat_service.py
   - Function is NEVER called in chat_stream() or chat_completion()
   - Only called in tests

5. TWO SEPARATE SYSTEMS
   - System 1: Chat path (chat_service.py → LLM)
   - System 2: Company workflow (discovery → planning → taskgraph → dispatcher → verification → delivery)
   - These systems are NOT connected

==================================================
13.6 ARCHITECTURAL INTENT
==================================================

REPOSITORY EVIDENCE:

1. README.md states:
   "Autonomous AI Company Operating System"
   "Full task lifecycle (8-phase FSM)"
   "E2E lifecycle test verifies: chat → task → dispatch → approval → phase advances → completed"

   This suggests the INTENT was to integrate the engines into a pipeline.

2. runtime/executor.py states:
   "Executes tasks through FSM phases adaptively based on Smart Triage execution levels"
   "L1 QUICK: Fast-path for localized changes, skipping unnecessary phases"
   "L2 STANDARD: Normal scoped engineering"
   "L3 EXTENDED: Cross-component / higher-risk engineering"
   "L4 FULL: Complete multi-agent lifecycle"

   This suggests the INTENT was to have different execution levels.

3. conversation/engine.py states:
   "AI Operator behavior: the assistant is a capable project partner"
   "Only dispatches to the task system when the user confirms"

   This suggests the INTENT was to have the conversation engine decide when to dispatch.

4. workflow/triage.py exists:
   "Smart Triage" determines execution level
   "L1 QUICK, L2 STANDARD, L3 EXTENDED, L4 FULL"

   This suggests the INTENT was to have triage determine which engines to invoke.

CONCLUSION:
The repository contains TWO SEPARATE SYSTEMS that were INTENDED to be connected:

System A: Chat Service (simple passthrough to LLM)
System B: Company Workflow (discovery → planning → taskgraph → dispatcher → verification → delivery)

The INTENT was for the Conversation Engine to detect intent and dispatch to System B.
However, this integration was NEVER IMPLEMENTED in the current chat path.

==================================================
13.7 ROOT CAUSE ANALYSIS
==================================================

WHY DOES CHAT BYPASS THE COMPANY ENGINES?

ANSWER: The chat path (chat_service.py) was implemented as a SIMPLE
PASSTHROUGH to the LLM provider WITHOUT integration into the company
workflow engines.

REPOSITORY EVIDENCE:

1. chat_service.py does NOT import any engine
2. chat_stream() does NOT call any engine
3. build_chat_context() exists but is NEVER called
4. The orchestrator_service.py does NOT import any engine
5. The runtime/executor.py is NOT called from chat path
6. The conversation/engine.py is NOT called from chat path

TWO POSSIBLE EXPLANATIONS (repository evidence):

A. PHASED IMPLEMENTATION
   - The engines were implemented independently
   - The integration layer was never built
   - Evidence: Each engine has its own REST endpoint but no orchestration

B. ARCHITECTURAL REVISION
   - The original design (README) shows integrated workflow
   - The current implementation is a simplified version
   - Evidence: README mentions "8-phase FSM" but chat path has no FSM

CONCLUSION:
The engines are ISOLATED because the INTEGRATION LAYER that would
connect the chat path to the company workflow was NEVER IMPLEMENTED.

The chat path is a SIMPLE PASSTHROUGH to the LLM provider.
The company workflow engines exist as SEPARATE REST endpoints.
There is NO code connecting these two systems.

==================================================
END OF DOCUMENT
==================================================

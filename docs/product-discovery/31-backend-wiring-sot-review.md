# BACKEND WIRING SOT v2.0 — CONSISTENCY REVIEW

==================================================
DATE: 2026-07-29
TYPE: READ-ONLY REVIEW
==================================================

==================================================
PASS
==================================================

The following sections are internally consistent:

1. EXECUTIVE SUMMARY — Consistent with Current State
2. CURRENT STATE — Consistent component list
3. ARCHITECTURE PRINCIPLES — Internally consistent
4. ENGINE RESPONSIBILITY MATRIX — Consistent engine list
5. CONTEXT PIPELINE — Consistent with Engine Responsibility Matrix
6. DECISION MATRIX — Consistent with Execution Pipeline
7. TESTING STRATEGY — Consistent with overall design
8. OBSERVABILITY — Consistent with overall design
9. OPEN QUESTIONS — Consistent with overall design
10. IMPLEMENTATION TIMELINE — Consistent with Implementation Order

==================================================
ISSUES
==================================================

ISSUE 1: Dependency Rules Contradiction (Runtime Executor)
--------------------------------------------------
Severity: HIGH
Location: Section 8 (Dependency Rules) vs Section 2 (Engine Responsibility Matrix)

Explanation:
- Section 8 ALLOWED (line 371-372): Runtime Executor → Verification Engine, Delivery Engine
- Section 8 FORBIDDEN (line 397-398): Delivery Engine MUST NOT depend on Runtime Executor
- Section 2 (line 108): Delivery Engine triggered "After Verification", depends on "Verification Report"

Exact contradiction:
- ALLOWED: Runtime Executor → Delivery Engine
- FORBIDDEN: Delivery Engine → Runtime Executor

Resolution needed: Clarify whether Runtime Executor calls Delivery Engine (allowed) or Delivery Engine is independent (forbidden).

ISSUE 2: Dependency Rules Contradiction (Verification Engine)
--------------------------------------------------
Severity: HIGH
Location: Section 8 (Dependency Rules) vs Section 2 (Engine Responsibility Matrix)

Explanation:
- Section 8 ALLOWED (line 371): Runtime Executor → Verification Engine
- Section 2 (line 102): Verification Engine triggered "After task completion", depends on "Engineering Brief"
- Section 7 (line 342): TaskCompleted published by Runtime Executor, consumed by Verification Engine

Exact contradiction:
- ALLOWED: Runtime Executor → Verification Engine
- Engine Responsibility Matrix: Verification Engine depends on Engineering Brief (not Runtime Executor)

Resolution needed: Clarify whether Verification Engine is called by Runtime Executor or is independent.

ISSUE 3: Event Model vs Dependency Rules (VerificationFailed)
--------------------------------------------------
Severity: MEDIUM
Location: Section 7 (Event Model) vs Section 9 (Failure Flow)

Explanation:
- Section 7 (line 344): VerificationFailed published by Verification Engine, consumed by Autonomy Engine
- Section 9 (line 426-430): Verification FAILURE fallback is "Mark task as verification_skipped", no Autonomy Engine involvement

Exact contradiction:
- Event Model: Autonomy Engine receives VerificationFailed
- Failure Flow: Verification failure does NOT trigger Autonomy Engine

Resolution needed: Clarify whether VerificationFailed triggers Autonomy Engine or is handled independently.

ISSUE 4: Inconsistent Terminology (MemoryStore vs Memory Service)
--------------------------------------------------
Severity: LOW
Location: Section 11 (Sequence Diagrams) vs Section 2 (Engine Responsibility Matrix)

Explanation:
- Section 11 (line 531): "ChatService → MemoryStore: store(conversation, response)"
- Section 2 (line 99): "Memory Service" is the engine name

Exact contradiction:
- Sequence Diagram uses "MemoryStore"
- Engine Responsibility Matrix uses "Memory Service"

Resolution needed: Use consistent terminology "Memory Service" throughout.

ISSUE 5: Missing Integration Contract (Autonomy Engine)
--------------------------------------------------
Severity: MEDIUM
Location: Section 12 (Integration Contracts)

Explanation:
- Section 2 (line 109): Autonomy Engine has defined inputs/outputs
- Section 12: No contract defined for Autonomy Engine

Exact contradiction:
- Engine Responsibility Matrix defines Autonomy Engine
- Integration Contracts does NOT define Autonomy Engine

Resolution needed: Add Autonomy Engine contract to Integration Contracts.

ISSUE 6: Missing Integration Contract (Runtime Executor)
--------------------------------------------------
Severity: MEDIUM
Location: Section 12 (Integration Contracts)

Explanation:
- Section 2 (line 110): Runtime Executor has defined inputs/outputs
- Section 12 (line 668-676): Contract exists but response is "success, results, error"

Exact contradiction:
- Engine Responsibility Matrix: Output is "Execution result"
- Integration Contract: Response is "success, results, error"

Resolution needed: Align contract response with engine output.

ISSUE 7: Implementation Order vs Dependencies (Verification Engine)
--------------------------------------------------
Severity: MEDIUM
Location: Implementation Order vs Section 3 (Integration Matrix)

Explanation:
- Implementation Order (line 817): Verification Engine depends on Runtime Executor
- Integration Matrix (line 122): Verification Engine called by Runtime Executor
- Implementation Order (line 815-818): Verification Engine is Week 2, before Discovery-Planning-TaskGraph-Dispatcher (Week 3)

Exact contradiction:
- Verification Engine depends on Runtime Executor
- But Runtime Executor calls Verification Engine
- Verification Engine is implemented before Runtime Executor is fully wired

Resolution needed: Clarify dependency direction and implementation order.

ISSUE 8: Decision Matrix vs Execution Pipeline (Research)
--------------------------------------------------
Severity: LOW
Location: Section 6 (Decision Matrix) vs Section 5 (Execution Pipeline)

Explanation:
- Decision Matrix (line 317): Research uses Discovery but NOT Planning/TaskGraph/Dispatcher
- Execution Pipeline (line 260-269): Discovery → Planning → TaskGraph → Dispatcher is sequential

Exact contradiction:
- Decision Matrix: Research skips Planning/TaskGraph/Dispatcher
- Execution Pipeline: Discovery leads to Planning leads to TaskGraph leads to Dispatcher

Resolution needed: Clarify whether Research uses only Discovery or the full pipeline.

ISSUE 9: State Machine vs Failure Flow (CONTEXT_READY)
--------------------------------------------------
Severity: LOW
Location: Section 10 (State Machine) vs Section 9 (Failure Flow)

Explanation:
- State Machine (line 460): CONTEXT_READY state exists
- Failure Flow: No failure defined for CONTEXT_READY state

Exact contradiction:
- State Machine defines CONTEXT_READY
- Failure Flow does not define failure for CONTEXT_READY

Resolution needed: Add CONTEXT_READY failure handling or remove state.

ISSUE 10: Integration Matrix vs Dependency Rules (ConversationEngine)
--------------------------------------------------
Severity: LOW
Location: Section 3 (Integration Matrix) vs Section 8 (Dependency Rules)

Explanation:
- Integration Matrix (line 121): ConversationEngine called by "ChatService route handler"
- Dependency Rules (line 356-360): ConversationEngine depends on Context Builder, Memory Service, Intent Detector
- Current implementation: ConversationEngine is called directly from /chat/stream route, NOT through ChatService

Exact contradiction:
- Integration Matrix says ChatService calls ConversationEngine
- Current implementation: Route handler calls ConversationEngine directly

Resolution needed: Clarify whether ChatService or route handler calls ConversationEngine.

==================================================
VERDICT
==================================================

REQUIRES REVISION

Reason: 2 HIGH severity contradictions found in Dependency Rules section.
Runtime Executor and Delivery Engine have conflicting allowed/forbidden dependencies.
Verification Engine dependency direction is unclear.

Recommended actions:
1. Resolve Dependency Rules contradictions (Issues 1, 2)
2. Clarify VerificationFailed event handling (Issue 3)
3. Add missing Autonomy Engine contract (Issue 5)
4. Fix terminology inconsistency (Issue 4)
5. Clarify Research pipeline (Issue 8)

==================================================
END OF REVIEW
==================================================

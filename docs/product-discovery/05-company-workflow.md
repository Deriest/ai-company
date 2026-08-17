# 05 — COMPANY WORKFLOW

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
5.1 OVERVIEW
==================================================

This document determines whether the repository implements a company workflow pattern.

Repository evidence:
- aic-platform/backend/services/orchestrator_service.py
- aic-platform/discovery/
- aic-platform/planning/
- aic-platform/taskgraph/
- aic-platform/dispatcher/
- aic-platform/verification/
- aic-platform/delivery/
- aic-platform/autonomy/

==================================================
5.2 COMPANY WORKFLOW CONCEPTS
==================================================

--------------------------------------------------
CONCEPT: Discovery
--------------------------------------------------
EXISTS: YES
Purpose: Analyze user requirements and generate engineering brief
Implementation: discovery/engine.py
Repository evidence: aic-platform/discovery/engine.py, discovery/brief.py, discovery/models.py

--------------------------------------------------
CONCEPT: Planning
--------------------------------------------------
EXISTS: YES
Purpose: Generate engineering plan from brief
Implementation: planning/engine.py
Repository evidence: aic-platform/planning/engine.py, planning/models.py

--------------------------------------------------
CONCEPT: Task Decomposition
--------------------------------------------------
EXISTS: YES
Purpose: Break plan into task graph
Implementation: taskgraph/engine.py
Repository evidence: aic-platform/taskgraph/engine.py, taskgraph/models.py

--------------------------------------------------
CONCEPT: Dispatcher
--------------------------------------------------
EXISTS: YES
Purpose: Route tasks to workers
Implementation: dispatcher/engine.py
Repository evidence: aic-platform/dispatcher/engine.py, dispatcher/queue.py

--------------------------------------------------
CONCEPT: Workers/Agents
--------------------------------------------------
EXISTS: YES
Purpose: Execute tasks
Implementation: workers/, backend/services/worker_runtime_service.py
Repository evidence: aic-platform/workers/, backend/services/worker_runtime_service.py

WORKER ROLES:
- Crafter: Code implementation specialist
- Manager: Workflow orchestration specialist
- Planner: Task planning and strategy
- Reviewer: Code review and quality assurance
- Thinker: Reasoning and planning specialist

Repository evidence: aic-platform/backend/services/worker_runtime_service.py

--------------------------------------------------
CONCEPT: Execution
--------------------------------------------------
EXISTS: YES
Purpose: Execute tasks through workers
Implementation: runtime/executor.py
Repository evidence: aic-platform/runtime/executor.py

--------------------------------------------------
CONCEPT: Verification
--------------------------------------------------
EXISTS: YES
Purpose: Verify worker output
Implementation: verification/engine.py
Repository evidence: aic-platform/verification/engine.py, verification/models.py

--------------------------------------------------
CONCEPT: Review
--------------------------------------------------
EXISTS: YES
Purpose: Review and approve work
Implementation: backend/models/orchestration.py (OrchestrationApproval)
Repository evidence: aic-platform/backend/models/orchestration.py

--------------------------------------------------
CONCEPT: Delivery
--------------------------------------------------
EXISTS: YES
Purpose: Package and deliver results
Implementation: delivery/engine.py
Repository evidence: aic-platform/delivery/engine.py, delivery/models.py

--------------------------------------------------
CONCEPT: Confidence
--------------------------------------------------
EXISTS: NOT SUPPORTED BY REPOSITORY EVIDENCE
Note: No confidence scoring system found

--------------------------------------------------
CONCEPT: Clarification
--------------------------------------------------
EXISTS: PARTIALLY
Purpose: Ask user for clarification
Implementation: discovery/engine.py (clarification questions)
Repository evidence: aic-platform/discovery/engine.py

--------------------------------------------------
CONCEPT: Approval
--------------------------------------------------
EXISTS: YES
Purpose: User approval for tasks
Implementation: backend/models/orchestration.py (OrchestrationApproval)
Repository evidence: aic-platform/backend/models/orchestration.py

==================================================
5.3 WORKFLOW SEQUENCE
==================================================

The repository implements the following workflow sequence:

1. DISCOVERY
   - User provides requirements
   - Discovery engine analyzes conversation
   - Generates engineering brief

2. PLANNING
   - Planning engine receives brief
   - Generates engineering plan
   - Breaks down into tasks

3. TASK GRAPH
   - Task graph engine receives plan
   - Creates task dependency graph
   - Determines execution order

4. DISPATCH
   - Dispatcher receives task graph
   - Routes tasks to appropriate workers
   - Manages task queue

5. EXECUTION
   - Workers execute assigned tasks
   - Runtime manages worker lifecycle
   - Progress tracked

6. VERIFICATION
   - Verification engine checks output
   - Quality validation
   - Generates verification report

7. DELIVERY
   - Delivery engine packages results
   - Generates delivery report
   - Presents to user

8. APPROVAL (OPTIONAL)
   - User approves/rejects work
   - Feedback loop to workers

Repository evidence:
- aic-platform/discovery/engine.py
- aic-platform/planning/engine.py
- aic-platform/taskgraph/engine.py
- aic-platform/dispatcher/engine.py
- aic-platform/runtime/executor.py
- aic-platform/verification/engine.py
- aic-platform/delivery/engine.py
- aic-platform/backend/models/orchestration.py

==================================================
5.4 WORKFLOW DIAGRAM
==================================================

User Requirements
       │
       ▼
┌─────────────────┐
│   Discovery     │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Planning      │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Task Graph    │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Dispatcher    │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Workers       │
│   (5 roles)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Verification  │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Delivery      │
│   Engine        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   User          │
│   Approval      │
└─────────────────┘

==================================================
5.5 ORCHESTRATION MODES
==================================================

The orchestrator supports two execution modes:

1. SEQUENTIAL
   - Tasks execute one after another
   - Each task completes before next starts
   - Repository evidence: aic-platform/backend/services/orchestrator_service.py

2. PARALLEL
   - Tasks execute simultaneously
   - Independent tasks run in parallel
   - Repository evidence: aic-platform/backend/services/orchestrator_service.py

==================================================
5.6 SHARED CONTEXT
==================================================

The orchestration system maintains shared context across workers:

- Session context: Shared across all tasks in a session
- Task context: Specific to each task
- Worker context: Worker-specific state

Repository evidence:
- aic-platform/backend/models/orchestration.py — OrchestrationSession.shared_context
- aic-platform/backend/models/orchestration.py — OrchestrationTask.input_context

==================================================
5.7 SUMMARY
==================================================

The repository DOES implement a company workflow pattern with:

✓ Discovery (requirement analysis)
✓ Planning (task decomposition)
✓ Task Graph (dependency management)
✓ Dispatcher (task routing)
✓ Workers (5 specialized roles)
✓ Execution (runtime management)
✓ Verification (quality checks)
✓ Delivery (result packaging)
✓ Approval (user feedback)
✗ Confidence scoring (not implemented)

The workflow is implemented as a pipeline of engine modules
that process user requirements through multiple stages to
produce verified, approved engineering work.

==================================================
END OF DOCUMENT
==================================================

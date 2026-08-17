# 06 — WORKER SYSTEM

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
6.1 WORKER REGISTRATION
==================================================

Workers are registered in the database with:
- Role (unique identifier)
- Status (idle, busy, error)
- Model assignment
- CPU/Memory metrics
- Task count

Repository evidence:
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/models/ai_runtime.py — WorkerRuntime model
- aic-platform/backend/models/schema.py — WORKER_DEFAULTS

DEFAULT WORKERS (from WORKER_DEFAULTS):
1. Crafter — Code implementation specialist
2. Manager — Workflow orchestration specialist
3. Planner — Task planning and strategy
4. Reviewer — Code review and quality assurance
5. Thinker — Reasoning and planning specialist

Repository evidence: aic-platform/backend/models/schema.py — WORKER_DEFAULTS

==================================================
6.2 WORKER LIFECYCLE
==================================================

STATES:
- idle: Worker is available
- busy: Worker is executing a task
- error: Worker encountered an error
- offline: Worker is not available

TRANSITIONS:
idle → busy: Task assigned
busy → idle: Task completed
busy → error: Task failed
error → idle: Error recovered

Repository evidence:
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/models/ai_runtime.py

==================================================
6.3 WORKER COMMUNICATION
==================================================

Workers communicate through:
1. Shared context (orchestration sessions)
2. Task dependencies (task graph)
3. Message passing (through orchestrator)

Repository evidence:
- aic-platform/backend/services/orchestrator_service.py
- aic-platform/backend/models/orchestration.py

==================================================
6.4 WORKER OWNERSHIP
==================================================

Workers are owned by:
- The system (default workers)
- Users (can configure worker models)

Repository evidence:
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/models/schema.py

==================================================
6.5 WORKER ORCHESTRATION
==================================================

Workers are orchestrated by:
- OrchestratorService (multi-agent sessions)
- DispatcherEngine (task routing)

ORCHESTRATION MODES:
- Sequential: Tasks execute one after another
- Parallel: Tasks execute simultaneously

Repository evidence:
- aic-platform/backend/services/orchestrator_service.py
- aic-platform/dispatcher/engine.py

==================================================
6.6 WORKER RESPONSIBILITIES
==================================================

CRAFTER:
- Code implementation
- Writing, refactoring, debugging
- File operations

MANAGER:
- Workflow orchestration
- Task delegation
- Progress tracking

PLANNER:
- Task planning
- Project architecture
- Breaking down complex tasks

REVIEWER:
- Code review
- Quality assurance
- Finding bugs and issues

THINKER:
- Reasoning and planning
- Long-context analysis
- Strategic thinking

Repository evidence:
- aic-platform/backend/models/schema.py — WORKER_DEFAULTS descriptions
- aic-ide/src/renderer/src/components/LiveCompanyView.tsx — Worker card descriptions

==================================================
6.7 WORKER DEPENDENCIES
==================================================

Workers depend on:
- LLM provider (for AI capabilities)
- Database (for state persistence)
- Orchestrator (for task coordination)
- Context engine (for context assembly)

Repository evidence:
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/services/orchestrator_service.py

==================================================
6.8 WORKER CAPABILITIES
==================================================

Each worker has:
- Role-specific system prompt
- Model assignment (configurable)
- Tool access (read_file, write_file, etc.)
- Context awareness (through context engine)

Repository evidence:
- aic-platform/workers/ — Worker definitions
- aic-platform/backend/services/chat_service.py — Tool schema

==================================================
6.9 WORKER METRICS
==================================================

Tracked metrics:
- CPU usage (percentage)
- Memory usage (MB)
- Task count
- Execution time
- Token usage

Repository evidence:
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/models/ai_runtime.py — WorkerExecution

==================================================
6.10 WORKER EXECUTION
==================================================

Execution flow:
1. Task assigned to worker
2. Worker receives task with context
3. Worker executes (calls LLM)
4. Worker produces output
5. Output verified
6. Results stored

Repository evidence:
- aic-platform/runtime/executor.py
- aic-platform/backend/services/orchestrator_service.py

==================================================
END OF DOCUMENT
==================================================

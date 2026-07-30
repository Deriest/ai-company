# 07 — STATE MANAGEMENT

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
7.1 OVERVIEW
==================================================

This document describes how state moves through the application.

Repository evidence:
- aic-platform/backend/models/
- aic-platform/backend/services/
- aic-ide/src/renderer/src/

==================================================
7.2 CONVERSATION STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/conversation.py

STATES:
- Active: Conversation is ongoing
- Archived: Conversation is completed

DATA:
- id: Unique identifier
- title: Conversation title
- created_at: Creation timestamp
- updated_at: Last update timestamp
- tags: Conversation tags
- pinned: Pin status

TRANSITIONS:
- Created → Active (user starts conversation)
- Active → Archived (user archives)
- Archived → Active (user restores)

Repository evidence:
- aic-platform/backend/models/conversation.py — Conversation model
- aic-platform/backend/routes/conversations.py — CRUD operations

==================================================
7.3 MESSAGE STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/conversation.py

DATA:
- id: Unique identifier
- conversation_id: Parent conversation
- role: user, assistant, system
- content: Message text
- model: Model used for generation
- provider: Provider used
- tokens_in: Input tokens
- tokens_out: Output tokens
- created_at: Creation timestamp

Repository evidence:
- aic-platform/backend/models/conversation.py — Message model

==================================================
7.4 TASK STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/orchestration.py

STATES:
- pending: Task created but not started
- queued: Task in queue
- running: Task executing
- completed: Task finished successfully
- failed: Task failed
- cancelled: Task cancelled

TRANSITIONS:
- pending → queued: Added to queue
- queued → running: Worker assigned
- running → completed: Execution successful
- running → failed: Execution failed
- pending/queued/running → cancelled: User cancelled

Repository evidence:
- aic-platform/backend/models/orchestration.py — OrchestrationTask

==================================================
7.5 PROJECT STATE
==================================================

LOCATION: Not supported by repository evidence
NOTE: No Project model found in backend/models/

Repository evidence: NOT SUPPORTED

==================================================
7.6 WORKER STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/ai_runtime.py

STATES:
- idle: Worker available
- busy: Worker executing
- error: Worker error
- offline: Worker unavailable

DATA:
- role: Worker role (unique)
- status: Current status
- model: Assigned model
- cpu_usage: CPU percentage
- memory_usage: Memory in MB
- task_count: Tasks completed
- last_active: Last activity timestamp

Repository evidence:
- aic-platform/backend/models/ai_runtime.py — WorkerRuntime

==================================================
7.7 EXECUTION STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/ai_runtime.py

DATA:
- id: Execution identifier
- worker_role: Worker that executed
- task_id: Task that was executed
- input_data: Input to worker
- output_data: Output from worker
- tokens_used: Token count
- duration_ms: Execution time
- status: Execution status
- created_at: Start timestamp
- completed_at: End timestamp

Repository evidence:
- aic-platform/backend/models/ai_runtime.py — WorkerExecution

==================================================
7.8 RUNTIME STATE
==================================================

LOCATION: In-memory (backend services)

COMPONENTS:
- ChatService: Active streaming sessions
- OrchestratorService: Active orchestration sessions
- WorkerRuntimeService: Worker status
- JobScheduler: Job queue

Repository evidence:
- aic-platform/backend/services/chat_service.py
- aic-platform/backend/services/orchestrator_service.py
- aic-platform/backend/services/worker_runtime_service.py
- aic-platform/backend/services/job_scheduler.py

==================================================
7.9 EVENT STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/ai_runtime.py — GenerationLog

DATA:
- id: Event identifier
- conversation_id: Related conversation
- model: Model used
- provider: Provider used
- prompt_tokens: Input tokens
- completion_tokens: Output tokens
- total_tokens: Total tokens
- cost_estimate: Estimated cost
- created_at: Timestamp

Repository evidence:
- aic-platform/backend/models/ai_runtime.py — GenerationLog

==================================================
7.10 MEMORY STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/storage/models.py

SCOPES:
- session: Current session only
- conversation: Single conversation
- workspace: Current workspace
- project: Single project
- user: User-wide

DATA:
- id: Entry identifier
- scope: Memory scope
- category: Entry category
- key: Entry key
- value: Entry value
- importance: Importance score
- created_at: Creation timestamp
- updated_at: Last update timestamp

Repository evidence:
- aic-platform/backend/services/memory_service.py
- aic-platform/storage/models.py

==================================================
7.11 ORCHESTRATION STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/orchestration.py

SESSION STATES:
- pending: Session created
- running: Session executing
- completed: Session finished
- cancelled: Session cancelled

DATA:
- id: Session identifier
- conversation_id: Related conversation
- mode: sequential/parallel
- status: Session status
- shared_context: Shared context across tasks
- created_at: Creation timestamp
- completed_at: Completion timestamp

Repository evidence:
- aic-platform/backend/models/orchestration.py — OrchestrationSession

==================================================
7.12 JOB STATE
==================================================

LOCATION: SQLite database
MODEL: aic-platform/backend/models/jobs.py

STATES:
- queued: Job in queue
- running: Job executing
- completed: Job finished
- failed: Job failed
- cancelled: Job cancelled
- paused: Job paused

DATA:
- id: Job identifier
- type: Job type
- status: Job status
- priority: Job priority
- progress: Progress percentage
- result: Job result
- error: Error message
- created_at: Creation timestamp
- started_at: Start timestamp
- completed_at: Completion timestamp

Repository evidence:
- aic-platform/backend/models/jobs.py — Job model

==================================================
END OF DOCUMENT
==================================================

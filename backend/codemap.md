# Repository Atlas: AIC-ADE Backend

## Project Responsibility

The AIC-ADE (Autonomous Engineering Platform) backend is a **multi-agent LLM orchestration system** that transforms natural language engineering requests into production-ready software through coordinated AI worker execution. The platform implements a complete engineering lifecycle pipeline—from discovery and requirements clarification through planning, implementation, verification, and delivery—using specialized AI agents (workers) organized by domain expertise and capability tiers.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **Intent Classification** | Regex-first pattern matching classifies user messages into task requests, questions, status inquiries, or approvals before any processing |
| **Smart Triage** | Automatically escalates tasks to appropriate execution levels (L1-QUICK through L4-FULL) based on scope, complexity, and guardrail triggers |
| **Agent Registry** | Centralized definitions of 15 specialized AI workers across Product, Engineering, Platform, and Leadership departments |
| **FSM Orchestration** | Deterministic state machine drives tasks through phases: created → discovery → investigate → planning → implementation → verification → closeout → completed |
| **Fault Tolerance** | Autonomy Engine detects anomalies, plans recovery actions, and executes healing strategies without manual intervention |
| **Quality Assurance** | Verification Engine validates outputs against acceptance criteria using keyword-based traceability and multi-dimensional quality scoring |
| **Event Streaming** | Real-time WebSocket broadcasts enable live UI updates for task progress, worker activity, and phase transitions |

---

## System Entry Points

### Main Application Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI application bootstrap, event bus initialization, heartbeat services |
| `backend/routes/*.py` | REST API endpoints for chat, conversations, tasks, approvals, dashboard |
| `backend/services/master_orchestrator.py` | High-level coordination of discovery→planning→taskgraph→dispatch stages |
| `backend/workers/base.py` | Abstract worker base class with SYSTEM_PROMPT injection from agent registry |
| `runtime/executor.py` | Core task execution engine orchestrating FSM phases and parallel workers |

### Configuration Manifests

| File | Purpose |
|------|---------|
| `storage/database.py` | SQLite async engine, session factories, database initialization |
| `backend/config/settings.py` | Environment variable loading for secrets and feature flags |
| `runtime.adaptive` | Capability profiles derived from LLM provider metadata |
| `policy/engine.py` | Policy Decision Point (PDP) for authorization gates |
| `shared/intent_patterns.py` | Canonical intent regex patterns used across conversation engine and API routes |

### Entry Scripts & Admin Utilities

| Script | Path | Purpose |
|--------|------|---------|
| `fix_url.py` | `scripts/archive/` | Database migration to update LLM provider URLs |
| `e2e_final.py` | `scripts/archive/` | End-to-end integration test suite validating full request→execution flow |

---

## Directory Map (Aggregated)

| Directory | Responsibility Summary | Detailed Map Link |
|-----------|------------------------|-------------------|
| `agents/` | **Canonical agent registry and context assembly system** defining 15 specialized LLM-powered workers; provides centralized data structures for agent identity, behavioral DNA (AgentSoul), tool permissions, model routing policies, and runtime context assembly via template method pattern | [View Map](agents/codemap.md) |
| `auth/` | **JWT authentication token management** implementing stateless authentication via symmetric cryptography (HMAC-SHA256); responsible for creating signed access tokens and verifying claims for API endpoints and WebSocket connections | [View Map](auth/codemap.md) |
| `autonomy/` | **Autonomous execution intelligence engine** for fault tolerance and self-healing; detects anomalies (timeouts, failures, deadlocks), determines recovery strategies (retry/replan/escalate), executes automated healing actions, and persists audit trails to database | [View Map](autonomy/codemap.md) |
| `context/` | **Persistent engineering memory and knowledge intelligence subsystem** providing RAG-based document retrieval, conversation history, project memories, and structured context assembly with token budget management; serves as central hub for injecting relevant context into LLM prompts | [View Map](context/codemap.md) |
| `conversation/` | **Primary AI operator layer** implementing conversational interface between users and engineering pipeline; handles intent classification, intake validation, task proposal/creation, fallback question answering, and coordinates with master orchestrator for background task execution | [View Map](conversation/codemap.md) |
| `data/` | **Data workspace sandboxes** for isolated per-conversation file operations and resource storage | N/A - no codemap.md found |
| `delivery/` | **Engineering output verification and continuous improvement** producing comprehensive reports documenting task outcomes, extracting lessons learned from failures, generating recommendations, and maintaining institutional knowledge via persistent lesson storage | [View Map](delivery/codemap.md) |
| `discovery/` | **Mandatory pre-processing gateway** transforming natural language requests into structured Engineering Briefs; performs intent classification, domain recognition, requirement extraction, ambiguity detection, readiness evaluation, and clarification management with configurable round limits | [View Map](discovery/codemap.md) |
| `dispatcher/` | **Core execution orchestration layer** transforming Task Graphs into distributed worker task execution; parses DAG structures, assigns optimal workers via capability-based selection, manages concurrent execution with isolated sessions, materializes PRD artifacts, and broadcasts real-time progress events | [View Map](dispatcher/codemap.md) |
| `events/` | **Asynchronous event bus with pub/sub semantics** providing centralized type-safe mechanism for decoupled communication between module boundaries; implements wildcard subscription, bounded LIFO history buffering, and fault-isolated handler execution with retry logic | [View Map](events/codemap.md) |
| `llm/` | **LLM Provider Abstraction Layer** serving vendor-neutral API for interacting with diverse providers (OpenAI, OpenRouter, vLLM, Ollama, etc.); implements tier-based model selection, smart routing, usage tracking, multi-turn conversation workarounds, concurrency limiting, and graceful degradation via fallback chains | [View Map](llm/codemap.md) |
| `observability/` | **Comprehensive observability infrastructure** implementing three pillars of modern monitoring: JSON-formatted structured logging with trace ID propagation, SQLite-backed time-series metrics collection, immutable audit trail logging, and real-time diagnostics service for system health monitoring | [View Map](observability/codemap.md) |
| `planning/` | **Planning engine** decomposing Engineering Briefs into technical approaches; generates implementation strategies, architecture decisions, risk mitigations, effort estimates, and acceptance criteria forming formal contracts handed off to task graph generation | N/A - no codemap.md found |
| `policy/` | **Policy Decision Point (PDP)** for authorization framework providing centralized gatekeeper evaluating ALL actions before execution; enforces security policies via cascading strategy pattern including hard denial filters, approval thresholds, user context validation, resource scope enforcement, sensitive path detection, task state guardians, and phase validity checks | [View Map](policy/codemap.md) |
| `runtime/` | **Unified adaptive execution engine** with smart triage and adaptive policies orchestrating multi-phase worker lifecycles through FSM; implements capability-based policy generation, progressive recovery ladders, local repair loops, dynamic escalation, isolation barriers, and compliance integrity checks | [View Map](runtime/codemap.md) |
| `scripts/` | **Administrative and operational utility layer** housing ephemeral automation scripts for database maintenance, end-to-end integration testing, and infrastructure configuration; functions as DevOps tooling external to core application lifecycle | [View Map](scripts/codemap.md) |
| `shared/` | **Cross-cutting utility functions** serving as single source of truth for key decision logic used across multiple subsystems; provides intake completeness evaluation, intent classification patterns, and workspace resolution algorithms eliminating code duplication | [View Map](shared/codemap.md) |
| `storage/` | **Persistence layer** providing canonical relational schema using SQLAlchemy 2.x async ORM; defines domain entities across autonomous engineering platform including task lifecycle, worker orchestration, discovery/engineering states, RAG infrastructure, plugin registries, and event ecosystem with optimistic locking via retry | [View Map](storage/codemap.md) |
| `taskgraph/` | **DAG generation & execution planning engine** transforming Engineering Plans into ordered Directed Acyclic Graphs defining execution sequences, dependencies, and parallelism opportunities; computes critical paths, detects cycles, generates recovery points, and persists serialized DAG structure for downstream dispatcher consumption | [View Map](taskgraph/codemap.md) |
| `verification/` | **Autonomous quality assurance module** validating worker-produced output against engineering brief acceptance criteria using declarative state-machine-driven orchestration; performs requirement traceability mapping, multi-dimensional quality scoring (code/tests/docs/security), regression analysis, and persists verification outcomes | [View Map](verification/codemap.md) |
| `workflow/` | **Task lifecycle management** using deterministic finite-state machine architecture; provides gatekeeper enforcing code-driven workflow rules, coordinator orchestrating multi-phase execution across specialized AI agents, validator applying barrier patterns ensuring required workers complete before phase advance, and guardrail rule engine scanning for risky keywords | [View Map](workflow/codemap.md) |

---

## Cross-Module Communication

### Event Bus Integration

The `events/` module provides asynchronous pub/sub messaging connecting all subsystems:

| Event Type | Producer | Consumers | Purpose |
|------------|----------|-----------|---------|
| `task.created` | Workflow engine, Executor | Frontend UI, Observability | Show new task start in Office Floor |
| `worker.started` / `worker.completed` / `worker.failed` | Runtime executor | Frontend UI | Highlight active workers, report completion/failure |
| `phase.advanced` | Workflow engine | Frontend UI, Metrics | Update progress bars, record state transitions |
| `pipeline.worker.started` / `pipeline.worker.completed` | Dispatcher engine | Observability, Automation hooks | Track long-running dispatch operations |
| `heartbeat.stale_tasks` / `heartbeat.blocked_leases` | Heartbeat service | Cleanup routines | Detect abandoned/stuck tasks |

Events follow standardized schema `{type, data, trace_id, timestamp}` enabling request correlation across async boundaries via `ContextVar` propagation in logging.

### Database Transaction Flow

```
User Request → ConversationEngine
     ↓
DiscoveryEngine.discover() → Persistence via AsyncSession
     ↓
MasterOrchestrator.run_engineering_pipeline()
     ├─ DiscoveryStage: Persist DiscoverySession + EngineeringBrief
     ├─ PlanningStage: Persist EngineeringPlan
     ├─ TaskGraphStage: Persist TaskGraphModel
     └─ DispatchStage: Create Tasks, Materialize PRD, Launch Workers
          ↓
RuntimeExecutor.execute_task()
     ├─ Isolate per-worker AsyncSessions
     ├─ Commits main session before gather()
     ├─ Worker leases persisted per iteration
     └─ Events emitted to EventBus + WebSocket
          ↓
VerificationEngine.verify(brief_id, task_results)
     ↓
DeliveryEngine.generate_report()
     ↓
Final COMPLETED status + LessonLearned persistence
```

**Critical Design Decision**: Explicit `await session.commit()` before `asyncio.gather()` prevents SQLite write-lock contention during long LLM calls while preserving transaction atomicity for phase transitions.

### API Gateway Contracts

All external-facing APIs require JWT authentication via `decode_access_token()` middleware, exposing routes under `/api/` namespace:

| Endpoint Category | Authentication Required? | Primary Function |
|------------------|-------------------------|------------------|
| `/api/auth/login` | No | Login, returns JWT access token |
| `/api/chat/*` | Yes | Direct task creation with streaming response |
| `/api/conversations/*` | Yes | Conversation lifecycle management |
| `/api/tasks/*` | Yes | Task CRUD operations, dispatch, status queries |
| `/api/approvals/*` | Yes | Human-in-the-loop approval gates |
| `/api/dashboard/*` | Yes | Overview statistics, entity lists |

Protected routes use Bearer token headers parsed by dependency injection patterns in FastAPI routers.

### LLM Provider Routing

```
LLMProvider.chat()
     ↓
ProviderManager._worker_fallback_chain(tier) → [THINKER, CRAFTER, SPRINTER]
     ↓
For each tier in chain:
     ├─ Resolve model name from provider config
     ├─ Flatten history if VansRouter detected (QA-249-R6 workaround)
     ├─ Inject reasoning_effort parameter if configured
     ├─ Acquire semaphore permit (max 4 concurrent outbound)
     ├─ httpx.AsyncClient.post("/chat/completions")
     ├─ Parse response (normalize formats, strip thinking tags)
     └─ Track usage asynchronously to DB
     ↓
If all tiers fail → Try fallback provider (if configured)
     ↓
Raise LLMError("All attempts exhausted")
```

Providers registered dynamically at startup via `init_provider_from_env()` reading `AIC_LLM_*` environment variables; hot-swappable via register/unregister API endpoints.

---

*Repository Atlas generated automatically from aggregated codemap.md files. Last updated: 2026-08-10*

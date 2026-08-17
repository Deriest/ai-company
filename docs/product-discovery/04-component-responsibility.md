# 04 — COMPONENT RESPONSIBILITY

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
4.1 FRONTEND COMPONENTS
==================================================

--------------------------------------------------
COMPONENT: AppShell
--------------------------------------------------
Purpose: Main application shell with sidebar navigation
Responsibilities: Layout, navigation, window controls
Inputs: children, view, onViewChange, health
Outputs: Rendered layout with sidebar and main content
Dependencies: React, Lucide icons
Called by: App.tsx
Calls: All view components

Repository evidence: aic-ide/src/renderer/src/components/AppShell.tsx

--------------------------------------------------
COMPONENT: ChatView
--------------------------------------------------
Purpose: Chat interface for AI conversation
Responsibilities: Message display, composer, history sidebar
Inputs: None (uses API)
Outputs: Messages sent to backend
Dependencies: apiClient, conversations API
Called by: AppShell
Calls: /chat, /chat/stream, /conversations

Repository evidence: aic-ide/src/renderer/src/components/ChatView.tsx

--------------------------------------------------
COMPONENT: WorkspaceView
--------------------------------------------------
Purpose: Main dashboard with quick actions
Responsibilities: Display workspace overview, quick actions
Inputs: None (uses API)
Outputs: Navigation actions
Dependencies: apiClient
Called by: AppShell
Calls: /runtime/workers

Repository evidence: aic-ide/src/renderer/src/components/WorkspaceView.tsx

--------------------------------------------------
COMPONENT: LiveCompanyView
--------------------------------------------------
Purpose: Worker status dashboard
Responsibilities: Display worker cards, worker details
Inputs: None (uses API)
Outputs: Worker selection
Dependencies: apiClient, runtime API
Called by: AppShell
Calls: /runtime/workers

Repository evidence: aic-ide/src/renderer/src/components/LiveCompanyView.tsx

--------------------------------------------------
COMPONENT: SettingsView
--------------------------------------------------
Purpose: Application configuration
Responsibilities: Provider setup, worker config, preferences
Inputs: None (uses API)
Outputs: Configuration changes
Dependencies: apiClient, providers API
Called by: AppShell
Calls: /providers, /profile

Repository evidence: aic-ide/src/renderer/src/components/SettingsView.tsx

--------------------------------------------------
COMPONENT: ObservabilityView
--------------------------------------------------
Purpose: Usage and cost monitoring
Responsibilities: Display token usage, costs, metrics
Inputs: None (uses API)
Outputs: None (read-only)
Dependencies: apiClient, usage API
Called by: AppShell
Calls: /api/usage/stats, /api/context/stats

Repository evidence: aic-ide/src/renderer/src/components/ObservabilityView.tsx

--------------------------------------------------
COMPONENT: ProjectsView
--------------------------------------------------
Purpose: Project management
Responsibilities: Display projects, filtering, search
Inputs: None (uses API)
Outputs: Project selection
Dependencies: None (empty state)
Called by: AppShell
Calls: None (no backend API)

Repository evidence: aic-ide/src/renderer/src/components/ProjectsView.tsx

--------------------------------------------------
COMPONENT: TimelineView
--------------------------------------------------
Purpose: Activity timeline
Responsibilities: Display events chronologically
Inputs: None (uses API)
Outputs: None (read-only)
Dependencies: None (empty state)
Called by: AppShell
Calls: None (no backend API)

Repository evidence: aic-ide/src/renderer/src/components/TimelineView.tsx

--------------------------------------------------
COMPONENT: EvidenceView
--------------------------------------------------
Purpose: Audit trail
Responsibilities: Display verification evidence
Inputs: None (uses API)
Outputs: None (read-only)
Dependencies: None (empty state)
Called by: AppShell
Calls: None (no backend API)

Repository evidence: aic-ide/src/renderer/src/components/EvidenceView.tsx

--------------------------------------------------
COMPONENT: OrchestrationView
--------------------------------------------------
Purpose: Multi-agent orchestration
Responsibilities: Session management, task management
Inputs: None (uses API)
Outputs: Session/task actions
Dependencies: apiClient, orchestration API
Called by: AppShell
Calls: /orchestration/sessions

Repository evidence: aic-ide/src/renderer/src/components/OrchestrationView.tsx

--------------------------------------------------
COMPONENT: WorkflowsView
--------------------------------------------------
Purpose: Workflow definition
Responsibilities: Workflow management, DAG visualization
Inputs: None (uses API)
Outputs: Workflow actions
Dependencies: apiClient, workflows API
Called by: AppShell
Calls: /workflows

Repository evidence: aic-ide/src/renderer/src/components/WorkflowsView.tsx

--------------------------------------------------
COMPONENT: JobsView
--------------------------------------------------
Purpose: Background job management
Responsibilities: Job listing, status, actions
Inputs: None (uses API)
Outputs: Job actions
Dependencies: apiClient, jobs API
Called by: AppShell
Calls: /jobs

Repository evidence: aic-ide/src/renderer/src/components/JobsView.tsx

--------------------------------------------------
COMPONENT: MCPView
--------------------------------------------------
Purpose: MCP server management
Responsibilities: Server registration, tool management
Inputs: None (uses API)
Outputs: MCP actions
Dependencies: apiClient, mcp API
Called by: AppShell
Calls: /mcp/servers, /mcp/tools

Repository evidence: aic-ide/src/renderer/src/components/MCPView.tsx

--------------------------------------------------
COMPONENT: MemoryView
--------------------------------------------------
Purpose: Memory management
Responsibilities: Memory CRUD, compression
Inputs: None (uses API)
Outputs: Memory actions
Dependencies: apiClient, memory API
Called by: AppShell
Calls: /memory

Repository evidence: aic-ide/src/renderer/src/components/MemoryView.tsx

--------------------------------------------------
COMPONENT: RAGView
--------------------------------------------------
Purpose: Document management
Responsibilities: Document CRUD, retrieval
Inputs: None (uses API)
Outputs: Document actions
Dependencies: apiClient, rag API
Called by: AppShell
Calls: /rag/documents

Repository evidence: aic-ide/src/renderer/src/components/RAGView.tsx

--------------------------------------------------
COMPONENT: AutomationView
--------------------------------------------------
Purpose: Automation management
Responsibilities: Hooks, triggers, notifications
Inputs: None (uses API)
Outputs: Automation actions
Dependencies: apiClient, automation API
Called by: AppShell
Calls: /hooks, /triggers, /notifications

Repository evidence: aic-ide/src/renderer/src/components/AutomationView.tsx

==================================================
4.2 BACKEND SERVICES
==================================================

--------------------------------------------------
SERVICE: ChatService
--------------------------------------------------
Purpose: Handle chat conversations
Responsibilities: Message processing, LLM interaction, tool execution
Inputs: User message, conversation ID
Outputs: AI response (streaming)
Dependencies: Provider, Context, ToolDispatcher, ArtifactService
Called by: API routes (/chat, /chat/stream)
Calls: LLM provider, Context engine, Tool dispatcher

Repository evidence: aic-platform/backend/services/chat_service.py

--------------------------------------------------
SERVICE: OrchestratorService
--------------------------------------------------
Purpose: Multi-agent orchestration
Responsibilities: Session management, task routing, execution
Inputs: Orchestration request
Outputs: Orchestration results
Dependencies: WorkerRuntimeService, ChatService
Called by: API routes (/orchestration/*)
Calls: Worker runtime, Chat service

Repository evidence: aic-platform/backend/services/orchestrator_service.py

--------------------------------------------------
SERVICE: WorkerRuntimeService
--------------------------------------------------
Purpose: Worker lifecycle management
Responsibilities: Worker registration, status, metrics
Inputs: Worker configuration
Outputs: Worker status
Dependencies: Database
Called by: OrchestratorService, API routes
Calls: Database

Repository evidence: aic-platform/backend/services/worker_runtime_service.py

--------------------------------------------------
SERVICE: MemoryService
--------------------------------------------------
Purpose: Multi-scope memory management
Responsibilities: Memory CRUD, retrieval, compression
Inputs: Memory entries
Outputs: Retrieved memories
Dependencies: Database
Called by: API routes (/memory), Context engine
Calls: Database

Repository evidence: aic-platform/backend/services/memory_service.py

--------------------------------------------------
SERVICE: RAGService
--------------------------------------------------
Purpose: Document retrieval
Responsibilities: Document management, chunking, retrieval
Inputs: Documents, queries
Outputs: Relevant chunks
Dependencies: EmbeddingProvider
Called by: API routes (/rag/*), Context engine
Calls: Embedding provider

Repository evidence: aic-platform/backend/services/rag_service.py

--------------------------------------------------
SERVICE: MCPService
--------------------------------------------------
Purpose: MCP server management
Responsibilities: Server registry, tool discovery, execution
Inputs: MCP server configuration
Outputs: Tool execution results
Dependencies: None
Called by: API routes (/mcp/*)
Calls: External MCP servers

Repository evidence: aic-platform/backend/services/mcp_service.py

--------------------------------------------------
SERVICE: AutomationService
--------------------------------------------------
Purpose: Event automation
Responsibilities: Hooks, triggers, notifications
Inputs: Events
Outputs: Triggered actions
Dependencies: Database
Called by: API routes (/hooks, /triggers, /notifications)
Calls: Database

Repository evidence: aic-platform/backend/services/automation_service.py

--------------------------------------------------
SERVICE: JobScheduler
--------------------------------------------------
Purpose: Background job management
Responsibilities: Job queue, execution, retry
Inputs: Job definitions
Outputs: Job results
Dependencies: Database
Called by: API routes (/jobs)
Calls: Database

Repository evidence: aic-platform/backend/services/job_scheduler.py

--------------------------------------------------
SERVICE: PricingService
--------------------------------------------------
Purpose: Cost calculation
Responsibilities: Token pricing, cost estimation
Inputs: Token counts
Outputs: Cost estimates
Dependencies: None
Called by: API routes (/usage/*)
Calls: None

Repository evidence: aic-platform/backend/services/pricing_service.py

--------------------------------------------------
SERVICE: ProfileService
--------------------------------------------------
Purpose: User profile management
Responsibilities: Profile CRUD, onboarding
Inputs: Profile data
Outputs: Profile object
Dependencies: Database
Called by: API routes (/profile)
Calls: Database

Repository evidence: aic-platform/backend/services/profile_service.py

==================================================
4.3 ENGINE MODULES
==================================================

--------------------------------------------------
ENGINE: DiscoveryEngine
--------------------------------------------------
Purpose: Engineering discovery and requirement analysis
Responsibilities: Conversation analysis, brief generation
Inputs: Conversation messages
Outputs: Engineering brief
Dependencies: Database
Called by: Discovery routes
Calls: Database

Repository evidence: aic-platform/discovery/engine.py

--------------------------------------------------
ENGINE: PlanningEngine
--------------------------------------------------
Purpose: Task planning and decomposition
Responsibilities: Plan generation, task breakdown
Inputs: Engineering brief
Outputs: Engineering plan
Dependencies: Database
Called by: Planning routes
Calls: Database

Repository evidence: aic-platform/planning/engine.py

--------------------------------------------------
ENGINE: TaskGraphEngine
--------------------------------------------------
Purpose: Task graph generation
Responsibilities: Task decomposition, dependency graph
Inputs: Engineering plan
Outputs: Task graph
Dependencies: Database
Called by: TaskGraph routes
Calls: Database

Repository evidence: aic-platform/taskgraph/engine.py

--------------------------------------------------
ENGINE: DispatcherEngine
--------------------------------------------------
Purpose: Task dispatching
Responsibilities: Task routing, worker assignment
Inputs: Task graph
Outputs: Dispatched tasks
Dependencies: WorkerRuntimeService
Called by: Dispatcher routes
Calls: Worker runtime

Repository evidence: aic-platform/dispatcher/engine.py

--------------------------------------------------
ENGINE: VerificationEngine
--------------------------------------------------
Purpose: Output verification
Responsibilities: Quality checks, validation
Inputs: Worker output
Outputs: Verification report
Dependencies: Database
Called by: Verification routes
Calls: Database

Repository evidence: aic-platform/verification/engine.py

--------------------------------------------------
ENGINE: ContextEngine
--------------------------------------------------
Purpose: Context assembly
Responsibilities: Context building, source management
Inputs: Query, conversation ID
Outputs: Assembled context
Dependencies: MemoryService, RAGService
Called by: ChatService
Calls: Memory, RAG, Workspace sources

Repository evidence: aic-platform/context/engine.py

--------------------------------------------------
ENGINE: DeliveryEngine
--------------------------------------------------
Purpose: Result delivery
Responsibilities: Report generation, artifact packaging
Inputs: Verification report
Outputs: Delivery package
Dependencies: Database
Called by: Delivery routes
Calls: Database

Repository evidence: aic-platform/delivery/engine.py

--------------------------------------------------
ENGINE: AutonomyEngine
--------------------------------------------------
Purpose: Anomaly detection
Responsibilities: Anomaly detection, self-healing
Inputs: System metrics
Outputs: Anomaly alerts
Dependencies: Database
Called by: Autonomy routes
Calls: Database

Repository evidence: aic-platform/autonomy/engine.py

==================================================
END OF DOCUMENT
==================================================

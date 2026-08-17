# 09 — UI NAVIGATION

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
9.1 SIDEBAR NAVIGATION
==================================================

The application has 15 sidebar items:

1. Workspace (home)
2. Chat (hermes)
3. Projects (mission)
4. Live Company (live)
5. Timeline (timeline)
6. Evidence (evidence)
7. Observability (observability)
8. Orchestration (orchestration)
9. Workflows (workflows)
10. Jobs (jobs)
11. MCP Servers (mcp)
12. Memory (memory)
13. RAG Docs (rag)
14. Automation (automation)
15. Settings (settings)

Repository evidence:
- aic-ide/src/renderer/src/components/AppShell.tsx — nav array

==================================================
9.2 PAGE DESCRIPTIONS
==================================================

--------------------------------------------------
PAGE: Workspace
--------------------------------------------------
Route: / (default)
Purpose: Entry point, project overview
Components: Quick actions, recent activity, active missions
Repository evidence: aic-ide/src/renderer/src/components/WorkspaceView.tsx

--------------------------------------------------
PAGE: Chat
--------------------------------------------------
Route: /chat
Purpose: AI conversation interface
Components: History sidebar, message area, composer
Repository evidence: aic-ide/src/renderer/src/components/ChatView.tsx

--------------------------------------------------
PAGE: Projects
--------------------------------------------------
Route: /projects
Purpose: Project management
Components: Project list, filters, search
Repository evidence: aic-ide/src/renderer/src/components/ProjectsView.tsx

--------------------------------------------------
PAGE: Live Company
--------------------------------------------------
Route: /live
Purpose: Worker dashboard
Components: Worker cards, worker details, pipeline, diagnostics
Repository evidence: aic-ide/src/renderer/src/components/LiveCompanyView.tsx

--------------------------------------------------
PAGE: Timeline
--------------------------------------------------
Route: /timeline
Purpose: Activity timeline
Components: Event list, filters, date selector
Repository evidence: aic-ide/src/renderer/src/components/TimelineView.tsx

--------------------------------------------------
PAGE: Evidence
--------------------------------------------------
Route: /evidence
Purpose: Audit trail
Components: Evidence list (empty state)
Repository evidence: aic-ide/src/renderer/src/components/EvidenceView.tsx

--------------------------------------------------
PAGE: Observability
--------------------------------------------------
Route: /observability
Purpose: Usage monitoring
Components: Metrics cards, tabs (Overview, Context, Workers, Usage)
Repository evidence: aic-ide/src/renderer/src/components/ObservabilityView.tsx

--------------------------------------------------
PAGE: Orchestration
--------------------------------------------------
Route: /orchestration
Purpose: Multi-agent orchestration
Components: Session list, session details, task management
Repository evidence: aic-ide/src/renderer/src/components/OrchestrationView.tsx

--------------------------------------------------
PAGE: Workflows
--------------------------------------------------
Route: /workflows
Purpose: Workflow definition
Components: Workflow list, DAG preview
Repository evidence: aic-ide/src/renderer/src/components/WorkflowsView.tsx

--------------------------------------------------
PAGE: Jobs
--------------------------------------------------
Route: /jobs
Purpose: Background jobs
Components: Job list, status filters
Repository evidence: aic-ide/src/renderer/src/components/JobsView.tsx

--------------------------------------------------
PAGE: MCP Servers
--------------------------------------------------
Route: /mcp
Purpose: MCP server management
Components: Server list, tools, execution history
Repository evidence: aic-ide/src/renderer/src/components/MCPView.tsx

--------------------------------------------------
PAGE: Memory
--------------------------------------------------
Route: /memory
Purpose: Memory management
Components: Memory list, search, CRUD
Repository evidence: aic-ide/src/renderer/src/components/MemoryView.tsx

--------------------------------------------------
PAGE: RAG Docs
--------------------------------------------------
Route: /rag
Purpose: Document management
Components: Document list, upload, retrieval
Repository evidence: aic-ide/src/renderer/src/components/RAGView.tsx

--------------------------------------------------
PAGE: Automation
--------------------------------------------------
Route: /automation
Purpose: Automation management
Components: Hooks, triggers, notifications
Repository evidence: aic-ide/src/renderer/src/components/AutomationView.tsx

--------------------------------------------------
PAGE: Settings
--------------------------------------------------
Route: /settings
Purpose: Application configuration
Components: 11 tabs (General, Account, Security, Sessions, Providers, Worker Runtime, Update, Auto Approve, Telemetry, About, Advanced)
Repository evidence: aic-ide/src/renderer/src/components/SettingsView.tsx

==================================================
9.3 PRIMARY WORKFLOWS
==================================================

WORKFLOW 1: First Launch
1. Splash screen
2. Onboarding (name input)
3. Provider setup
4. Workspace dashboard

Repository evidence:
- aic-ide/src/renderer/src/components/Splash.tsx
- aic-ide/src/renderer/src/components/auth/OnboardingFlow.tsx
- aic-ide/src/renderer/src/components/auth/ProviderSetup.tsx

WORKFLOW 2: Chat Conversation
1. Click "Chat" in sidebar
2. Click "+ New Chat"
3. Type message
4. View AI response
5. Continue conversation

Repository evidence:
- aic-ide/src/renderer/src/components/ChatView.tsx

WORKFLOW 3: Worker Monitoring
1. Click "Live Company" in sidebar
2. View worker cards
3. Click worker to see details
4. View metrics, tasks, logs

Repository evidence:
- aic-ide/src/renderer/src/components/LiveCompanyView.tsx

WORKFLOW 4: Provider Configuration
1. Click "Settings" in sidebar
2. Click "Providers" tab
3. Add/edit provider
4. Fetch models
5. Test connection

Repository evidence:
- aic-ide/src/renderer/src/components/SettingsView.tsx

==================================================
9.4 DIALOGS AND MODALS
==================================================

DIALOG: Provider Setup
Purpose: Configure AI provider
Trigger: Settings → Providers → Add Provider
Repository evidence: aic-ide/src/renderer/src/components/auth/ProviderSetup.tsx

DIALOG: Worker Config
Purpose: Configure worker model
Trigger: Settings → Worker Runtime
Repository evidence: aic-ide/src/renderer/src/components/SettingsView.tsx

DIALOG: Approval
Purpose: Approve/reject orchestration tasks
Trigger: Orchestration → Task approval
Repository evidence: aic-ide/src/renderer/src/components/OrchestrationView.tsx

==================================================
9.5 TOP BAR
==================================================

ELEMENTS:
- Window title: "AIC ADE — AI Company Workspace"
- Window controls: Minimize, Maximize, Close
- Version label: Displayed in footer

Repository evidence:
- aic-ide/src/renderer/src/components/AppShell.tsx

==================================================
9.6 FOOTER
==================================================

ELEMENTS:
- System status: "System operational"
- Version: "OC/MIMO-V2.5-FREE"

Repository evidence:
- aic-ide/src/renderer/src/components/AppShell.tsx

==================================================
9.7 KEYBOARD SHORTCUTS
==================================================

SHORTCUTS:
- Ctrl+N: New chat
- Ctrl+,: Settings
- Ctrl+/: Help

Repository evidence:
- aic-ide/src/renderer/src/App.tsx — useEffect keyboard handler

==================================================
END OF DOCUMENT
==================================================

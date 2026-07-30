# PRODUCT UI AUDIT — USER EXPERIENCE INVESTIGATION

==================================================
DATE: 2026-07-29
TYPE: READ-ONLY INVESTIGATION
==================================================

==================================================
MASTER TABLE
==================================================

| UI Name | Purpose | Current Location | Target User | Category | Business Value | Frequency | Recommendation | Reason |
|---------|---------|------------------|-------------|----------|----------------|-----------|----------------|--------|
| Workspace | Dashboard with stats, activity, quick actions | Sidebar | All users | A: Core | HIGH | Daily | Keep | Entry point for all users |
| Chat | AI conversation interface | Sidebar | All users | A: Core | HIGH | Daily | Keep | Primary interaction method |
| Projects | Project and mission management | Sidebar | All users | A: Core | HIGH | Daily | Keep | Organizes work |
| Live Company | Worker dashboard and status | Sidebar | Power users | B: Power | MEDIUM | Weekly | Keep | Worker monitoring |
| Timeline | System and mission events | Sidebar | Operators | C: Operator | LOW | Monthly | Move to Live Company | Operational monitoring |
| Evidence | Audit trail of verifications | Sidebar | Operators | C: Operator | LOW | Monthly | Move to Live Company | Compliance tracking |
| Observability | Usage metrics and statistics | Sidebar | Operators | C: Operator | MEDIUM | Weekly | Move to Live Company | System monitoring |
| Orchestration | Multi-agent session management | Sidebar | Power users | B: Power | MEDIUM | Weekly | Move to Settings | Advanced feature |
| Workflows | Workflow DAG management | Sidebar | Power users | B: Power | MEDIUM | Weekly | Move to Settings | Advanced feature |
| Jobs | Background job management | Sidebar | Power users | B: Power | MEDIUM | Weekly | Move to Settings | Advanced feature |
| MCP Servers | MCP server management | Sidebar | Power users | B: Power | LOW | Monthly | Move to Settings | Advanced feature |
| Memory | Multi-scope memory management | Sidebar | Power users | B: Power | LOW | Monthly | Move to Settings | Advanced feature |
| RAG Docs | Document management for RAG | Sidebar | Power users | B: Power | LOW | Monthly | Move to Settings | Advanced feature |
| Automation | Event hooks and triggers | Sidebar | Power users | B: Power | LOW | Monthly | Move to Settings | Advanced feature |
| Settings | Configuration and setup | Sidebar | All users | A: Core | HIGH | Weekly | Keep | Required for setup |
| General | General settings | Settings tab | All users | A: Core | HIGH | Weekly | Keep | Basic configuration |
| Account | User account settings | Settings tab | All users | A: Core | MEDIUM | Monthly | Keep | Profile management |
| Security | Security settings | Settings tab | All users | A: Core | MEDIUM | Monthly | Keep | Security configuration |
| Sessions | Session management | Settings tab | Power users | B: Power | LOW | Monthly | Keep | Session control |
| Providers | LLM provider configuration | Settings tab | All users | A: Core | HIGH | Weekly | Keep | Required for AI |
| Worker Runtime | Worker configuration | Settings tab | Power users | B: Power | MEDIUM | Monthly | Keep | Worker management |
| Update | Application updates | Settings tab | All users | A: Core | MEDIUM | Monthly | Keep | Update management |
| Auto Approve | Approval automation | Settings tab | Power users | B: Power | LOW | Monthly | Keep | Workflow automation |
| Telemetry | Usage telemetry | Settings tab | Operators | C: Operator | LOW | Monthly | Hide | Internal metrics |
| About | Application information | Settings tab | All users | A: Core | LOW | Rare | Keep | Version info |
| Advanced | Advanced settings | Settings tab | Power users | B: Power | LOW | Rare | Keep | Expert configuration |

==================================================
CATEGORY A: CORE PRODUCT (7 items)
==================================================

1. Workspace — Dashboard entry point
2. Chat — AI conversation interface
3. Projects — Project management
4. Settings — Configuration
5. Providers — LLM setup
6. General — Basic settings
7. About — Version info

These must be immediately accessible and dominate the interface.

==================================================
CATEGORY B: POWER USER (10 items)
==================================================

1. Live Company — Worker dashboard
2. Orchestration — Multi-agent sessions
3. Workflows — Workflow management
4. Jobs — Background jobs
5. MCP Servers — External tools
6. Memory — Knowledge management
7. RAG Docs — Document management
8. Automation — Event automation
9. Sessions — Session control
10. Worker Runtime — Worker config

These should exist but not dominate the interface.

==================================================
CATEGORY C: OPERATOR (4 items)
==================================================

1. Timeline — Event timeline
2. Evidence — Audit trail
3. Observability — Usage metrics
4. Telemetry — Internal metrics

These are for monitoring and administration only.

==================================================
CATEGORY D: INTERNAL SYSTEM (0 items)
==================================================

No UI elements are purely internal system details.

==================================================
PAGES TO KEEP (7)
==================================================

1. Workspace — Entry point
2. Chat — Primary interaction
3. Projects — Work organization
4. Settings — Configuration
5. Providers — LLM setup
6. General — Basic settings
7. About — Version info

==================================================
PAGES TO MERGE (3)
==================================================

1. Timeline → Merge into Live Company
2. Evidence → Merge into Live Company
3. Observability → Merge into Live Company

Reason: These are all operational monitoring pages that belong together.

==================================================
PAGES TO MOVE TO SETTINGS (7)
==================================================

1. Orchestration → Settings tab
2. Workflows → Settings tab
3. Jobs → Settings tab
4. MCP Servers → Settings tab
5. Memory → Settings tab
6. RAG Docs → Settings tab
7. Automation → Settings tab

Reason: These are advanced features that don't need daily access.

==================================================
PAGES TO HIDE (1)
==================================================

1. Telemetry → Hide from Settings

Reason: Internal metrics not useful for users.

==================================================
PAGES TO REMOVE (0)
==================================================

None.

==================================================
PAGES TO CONVERT TO ADVANCED SETTINGS (0)
==================================================

None.

==================================================
PAGES TO CONVERT TO DEVELOPER MODE (0)
==================================================

None.

==================================================
IDEAL NAVIGATION HIERARCHY
==================================================

SIDEBAR (5 items):
├── Workspace (entry point)
├── Chat (conversation center)
├── Projects (project management)
├── Live Company (operational center)
│   ├── Workers
│   ├── Timeline
│   ├── Evidence
│   └── Observability
└── Settings (configuration)
    ├── General
    ├── Account
    ├── Security
    ├── Sessions
    ├── Providers
    ├── Worker Runtime
    ├── Update
    ├── Auto Approve
    ├── About
    ├── Advanced
    ├── Orchestration
    ├── Workflows
    ├── Jobs
    ├── MCP Servers
    ├── Memory
    ├── RAG Docs
    └── Automation

==================================================
RATIONALE
==================================================

1. REDUCES SIDEBAR FROM 15 TO 5 ITEMS
   - Less cognitive load
   - Easier navigation
   - Cleaner interface

2. GROUPS RELATED FEATURES
   - Timeline, Evidence, Observability → Live Company
   - Orchestration, Workflows, Jobs → Settings
   - MCP, Memory, RAG, Automation → Settings

3. PRESERVES ALL FUNCTIONALITY
   - No features removed
   - All capabilities accessible
   - Just reorganized

4. ALIGNS WITH PRODUCT PHILOSOPHY
   - Conversation First → Chat is primary
   - Worker Oriented → Live Company is operational center
   - Desktop Native → Simple navigation
   - Local First → No cloud complexity

5. IMPROVES DISCOVERABILITY
   - Core features are immediately visible
   - Power features are in Settings
   - Operator features are in Live Company

==================================================
CUSTOMER PERSPECTIVE
==================================================

NORMAL CUSTOMER UNDERSTANDING:
- Workspace: "This is where I start"
- Chat: "This is where I talk to AI"
- Projects: "This is where I organize work"
- Live Company: "This is where I see what's happening"
- Settings: "This is where I configure things"

CONFUSING ELEMENTS (current):
- Timeline: "What events?"
- Evidence: "What evidence?"
- Observability: "What metrics?"
- Orchestration: "What is orchestration?"
- Workflows: "What workflows?"
- Jobs: "What jobs?"
- MCP Servers: "What is MCP?"
- Memory: "What memory?"
- RAG Docs: "What is RAG?"
- Automation: "What automation?"

==================================================
BUSINESS VALUE ANALYSIS
==================================================

HIGH VALUE (daily use):
- Chat — Primary AI interaction
- Workspace — Entry point
- Projects — Work organization
- Providers — LLM configuration

MEDIUM VALUE (weekly use):
- Live Company — Worker monitoring
- Settings — Configuration
- Orchestration — Multi-agent tasks
- Workflows — Workflow management
- Jobs — Background jobs

LOW VALUE (monthly use):
- Timeline — Event history
- Evidence — Audit trail
- Observability — Usage metrics
- MCP Servers — External tools
- Memory — Knowledge management
- RAG Docs — Document management
- Automation — Event automation

==================================================
FREQUENCY ANALYSIS
==================================================

DAILY:
- Chat — Every session
- Workspace — Every session
- Projects — Most sessions

WEEKLY:
- Live Company — Worker monitoring
- Settings — Configuration changes
- Providers — Provider management

MONTHLY:
- Timeline — Event review
- Evidence — Audit review
- Observability — Metrics review
- Orchestration — Multi-agent tasks
- Workflows — Workflow changes
- Jobs — Job management
- MCP Servers — Tool management
- Memory — Knowledge updates
- RAG Docs — Document updates
- Automation — Hook changes

==================================================
END OF AUDIT
==================================================

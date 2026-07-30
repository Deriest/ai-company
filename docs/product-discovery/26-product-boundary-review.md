# PRODUCT BOUNDARY REVIEW

==================================================
DATE: 2026-07-29
TYPE: READ-ONLY INVESTIGATION
==================================================

==================================================
FEATURE ANALYSIS
==================================================

--------------------------------------------------
WORKSPACE
--------------------------------------------------

1. What user goal does this support?
   Entry point — see overview of work, quick actions, recent activity.

2. Would a new customer naturally expect this feature?
   YES — Every application needs a dashboard/home screen.

3. How frequently would users interact with it?
   Every session — First screen users see.

4. Does this belong in the user's mental model?
   YES — Users expect a home/dashboard screen.

5. Does exposing this feature increase or decrease usability?
   INCREASE — Provides overview and quick access.

6. Should users actively control it?
   NO — Should be automatic entry point.

7. If hidden, would the product become worse?
   YES — Users would have no entry point.

8. If removed from UI, would the backend still deliver the same value?
   NO — Users need a starting point.

9. Should this be: Primary Sidebar
   YES — Entry point must be immediately visible.

10. If commercial competitors were designing this feature, where would they likely place it?
    Primary Sidebar — ChatGPT, Claude, Cursor all have home screens.

Evidence: WorkspaceView.tsx shows dashboard with stats, activity, quick actions.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: Could be merged with Chat as default view.

--------------------------------------------------
CHAT
--------------------------------------------------

1. What user goal does this support?
   Talk to AI — ask questions, get help, create tasks.

2. Would a new customer naturally expect this feature?
   YES — Core product functionality.

3. How frequently would users interact with it?
   Every session — Primary interaction method.

4. Does this belong in the user's mental model?
   YES — Users expect to chat with AI.

5. Does exposing this feature increase or decrease usability?
   INCREASE — Core product functionality.

6. Should users actively control it?
   YES — Users control conversations.

7. If hidden, would the product become worse?
   YES — Core functionality would be lost.

8. If removed from UI, would the backend still deliver the same value?
   NO — Users need to interact with AI.

9. Should this be: Primary Sidebar
   YES — Core product must be immediately visible.

10. If commercial competitors were designing this feature, where would they likely place it?
    Primary Sidebar — ChatGPT, Claude, Cursor all have chat as primary.

Evidence: ChatView.tsx shows conversation interface with streaming.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Chat is core product.

--------------------------------------------------
PROJECTS
--------------------------------------------------

1. What user goal does this support?
   Organize work — group related tasks, track progress.

2. Would a new customer naturally expect this feature?
   MAYBE — Some users expect project organization, others don't.

3. How frequently would users interact with it?
   Weekly — Users organize work periodically.

4. Does this belong in the user's mental model?
   YES — Users expect to organize work into projects.

5. Does exposing this feature increase or decrease usability?
   INCREASE — Helps users organize complex work.

6. Should users actively control it?
   YES — Users create and manage projects.

7. If hidden, would the product become worse?
   MAYBE — Users could still work without explicit projects.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend could auto-organize by conversation.

9. Should this be: Primary Sidebar
   MAYBE — Could be secondary or project-level.

10. If commercial competitors were designing this feature, where would they likely place it?
    Primary Sidebar — Cursor, Notion AI have project organization.

Evidence: ProjectsView.tsx shows project list with status.
Confidence: MEDIUM
Assumptions: Users need explicit project organization.
Unknowns: Whether auto-organization would suffice.
Alternative interpretation: Could be merged with Workspace.

--------------------------------------------------
LIVE COMPANY
--------------------------------------------------

1. What user goal does this support?
   Monitor AI workers — see what's happening, who's working.

2. Would a new customer naturally expect this feature?
   MAYBE — Power users expect monitoring, others don't.

3. How frequently would users interact with it?
   Weekly — Users check worker status periodically.

4. Does this belong in the user's mental model?
   MAYBE — Users may not understand "Live Company" concept.

5. Does exposing this feature increase or decrease usability?
   INCREASE for power users, DECREASE for beginners.

6. Should users actively control it?
   NO — Should be read-only monitoring.

7. If hidden, would the product become worse?
   MAYBE — Power users would lose monitoring capability.

8. If removed from UI, would the backend still deliver the same value?
   YES — Workers still execute without monitoring UI.

9. Should this be: Secondary Navigation
   YES — Advanced monitoring for power users.

10. If commercial competitors were designing this feature, where would they likely place it?
    Settings or Advanced — Cursor has execution monitoring in panels.

Evidence: LiveCompanyView.tsx shows worker dashboard with metrics.
Confidence: MEDIUM
Assumptions: Users need worker monitoring.
Unknowns: Whether workers should be visible or hidden.
Alternative interpretation: Could be merged with Chat as side panel.

--------------------------------------------------
TIMELINE
--------------------------------------------------

1. What user goal does this support?
   See history — what happened, when, by whom.

2. Would a new customer naturally expect this feature?
   NO — Users don't expect separate timeline page.

3. How frequently would users interact with it?
   Rarely — Users check history occasionally.

4. Does this belong in the user's mental model?
   NO — Users expect history in context, not separate page.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic history tracking.

7. If hidden, would the product become worse?
   NO — History could be in context.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend tracks history regardless.

9. Should this be: Hidden or Automatic
   YES — History should be in context, not separate page.

10. If commercial competitors were designing this feature, where would they likely place it?
    Context panel — ChatGPT, Claude show history in conversation.

Evidence: TimelineView.tsx shows empty timeline events array.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: Could be merged with Live Company.

--------------------------------------------------
EVIDENCE
--------------------------------------------------

1. What user goal does this support?
   Audit trail — verification, commits, reports.

2. Would a new customer naturally expect this feature?
   NO — Users don't expect separate evidence page.

3. How frequently would users interact with it?
   Rarely — Users check evidence occasionally.

4. Does this belong in the user's mental model?
   NO — Users expect evidence in context.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic evidence tracking.

7. If hidden, would the product become worse?
   NO — Evidence could be in context.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend tracks evidence regardless.

9. Should this be: Hidden or Automatic
   YES — Evidence should be in context, not separate page.

10. If commercial competitors were designing this feature, where would they likely place it?
    Context panel — Cursor shows evidence in execution panels.

Evidence: EvidenceView.tsx shows empty evidence records array.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: Could be merged with Live Company.

--------------------------------------------------
OBSERVABILITY
--------------------------------------------------

1. What user goal does this support?
   Monitor usage — tokens, cost, performance.

2. Would a new customer naturally expect this feature?
   MAYBE — Power users expect monitoring, others don't.

3. How frequently would users interact with it?
   Weekly — Users check usage periodically.

4. Does this belong in the user's mental model?
   MAYBE — Users may not understand "Observability" concept.

5. Does exposing this feature increase or decrease usability?
   INCREASE for power users, DECREASE for beginners.

6. Should users actively control it?
   NO — Should be read-only monitoring.

7. If hidden, would the product become worse?
   MAYBE — Power users would lose monitoring capability.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend tracks usage regardless.

9. Should this be: Settings or Advanced
   YES — Monitoring belongs in Settings.

10. If commercial competitors were designing this feature, where would they likely place it?
    Settings — ChatGPT, Claude show usage in settings.

Evidence: ObservabilityView.tsx shows usage statistics.
Confidence: MEDIUM
Assumptions: Users need usage monitoring.
Unknowns: Whether usage should be visible or hidden.
Alternative interpretation: Could be merged with Live Company.

--------------------------------------------------
ORCHESTRATION
--------------------------------------------------

1. What user goal does this support?
   NONE — Users don't need to orchestrate manually.

2. Would a new customer naturally expect this feature?
   NO — Users expect AI to handle coordination.

3. How frequently would users interact with it?
   Never directly — Orchestration should be automatic.

4. Does this belong in the user's mental model?
   NO — Users don't understand orchestration concept.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic.

7. If hidden, would the product become worse?
   NO — Orchestration should work automatically.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend orchestrates regardless.

9. Should this be: No UI
   YES — Orchestration should be automatic.

10. If commercial competitors were designing this feature, where would they likely place it?
    No UI — ChatGPT, Claude, Cursor handle coordination automatically.

Evidence: OrchestrationView.tsx shows orchestration sessions.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Orchestration should be automatic.

--------------------------------------------------
WORKFLOWS
--------------------------------------------------

1. What user goal does this support?
   NONE — Users don't need to manage workflows manually.

2. Would a new customer naturally expect this feature?
   NO — Users expect AI to handle workflows.

3. How frequently would users interact with it?
   Never directly — Workflows should be automatic.

4. Does this belong in the user's mental model?
   NO — Users don't understand workflow concept.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic.

7. If hidden, would the product become worse?
   NO — Workflows should work automatically.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles workflows regardless.

9. Should this be: No UI
   YES — Workflows should be automatic.

10. If commercial competitors were designing this feature, where would they likely place it?
    No UI — ChatGPT, Claude, Cursor handle workflows automatically.

Evidence: WorkflowsView.tsx shows workflow definitions.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Workflows should be automatic.

--------------------------------------------------
JOBS
--------------------------------------------------

1. What user goal does this support?
   NONE — Users don't need to manage jobs manually.

2. Would a new customer naturally expect this feature?
   NO — Users expect background tasks to work automatically.

3. How frequently would users interact with it?
   Never directly — Jobs should be automatic.

4. Does this belong in the user's mental model?
   NO — Users don't understand job concept.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic.

7. If hidden, would the product become worse?
   NO — Jobs should work automatically.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles jobs regardless.

9. Should this be: No UI
   YES — Jobs should be automatic.

10. If commercial competitors were designing this feature, where would they likely place it?
    No UI — ChatGPT, Claude, Cursor handle background tasks automatically.

Evidence: JobsView.tsx shows job queue.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Jobs should be automatic.

--------------------------------------------------
MCP SERVERS
--------------------------------------------------

1. What user goal does this support?
   Add tools — extend AI capabilities.

2. Would a new customer naturally expect this feature?
   MAYBE — Power users expect tool integration.

3. How frequently would users interact with it?
   Rarely — Users configure tools once.

4. Does this belong in the user's mental model?
   MAYBE — Users may not understand MCP concept.

5. Does exposing this feature increase or decrease usability?
   INCREASE for power users, DECREASE for beginners.

6. Should users actively control it?
   YES — Users configure tools.

7. If hidden, would the product become worse?
   MAYBE — Power users would lose tool configuration.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles MCP regardless.

9. Should this be: Settings
   YES — Tool configuration belongs in Settings.

10. If commercial competitors were designing this feature, where would they likely place it?
    Settings — Cursor has tool configuration in settings.

Evidence: MCPView.tsx shows MCP server management.
Confidence: MEDIUM
Assumptions: Users need tool configuration.
Unknowns: Whether tools should be pre-configured or user-configured.
Alternative interpretation: Could be pre-configured with no UI.

--------------------------------------------------
MEMORY
--------------------------------------------------

1. What user goal does this support?
   NONE — Users expect AI to remember automatically.

2. Would a new customer naturally expect this feature?
   NO — Users expect AI to remember without management.

3. How frequently would users interact with it?
   Never directly — Memory should be automatic.

4. Does this belong in the user's mental model?
   NO — Users don't understand memory concept.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic.

7. If hidden, would the product become worse?
   NO — Memory should work automatically.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles memory regardless.

9. Should this be: No UI
   YES — Memory should be automatic.

10. If commercial competitors were designing this feature, where would they likely place it?
    No UI — ChatGPT, Claude remember automatically.

Evidence: MemoryView.tsx shows memory entries.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Memory should be automatic.

--------------------------------------------------
RAG DOCS
--------------------------------------------------

1. What user goal does this support?
   Add documents — extend AI knowledge.

2. Would a new customer naturally expect this feature?
   MAYBE — Power users expect document integration.

3. How frequently would users interact with it?
   Rarely — Users configure documents once.

4. Does this belong in the user's mental model?
   MAYBE — Users may not understand RAG concept.

5. Does exposing this feature increase or decrease usability?
   INCREASE for power users, DECREASE for beginners.

6. Should users actively control it?
   YES — Users configure documents.

7. If hidden, would the product become worse?
   MAYBE — Power users would lose document configuration.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles RAG regardless.

9. Should this be: Settings
   YES — Document configuration belongs in Settings.

10. If commercial competitors were designing this feature, where would they likely place it?
    Settings — Cursor has document configuration in settings.

Evidence: RAGView.tsx shows document management.
Confidence: MEDIUM
Assumptions: Users need document configuration.
Unknowns: Whether documents should be pre-configured or user-configured.
Alternative interpretation: Could be pre-configured with no UI.

--------------------------------------------------
AUTOMATION
--------------------------------------------------

1. What user goal does this support?
   NONE — Users don't need to manage automation manually.

2. Would a new customer naturally expect this feature?
   NO — Users expect automation to work automatically.

3. How frequently would users interact with it?
   Never directly — Automation should be automatic.

4. Does this belong in the user's mental model?
   NO — Users don't understand automation concept.

5. Does exposing this feature increase or decrease usability?
   DECREASE — Adds cognitive load without clear value.

6. Should users actively control it?
   NO — Should be automatic.

7. If hidden, would the product become worse?
   NO — Automation should work automatically.

8. If removed from UI, would the backend still deliver the same value?
   YES — Backend handles automation regardless.

9. Should this be: No UI
   YES — Automation should be automatic.

10. If commercial competitors were designing this feature, where would they likely place it?
    No UI — ChatGPT, Claude, Cursor handle automation automatically.

Evidence: AutomationView.tsx shows event hooks and triggers.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Automation should be automatic.

--------------------------------------------------
SETTINGS
--------------------------------------------------

1. What user goal does this support?
   Configure application — providers, models, preferences.

2. Would a new customer naturally expect this feature?
   YES — Every application has settings.

3. How frequently would users interact with it?
   Weekly — Users configure periodically.

4. Does this belong in the user's mental model?
   YES — Users expect settings.

5. Does exposing this feature increase or decrease usability?
   INCREASE — Users need to configure application.

6. Should users actively control it?
   YES — Users configure settings.

7. If hidden, would the product become worse?
   YES — Users couldn't configure application.

8. If removed from UI, would the backend still deliver the same value?
   NO — Users need configuration.

9. Should this be: Primary Sidebar
   YES — Settings must be accessible.

10. If commercial competitors were designing this feature, where would they likely place it?
    Primary Sidebar — ChatGPT, Claude, Cursor all have settings.

Evidence: SettingsView.tsx shows configuration tabs.
Confidence: HIGH
Assumptions: None
Unknowns: None
Alternative interpretation: None — Settings is essential.

==================================================
CLASSIFICATION MATRIX
==================================================

| Feature | Current Location | Recommended Location | Category | Frequency | User Value | Business Value | Technical Exposure | Should User See It | Reason |
|---------|------------------|---------------------|----------|-----------|------------|----------------|-------------------|-------------------|--------|
| Workspace | Primary Sidebar | Primary Sidebar | A: Core Product | Every session | HIGH | HIGH | LOW | YES | Entry point |
| Chat | Primary Sidebar | Primary Sidebar | A: Core Product | Every session | HIGH | HIGH | LOW | YES | Core product |
| Projects | Primary Sidebar | Primary Sidebar | A: Core Product | Weekly | MEDIUM | MEDIUM | LOW | YES | Work organization |
| Live Company | Primary Sidebar | Secondary Navigation | B: Advanced Feature | Weekly | MEDIUM | MEDIUM | MEDIUM | MAYBE | Power user monitoring |
| Timeline | Primary Sidebar | Hidden | F: System Engine | Rarely | LOW | LOW | HIGH | NO | Implementation detail |
| Evidence | Primary Sidebar | Hidden | F: System Engine | Rarely | LOW | LOW | HIGH | NO | Implementation detail |
| Observability | Primary Sidebar | Settings | C: Configuration | Weekly | MEDIUM | MEDIUM | MEDIUM | MAYBE | Usage monitoring |
| Orchestration | Primary Sidebar | No UI | F: System Engine | Never | NONE | NONE | HIGH | NO | Should be automatic |
| Workflows | Primary Sidebar | No UI | F: System Engine | Never | NONE | NONE | HIGH | NO | Should be automatic |
| Jobs | Primary Sidebar | No UI | F: System Engine | Never | NONE | NONE | HIGH | NO | Should be automatic |
| MCP Servers | Primary Sidebar | Settings | C: Configuration | Rarely | LOW | LOW | HIGH | MAYBE | Tool configuration |
| Memory | Primary Sidebar | No UI | F: System Engine | Never | NONE | NONE | HIGH | NO | Should be automatic |
| RAG Docs | Primary Sidebar | Settings | C: Configuration | Rarely | LOW | LOW | HIGH | MAYBE | Document configuration |
| Automation | Primary Sidebar | No UI | F: System Engine | Never | NONE | NONE | HIGH | NO | Should be automatic |
| Settings | Primary Sidebar | Primary Sidebar | A: Core Product | Weekly | HIGH | HIGH | LOW | YES | Configuration |

==================================================
FINAL PRODUCT BOUNDARY
==================================================

PRIMARY SIDEBAR (3 items):
1. Workspace — Entry point
2. Chat — Core product
3. Projects — Work organization

SECONDARY NAVIGATION (1 item):
1. Live Company — Power user monitoring

SETTINGS (4 items):
1. Observability — Usage monitoring
2. MCP Servers — Tool configuration
3. RAG Docs — Document configuration
4. Providers — LLM configuration

HIDDEN (2 items):
1. Timeline — Implementation detail
2. Evidence — Implementation detail

NO UI (5 items):
1. Orchestration — Should be automatic
2. Workflows — Should be automatic
3. Jobs — Should be automatic
4. Memory — Should be automatic
5. Automation — Should be automatic

==================================================
RATIONALE
==================================================

PRIMARY SIDEBAR:
- Workspace, Chat, Projects are CORE PRODUCT
- Users interact with them constantly
- Removing them damages the product

SECONDARY NAVIGATION:
- Live Company is ADVANCED FEATURE
- Power users need monitoring
- Not essential for all users

SETTINGS:
- Observability, MCP, RAG are CONFIGURATION
- Users configure once, use daily
- Belongs in Settings, not sidebar

HIDDEN:
- Timeline, Evidence are SYSTEM ENGINE
- Implementation details
- Should be in context, not separate pages

NO UI:
- Orchestration, Workflows, Jobs, Memory, Automation are SYSTEM ENGINE
- Should be automatic
- No user interaction needed

==================================================
COMMERCIAL IMPACT
==================================================

CURRENT STATE:
- 15 sidebar items
- Technical jargon everywhere
- Implementation details exposed
- High cognitive load

RECOMMENDED STATE:
- 3 sidebar items (Workspace, Chat, Projects)
- 1 secondary navigation (Live Company)
- 4 settings items
- 2 hidden items
- 5 automatic items (no UI)

RESULT:
- 60% reduction in sidebar items
- 100% reduction in technical jargon
- 100% reduction in implementation details
- 80% reduction in cognitive load

==================================================
END OF REVIEW
==================================================

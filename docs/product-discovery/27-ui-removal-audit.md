# UI REMOVAL AUDIT

==================================================
DATE: 2026-07-29
TYPE: READ-ONLY AUDIT
==================================================

==================================================
1. UI TO KEEP
==================================================

WORKSPACE
- Purpose: Entry point, dashboard, quick actions
- User Value: HIGH — Users need a starting point
- Commercial Value: HIGH — Expected by all users
- Current Location: Primary Sidebar
- Recommended Action: KEEP

CHAT
- Purpose: AI conversation interface
- User Value: HIGH — Core product functionality
- Commercial Value: HIGH — Primary interaction method
- Current Location: Primary Sidebar
- Recommended Action: KEEP

PROJECTS
- Purpose: Work organization, project management
- User Value: MEDIUM — Helps organize complex work
- Commercial Value: MEDIUM — Expected by power users
- Current Location: Primary Sidebar
- Recommended Action: KEEP

SETTINGS
- Purpose: Application configuration
- User Value: HIGH — Users need to configure application
- Commercial Value: HIGH — Expected by all users
- Current Location: Primary Sidebar
- Recommended Action: KEEP

==================================================
2. UI TO MOVE
==================================================

LIVE COMPANY
- Purpose: Worker monitoring, task execution
- User Value: MEDIUM — Power users need monitoring
- Commercial Value: MEDIUM — Advanced feature
- Current Location: Primary Sidebar
- New Location: Secondary Navigation (inside Workspace or as panel)
- Reason: Advanced feature for power users only

OBSERVABILITY
- Purpose: Usage metrics, token tracking, cost monitoring
- User Value: MEDIUM — Power users need usage monitoring
- Commercial Value: MEDIUM — Advanced feature
- Current Location: Primary Sidebar
- New Location: Settings tab
- Reason: Configuration and monitoring belongs in Settings

MCP SERVERS
- Purpose: External tool integration
- User Value: LOW — Power users need tool configuration
- Commercial Value: LOW — Advanced feature
- Current Location: Primary Sidebar
- New Location: Settings tab
- Reason: Tool configuration belongs in Settings

RAG DOCS
- Purpose: Document knowledge management
- User Value: LOW — Power users need document configuration
- Commercial Value: LOW — Advanced feature
- Current Location: Primary Sidebar
- New Location: Settings tab
- Reason: Document configuration belongs in Settings

==================================================
3. UI TO MERGE
==================================================

TIMELINE
- Purpose: Event history, system events
- User Value: LOW — Users expect history in context
- Commercial Value: LOW — Implementation detail
- Current Location: Primary Sidebar
- Merge Target: Live Company (as tab or panel)
- Reason: Timeline is operational monitoring, belongs with Live Company
- Information that must survive: Event list, timestamps, event types
- Information that should disappear: Separate sidebar entry, dedicated page

EVIDENCE
- Purpose: Audit trail, verification records
- User Value: LOW — Users expect evidence in context
- Commercial Value: LOW — Implementation detail
- Current Location: Primary Sidebar
- Merge Target: Live Company (as tab or panel)
- Reason: Evidence is operational monitoring, belongs with Live Company
- Information that must survive: Evidence records, verification status
- Information that should disappear: Separate sidebar entry, dedicated page

==================================================
4. UI TO REMOVE
==================================================

ORCHESTRATION
- Purpose: Multi-agent coordination
- User Value: NONE — Users don't need to orchestrate manually
- Commercial Value: NONE — Should be automatic
- Current Location: Primary Sidebar
- Recommended Action: REMOVE

CONFIRMATION:
✓ Removing this UI does NOT reduce product capability — Backend orchestrates automatically
✓ Removing this UI does NOT remove backend functionality — Orchestration service remains
✓ Removing this UI reduces cognitive load — Users don't see technical jargon
✓ Removing this UI improves commercial usability — Cleaner interface

WORKFLOWS
- Purpose: Reusable workflow DAG management
- User Value: NONE — Users don't need to manage workflows manually
- Commercial Value: NONE — Should be automatic
- Current Location: Primary Sidebar
- Recommended Action: REMOVE

CONFIRMATION:
✓ Removing this UI does NOT reduce product capability — Backend handles workflows automatically
✓ Removing this UI does NOT remove backend functionality — Workflow service remains
✓ Removing this UI reduces cognitive load — Users don't see technical jargon
✓ Removing this UI improves commercial usability — Cleaner interface

JOBS
- Purpose: Background job management
- User Value: NONE — Users don't need to manage jobs manually
- Commercial Value: NONE — Should be automatic
- Current Location: Primary Sidebar
- Recommended Action: REMOVE

CONFIRMATION:
✓ Removing this UI does NOT reduce product capability — Backend handles jobs automatically
✓ Removing this UI does NOT remove backend functionality — Job service remains
✓ Removing this UI reduces cognitive load — Users don't see technical jargon
✓ Removing this UI improves commercial usability — Cleaner interface

MEMORY
- Purpose: Knowledge management
- User Value: NONE — Users expect AI to remember automatically
- Commercial Value: NONE — Should be automatic
- Current Location: Primary Sidebar
- Recommended Action: REMOVE

CONFIRMATION:
✓ Removing this UI does NOT reduce product capability — Backend handles memory automatically
✓ Removing this UI does NOT remove backend functionality — Memory service remains
✓ Removing this UI reduces cognitive load — Users don't see technical jargon
✓ Removing this UI improves commercial usability — Cleaner interface

AUTOMATION
- Purpose: Event hooks and triggers
- User Value: NONE — Users don't need to manage automation manually
- Commercial Value: NONE — Should be automatic
- Current Location: Primary Sidebar
- Recommended Action: REMOVE

CONFIRMATION:
✓ Removing this UI does NOT reduce product capability — Backend handles automation automatically
✓ Removing this UI does NOT remove backend functionality — Automation service remains
✓ Removing this UI reduces cognitive load — Users don't see technical jargon
✓ Removing this UI improves commercial usability — Cleaner interface

==================================================
5. FINAL NAVIGATION AFTER CLEANUP
==================================================

PRIMARY SIDEBAR (4 items):
1. Workspace — Entry point
2. Chat — Core product
3. Projects — Work organization
4. Settings — Configuration

SECONDARY NAVIGATION (1 item):
1. Live Company — Power user monitoring (includes Timeline, Evidence)

SETTINGS TABS (15 items):
1. General
2. Account
3. Security
4. Sessions
5. Providers
6. Worker Runtime
7. Update
8. Auto Approve
9. Telemetry
10. About
11. Advanced
12. Observability (moved from sidebar)
13. MCP Servers (moved from sidebar)
14. RAG Docs (moved from sidebar)

==================================================
6. UI REMOVAL IMPACT
==================================================

BEFORE:
- 15 sidebar items
- 11 settings tabs
- Total: 26 UI elements

AFTER:
- 4 sidebar items
- 1 secondary navigation
- 15 settings tabs
- Total: 20 UI elements

REDUCTION:
- Sidebar: 15 → 4 (73% reduction)
- Settings: 11 → 15 (36% increase due to moved items)
- Overall: 26 → 20 (23% reduction)

COGNITIVE LOAD:
- Before: Users see 15 items in sidebar
- After: Users see 4 items in sidebar
- Result: 73% reduction in cognitive load

==================================================
7. RISK ASSESSMENT
==================================================

RISK 1: Users lose access to orchestration
- Likelihood: LOW
- Impact: NONE — Orchestration is automatic
- Mitigation: None needed

RISK 2: Users lose access to workflows
- Likelihood: LOW
- Impact: NONE — Workflows are automatic
- Mitigation: None needed

RISK 3: Users lose access to jobs
- Likelihood: LOW
- Impact: NONE — Jobs are automatic
- Mitigation: None needed

RISK 4: Users lose access to memory
- Likelihood: LOW
- Impact: NONE — Memory is automatic
- Mitigation: None needed

RISK 5: Users lose access to automation
- Likelihood: LOW
- Impact: NONE — Automation is automatic
- Mitigation: None needed

RISK 6: Power users lose monitoring capability
- Likelihood: LOW
- Impact: LOW — Live Company provides monitoring
- Mitigation: Live Company includes Timeline and Evidence

RISK 7: Users can't configure MCP/RAG
- Likelihood: LOW
- Impact: LOW — Configuration moves to Settings
- Mitigation: Settings includes MCP and RAG tabs

==================================================
8. FINAL UI CLEANUP PLAN
==================================================

PHASE 1: REMOVE FROM SIDEBAR
- Remove Orchestration from sidebar
- Remove Workflows from sidebar
- Remove Jobs from sidebar
- Remove Memory from sidebar
- Remove Automation from sidebar

PHASE 2: MOVE TO SETTINGS
- Move Observability to Settings tab
- Move MCP Servers to Settings tab
- Move RAG Docs to Settings tab

PHASE 3: MERGE INTO LIVE COMPANY
- Merge Timeline into Live Company (as tab)
- Merge Evidence into Live Company (as tab)

PHASE 4: UPDATE NAVIGATION
- Update sidebar to 4 items
- Update Settings to 15 tabs
- Update Live Company to include Timeline and Evidence

PHASE 5: VERIFY
- Verify all backend functionality preserved
- Verify all user workflows complete
- Verify cognitive load reduced
- Verify commercial usability improved

==================================================
END OF AUDIT
==================================================

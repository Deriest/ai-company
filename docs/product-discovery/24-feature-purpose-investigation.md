# FEATURE PURPOSE INVESTIGATION

==================================================
DATE: 2026-07-29
TYPE: READ-ONLY INVESTIGATION
==================================================

==================================================
MASTER TABLE
==================================================

| Feature | Purpose | Current UI | Backend Components | Automatically Used | Manual Usage | Primary User | Business Value | Duplicate | Keep UI | Move | Merge | Hide | Remove UI | Keep Backend | Reason |
|---------|---------|------------|-------------------|-------------------|--------------|--------------|----------------|-----------|---------|------|-------|------|-----------|--------------|--------|
| Orchestration | Multi-agent task coordination | Sidebar page | orchestrator_service.py, OrchestrationSession, OrchestrationTask | NO | YES | Power User | MEDIUM | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for complex multi-agent tasks |
| Workflows | Reusable workflow DAG management | Sidebar page | workflows_api, WorkflowDefinition | NO | YES | Power User | MEDIUM | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for workflow automation |
| Jobs | Background job scheduling | Sidebar page | job_scheduler.py, Job | YES (background dispatch) | YES | Power User | MEDIUM | NO | YES | Settings | NO | NO | NO | YES | Required for background task execution |
| MCP Servers | External tool integration | Sidebar page | mcp_service.py, MCPRegistry, MCPTool | NO | YES | Power User | LOW | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for external tool integration |
| Memory | Multi-scope knowledge management | Sidebar page | memory_service.py, MemoryEntry | NO | YES | Power User | LOW | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for knowledge persistence |
| RAG Docs | Document management for RAG | Sidebar page | rag_service.py, Document, DocumentChunk | NO | YES | Power User | LOW | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for document retrieval |
| Automation | Event hooks and triggers | Sidebar page | automation_service.py, EventHook, Trigger | NO | YES | Power User | LOW | NO | YES | Settings | NO | NO | NO | YES | Advanced feature for event automation |

==================================================
DETAILED INVESTIGATION
==================================================

--------------------------------------------------
ORCHESTRATION
--------------------------------------------------

1. Why does this feature exist?
   Multi-agent orchestration allows complex tasks to be broken down and executed by multiple workers in sequence or parallel.

2. What business problem does it solve?
   Complex engineering tasks require multiple specialists (architect, backend, frontend, QA). Orchestration coordinates their work.

3. Who uses it?
   Power User — Users who need to coordinate complex multi-agent tasks.

4. What backend components use it?
   - orchestrator_service.py — Core orchestration engine
   - OrchestrationSession — Session management
   - OrchestrationTask — Task routing
   - OrchestrationApproval — Approval chains
   - worker_runtime_service.py — Worker lifecycle

5. Is it manually invoked or automatically invoked?
   Manually invoked — Users create orchestration sessions.

6. Can the product function normally if users never open this page?
   YES — ConversationEngine handles simple tasks automatically. Orchestration is for complex multi-agent coordination only.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for complex tasks.

8. Does it expose implementation details?
   YES — Exposes orchestration sessions, tasks, approvals.

9. Does it duplicate another feature?
   NO — Orchestration is unique coordination layer.

10. Could the same capability exist without a dedicated page?
    YES — Could be automatic when ConversationEngine detects complex tasks.

11. Is the current UI actually useful?
    YES — Allows monitoring and managing multi-agent sessions.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual oversight.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    NO — Orchestration is manually invoked.

15. Does the user need to understand this concept?
    NO — Users just want tasks done. Orchestration is implementation detail.

--------------------------------------------------
WORKFLOWS
--------------------------------------------------

1. Why does this feature exist?
   Workflows allow reusable DAG definitions for common engineering patterns.

2. What business problem does it solve?
   Repeating engineering patterns (e.g., feature development, bug fixes) can be templated as workflows.

3. Who uses it?
   Power User — Users who create reusable engineering patterns.

4. What backend components use it?
   - WorkflowDefinition — DAG storage
   - WorkflowInstantiation — Instance creation
   - orchestrator_service.py — Workflow execution

5. Is it manually invoked or automatically invoked?
   Manually invoked — Users create and instantiate workflows.

6. Can the product function normally if users never open this page?
   YES — ConversationEngine handles tasks without workflows.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for workflow automation.

8. Does it expose implementation details?
    YES — Exposes DAG definitions, node configurations.

9. Does it duplicate another feature?
    NO — Workflows are unique templating layer.

10. Could the same capability exist without a dedicated page?
    YES — Could be automatic when ConversationEngine detects repeatable patterns.

11. Is the current UI actually useful?
    YES — Allows creating and managing reusable workflows.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual workflow creation.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    NO — Workflows are manually invoked.

15. Does the user need to understand this concept?
    NO — Users just want tasks done. Workflows are implementation detail.

--------------------------------------------------
JOBS
--------------------------------------------------

1. Why does this feature exist?
   Jobs manage background task execution, scheduling, and monitoring.

2. What business problem does it solve?
   Long-running tasks (orchestration, chat, tools) need background execution to avoid blocking the UI.

3. Who uses it?
   Power User — Users who need to monitor background tasks.

4. What backend components use it?
   - job_scheduler.py — Job scheduling
   - Job — Job storage
   - _dispatch_created_task() — Background dispatch

5. Is it manually invoked or automatically invoked?
   BOTH — Jobs are created automatically (background dispatch) and manually (user-created jobs).

6. Can the product function normally if users never open this page?
   YES — Jobs execute automatically in background.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for job monitoring.

8. Does it expose implementation details?
    YES — Exposes job queue, scheduling, execution status.

9. Does it duplicate another feature?
    NO — Jobs are unique background execution layer.

10. Could the same capability exist without a dedicated page?
    YES — Jobs already run automatically without user intervention.

11. Is the current UI actually useful?
    YES — Allows monitoring and managing background jobs.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual oversight.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    YES — _dispatch_created_task() creates jobs automatically.

15. Does the user need to understand this concept?
    NO — Users just want tasks done. Jobs are implementation detail.

--------------------------------------------------
MCP SERVERS
--------------------------------------------------

1. Why does this feature exist?
   MCP (Model Context Protocol) allows integration with external tool servers.

2. What business problem does it solve?
   Extends AI capabilities with external tools (file system, database, APIs).

3. Who uses it?
   Power User — Users who need external tool integration.

4. What backend components use it?
   - mcp_service.py — MCP server management
   - MCPRegistry — Server storage
   - MCPTool — Tool storage
   - MCPToolExecution — Execution tracking

5. Is it manually invoked or automatically invoked?
   Manually invoked — Users register MCP servers and execute tools.

6. Can the product function normally if users never open this page?
   YES — Core functionality doesn't require MCP.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for tool integration.

8. Does it expose implementation details?
    YES — Exposes server registration, tool discovery, execution.

9. Does it duplicate another feature?
    NO — MCP is unique external integration layer.

10. Could the same capability exist without a dedicated page?
    YES — Could be configured in Settings.

11. Is the current UI actually useful?
    YES — Allows managing external tool integrations.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual configuration.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    NO — MCP is manually configured.

15. Does the user need to understand this concept?
    NO — Users just want AI to have tools. MCP is implementation detail.

--------------------------------------------------
MEMORY
--------------------------------------------------

1. Why does this feature exist?
   Memory allows persistent knowledge storage across sessions and conversations.

2. What business problem does it solve?
   AI needs to remember facts, preferences, and context across conversations.

3. Who uses it?
   Power User — Users who need to manage AI knowledge.

4. What backend components use it?
   - memory_service.py — Memory management
   - MemoryEntry — Memory storage

5. Is it manually invoked or automatically invoked?
   BOTH — Memory can be stored manually or automatically by ConversationEngine.

6. Can the product function normally if users never open this page?
   YES — Memory works automatically in background.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for knowledge management.

8. Does it expose implementation details?
    YES — Exposes memory scopes, categories, importance.

9. Does it duplicate another feature?
    NO — Memory is unique knowledge persistence layer.

10. Could the same capability exist without a dedicated page?
    YES — Memory already works automatically.

11. Is the current UI actually useful?
    YES — Allows managing AI knowledge base.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual management.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    YES — ConversationEngine can store/retrieve memory automatically.

15. Does the user need to understand this concept?
    NO — Users just want AI to remember. Memory is implementation detail.

--------------------------------------------------
RAG DOCS
--------------------------------------------------

1. Why does this feature exist?
   RAG (Retrieval-Augmented Generation) allows document-based knowledge retrieval.

2. What business problem does it solve?
   AI needs to access project documentation, code, and knowledge bases.

3. Who uses it?
   Power User — Users who need to manage document knowledge.

4. What backend components use it?
   - rag_service.py — RAG document management
   - Document — Document storage
   - DocumentChunk — Chunk storage
   - embedding_provider.py — Embedding generation

5. Is it manually invoked or automatically invoked?
   Manually invoked — Users upload documents and search.

6. Can the product function normally if users never open this page?
   YES — Core functionality doesn't require RAG.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for document knowledge.

8. Does it expose implementation details?
    YES — Exposes document chunks, embeddings, retrieval.

9. Does it duplicate another feature?
    NO — RAG is unique document knowledge layer.

10. Could the same capability exist without a dedicated page?
    YES — Could be configured in Settings.

11. Is the current UI actually useful?
    YES — Allows managing document knowledge base.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual document management.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    NO — RAG is manually configured.

15. Does the user need to understand this concept?
    NO — Users just want AI to know their docs. RAG is implementation detail.

--------------------------------------------------
AUTOMATION
--------------------------------------------------

1. Why does this feature exist?
   Automation allows event-driven hooks, triggers, and notifications.

2. What business problem does it solve?
   Users need automated responses to system events (task completion, errors, etc.).

3. Who uses it?
   Power User — Users who need event automation.

4. What backend components use it?
   - automation_service.py — Automation engine
   - EventHook — Hook storage
   - Trigger — Trigger storage
   - Notification — Notification storage

5. Is it manually invoked or automatically invoked?
   Manually invoked — Users create hooks and triggers.

6. Can the product function normally if users never open this page?
   YES — Core functionality doesn't require automation.

7. Is it: Core Product / Power User / Operator / Developer Tool / Internal Infrastructure?
   Power User — Advanced feature for event automation.

8. Does it expose implementation details?
    YES — Exposes event types, hook configurations, triggers.

9. Does it duplicate another feature?
    NO — Automation is unique event-driven layer.

10. Could the same capability exist without a dedicated page?
    YES — Could be configured in Settings.

11. Is the current UI actually useful?
    YES — Allows managing event automation.

12. Would hiding this feature change product capability?
    NO — Backend would still work, just no manual automation configuration.

13. Would removing only the UI still preserve backend functionality?
    YES — Backend operates independently.

14. Does ConversationEngine or Hermes already use this automatically?
    NO — Automation is manually configured.

15. Does the user need to understand this concept?
    NO — Users just want things automated. Automation is implementation detail.

==================================================
FINAL CONCLUSION
==================================================

KEEP AS PRODUCT FEATURE:
- None — All 7 features are advanced/power user features

MOVE TO SETTINGS:
- Orchestration — Advanced multi-agent coordination
- Workflows — Advanced workflow automation
- Jobs — Background job monitoring
- MCP Servers — External tool integration
- Memory — Knowledge management
- RAG Docs — Document knowledge
- Automation — Event automation

MERGE WITH ANOTHER FEATURE:
- None — All features are distinct

HIDE FROM NORMAL USERS:
- None — All features have value for power users

DEVELOPER ONLY:
- None — All features have user-facing value

OPERATOR ONLY:
- None — All features have user-facing value

INTERNAL SYSTEM ONLY:
- None — All features have user-facing value

SAFE TO REMOVE UI:
- None — All features have user-facing value

KEEP BACKEND ONLY:
- None — All features have user-facing value

==================================================
RATIONALE
==================================================

All 7 features are ADVANCED FEATURES that:

1. Have legitimate user-facing value
2. Are not implementation details
3. Are not duplicated elsewhere
4. Have unique backend components
5. Provide power user capabilities

However, they are NOT CORE FEATURES because:

1. ConversationEngine handles simple tasks automatically
2. Core functionality doesn't require these features
3. Users can use the product without ever opening these pages
4. These features are for advanced users only

RECOMMENDATION:
- Move all 7 features to Settings
- Keep all 7 backends operational
- Reduce sidebar from 15 to 5 items
- Preserve all functionality

==================================================
END OF INVESTIGATION
==================================================

# 08 — CONFIGURATION

==================================================
DATE: 2026-07-29
SOURCE: Repository reverse engineering
==================================================

==================================================
8.1 OVERVIEW
==================================================

This document describes every configurable system in the application.

Repository evidence:
- aic-platform/backend/config.py
- aic-ide/src/renderer/src/components/SettingsView.tsx
- aic-platform/.env

==================================================
8.2 PROVIDERS
==================================================

PURPOSE: Configure AI providers (OpenAI, Anthropic, etc.)
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Providers

DATA:
- name: Provider name
- base_url: API endpoint
- api_key: API key (encrypted)
- enabled: Provider status
- models: Available models

Repository evidence:
- aic-platform/backend/models/schema.py — Provider model
- aic-platform/backend/services/provider_client.py
- aic-ide/src/renderer/src/components/SettingsView.tsx — ProviderSetup

==================================================
8.3 MODELS
==================================================

PURPOSE: Configure AI models
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Providers → Fetch Models

DATA:
- model_id: Model identifier
- provider_id: Parent provider
- enabled: Model status

Repository evidence:
- aic-platform/backend/models/schema.py — ProviderModel

==================================================
8.4 WORKER RUNTIME
==================================================

PURPOSE: Configure worker model assignments
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Worker Runtime

DATA:
- role: Worker role
- model_id: Assigned model
- provider_id: Assigned provider

Repository evidence:
- aic-platform/backend/models/schema.py — WorkerRuntime
- aic-ide/src/renderer/src/components/SettingsView.tsx — WorkerRuntimeSetup

==================================================
8.5 MEMORY
==================================================

PURPOSE: Configure memory system
CONFIGURATION TYPE: Automatic (system-managed)
LOCATION: Settings → Memory (sidebar)

CONFIGURABLE:
- Memory entries (CRUD)
- Compression settings
- Scope management

Repository evidence:
- aic-platform/backend/services/memory_service.py
- aic-ide/src/renderer/src/components/MemoryView.tsx

==================================================
8.6 KNOWLEDGE (RAG)
==================================================

PURPOSE: Configure knowledge base
CONFIGURATION TYPE: User configurable
LOCATION: Settings → RAG Docs (sidebar)

CONFIGURABLE:
- Document upload
- Document management
- Retrieval settings

Repository evidence:
- aic-platform/backend/services/rag_service.py
- aic-ide/src/renderer/src/components/RAGView.tsx

==================================================
8.7 MCP (Model Context Protocol)
==================================================

PURPOSE: Configure external tool servers
CONFIGURATION TYPE: User configurable
LOCATION: Settings → MCP Servers (sidebar)

CONFIGURABLE:
- Server registration
- Tool discovery
- Tool execution permissions

Repository evidence:
- aic-platform/backend/services/mcp_service.py
- aic-ide/src/renderer/src/components/MCPView.tsx

==================================================
8.8 HOOKS (AUTOMATION)
==================================================

PURPOSE: Configure event hooks
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Automation (sidebar)

CONFIGURABLE:
- Hook creation
- Event types
- Hook actions

Repository evidence:
- aic-platform/backend/services/automation_service.py
- aic-ide/src/renderer/src/components/AutomationView.tsx

==================================================
8.9 TRIGGERS (AUTOMATION)
==================================================

PURPOSE: Configure automated triggers
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Automation (sidebar)

CONFIGURABLE:
- Trigger conditions
- Trigger actions
- Trigger schedules

Repository evidence:
- aic-platform/backend/services/automation_service.py

==================================================
8.10 WORKFLOWS
==================================================

PURPOSE: Configure workflow definitions
CONFIGURATION TYPE: User configurable (advanced)
LOCATION: Settings → Workflows (sidebar)

CONFIGURABLE:
- Workflow DAGs
- Task definitions
- Execution modes

Repository evidence:
- aic-platform/backend/services/orchestrator_service.py
- aic-ide/src/renderer/src/components/WorkflowsView.tsx

==================================================
8.11 APPROVAL POLICIES
==================================================

PURPOSE: Configure approval requirements
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Auto Approve

CONFIGURABLE:
- Auto-approve thresholds
- Approval requirements
- Bypass rules

Repository evidence:
- aic-platform/backend/approval_config.json
- aic-ide/src/renderer/src/components/SettingsView.tsx

==================================================
8.12 ENVIRONMENT VARIABLES
==================================================

PURPOSE: System-level configuration
CONFIGURATION TYPE: Developer configurable
LOCATION: aic-platform/.env

VARIABLES:
- AIC_DATA_DIR: Data directory path
- AIC_LLM_BASE_URL: LLM provider URL
- AIC_LLM_API_KEY: LLM API key
- AIC_LLM_MODEL: Default model

Repository evidence:
- aic-platform/.env
- aic-platform/backend/config.py

==================================================
8.13 FEATURE FLAGS
==================================================

PURPOSE: Enable/disable features
CONFIGURATION TYPE: Hardcoded
LOCATION: Not found in repository

NOTE: No feature flag system found in repository evidence.

Repository evidence: NOT SUPPORTED

==================================================
8.14 UI CONFIGURATION
==================================================

PURPOSE: Frontend appearance
CONFIGURATION TYPE: User configurable
LOCATION: Settings → General

CONFIGURABLE:
- Theme (dark/light)
- Font size
- Layout preferences

Repository evidence:
- aic-ide/src/renderer/src/components/SettingsView.tsx — General tab

==================================================
8.15 NOTIFICATION CONFIGURATION
==================================================

PURPOSE: Notification preferences
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Notifications

CONFIGURABLE:
- Notification types
- Sound settings
- Desktop notifications

Repository evidence:
- aic-ide/src/renderer/src/components/SettingsView.tsx

==================================================
8.16 TELEMETRY CONFIGURATION
==================================================

PURPOSE: Usage data collection
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Telemetry

CONFIGURABLE:
- Telemetry enabled/disabled
- Data collection scope

Repository evidence:
- aic-ide/src/renderer/src/components/SettingsView.tsx — Telemetry tab

==================================================
8.17 UPDATE CONFIGURATION
==================================================

PURPOSE: Application updates
CONFIGURATION TYPE: User configurable
LOCATION: Settings → Update

CONFIGURABLE:
- Auto-update enabled/disabled
- Update channel

Repository evidence:
- aic-ide/src/renderer/src/components/SettingsView.tsx — Update tab

==================================================
8.18 CONFIGURATION SUMMARY
==================================================

| System | Type | Location | User Configurable |
|--------|------|----------|-------------------|
| Providers | User | Settings → Providers | Yes |
| Models | User | Settings → Providers | Yes |
| Worker Runtime | User | Settings → Worker Runtime | Yes |
| Memory | Automatic | Sidebar → Memory | Yes (CRUD) |
| Knowledge | User | Sidebar → RAG Docs | Yes |
| MCP | User | Sidebar → MCP Servers | Yes |
| Hooks | User | Sidebar → Automation | Yes |
| Triggers | User | Sidebar → Automation | Yes |
| Workflows | Advanced | Sidebar → Workflows | Yes |
| Approval | User | Settings → Auto Approve | Yes |
| Environment | Developer | .env file | No (developer) |
| Feature Flags | Hardcoded | Not found | No |
| UI | User | Settings → General | Yes |
| Notifications | User | Settings → Notifications | Yes |
| Telemetry | User | Settings → Telemetry | Yes |
| Update | User | Settings → Update | Yes |

==================================================
END OF DOCUMENT
==================================================

# AIC IDE — Web vs Desktop Feature Parity

Last updated: 2026-07-24 (Cycle 11)

| Web SPA Capability | Desktop Equivalent | Evidence | Status |
|---------------------|---------------------|----------|--------|
| Chat | Chat view (SSE streaming + conversation history + switcher) | Code review | REPLACED |
| Command Center | Overview component | Code review | REPLACED |
| Projects | Projects view + create + dispatch + cancel | Code review | REPLACED |
| Tasks | TaskDetail (overview, files, leases, dispatch, cancel, ZIP export) | Code review | REPLACED |
| Workers | LiveCompany + WorkerInspector | Code review | REPLACED |
| Approvals | Approvals component | Code review | REPLACED |
| Usage | N/A | — | NOT APPLICABLE |
| Providers | Settings (baseUrl + system status + approval config) | Code review | REPLACED |
| Settings | Settings view (login + system status + approval config) | Code review | REPLACED |
| Files | File explorer (recursive tree + search + context menu + tabs) | Code review | REPLACED |
| Delivery | Delivery component (ZIP export) | Code review | REPLACED |
| Logs/Audit | Activity timeline | Code review | REPLACED |
| Verification | Verification center | Code review | REPLACED (new) |
| Problems | Problems view | Code review | REPLACED (new) |
| System Console | Settings (system status + topology) | Code review | REPLACED |

## Decision: Desktop now supersedes all necessary web capabilities.

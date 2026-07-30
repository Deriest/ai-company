# AIC-ADE REST API Documentation
# Last Updated: 2026-07-27

## Base URL
`http://127.0.0.1:{port}` (port read from `runtime.json`)

## Health
- `GET /health` — Health check

## Providers
- `GET /providers` — List all providers with models
- `POST /providers` — Create provider
- `PATCH /providers/{id}` — Update provider
- `DELETE /providers/{id}` — Delete provider
- `POST /providers/{id}/test` — Test provider connection
- `POST /providers/{id}/fetch-models` — Fetch models from provider
- `POST /providers/test-ephemeral` — Test without saving

## Worker Runtime
- `GET /runtime/workers` — List all workers with metrics
- `PATCH /runtime/workers/{role}` — Update worker config

## Conversations
- `GET /conversations` — List conversations (filter: folder_id, is_archived, is_favorite, tag)
- `POST /conversations` — Create conversation
- `GET /conversations/{id}` — Get conversation detail
- `PATCH /conversations/{id}` — Update conversation
- `DELETE /conversations/{id}` — Delete conversation
- `POST /conversations/{id}/duplicate` — Duplicate conversation
- `GET /conversations/{id}/export` — Export (format=json|markdown)
- `POST /conversations/import` — Import conversation
- `GET /conversations/{id}/messages` — List messages
- `POST /conversations/{id}/messages` — Create message
- `GET /conversations/search?q=...` — FTS5 search

## Messages
- `PATCH /messages/{id}` — Update message
- `DELETE /messages/{id}` — Delete message

## Folders & Tags
- `GET /folders` — List folders
- `POST /folders` — Create folder
- `DELETE /folders/{id}` — Delete folder
- `GET /tags` — List all tags

## Chat
- `POST /chat` — Chat completion (non-streaming)
- `POST /chat/stream` — Chat completion (SSE streaming)
- `POST /chat/cancel` — Cancel streaming
- `POST /chat/regenerate` — Regenerate last response

## Artifacts
- `GET /artifacts/{conversation_id}` — List artifacts

## Workers
- `GET /workers` — List workers
- `PATCH /workers/{id}` — Update worker

## Tools
- `POST /tools/execute` — Execute native tool

## Orchestration
- `GET /orchestration/sessions` — List sessions
- `POST /orchestration/sessions` — Create session
- `GET /orchestration/sessions/{id}` — Session detail with tasks + approvals
- `POST /orchestration/sessions/{id}/tasks` — Add task
- `POST /orchestration/sessions/{id}/execute` — Execute session
- `POST /orchestration/sessions/{id}/cancel` — Cancel session
- `POST /orchestration/sessions/{id}/resume` — Resume from checkpoint
- `GET /orchestration/sessions/{id}/checkpoints` — List checkpoints
- `POST /orchestration/tasks/{id}/approval` — Request approval
- `PATCH /orchestration/approvals/{id}` — Resolve approval

## Workflows
- `GET /workflows` — List workflow definitions
- `POST /workflows` — Create workflow
- `GET /workflows/{id}` — Workflow detail
- `POST /workflows/{id}/instantiate` — Instantiate workflow as session

## Jobs
- `GET /jobs` — List jobs (filter: status, job_type)
- `POST /jobs` — Create job
- `GET /jobs/{id}` — Job detail with logs
- `POST /jobs/{id}/cancel` — Cancel job
- `POST /jobs/{id}/pause` — Pause job
- `POST /jobs/{id}/resume` — Resume job

## MCP
- `GET /mcp/servers` — List MCP servers
- `POST /mcp/servers` — Register server
- `PATCH /mcp/servers/{id}` — Update server
- `DELETE /mcp/servers/{id}` — Delete server
- `POST /mcp/servers/{id}/discover` — Discover tools
- `GET /mcp/tools` — List tools
- `POST /mcp/tools/{id}/execute` — Execute tool
- `POST /mcp/executions/{id}/approve` — Approve/deny execution
- `GET /mcp/executions` — List executions

## Memory
- `GET /memory` — Retrieve memories (scope, key, scope_id, category, min_importance)
- `POST /memory` — Store memory
- `DELETE /memory/{id}` — Forget memory
- `POST /memory/compress` — Compress low-importance entries
- `GET /memory/stats` — Memory statistics

## RAG
- `GET /rag/documents` — List documents
- `POST /rag/documents` — Load document
- `DELETE /rag/documents/{id}` — Delete document
- `POST /rag/retrieve` — Semantic search
- `POST /rag/context` — Build context with citations

## Automation
- `GET /hooks` — List event hooks
- `POST /hooks` — Create hook
- `DELETE /hooks/{id}` — Delete hook
- `POST /hooks/fire/{event_type}` — Fire event
- `GET /triggers` — List triggers
- `POST /triggers` — Create trigger
- `DELETE /triggers/{id}` — Delete trigger
- `GET /notifications` — List notifications
- `PATCH /notifications/{id}/read` — Mark read
- `POST /notifications/read-all` — Mark all read

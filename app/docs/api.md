# AIC-ADE API Documentation

## Base URL
```
http://127.0.0.1:8000
```

## Authentication
None required. Localhost-only security model.

---

## Health & Status

### GET /health
Comprehensive health check.

**Response:**
```json
{
  "status": "ok",
  "version": "2.4.0",
  "service": "AIC-ADE Backend",
  "timestamp": "2026-07-28T15:30:00",
  "checks": {
    "database": {"status": "ok"},
    "providers": {"status": "ok", "total": 2, "connected": 1}
  }
}
```

### GET /version
Get API version information.

**Response:**
```json
{
  "version": "2.4.0",
  "api_version": "1",
  "service": "AIC-ADE Backend",
  "platform": "desktop",
  "architecture": "local-first"
}
```

### GET /metrics
Get API metrics.

---

## Providers

### GET /providers
List all configured providers.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "OpenAI",
    "endpoint": "https://api.openai.com",
    "apiKey": "***",
    "enabled": true,
    "status": "connected",
    "latencyMs": 150,
    "models": [...]
  }
]
```

### POST /providers
Create a new provider.

**Request:**
```json
{
  "name": "OpenAI",
  "endpoint": "https://api.openai.com",
  "apiKey": "sk-...",
  "latencyMs": 0,
  "version": "1.0",
  "healthNotes": [],
  "models": []
}
```

### PATCH /providers/{id}
Update a provider.

### DELETE /providers/{id}
Delete a provider.

### POST /providers/{id}/test
Test provider connection.

### POST /providers/{id}/fetch-models
Fetch available models from provider.

---

## Conversations

### GET /conversations
List all conversations.

**Query Parameters:**
- `limit` (int): Max results (default: 50)
- `offset` (int): Skip results (default: 0)

### POST /conversations
Create a new conversation.

**Request:**
```json
{
  "title": "New Conversation",
  "project_id": null,
  "folder_id": null
}
```

### GET /conversations/{id}
Get conversation by ID.

### PATCH /conversations/{id}
Update conversation.

### DELETE /conversations/{id}
Delete conversation.

### GET /conversations/{id}/messages
Get messages for conversation.

### POST /conversations/{id}/messages
Add message to conversation.

**Request:**
```json
{
  "content": "Hello, world!",
  "role": "user",
  "model_id": null,
  "provider_id": null
}
```

---

## Chat

### POST /chat
Send chat message (non-streaming).

**Request:**
```json
{
  "content": "Write a Python function",
  "model_id": "gpt-4",
  "provider_id": "uuid",
  "stream": false
}
```

### POST /chat/stream
Send chat message (streaming).

**Response:** Server-Sent Events (SSE)

---

## Discovery Engine

### POST /api/discovery/start
Start a discovery session.

**Request:**
```json
{
  "content": "Build a login page with OAuth",
  "conversation_id": "uuid"
}
```

### GET /api/discovery/{id}
Get discovery session status.

### POST /api/discovery/{id}/clarify
Respond to clarification questions.

### GET /api/discovery/{id}/brief
Get engineering brief.

---

## Planning Engine

### POST /api/planning/generate
Generate engineering plan from brief.

**Request:**
```json
{
  "brief_id": "uuid",
  "project_context": {}
}
```

### GET /api/planning/{id}
Get planning session status.

### GET /api/planning/{id}/plan
Get engineering plan.

---

## Task Graph Engine

### POST /api/taskgraph/generate
Generate task graph from plan.

**Request:**
```json
{
  "plan_id": "uuid"
}
```

### GET /api/taskgraph/{id}
Get task graph.

### GET /api/taskgraph/{id}/execution-order
Get execution order.

---

## Dispatcher

### POST /api/dispatcher/dispatch
Dispatch tasks for execution.

**Request:**
```json
{
  "graph_id": "uuid"
}
```

### GET /api/dispatcher/{id}
Get dispatch status.

---

## Verification Engine

### POST /api/verification/verify
Verify output against acceptance criteria.

**Request:**
```json
{
  "brief_id": "uuid",
  "task_results": {}
}
```

### GET /api/verification/{id}
Get verification report.

---

## Context Engine

### GET /api/context/{project_id}
Get project context.

### POST /api/context/{project_id}/knowledge
Add knowledge entry.

### POST /api/context/{project_id}/decisions
Record decision.

### GET /api/context/{project_id}/search
Search knowledge.

---

## Autonomy Engine

### POST /api/autonomy/detect
Detect anomaly.

**Request:**
```json
{
  "anomaly_type": "timeout",
  "severity": "medium",
  "description": "Task timed out",
  "affected_component": "worker-1"
}
```

### POST /api/autonomy/handle
Handle anomaly.

### GET /api/autonomy/stats
Get autonomy statistics.

---

## Delivery Engine

### POST /api/delivery/deliver
Deliver engineering output.

**Request:**
```json
{
  "brief_id": "uuid",
  "plan_id": "uuid",
  "graph_id": "uuid",
  "verification_id": "uuid",
  "task_results": {}
}
```

### GET /api/delivery/{id}
Get engineering report.

### GET /api/delivery/stats
Get delivery statistics.

---

## Memory Engine

### POST /memory
Store memory entry.

### GET /memory
Search memory.

### POST /memory/search
Search memory with query.

---

## RAG Engine

### POST /rag/documents
Load document for RAG.

### GET /rag/documents
List RAG documents.

### POST /rag/context
Get RAG context for query.

---

## MCP Engine

### POST /mcp/servers
Register MCP server.

### GET /mcp/servers
List MCP servers.

### POST /mcp/tools/execute
Execute MCP tool.

---

## Workflows

### POST /workflows
Create workflow definition.

### GET /workflows
List workflows.

### POST /workflows/{id}/execute
Execute workflow.

---

## Automation

### POST /hooks
Create automation hook.

### GET /hooks
List automation hooks.

### POST /hooks/{id}/test
Test automation hook.

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 404 | Not Found |
| 405 | Method Not Allowed |
| 413 | Payload Too Large |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Rate Limiting

- 300 requests per 60-second window
- 50 concurrent requests maximum

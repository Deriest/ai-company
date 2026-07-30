# AIC Platform - API Documentation

**Version:** 1.0.0  
**Base URL:** `http://your-domain:8000/api`  
**Authentication:** JWT Bearer Token

---

## Authentication

### POST /api/auth/login
Login and get JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_id": "uuid",
  "username": "admin",
  "role": "admin"
}
```

### POST /api/auth/register
Register new user (if enabled).

**Request:**
```json
{
  "username": "newuser",
  "password": "securepassword",
  "email": "user@example.com"
}
```

---

## Conversations

### GET /api/conversations
List all conversations for current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Conversation Title",
    "project_id": "uuid",
    "status": "active",
    "message_count": 10,
    "updated_at": "2026-07-21T19:00:00Z",
    "created_at": "2026-07-21T18:00:00Z"
  }
]
```

### POST /api/conversations
Create new conversation.

**Request:**
```json
{
  "title": "New Conversation",
  "project_id": "uuid"  // optional
}
```

### GET /api/conversations/{id}
Get single conversation metadata.

### GET /api/conversations/{id}/messages
Get all messages in conversation.

### POST /api/conversations/{id}/messages
Send message to conversation.

**Request:**
```json
{
  "content": "Build a new feature"
}
```

**Response:**
```json
{
  "response": "Got it — task T-001 created...",
  "intent": "task_request",
  "metadata": {
    "task_id": "uuid",
    "model": "FREE",
    "total_tokens": 245
  }
}
```

### POST /api/conversations/{id}/messages/stream
Send message with SSE streaming response.

**Response:** `text/event-stream`
```
data: {"type":"chunk","content":"Got"}
data: {"type":"chunk","content":" it"}
data: {"type":"done","intent":"task_request","metadata":{...}}
```

### PATCH /api/conversations/{id}
Update conversation (rename, archive).

**Request:**
```json
{
  "title": "Updated Title",
  "status": "archived"
}
```

### DELETE /api/conversations/{id}
Delete conversation.

### POST /api/conversations/batch
Batch operations on conversations.

**Request:**
```json
{
  "action": "delete",  // delete | archive | unarchive
  "ids": ["uuid1", "uuid2"]
}
```

---

## Tasks

### GET /api/tasks
List all tasks with filters.

**Query Parameters:**
- `status` - Filter by status
- `project_id` - Filter by project
- `limit` - Results per page (default: 50)
- `offset` - Pagination offset

**Response:**
```json
[
  {
    "id": "uuid",
    "code": "T-001",
    "title": "Build new feature",
    "description": "...",
    "type": "feature",
    "status": "implementation",
    "progress": 45,
    "worker_type": "backend",
    "project_id": "uuid",
    "created_at": "2026-07-21T18:00:00Z",
    "phase_results": {...}
  }
]
```

### POST /api/tasks
Create new task.

**Request:**
```json
{
  "project_id": "uuid",
  "title": "Task title",
  "description": "Task description",
  "type": "feature"  // feature | bugfix | refactor | test | docs
}
```

### GET /api/tasks/{id}
Get single task with full details.

### POST /api/tasks/{id}/dispatch
Dispatch task to worker pipeline.

### POST /api/tasks/{id}/cancel
Cancel running task.

### DELETE /api/tasks/{id}
Delete task.

---

## Workers

### GET /api/workers
List all workers.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "PM",
    "type": "pm",
    "status": "idle",
    "capabilities": ["planning", "coordination"],
    "current_task_id": null,
    "config": {"tier": "thinker"},
    "last_heartbeat": "2026-07-21T19:20:00Z"
  }
]
```

### GET /api/workers/{id}
Get single worker details.

### GET /api/workers/{id}/leases
Get worker's lease history.

---

## Projects

### GET /api/projects
List all projects.

### POST /api/projects
Create new project.

**Request:**
```json
{
  "name": "Project Name",
  "description": "Project description",
  "repo_path": "/path/to/repo"  // optional
}
```

### GET /api/projects/{id}
Get single project.

### PATCH /api/projects/{id}
Update project.

### DELETE /api/projects/{id}
Delete project.

---

## Approvals

### GET /api/approvals
List approval requests.

**Query Parameters:**
- `status` - Filter by status (pending | approved | rejected)

### POST /api/approvals/{id}/approve
Approve request.

### POST /api/approvals/{id}/reject
Reject request.

**Request (optional):**
```json
{
  "reason": "Reason for rejection"
}
```

---

## AI Providers

### GET /api/llm/providers
List configured LLM providers.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "VansRouter",
    "base_url": "http://172.19.0.2:20128/v1",
    "is_active": true,
    "config": {
      "thinker": "FREE",
      "crafter": "FREE",
      "sprinter": "FREE"
    }
  }
]
```

### GET /api/llm/providers/{id}/models
Get available models for provider.

### POST /api/llm/providers/{id}/activate
Activate provider.

### GET /api/llm/usage/breakdown
Get token usage breakdown.

**Response:**
```json
{
  "total_tokens": 125000,
  "input_tokens": 50000,
  "output_tokens": 75000,
  "by_provider": {"VansRouter": 125000},
  "by_model": {"FREE": 125000},
  "by_purpose": {"chat": 80000, "task": 45000}
}
```

### GET /api/llm/usage/timeline
Get 30-day usage timeline.

**Query Parameters:**
- `days` - Number of days (default: 30, max: 90)

---

## Dashboard

### GET /api/dashboard/overview
Get dashboard statistics.

**Response:**
```json
{
  "tasks": {
    "total": 50,
    "active": 5,
    "completed": 40,
    "failed": 2
  },
  "workers": {
    "total": 15,
    "active": 3
  },
  "tokens": {
    "today": 5000
  }
}
```

### GET /api/dashboard/events
Get recent system events.

**Query Parameters:**
- `limit` - Number of events (default: 20, max: 100)

---

## Console

### GET /api/console/logs
Get application logs.

**Query Parameters:**
- `limit` - Number of entries (default: 100, max: 1000)
- `level` - Filter by level (debug | info | warning | error)

---

## Users (Admin Only)

### GET /api/users
List all users.

### POST /api/users
Create new user.

### GET /api/users/{id}
Get user details.

### PATCH /api/users/{id}
Update user.

### DELETE /api/users/{id}
Delete user.

---

## Health Check

### GET /health
### GET /api/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "aic-platform",
  "version": "1.0.0",
  "database": "connected",
  "llm_configured": true
}
```

---

## WebSocket

### WS /ws
WebSocket connection for real-time updates.

**Client → Server:**
```json
{
  "type": "subscribe",
  "channel": "tasks"  // tasks | workers | events
}
```

**Server → Client:**
```json
{
  "type": "task.updated",
  "data": {
    "id": "uuid",
    "status": "implementation",
    "progress": 45
  }
}
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Error message"
}
```

**HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Rate Limit Exceeded
- `500` - Internal Server Error

---

## Rate Limiting

Default limits:
- Anonymous: 100 requests/minute
- Authenticated: 1000 requests/minute
- Admin: Unlimited

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1721590800
```

---

## Authentication

Include JWT token in Authorization header:

```
Authorization: Bearer <token>
```

Token expires after 7 days.

---

**Last Updated:** 2026-07-21  
**Version:** 1.0.0

# AIC Platform Backend API Audit Report

**Date:** 2026-07-21  
**Scope:** Backend CRUD endpoints for Projects, Milestones, Workers, Tasks, and related entities  
**Goal:** Commercial-grade API completeness

---

## Executive Summary

The AIC Platform backend provides 56 API endpoints across 12 route modules. Core CRUD operations exist for primary entities (Projects, Tasks, Workers, Approvals, Conversations), but **significant gaps remain** in advanced features essential for commercial-grade operation:

- **Missing:** Bulk operations, advanced filtering, proper pagination, sorting
- **Missing:** Milestone CRUD endpoints (read-only access exists)
- **Missing:** Project update/delete operations
- **Missing:** Worker update/delete operations
- **Missing:** Task update/reassignment operations
- **Incomplete:** Search capabilities across entities
- **Incomplete:** Batch operations (only conversations support batch)

---

## 1. Projects API (`/api/projects`)

### Current Endpoints (5)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/` | List all projects | ✅ Basic |
| POST | `/` | Create project | ✅ Complete |
| GET | `/{project_id}` | Get project detail | ✅ Complete |
| GET | `/{project_id}/tasks` | Get project tasks | ✅ Complete |
| GET | `/{project_id}/milestones` | Get project milestones | ✅ Complete |

### Gaps & Missing Features

#### Critical (P0)
- ❌ **PUT `/projects/{project_id}`** — Update project (name, description, repo_path, status)
- ❌ **DELETE `/projects/{project_id}`** — Delete/archive project
- ❌ **Pagination** — List endpoint returns unbounded results
- ❌ **Filtering** — No filter by status, owner_id, date range

#### High Priority (P1)
- ❌ **POST `/projects/batch`** — Bulk operations (archive, delete, status change)
- ❌ **GET `/projects?search=...`** — Full-text search by name/description
- ❌ **GET `/projects?sort=...`** — Sorting by name, created_at, updated_at
- ❌ **GET `/projects/{id}/stats`** — Project statistics (task counts by status, completion %)
- ❌ **PUT `/projects/{id}/config`** — Update project configuration JSON

#### Medium Priority (P2)
- ❌ **POST `/projects/{id}/duplicate`** — Clone project structure
- ❌ **GET `/projects/{id}/activity`** — Recent activity feed
- ❌ **GET `/projects/{id}/members`** — Project team members (if multi-user)

---

## 2. Milestones API (`/api/milestones` or `/api/projects/{id}/milestones`)

### Current Endpoints (1)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/projects/{id}/milestones` | List project milestones | ✅ Read-only |

### Gaps & Missing Features

#### Critical (P0)
- ❌ **POST `/milestones`** — Create milestone
- ❌ **GET `/milestones/{id}`** — Get milestone detail
- ❌ **PUT `/milestones/{id}`** — Update milestone (name, description, status, due_date)
- ❌ **DELETE `/milestones/{id}`** — Delete milestone
- ❌ **GET `/milestones/{id}/tasks`** — Get tasks in milestone

#### High Priority (P1)
- ❌ **POST `/milestones/batch`** — Bulk milestone operations
- ❌ **PUT `/milestones/{id}/status`** — Change milestone status (planned → active → done)
- ❌ **POST `/milestones/{id}/tasks`** — Add tasks to milestone
- ❌ **DELETE `/milestones/{id}/tasks/{task_id}`** — Remove task from milestone

**Note:** Milestone model exists in storage layer but has zero write endpoints. This is a **major gap** for project planning features.

---

## 3. Tasks API (`/api/tasks`)

### Current Endpoints (5)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/` | List tasks | ✅ Basic filtering |
| POST | `/` | Create task | ✅ Complete |
| GET | `/{task_id}` | Get task detail | ✅ Complete |
| POST | `/{task_id}/dispatch` | Dispatch task to worker | ✅ Complete |
| POST | `/{task_id}/cancel` | Cancel task | ✅ Complete |

### Gaps & Missing Features

#### Critical (P0)
- ❌ **PUT `/tasks/{id}`** — Update task (title, description, priority, worker_type, milestone_id)
- ❌ **DELETE `/tasks/{id}`** — Delete task
- ❌ **Pagination** — List endpoint returns unbounded results
- ❌ **Sorting** — No sort by priority, created_at, updated_at

#### High Priority (P1)
- ❌ **POST `/tasks/batch`** — Bulk operations (cancel, reassign, change priority)
- ❌ **PUT `/tasks/{id}/priority`** — Update task priority
- ❌ **PUT `/tasks/{id}/assign`** — Reassign task to different worker
- ❌ **POST `/tasks/{id}/retry`** — Retry failed task
- ❌ **GET `/tasks?search=...`** — Search by title/description
- ❌ **Advanced filtering** — Filter by priority, date range, created_by, worker_type, milestone_id

#### Medium Priority (P2)
- ❌ **POST `/tasks/{id}/duplicate`** — Clone task
- ❌ **GET `/tasks/{id}/timeline`** — Task execution timeline/history
- ❌ **GET `/tasks/{id}/artifacts`** — List task artifacts with details
- ❌ **POST `/tasks/{id}/artifacts`** — Manually add artifact
- ❌ **GET `/tasks/{id}/dependencies`** — Task dependency graph

---

## 4. Workers API (`/api/workers`)

### Current Endpoints (4)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/` | List workers | ✅ Complete (auto-registers) |
| GET | `/registry` | Worker type registry | ✅ Complete |
| GET | `/{worker_id}` | Get worker detail | ✅ Complete |
| GET | `/{worker_id}/leases` | Get worker leases | ✅ Complete |

### Gaps & Missing Features

#### Critical (P0)
- ❌ **PUT `/workers/{id}`** — Update worker config (tier, model, timeout, capabilities)
- ❌ **DELETE `/workers/{id}`** — Delete/deregister worker
- ❌ **POST `/workers/{id}/heartbeat`** — Manual heartbeat/health check

#### High Priority (P1)
- ❌ **POST `/workers`** — Manual worker registration (currently auto-only)
- ❌ **POST `/workers/{id}/restart`** — Restart worker (clear state)
- ❌ **GET `/workers?status=...`** — Filter by status (idle, working, failed)
- ❌ **GET `/workers?type=...`** — Filter by worker type
- ❌ **GET `/workers/{id}/stats`** — Worker statistics (success rate, avg duration, task count)
- ❌ **POST `/workers/batch`** — Bulk operations (restart, config update)

#### Medium Priority (P2)
- ❌ **GET `/workers/{id}/performance`** — Performance metrics over time
- ❌ **POST `/workers/{id}/enable` / `disable`** — Enable/disable worker
- ❌ **GET `/workers/{id}/current-task`** — Currently executing task details

---

## 5. Approvals API (`/api/approvals`)

### Current Endpoints (3)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/` | List approvals | ✅ Basic filtering |
| GET | `/pending` | List pending approvals | ✅ Complete |
| POST | `/{approval_id}/decide` | Approve/reject | ✅ Complete |

### Gaps & Missing Features

#### Critical (P0)
- ❌ **Pagination** — List endpoint has hard limit of 50

#### High Priority (P1)
- ❌ **GET `/approvals/{id}`** — Get approval detail
- ❌ **GET `/approvals?task_id=...`** — Filter by task
- ❌ **POST `/approvals/batch`** — Bulk approve/reject
- ❌ **GET `/approvals?approver_id=...`** — Filter by approver
- ❌ **GET `/approvals?requested_by=...`** — Filter by requester

#### Medium Priority (P2)
- ❌ **POST `/approvals/{id}/delegate`** — Delegate approval to another user
- ❌ **PUT `/approvals/{id}/reason`** — Update approval reason

---

## 6. Conversations API (`/api/conversations`)

### Current Endpoints (10)
| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| GET | `/` | List conversations | ✅ Complete |
| POST | `/` | Create conversation | ✅ Complete |
| GET | `/{id}` | Get conversation | ✅ Complete |
| PUT | `/{id}` | Update conversation | ✅ Complete |
| DELETE | `/{id}` | Delete conversation | ✅ Complete |
| POST | `/batch` | Batch operations | ✅ Complete |
| GET | `/{id}/messages` | Get messages | ✅ Complete |
| POST | `/{id}/messages` | Send message | ✅ Complete |
| POST | `/{id}/messages/stream` | Send message (SSE) | ✅ Complete |
| DELETE | `/{id}/messages` | Clear messages | ✅ Complete |

### Gaps & Missing Features

#### High Priority (P1)
- ❌ **Pagination** — Messages endpoint returns unbounded results
- ❌ **GET `/conversations?search=...`** — Search by title/content
- ❌ **GET `/messages?conversation_id=...&role=...`** — Filter messages by role
- ❌ **PUT `/messages/{id}`** — Edit message
- ❌ **DELETE `/messages/{id}`** — Delete individual message

#### Medium Priority (P2)
- ❌ **POST `/conversations/{id}/export`** — Export conversation (JSON, Markdown)
- ❌ **GET `/conversations/{id}/summary`** — AI-generated summary
- ❌ **POST `/conversations/{id}/fork`** — Fork conversation from a message

**Note:** Conversations is the most complete API, including batch operations. Use as reference for other endpoints.

---

## 7. Supporting APIs

### Users API (`/api/users`) — ✅ Complete
- Full CRUD: list, create, update, delete (soft delete)
- Admin-only access controls
- Role management

### Auth API (`/api/auth`) — ✅ Complete
- Login, register, token refresh
- API key generation
- Current user info

### LLM Providers API (`/api/llm`) — ✅ Complete
- Full provider CRUD
- Model listing, testing
- Activation/deactivation
- Usage tracking with breakdowns

### Dashboard API (`/api/dashboard`) — ✅ Complete
- Overview stats
- Events, audit logs, metrics
- No pagination on events/audit logs (P1 gap)

---

## Cross-Cutting Gaps

### 1. Pagination (Critical)
**Current State:** Only `approvals` endpoint has hard limit (50). All other list endpoints return unbounded results.

**Recommendation:** Implement cursor-based or offset/limit pagination across all list endpoints:
```
GET /api/projects?limit=20&offset=0
GET /api/tasks?limit=50&cursor=abc123
```

**Standard Response:**
```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

### 2. Filtering (Critical)
**Current State:** Minimal filtering exists (tasks by project_id/status, approvals by status, conversations by status).

**Recommendation:** Implement query parameter filtering for common fields:
- Status filters on all stateful entities
- Date range filters (`created_after`, `created_before`, `updated_after`, `updated_before`)
- Owner/creator filters
- Project/milestone association filters

**Example:**
```
GET /api/tasks?status=completed&project_id=abc&created_after=2026-07-01&priority=2
```

### 3. Sorting (Critical)
**Current State:** Hard-coded sorting (mostly `created_at DESC`).

**Recommendation:** Add `sort` and `order` query parameters:
```
GET /api/projects?sort=name&order=asc
GET /api/tasks?sort=priority,created_at&order=desc,desc
```

### 4. Search (High Priority)
**Current State:** No full-text search on any endpoint.

**Recommendation:** Add `search` or `q` parameter for text fields:
```
GET /api/projects?q=frontend
GET /api/tasks?search=authentication bug
```

Use SQLite FTS5 or `LIKE` queries for implementation.

### 5. Bulk Operations (High Priority)
**Current State:** Only conversations support batch operations.

**Recommendation:** Add bulk endpoints for common operations:
```
POST /api/projects/batch
POST /api/tasks/batch
POST /api/workers/batch
POST /api/approvals/batch
```

**Payload:**
```json
{
  "action": "archive" | "delete" | "update_status" | "assign",
  "ids": ["id1", "id2", "id3"],
  "params": { "status": "archived" }
}
```

### 6. Field Selection (Medium Priority)
**Recommendation:** Add `fields` parameter to reduce payload size:
```
GET /api/tasks?fields=id,title,status
```

### 7. Include/Expand Relations (Medium Priority)
**Recommendation:** Add `include` parameter to embed related entities:
```
GET /api/projects/{id}?include=tasks,milestones
GET /api/tasks/{id}?include=project,worker,approvals
```

---

## Recommended Priority Matrix

### Phase 1: Critical Gaps (P0) — 1-2 weeks
1. **Pagination** — Implement across all list endpoints
2. **Projects:** Update, Delete endpoints
3. **Tasks:** Update, Delete endpoints
4. **Milestones:** Full CRUD (create, read, update, delete)
5. **Workers:** Update, Delete endpoints
6. **Filtering:** Basic status/date range filters

### Phase 2: High Priority (P1) — 2-3 weeks
1. **Bulk Operations** — Projects, Tasks, Workers, Approvals
2. **Search** — Full-text search on Projects, Tasks
3. **Sorting** — Configurable sort on all list endpoints
4. **Advanced Filtering** — Priority, assignment, milestone filters
5. **Task Management** — Retry, reassign, priority update

### Phase 3: Medium Priority (P2) — 3-4 weeks
1. **Statistics Endpoints** — Project stats, worker stats, task timelines
2. **Relation Expansion** — Include/expand query params
3. **Export/Import** — Conversation export, project export
4. **Performance Metrics** — Worker performance, task analytics
5. **Field Selection** — Reduce payload size with field filters

---

## OpenAPI/Swagger Documentation Gaps

**Current State:** Basic FastAPI auto-generated docs at `/api/docs`

**Recommendations:**
1. Add comprehensive docstrings to all route functions
2. Add request/response examples using Pydantic `Config.schema_extra`
3. Document query parameters with FastAPI `Query()` annotations
4. Add error response models (400, 401, 403, 404, 500)
5. Version the API (`/api/v1/projects`) for future breaking changes

---

## Security & Validation Gaps

1. **Input Validation:** Some endpoints lack request body validation (e.g., batch operations)
2. **Rate Limiting:** Global 200/min limit exists, but no per-endpoint limits
3. **Authorization:** Most endpoints check authentication but not resource ownership (user can access any project/task)
4. **Audit Logging:** Only basic event recording, no comprehensive audit trail on all mutations

---

## Performance Concerns

1. **N+1 Queries:** Several endpoints fetch related entities without eager loading
2. **Unbounded Lists:** Memory risk with large result sets
3. **No Caching:** Frequently accessed data (worker registry, project list) not cached
4. **No Database Indexes:** Check index coverage on foreign keys and filter columns

---

## Summary of Findings

### Endpoint Counts by Completeness
- **Complete (full CRUD + advanced):** 2 (Conversations, Users)
- **Good (full CRUD, missing advanced):** 2 (Auth, LLM Providers)
- **Basic (read + create only):** 3 (Projects, Tasks, Workers)
- **Incomplete (read-only or partial):** 2 (Milestones, Approvals)
- **Supporting (stats/observability):** 1 (Dashboard)

### Total Missing Endpoints
- **Critical (P0):** ~25 endpoints
- **High Priority (P1):** ~30 endpoints
- **Medium Priority (P2):** ~20 endpoints

### Implementation Effort Estimate
- **P0 (Critical):** 40-60 developer hours
- **P1 (High):** 60-80 developer hours
- **P2 (Medium):** 40-60 developer hours
- **Total:** 140-200 developer hours (~4-5 weeks for 1 developer)

---

## Next Steps

1. **Review & Prioritize:** Validate priority assignments with product/stakeholders
2. **API Design Review:** Create detailed specs for new endpoints before implementation
3. **Database Migration Plan:** Add indexes for new filter columns
4. **Testing Strategy:** Ensure comprehensive API tests for new endpoints
5. **Documentation:** Update OpenAPI specs and developer documentation
6. **Versioning Strategy:** Decide on API versioning approach before breaking changes

---

**Report Generated:** 2026-07-21  
**Backend Version:** Current (main branch)  
**Total API Endpoints Audited:** 56  
**Recommended New Endpoints:** ~75

# API Contract Audit: Frontend ↔ Backend

**Date:** 2026-07-21
**Scope:** All frontend API calls in `frontend/src/` vs all backend route handlers in `backend/routes/`

---

## Route Mounting (backend/main.py)

| Prefix | Module |
|---|---|
| `/api/auth` | auth.py |
| `/api/projects` | projects.py |
| `/api/tasks` | tasks.py |
| `/api/conversations` | conversations.py |
| `/api/workers` | workers.py |
| `/api/approvals` | approvals.py |
| `/api/dashboard` | dashboard.py |
| `/api/llm` | llm.py |
| `/api/users` | users.py |
| `/api/console` | console.py |
| `/ws` | websocket.py |

---

## 🔴 Bugs / Breaking Mismatches

### 1. Tasks list endpoint missing `description` — search-by-description broken

**File:** `frontend/src/pages/Tasks.tsx:176`
```ts
.filter((t) => !search || t.title.toLowerCase().includes(search) || t.description?.toLowerCase().includes(search))
```
**Backend:** `GET /api/tasks` returns `{id, title, type, status, progress, worker_type, project_id, created_at}` — **does NOT include `description`**.

**Impact:** Searching tasks by description content will never match because `t.description` is always `undefined` on list results. The search silently ignores description.

**Fix:** Add `description` to the task list endpoint response dict in `backend/routes/tasks.py:list_tasks`.

---

### 2. Tasks list missing fields that frontend `Task` type expects

**Frontend type** (`client.ts:73-88`) defines: `description`, `approval_required`, `artifacts`, `error_message`, `started_at`, `completed_at`.

**Backend `GET /api/tasks`** returns none of these. Only `GET /api/tasks/{id}` returns them.

**Impact:** The task list type is silently incomplete. `approval_required` is always `undefined` in list view (though not displayed currently). Not breaking since the detail panel fetches the full task separately.

**Severity:** Low (informational — detail panel works correctly).

---

### 3. Backend cancel task uses query param for `reason` — frontend never sends it

**Backend:** `POST /api/tasks/{id}/cancel` has `reason: str = ""` as a **query parameter** (FastAPI function arg).
**Frontend:** `api.post(`/tasks/${id}/cancel`)` — sends POST with no body, no query params.

**Impact:** Cancel reasons are always empty. Backend should accept JSON body instead of query param for POST requests.

---

## 🟡 Schema Discrepancies (non-breaking but risky)

### 4. Chat.tsx uses raw `fetch()` bypassing centralized `api` client

**File:** `frontend/src/pages/Chat.tsx:137-144`
```ts
let res = await fetch(`/api/conversations/${active}/messages/stream`, { method: "POST", headers, body });
// fallback:
res = await fetch(`/api/conversations/${active}/messages`, { method: "POST", headers, body });
```

These bypass `client.ts` which handles 401→redirect and error extraction. If the stream endpoint returns 401, the raw fetch won't trigger the auth cleanup that the `api` wrapper does.

**Impact:** Auth failures on the stream path leave stale tokens in localStorage.

---

### 5. `POST /auth/api-key` — no way to set custom key name from frontend

**Backend:** `POST /api/auth/api-key` has `name: str = "default"` as a **query parameter**.
**Frontend:** `api.post("/auth/api-key")` — sends no body, no query param.

**Impact:** API keys always get name `"default"`. Minor — probably fine for single-key usage.

---

### 6. Create conversation returns incomplete object

**Backend `POST /api/conversations`** returns `{id, title, project_id, status}` — missing `message_count`, `updated_at`, `created_at`.
**Frontend** casts the response as `ConversationWithMeta` and immediately inserts into the list.

**Impact:** Newly created conversations show without `message_count` or timestamps until the list reloads on `loadConvs()`. UX nit.

---

## 🟢 Verified Correct (all match)

### Auth (AuthContext.tsx ↔ auth.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /auth/me` | `GET /api/auth/me` → `{id, username, email, role, is_active}` | ✅ matches `AuthUser` |
| `POST /auth/login` `{username, password}` | `POST /api/auth/login` `LoginRequest` → `TokenResponse` | ✅ |
| `POST /auth/register` `{username, password, email?}` | `POST /api/auth/register` `RegisterRequest` → `TokenResponse` | ✅ |

### Chat (Chat.tsx ↔ conversations.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /conversations` | `GET /api/conversations` → `[{id, title, project_id, status, message_count, updated_at, created_at}]` | ✅ |
| `GET /conversations/{id}/messages` | `GET /api/conversations/{id}/messages` → `[{id, role, content, intent, metadata, created_at}]` | ✅ |
| `POST /conversations` `{title}` | `POST /api/conversations` `ConversationCreate` | ✅ |
| `PUT /conversations/{id}` `{title}` or `{status}` | `PUT /api/conversations/{id}` `ConversationUpdate` | ✅ |
| `DELETE /conversations/{id}` | `DELETE /api/conversations/{id}` | ✅ |
| `POST /conversations/batch` `{action, ids}` | `POST /api/conversations/batch` `BatchRequest` | ✅ |
| `POST /conversations/{id}/messages/stream` `{content}` | `POST /api/conversations/{id}/messages/stream` SSE | ✅ |
| `POST /conversations/{id}/messages` `{content}` | `POST /api/conversations/{id}/messages` `MessageSend` → `{response, intent, metadata}` | ✅ |

### Dashboard (Dashboard.tsx ↔ dashboard.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /dashboard/overview` | `GET /api/dashboard/overview` → `Overview` | ✅ |
| `GET /dashboard/events?limit=20` | `GET /api/dashboard/events` → `[EventItem]` | ✅ |

### Workers (Workers.tsx + WorkerDetail.tsx ↔ workers.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /workers` | `GET /api/workers` → `[Worker]` | ✅ (backend adds extra `role`, `description` — ignored by frontend) |
| `GET /workers/{id}` | `GET /api/workers/{id}` | ✅ |
| `GET /workers/{id}/leases` | `GET /api/workers/{id}/leases` → `[Lease]` | ✅ |

### Tasks (Tasks.tsx ↔ tasks.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /tasks` | `GET /api/tasks` | ⚠️ missing fields (see #1, #2) |
| `GET /tasks/{id}` | `GET /api/tasks/{id}` | ✅ (all fields present) |
| `POST /tasks` `{project_id, title, description, type}` | `POST /api/tasks` `TaskCreate` | ✅ |
| `POST /tasks/{id}/dispatch` | `POST /api/tasks/{id}/dispatch` | ✅ |
| `POST /tasks/{id}/cancel` | `POST /api/tasks/{id}/cancel` | ⚠️ reason not sent (see #3) |

### Projects (Projects.tsx ↔ projects.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /projects` | `GET /api/projects` → `[ProjectResponse]` | ✅ |
| `GET /projects/{id}/tasks` | `GET /api/projects/{id}/tasks` → `[Task]` | ✅ |
| `POST /projects` `{name, description, repo_path}` | `POST /api/projects` `ProjectCreate` | ✅ |

### Approvals (Approvals.tsx ↔ approvals.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /approvals` | `GET /api/approvals` → `[Approval]` | ✅ |
| `POST /approvals/{id}/decide` `{decision}` | `POST /api/approvals/{id}/decide` `ApprovalDecision` | ✅ (`reason` defaults to `""`) |

### Console (Console.tsx ↔ console.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /console/logs?limit=200` | `GET /api/console/logs` → `{logs: [...], total}` | ✅ |
| `GET /console/events?limit=100` | `GET /api/console/events` → `[EventItem]` | ✅ |
| `GET /console/status` | `GET /api/console/status` | ✅ |

### LLM / Usage (Usage.tsx + Settings.tsx + Providers.tsx ↔ llm.py)
| Frontend Call | Backend Endpoint | Schema |
|---|---|---|
| `GET /llm/providers` | `GET /api/llm/providers` → `[ProviderResponse]` | ✅ |
| `POST /llm/providers` `{name, base_url, api_key, models, set_active}` | `POST /api/llm/providers` `ProviderCreate` | ✅ |
| `PUT /llm/providers/{id}` `{models}` | `PUT /api/llm/providers/{id}` `ProviderUpdate` | ✅ |
| `DELETE /llm/providers/{id}` | `DELETE /api/llm/providers/{id}` | ✅ |
| `POST /llm/providers/{id}/activate` | `POST /api/llm/providers/{id}/activate` | ✅ |
| `POST /llm/providers/{id}/test` | `POST /api/llm/providers/{id}/test` → `{status, count?, error?}` | ✅ |
| `GET /llm/providers/{id}/models` | `GET /api/llm/providers/{id}/models` → `{models: [{id, owned_by}], count}` | ✅ |
| `GET /llm/usage` | `GET /api/llm/usage` → `{summary, recent_db}` | ✅ |
| `GET /llm/usage/breakdown` | `GET /api/llm/usage/breakdown` | ✅ |
| `GET /llm/usage/timeline` | `GET /api/llm/usage/timeline` | ✅ |

---

## 📋 Orphaned Backend Endpoints (no frontend consumer)

| Endpoint | Module | Purpose |
|---|---|---|
| `GET /api/users` | users.py | Admin user listing |
| `POST /api/users` | users.py | Admin user creation |
| `PUT /api/users/{id}` | users.py | Admin user update |
| `DELETE /api/users/{id}` | users.py | Admin user deactivation |
| `GET /api/workers/registry` | workers.py | Worker type registry metadata |
| `GET /api/dashboard/metrics` | dashboard.py | 24h metrics |
| `GET /api/dashboard/audit` | dashboard.py | Audit log (used by Audit page — not orphaned) |
| `GET /api/console/metrics` | console.py | System metrics |
| `GET /api/console/audit` | console.py | Duplicate of dashboard/audit |
| `DELETE /api/conversations/{id}/messages` | conversations.py | Clear message history |
| `GET /api/projects/{id}` | projects.py | Single project detail |
| `GET /api/projects/{id}/milestones` | projects.py | Project milestones |
| `GET /api/approvals/pending` | approvals.py | Pending-only approval filter |
| `GET /api/llm/usage/summary` | llm.py | Simple usage summary |
| `GET /api/auth/api-key` | N/A | Only `POST` exists (correct) |

---

## Summary of Required Fixes

| Priority | Issue | Fix Location |
|---|---|---|
| 🔴 High | Task list missing `description` → search broken | `backend/routes/tasks.py:list_tasks` — add `description` to response |
| 🟡 Medium | Chat stream bypasses auth error handling | `frontend/src/pages/Chat.tsx` — wrap raw fetch with auth-aware error handling |
| 🟢 Low | Cancel task can't send reason | `backend/routes/tasks.py:cancel_task` — accept JSON body |
| 🟢 Low | Create conversation returns incomplete object | `backend/routes/conversations.py:create_conversation` — add timestamps |

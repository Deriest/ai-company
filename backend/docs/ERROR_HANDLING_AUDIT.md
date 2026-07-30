# AIC Platform Backend Error Handling Audit

**Date:** 2026-07-21  
**Auditor:** Automated Analysis  
**Scope:** All FastAPI backend routes in `/backend/routes/`

## Executive Summary

The audit reviewed 12 route modules covering authentication, projects, tasks, conversations, workers, approvals, dashboard, LLM providers, users, WebSocket, and console endpoints. The backend demonstrates **good baseline error handling** with consistent use of HTTPException and Pydantic validation. However, several **critical gaps** exist around input validation, error messages, database error handling, and async exception handling.

---

## Findings by Severity

### 🔴 CRITICAL Issues

#### 1. **Missing Database Error Handling**
- **Files:** All route files
- **Issue:** No `try-except` blocks around database operations. SQLAlchemy errors (connection loss, constraint violations, deadlocks) will bubble up as 500 errors with internal stack traces.
- **Impact:** Exposes internal database structure, connection strings, and implementation details to clients.
- **Example:** 
  ```python
  # conversations.py:143
  result = await session.execute(
      select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
  )
  conv = result.scalar_one_or_none()
  # No error handling if DB connection is lost
  ```

#### 2. **Missing Input Validation on Query Parameters**
- **Files:** `tasks.py`, `conversations.py`, `approvals.py`, `llm.py`, `console.py`
- **Issue:** Query parameters like `status`, `project_id`, `limit` are accepted without validation beyond type hints. Invalid enum values or out-of-range limits are not caught.
- **Example:**
  ```python
  # tasks.py:43-44
  status: str | None = None,  # No validation if it's a valid TaskStatus
  ```

#### 3. **No Authorization Checks for Resource Ownership**
- **Files:** `conversations.py`, `projects.py`, `tasks.py`
- **Issue:** Some endpoints verify `user_id`, but many resource-fetching operations don't verify the current user owns/has access to the resource before operating on it.
- **Example:**
  ```python
  # projects.py:72-76
  # GET /projects/{project_id} doesn't check if user has access to this project
  result = await session.execute(select(Project).where(Project.id == project_id))
  project = result.scalar_one_or_none()
  if not project:
      raise HTTPException(404, "Project not found")
  return project  # Returns ANY project, regardless of ownership
  ```

#### 4. **Unhandled External Service Failures**
- **Files:** `llm.py`
- **Issue:** Provider test endpoints (lines 215-249, 252-283) have basic error handling but don't distinguish between network failures, auth failures, and timeout errors. All return generic error strings.
- **Example:**
  ```python
  # llm.py:247-249
  except Exception as e:
      await test_llm.close()
      return {"status": "error", "error": str(e)}  # Too generic
  ```

### 🟡 HIGH Priority Issues

#### 5. **Inconsistent Error Messages**
- **Files:** Multiple
- **Issue:** Error messages vary in style and detail. Some are user-friendly, others are technical.
- **Examples:**
  - `auth.py:46`: "Username already exists" ✅ Good
  - `auth.py:73`: "Invalid credentials" ✅ Good
  - `tasks.py:149`: "Task cannot be dispatched from status: {task.status}" ✅ Good
  - `conversations.py:89`: "Invalid action" ❌ Too vague
  - `approvals.py:84`: "Approval already {approval.status}" ❌ Exposes internal state directly

#### 6. **Missing Validation on Complex Inputs**
- **Files:** `llm.py`, `conversations.py`, `approvals.py`
- **Issue:** Pydantic models validate structure but not business rules.
- **Examples:**
  - `llm.py:28`: No validation that `timeout` is reasonable (1-300 range)
  - `conversations.py:88`: `action` validated in code rather than Pydantic enum
  - `approvals.py:16`: `decision` is string instead of enum ("approved"/"rejected")

#### 7. **Incomplete Background Task Error Handling**
- **Files:** `conversations.py`, `tasks.py`
- **Issue:** Background tasks catch all exceptions and log them, but don't update task status or notify users of failures.
- **Example:**
  ```python
  # conversations.py:347-348
  except Exception as e:
      logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
  # Task remains in "created" status forever
  ```

#### 8. **No Rate Limit Error Context**
- **Files:** `main.py`
- **Issue:** Rate limit handler returns generic message without telling users when they can retry.
- **Example:**
  ```python
  # main.py:101-105
  return JSONResponse(
      status_code=429,
      content={"detail": "Rate limit exceeded. Try again later."},
  )
  # Missing: Retry-After header, current limit info
  ```

### 🟢 MEDIUM Priority Issues

#### 9. **No Pagination Validation**
- **Files:** `console.py`, `dashboard.py`, `llm.py`
- **Issue:** `limit` parameters have bounds (e.g., `ge=1, le=1000`) but no handling when client requests exceed reasonable bounds.
- **Impact:** Large limit values could cause memory issues or slow queries.

#### 10. **Missing Request ID Tracing**
- **Files:** All routes
- **Issue:** No correlation IDs or trace IDs in error responses. Makes debugging difficult when users report errors.

#### 11. **WebSocket Error Handling Incomplete**
- **Files:** `websocket.py`
- **Issue:** JSON parse errors (line 118) will crash the connection instead of sending an error message.
- **Example:**
  ```python
  # websocket.py:118
  msg = json.loads(data) if data.startswith("{") else {"text": data}
  # JSONDecodeError not caught
  ```

#### 12. **Inconsistent NULL Handling**
- **Files:** Multiple
- **Issue:** Some endpoints handle missing fields gracefully, others don't check for null values from DB queries.
- **Example:**
  ```python
  # conversations.py:240
  "metadata": m.meta if hasattr(m, 'meta') else {},
  # Should check if m.meta is None
  ```

---

## HTTP Status Code Usage Audit

| Code | Usage | Correctness |
|------|-------|-------------|
| **200** | Implicit default for all GET/PUT endpoints | ✅ Correct |
| **201** | Missing for POST create operations | ❌ Should use 201 for creates |
| **400** | Used for invalid actions, bad inputs | ✅ Mostly correct |
| **401** | Auth failures, invalid credentials | ✅ Correct |
| **403** | Role/permission checks | ✅ Correct |
| **404** | Resource not found | ✅ Correct |
| **409** | Username conflict (`users.py:57`) | ✅ Correct |
| **429** | Rate limit exceeded | ✅ Correct |
| **500** | Unhandled exceptions (implicit) | ⚠️ Too generic |
| **502** | External service failure (`llm.py:283`) | ✅ Correct |

**Missing:**
- **422** Unprocessable Entity (let FastAPI/Pydantic handle this automatically)
- **503** Service Unavailable (for DB connection loss, LLM provider down)

---

## Validation Coverage

### ✅ Well-Validated

| Route | Validation Method | Notes |
|-------|------------------|-------|
| `auth.py` | Pydantic models + DB uniqueness checks | Good |
| `users.py` | Pydantic models + enum validation | Good |
| `projects.py` | Pydantic models + slug generation | Good |

### ⚠️ Partially Validated

| Route | Issue |
|-------|-------|
| `tasks.py` | Query params not validated against enums |
| `conversations.py` | Batch action validated in route, not Pydantic |
| `approvals.py` | Decision string not validated (should be enum) |
| `llm.py` | Timeout/limit ranges not enforced |

### ❌ Poorly Validated

| Route | Issue |
|-------|-------|
| `dashboard.py` | No validation on query filters |
| `console.py` | Filter params accepted without sanitization |
| `websocket.py` | Message payloads not validated |

---

## Detailed Route-by-Route Analysis

### 1. `auth.py` (110 lines)

**Strengths:**
- ✅ Good password validation
- ✅ Proper 401 for invalid credentials
- ✅ 400 for duplicate username
- ✅ 403 for disabled accounts

**Issues:**
- ❌ No password strength requirements
- ❌ No rate limiting on login attempts (relies on global limiter)
- ❌ API key generation doesn't check for duplicates
- ❌ No validation that role is valid enum value (line 20)

**Missing Error Cases:**
- Database connection failure during user lookup
- Concurrent registration of same username

---

### 2. `conversations.py` (349 lines)

**Strengths:**
- ✅ User ownership validation on most endpoints
- ✅ 404 for missing conversations
- ✅ Good error handling in message processing (lines 266-269)

**Issues:**
- ❌ Batch action validation done in route code (line 88) instead of Pydantic enum
- ❌ `/messages` endpoint (line 222) doesn't verify conversation ownership before returning messages
- ❌ SSE streaming endpoint (line 283) doesn't handle connection drops during message processing
- ❌ Background task failure leaves task in "created" status forever (line 347)
- ❌ No validation on `req.content` length (could send multi-MB prompts)

**Missing Error Cases:**
- ConversationEngine throws unhandled exceptions
- Database transaction fails mid-batch operation
- Message deletion when conversation has active streams

---

### 3. `tasks.py` (186 lines)

**Strengths:**
- ✅ Good Pydantic validation
- ✅ Clear error messages
- ✅ 404 for missing tasks

**Issues:**
- ❌ No validation that `status` query param (line 44) is a valid TaskStatus enum value
- ❌ No validation that `project_id` query param (line 43) actually exists
- ❌ Dispatch endpoint (line 136) doesn't check if user has permission to dispatch task
- ❌ Background executor failure (line 184) not handled
- ❌ No check if task was already cancelled while dispatching

**Missing Error Cases:**
- Task creation when project doesn't exist
- Concurrent dispatch of same task
- Executor crashes during task execution

---

### 4. `projects.py` (113 lines)

**Strengths:**
- ✅ Clean Pydantic models
- ✅ Slug auto-generation
- ✅ 404 for missing projects

**Issues:**
- ❌ **CRITICAL:** GET `/projects/{project_id}` (line 66) returns ANY project without ownership check
- ❌ **CRITICAL:** GET `/projects/{project_id}/tasks` (line 79) returns tasks without verifying user access
- ❌ No validation that slug is unique
- ❌ No validation on repo_path format/existence

**Missing Error Cases:**
- Slug collision
- Invalid repo path format
- Project creation when repo_path already used by another project

---

### 5. `workers.py` (180 lines)

**Strengths:**
- ✅ Auto-registration logic
- ✅ Public registry endpoint (no auth needed)
- ✅ Good metadata structure

**Issues:**
- ❌ No validation that worker_id exists before querying leases
- ❌ Auto-registration doesn't handle duplicate inserts well (line 60)
- ❌ No error handling if WORKER_META is missing a type

**Missing Error Cases:**
- Race condition in ensure_workers_registered
- Worker metadata missing required fields

---

### 6. `approvals.py` (96 lines)

**Strengths:**
- ✅ Clean separation of pending vs all approvals
- ✅ Good status validation (line 83)

**Issues:**
- ❌ `decision` field (line 16) is string instead of enum
- ❌ No validation that approver has permission to approve
- ❌ Dispatcher.decide_approval errors not caught (line 88)

**Missing Error Cases:**
- Approval decision race condition (two users approve simultaneously)
- Dispatcher throws exception

---

### 7. `llm.py` (424 lines)

**Strengths:**
- ✅ Comprehensive CRUD for providers
- ✅ Good error handling in test endpoint (line 239-249)
- ✅ Proper 502 for external failures (line 283)

**Issues:**
- ❌ No validation on timeout range (line 28)
- ❌ Provider name uniqueness check but no handling of race conditions (line 81)
- ❌ Test endpoint returns `{"status": "error", "error": str(e)}` - too generic (line 249)
- ❌ No distinction between network timeout, auth failure, invalid endpoint
- ❌ Usage breakdown queries (lines 340-374) can be slow with no pagination

**Missing Error Cases:**
- Provider deletion while tasks are running using it
- Model fetch fails with non-JSON response
- Concurrent provider activation

---

### 8. `dashboard.py` (149 lines)

**Strengths:**
- ✅ Good aggregation queries
- ✅ Proper NULL coalescing (line 51-52)

**Issues:**
- ❌ No error handling around aggregate queries
- ❌ No pagination on events endpoint (fixed limit 50)
- ❌ No validation on date ranges for metrics

**Missing Error Cases:**
- Aggregate queries timeout on large datasets
- Database connection loss mid-query

---

### 9. `users.py` (117 lines)

**Strengths:**
- ✅ Excellent role validation (lines 60-62, 90-92)
- ✅ Good authorization (require_roles dependency)
- ✅ Proper 409 for duplicate usernames

**Issues:**
- ❌ Self-deletion check (line 107) but user could disable themselves
- ❌ No validation on email format
- ❌ Password change not implemented

**Missing Error Cases:**
- Role downgrade of last admin user
- Deactivating user with active tasks

---

### 10. `websocket.py` (143 lines)

**Strengths:**
- ✅ JWT auth support
- ✅ Channel-based pub/sub
- ✅ Connection cleanup

**Issues:**
- ❌ JSON parsing (line 118) not wrapped in try-except
- ❌ Anonymous connections allowed (line 109) - security risk
- ❌ No max connection limit per user
- ❌ No message rate limiting

**Missing Error Cases:**
- JSON parse errors
- Send failures during broadcast
- Channel subscription flooding

---

### 11. `console.py` (174 lines)

**Strengths:**
- ✅ Query parameter validation with bounds (line 25)
- ✅ Good filtering logic

**Issues:**
- ❌ Log file read (line 34) not wrapped in try-except
- ❌ JSON parsing (line 37) can fail silently
- ❌ Filter params not sanitized (SQL injection risk if used in raw queries)
- ❌ Search param (line 28) not escaped for regex if used in pattern matching

**Missing Error Cases:**
- Log file missing or inaccessible
- Malformed JSON lines in log file
- Log file too large (no size check before read)

---

## Recommendations

### Immediate Actions (Critical)

1. **Add Database Error Handling Middleware**
   ```python
   # backend/middleware/error_handler.py
   @app.exception_handler(SQLAlchemyError)
   async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
       logger.error(f"Database error: {exc}", exc_info=True)
       return JSONResponse(
           status_code=503,
           content={"detail": "Database service unavailable. Please try again later."}
       )
   ```

2. **Add Authorization Checks for Resource Access**
   ```python
   # projects.py:66
   @router.get("/{project_id}", response_model=ProjectResponse)
   async def get_project(
       project_id: str,
       session: AsyncSession = Depends(get_session),
       user: User = Depends(get_current_user),
   ):
       result = await session.execute(
           select(Project).where(
               Project.id == project_id,
               Project.owner_id == user.id  # ADD THIS
           )
       )
       project = result.scalar_one_or_none()
       if not project:
           raise HTTPException(404, "Project not found or access denied")
       return project
   ```

3. **Add Input Validation for Enums**
   ```python
   # tasks.py
   from storage.models import TaskStatus, TaskType
   
   @router.get("")
   async def list_tasks(
       project_id: str | None = None,
       status: str | None = None,
       session: AsyncSession = Depends(get_session),
       user: User = Depends(get_current_user),
   ):
       # Validate status is a valid enum
       if status and status not in {s.value for s in TaskStatus}:
           raise HTTPException(400, f"Invalid status: {status}")
       # ... rest of endpoint
   ```

4. **Add LLM Provider Error Classification**
   ```python
   # llm.py
   from httpx import TimeoutException, ConnectError
   
   @router.post("/providers/{provider_id}/test")
   async def test_provider(...):
       try:
           models = await test_llm.list_models()
           await test_llm.close()
           return {"status": "ok", "models": [...]}
       except TimeoutException:
           return {"status": "error", "error": "Connection timeout", "code": "TIMEOUT"}
       except ConnectError:
           return {"status": "error", "error": "Cannot connect to provider", "code": "CONNECTION_FAILED"}
       except Exception as e:
           return {"status": "error", "error": "Provider test failed", "code": "UNKNOWN", "details": str(e)}
   ```

### Short-term Improvements (High Priority)

5. **Standardize Error Response Format**
   ```python
   # backend/errors.py
   from pydantic import BaseModel
   
   class ErrorResponse(BaseModel):
       error: str
       code: str
       details: dict | None = None
       trace_id: str | None = None
   
   # Usage in routes:
   raise HTTPException(
       status_code=400,
       detail=ErrorResponse(
           error="Invalid action",
           code="INVALID_ACTION",
           details={"action": req.action, "allowed": ["delete", "archive", "unarchive"]}
       ).dict()
   )
   ```

6. **Add Pydantic Enums for String Constants**
   ```python
   # backend/routes/conversations.py
   from enum import Enum
   
   class BatchAction(str, Enum):
       DELETE = "delete"
       ARCHIVE = "archive"
       UNARCHIVE = "unarchive"
   
   class BatchRequest(BaseModel):
       action: BatchAction  # Changed from str
       ids: list[str]
   ```

7. **Update Background Task Error Handling**
   ```python
   # conversations.py:329
   async def _dispatch_created_task(task_id: str):
       try:
           # ... existing logic ...
       except Exception as e:
           logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
           # UPDATE TASK STATUS
           async with _db() as s:
               result = await s.execute(select(Task).where(Task.id == task_id))
               task = result.scalar_one_or_none()
               if task:
                   task.status = "failed"
                   task.error_message = f"Dispatch failed: {str(e)}"
                   await s.commit()
   ```

8. **Add Retry-After Header to Rate Limit Response**
   ```python
   # main.py:100
   @app.exception_handler(RateLimitExceeded)
   async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
       return JSONResponse(
           status_code=429,
           content={
               "detail": "Rate limit exceeded. Please try again later.",
               "limit": "200/minute",
               "retry_after": 60
           },
           headers={"Retry-After": "60"}
       )
   ```

### Medium-term Enhancements

9. **Add Request Tracing**
   ```python
   # backend/middleware/tracing.py
   import uuid
   from contextvars import ContextVar
   
   trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
   
   @app.middleware("http")
   async def add_trace_id(request: Request, call_next):
       trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
       trace_id_var.set(trace_id)
       response = await call_next(request)
       response.headers["X-Trace-ID"] = trace_id
       return response
   ```

10. **Add Comprehensive Logging**
    ```python
    # Before each route handler
    logger.info(f"Request: {request.method} {request.url.path}", extra={
        "user_id": user.id,
        "trace_id": trace_id_var.get()
    })
    ```

11. **Add Content Length Validation**
    ```python
    # conversations.py:39
    class MessageSend(BaseModel):
        content: str
        
        @validator('content')
        def validate_content_length(cls, v):
            if len(v) > 50000:  # 50KB max
                raise ValueError("Message content too long (max 50KB)")
            if len(v.strip()) == 0:
                raise ValueError("Message content cannot be empty")
            return v
    ```

12. **Add WebSocket Message Validation**
    ```python
    # websocket.py:117
    try:
        data = await websocket.receive_text()
        try:
            msg = json.loads(data) if data.startswith("{") else {"text": data}
        except json.JSONDecodeError as e:
            await websocket.send_json({
                "type": "error",
                "error": "Invalid JSON message",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            continue
    ```

---

## Validation Matrix

| Route | Pydantic Validation | Query Param Validation | Authorization | DB Error Handling | External Service Errors |
|-------|---------------------|------------------------|---------------|-------------------|------------------------|
| `auth.py` | ✅ | N/A | ✅ | ❌ | N/A |
| `conversations.py` | ✅ | ❌ | ⚠️ Partial | ❌ | ❌ |
| `tasks.py` | ✅ | ❌ | ⚠️ Missing dispatch check | ❌ | N/A |
| `projects.py` | ✅ | N/A | ❌ Critical | ❌ | N/A |
| `workers.py` | N/A | N/A | ✅ | ❌ | N/A |
| `approvals.py` | ⚠️ String not enum | N/A | ⚠️ No approver check | ❌ | ❌ |
| `llm.py` | ⚠️ No range validation | ❌ | ✅ | ❌ | ⚠️ Generic errors |
| `dashboard.py` | N/A | ✅ | ✅ | ❌ | N/A |
| `users.py` | ✅ | N/A | ✅ | ❌ | N/A |
| `websocket.py` | ❌ | N/A | ⚠️ Anonymous allowed | N/A | ❌ |
| `console.py` | N/A | ⚠️ Partial | ✅ | ❌ | N/A |

---

## Error Message Quality Assessment

### ✅ Good Examples
- `"Invalid credentials"` - Clear, secure (doesn't reveal if username or password was wrong)
- `"Project not found"` - Simple, user-friendly
- `"Task cannot be dispatched from status: {status}"` - Informative

### ❌ Poor Examples
- `"Invalid action"` - Too vague, should list valid actions
- `"Approval already {status}"` - Exposes internal state
- `"Could not validate credentials"` - Too technical
- Generic `str(e)` error messages from external services

### Recommendations
- Add error codes (e.g., `INVALID_ACTION`, `RESOURCE_NOT_FOUND`)
- Include actionable information where possible
- Never expose stack traces or internal implementation details
- Use consistent format across all endpoints

---

## Security Considerations

1. **Information Disclosure**
   - Database errors expose table/column names
   - Stack traces in development mode leak file paths
   - Error messages sometimes expose internal state

2. **Authorization Gaps**
   - Projects endpoint returns any project without ownership check
   - Tasks endpoint doesn't verify dispatch permissions
   - Approval endpoint doesn't verify approver role

3. **Input Validation**
   - Query params not validated against enum values
   - No length limits on text fields
   - WebSocket messages not validated

4. **Rate Limiting**
   - Only global rate limit, no per-endpoint limits
   - No rate limiting on expensive operations (bulk queries, LLM tests)
   - WebSocket connections unlimited per user

---

## Testing Recommendations

### Unit Tests Needed
- [ ] Invalid enum values in query params
- [ ] Database connection failures
- [ ] Concurrent resource access
- [ ] Oversized request payloads
- [ ] Invalid JSON in request bodies
- [ ] NULL/None handling in all fields

### Integration Tests Needed
- [ ] Authorization checks for all protected endpoints
- [ ] Background task failure recovery
- [ ] Rate limit exhaustion
- [ ] WebSocket connection limits
- [ ] LLM provider failures

### Load Tests Needed
- [ ] Large pagination requests
- [ ] Concurrent task dispatches
- [ ] WebSocket broadcast to many clients
- [ ] Aggregate query performance

---

## Summary Statistics

- **Total Routes Audited:** 12 modules, ~60 endpoints
- **Critical Issues:** 4
- **High Priority Issues:** 4
- **Medium Priority Issues:** 4
- **Routes with Good Error Handling:** 3/12 (auth, users, llm - partial)
- **Routes Needing Immediate Attention:** 5/12 (projects, tasks, conversations, websocket, console)
- **Overall Error Handling Grade:** C+ (Baseline is good, but critical gaps exist)

---

## Next Steps

1. **Implement database error handling middleware** (1-2 hours)
2. **Fix authorization gaps in projects.py** (30 minutes)
3. **Add enum validation for query parameters** (2-3 hours)
4. **Standardize error response format** (1-2 hours)
5. **Add comprehensive integration tests** (4-6 hours)
6. **Document error codes and responses** (2 hours)

**Estimated Total Effort:** 11-16 hours to address all critical and high-priority issues.

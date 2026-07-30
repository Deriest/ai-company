# Error Handling Implementation Guide

This guide shows how to integrate the error handling improvements into the AIC Platform backend.

---

## Step 1: Register Error Handlers in main.py

Add these imports and registrations to `backend/main.py`:

```python
# Add to imports section (after line 19)
from backend.middleware.error_handler import (
    database_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
    trace_id_middleware,
)
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

# Add after app creation (after line 97)
# Register error handlers
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Add trace ID middleware
app.middleware("http")(trace_id_middleware)
```

---

## Step 2: Update Rate Limit Handler

Replace the existing rate limit handler (lines 100-105) with:

```python
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded. Please try again later.",
            "code": "RATE_LIMIT_EXCEEDED",
            "details": {
                "limit": "200/minute",
                "retry_after_seconds": 60,
            }
        },
        headers={"Retry-After": "60"},
    )
```

---

## Step 3: Fix Critical Authorization Issues

### projects.py

**Line 66-76:** Add ownership check to `get_project`:

```python
@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id  # ADD THIS LINE
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project
```

**Line 79-100:** Add ownership check to `get_project_tasks`:

```python
@router.get("/{project_id}/tasks")
async def get_project_tasks(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # ADD: Verify project ownership first
    project_result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Now fetch tasks
    result = await session.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    return [...]  # existing return
```

---

## Step 4: Add Input Validation to Task Routes

### tasks.py

**Add import at top:**

```python
from backend.validation import validate_enum_value
```

**Line 41-52:** Add validation to `list_tasks`:

```python
@router.get("")
async def list_tasks(
    project_id: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # ADD: Validate status enum
    validate_enum_value(status, TaskStatus, "status")
    
    # ADD: If project_id provided, verify access
    if project_id:
        proj_result = await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == user.id
            )
        )
        if not proj_result.scalar_one_or_none():
            raise HTTPException(404, "Project not found")
    
    # ... rest of existing logic
```

**Line 136-153:** Add authorization to `dispatch_task`:

```python
@router.post("/{task_id}/dispatch")
async def dispatch_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    # ADD: Verify user owns the project
    project_result = await session.execute(
        select(Project).where(
            Project.id == task.project_id,
            Project.owner_id == user.id
        )
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(404, "Task not found or access denied")

    if task.status not in ("created", "blocked"):
        raise HTTPException(400, f"Task cannot be dispatched from status: {task.status}")

    # ... rest of existing logic
```

---

## Step 5: Fix Conversation Routes

### conversations.py

**Add imports at top:**

```python
from backend.validation import BatchAction
from pydantic import validator
```

**Line 34-36:** Replace BatchRequest with:

```python
class BatchRequest(BaseModel):
    action: BatchAction  # Changed from str
    ids: list[str]
```

**Line 39-41:** Replace MessageSend with:

```python
class MessageSend(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        if len(v) > 50000:
            raise ValueError("Message content too long (max 50KB)")
        return v.strip()
```

**Line 82-111:** Remove manual action validation (now handled by enum):

```python
@router.post("/batch")
async def batch_conversations(
    req: BatchRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # REMOVE: if req.action not in ("delete", "archive", "unarchive"):
    #             raise HTTPException(400, "Invalid action")
    # Enum validation happens automatically
    
    # ... rest of existing logic
    
    if req.action == BatchAction.DELETE:
        # ... delete logic
    else:
        target_status = "archived" if req.action == BatchAction.ARCHIVE else "active"
        # ... archive logic
```

**Line 222-244:** Add ownership check to `get_messages`:

```python
@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # ADD: Verify conversation ownership first
    conv_result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    
    # Now fetch messages
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [...]  # existing return
```

**Line 329-348:** Update background task error handling:

```python
async def _dispatch_created_task(task_id: str):
    """Background: dispatch a newly created task through the worker pipeline."""
    import asyncio as _aio
    await _aio.sleep(2)
    try:
        # ... existing logic ...
    except Exception as e:
        logger.error(f"Dispatch bg failed for {task_id}: {e}", exc_info=True)
        
        # ADD: Update task status on failure
        try:
            async with _db() as s:
                result = await s.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = f"Dispatch failed: {str(e)[:500]}"
                    await s.commit()
        except Exception as update_err:
            logger.error(f"Failed to update task status: {update_err}")
```

---

## Step 6: Improve Approvals Validation

### approvals.py

**Add imports:**

```python
from backend.validation import ApprovalDecisionType
```

**Line 15-17:** Replace ApprovalDecision with:

```python
class ApprovalDecision(BaseModel):
    decision: ApprovalDecisionType  # Changed from str
    reason: str = ""
```

**Line 86:** Update decision conversion:

```python
decision = ApprovalStatus.APPROVED if req.decision == ApprovalDecisionType.APPROVED else ApprovalStatus.REJECTED
```

---

## Step 7: Enhance LLM Provider Error Handling

### llm.py

**Add imports:**

```python
import httpx
```

**Line 215-249:** Replace test_provider with:

```python
@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Test provider connection by listing models."""
    result = await session.execute(
        select(LLMProviderConfig).where(LLMProviderConfig.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Provider not found")

    cfg = ProviderConfig(
        name=provider.name,
        base_url=provider.base_url,
        api_key=provider.api_key,
        models=provider.models or {},
    )
    from llm.provider import LLMProvider
    test_llm = LLMProvider(cfg)

    try:
        models = await test_llm.list_models()
        await test_llm.close()
        return {
            "status": "ok",
            "models": [m.get("id", "") for m in models[:20]],
            "count": len(models),
        }
    except httpx.TimeoutException:
        await test_llm.close()
        return {
            "status": "error",
            "error": "Connection to provider timed out",
            "code": "TIMEOUT",
        }
    except httpx.ConnectError:
        await test_llm.close()
        return {
            "status": "error",
            "error": "Cannot connect to provider",
            "code": "CONNECTION_FAILED",
        }
    except httpx.HTTPStatusError as e:
        await test_llm.close()
        if e.response.status_code == 401:
            error = "Invalid API key"
            code = "AUTH_FAILED"
        elif e.response.status_code == 403:
            error = "Access forbidden"
            code = "FORBIDDEN"
        else:
            error = f"HTTP {e.response.status_code}"
            code = "HTTP_ERROR"
        return {"status": "error", "error": error, "code": code}
    except Exception as e:
        await test_llm.close()
        return {
            "status": "error",
            "error": "Provider test failed",
            "code": "UNKNOWN",
            "details": type(e).__name__,
        }
```

---

## Step 8: Fix WebSocket JSON Parsing

### websocket.py

**Line 115-119:** Wrap JSON parsing in try-except:

```python
try:
    while True:
        data = await websocket.receive_text()
        try:
            msg = json.loads(data) if data.startswith("{") else {"text": data}
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "error": "Invalid JSON message",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            continue
        
        # ... rest of handler
except WebSocketDisconnect:
    # ... existing cleanup
```

---

## Step 9: Add Console Log Safety

### console.py

**Line 32-58:** Wrap file operations in try-except:

```python
@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: str | None = None,
    component: str | None = None,
    search: str | None = None,
    user: User = Depends(get_current_user),
):
    """Get backend logs with optional filtering."""
    lines = []
    
    try:
        if LOG_FILE.exists():
            # ADD: Check file size before reading
            file_size = LOG_FILE.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                raise HTTPException(400, "Log file too large to read via API")
            
            raw_lines = LOG_FILE.read_text().splitlines()
            for line in raw_lines[-limit * 2:]:
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    data = {"message": line, "level": "info", "component": "raw"}
                
                # ... existing filter logic ...
                lines.append({...})
    except PermissionError:
        raise HTTPException(403, "Cannot access log file")
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        raise HTTPException(500, "Failed to read logs")
    
    return {"logs": lines[-limit:], "total": len(lines)}
```

---

## Step 10: Update HTTP Status Codes for Creates

Add `status_code=201` to all POST endpoints that create resources:

```python
# auth.py:41
@router.post("/register", response_model=TokenResponse, status_code=201)

# projects.py:44
@router.post("", response_model=ProjectResponse, status_code=201)

# tasks.py:72
@router.post("", response_model=TaskResponse, status_code=201)

# conversations.py:114
@router.post("", status_code=201)

# users.py:48
@router.post("", status_code=201)

# llm.py:71
@router.post("/providers", response_model=ProviderResponse, status_code=201)
```

---

## Testing Checklist

After implementing these changes, test:

- [ ] Database connection loss during query
- [ ] Invalid enum values in query params (`?status=invalid`)
- [ ] Unauthorized access to other users' resources
- [ ] Message content > 50KB
- [ ] Empty message content
- [ ] Invalid JSON in WebSocket messages
- [ ] LLM provider timeout/connection failures
- [ ] Concurrent task dispatch
- [ ] Background task failures update task status
- [ ] Rate limit returns Retry-After header
- [ ] All errors include trace_id in response
- [ ] 201 status for create operations
- [ ] Large log file access (> 100MB)

---

## Rollback Plan

If issues occur after deployment:

1. **Disable error middleware:** Comment out the middleware registrations in `main.py`
2. **Revert validation imports:** Remove `from backend.validation import ...` 
3. **Keep trace ID middleware:** This is safe and helpful for debugging
4. **Database error handler is safe:** Can be kept enabled
5. **Validation changes:** Revert Pydantic model changes if causing issues

---

## Performance Considerations

- **Trace ID middleware:** Negligible overhead (~0.1ms per request)
- **Database error handler:** No overhead when no errors occur
- **Validation helpers:** Add ~0.5-1ms for enum/range checks
- **Authorization checks:** Add one extra DB query per request (consider caching if needed)

---

## Monitoring

After deployment, monitor:

- Error rate by error code (track `DUPLICATE_RESOURCE`, `DATABASE_UNAVAILABLE`, etc.)
- Rate limit hits (should see `RATE_LIMIT_EXCEEDED` in logs)
- Authorization failures (track 404s on resource endpoints)
- Background task failure rate
- Trace IDs in error logs for debugging

Use the trace_id to correlate errors across logs, events, and user reports.

# Error Handling Quick Reference

**For AIC Platform Backend Developers**

---

## Common Patterns

### ✅ Always Check Resource Ownership

```python
# ❌ BAD - Returns any resource
result = await session.execute(select(Project).where(Project.id == project_id))
project = result.scalar_one_or_none()

# ✅ GOOD - Only returns user's resources
result = await session.execute(
    select(Project).where(
        Project.id == project_id,
        Project.owner_id == user.id
    )
)
project = result.scalar_one_or_none()
```

### ✅ Validate Enum Query Params

```python
# ❌ BAD - Accepts any string
status: str | None = None

# ✅ GOOD - Validates against enum
from backend.validation import validate_enum_value
status: str | None = None
validate_enum_value(status, TaskStatus, "status")
```

### ✅ Use Enums in Pydantic Models

```python
# ❌ BAD - String with manual validation
class Request(BaseModel):
    action: str

@router.post("/batch")
async def batch(req: Request):
    if req.action not in ["delete", "archive"]:
        raise HTTPException(400, "Invalid action")

# ✅ GOOD - Enum with automatic validation
from backend.validation import BatchAction

class Request(BaseModel):
    action: BatchAction

@router.post("/batch")
async def batch(req: Request):
    # No manual validation needed
    if req.action == BatchAction.DELETE:
        ...
```

### ✅ Validate String Length

```python
# ❌ BAD - No length limit
class MessageSend(BaseModel):
    content: str

# ✅ GOOD - With length validation
from pydantic import validator

class MessageSend(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        if len(v) > 50000:
            raise ValueError("Content too long (max 50KB)")
        return v.strip()
```

### ✅ Classify External Service Errors

```python
# ❌ BAD - Generic error
try:
    result = await external_service.call()
except Exception as e:
    return {"status": "error", "error": str(e)}

# ✅ GOOD - Classified errors
import httpx

try:
    result = await external_service.call()
except httpx.TimeoutException:
    return {"status": "error", "error": "Timeout", "code": "TIMEOUT"}
except httpx.ConnectError:
    return {"status": "error", "error": "Connection failed", "code": "CONNECTION_FAILED"}
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        return {"status": "error", "error": "Auth failed", "code": "AUTH_FAILED"}
    return {"status": "error", "error": f"HTTP {e.response.status_code}", "code": "HTTP_ERROR"}
```

### ✅ Handle Background Task Failures

```python
# ❌ BAD - Failure leaves task in limbo
async def background_task(task_id: str):
    try:
        await execute_task(task_id)
    except Exception as e:
        logger.error(f"Task failed: {e}")

# ✅ GOOD - Updates task status on failure
async def background_task(task_id: str):
    try:
        await execute_task(task_id)
    except Exception as e:
        logger.error(f"Task failed: {e}")
        try:
            async with db() as session:
                task = await session.get(Task, task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(e)[:500]
                    await session.commit()
        except Exception as update_err:
            logger.error(f"Failed to update task: {update_err}")
```

### ✅ Return Proper Status Codes

```python
# ❌ BAD - Returns 200 for creates
@router.post("/projects")
async def create_project(req: ProjectCreate):
    project = Project(...)
    session.add(project)
    await session.commit()
    return project  # Returns 200

# ✅ GOOD - Returns 201 for creates
@router.post("/projects", status_code=201)
async def create_project(req: ProjectCreate):
    project = Project(...)
    session.add(project)
    await session.commit()
    return project  # Returns 201
```

---

## HTTP Status Code Guide

| Code | When to Use | Example |
|------|-------------|---------|
| **200** | Successful GET, PUT, DELETE | Get user profile |
| **201** | Successful POST create | Create project |
| **400** | Invalid input, bad request | Invalid enum value |
| **401** | Not authenticated | Missing/invalid token |
| **403** | Not authorized | Insufficient role |
| **404** | Resource not found | Project doesn't exist |
| **409** | Resource conflict | Duplicate username |
| **422** | Validation failed | Pydantic validation error |
| **429** | Rate limit exceeded | Too many requests |
| **500** | Unexpected server error | Unhandled exception |
| **502** | External service error | LLM provider unreachable |
| **503** | Service unavailable | Database down |

---

## Error Response Format

All errors should follow this structure:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "details": {
    "field": "additional context",
    "provided": "what user sent",
    "expected": "what we expected"
  },
  "trace_id": "uuid-for-debugging"
}
```

### Standard Error Codes

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `VALIDATION_ERROR` | Pydantic validation failed | 422 |
| `INVALID_ENUM` | Enum value not in allowed set | 400 |
| `INVALID_LENGTH` | String too long/short | 400 |
| `INVALID_RANGE` | Number out of range | 400 |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist | 404 |
| `DUPLICATE_RESOURCE` | Unique constraint violation | 409 |
| `INVALID_REFERENCE` | Foreign key violation | 400 |
| `CONSTRAINT_VIOLATION` | Other DB constraint | 400 |
| `DATABASE_UNAVAILABLE` | DB connection failed | 503 |
| `DATABASE_ERROR` | Other DB error | 500 |
| `AUTH_FAILED` | Authentication failed | 401 |
| `FORBIDDEN` | Authorization failed | 403 |
| `TIMEOUT` | External service timeout | 502 |
| `CONNECTION_FAILED` | Cannot connect to service | 502 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `INTERNAL_ERROR` | Unexpected error | 500 |

---

## Validation Helpers

### Import

```python
from backend.validation import (
    validate_enum_value,
    validate_positive_integer,
    validate_resource_exists,
    validate_resource_ownership,
    validate_string_length,
    BatchAction,
    ApprovalDecisionType,
)
```

### Usage

```python
# Validate enum
validate_enum_value(status, TaskStatus, "status")

# Validate positive integer with max
validate_positive_integer(limit, "limit", max_value=1000)

# Validate resource exists
project = await session.get(Project, project_id)
validate_resource_exists(project, "Project", project_id)

# Validate ownership
validate_resource_ownership(project, user.id, "owner_id", "Project")

# Validate string length
validate_string_length(content, "content", min_length=1, max_length=50000)
```

---

## Common Mistakes

### ❌ Don't Return Internal Errors

```python
# BAD
raise HTTPException(500, str(exception))

# GOOD
logger.error(f"Internal error: {exception}", exc_info=True)
raise HTTPException(500, "An unexpected error occurred")
```

### ❌ Don't Expose Internal State

```python
# BAD
raise HTTPException(400, f"Approval already {approval.status}")

# GOOD
raise HTTPException(400, {
    "error": "Approval has already been decided",
    "code": "APPROVAL_ALREADY_DECIDED"
})
```

### ❌ Don't Use 404 for Authorization

```python
# BAD - Reveals resource exists
if project.owner_id != user.id:
    raise HTTPException(403, "Access denied")

# GOOD - Security through obscurity
if project.owner_id != user.id:
    raise HTTPException(404, "Project not found")
```

### ❌ Don't Let DB Errors Bubble Up

```python
# BAD - No error handling
result = await session.execute(query)
# IntegrityError, OperationalError, etc. bubble up as 500

# GOOD - Middleware catches all SQLAlchemy errors
# (Already handled by error_handler.py middleware)
```

---

## Debugging with Trace IDs

Every error response includes a `trace_id`. Use it to find the error in logs:

```bash
# Search logs for specific trace_id
grep "trace_id: abc-123-def" /tmp/aic-backend.log

# Or use the console API
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/console/logs?search=abc-123-def"
```

Users can provide the trace_id when reporting issues:
> "I got an error with trace_id: abc-123-def"

---

## Testing Checklist

When adding a new endpoint, test:

- [ ] ✅ Valid input returns correct status code (200/201)
- [ ] ✅ Missing auth returns 401
- [ ] ✅ Wrong user returns 404 (not 403)
- [ ] ✅ Invalid enum returns 400 with valid values listed
- [ ] ✅ Out of range values return 400
- [ ] ✅ Oversized input returns 422
- [ ] ✅ Resource not found returns 404
- [ ] ✅ Duplicate create returns 409
- [ ] ✅ All errors include trace_id
- [ ] ✅ No stack traces in error responses

---

## Resources

- **Full Audit Report:** `docs/ERROR_HANDLING_AUDIT.md`
- **Implementation Guide:** `docs/ERROR_HANDLING_IMPLEMENTATION.md`
- **Code Examples:** `docs/error_handling_examples.py`
- **Implementation Checklist:** `docs/ERROR_HANDLING_CHECKLIST.md`
- **Middleware:** `backend/middleware/error_handler.py`
- **Validation Utils:** `backend/validation.py`

---

## Questions?

- Check the full audit report for detailed analysis
- Review error_handling_examples.py for reference implementations
- Follow the implementation guide for step-by-step instructions
- Use the checklist to track progress

---

**Last Updated:** 2026-07-21  
**Version:** 1.0  
**Maintainer:** AIC Platform Team

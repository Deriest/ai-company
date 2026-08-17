# API Implementation Plan - Commercial-Grade Completeness

**Based on:** API Audit Report (2026-07-21)  
**Target:** Achieve commercial-grade API completeness for AIC Platform  
**Timeline:** 4-5 weeks (1 developer full-time)

---

## Phase 1: Critical Foundation (Week 1-2)

### 1.1 Pagination Infrastructure (3 days)

**Goal:** Implement reusable pagination for all list endpoints

**Implementation:**
```python
# backend/utils/pagination.py
from typing import TypeVar, Generic, List
from pydantic import BaseModel

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: dict

def paginate(query, offset: int = 0, limit: int = 50):
    """Apply pagination to SQLAlchemy query"""
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "data": items,
        "pagination": {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total
        }
    }
```

**Endpoints to Update:**
- `/api/projects` (GET)
- `/api/tasks` (GET)
- `/api/workers` (GET)
- `/api/approvals` (GET)
- `/api/conversations` (GET)
- `/api/conversations/{id}/messages` (GET)
- `/api/dashboard/events` (GET)
- `/api/dashboard/audit` (GET)

**Testing:** Add pagination tests for each endpoint

---

### 1.2 Projects CRUD Completion (2 days)

**New Endpoints:**

#### Update Project
```python
@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update project metadata"""
```

**Request Model:**
```python
class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repo_path: str | None = None
    status: str | None = None  # active, archived, paused
```

#### Delete/Archive Project
```python
@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    permanent: bool = False,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Delete or archive project. If permanent=false, archives instead."""
```

**Testing:** CRUD lifecycle tests, validation tests

---

### 1.3 Tasks CRUD Completion (2 days)

**New Endpoints:**

#### Update Task
```python
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    req: TaskUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update task metadata"""
```

**Request Model:**
```python
class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: int | None = None  # 0-3
    worker_type: str | None = None
    milestone_id: str | None = None
    approval_required: bool | None = None
```

#### Delete Task
```python
@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Delete task (only if not started)"""
```

**Testing:** Update validation, cascade delete checks

---

### 1.4 Milestones Full CRUD (3 days)

**New Route File:** `backend/routes/milestones.py`

**Endpoints:**

```python
@router.post("", response_model=MilestoneResponse)
async def create_milestone(req: MilestoneCreate, ...):
    """Create milestone"""

@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(milestone_id: str, ...):
    """Get milestone detail"""

@router.put("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(milestone_id: str, req: MilestoneUpdate, ...):
    """Update milestone"""

@router.delete("/{milestone_id}")
async def delete_milestone(milestone_id: str, ...):
    """Delete milestone"""

@router.get("/{milestone_id}/tasks")
async def get_milestone_tasks(milestone_id: str, ...):
    """Get tasks in milestone"""

@router.post("/{milestone_id}/tasks/{task_id}")
async def add_task_to_milestone(milestone_id: str, task_id: str, ...):
    """Add task to milestone"""

@router.delete("/{milestone_id}/tasks/{task_id}")
async def remove_task_from_milestone(milestone_id: str, task_id: str, ...):
    """Remove task from milestone"""
```

**Models:**
```python
class MilestoneCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    due_date: datetime | None = None

class MilestoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None  # planned, active, done
    due_date: datetime | None = None

class MilestoneResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    status: str
    due_date: str | None
    task_count: int
    completed_tasks: int
    created_at: str
```

**Register in main.py:**
```python
from backend.routes import milestones
app.include_router(milestones.router, prefix="/api/milestones", tags=["milestones"])
```

**Testing:** Full CRUD lifecycle, task association tests

---

### 1.5 Workers CRUD Completion (2 days)

**New Endpoints:**

#### Update Worker
```python
@router.put("/{worker_id}")
async def update_worker(
    worker_id: str,
    req: WorkerUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update worker configuration"""
```

**Request Model:**
```python
class WorkerUpdate(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None
    config: dict | None = None
    status: str | None = None
```

#### Delete Worker
```python
@router.delete("/{worker_id}")
async def delete_worker(
    worker_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Delete worker (only if not working)"""
```

#### Manual Registration
```python
@router.post("")
async def register_worker(
    req: WorkerCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Manually register a worker"""
```

**Testing:** Config update tests, deletion constraint tests

---

### 1.6 Basic Filtering (2 days)

**Add filtering utilities:**
```python
# backend/utils/filters.py
from sqlalchemy import and_, or_

def apply_filters(query, model, filters: dict):
    """Apply query parameter filters to SQLAlchemy query"""
    conditions = []
    
    if "status" in filters:
        conditions.append(model.status == filters["status"])
    
    if "created_after" in filters:
        conditions.append(model.created_at >= filters["created_after"])
    
    if "created_before" in filters:
        conditions.append(model.created_at <= filters["created_before"])
    
    # ... more filters
    
    if conditions:
        query = query.where(and_(*conditions))
    
    return query
```

**Endpoints to Update:**
- Projects: filter by status, owner_id, created_after/before
- Tasks: filter by status, priority, project_id, milestone_id, worker_type, created_by
- Workers: filter by status, type
- Approvals: filter by task_id, approver_id, requested_by

---

## Phase 2: Advanced Features (Week 3)

### 2.1 Bulk Operations (4 days)

**Implementation Pattern:**
```python
class BatchRequest(BaseModel):
    action: str
    ids: list[str]
    params: dict = {}

@router.post("/batch")
async def batch_operation(
    req: BatchRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Execute bulk operation on multiple entities"""
    if req.action == "delete":
        # ... delete logic
    elif req.action == "update_status":
        # ... status update logic
    # ...
```

**Endpoints to Add:**
- `POST /api/projects/batch` (archive, delete, update status)
- `POST /api/tasks/batch` (cancel, reassign, update priority, update status)
- `POST /api/workers/batch` (restart, update config, enable/disable)
- `POST /api/approvals/batch` (approve, reject)

**Supported Actions:**
- Projects: archive, restore, delete
- Tasks: cancel, change_priority, reassign, retry
- Workers: restart, enable, disable, update_config
- Approvals: approve, reject

**Testing:** Batch validation, partial failure handling, transaction rollback

---

### 2.2 Search Functionality (2 days)

**Implementation:**
```python
# For SQLite - use LIKE queries
@router.get("")
async def list_projects(
    q: str | None = None,  # search query
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    query = select(Project)
    
    if q:
        search_pattern = f"%{q}%"
        query = query.where(
            or_(
                Project.name.ilike(search_pattern),
                Project.description.ilike(search_pattern),
            )
        )
    
    # ... pagination, etc
```

**Endpoints to Update:**
- Projects: search by name, description
- Tasks: search by title, description
- Workers: search by name, type
- Conversations: search by title

**Future Enhancement:** Migrate to SQLite FTS5 for better performance

---

### 2.3 Sorting (1 day)

**Implementation:**
```python
# backend/utils/sorting.py
def apply_sorting(query, model, sort: str | None, order: str = "desc"):
    """Apply sorting to query"""
    if not sort:
        return query.order_by(model.created_at.desc())
    
    valid_fields = ["name", "created_at", "updated_at", "status", "priority"]
    
    if sort not in valid_fields:
        return query
    
    field = getattr(model, sort)
    
    if order == "asc":
        return query.order_by(field.asc())
    else:
        return query.order_by(field.desc())
```

**Endpoints to Update:**
- All list endpoints with `?sort=...&order=asc|desc`

---

### 2.4 Task Management Enhancements (2 days)

**New Endpoints:**

```python
@router.post("/{task_id}/retry")
async def retry_task(...):
    """Retry a failed task"""

@router.put("/{task_id}/priority")
async def update_task_priority(...):
    """Update task priority"""

@router.post("/{task_id}/reassign")
async def reassign_task(
    task_id: str,
    req: TaskReassign,
    ...
):
    """Reassign task to different worker"""
```

**Models:**
```python
class TaskReassign(BaseModel):
    worker_type: str
    reason: str = ""
```

---

## Phase 3: Statistics & Analytics (Week 4)

### 3.1 Project Statistics (2 days)

**New Endpoint:**
```python
@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get project statistics"""
    # Task counts by status
    # Completion percentage
    # Average task duration
    # Worker distribution
    # Token usage
```

**Response:**
```json
{
  "tasks": {
    "total": 45,
    "completed": 30,
    "active": 10,
    "failed": 5,
    "completion_rate": 0.67
  },
  "milestones": {
    "total": 5,
    "completed": 2,
    "active": 3
  },
  "workers": {
    "by_type": {"backend": 15, "frontend": 20, "qa": 10}
  },
  "tokens": {
    "total": 1500000,
    "by_tier": {"thinker": 800000, "crafter": 700000}
  }
}
```

---

### 3.2 Worker Statistics (2 days)

**New Endpoint:**
```python
@router.get("/{worker_id}/stats")
async def get_worker_stats(
    worker_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get worker performance statistics"""
```

**Response:**
```json
{
  "total_leases": 120,
  "completed": 110,
  "failed": 10,
  "success_rate": 0.92,
  "avg_duration_seconds": 450,
  "total_tokens": 250000,
  "last_7_days": {
    "leases": 15,
    "success_rate": 0.93
  }
}
```

---

### 3.3 Task Timeline & Artifacts (1 day)

**New Endpoints:**
```python
@router.get("/{task_id}/timeline")
async def get_task_timeline(...):
    """Get task execution timeline with phase transitions"""

@router.get("/{task_id}/artifacts")
async def get_task_artifacts(...):
    """Get detailed artifact list"""

@router.post("/{task_id}/artifacts")
async def add_task_artifact(...):
    """Manually add artifact to task"""
```

---

### 3.4 Relation Expansion (2 days)

**Implementation:**
```python
@router.get("/{project_id}")
async def get_project(
    project_id: str,
    include: str | None = None,  # "tasks,milestones"
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = await session.get(Project, project_id)
    
    response = {...}
    
    if include:
        includes = include.split(",")
        
        if "tasks" in includes:
            tasks = await session.execute(
                select(Task).where(Task.project_id == project_id)
            )
            response["tasks"] = [...]
        
        if "milestones" in includes:
            milestones = await session.execute(
                select(Milestone).where(Milestone.project_id == project_id)
            )
            response["milestones"] = [...]
    
    return response
```

**Endpoints to Support:**
- Projects: include tasks, milestones
- Tasks: include project, worker, approvals, leases
- Milestones: include tasks
- Workers: include current_task, recent_leases

---

## Phase 4: Polish & Documentation (Week 5)

### 4.1 OpenAPI Documentation (2 days)

**Enhancements:**
- Add comprehensive docstrings to all endpoints
- Add request/response examples
- Document query parameters with `Query()` annotations
- Add error response models
- Generate client SDK (optional)

**Example:**
```python
@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        404: {"description": "Project not found"},
        403: {"description": "Access denied"}
    }
)
async def get_project(
    project_id: str = Path(..., description="Project UUID"),
    include: str | None = Query(None, description="Comma-separated relations to include (tasks, milestones)"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Get project detail by ID.
    
    Returns comprehensive project information including metadata,
    status, and optionally related tasks and milestones.
    """
```

---

### 4.2 API Testing Suite (2 days)

**Test Coverage:**
- CRUD lifecycle tests for all entities
- Pagination edge cases
- Filtering validation
- Sorting correctness
- Bulk operation transaction handling
- Search functionality
- Authorization checks
- Error handling (400, 401, 403, 404, 500)

**Framework:** pytest + httpx

---

### 4.3 Performance Optimization (2 days)

**Tasks:**
1. Add database indexes for filter columns
2. Implement eager loading to prevent N+1 queries
3. Add response caching for frequently accessed endpoints (worker registry, project list)
4. Profile slow queries and optimize
5. Add query result limits to prevent memory issues

**Index Migration:**
```sql
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
CREATE INDEX idx_tasks_milestone_id ON tasks(milestone_id);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_workers_status ON workers(status);
CREATE INDEX idx_workers_type ON workers(type);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_created_at ON events(created_at);
```

---

### 4.4 Security Hardening (1 day)

**Tasks:**
1. Add resource ownership checks (user can only access their projects/tasks)
2. Implement per-endpoint rate limiting
3. Add comprehensive audit logging for all mutations
4. Validate all input with Pydantic
5. Add CSRF protection for state-changing operations
6. Review and document authorization model

---

## Implementation Checklist

### Week 1-2: Foundation
- [ ] Pagination infrastructure
- [ ] Projects: PUT, DELETE
- [ ] Tasks: PUT, DELETE
- [ ] Milestones: Full CRUD (7 endpoints)
- [ ] Workers: PUT, DELETE, POST
- [ ] Basic filtering on all list endpoints

### Week 3: Advanced
- [ ] Bulk operations (4 endpoints)
- [ ] Search functionality (4 endpoints)
- [ ] Sorting support (all list endpoints)
- [ ] Task management (retry, reassign, priority)

### Week 4: Analytics
- [ ] Project statistics
- [ ] Worker statistics
- [ ] Task timeline & artifacts
- [ ] Relation expansion (include parameter)

### Week 5: Polish
- [ ] OpenAPI documentation
- [ ] Comprehensive test suite
- [ ] Performance optimization & indexes
- [ ] Security hardening

---

## Deliverables

1. **75+ new/updated endpoints** achieving commercial-grade completeness
2. **Comprehensive API documentation** with examples and error codes
3. **Full test coverage** for all CRUD operations and edge cases
4. **Performance benchmarks** demonstrating response times under load
5. **Security audit report** documenting authorization model
6. **Migration guide** for frontend to adopt new endpoints

---

## Success Criteria

- [ ] All entities support full CRUD operations
- [ ] All list endpoints support pagination, filtering, sorting
- [ ] Bulk operations available for common actions
- [ ] Search functionality for text fields
- [ ] Statistics endpoints for analytics
- [ ] Response times < 200ms for simple queries, < 1s for complex
- [ ] Test coverage > 80%
- [ ] Zero SQL injection or authorization vulnerabilities
- [ ] OpenAPI spec complete and accurate

---

**Plan Version:** 1.0  
**Last Updated:** 2026-07-21  
**Estimated Effort:** 140-200 hours (4-5 weeks)

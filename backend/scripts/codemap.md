# backend/scripts/

<!-- Fixer: Fill in this section with architectural understanding -->

## Responsibility

The `backend/scripts/` directory serves as an **administrative and operational utility** layer for the AIC Platform, housing ephemeral automation scripts for three primary purposes:

1. **Database Maintenance & Migration**: Executing ad-hoc data corrections and schema updates via direct SQLAlchemy ORM operations
2. **End-to-End Integration Testing**: Running complete system validation workflows against the running API surface
3. **Infrastructure Configuration**: Modifying runtime environment settings stored in configuration tables

These scripts function as **infrastructure tooling** external to the core application lifecycle, designed for DevOps operations, QA verification, and one-time corrective actions. They are categorized by maturity and permanence via subdirectories (`archive/` indicates retired or legacy utilities).

---

## Design Patterns

### 1. **Script-as-Entry-Point Pattern**
Both files use `asyncio.run(main())` / `asyncio.run(test())` as synchronous entry points that bootstrap async execution contexts. This follows Python's recommended pattern for standalone async scripts (PEP 565 compliance).

```python
asyncio.run(main())  # fix_url.py line 17
asyncio.run(test())  # e2e_final.py line 102
```

### 2. **Test Fixture Collection Pattern**
`e2e_final.py` implements a structured test result collection using tuples `(test_name, status, detail)` stored in a results list. This provides deterministic output formatting and pass/fail aggregation logic.

```python
results = []
results.append(("LOGIN", "PASS", ""))  # Test case registration
```

### 3. **Async HTTP Client Session Pattern**
Uses `httpx.AsyncClient` as a context manager for connection pooling and proper resource cleanup across multiple sequential API calls:

```python
async with httpx.AsyncClient(timeout=120) as c:
    # Multiple requests share same connection pool
```

### 4. **Dependency Injection via Import**
`fix_url.py` directly imports database session management from `storage.database`, coupling the script to the application's database abstraction layer:

```python
from storage.database import async_session, init_db
```

### 5. **Guarded Conditional Execution Pattern**
Scripts implement defensive checks before operations (e.g., checking for created tasks before dispatch):

```python
created = [t for t in tasks if t["status"] == "created"]
if created:
    # dispatch logic
```

---

## Data & Control Flow

### Script: `fix_url.py`

**Entry Point**: `python fix_url.py` → `asyncio.run(main())`

**Flow Sequence**:

1. **Database Initialization**: `init_db()` bootstraps connection pool and metadata
2. **Session Acquisition**: Async context manager yields transactional session
3. **Update Operation**: Executes parameterized SQL UPDATE via SQLAlchemy Core text() construct
4. **Commit**: Transaction persists changes to `llm_provider_configs` table
5. **Verification Query**: SELECT all providers to display current state
6. **Output**: Prints each provider name/base_url to stdout
7. **Termination**: Session exits, connection returned to pool

**Data In**: Runtime execution (no input arguments), embedded target URL (`http://172.19.0.2:20128/v1`)
**Data Out**: Printed rows from `llm_provider_configs` table

### Script: `e2e_final.py`

**Entry Point**: `python e2e_final.py` → `asyncio.run(test())`

**Flow Sequence**:

1. **Client Bootstrapping**: Creates async HTTP client with 120s timeout
2. **Authentication Phase**: POST `/api/auth/login` → extracts JWT access token
3. **Authorization Header Setup**: Bearer token attached to subsequent requests
4. **Sequential Health Checks**:

| Step | Endpoint | Purpose |
|------|----------|---------|
| 1 | GET `/health` | System readiness probe |
| 2 | GET `/api/llm/providers` | LLM gateway availability |
| 3 | GET `/api/llm/providers/{id}/models` | Model catalog fetch |

5. **Functional Validation**:
   - POST `/api/conversations` → creates conversation
   - POST `/api/conversations/{id}/messages` → sends "hello" → validates AI response
   - Complex task creation message → verifies task generation workflow

6. **Dashboard & List Aggregation**: Fetches overview statistics and entity lists:
   - GET `/api/dashboard/overview`
   - GET `/api/tasks`
   - GET `/api/workers`
   - GET `/api/approvals`
   - GET `/api/users`

7. **State Transition Test**: Dispatches a created task → waits 10s → verifies status change

8. **Result Compilation**: Aggregates all test outcomes, prints formatted report with PASS/WARN/FAIL symbols

**Data In**: Environment variable `BASE` (default: `http://localhost:8000`), embedded credentials (`admin/admin123`)
**Data Out**: Structured console report with per-test metrics, pass count summary

---

## Integration

### External Dependencies

| Dependency | Purpose | Module Level |
|------------|---------|--------------|
| `storage.database` | Async session factory, DB initialization | Internal package |
| `sqlalchemy` | ORM/text query construction | Direct |
| `httpx` | Async HTTP client for REST calls | Direct |
| `asyncio` | Event loop coordination | Standard library |

### Consumer Modules

| Consumer | Relationship |
|----------|--------------|
| CI/CD Pipeline | `e2e_final.py` invoked as post-deployment verification step |
| DevOps Engineers | Manual execution of `fix_url.py` for configuration corrections |
| Quality Assurance | E2E test suite executed before release sign-off |

### API Endpoints Consumed

**Authentication**:
- `POST /api/auth/login`

**LLM Services**:
- `GET /health`
- `GET /api/llm/providers`
- `GET /api/llm/providers/{id}/models`

**Conversation Management**:
- `POST /api/conversations`
- `POST /api/conversations/{id}/messages`

**Dashboard & Monitoring**:
- `GET /api/dashboard/overview`

**Resource Lists**:
- `GET /api/tasks`
- `GET /api/workers`
- `GET /api/approvals`
- `GET /api/users`

**Task Operations**:
- `POST /api/tasks/{id}/dispatch`
- `GET /api/tasks/{id}`

### Database Schema Touchpoints

**Tables Modified**:
- `llm_provider_configs`: base_url column update (SELECT also reads name, base_url)

**Tables Read**:
- `llm_provider_configs`: provider listing

---

## File Inventory

| File | Path | Lines | Status |
|------|------|-------|--------|
| `fix_url.py` | `/archive/` | 17 | Active migration utility |
| `e2e_final.py` | `/archive/` | 102 | Regression test suite |

**Note**: Both scripts reside in `archive/` subdirectory, indicating they may be legacy or reference implementations awaiting reorganization into dedicated directories (`maintenance/`, `tests/e2e/`).

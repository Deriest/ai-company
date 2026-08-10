# Middleware Layer — Codemap

**Directory**: `/backend/backend/middleware/`  
**Purpose**: Cross-cutting concerns for request handling, security, observability, and API governance.

---

## 1. Responsibility

This directory implements **middleware components** that intercept FastAPI requests before reaching route handlers and/or post-process responses. Each component provides a distinct cross-cutting concern:

| File | Responsibility |
|------|----------------|
| `logging_middleware.py` | Structured JSON request logging with unique request IDs and performance tracking |
| `error_handler.py` | Global exception handling with consistent error response formatting |
| `metrics.py` | In-memory metrics collection (request counts, errors, latencies) with `/metrics` endpoint |
| `validation.py` | Comprehensive input validation (body size, path/query params, content type, format checks) |
| `rate_limiter.py` | Per-user, per-category sliding window rate limiting to prevent abuse |
| `__init__.py` | Package initialization (empty) |

---

## 2. Design Patterns

### 2.1 Common Architectural Patterns

#### Asynchronous Middleware Pattern (`async def middleware(request, call_next)`)
All primary middleware follow the same signature pattern:

```python
async def middleware_name(request: Request, call_next: Callable) -> Response:
    # Pre-processing (extraction, validation, setup)
    start = time.perf_counter()
    
    # Delegate to next handler
    response: Response = await call_next(request)
    
    # Post-processing (logging, metrics, modifications)
    return response
```

**Benefits**:
- Non-blocking async execution
- Clean separation of pre/post processing logic
- Consistent integration point across the stack

#### Decorator-like Wrapper Pattern
Helper functions act as reusable utilities that can be called outside middleware context:

```python
# From validation.py
def validate_json_body(body: bytes, max_size: int) -> tuple[bool, str]:
    def sanitize_string(value: str, max_length: int) -> str:
    def validate_url(value: str) -> tuple[bool, str]:
```

#### Single Responsibility Principle
Each file handles exactly one concern:
- `logging_middleware.py`: Logging only
- `error_handler.py`: Exception handling only
- `metrics.py`: Metrics aggregation only
- `validation.py`: Input validation only
- `rate_limiter.py`: Rate limiting only

### 2.2 Specific Implementation Patterns

#### Singleton State with Thread Safety
`metrics.py` uses module-level state protected by locks:

```python
_lock = threading.Lock()
_endpoints: dict[str, EndpointStats] = defaultdict(EndpointStats)

def record(...):
    with _lock:
        # Critical section
```

#### Sliding Window Rate Limiting
`rate_limiter.py` implements a sliding window algorithm:

```python
_request_counts: dict[str, list[float]] = defaultdict(list)

def _cleanup_old_entries(bucket_key: str):
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _request_counts[bucket_key] = [t for t in times if t > cutoff]
```

#### Pattern Normalization for Metrics Grouping
UUIDs and hex IDs are normalized to `{id}` placeholders to prevent unbounded metric cardinality:

```python
_UUID_RE = re.compile(r"[0-9a-f]{8}...")
_HEX_ID_RE = re.compile(r"\b[0-9a-f]{12,}\b")

def _normalize_path(path: str) -> str:
    return _HEX_ID_RE.sub("{id}", _UUID_RE.sub("{id}", path))
```

#### Early Return Guard Pattern
Validation middleware uses early returns to fail fast:

```python
if size > 70 * 1024 * 1024:
    return JSONResponse(status_code=413, ...)
```

#### Category-Based Classification
Rate limiting uses path prefix classification:

```python
_CATEGORY_PREFIXES = (
    ("/conversations", "chat"),
    ("/chat", "chat"),
    ("/tasks", "runtime"),
)

def _endpoint_category(path: str) -> str:
    for prefix, category in _CATEGORY_PREFIXES:
        if path.startswith(prefix + "/"):
            return category
    return "default"
```

---

## 3. Data & Control Flow

### 3.1 Request Processing Pipeline

```
Request → Validation Middleware → Rate Limiter → Logging Middleware → Metrics Middleware → Route Handler
         ↓                           ↓               ↓                  ↓
         Validate params             Check limits    Capture ID          Record metrics
         Reject invalid              Block bursts    Log request         Track latency
         Return 400/422              Return 429      Attach header       Aggregate stats
```

### 3.2 Response Processing Pipeline

```
Route Handler → Metrics Middleware → Logging Middleware → User
              ↓                       ↓
              Record stats            Log status/duration
              Return response         Add X-Request-ID header
```

### 3.3 File-Specific Flows

#### `logging_middleware.py` Flow
1. Generate UUID request_id
2. Store in `request.state.request_id`
3. Time request execution via `call_next`
4. Stamp `X-Request-ID` header on response
5. Determine log level by status code:
   - ≥500 → ERROR
   - ≥400 → WARNING
   - <400 → INFO
6. Emit structured JSON log with fields:
   ```json
   {
     "request_id": "...",
     "method": "GET",
     "path": "/api/resource",
     "status_code": 200,
     "duration_ms": 45.2
   }
   ```

#### `error_handler.py` Flow
1. Catch exception in route handler
2. Log error details at ERROR level
3. Log stack trace at DEBUG level
4. Return standardized JSON:
   ```json
   {
     "detail": "Internal server error",
     "type": "ExceptionName"
   }
   ```

**Specialized handlers**:
- `value_error_handler`: Converts ValueError to 400 Bad Request

#### `metrics.py` Flow
1. Normalize path (replace UUIDs/hex IDs with `{id}`)
2. Create key: `{method} {normalized_path}`
3. Increment counters under lock:
   - `_global.request_count`
   - `_global.error_count` (if status ≥400)
   - `_global.total_latency_ms`
   - Per-endpoint stats
4. Enforce `_MAX_ENDPOINTS = 500` cap
5. Expose via `GET /metrics`:
   ```json
   {
     "uptime_seconds": 3600.5,
     "total_requests": 10000,
     "total_errors": 45,
     "avg_latency_ms": 125.3,
     "endpoints": {
       "GET /users/{id}": {
         "request_count": 5000,
         "error_count": 10,
         "avg_latency_ms": 85.2
       }
     }
   }
   ```

#### `validation.py` Flow
1. **Body Size Check**: Reject if POST/PUT/PATCH >70MB (returns 413)
2. **Path Parameter Sanitization**:
   - Reject path traversal (`../`)
   - Reject SQL injection patterns (`;`, `--`, `/*`, `*/`, keywords)
   - Reject values >1024 chars
3. **Query Parameter Validation**:
   - Reject values >10000 chars
4. **Pass Through**: Call `call_next`
5. **Catch Pydantic Errors**: Return 422 with detailed field errors

**Helper Functions** (standalone utilities):
- `validate_json_body()`: Returns `(bool, str)` tuple
- `sanitize_string()`: Removes null bytes, strips whitespace, truncates
- `validate_enum_value()`: Validates against allowed values
- `validate_integer_range()`: Min/max range checking
- `validate_string_length()`: Length constraints
- `validate_url()`: Proper URL parsing with `urlparse`
- `validate_email()`: Basic email format check

#### `rate_limiter.py` Flow
1. Extract user identifier:
   - Bearer token → SHA256 hash (first 16 chars)
   - No auth → Client IP prefixed with `ip_`
2. Skip `/health` endpoint entirely
3. Cleanup expired entries every 10 seconds (global cleanup)
4. Classify endpoint into category:
   - `chat`: /conversations, /chat, /stream
   - `runtime`: /tasks, /runtime, /workers, /dispatch
   - `default`: All others
5. Create bucket keys:
   - Category bucket: `{user_id}:{category}`
   - Global bucket: `{user_id}:__global__`
6. Check category limit (`_CATEGORY_LIMITS[category]`)
7. Check global limit (`RATE_LIMIT_MAX_REQUESTS = 300`)
8. If exceeded: Return 429 with `Retry-After` header
9. Append timestamp to both buckets
10. Pass request through

**Rate Limit Configuration**:
| Bucket | Limit | Window |
|--------|-------|--------|
| chat | 600 req/min | 60s |
| runtime | 300 req/min | 60s |
| default | 300 req/min | 60s |
| global | 300 req/min | 60s |

---

## 4. Integration Points

### 4.1 Dependencies

#### External Libraries
| Library | Usage | Files |
|---------|-------|-------|
| `fastapi.Request` | Request object access | All middleware |
| `fastapi.responses.*` | Response classes (JSONResponse, Response) | All middleware |
| `uuid.uuid4` | Unique request ID generation | `logging_middleware.py` |
| `threading.Lock` | Thread-safe state management | `metrics.py` |
| `collections.defaultdict` | Automatic dictionary initialization | `metrics.py`, `rate_limiter.py` |
| `dataclasses.dataclass` | Stats structure definition | `metrics.py` |
| `re.compile` | Path normalization regex | `metrics.py` |
| `time.perf_counter` | High-resolution timing | `logging_middleware.py`, `metrics.py`, `rate_limiter.py` |
| `hashlib.sha256` | Token hashing for user ID | `rate_limiter.py` |
| `logging` | Structured logging | All middleware |
| `json.dumps` | JSON log serialization | `logging_middleware.py` |
| `json.loads` | Body validation | `validation.py` |
| `urllib.parse.urlparse` | URL validation | `validation.py` |
| `pydantic.ValidationError` | Model validation errors | `validation.py` |

### 4.2 Consumers

#### Direct Integration Points
Middleware components are imported and mounted in the FastAPI application:

```python
from backend.middleware import (
    logging_middleware,
    error_handler,
    metrics_middleware,
    validation_middleware,
    rate_limit_middleware,
)

app.add_middleware(logging_middleware.logging_middleware)
app.add_middleware(validation_middleware.validation_middleware)
app.add_middleware(rate_limit_middleware.rate_limit_middleware)
app.add_middleware(metrics_middleware.metrics_middleware)

app.exception_handler(Exception)(error_handler.global_exception_handler)
app.exception_handler(ValueError)(error_handler.value_error_handler)
```

#### Route Handler Integration
- `metrics_endpoint()`: Mounts as `GET /metrics` route exposing aggregated statistics
- Error handlers automatically invoked by FastAPI exception propagation
- Other middleware transparently wrap all routes via `add_middleware()`

### 4.3 Shared State Management

#### Module-Level Variables
| Variable | Scope | Purpose | Thread-Safe? |
|----------|-------|---------|--------------|
| `_request_counts` | `rate_limiter.py` | Sliding window timestamps per bucket | Yes (implicit GIL protection) |
| `_endpoints` | `metrics.py` | Per-endpoint statistics map | Yes (`threading.Lock`) |
| `_global` | `metrics.py` | Aggregated global stats | Yes (`threading.Lock`) |
| `_lock` | `metrics.py` | Mutex for stats updates | Yes |

#### Request State Extensions
- `request.state.request_id`: Attached by logging middleware for correlation

### 4.4 Cross-Cutting Concerns

#### Security Controls
- **Input sanitization** (validation.py): Path traversal, SQL injection prevention
- **Size limits** (validation.py): 70MB body ceiling
- **Rate limiting** (rate_limiter.py): Prevents DoS and resource exhaustion
- **User isolation**: Rate buckets keyed by authenticated user or IP

#### Observability Features
- **Structured logging**: JSON format for log aggregation tools
- **Request tracing**: Unique UUID propagated via header
- **Performance metrics**: Latency percentiles via averaging
- **Error tracking**: Per-endpoint error counts
- **Health endpoint**: Unmonitored for availability testing

#### Error Response Standardization
All middleware return consistent error schema:
```json
{
  "detail": "Human-readable description",
  "type": "ErrorTypeName",
  ...optional context fields...
}
```

Status codes used:
| Code | Source | Trigger |
|------|--------|---------|
| 400 | error_handler, validation.py | Invalid parameter/syntax |
| 413 | validation.py | Body exceeds 70MB |
| 422 | validation.py | Pydantic validation failure |
| 429 | rate_limiter.py | Rate limit exceeded |
| 500 | error_handler.py | Unhandled exceptions |

---

## 5. Key Constants and Configuration

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| `RATE_LIMIT_WINDOW` | 60 | rate_limiter.py | Sliding window duration (seconds) |
| `RATE_LIMIT_MAX_REQUESTS` | 300 | rate_limiter.py | Global backstop limit |
| `_MAX_ENDPOINTS` | 500 | metrics.py | Maximum tracked endpoints |
| `_CATEGORY_LIMITS.chat` | 600 | rate_limiter.py | Chat/stream burst allowance |
| `_CATEGORY_LIMITS.runtime` | 300 | rate_limiter.py | Runtime operation limit |
| 70MB | 73,400,320 bytes | validation.py | Max request body size |
| 1024 chars | 1024 | validation.py | Max path param length |
| 10000 chars | 10000 | validation.py | Max query param length |

---

## 6. Known Issues and Fixes Referenced

### P12 Fix — Per-Endpoint Category Granularity
Previously shared single bucket per user caused chat/SSE bursts to starve control-plane endpoints. Now classified into `chat`, `runtime`, and `default` categories with independent limits while maintaining global backstop.

### F11 Fix — Path Parameter Sanitization
Enhanced validation to permit legitimate double-hyphens (skill/plugin IDs) while blocking dangerous patterns like `..../`, `--`, SQL comment markers, and injection keywords.

### P15 Fix — URL Validation
Replaced naive `startswith("http://")` with proper `urlparse()` parsing to reject malformed URLs like `http://evil.com.evil` or scheme spoofing attempts.

---

## 7. File Summary

| File | Lines | Key Classes/Functions |
|------|-------|----------------------|
| `logging_middleware.py` | 53 | `logging_middleware()`, `_json_log()` |
| `error_handler.py` | 32 | `global_exception_handler()`, `value_error_handler()` |
| `metrics.py` | 111 | `EndpointStats`, `metrics_middleware()`, `metrics_endpoint()`, `record()`, `snapshot()` |
| `validation.py` | 271 | `validation_middleware()`, `validate_json_body()`, `sanitize_string()`, `validate_url()`, etc. |
| `rate_limiter.py` | 142 | `rate_limit_middleware()`, `_endpoint_category()`, `_cleanup_old_entries()` |
| `__init__.py` | 0 | N/A |

**Total**: 608 lines of Python implementing comprehensive middleware layer.

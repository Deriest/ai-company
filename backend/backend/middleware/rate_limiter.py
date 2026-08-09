"""
Rate limiting middleware for AIC-ADE backend.

Simple in-memory sliding window rate limiter.
Suitable for desktop single-user deployment.

P12 FIX: per-endpoint bucket granularity. Previously every endpoint shared ONE
300 req/min bucket per user, so a burst of chat/SSE streaming requests could
starve dashboard, settings, and health API calls. Requests are now classified
into endpoint categories, each with its own bucket and limit, while the global
cap remains as an overall backstop.
"""

import time
import logging
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 300  # max requests per window (global backstop)

# P12: per-category limits within the window. Chat/SSE traffic is inherently
# bursty (streaming tokens, polling), so it gets its own generous bucket that
# cannot starve the control-plane endpoints (settings, projects, providers).
_CATEGORY_LIMITS = {
    "chat": 600,        # /conversations, /chat, /stream — bursty by design
    "runtime": 300,     # /tasks, /runtime, /workers, /dispatch
    "default": 300,     # everything else
}

# Path prefixes mapped to a category (first match wins).
_CATEGORY_PREFIXES = (
    ("/conversations", "chat"),
    ("/chat", "chat"),
    ("/stream", "chat"),
    ("/tasks", "runtime"),
    ("/runtime", "runtime"),
    ("/workers", "runtime"),
    ("/dispatch", "runtime"),
)


def _endpoint_category(path: str) -> str:
    """Classify a request path into a rate-limit category."""
    for prefix, category in _CATEGORY_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return category
    return "default"


_request_counts: dict[str, list[float]] = defaultdict(list)

_last_global_cleanup: float = 0.0


def _cleanup_old_entries(bucket_key: str):
    """Remove entries older than the window."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _request_counts[bucket_key] = [
        t for t in _request_counts[bucket_key] if t > cutoff
    ]


def _cleanup_all_entries():
    """Prune expired entries for all buckets and drop empty keys."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    empty = []
    for key, times in _request_counts.items():
        kept = [t for t in times if t > cutoff]
        if kept:
            _request_counts[key] = kept
        else:
            empty.append(key)
    for key in empty:
        del _request_counts[key]


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting per authenticated user session and endpoint category."""
    # Extract user identifier from auth token or fallback to IP
    user_id = "unknown"
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # In a real implementation, this would decode the JWT and extract user ID
        # For desktop app, we'll use a simple hash of the token for rate limiting
        import hashlib
        user_id = hashlib.sha256(token.encode()).hexdigest()[:16]
    else:
        # Fallback to client IP for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        user_id = f"ip_{client_ip}"

    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)

    # Periodically prune all user entries so stale entries never accumulate without bound.
    global _last_global_cleanup
    now = time.time()
    if now - _last_global_cleanup >= 10:
        _cleanup_all_entries()
        _last_global_cleanup = now

    # P12: bucket key includes the endpoint category so a chat burst cannot
    # consume the budget for dashboard/settings API calls.
    category = _endpoint_category(request.url.path)
    category_key = f"{user_id}:{category}"
    global_key = f"{user_id}:__global__"

    _cleanup_old_entries(category_key)
    _cleanup_old_entries(global_key)

    # Category-level check
    category_limit = _CATEGORY_LIMITS.get(category, RATE_LIMIT_MAX_REQUESTS)
    if len(_request_counts[category_key]) >= category_limit:
        logger.warning(f"Rate limit exceeded for user {user_id} category={category}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please wait."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    # Global backstop across all categories
    if len(_request_counts[global_key]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Global rate limit exceeded for user {user_id}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please wait."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    ts = time.time()
    _request_counts[category_key].append(ts)
    _request_counts[global_key].append(ts)
    return await call_next(request)

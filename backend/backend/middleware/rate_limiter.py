"""
Rate limiting middleware for AIC-ADE backend.

Simple in-memory sliding window rate limiter.
Suitable for desktop single-user deployment.
"""

import time
import logging
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 300  # max requests per window

_request_counts: dict[str, list[float]] = defaultdict(list)

_last_global_cleanup: float = 0.0


def _cleanup_old_entries(client_ip: str):
    """Remove entries older than the window."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if t > cutoff
    ]


def _cleanup_all_entries():
    """Prune expired entries for all IPs and drop empty keys."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    empty = []
    for ip, times in _request_counts.items():
        kept = [t for t in times if t > cutoff]
        if kept:
            _request_counts[ip] = kept
        else:
            empty.append(ip)
    for ip in empty:
        del _request_counts[ip]


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting per authenticated user session."""
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

    _cleanup_old_entries(user_id)

    if len(_request_counts[user_id]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please wait."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _request_counts[user_id].append(time.time())
    return await call_next(request)

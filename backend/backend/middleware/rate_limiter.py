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
RATE_LIMIT_BURST = 50  # max concurrent requests

_request_counts: dict[str, list[float]] = defaultdict(list)


def _cleanup_old_entries(client_ip: str):
    """Remove entries older than the window."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if t > cutoff
    ]


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting per client IP."""
    client_ip = request.client.host if request.client else "unknown"

    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)

    _cleanup_old_entries(client_ip)

    if len(_request_counts[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please wait."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _request_counts[client_ip].append(time.time())
    return await call_next(request)

"""
In-memory metrics collector for AIC-ADE backend.

Tracks global and per-endpoint request counts, error counts, and
average response times.  Exposes a GET /metrics JSON endpoint.
"""

import time
import re
import threading
from collections import defaultdict
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response, JSONResponse

# ── Data Structures ────────────────────────────────────────────


@dataclass
class EndpointStats:
    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return round(self.total_latency_ms / self.request_count, 2)


# Module-level state (lives for the lifetime of the process)
_lock = threading.Lock()
_start_time: float = time.time()
_global = EndpointStats()
_endpoints: dict[str, EndpointStats] = defaultdict(EndpointStats)

# M1: normalize dynamic path segments (UUIDs / long hex ids) to a route
# pattern so every distinct resource id doesn't add a permanent entry.
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_HEX_ID_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
# Hard cap so a long-tail of distinct routes can never grow unbounded.
_MAX_ENDPOINTS = 500


def _normalize_path(path: str) -> str:
    return _HEX_ID_RE.sub("{id}", _UUID_RE.sub("{id}", path))


# ── Public API ─────────────────────────────────────────────────


def record(method: str, path: str, status_code: int, duration_ms: float):
    """Record a completed request into the in-memory store."""
    key = f"{method} {_normalize_path(path)}"
    with _lock:
        _global.request_count += 1
        _global.total_latency_ms += duration_ms
        if status_code >= 400:
            _global.error_count += 1

        # M1: cap the per-endpoint map so it never grows unbounded.
        if key not in _endpoints and len(_endpoints) >= _MAX_ENDPOINTS:
            return
        ep = _endpoints[key]
        ep.request_count += 1
        ep.total_latency_ms += duration_ms
        if status_code >= 400:
            ep.error_count += 1


def snapshot() -> dict:
    """Return a point-in-time JSON-serialisable snapshot."""
    with _lock:
        uptime = round(time.time() - _start_time, 1)
        endpoints = {}
        for key, ep in sorted(_endpoints.items()):
            endpoints[key] = {
                "request_count": ep.request_count,
                "error_count": ep.error_count,
                "avg_latency_ms": ep.avg_latency_ms,
            }
        return {
            "uptime_seconds": uptime,
            "total_requests": _global.request_count,
            "total_errors": _global.error_count,
            "avg_latency_ms": _global.avg_latency_ms,
            "endpoints": endpoints,
        }


# ── Middleware ─────────────────────────────────────────────────


async def metrics_middleware(request: Request, call_next) -> Response:
    """Time each request and feed it into the metrics store."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    record(request.method, str(request.url.path), response.status_code, duration_ms)
    return response


# ── Endpoint handler ───────────────────────────────────────────


async def metrics_endpoint() -> JSONResponse:
    """GET /metrics — return the current snapshot."""
    return JSONResponse(content=snapshot())

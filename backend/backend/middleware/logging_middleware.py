"""
Structured request logging middleware for AIC-ADE backend.

Generates a unique request_id per request, logs method/path/status/duration
in JSON format, and attaches the request_id to response headers.
"""

import json
import logging
import time
import uuid
from fastapi import Request
from fastapi.responses import Response

logger = logging.getLogger("aic.request")


def _json_log(level: str, **fields):
    """Emit a structured JSON log line."""
    logger.log(
        getattr(logging, level, logging.INFO),
        json.dumps(fields, default=str),
    )


async def logging_middleware(request: Request, call_next) -> Response:
    """Attach a request_id, time the call, and log structured JSON."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    # Stamp request_id into response headers
    response.headers["X-Request-ID"] = request_id

    fields = dict(
        request_id=request_id,
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    if response.status_code >= 500:
        _json_log("ERROR", **fields)
    elif response.status_code >= 400:
        _json_log("WARNING", **fields)
    else:
        _json_log("INFO", **fields)

    return response

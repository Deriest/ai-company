"""
Global error handler middleware for FastAPI.
Catches unhandled exceptions and returns consistent error responses.
"""

import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError as 400 Bad Request."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )

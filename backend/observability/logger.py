"""AIC Platform — Structured JSON logging with trace_id propagation.

Log records emit a single JSON line per record:
    {"timestamp","component","event","severity","trace_id","message"}

trace_id flows through a contextvar; set it once per request/worker task via
``set_trace_id`` (use the returned token with ``reset_trace_id`` to restore).
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone

# ponytail: single global contextvar; fine for asyncio tasks since each task
# copies context. Upgrade to a per-request middleware-injected carrier only if
# threaded (non-async) callers need isolation.
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

_ROOT_NAME = "aic"
_configured = False


def set_trace_id(trace_id: str | None) -> Token[str | None]:
    """Bind ``trace_id`` to the current context. Returns a token for reset."""
    return trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    """Restore the previous trace_id binding."""
    trace_id_var.reset(token)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonFormatter(logging.Formatter):
    """Emit each record as one JSON line with the AIC schema."""

    def format(self, record: logging.LogRecord) -> str:
        # `event` defaults to the log message; callers passing `extra={"event": ...}`
        # override it. `component` defaults to the logger name.
        event = getattr(record, "event", record.getMessage())
        component = getattr(record, "component", record.name)
        payload = {
            "timestamp": _utc_iso(),
            "component": component,
            "event": event,
            "severity": record.levelname.lower(),
            "trace_id": trace_id_var.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logger(name: str) -> logging.Logger:
    """Configure (once) and return a logger under the root ``aic`` logger.

    Idempotent: repeated calls attach no duplicate handlers.
    Writes to stdout AND to /tmp/aic-backend.log for the Console UI.
    """
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if not _configured:
        fmt = JsonFormatter()
        # stdout handler (for uvicorn terminal output)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(fmt)
        root.addHandler(stdout_handler)
        # file handler (for Console UI logs tab)
        try:
            from pathlib import Path
            log_path = Path("/tmp/aic-backend.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
            file_handler.setFormatter(fmt)
            root.addHandler(file_handler)
        except Exception:
            pass  # non-critical
        root.setLevel(logging.DEBUG if __debug__ else logging.INFO)
        root.propagate = False
        _configured = True
    return root.getChild(name)


def get_logger() -> logging.Logger:
    """Return the root ``aic`` logger (configuring it on first call)."""
    if not _configured:
        setup_logger(_ROOT_NAME)
    return logging.getLogger(_ROOT_NAME)

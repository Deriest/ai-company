"""AIC Platform — Structured Tool System for Workers.

Provides real tool execution (file read/write, shell, explore) with
structured output that streams to the frontend as events.

OpenCode-inspired: every tool call produces a visible panel in the UI.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import signal
import socket
import time
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any

from backend.services.path_utils import resolve_workspace_path
from backend.services.tool_executor import check_dangerous_patterns

logger = logging.getLogger("aic.workers.tools")

# Command contains a shell background token: a standalone `&` (not `&&`, `&>`,
# `2>&1`), or an explicit `nohup` / `setsid`. Backgrounded commands keep the
# output pipe write-ends open after the shell exits, which makes
# proc.communicate() hang forever — so they are detached instead.
_BG_TOKEN_RE = re.compile(r"\s&(?:\s|$)|\bnohup(?:\s|$)|\bsetsid(?:\s|$)")

def get_safe_env():
    """Return minimal env without secrets for subprocess execution."""
    SECRET_ENV_VARS = frozenset([
        'AIC_LLM_API_KEY',
        'AIC_IDENTITY_PASSWORD', 
        'SECRET_KEY',
        'LLM_API_KEY',
        'AIC_SECRET_KEY',
        'JWT_SECRET',
    ])
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV_VARS}



def get_safe_env():
    """Return minimal env without secrets for subprocess execution."""
    SECRET_ENV_VARS = frozenset([
        'AIC_LLM_API_KEY',
        'AIC_IDENTITY_PASSWORD', 
        'SECRET_KEY',
        'LLM_API_KEY',
        'AIC_SECRET_KEY',
        'JWT_SECRET',
    ])
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV_VARS}


def _close_proc_pipes(proc) -> None:
    """Close stdout/stderr pipes so orphaned writers hit EPIPE instead of
    holding the asyncio transports open forever."""
    if proc is None:
        return
    for stream in (getattr(proc, "stdout", None), getattr(proc, "stderr", None)):
        if stream is None:
            continue
        close = getattr(stream, "close", None)
        if close is None:
            continue
        try:
            close()
        except Exception:
            pass


async def _kill_process_group(proc) -> None:
    """Kill the whole process group (shell + any backgrounded children) and reap.

    The shell is spawned with ``start_new_session=True``, so every descendant
    lands in one process group. Killing the group (SIGKILL) reaps backgrounded
    children that ``proc.kill()`` alone would orphan.
    """
    if proc is None:
        return
    try:
        if proc.returncode is None:
            pgid = os.getpgid(proc.pid)
            if pgid > 1:
                os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass
    try:
        await proc.wait()
    except Exception:
        pass


def _surface_port_in_use(command: str, error: str) -> str:
    """Surface a port-in-use failure explicitly so the LLM does not loop on a
    poisoned port."""
    if not error:
        return error
    err_lower = error.lower()
    if "address already in use" in err_lower or (
        "oserror" in err_lower and "bind" in err_lower and "address" in err_lower
    ):
        return (
            f"Port already in use (Address already in use). Choose a different "
            f"port or stop the existing server. Raw: {error}"
        )
    return error


# ── SSRF guard for web_fetch ─────────────────────────────

# Private / loopback / link-local / metadata / CGNAT ranges that must never be
# fetched from a server-side tool. Covers 10/8, 172.16/12, 192.168/16, 127/8,
# 169.254/16 (incl. cloud metadata 169.254.169.254), ::1, fc00::/7, fe80::/10.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _ip_is_blocked(ip) -> bool:
    """Return True if *ip* is a private/loopback/link-local/metadata address."""
    if ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return True
    if ip.is_private:
        return True
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def _validate_web_url(url: str, previous_scheme: str | None = None) -> None:
    """Validate a web_fetch URL — scheme + hostname resolution (SSRF guard).

    Raises ValueError with a safe message when the URL is not fetchable.
    """
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Blocked URL scheme '{scheme or 'none'}' — only http/https allowed")
    if previous_scheme == "https" and scheme == "http":
        raise ValueError("Blocked HTTPS→HTTP redirect downgrade")

    host = parsed.hostname
    if not host:
        raise ValueError("URL has no hostname")

    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise ValueError(f"Could not resolve hostname: {host}") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_is_blocked(ip):
            raise ValueError(f"Blocked private/internal IP: {ip}")


class _WebFetchRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects that escape to a blocked/private IP (SSRF guard)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        previous = getattr(req, "type", None)
        _validate_web_url(newurl, previous_scheme=previous)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ── Tool Call Schema ─────────────────────────────────────

@dataclass
class ToolCall:
    """A single tool invocation by a worker."""
    id: str = ""
    type: str = ""          # read_file, write_file, shell, explore, search, diff
    label: str = ""         # Human-readable label
    status: str = "pending" # pending, running, completed, error
    args: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    output: str = ""        # Raw output text
    duration_ms: int = 0
    timestamp: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_event(self, event_type: str = "tool_result") -> dict:
        return {"type": event_type, "tool_call": self.to_dict()}


@dataclass
class TodoItem:
    """A task item tracked in the chat."""
    id: str = ""
    content: str = ""
    status: str = "pending"  # pending, in_progress, completed, cancelled
    priority: str = "medium" # high, medium, low

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileDiff:
    """Represents a file change."""
    path: str = ""
    before: str = ""
    after: str = ""
    action: str = "modified"  # created, modified, deleted

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShellOutput:
    """Streaming shell command output."""
    command: str = ""
    output: str = ""
    exit_code: int | None = None
    status: str = "running"  # running, completed, error

    def to_dict(self) -> dict:
        return asdict(self)


# ── Tool Executor ────────────────────────────────────────

class ToolExecutor:
    """Executes real tools and collects structured results.

    Each tool call is tracked and can be streamed to the frontend.
    """

    def __init__(self, workspace_root: str = "", on_event=None, permission_checker=None, allowed_tools: list[str] | None = None, write_scope: str = "full"):
        self.workspace_root = workspace_root
        self.tool_calls: list[ToolCall] = []
        self.todos: list[TodoItem] = []
        self.file_diffs: list[FileDiff] = []
        self._on_event = on_event
        self._counter = 0
        self._permission_checker = permission_checker
        self._allowed_tools = allowed_tools
        self._write_scope = write_scope

    def _next_id(self) -> str:
        self._counter += 1
        return f"tc_{self._counter:04d}"

    async def _emit(self, event_type: str, data: dict):
        """Emit an event to the streaming callback."""
        if self._on_event:
            try:
                await self._on_event({"type": event_type, **data})
            except Exception:
                pass

    # ── File Read ────────────────────────────────────────

    async def read_file(self, path: str, offset: int = 0, limit: int = 2000) -> ToolCall:
        """Read a file from the workspace or filesystem."""
        tc = ToolCall(
            id=self._next_id(),
            type="read_file",
            label=f"Read {path}",
            status="running",
            args={"path": path, "offset": offset, "limit": limit},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._emit("tool_start", {"tool_call": tc.to_dict()})

        if self._permission_checker and not self._permission_checker("read_file"):
            tc.status = "error"
            tc.error = "Permission denied for tool: read_file"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        start = time.monotonic()

        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                # FIX: seek by BYTES previously — the schema documents offset as
                # a LINE offset. Skip lines like tool_executor.run_shell does so
                # both executors agree (offset=0 → from the top).
                if offset > 0:
                    for _ in range(offset):
                        f.readline()
                content = f.read(limit * 80)  # ~80 chars per line avg
                lines = content.split("\n")
                total_lines = len(lines)
                # Read total line count
                f.seek(0)
                all_lines = f.readlines()
                total_lines = len(all_lines)

            tc.result = {
                "path": path,
                "content": content,
                "total_lines": total_lines,
                "offset": offset,
                "lines_read": len(lines),
            }
            tc.output = content[:5000]
            tc.status = "completed"
        except FileNotFoundError:
            tc.status = "error"
            tc.error = f"File not found: {path}"
            tc.output = tc.error
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = tc.error

        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── File Write ───────────────────────────────────────

    def _validate_doc_path(self, path: str):
        """Placeholder for doc-scope validation."""
        pass  # R8 FIX placeholder

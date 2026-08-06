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

logger = logging.getLogger("aic.workers.tools")

# Command contains a shell background token: a standalone `&` (not `&&`, `&>`,
# `2>&1`), or an explicit `nohup` / `setsid`. Backgrounded commands keep the
# output pipe write-ends open after the shell exits, which makes
# proc.communicate() hang forever — so they are detached instead.
_BG_TOKEN_RE = re.compile(r"\s&(?:\s|$)|\bnohup(?:\s|$)|\bsetsid(?:\s|$)")


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
        """Validate a target path for docs-scoped write_file.

        Returns (ok: bool, reason: str). Docs-scoped roles may only write
        documentation artifacts: doc extensions (.md/.markdown/.txt/.rst/.adoc),
        files under docs/ or documentation/ (still doc extensions only), or
        standard doc basenames (README, LICENSE, CHANGELOG, CONTRIBUTING,
        ARCHITECTURE, DESIGN, PRD, RESEARCH, SECURITY_AUDIT,
        PERFORMANCE_REPORT) with or without an extension. Path traversal is
        rejected before any extension check.
        """
        import posixpath

        if not isinstance(path, str) or not path.strip():
            return False, "Invalid path"

        # Normalize (posix-style, workspace-relative) and reject traversal
        # BEFORE any extension check.
        norm = posixpath.normpath(path.strip().replace("\\", "/"))
        if norm.startswith("..") or norm.startswith("/"):
            return False, "Path traversal not allowed"
        parts = [p for p in norm.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return False, "Path traversal not allowed"
        if not parts:
            return False, "Invalid path"
        norm = "/".join(parts)

        doc_exts = ("md", "markdown", "txt", "rst", "adoc")
        doc_names = ("readme", "license", "changelog", "contributing",
                     "architecture", "design", "prd", "research",
                     "qa_report", "test_report", "project_plan", "compliance",
                     "security_audit", "performance_report", "bug_report")

        basename = parts[-1]
        stem, dot, ext = basename.rpartition(".")
        stem_lower = (stem if dot else basename).lower()
        ext_lower = ext.lower() if dot else ""

        # 1) Standard documentation basenames (case-insensitive), with or
        #    without an extension. Extension, when present, must still be a
        #    doc extension (README.md ok, README.py not).
        if stem_lower in doc_names:
            if not dot or ext_lower in doc_exts:
                return True, ""
            return False, (
                "This role can only write documentation artifacts "
                "(.md/.txt/docs/). Source code must be written by "
                "backend/frontend/coding/database workers."
            )

        # 2) Doc extension anywhere in the workspace (docs/ prefix not required).
        if ext_lower in doc_exts:
            return True, ""

        # 3) Anything else is a non-doc file (e.g. .py/.ts/.js/.json/.yaml).
        return False, (
            "This role can only write documentation artifacts "
            "(.md/.txt/docs/). Source code must be written by "
            "backend/frontend/coding/database workers."
        )

    async def write_file(self, path: str, content: str, create_dirs: bool = True) -> ToolCall:
        """Write content to a file, tracking the diff."""
        tc = ToolCall(
            id=self._next_id(),
            type="write_file",
            label=f"Wrote {path}",
            status="running",
            args={"path": path, "size": len(content)},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._emit("tool_start", {"tool_call": tc.to_dict()})

        if self._permission_checker and not self._permission_checker("write_file"):
            tc.status = "error"
            tc.error = "Permission denied for tool: write_file"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        # Docs-scoped write enforcement: thinker/artifact workers may only
        # write documentation paths. Validate BEFORE any filesystem access.
        if self._write_scope == "docs":
            ok, reason = self._validate_doc_path(path)
            if not ok:
                tc.status = "error"
                tc.error = reason
                tc.output = tc.error
                tc.duration_ms = 0
                self.tool_calls.append(tc)
                await self._emit("tool_result", {"tool_call": tc.to_dict()})
                return tc

        start = time.monotonic()

        try:
            full_path = resolve_workspace_path(self.workspace_root, path)

            # Capture before state
            before = ""
            action = "created"
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    before = f.read()
                action = "modified"

            # Create directories
            if create_dirs:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Write
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Record diff
            diff = FileDiff(path=path, before=before, after=content, action=action)
            self.file_diffs.append(diff)
            await self._emit("file_diff", diff.to_dict())

            tc.result = {
                "path": path,
                "action": action,
                "bytes_written": len(content),
                "lines": content.count("\n") + 1,
            }
            tc.output = f"{action}: {path} ({len(content)} bytes, {content.count(chr(10)) + 1} lines)"
            tc.status = "completed"
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = tc.error

        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── Shell Execution ──────────────────────────────────

    async def shell(self, command: str, timeout: int = 60, cwd: str | None = None) -> ToolCall:
        """Execute a shell command and capture output."""
        tc = ToolCall(
            id=self._next_id(),
            type="shell",
            label=f"$ {command}",
            status="running",
            args={"command": command, "timeout": timeout},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._emit("tool_start", {"tool_call": tc.to_dict()})

        # QA-E2E FIX: shell is arbitrary command execution — fail closed when
        # no permission checker is configured (e.g. the /chat/stream tool path
        # previously passed no checker, so create_subprocess_shell ran any
        # LLM-controlled command). Mirror agent_runner.py's check_permission
        # gate: the tool must never run without an explicit permission gate.
        if not self._permission_checker or not self._permission_checker("shell"):
            tc.status = "error"
            tc.error = "Permission denied for tool: shell"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        # Docs-scoped shell hardening: roles with write_scope="docs" cannot
        # run file-mutating shell commands that would bypass the doc-only
        # policy (e.g. `echo x > src/app.py`). Block destructive operations
        # by checking command tokens (word boundaries) rather than substrings.
        if self._write_scope == "docs":
            blocked = []
            # Extract all word tokens from the command
            tokens = re.findall(r"\b\w+\b", command.lower())
            if any(tok in ("rm", "mv", "dd", "chmod", "chown", "mkfs") for tok in tokens):
                blocked.append("destructive/moving commands (rm/mv/dd/chmod/chown/mkfs)")
            if ">" in command or ">>" in command:
                # Avoid matching >>> (Python)
                if "> " in command or ">>" in command or command.endswith(">") or command.endswith(">>"):
                    blocked.append("output redirection (> / >>)")
            if "tee" in tokens:
                blocked.append("tee")
            # Pipe-to-shell patterns
            if bool(re.search(r"\|\s*(sh|bash)\s*$", command)):
                blocked.append("pipe to shell (| sh/ bash)")
            if blocked:
                tc.status = "error"
                tc.error = f"Documentation-scoped roles cannot run file-mutating shell commands: {', '.join(blocked)}"
                tc.output = tc.error
                tc.duration_ms = 0
                self.tool_calls.append(tc)
                await self._emit("tool_result", {"tool_call": tc.to_dict()})
                return tc

        start = time.monotonic()

        work_dir = cwd or self.workspace_root or "."
        proc = None
        is_background = bool(_BG_TOKEN_RE.search(command or ""))
        raw_output = ""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.STDOUT,
                cwd=work_dir,
                # Own session/process group so a timeout can kill the shell AND
                # any backgrounded children with one SIGKILL to the group.
                start_new_session=True,
            )

            if is_background:
                # Detached: the shell exits immediately after backgrounding the
                # real command (DEVNULL means no pipe fds to inherit). Reap the
                # shell transport without waiting on the backgrounded child.
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except (asyncio.TimeoutError, ProcessLookupError):
                    pass
                _close_proc_pipes(proc)
                raw_output = "Started in background (detached). Command keeps running independently."
                exit_code = 0
                output_lines = [raw_output]
                await self._emit("shell_output", {
                    "command": command,
                    "chunk": "",
                    "exit_code": exit_code,
                    "status": "completed",
                })
            else:
                # Stream output
                output_lines = []
                try:
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    raw_output = stdout.decode("utf-8", errors="replace") if stdout else ""
                    output_lines = raw_output.split("\n")

                    # Emit shell output in chunks for streaming display
                    chunk_size = 500
                    for i in range(0, len(raw_output), chunk_size):
                        chunk = raw_output[i:i + chunk_size]
                        await self._emit("shell_output", {
                            "command": command,
                            "chunk": chunk,
                            "status": "running",
                        })

                except asyncio.TimeoutError:
                    # Kill the whole process group and close the pipes.
                    await _kill_process_group(proc)
                    raw_output = f"Command timed out after {timeout}s"
                    output_lines = [raw_output]
                except asyncio.CancelledError:
                    await _kill_process_group(proc)
                    raise
                finally:
                    _close_proc_pipes(proc)

                exit_code = proc.returncode or 0

                # Final shell output
                await self._emit("shell_output", {
                    "command": command,
                    "chunk": "",
                    "exit_code": exit_code,
                    "status": "completed" if exit_code == 0 else "error",
                })

            tc.result = {
                "command": command,
                "exit_code": exit_code,
                "output_lines": len(output_lines),
                "background": is_background,
            }
            raw_output = _surface_port_in_use(command, raw_output)
            tc.output = raw_output[:10000]
            tc.status = "completed" if exit_code == 0 else "error"
            if exit_code != 0:
                tc.error = _surface_port_in_use(command, raw_output) or f"Exit code: {exit_code}"

        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = tc.error

        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── Explore (directory listing + file tree) ──────────

    async def explore(self, path: str = ".", max_depth: int = 3, pattern: str = "*") -> ToolCall:
        """Explore directory structure."""
        tc = ToolCall(
            id=self._next_id(),
            type="explore",
            label=f"Explore {path}",
            status="running",
            args={"path": path, "max_depth": max_depth, "pattern": pattern},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._emit("tool_start", {"tool_call": tc.to_dict()})

        if self._permission_checker and not self._permission_checker("explore"):
            tc.status = "error"
            tc.error = "Permission denied for tool: explore"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        start = time.monotonic()

        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            tree_lines = []
            file_count = 0

            def _walk(dir_path: str, prefix: str, depth: int):
                nonlocal file_count
                if depth > max_depth or file_count > 200:
                    return
                try:
                    entries = sorted(os.listdir(dir_path))
                except PermissionError:
                    return
                for entry in entries:
                    if entry.startswith('.') or entry in ('__pycache__', 'node_modules', '.venv', 'venv'):
                        continue
                    full = os.path.join(dir_path, entry)
                    if os.path.isdir(full):
                        tree_lines.append(f"{prefix}{entry}/")
                        _walk(full, prefix + "  ", depth + 1)
                    else:
                        file_count += 1
                        tree_lines.append(f"{prefix}{entry}")
                        if file_count > 200:
                            tree_lines.append(f"{prefix}... (truncated at 200 files)")
                            return

            _walk(full_path, "", 0)
            tree_output = "\n".join(tree_lines[:300])

            tc.result = {
                "path": path,
                "tree": tree_output,
                "file_count": file_count,
                "entries": len(tree_lines),
            }
            tc.output = tree_output
            tc.status = "completed"
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = tc.error

        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── Search (grep-like) ───────────────────────────────

    async def search(self, pattern: str, path: str = ".", file_pattern: str = "*") -> ToolCall:
        """Search file contents with regex."""
        tc = ToolCall(
            id=self._next_id(),
            type="search",
            label=f"Search \"{pattern}\" in {path}",
            status="running",
            args={"pattern": pattern, "path": path, "file_pattern": file_pattern},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._emit("tool_start", {"tool_call": tc.to_dict()})

        if self._permission_checker and not self._permission_checker("search"):
            tc.status = "error"
            tc.error = "Permission denied for tool: search"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        start = time.monotonic()

        try:
            import re
            full_path = resolve_workspace_path(self.workspace_root, path)
            regex = re.compile(pattern, re.IGNORECASE)
            matches = []

            for root, dirs, files in os.walk(full_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.venv')]
                for fn in files:
                    if len(matches) > 100:
                        break
                    fp = os.path.join(root, fn)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as f:
                            for line_no, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel = os.path.relpath(fp, full_path)
                                    matches.append({
                                        "file": rel,
                                        "line": line_no,
                                        "content": line.strip()[:200],
                                    })
                                    if len(matches) > 100:
                                        break
                    except (PermissionError, IsADirectoryError):
                        continue

            tc.result = {"matches": matches, "total": len(matches)}
            tc.output = "\n".join(f"{m['file']}:{m['line']}: {m['content']}" for m in matches[:50])
            tc.status = "completed"
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = tc.error

        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── Todo Management ──────────────────────────────────

    def add_todo(self, content: str, status: str = "pending", priority: str = "medium") -> TodoItem:
        item = TodoItem(
            id=f"todo_{len(self.todos) + 1:03d}",
            content=content,
            status=status,
            priority=priority,
        )
        self.todos.append(item)
        return item

    def update_todo(self, todo_id: str, status: str) -> TodoItem | None:
        for item in self.todos:
            if item.id == todo_id:
                item.status = status
                return item
        return None

    # ── Git Tools ─────────────────────────────────────────

    async def git_status(self) -> ToolCall:
        """Get git status."""
        tc = ToolCall(id=self._next_id(), type="git_status", label="git status", status="running", args={}, timestamp=datetime.now(timezone.utc).isoformat())
        await self._emit("tool_start", {"tool_call": tc.to_dict()})
        start = time.monotonic()
        try:
            result = await self.shell("git status --porcelain")
            tc.output = result.output
            tc.status = "completed"
            tc.result = {"output": result.output}
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    async def git_diff(self, staged: bool = False) -> ToolCall:
        """Get git diff."""
        cmd = "git diff --staged" if staged else "git diff"
        tc = ToolCall(id=self._next_id(), type="git_diff", label=cmd, status="running", args={"staged": staged}, timestamp=datetime.now(timezone.utc).isoformat())
        await self._emit("tool_start", {"tool_call": tc.to_dict()})
        start = time.monotonic()
        try:
            result = await self.shell(cmd)
            tc.output = result.output[:10000]
            tc.status = "completed"
            tc.result = {"output": result.output}
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    async def git_log(self, count: int = 10) -> ToolCall:
        """Get recent git log."""
        tc = ToolCall(id=self._next_id(), type="git_log", label=f"git log -{count}", status="running", args={"count": count}, timestamp=datetime.now(timezone.utc).isoformat())
        await self._emit("tool_start", {"tool_call": tc.to_dict()})
        start = time.monotonic()
        try:
            result = await self.shell(f"git log --oneline -{count}")
            tc.output = result.output
            tc.status = "completed"
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    async def web_fetch(self, url: str, format: str = "markdown") -> ToolCall:
        """Fetch content from a URL."""
        tc = ToolCall(id=self._next_id(), type="web_fetch", label=f"Fetch {url}", status="running", args={"url": url, "format": format}, timestamp=datetime.now(timezone.utc).isoformat())
        await self._emit("tool_start", {"tool_call": tc.to_dict()})
        start = time.monotonic()

        # QA-SEC FIX: web_fetch performs an arbitrary network request — fail
        # closed when no permission checker is configured (mirror shell()).
        if not self._permission_checker or not self._permission_checker("web_fetch"):
            tc.status = "error"
            tc.error = "Permission denied for tool: web_fetch"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        try:
            # QA-SEC FIX: SSRF guard — validate scheme + block private/loopback/
            # link-local/metadata targets, and reject redirects that escape to
            # a blocked IP.
            _validate_web_url(url)
            req = urllib.request.Request(url, headers={"User-Agent": "AIC-Platform/1.0"})
            opener = urllib.request.build_opener(_WebFetchRedirectHandler())
            with opener.open(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")[:50000]
            tc.output = content
            tc.status = "completed"
            tc.result = {"output": content}
        except Exception as e:
            tc.status = "error"
            tc.error = str(e)
            tc.output = f"Error fetching {url}: {e}"
        tc.duration_ms = int((time.monotonic() - start) * 1000)
        self.tool_calls.append(tc)
        await self._emit("tool_result", {"tool_call": tc.to_dict()})
        return tc

    # ── Helpers ──────────────────────────────────────────

    def to_openai_schema(self) -> list[dict]:
        """Return tool definitions in OpenAI function-calling format."""
        all_tools = [
            {"type": "function", "function": {"name": "read_file", "description": "Read a file from the project workspace", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path relative to project root"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Write content to a file in the project workspace", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path relative to project root"}, "content": {"type": "string", "description": "File content to write"}}, "required": ["path", "content"]}}},
            {"type": "function", "function": {"name": "shell", "description": "Execute a shell command", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"}, "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "explore", "description": "List directory contents", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path", "default": "."}}}}},
            {"type": "function", "function": {"name": "search", "description": "Search file contents with regex", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Regex pattern"}, "path": {"type": "string", "description": "Directory to search in", "default": "."}}, "required": ["pattern"]}}},
            {"type": "function", "function": {"name": "git_status", "description": "Get git working tree status", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "git_diff", "description": "Get git diff of changes", "parameters": {"type": "object", "properties": {"staged": {"type": "boolean", "description": "Show staged changes instead of unstaged", "default": False}}}}},
            {"type": "function", "function": {"name": "git_log", "description": "Get recent git commit history", "parameters": {"type": "object", "properties": {"count": {"type": "integer", "description": "Number of commits to show", "default": 10}}}}},
            {"type": "function", "function": {"name": "web_fetch", "description": "Fetch content from a URL", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to fetch"}, "format": {"type": "string", "description": "Output format", "enum": ["text", "markdown", "html"], "default": "markdown"}}, "required": ["url"]}}},
        ]
        if self._allowed_tools is not None:
            allowed = set(self._allowed_tools)
            return [t for t in all_tools if t["function"]["name"] in allowed]
        return all_tools

    def get_summary(self) -> dict:
        """Get a summary of all tool calls for the response."""
        return {
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "todos": [t.to_dict() for t in self.todos],
            "file_diffs": [d.to_dict() for d in self.file_diffs],
            "files_modified": [d.path for d in self.file_diffs],
            "total_tool_calls": len(self.tool_calls),
            "total_errors": sum(1 for tc in self.tool_calls if tc.status == "error"),
        }

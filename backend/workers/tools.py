"""AIC Platform — Structured Tool System for Workers.

Provides real tool execution (file read/write, shell, explore) with
structured output that streams to the frontend as events.

OpenCode-inspired: every tool call produces a visible panel in the UI.
"""
from __future__ import annotations

import asyncio
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger("aic.workers.tools")


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

    def __init__(self, workspace_root: str = "", on_event=None, permission_checker=None, allowed_tools: list[str] | None = None):
        self.workspace_root = workspace_root
        self.tool_calls: list[ToolCall] = []
        self.todos: list[TodoItem] = []
        self.file_diffs: list[FileDiff] = []
        self._on_event = on_event  # async callback for streaming events
        self._counter = 0
        self._permission_checker = permission_checker  # callable(tool_name) -> bool
        self._allowed_tools = allowed_tools  # if set, only these tools are exposed

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
            full_path = self._resolve_path(path)
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                if offset > 0:
                    f.seek(offset)
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

        start = time.monotonic()

        try:
            full_path = self._resolve_path(path)

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

        if self._permission_checker and not self._permission_checker("shell"):
            tc.status = "error"
            tc.error = "Permission denied for tool: shell"
            tc.output = tc.error
            tc.duration_ms = 0
            self.tool_calls.append(tc)
            await self._emit("tool_result", {"tool_call": tc.to_dict()})
            return tc

        start = time.monotonic()

        work_dir = cwd or self.workspace_root or "."
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
            )

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
                proc.kill()
                raw_output = f"Command timed out after {timeout}s"
                output_lines = [raw_output]

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
            }
            tc.output = raw_output[:10000]
            tc.status = "completed" if exit_code == 0 else "error"
            if exit_code != 0:
                tc.error = f"Exit code: {exit_code}"

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
            full_path = self._resolve_path(path)
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
            full_path = self._resolve_path(path)
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
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(url, headers={"User-Agent": "AIC-Platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
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

    def _resolve_path(self, path: str) -> str:
        """Resolve a path relative to workspace root."""
        if os.path.isabs(path):
            return path
        if self.workspace_root:
            return os.path.join(self.workspace_root, path)
        return path

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

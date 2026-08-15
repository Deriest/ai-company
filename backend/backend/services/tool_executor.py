"""Worker tool executor with path safety and permission enforcement.

This module provides the core infrastructure for AI agent tool execution:
- WorkerToolExecutor: Main class that executes tools with safety checks
- check_permission: Runtime permission verification against worker types
- get_tools_for_worker: Returns available tool definitions per worker type
- WORKER_PERMISSIONS: Registry mapping workers to allowed tools
- DEFAULT_MINIMAL_TOOLS: Conservative default set for unknown workers

Security layers:
1. Path traversal prevention via _resolve_path()
2. Permission checking before each tool execution
3. Shell command dangerous pattern blocking
4. Docs-scoped write validation for read-only roles
5. MCP access control based on shell capability
"""
import os
import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict, List, Set

from backend.services.path_utils import resolve_workspace_path
from backend.security.shell_security import (
    check_dangerous_patterns,
    _close_proc_pipes,
    _BG_TOKEN_RE,
    _kill_process_group,
    _surface_port_in_use,
)

class _OutputOverflow(Exception):
    """Raised when a subprocess emits more output than the executor will retain."""


async def _read_output_with_cap(proc, cap: int = 1_000_000, kill_at: int = 4_000_000) -> bytes:
    """Drain proc.stdout with a memory cap.

    M5: ``communicate()`` buffers everything — ``yes`` for 600s is ~GBs of RAM.
    Read incrementally; past the retention cap keep draining (discarding), and
    hard-kill the process group once it exceeds kill_at.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await proc.stdout.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total <= cap:
            chunks.append(chunk)
        if total > kill_at:
            await _kill_process_group(proc)
            raise _OutputOverflow(f"output exceeded {kill_at} bytes")
    return b"".join(chunks)


def _clamp_timeout(v, default=60, lo=1, hi=600):
    try:
        n = int(v)
    except Exception:
        return default
    return max(lo, min(hi, n))

logger = logging.getLogger("aic.tool_executor")

# ── Minimal permission set for unknown/undefined workers ───────────────

DEFAULT_MINIMAL_TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file from the workspace", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_directory", "description": "List directory contents", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_depth": {"type": "integer"}}, "required": ["path"]}}},
]

# ── Worker-to-permission registry ───────────────────────────────────────

WORKER_PERMISSIONS: Dict[str, Set[str]] = {
    # Full-access coders (can execute code, modify files, run shells)
    "backend": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "frontend": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "coding": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},  # legacy alias
    "fullstack": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "database": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "nexus": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},  # devops/integration
    "flint": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},  # infra
    "devops": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "deployment": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "debugger": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    
    # QA/testers with full access for testing
    "qa": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "testing": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},  # legacy alias
    "performance": {"read_file", "explore", "search"},  # perf review (read-only)
    
    # Sprinter/crafter - coding-focused workers
    "sprinter": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},
    "crafter": {"run_shell", "write_file", "read_file", "explore", "search", "mcp_call"},  # legacy alias
    
    # Read-only/docs-writers (NO shell, limited write scope)
    "research": {"read_file", "explore", "search"},
    "pm": {"read_file", "write_file_docs", "explore", "search"},  # docs-scoped write
    "architect": {"read_file", "write_file_docs", "explore", "search"},  # docs-scoped write
    "designer": {"read_file", "write_file_docs", "explore", "search"},  # docs-scoped write
    "documentation": {"read_file", "write_file_docs", "explore", "search"},  # docs-scoped write
    
    # Governance/read-only
    "hermes": {"read_file", "explore", "search", "git_status"},
    "rex": {"read_file", "explore", "search", "git_status"},  # compliance gatekeeper
    "security": {"read_file", "explore", "search"},  # security review (read-only)
    
    # Planning/tiered workers
    "thinker": {"read_file", "explore", "search", "mcp_call"},  # can call MCP but not shell directly
    "planner": {"read_file", "explore", "search"},
    "reviewer": {"read_file", "explore", "search"},
    "vision": {"read_file", "explore", "search"},
    "review": {"read_file", "explore", "search"},
}


def _get_default_permissions(worker: str) -> Set[str]:
    """Return permissions for known worker, conservative defaults for unknown."""
    if worker in WORKER_PERMISSIONS:
        return WORKER_PERMISSIONS[worker]
    # Unknown worker → minimal read-only set
    return {"read_file", "explore", "search", "git_status"}


def _is_shell_capable(permission_set: Set[str]) -> bool:
    """Check if worker has shell capability (grants mcp_call auto-grant)."""
    return "run_shell" in permission_set or "write_file" in permission_set


# ── Permission checking API ─────────────────────────────────────────────


def check_permission(
    worker_type: str,
    tool_name: str,
    allowed_plugin_tools: Optional[List[str]] = None,
) -> bool:
    """Check if worker has permission to execute a specific tool."""
    allowed_plugins = set(allowed_plugin_tools or [])
    
    if tool_name in allowed_plugins:
        return True
    
    permissions = _get_default_permissions(worker_type)
    
    # Normalize aliases
    normalized_tool = tool_name
    if normalized_tool == "shell":
        normalized_tool = "run_shell"
    elif normalized_tool in ("list_dir", "list_directory"):
        normalized_tool = "explore"
    
    if tool_name.startswith("mcp_"):
        return "mcp_call" in permissions or "mcp_call" in allowed_plugins
    
    return normalized_tool in permissions


def get_tools_for_worker(worker_type: str) -> List[Dict[str, Any]]:
    """Get available tool definitions for a specific worker type."""
    permissions = _get_default_permissions(worker_type)
    tools = []
    
    # Base read-only tools (available to everyone)
    tools.append({
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": 2000},
                },
                "required": ["path"],
            },
        },
    })
    
    tools.append({
        "type": "function",
        "function": {
            "name": "explore",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "max_depth": {"type": "integer", "default": 3},
                    "pattern": {"type": "string", "default": "*"},
                },
                "required": ["path"],
            },
        },
    })
    
    tools.append({
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search file contents with regex",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "file_pattern": {"type": "string", "default": "*"},
                },
                "required": ["pattern"],
            },
        },
    })
    
    if "git_status" in permissions:
        tools.append({"type": "function", "function": {"name": "git_status", "description": "Get git status"}})
    
    # Write tools
    write_scope = "full" if "write_file" in permissions else "docs" if "write_file_docs" in permissions else None
    
    if write_scope:
        desc = "Write code/file" if write_scope == "full" else "Write documentation only"
        tools.append({
            "type": "function",
            "function": {
                "name": "write_file",
                "description": f"{desc} in workspace ({write_scope}-scoped)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "create_dirs": {"type": "boolean", "default": True},
                    },
                    "required": ["path", "content"],
                },
            },
        })
    
    # Shell/MCP for capable workers
    if "run_shell" in permissions:
        tools.append({
            "type": "function",
            "function": {
                "name": "run_shell",
                "description": "Execute shell command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout": {"type": "integer", "default": 60},
                    },
                    "required": ["command"],
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "mcp_call",
                "description": "Call MCP server tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["tool"],
                },
            },
        })
    
    return tools


# ── Result Data Classes ───────────────────────────────────────────────────


@dataclass
class ToolResult:
    """Standardized result from tool execution."""
    tool: str = ""
    success: bool = True
    output: str = ""
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def success_result(cls, tool: str, output: str, data: Optional[Dict] = None) -> "ToolResult":
        return cls(tool=tool, success=True, output=output, data=data)
    
    @classmethod
    def error_result(cls, tool: str, error: str) -> "ToolResult":
        return cls(tool=tool, success=False, error=error)


# ── WorkerToolExecutor Class ──────────────────────────────────────────────


class WorkerToolExecutor:
    """Executes tools with path safety and permission enforcement.
    
    This is the primary execution engine that agents use to interact with
    the filesystem, run commands, and perform operations on the workspace.
    """
    
    def __init__(
        self,
        workspace_root: str,
        permission_checker: Optional[callable] = None,
        write_scope: str = "full",
    ):
        """Initialize executor.
        
        Args:
            workspace_root: Root directory for safe path resolution
            permission_checker: Optional callable(type, tool_name) → bool
            write_scope: "full" or "docs" for write validation
        """
        self.workspace_root = os.path.realpath(workspace_root)
        self._permission_checker = permission_checker
        self._write_scope = write_scope
        self._call_counter = 0
    
    def _next_id(self) -> str:
        self._call_counter += 1
        return f"tc_{self._call_counter:04d}"
    
    def _resolve_path(self, path: str) -> str:
        """Resolve user-supplied path inside workspace, blocking traversal.

        Delegates to the single consolidated resolver (path_utils) so this
        copy can't drift. Raises ValueError on any escape attempt.
        """
        return resolve_workspace_path(self.workspace_root, path)
    
    async def check_tool_permission(self, tool_name: str) -> bool:
        """Check if current worker can execute this tool.

        When a permission_checker is wired (tool_chat_service), that is the
        authoritative gate. Without one (AgentRunner builds the executor
        directly), the executor is trusted and tools are allowed — the
        security default-deny for unknown *workers* lives in check_permission()
        (the registry), not here.
        """
        if self._permission_checker:
            return self._permission_checker(tool_name)
        return True
    
    async def read_file(self, path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
        """Read file with path safety checks."""
        if not await self.check_tool_permission("read_file"):
            return ToolResult.error_result("read_file", "Permission denied")
        
        try:
            full_path = self._resolve_path(path)
            
            # Safety check
            if not os.path.exists(full_path):
                return ToolResult.error_result("read_file", f"File not found: {path}")
            
            if not os.path.isfile(full_path):
                return ToolResult.error_result("read_file", "Path is not a file")
            
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            # Apply offset/limit (line-based)
            lines = content.split("\n")
            if offset > 0:
                lines = lines[offset:]
            if limit > 0:
                lines = lines[:limit]
            
            return ToolResult.success_result(
                "read_file",
                "\n".join(lines),
                {"total_lines": len(content.split("\n")), "lines_read": len(lines)}
            )
        except Exception as e:
            return ToolResult.error_result("read_file", str(e))
    
    async def write_file(self, path: str, content: str, create_dirs: bool = True) -> ToolResult:
        """Write file with docs-scoped enforcement."""
        if not await self.check_tool_permission("write_file"):
            return ToolResult.error_result("write_file", "Permission denied")
        
        # Validate doc scope
        if self._write_scope == "docs":
            import posixpath
            norm = posixpath.normpath(path.strip().replace("\\", "/"))
            if norm.startswith("..") or norm.startswith("/"):
                return ToolResult.error_result("write_file", "Path traversal not allowed")
            
            parts = [p for p in norm.split("/") if p not in ("", ".")]
            if any(p == ".." for p in parts):
                return ToolResult.error_result("write_file", "Path traversal not allowed")
            
            allowed_doc_names = {"readme", "license", "changelog", "contributing", "architecture", 
                               "design", "prd", "research", "qa_report", "test_report",
                               "security_audit", "performance_report"}
            exts = ("md", "markdown", "txt", "rst", "adoc")
            
            basename = os.path.basename(path).lower()
            if not any(basename == n or basename.endswith(f".{ext}") for n in allowed_doc_names for ext in exts):
                return ToolResult.error_result(
                    "write_file", 
                    "Docs-scoped: Only .md/.txt/doc files allowed"
                )
        
        try:
            full_path = self._resolve_path(path)
            
            if create_dirs:
                os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult.success_result(
                "write_file",
                f"Wrote {len(content)} bytes",
                {"path": path, "bytes_written": len(content)}
            )
        except Exception as e:
            return ToolResult.error_result("write_file", str(e))
    
    async def run_shell(self, command: str, timeout: int = 60) -> ToolResult:
        """Execute shell command with security checks.

        Supports backgrounded commands (``cmd &``) by detaching them and
        returning immediately (no pipe-hold hang), kills the whole process
        group on timeout, and surfaces port-in-use failures explicitly.
        """
        timeout = _clamp_timeout(timeout)
        if not await self.check_tool_permission("run_shell"):
            return ToolResult.error_result("run_shell", "Permission denied")
        
        # Dangerous pattern check
        try:
            check_dangerous_patterns(command)
        except PermissionError:
            return ToolResult.error_result("run_shell", "Command contains dangerous patterns")
        
        is_background = bool(_BG_TOKEN_RE.search(command or ""))
        proc = None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.STDOUT,
                cwd=self.workspace_root,
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
                return ToolResult(
                    tool="run_shell",
                    success=True,
                    output="Started in background (detached). Command keeps running independently.",
                    metadata={"background": True, "exit_code": proc.returncode},
                )
            
            try:
                stdout = await asyncio.wait_for(_read_output_with_cap(proc), timeout=timeout)
                await asyncio.wait_for(proc.wait(), timeout=5)
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                exit_code = proc.returncode or 0
            except _OutputOverflow as oe:
                return ToolResult(
                    tool="run_shell",
                    success=False,
                    output="",
                    error=f"Command output too large: {oe}",
                    metadata={"background": False},
                )
            except asyncio.CancelledError:
                # CancelledError derives from BaseException: without this handler
                # the cancel propagates and leaves an orphaned subprocess behind
                # (workers/tools.py already handles this — mirror it here).
                await _kill_process_group(proc)
                raise
            except asyncio.TimeoutError:
                await _kill_process_group(proc)
                return ToolResult(
                    tool="run_shell",
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout}s",
                    metadata={"background": False},
                )
            
            output = _surface_port_in_use(command, output)
            return ToolResult(
                tool="run_shell",
                success=exit_code == 0,
                output=output[:50000],  # Limit output size
                error=None if exit_code == 0 else (output or f"Exit code: {exit_code}"),
                metadata={"background": False, "exit_code": exit_code},
            )
        except Exception as e:
            return ToolResult.error_result("run_shell", _surface_port_in_use(command, str(e)))
    
    async def explore(self, path: str = ".", max_depth: int = 3) -> ToolResult:
        """List directory contents."""
        if not await self.check_tool_permission("explore"):
            return ToolResult.error_result("explore", "Permission denied")
        
        try:
            full_path = self._resolve_path(path)
            
            if not os.path.isdir(full_path):
                return ToolResult.error_result("explore", f"Not a directory: {path}")
            
            tree = []
            MAX_NODES = 2000
            state = {"count": 0}

            def _walk(dir_path: str, prefix: str, depth: int):
                if depth > max_depth or state["count"] >= MAX_NODES:
                    return
                try:
                    entries = sorted(os.listdir(dir_path))
                except PermissionError:
                    return

                for entry in entries:
                    if state["count"] >= MAX_NODES:
                        return
                    if entry.startswith("."):
                        continue
                    state["count"] += 1
                    full = os.path.join(dir_path, entry)
                    if os.path.isdir(full):
                        tree.append(f"{prefix}{entry}/")
                        _walk(full, prefix + "  ", depth + 1)
                    else:
                        tree.append(f"{prefix}{entry}")
            
            _walk(full_path, "", 0)
            return ToolResult.success_result("explore", "\n".join(tree[:500]))
        except Exception as e:
            return ToolResult.error_result("explore", str(e))
    
    async def search(self, pattern: str, path: str = ".") -> ToolResult:
        """Search files with regex."""
        if not await self.check_tool_permission("search"):
            return ToolResult.error_result("search", "Permission denied")
        
        try:
            full_path = self._resolve_path(path)
            import re

            matches = []
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return ToolResult.error_result("search", f"Invalid regex: {e}")

            # M6 budgets: bound work so an LLM-supplied pathological regex or a
            # huge tree cannot pin the executor (ReDoS / runaway scan).
            MAX_FILES = 500
            MAX_FILE_BYTES = 2_000_000
            MAX_LINES_PER_FILE = 50_000

            files_scanned = 0
            budget_exhausted = False
            for root, dirs, files in os.walk(full_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    if files_scanned >= MAX_FILES:
                        budget_exhausted = True
                        break
                    files_scanned += 1
                    fp = os.path.join(root, fn)
                    try:
                        if os.path.getsize(fp) > MAX_FILE_BYTES:
                            continue
                        with open(fp, "r", encoding="utf-8", errors="replace") as f:
                            for line_no, line in enumerate(f, 1):
                                if line_no > MAX_LINES_PER_FILE:
                                    break
                                if regex.search(line):
                                    matches.append({
                                        "file": os.path.relpath(fp, full_path),
                                        "line": line_no,
                                        "content": line.strip()[:200],
                                    })
                    except (PermissionError, UnicodeDecodeError) as e:
                        logger.debug(f"Skipping unreadable file {fp}: {e}")
                        continue
                    
                    if len(matches) >= 100:
                        budget_exhausted = True
                        break
                if budget_exhausted:
                    break
            
            output = "\n".join(f"{m['file']}:{m['line']}: {m['content']}" for m in matches[:50])
            return ToolResult.success_result("search", output, {"total_matches": len(matches), "files_scanned": files_scanned})
        except Exception as e:
            return ToolResult.error_result("search", str(e))
    
    async def git_status(self) -> ToolResult:
        """Get git status via shell."""
        return await self.run_shell("git status --porcelain")
    
    async def mcp_call(self, tool: str, arguments: Optional[Dict] = None) -> ToolResult:
        """MCP tool call stub - actual implementation requires MCP server connection."""
        if not await self.check_tool_permission("mcp_call"):
            return ToolResult.error_result("mcp_call", "Permission denied")
        
        return ToolResult.success_result("mcp_call", f"MCP tool '{tool}' called with {arguments or '{}'}")

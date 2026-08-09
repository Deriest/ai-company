"""Simple tool execution for workers — OpenCode-style real file/shell/search operations."""
import os
import re
import signal
import asyncio
import glob as glob_mod
from dataclasses import dataclass, field
from typing import Optional

from backend.services.path_utils import resolve_workspace_path

# Command contains a shell background token: a standalone `&` (not `&&`, `&>`,
# `2>&1`), or an explicit `nohup` / `setsid`. Backgrounded commands keep the
# output pipe write-ends open after the shell exits, which makes
# proc.communicate() hang forever — so they are detached instead.
_BG_TOKEN_RE = re.compile(r"\s&(?:\s|$)|\bnohup(?:\s|$)|\bsetsid(?:\s|$)")

# Hard ceiling for any shell subprocess, even if the caller (or model) requests
# a larger timeout. Foreground commands are bound by this in run_shell.
MAX_SHELL_TIMEOUT = 300

# ── Shell command safety denylist ────────────────────────
# Pragmatic guard against obviously destructive / exfiltration commands. Each
# entry is (compiled regex, human reason); matched case-insensitively against
# the raw command BEFORE the shell is spawned. This is NOT a substitute for a
# full argv allowlist / sandbox — legit multi-command agent usage (git, build,
# test) must keep working, so we only block clearly catastrophic patterns.
# A full allowlist-based sandbox is documented as future work in run_shell.
_SHELL_DENYLIST = [
    (re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.I), "rm -rf / (delete filesystem root)"),
    (re.compile(r"\brm\s+-rf\s+~(?:\s|$)", re.I), "rm -rf ~ (delete home directory)"),
    (re.compile(r"\brm\s+-rf\s+\$HOME(?:\s|$)", re.I), "rm -rf $HOME (delete home directory)"),
    (re.compile(r"\bmkfs\b", re.I), "mkfs (format a filesystem)"),
    (re.compile(r"\bdd\s+if=", re.I), "dd if= (raw disk read/copy)"),
    (re.compile(r">\s*/dev/sd", re.I), "write to raw block device /dev/sd*"),
    (re.compile(r"\b(?:curl|wget|aria2c)\b.*\|\s*(?:sh|bash)\b", re.I | re.S), "pipe downloaded script to shell"),
    (re.compile(r":\s*\(\s*\)\s*\{.*\};:", re.I | re.S), "fork bomb"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/(?:\s|$)", re.I), "chmod -R 777 / (world-writable root)"),
]


def _denylisted_shell_command(command: str) -> str | None:
    """Return a human-readable reason if the command is blocked, else None."""
    if not command:
        return None
    for pattern, reason in _SHELL_DENYLIST:
        if pattern.search(command):
            return reason
    return None


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

@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool: str
    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

class WorkerToolExecutor:
    """Execute real file/shell/search operations for workers.
    
    This is the core of OpenCode-style real tool execution.
    Workers use this to actually read files, write code, run tests, etc.
    """
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root

    def _resolve_path(self, path: str) -> str:
        """Resolve a path inside the workspace (delegates to the shared helper).

        Kept as a thin backward-compat shim — all logic lives in
        backend.services.path_utils.resolve_workspace_path.
        """
        return resolve_workspace_path(self.workspace_root, path)

    async def read_file(self, path: str, offset: int = 0, limit: int = -1) -> ToolResult:
        """Read file contents."""
        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                if offset > 0:
                    for _ in range(offset):
                        f.readline()
                if limit > 0:
                    content = ''.join(f.readline() for _ in range(limit))
                else:
                    content = f.read(50000)  # 50KB limit
            return ToolResult(
                tool="read_file", 
                success=True, 
                output=content,
                metadata={"path": path, "lines": content.count('\n'), "bytes": len(content)}
            )
        except Exception as e:
            return ToolResult(tool="read_file", success=False, output="", error=str(e))
    
    async def write_file(self, path: str, content: str) -> ToolResult:
        """Write content to file."""
        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(
                tool="write_file", 
                success=True, 
                output=f"Wrote {len(content)} bytes to {path}",
                metadata={"path": path, "bytes": len(content), "lines": content.count('\n')}
            )
        except Exception as e:
            return ToolResult(tool="write_file", success=False, output="", error=str(e))
    
    async def list_directory(self, path: str = ".") -> ToolResult:
        """List directory contents."""
        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            entries = []
            for entry in os.scandir(full_path):
                type_str = "dir" if entry.is_dir() else "file"
                size = entry.stat().st_size if entry.is_file() else 0
                if entry.is_file():
                    entries.append(f"[{type_str}] {entry.name} ({size}B)")
                else:
                    entries.append(f"[{type_str}] {entry.name}/")
            return ToolResult(
                tool="list_directory", 
                success=True, 
                output='\n'.join(entries[:200]),
                metadata={"count": len(entries)}
            )
        except Exception as e:
            return ToolResult(tool="list_directory", success=False, output="", error=str(e))
    
    async def search_files(self, pattern: str, path: str = ".", file_pattern: str = "*", is_regex: bool = False) -> ToolResult:
        """Search for pattern in files (grep-like).

        P10 FIX: supports optional regex matching (is_regex=True) so the LLM can
        run grep-like searches. Invalid regex falls back to case-insensitive
        substring matching instead of failing the whole tool call.
        """
        try:
            full_path = resolve_workspace_path(self.workspace_root, path)
            matches = []
            search_pattern = os.path.join(full_path, "**", file_pattern)

            # Compile the regex once, outside the per-line loop (P10).
            compiled = None
            if is_regex:
                try:
                    compiled = re.compile(pattern)
                except re.error:
                    compiled = None  # fall back to substring search

            for filepath in glob_mod.glob(search_pattern, recursive=True):
                if not os.path.isfile(filepath):
                    continue
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if compiled is not None:
                                found = compiled.search(line) is not None
                            else:
                                found = pattern.lower() in line.lower()
                            if found:
                                rel_path = os.path.relpath(filepath, self.workspace_root)
                                matches.append(f"{rel_path}:{line_num}: {line.strip()[:200]}")
                except (IOError, UnicodeDecodeError, OSError):
                    continue
                if len(matches) > 100:
                    break
            return ToolResult(
                tool="search_files", 
                success=True, 
                output='\n'.join(matches[:100]),
                metadata={"count": len(matches)}
            )
        except Exception as e:
            return ToolResult(tool="search_files", success=False, output="", error=str(e))
    
    async def run_shell(self, command: str, timeout: int = 30, cwd: str | None = None) -> ToolResult:
        """Execute shell command.

        Background commands (containing `&` / `nohup` / `setsid`) are detached:
        output is redirected to DEVNULL and the command returns immediately so a
        long-running server (e.g. `python -m http.server 8080 &`) never holds
        the output pipes open — which would otherwise hang proc.communicate()
        forever. Foreground commands keep the existing behavior.

        Safety hardening (pragmatic, without breaking legit multi-command agent
        usage like git/build/test):
        - A command denylist rejects obviously destructive/exfil patterns
          (rm -rf /, mkfs, dd if=, curl|sh, fork bomb, ...) before spawning.
        - A hard timeout ceiling (MAX_SHELL_TIMEOUT) bounds every subprocess.
        - cwd defaults to the workspace root (never the process cwd).
        NOTE: full argv-allowlist / sandboxing of the shell is future work; we
        deliberately keep shell=True so multi-command agents keep working.
        """
        command = command or ""
        blocked = _denylisted_shell_command(command)
        if blocked:
            return ToolResult(
                tool="run_shell", success=False, output="",
                error=f"Command blocked by safety denylist: {blocked}",
            )
        timeout = min(int(timeout or 30), MAX_SHELL_TIMEOUT)

        proc = None
        is_background = bool(_BG_TOKEN_RE.search(command))
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL if is_background else asyncio.subprocess.PIPE,
                cwd=cwd or self.workspace_root,
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
                return ToolResult(
                    tool="run_shell",
                    success=True,
                    output="Started in background (detached). Command keeps running independently.",
                    metadata={"command": command, "background": True, "exit_code": 0},
                )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            _close_proc_pipes(proc)
            output = stdout.decode('utf-8', errors='replace')[:10000] if stdout else ""
            error = stderr.decode('utf-8', errors='replace')[:5000] if stderr else ""
            error = _surface_port_in_use(command, error)
            return ToolResult(
                tool="run_shell",
                success=proc.returncode == 0,
                output=output,
                error=error if (proc.returncode != 0 and error) else None,
                metadata={"command": command, "exit_code": proc.returncode}
            )
        except asyncio.TimeoutError:
            # Kill the whole process group — the shell AND any children that
            # inherited the pipe write-ends — then close the pipes.
            await _kill_process_group(proc)
            _close_proc_pipes(proc)
            return ToolResult(tool="run_shell", success=False, output="", error=f"Command timed out after {timeout}s")
        except asyncio.CancelledError:
            await _kill_process_group(proc)
            _close_proc_pipes(proc)
            raise
        except Exception as e:
            await _kill_process_group(proc)
            _close_proc_pipes(proc)
            return ToolResult(tool="run_shell", success=False, output="", error=str(e))

    async def mcp_call(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute an MCP tool by name."""
        try:
            from backend.services.mcp_client import mcp_pool
            result = await mcp_pool.call_tool(tool_name, arguments)
            content_parts = result.get("content", [])
            output = "\n".join(p.get("text", "") for p in content_parts if p.get("type") == "text") or str(result)
            return ToolResult(tool="mcp_call", success=True, output=output[:5000])
        except Exception as e:
            return ToolResult(tool="mcp_call", success=False, output="", error=str(e))

# Tool definitions for OpenAI function calling format
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Always read a file before modifying it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"},
                    "offset": {"type": "integer", "description": "Line offset to start reading", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines to read (-1 for all)", "default": -1}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates directories if needed. Use after reading the file first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace"},
                    "content": {"type": "string", "description": "Complete file content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory. Use to explore project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": "."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text patterns in files (grep-like). Use to find code patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                    "file_pattern": {"type": "string", "description": "File glob pattern", "default": "*"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Execute a shell command. Use for running tests, building, git operations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_call",
            "description": "Execute an MCP (Model Context Protocol) tool by name. Use for external integrations, specialized tools, or when built-in tools are insufficient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Name of the MCP tool to execute"},
                    "arguments": {"type": "object", "description": "Arguments to pass to the MCP tool", "default": {}}
                },
                "required": ["tool_name"]
            }
        }
    }
]

# ── Tool permission model (registry-first) ───────────────
#
# SINGLE SOURCE OF TRUTH: For canonical agents (those defined in
# agents/registry.py) and the tool_permissions roles derived from the registry,
# tool access is computed from the registry via backend.services.tool_permissions
# (see _registry_allowed_tools below). This means an agent whose registry entry
# restricts/prohibits "shell" is NOT granted run_shell, and an agent not granted
# mcp_call cannot use mcp_* tools.
#
# WORKER_PERMISSIONS below is a DEPRECATED legacy map kept ONLY for backward
# compatibility with non-registry worker aliases (model-tier names like
# "crafter"/"sprinter"/"thinker" and legacy aliases like "coding"/"devops"/
# "fullstack"). It is consulted ONLY as a fallback when the worker is neither a
# canonical agent nor a tool_permissions-defined role. It must NOT be used for
# canonical agents — registry-derived permissions always win for those.
_FULL_TOOLS = frozenset({"read_file", "write_file", "list_directory", "search_files", "run_shell", "mcp_call"})
_READ_ONLY_TOOLS = frozenset({"read_file", "list_directory", "search_files"})
_READ_WRITE_TOOLS = frozenset({"read_file", "write_file", "list_directory", "search_files"})

# DEPRECATED: legacy fallback for non-registry worker aliases only.
WORKER_PERMISSIONS: dict[str, set[str]] = {
    # Read-only / research & planning aliases
    "research": set(_READ_ONLY_TOOLS),
    "pm": set(_READ_ONLY_TOOLS),
    "designer": set(_READ_ONLY_TOOLS),
    "review": set(_READ_ONLY_TOOLS),
    "vision": set(_READ_ONLY_TOOLS),
    "thinker": set(_READ_ONLY_TOOLS),
    "planner": set(_READ_ONLY_TOOLS),
    "reviewer": set(_READ_ONLY_TOOLS),
    # Read + write (no shell / no mcp)
    "documentation": set(_READ_WRITE_TOOLS),
    # Implementation / verification / iteration aliases
    "qa": set(_FULL_TOOLS),
    "security": set(_FULL_TOOLS),
    "performance": set(_FULL_TOOLS),
    "sprinter": set(_FULL_TOOLS),
    "crafter": set(_FULL_TOOLS),
    "testing": set(_FULL_TOOLS),
    # Full-access engineering aliases
    "backend": set(_FULL_TOOLS),
    "frontend": set(_FULL_TOOLS),
    "coding": set(_FULL_TOOLS),
    "fullstack": set(_FULL_TOOLS),
    "architect": set(_FULL_TOOLS),
    "database": set(_FULL_TOOLS),
    "devops": set(_FULL_TOOLS),
    "deployment": set(_FULL_TOOLS),
    "hermes": set(_FULL_TOOLS),
    "rex": set(_FULL_TOOLS),
    "nexus": set(_FULL_TOOLS),
    "flint": set(_FULL_TOOLS),
    "debugger": set(_FULL_TOOLS),
}

# Default-deny minimal set for unknown worker types.
DEFAULT_MINIMAL_TOOLS = frozenset(_READ_ONLY_TOOLS)

# Map executor tool names → logical registry/permission tool names.
# The registry (and tool_permissions) reason about logical tools like
# "shell"/"explore"/"search"; the executor exposes them as
# "run_shell"/"list_directory"/"search_files".
_EXECUTOR_TO_LOGICAL = {
    "read_file": "read_file",
    "write_file": "write_file",
    "list_directory": "explore",
    "search_files": "search",
    "run_shell": "shell",
    "mcp_call": "mcp_call",
}
_LOGICAL_TO_EXECUTOR = {v: k for k, v in _EXECUTOR_TO_LOGICAL.items()}


def _registry_allowed_tools(worker_type: str) -> Optional[set]:
    """Return the worker's allowed executor tools derived from the registry.

    Delegates to backend.services.tool_permissions.get_allowed_tools, which
    loads each canonical agent's ToolPermissions from AGENT_REGISTRY (plus a
    small set of registry-derived role policies). Returns None when the worker
    is neither a canonical agent nor a tool_permissions-defined role, so the
    caller falls back to the legacy WORKER_PERMISSIONS map.

    MCP POLICY: MCP servers/tools are external integrations the user explicitly
    configures, so ``mcp_call`` is auto-granted to any shell-capable worker
    (one that already has ``run_shell``). Read-only / docs-only / governance
    agents (no shell) do NOT get MCP. Centralizing the rule here means every
    registry-derived worker is covered without enumerating mcp_call per role.
    """
    from backend.services.tool_permissions import get_allowed_tools
    logical = get_allowed_tools(worker_type)
    if logical is None:
        return None
    executor_tools = set()
    for name in logical:
        mapped = _LOGICAL_TO_EXECUTOR.get(name)
        if mapped:
            executor_tools.add(mapped)
    # MCP follows shell capability (see docstring MCP POLICY).
    if "run_shell" in executor_tools:
        executor_tools.add("mcp_call")
    return executor_tools


def check_permission(worker_type: str, tool_name: str, allowed_plugin_tools: list[str] | None = None) -> bool:
    """Check if a worker is allowed to use a tool. Returns True if allowed.

    Permission model (registry-first):
    - Plugin tools assigned to the worker are auto-granted.
    - Canonical agents (and tool_permissions roles) derive their tools from the
      registry via `_registry_allowed_tools`. An agent whose registry entry
      restricts/prohibits "shell" is NOT granted run_shell; an agent not granted
      mcp_call cannot use mcp_* prefixed tools.
    - Non-canonical legacy aliases fall back to WORKER_PERMISSIONS.
    - Unknown worker types default-deny to DEFAULT_MINIMAL_TOOLS (read-only).
    """
    # Auto-grant the plugin's own tools for assigned workers.
    if allowed_plugin_tools and tool_name in allowed_plugin_tools:
        return True

    registry_tools = _registry_allowed_tools(worker_type)
    if registry_tools is not None:
        # Canonical / registry-derived worker — registry is the source of truth.
        if tool_name in registry_tools:
            return True
        # mcp_* prefixed tools require mcp_call permission.
        if tool_name.startswith("mcp_") and "mcp_call" in registry_tools:
            return True
        return False

    # Legacy fallback for non-registry aliases (crafter, coding, devops, ...).
    allowed = WORKER_PERMISSIONS.get(worker_type)
    if allowed is None:
        allowed = DEFAULT_MINIMAL_TOOLS  # default-deny, not full access

    if tool_name in allowed:
        return True
    if tool_name.startswith("mcp_") and "mcp_call" in allowed:
        return True
    return False


def get_tools_for_worker(worker_type: str) -> list:
    """Get tool definitions filtered by worker permissions (registry-first)."""
    registry_tools = _registry_allowed_tools(worker_type)
    if registry_tools is not None:
        return [t for t in AGENT_TOOLS if t["function"]["name"] in registry_tools]

    allowed = WORKER_PERMISSIONS.get(worker_type)
    if allowed is None:
        allowed = DEFAULT_MINIMAL_TOOLS  # default-deny for unknown workers
    return [t for t in AGENT_TOOLS if t["function"]["name"] in allowed]

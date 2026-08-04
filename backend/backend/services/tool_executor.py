"""Simple tool execution for workers — OpenCode-style real file/shell/search operations."""
import os
import asyncio
import glob as glob_mod
from dataclasses import dataclass, field
from typing import Optional

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
        """Resolve a path inside the workspace, blocking traversal outside.

        QA-E2E FIX: previously os.path.isabs() accepted absolute paths and
        '..' was never normalized, so a worker could read/write arbitrary
        files outside the workspace (e.g. /etc/passwd). Now every path is
        resolved against the workspace root and must stay inside it.
        """
        root = os.path.abspath(self.workspace_root)
        candidate = os.path.abspath(os.path.join(root, path))
        if candidate != root and not candidate.startswith(root + os.sep):
            raise ValueError(f"Path is outside the workspace: {path}")
        return candidate

    async def read_file(self, path: str, offset: int = 0, limit: int = -1) -> ToolResult:
        """Read file contents."""
        try:
            full_path = self._resolve_path(path)
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
            full_path = self._resolve_path(path)
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
            full_path = self._resolve_path(path)
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
    
    async def search_files(self, pattern: str, path: str = ".", file_pattern: str = "*") -> ToolResult:
        """Search for pattern in files (grep-like)."""
        try:
            full_path = self._resolve_path(path)
            matches = []
            search_pattern = os.path.join(full_path, "**", file_pattern)
            for filepath in glob_mod.glob(search_pattern, recursive=True):
                if not os.path.isfile(filepath):
                    continue
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.lower() in line.lower():
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
    
    async def run_shell(self, command: str, timeout: int = 30) -> ToolResult:
        """Execute shell command."""
        proc = None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode('utf-8', errors='replace')[:10000]
            error = stderr.decode('utf-8', errors='replace')[:5000] if stderr else None
            return ToolResult(
                tool="run_shell", 
                success=proc.returncode == 0, 
                output=output,
                error=error if proc.returncode != 0 else None,
                metadata={"command": command, "exit_code": proc.returncode}
            )
        except asyncio.TimeoutError:
            # FIX: kill the orphaned subprocess so it does not keep running.
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return ToolResult(tool="run_shell", success=False, output="", error=f"Command timed out after {timeout}s")
        except Exception as e:
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

# Permission rules per worker type
# Format: worker_type → allowed tools
# G3 FIX: workers NOT in this dict get a minimal read-only set (default-deny)
# instead of full access. Every known worker is enumerated explicitly so no
# capability is silently lost.
_FULL_TOOLS = frozenset({"read_file", "write_file", "list_directory", "search_files", "run_shell", "mcp_call"})
_READ_ONLY_TOOLS = frozenset({"read_file", "list_directory", "search_files"})
_READ_WRITE_TOOLS = frozenset({"read_file", "write_file", "list_directory", "search_files"})

WORKER_PERMISSIONS: dict[str, set[str]] = {
    # Read-only / research & planning workers
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
    # Implementation / verification / iteration workers
    "qa": set(_FULL_TOOLS),
    "security": set(_FULL_TOOLS),
    "performance": set(_FULL_TOOLS),
    "sprinter": set(_FULL_TOOLS),
    "crafter": set(_FULL_TOOLS),
    "testing": set(_FULL_TOOLS),
    # Full-access engineering workers
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


def check_permission(worker_type: str, tool_name: str, allowed_plugin_tools: list[str] | None = None) -> bool:
    """Check if a worker is allowed to use a tool. Returns True if allowed.

    BUG-17 FIX: Workers with 'mcp_call' permission can also use mcp_* prefixed tools.
    G3 FIX: unknown worker types default-deny to the minimal read-only set,
    and plugin tools (plugin_* / plugin_cmd_*) are auto-granted for workers the
    plugin is assigned to (the caller passes the exact plugin tool names).
    """
    # G3: auto-grant the plugin's own tools for assigned workers.
    if allowed_plugin_tools and tool_name in allowed_plugin_tools:
        return True

    allowed = WORKER_PERMISSIONS.get(worker_type)
    if allowed is None:
        allowed = DEFAULT_MINIMAL_TOOLS  # G3: default-deny, not full access

    # Direct match
    if tool_name in allowed:
        return True

    # BUG-17 FIX: mcp_* prefixed tools require mcp_call permission
    if tool_name.startswith("mcp_") and "mcp_call" in allowed:
        return True

    return False


def get_tools_for_worker(worker_type: str) -> list:
    """Get tool definitions filtered by worker type permissions."""
    allowed = WORKER_PERMISSIONS.get(worker_type)
    if allowed is None:
        allowed = DEFAULT_MINIMAL_TOOLS  # G3: default-deny for unknown workers
    return [t for t in AGENT_TOOLS if t["function"]["name"] in allowed]

"""Tool Permissions Enforcement.

Validates that a worker's tool calls are allowed by their ToolPermissions
defined in agents/registry.py. Workers can only use tools they're explicitly
permitted to use.

Usage:
    from backend.services.tool_permissions import check_tool_permission

    allowed = check_tool_permission("backend", "file_write")
    if not allowed:
        raise PermissionError("Backend worker cannot use file_write")
"""
import logging
from typing import Optional

logger = logging.getLogger("aic.tool_permissions")

# Tool permissions cache — loaded from AGENT_REGISTRY on first access
_permissions_cache: dict[str, dict] = {}

# Read-only tool set shared by conservative defaults and read-only roles.
_READ_ONLY_TOOLS = {"read_file", "explore", "search", "web_fetch",
                    "git_status", "git_diff", "git_log"}

# Roles that produce DOCUMENTATION artifacts (PRD, RESEARCH, ARCHITECTURE,
# DESIGN, SECURITY_AUDIT, PERFORMANCE_REPORT, README). They get write_file —
# but the ToolExecutor is constructed with write_scope="docs" so only
# documentation paths can actually be written. Shell is always denied.
DOCS_WRITER_ROLES = ("pm", "research", "architect", "designer",
                     "security", "performance", "documentation")


def _load_permissions() -> dict[str, dict]:
    """Load tool permissions from agent registry."""
    global _permissions_cache
    if _permissions_cache:
        return _permissions_cache

    try:
        from agents.registry import AGENT_REGISTRY
        for agent_id, agent in AGENT_REGISTRY.items():
            # FIX M1: AgentDefinition exposes permissions under 'tools'
            # (previously this checked a nonexistent 'tool_permissions'
            # attribute, so the cache never populated and every check was
            # permissive).
            if hasattr(agent, "tools"):
                tp = agent.tools
                _permissions_cache[agent_id] = {
                    "allowed": set(getattr(tp, "allowed", []) or []),
                    "restricted": set(getattr(tp, "restricted", []) or []),
                    "prohibited": set(getattr(tp, "prohibited", []) or []),
                }
    except (ImportError, Exception) as e:
        logger.debug(f"Could not load agent registry permissions: {e}")

    # Conservative read-only defaults for worker types NOT in AGENT_REGISTRY
    # (worker aliases with no corresponding agent definition). These roles must
    # not write files or run shell commands.
    for role_name in ("planner", "testing"):
        if role_name not in _permissions_cache:
            _permissions_cache[role_name] = {
                "allowed": {"read_file", "explore", "search"},
                "restricted": set(),
                "prohibited": {"write_file", "shell"},
            }

    # Coder aliases that should allow write/shell (not in AGENT_REGISTRY).
    for role_name in ("coding", "devops", "deployment"):
        if role_name not in _permissions_cache:
            _permissions_cache[role_name] = {
                "allowed": {"read_file", "write_file", "shell", "explore", "search"},
                "restricted": set(),
                "prohibited": set(),
            }

    # Debugger: bug-audit role — allows write_file (docs-scoped, enforced by
    # ToolExecutor write_scope="docs" so only docs/BUG_REPORT.md-style paths
    # can be written) plus shell for running existing diagnostics/tests.
    _permissions_cache["debugger"] = {
        "allowed": {"read_file", "write_file", "shell", "explore", "search"},
        "restricted": set(),
        "prohibited": set(),
    }

    # ── Explicit role policies (override raw registry data) ──────────────
    # Docs-scoped writer roles: artifact-producing thinkers. They get
    # write_file (the ToolExecutor enforces write_scope="docs" so only
    # documentation paths can be written) but NEVER shell.
    _docs_writer_tools = {
        "pm": {"read_file", "explore", "search", "write_file"},
        "research": {"read_file", "explore", "search", "web_fetch", "write_file"},
        "architect": {"read_file", "explore", "search", "write_file"},
        "designer": {"read_file", "explore", "search", "write_file"},
        "security": {"read_file", "search", "write_file"},
        "performance": {"read_file", "write_file"},
        "documentation": {"read_file", "write_file", "explore", "search"},
    }
    for role_name, tools in _docs_writer_tools.items():
        _permissions_cache[role_name] = {
            "allowed": tools,
            "restricted": set(),
            "prohibited": {"shell"},
        }

    # QA: runs tests (shell) AND writes QA_REPORT.md (docs-scoped write_file).
    _permissions_cache["qa"] = {
        "allowed": {"read_file", "explore", "search", "shell", "write_file"},
        "restricted": set(),
        "prohibited": set(),
    }

    # Rex (governor): docs-scoped write_file for COMPLIANCE.md, never shell.
    _permissions_cache["rex"] = {
        "allowed": {"read_file", "explore", "search", "write_file"},
        "restricted": set(),
        "prohibited": {"shell"},
    }

    # Read-only roles: hermes (router) — no write_file, no shell.
    # (review worker removed in round-6 audit — QA covers code review)
    for role_name in ("hermes",):
        _permissions_cache[role_name] = {
            "allowed": {"read_file", "explore", "search"},
            "restricted": set(),
            "prohibited": {"write_file", "shell"},
        }

    # Coder roles: full write_file + shell.
    for role_name in ("backend", "frontend", "database", "nexus", "flint"):
        _permissions_cache[role_name] = {
            "allowed": {"read_file", "write_file", "shell", "explore", "search"},
            "restricted": set(),
            "prohibited": set(),
        }

    return _permissions_cache


def check_tool_permission(worker_type: str, tool_name: str) -> bool:
    """Check if a worker is allowed to use a specific tool.

    NOTE (M1 fix + docs-scoped writing): the permission cache loads from
    AgentDefinition.tools. Docs-writer roles (pm, research, architect,
    designer, security, performance, documentation) allow write_file but deny
    shell; the ToolExecutor is constructed with write_scope="docs" so only
    documentation paths can actually be written. QA allows write_file and shell.
    Rex allows write_file but denies shell. Coders allow write_file and shell.
    hermes denies both. Unknown worker types default to a
    conservative read-only set.

    Returns True if:
    - The worker has no permissions defined AND the tool is read-only (conservative default)
    - The tool is in the worker's allowed list
    - The tool is NOT in the prohibited list

    Returns False if:
    - The tool is in the prohibited list
    - The tool is in the restricted list (restricted = requires approval)
    - The worker is unknown and the tool is not read-only
    """
    permissions = _load_permissions()

    if worker_type not in permissions:
        # M1 FIX: unknown worker types default to a conservative read-only set
        # (no write_file/shell) instead of the previous permissive default.
        if tool_name in _READ_ONLY_TOOLS:
            return True
        logger.warning(
            f"Tool '{tool_name}' denied for unknown worker '{worker_type}': "
            f"conservative read-only default (no write_file/shell)"
        )
        return False

    perms = permissions[worker_type]

    # Prohibited tools are always denied
    if tool_name in perms.get("prohibited", set()):
        logger.warning(f"Tool '{tool_name}' denied for worker '{worker_type}': prohibited")
        return False

    # Restricted tools require approval (for now, deny them)
    if tool_name in perms.get("restricted", set()):
        logger.info(f"Tool '{tool_name}' restricted for worker '{worker_type}'")
        return False

    # If allowed list exists and tool is not in it, deny
    allowed = perms.get("allowed", set())
    if allowed and tool_name not in allowed:
        logger.debug(f"Tool '{tool_name}' not in allowed list for worker '{worker_type}'")
        return False

    return True


def get_allowed_tools(worker_type: str) -> Optional[set]:
    """Get the set of allowed tools for a worker.

    Returns None if no restrictions are defined (all tools allowed).
    """
    permissions = _load_permissions()
    if worker_type not in permissions:
        return None

    perms = permissions[worker_type]
    allowed = perms.get("allowed", set())
    return allowed if allowed else None


def clear_cache():
    """Clear the permissions cache (useful for testing)."""
    global _permissions_cache
    _permissions_cache = {}

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


def _load_permissions() -> dict[str, dict]:
    """Load tool permissions from agent registry."""
    global _permissions_cache
    if _permissions_cache:
        return _permissions_cache

    try:
        from agents.registry import AGENT_REGISTRY
        for agent_id, agent in AGENT_REGISTRY.items():
            if hasattr(agent, "tool_permissions"):
                tp = agent.tool_permissions
                _permissions_cache[agent_id] = {
                    "allowed": set(getattr(tp, "allowed", []) or []),
                    "restricted": set(getattr(tp, "restricted", []) or []),
                    "prohibited": set(getattr(tp, "prohibited", []) or []),
                }
    except (ImportError, Exception) as e:
        logger.debug(f"Could not load agent registry permissions: {e}")

    return _permissions_cache


def check_tool_permission(worker_type: str, tool_name: str) -> bool:
    """Check if a worker is allowed to use a specific tool.

    Returns True if:
    - The worker has no permissions defined (permissive default)
    - The tool is in the worker's allowed list
    - The tool is NOT in the prohibited list

    Returns False if:
    - The tool is in the prohibited list
    - The tool is in the restricted list (restricted = requires approval)
    """
    permissions = _load_permissions()

    if worker_type not in permissions:
        # No permissions defined — permissive default
        return True

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

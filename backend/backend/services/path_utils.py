"""Shared workspace path resolution — single source of truth for path safety.

Consolidates three previously-divergent copies of ``_resolve_path``:
- backend/services/tool_executor.py
- workers/tools.py
- backend/services/tool_dispatcher.py

Security intent: a user/LLM-supplied path must never escape the workspace — it
may not be absolute, may not normalize outside the root via ``..``, and may not
abuse a sibling-prefix bypass (``/root2/...`` when the root is ``/root``).
"""
import os


def resolve_workspace_path(workspace_root: str, path: str) -> str:
    """Resolve a user-supplied path inside the workspace, blocking traversal.

    - Rejects absolute paths (must stay inside workspace)
    - Normalizes and blocks '..' escaping
    - Blocks sibling-prefix bypass (/root2/... when root is /root)
    - Raises ValueError on any escape
    """
    root = os.path.abspath(workspace_root)
    candidate = os.path.abspath(os.path.join(root, path))
    if candidate != root and not candidate.startswith(root + os.sep):
        raise ValueError(f"Path is outside the workspace: {path}")
    return candidate
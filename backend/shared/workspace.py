"""Shared workspace resolution — single source of truth for chat/executor paths.

Regression fix: project files previously landed in ``data/workspace`` because
workspace resolution fell back to ``"."`` (process cwd). The resolution below
NEVER falls back to process cwd:

1. explicit ``payload.workspace`` (if provided and non-empty)
2. ``conversation.project_id`` → ``Project.repo_path`` (if set)
3. active local profile ``active_project_id`` → ``Project.repo_path`` (if set)
4. per-conversation sandbox: ``DATA_DIR/workspaces/<conversation_id>``

``is_resolved`` is True only when the workspace came from an explicit payload or
a project repo_path — a sandbox fallback means the caller should treat the
request as "no workspace chosen" (e.g. trigger a clarify step).
"""
import logging
from pathlib import Path

logger = logging.getLogger("aic.workspace_resolution")


def sandbox_workspace_dir(scope_id) -> str:
    """Per-scope sandbox under ``DATA_DIR/workspaces`` — never process cwd.

    ``scope_id`` is a conversation id (chat path) or task id (runtime executor).
    The directory is created on demand.
    """
    from backend.config import settings
    d = Path(settings.DATA_DIR) / "workspaces" / str(scope_id)
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


async def _project_repo_path(db, project_id: str) -> str | None:
    """Return Project.repo_path if the row exists and has one."""
    from storage.models import Project
    try:
        proj = await db.get(Project, project_id)
    except Exception as e:
        logger.debug(f"Project lookup failed for {project_id}: {e}")
        return None
    if proj and proj.repo_path:
        return str(proj.repo_path)
    return None


async def resolve_conversation_workspace(db, payload_workspace: str | None, conversation_id: str):
    """Resolve the workspace root for a conversation.

    Returns ``(workspace_path, is_resolved)``. ``is_resolved`` is False when the
    result is the per-conversation sandbox fallback.
    """
    # 1. explicit payload.workspace
    if payload_workspace and str(payload_workspace).strip():
        return str(payload_workspace).strip(), True

    from sqlalchemy import select
    from storage.models import Conversation

    # 2. conversation.project_id → project.repo_path
    try:
        conv = await db.get(Conversation, conversation_id)
    except Exception as e:
        logger.debug(f"Conversation lookup failed for {conversation_id}: {e}")
        conv = None
    if conv is not None and conv.project_id:
        repo = await _project_repo_path(db, conv.project_id)
        if repo:
            return repo, True

    # 3. active local profile project → project.repo_path
    try:
        from backend.models.local_profile import LocalProfile
        prof = (await db.execute(select(LocalProfile).limit(1))).scalar_one_or_none()
        if prof is not None and prof.active_project_id:
            repo = await _project_repo_path(db, prof.active_project_id)
            if repo:
                return repo, True
    except Exception as e:
        logger.debug(f"Active profile workspace resolution skipped: {e}")

    # 4. per-conversation sandbox (never process cwd)
    return sandbox_workspace_dir(conversation_id), False
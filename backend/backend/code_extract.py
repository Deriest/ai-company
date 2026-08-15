"""Extract fenced code blocks from worker output into workspace files and optional repo_path.

Convention (same as aic-skill extract-code-blocks.py):
  ```python src/app.py
  ...
  ```
  or
  ```file:src/app.py
  ...
  ```
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path

from backend.workspace_manager import get_task_workspace_dir

logger = logging.getLogger(__name__)

BLOCK_PATTERN = re.compile(
    r"```(?:(\w+)\s+([\w./@\-_]+)|file:([\w./@\-_]+))\s*\n(.*?)```",
    re.DOTALL,
)

VALID_EXTS = {
    ".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".json", ".md",
    ".py", ".sh", ".yaml", ".yml", ".toml", ".svg", ".txt", ".sql",
    ".ini", ".cfg",
}


def _is_valid_filepath(fp: str) -> bool:
    _, ext = os.path.splitext(fp)
    if ext.lower() in VALID_EXTS:
        return True
    basename = os.path.basename(fp)
    return basename in (
        "Makefile", "Dockerfile", ".env", ".env.example", ".gitignore",
        "requirements.txt", "package.json", "pyproject.toml",
    )


def extract_code_blocks_to_workspace(task_id: str, content: str, repo_path: str | None = None) -> list[str]:
    """Write annotated code fences into task workspace and optional target repo_path. Returns relative paths written."""
    if not content:
        return []
    wdir = get_task_workspace_dir(task_id)
    repo_dir = Path(repo_path).resolve() if repo_path and os.path.isdir(repo_path) else None

    written: list[str] = []
    for lang, path1, path2, code in BLOCK_PATTERN.findall(content):
        filepath = (path1 or path2 or "").strip().strip("`").strip('"').strip("'")
        if not filepath or not _is_valid_filepath(filepath):
            continue
        if filepath.startswith("/") or ".." in Path(filepath).parts:
            continue

        # Write to task workspace
        target = (wdir / filepath).resolve()
        if not str(target).startswith(str(wdir.resolve())):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        body = code.rstrip() + "\n"
        target.write_text(body, encoding="utf-8")
        written.append(filepath)

        # Write to real project repo_path if available
        if repo_dir:
            try:
                repo_target = (repo_dir / filepath).resolve()
                if str(repo_target).startswith(str(repo_dir)):
                    repo_target.parent.mkdir(parents=True, exist_ok=True)
                    repo_target.write_text(body, encoding="utf-8")
            except Exception:
                logger.warning("Failed to write extracted code to repo_path (%s)", filepath, exc_info=True)

    return written

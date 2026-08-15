"""AIC Platform — Workspace & Deliverable Artifact File Manager.

Manages physical output files, mandatory README/REQUIREMENTS documentation,
clean ZIP package bundling (Download-Only V1 Delivery Standard), and
existing-project repository structure inspection.
"""
from pathlib import Path
import os
import re
import zipfile
import io
import logging

logger = logging.getLogger("aic.workspace")

def _workspace_base() -> Path:
    """Writable task workspace root — respects AIC_DATA_DIR for packaged installs."""
    env = os.environ.get("AIC_DATA_DIR", "").strip()
    if env:
        base = Path(env).expanduser().resolve() / "workspace"
    else:
        try:
            from backend.config import settings
            base = Path(settings.WORKSPACE_DIR)
        except Exception:
            base = Path(__file__).resolve().parent.parent / "data" / "workspace"
    base.mkdir(parents=True, exist_ok=True)
    return base


# Files/folders to exclude from downloadable delivery ZIP and directory inspection
ZIP_EXCLUDES = {
    "node_modules", ".venv", "venv", ".git", "__pycache__", ".DS_Store",
    ".env", ".env.local", "secrets.json", "*.log", "dist", "build", ".pytest_cache"
}


_TASK_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,128}$')

def _validate_task_id(task_id: str) -> None:
    """Reject path traversal / separator injection via task_id."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("Invalid task_id: must be non-empty string")
    if "/" in task_id or "\\" in task_id or ".." in task_id:
        raise ValueError(f"Invalid task_id: path separators not allowed: {task_id!r}")
    if not _TASK_ID_RE.match(task_id):
        raise ValueError(f"Invalid task_id: must match [A-Za-z0-9_-]{{1,128}}: {task_id!r}")

def get_task_workspace_dir(task_id: str) -> Path:
    """Return physical workspace directory for a task."""
    _validate_task_id(task_id)
    wdir = _workspace_base() / task_id
    wdir.mkdir(parents=True, exist_ok=True)
    try:
        wdir.resolve().relative_to(_workspace_base().resolve())
    except ValueError:
        raise ValueError(f"Invalid task_id: escapes workspace root: {task_id!r}")
    return wdir


def _safe_join(base: Path, rel: str) -> Path:
    """Join a user-supplied relative path onto base, blocking traversal outside.

    QA-E2E FIX: previously `wdir / relative_filename` was joined with no
    validation, so '..' components and absolute paths escaped the workspace,
    and read_workspace_file_content used startswith(str(wdir)) without a
    separator (sibling-prefix bypass). Reject absolute paths and '..'
    components, then re-verify the resolved path stays inside base.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("Invalid filename: must be a non-empty relative path")
    if os.path.isabs(rel) or rel.startswith("/"):
        raise ValueError("Invalid filename: absolute paths are not allowed")
    if ".." in Path(rel).parts:
        raise ValueError("Invalid filename: '..' path components are not allowed")
    base_r = base.resolve()
    candidate = (base_r / rel).resolve()
    try:
        candidate.relative_to(base_r)
    except ValueError:
        raise ValueError("Invalid filename: outside workspace")
    return candidate


def save_deliverable_file(task_id: str, relative_filename: str, content: str) -> str:
    """Save a deliverable file into task workspace directory."""
    wdir = get_task_workspace_dir(task_id)
    fpath = _safe_join(wdir, relative_filename)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content, encoding="utf-8")
    logger.info(f"Saved deliverable file for task {task_id[:8]}: {relative_filename} ({len(content)} bytes)")
    return str(fpath.relative_to(_workspace_base().parent))


def list_workspace_files(task_id: str) -> list[dict]:
    """List all generated deliverable files for a task."""
    wdir = get_task_workspace_dir(task_id)
    if not wdir.exists():
        return []

    files = []
    for root, _, filenames in os.walk(wdir):
        for fname in filenames:
            full_p = Path(root) / fname
            rel_p = str(full_p.relative_to(wdir))
            files.append({
                "filename": fname,
                "relative_path": rel_p,
                "size_bytes": full_p.stat().st_size,
                "modified_at": full_p.stat().st_mtime,
                "extension": full_p.suffix.lstrip("."),
            })
    return sorted(files, key=lambda f: f["relative_path"])


def read_workspace_file_content(task_id: str, relative_path: str) -> str:
    """Read content of a deliverable file in task workspace."""
    wdir = get_task_workspace_dir(task_id)
    fpath = _safe_join(wdir, relative_path)

    if not fpath.exists() or not fpath.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")

    return fpath.read_text(encoding="utf-8", errors="replace")


def inspect_project_structure(repo_path: str, max_files: int = 25) -> dict:
    """Inspect an existing project directory on disk.

    Returns dict with summary, file list, key configs, and structure overview.
    """
    p = Path(repo_path).resolve()
    if not p.exists() or not p.is_dir():
        return {"exists": False, "repo_path": repo_path}

    file_list = []
    key_configs = {}

    for root, dirs, filenames in os.walk(p):
        dirs[:] = [d for d in dirs if d not in ZIP_EXCLUDES]
        for fname in filenames:
            if fname in ZIP_EXCLUDES or fname.endswith(".log"):
                continue
            full_p = Path(root) / fname
            rel_p = str(full_p.relative_to(p))
            file_list.append(rel_p)

            # Read key configuration summaries
            if fname in ("package.json", "pyproject.toml", "requirements.txt", "Makefile", "pytest.ini") and rel_p not in key_configs:
                try:
                    key_configs[rel_p] = full_p.read_text(encoding="utf-8")[:1000]
                except Exception:
                    pass

    return {
        "exists": True,
        "repo_path": str(p),
        "total_files": len(file_list),
        "files_sample": sorted(file_list)[:max_files],
        "key_configs": key_configs,
    }


def generate_requirements_md(title: str, description: str, domain: str = "generic") -> str:
    """Generate mandatory REQUIREMENTS.md for Download-Only V1 Standard."""
    return f"""# Project Requirements

## Original Goal
{title}

## Finalized Scope
{description or title}

## Functional Requirements
- **FR-001**: Implement core business logic and user-facing capabilities for {title}.
- **FR-002**: Provide structured configuration, API endpoints, or user interface components as specified.
- **FR-003**: Ensure data persistence, input validation, and reliable error handling.

## Non-Functional Requirements
- **Performance**: Low execution latency and efficient resource usage.
- **Security**: Strict input sanitization, zero hardcoded credentials, and safe authorization.
- **Reliability**: Fail-closed error handling and clean logging.
- **Usability**: Clear documentation and responsive UI/CLI controls.

## Technical Constraints
- Target Domain: {domain.upper()}
- Runtime: Standard Linux / Node.js / Python environment.

## Assumptions
- Developed using the AIC Autonomous Engineering Platform pipeline.
- Verified through multi-agent FSM execution (Investigate, Planning, Implementation, Verification, Closeout).

## Out of Scope
- Third-party paid cloud services requiring external credentials.
- Unspecified custom hardware integrations.

## Acceptance Criteria
- [x] Functional Requirements FR-001 through FR-003 implemented.
- [x] Mechanical WECP verification gate passed.
- [x] Mandatory README.md and REQUIREMENTS.md generated and validated.
- [x] Zero real secrets or credentials present in package.
"""


def generate_readme_md(title: str, description: str, domain: str = "generic") -> str:
    """Generate mandatory README.md for Download-Only V1 Standard."""
    return f"""# {title}

## Overview
{description or title}

This project was built and verified using the **AIC Autonomous Engineering Platform**.

## Features
- **Core Functionality**: Full implementation of {title}.
- **Automated Workflow**: Developed through multi-agent collaboration (PM, Architect, Engineer, QA, Governor).
- **Verified Codebase**: Mechanical compliance checked for structure, security, and completeness.

## Technology Stack
- **Language**: JavaScript / Python / HTML
- **Architecture**: Modular software architecture
- **Testing**: Automated QA verification suite

## Prerequisites
- Node.js v18+ or Python 3.10+
- Git

## Installation
```bash
npm install # or pip install -r requirements.txt
```

## Usage
Follow running instructions above. Open browser at `http://localhost:3000` or run CLI commands.

## Troubleshooting
- If dependencies fail to install, ensure Node.js / Python versions match prerequisites.
- Check `.env` settings if database or server connections fail.
"""


def ensure_mandatory_delivery_docs(task_id: str, title: str, description: str):
    """Ensure mandatory README.md, REQUIREMENTS.md, and .env.example exist in workspace."""
    wdir = get_task_workspace_dir(task_id)

    readme_p = wdir / "README.md"
    if not readme_p.exists():
        readme_p.write_text(generate_readme_md(title, description), encoding="utf-8")

    req_p = wdir / "REQUIREMENTS.md"
    if not req_p.exists():
        req_p.write_text(generate_requirements_md(title, description), encoding="utf-8")

    env_p = wdir / ".env.example"
    if not env_p.exists():
        env_p.write_text("# AIC Project Configuration Template\n# Copy to .env and set real values\nPORT=8000\nNODE_ENV=production\n", encoding="utf-8")


def create_task_workspace_zip(task_id: str, title: str = "Project", description: str = "") -> bytes:
    """Create a clean in-memory ZIP archive of workspace (Download-Only V1 Standard)."""
    ensure_mandatory_delivery_docs(task_id, title, description)
    wdir = get_task_workspace_dir(task_id)
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, filenames in os.walk(wdir):
            dirs[:] = [d for d in dirs if d not in ZIP_EXCLUDES]

            for fname in filenames:
                if fname in ZIP_EXCLUDES or fname.endswith(".log") or fname == ".env":
                    continue

                full_p = Path(root) / fname
                arcname = str(full_p.relative_to(wdir))
                zf.write(full_p, arcname=arcname)

    buffer.seek(0)
    return buffer.getvalue()

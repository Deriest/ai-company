"""Plugin registry — install, list, assign, toggle, uninstall GitHub plugins."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.models import PluginEntry


def _plugin_root() -> Path:
    base = os.environ.get("AIC_DATA_DIR", "").strip()
    return Path(base) / "plugins" if base else Path(__file__).resolve().parents[3] / "data" / "plugins"


def _detect_components(package_dir: Path) -> list[str]:
    """Read plugin manifest or detect components from package structure."""
    manifest_file = None
    for candidate in (package_dir / ".claude-plugin" / "marketplace.json",
                      package_dir / "plugin.json",
                      package_dir / ".claude-plugin" / "plugin.json"):
        if candidate.exists():
            manifest_file = candidate
            break

    manifest = {}
    if manifest_file:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            pass

    components = []
    lookup = {
        "skill": lambda: bool(list(package_dir.rglob("SKILL.md"))),
        "scripts": lambda: (package_dir / "scripts").is_dir(),
        "commands": lambda: (package_dir / "commands").is_dir() or bool(manifest.get("commands")),
        "agents": lambda: (package_dir / "agents").is_dir() or bool(manifest.get("agents")),
        "hooks": lambda: (package_dir / "hooks").is_dir() or bool(manifest.get("hooks")),
        "mcp": lambda: (package_dir / "mcp").is_dir() or bool(manifest.get("mcp")),
        "assets": lambda: (package_dir / "assets").is_dir(),
        "docs": lambda: (package_dir / "docs").is_dir(),
        "references": lambda: (package_dir / "references").is_dir(),
        "templates": lambda: (package_dir / "templates").is_dir(),
    }
    for name, check in lookup.items():
        try:
            if check():
                components.append(name)
        except (OSError, ValueError):
            pass
    return components or ["skill"]


async def install_plugin(session: AsyncSession, repo_url: str, plugin_path: str = "", is_required: bool = False) -> dict:
    """Clone a GitHub repository and register its plugin/package."""
    # Parse URL
    requested = repo_url.strip().rstrip("/")
    path_hint = plugin_path.strip().strip("/")
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/[^/]+(?:/(.*))?)?", requested)
    if not match:
        raise ValueError("Invalid GitHub URL")

    repo_url = f"https://github.com/{match.group(1)}/{match.group(2)}.git"
    sub_path = path_hint or (match.group(3) or "")
    temp_dir = Path(tempfile.mkdtemp(prefix="aic-plugin-"))
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(temp_dir / "repo")],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise ValueError(f"Git clone failed: {result.stderr[-300:]}")

        root = (temp_dir / "repo" / sub_path).resolve()
        repo_root = (temp_dir / "repo").resolve()
        if repo_root not in root.parents and root != repo_root:
            raise ValueError("Invalid path")

        # Read manifest
        manifest_file = None
        for candidate in (root / ".claude-plugin" / "marketplace.json",
                          root / "plugin.json",
                          root / ".claude-plugin" / "plugin.json"):
            if candidate.exists():
                manifest_file = candidate
                break

        manifest = {}
        plugin_name = ""
        plugin_source = ""
        if manifest_file:
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if "plugins" in manifest and len(manifest["plugins"]) > 0:
                    plugin_name = manifest["plugins"][0].get("name", root.name)
                    plugin_source = manifest["plugins"][0].get("source", "")
                else:
                    plugin_name = manifest.get("name", root.name)
            except (json.JSONDecodeError, OSError):
                pass

        if not plugin_name:
            plugin_name = root.name

        components = _detect_components(root)

        # Determine skill instructions from SKILL.md
        instructions = ""
        skill_files = list(root.rglob("SKILL.md"))
        if skill_files:
            raw = skill_files[0].read_text(encoding="utf-8", errors="replace")
            front = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
            if front:
                instructions = raw[front.end():].strip()
            else:
                instructions = raw.strip()

        # Copy plugin package to local storage
        plugin_id = re.sub(r"[^a-z0-9-]+", "-", plugin_name.lower()).strip("-")[:64]
        installed_dir = _plugin_root() / plugin_id
        installed_dir.parent.mkdir(parents=True, exist_ok=True)
        if installed_dir.exists():
            shutil.rmtree(installed_dir)
        shutil.copytree(root, installed_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))

        # Resolve actual source from manifest
        if plugin_source:
            resolved_source = str((root / plugin_source).resolve())
            if resolved_source.startswith(str(root)):
                installed_dir = _plugin_root() / plugin_id / plugin_source.strip("./")
                installed_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(root / plugin_source, installed_dir, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))

        # Upsert plugin entry
        result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
        entry = result.scalar_one_or_none()
        if entry:
            entry.name = plugin_name
            entry.description = manifest.get("description", "") or ""
            entry.version = manifest.get("version", "0.0.0")
            entry.source_url = repo_url
            entry.package_path = str(installed_dir)
            entry.manifest = manifest
            entry.components = components
            entry.is_required = is_required
        else:
            entry = PluginEntry(
                plugin_id=plugin_id,
                name=plugin_name,
                description=manifest.get("description", "") or "",
                version=manifest.get("version", "0.0.0"),
                source="github",
                source_url=repo_url,
                package_path=str(installed_dir),
                manifest=manifest,
                components=components,
                assigned_workers=[],
                is_enabled=True,
                is_required=is_required,
            )
            session.add(entry)
        await session.commit()
        await session.refresh(entry)

        return {
            "id": entry.id,
            "plugin_id": entry.plugin_id,
            "name": entry.name,
            "description": entry.description,
            "version": entry.version,
            "source": entry.source,
            "source_url": entry.source_url,
            "package_path": entry.package_path,
            "components": entry.components or [],
            "assigned_workers": entry.assigned_workers or [],
            "is_enabled": entry.is_enabled,
            "is_required": entry.is_required,
            "instructions": instructions,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def list_plugins(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(PluginEntry))
    entries = result.scalars().all()
    return [{
        "id": e.id,
        "plugin_id": e.plugin_id,
        "name": e.name,
        "description": e.description,
        "version": e.version,
        "source": e.source,
        "source_url": e.source_url,
        "package_path": e.package_path,
        "components": e.components or [],
        "assigned_workers": e.assigned_workers or [],
        "is_enabled": e.is_enabled,
        "is_required": e.is_required,
    } for e in entries]


async def update_plugin(session: AsyncSession, plugin_id: str, patch: dict) -> dict | None:
    result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return None
    if "assigned_workers" in patch:
        entry.assigned_workers = patch["assigned_workers"]
    if "is_enabled" in patch:
        entry.is_enabled = patch["is_enabled"]
    if "is_required" in patch:
        entry.is_required = patch["is_required"]
    await session.commit()
    await session.refresh(entry)
    return {
        "id": entry.id,
        "plugin_id": entry.plugin_id,
        "name": entry.name,
        "description": entry.description,
        "version": entry.version,
        "source": entry.source,
        "source_url": entry.source_url,
        "package_path": entry.package_path,
        "components": entry.components or [],
        "assigned_workers": entry.assigned_workers or [],
        "is_enabled": entry.is_enabled,
        "is_required": entry.is_required,
    }


async def uninstall_plugin(session: AsyncSession, plugin_id: str) -> bool:
    result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    await session.delete(entry)
    await session.commit()
    shutil.rmtree(_plugin_root() / plugin_id, ignore_errors=True)
    return True


async def resolve_plugins_for_worker(session: AsyncSession, worker_type: str) -> list[dict]:
    """Resolve enabled plugins assigned to a specific worker type."""
    result = await session.execute(
        select(PluginEntry).where(PluginEntry.is_enabled == True)
    )
    plugins = result.scalars().all()
    matching = []
    for p in plugins:
        assigned = p.assigned_workers or []
        if worker_type in assigned or "all" in assigned:
            matching.append({
                "plugin_id": p.plugin_id,
                "name": p.name,
                "package_path": p.package_path,
                "components": p.components or [],
                "is_required": p.is_required,
            })
    return matching
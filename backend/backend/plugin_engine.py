"""Plugin registry — install, list, update, assign, toggle, uninstall GitHub plugins."""
import asyncio
import logging
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

logger = logging.getLogger("aic.plugin_engine")


def _plugin_root() -> Path:
    base = os.environ.get("AIC_DATA_DIR", "").strip()
    # plugin_engine.py = backend/backend/plugin_engine.py → parents[2] = repo root
    return Path(base) / "plugins" if base else Path(__file__).resolve().parents[2] / "data" / "plugins"


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
        # G11 FIX: run git clone off the event loop — subprocess.run blocks up
        # to 120s and would otherwise stall the whole async endpoint.
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "clone", "--depth", "1", repo_url, str(temp_dir / "repo")],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise ValueError(f"Git clone failed: {result.stderr[-300:]}")

        root = (temp_dir / "repo" / sub_path).resolve()
        repo_root = (temp_dir / "repo").resolve()
        # QA-E2E FIX: verify root is a strict descendant (or the repo root
        # itself) of repo_root. relative_to() raises ValueError for any path
        # that escapes the repo — including a plugin_path of ".." resolving
        # to temp_dir, which the prior parents-based check had to special-case.
        try:
            root.relative_to(repo_root)
        except ValueError:
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
            # QA-E2E FIX: path-boundary check — startswith(str(root)) was
            # bypassable via a sibling dir prefix (e.g. <root>2/...). Use
            # commonpath so only true descendants of the plugin root pass.
            try:
                is_inside = os.path.commonpath([str(root), resolved_source]) == str(root)
            except ValueError:
                is_inside = False
            if is_inside:
                # QA-E2E FIX: the destination was built from
                # plugin_source.strip("./") with no validation, so a mid-string
                # '..' (e.g. "a/../../x") wrote outside the plugin dir. Resolve
                # the destination and require it to stay inside _plugin_root()/plugin_id.
                dest_base = (_plugin_root() / plugin_id).resolve()
                dest_candidate = (dest_base / plugin_source.strip("./")).resolve()
                try:
                    dest_candidate.relative_to(dest_base)
                except ValueError:
                    raise ValueError("Invalid plugin source path")
                installed_dir = dest_candidate
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

        logger.info(
            "Plugin installed: plugin_id=%s name=%s version=%s",
            entry.plugin_id, entry.name, entry.version,
        )
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
    except Exception as e:
        logger.warning("Plugin install failed (repo=%s): %s", repo_url, e)
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def list_plugins(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(PluginEntry))
    entries = result.scalars().all()
    plugins = []
    for e in entries:
        # Parse manifest to extract minimum required version (if defined)
        manifest = e.manifest or {}
        min_version = manifest.get("minRequiredVersion", "0.0.0")
        
        plugins.append({
            "id": e.id,
            "plugin_id": e.plugin_id,
            "name": e.name,
            "description": e.description,
            "version": e.version,
            "min_required_version": min_version,
            "source": e.source,
            "source_url": e.source_url,
            "package_path": e.package_path,
            "components": e.components or [],
            "assigned_workers": e.assigned_workers or [],
            "is_enabled": e.is_enabled,
            "is_required": e.is_required,
        })
    return plugins


async def update_plugin(session: AsyncSession, plugin_id: str, patch: dict) -> dict | None:
    result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        logger.warning("Plugin update failed: plugin_id=%s not found", plugin_id)
        return None
    if "assigned_workers" in patch:
        entry.assigned_workers = patch["assigned_workers"]
    if "is_enabled" in patch:
        entry.is_enabled = patch["is_enabled"]
    if "is_required" in patch:
        # A plugin cannot be required if its package is missing (would crash enforcement).
        if patch["is_required"] and (not entry.package_path or not Path(entry.package_path).exists()):
            raise ValueError("Cannot mark plugin as required: package is missing")
        entry.is_required = patch["is_required"]
    await session.commit()
    await session.refresh(entry)
    logger.info(
        "Plugin updated: plugin_id=%s enabled=%s required=%s workers=%s",
        entry.plugin_id, entry.is_enabled, entry.is_required, entry.assigned_workers or [],
    )
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


async def update_plugin_repo(session: AsyncSession, plugin_id: str) -> dict | None:
    """Re-clone a plugin's source repository, compare versions, and upsert.

    G4 FIX: previously there was no update/version mechanism — the PATCH
    endpoint only toggled assignment/enable/required. This reuses the install
    pipeline against the plugin's stored source_url (which preserves
    assigned_workers and is_enabled) and reports whether the version changed.

    Returns a dict with `updated`/`version`/`previous_version`, or None if the
    plugin does not exist.
    """
    result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        logger.warning("Plugin update-repo failed: plugin_id=%s not found", plugin_id)
        return None
    if not entry.source_url:
        raise ValueError("Plugin has no source URL; cannot update")
    previous_version = entry.version or "0.0.0"
    fresh = await install_plugin(session, entry.source_url, "", is_required=entry.is_required)
    new_version = fresh.get("version") or "0.0.0"
    same_identity = fresh.get("plugin_id") == plugin_id
    logger.info(
        "Plugin repo updated: plugin_id=%s version=%s->%s updated=%s",
        plugin_id, previous_version, new_version,
        same_identity and new_version != previous_version,
    )
    return {
        "updated": same_identity and new_version != previous_version,
        "plugin_id": fresh.get("plugin_id"),
        "name": fresh.get("name"),
        "version": new_version,
        "previous_version": previous_version,
        "package_path": fresh.get("package_path"),
    }


async def uninstall_plugin(session: AsyncSession, plugin_id: str) -> bool:
    result = await session.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        logger.warning("Plugin uninstall failed: plugin_id=%s not found", plugin_id)
        return False
    await session.delete(entry)
    await session.commit()
    shutil.rmtree(_plugin_root() / plugin_id, ignore_errors=True)
    logger.info("Plugin uninstalled: plugin_id=%s name=%s", plugin_id, entry.name)
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
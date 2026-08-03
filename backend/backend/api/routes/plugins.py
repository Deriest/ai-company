"""Plugin management routes — install, list, update, uninstall, resolve."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.session import get_db
from backend.plugin_engine import (
    install_plugin, list_plugins, update_plugin, uninstall_plugin,
    resolve_plugins_for_worker,
)
from backend.services.plugin_adapter import build_plugin_context

router = APIRouter()


@router.post("/plugins/install")
async def install_plugin_endpoint(payload: dict, db: AsyncSession = Depends(get_db)):
    """Install a plugin from a public GitHub repository."""
    repo_url = payload.get("repo_url", "")
    plugin_path = payload.get("plugin_path", "")
    is_required = payload.get("is_required", False)
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")
    try:
        result = await install_plugin(db, repo_url, plugin_path, is_required)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plugins")
async def list_plugins_endpoint(db: AsyncSession = Depends(get_db)):
    """List all registered plugins."""
    return await list_plugins(db)


@router.patch("/plugins/{plugin_id}")
async def update_plugin_endpoint(plugin_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Update plugin assignment, enable/disable, required status."""
    result = await update_plugin(db, plugin_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return result


@router.delete("/plugins/{plugin_id}")
async def uninstall_plugin_endpoint(plugin_id: str, db: AsyncSession = Depends(get_db)):
    """Uninstall a plugin and remove its package."""
    ok = await uninstall_plugin(db, plugin_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {"status": "ok"}


@router.get("/plugins/{plugin_id}/context")
async def plugin_context_endpoint(plugin_id: str, db: AsyncSession = Depends(get_db)):
    """Get the adapted context for a plugin (tools, instructions, etc.)."""
    from storage.models import PluginEntry
    from sqlalchemy import select
    result = await db.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    if not entry.package_path or not Path(entry.package_path).exists():
        raise HTTPException(status_code=400, detail="Plugin package missing")
    ctx = build_plugin_context(entry.package_path, entry.components or [])
    ctx["plugin"] = {
        "plugin_id": entry.plugin_id,
        "name": entry.name,
        "version": entry.version,
        "is_required": entry.is_required,
    }
    return ctx


@router.get("/workers/{worker_type}/plugins")
async def worker_plugins_endpoint(worker_type: str, db: AsyncSession = Depends(get_db)):
    """Resolve plugins assigned to a worker type, with adapted context."""
    plugins = await resolve_plugins_for_worker(db, worker_type)
    results = []
    for p in plugins:
        ctx = {"plugin_id": p["plugin_id"], "name": p["name"], "is_required": p["is_required"], "components": p["components"]}
        if p.get("package_path") and Path(p["package_path"]).exists():
            adapted = build_plugin_context(p["package_path"], p["components"])
            ctx.update(adapted)
            ctx["loaded"] = True
        else:
            ctx["loaded"] = False
            if p["is_required"]:
                ctx["error"] = f"Plugin package missing for '{p['name']}'"
        results.append(ctx)
    return results
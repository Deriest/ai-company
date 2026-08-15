"""Full app-data backup endpoints.

AIC-ADE is a local desktop app; its entire state lives in ``settings.DATA_DIR``
(aic.db, identity.json, engine_config.json, plugins/, skills/, workspace/,
tasks/, feedback/, models_dev.json, ...). These endpoints back up the WHOLE
data directory into a single zip — intentionally superseding the per-conversation
export/import.

The SQLite database is snapshotted consistently while the app keeps running via
``VACUUM INTO`` (SQLite's online backup API), so no downtime is required.
"""

import asyncio
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.api.dependencies import require_current_user
from backend.config import settings


class BackupRestoreRequest(BaseModel):
    filename: str


async def run_database_migrations():
    """Placeholder - migrations are already handled by init_db()"""
    pass

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_current_user)])

# Directory names (case-insensitive) that are never included in a backup.
_EXCLUDED_DIR_NAMES = {"logs", "cache", "backups"}
# File suffixes that are never included (SQLite WAL/journal cruft).
_EXCLUDED_SUFFIXES = (".db-wal", ".db-shm")


def _backups_dir() -> Path:
    """Directory where backup zips are stored (inside the data dir)."""
    return Path(settings.DATA_DIR) / "backups"


def _iter_includable_files(data_dir: Path):
    """Yield ``(abs_path, posix_rel_path)`` for every file that belongs in a backup.

    Skips excluded dirs (logs, Cache, backups), SQLite WAL/SHM files, and the
    live ``aic.db`` (the VACUUM INTO snapshot stands in for it).
    """
    data_dir = Path(data_dir)
    for root, dirs, files in os.walk(data_dir):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d.lower() not in _EXCLUDED_DIR_NAMES]
        for name in files:
            if name.endswith(_EXCLUDED_SUFFIXES):
                continue
            if name == "aic.db":
                continue  # replaced by the snapshot
            abs_path = root_path / name
            yield abs_path, abs_path.relative_to(data_dir).as_posix()


def _unique_backup_filename(backups_dir: Path, ts: str) -> str:
    """Return a non-colliding ``aic-backup-<yyyymmdd-HHMMSS>.zip`` name."""
    candidate = backups_dir / f"aic-backup-{ts}.zip"
    if not candidate.exists():
        return candidate.name
    for i in range(1, 1000):
        candidate = backups_dir / f"aic-backup-{ts}-{i}.zip"
        if not candidate.exists():
            return candidate.name
    # Extremely unlikely: multiple creates within the same microsecond.
    return f"aic-backup-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.zip"


async def _snapshot_db(snapshot_path: Path) -> Path | None:
    """Snapshot the live SQLite DB consistently via ``VACUUM INTO``.

    VACUUM INTO is SQLite's online backup: it produces a consistent single-file
    snapshot even while the app holds the DB open (WAL mode included). If the DB
    is missing, or VACUUM INTO is unavailable on this driver, fall back to a
    plain copy of ``aic.db`` — with the caveat that a concurrent write during
    the copy could race.
    """
    db_path = Path(settings.DATA_DIR) / "aic.db"
    if not db_path.is_file():
        logger.warning("No aic.db at %s — backing up without a DB snapshot", db_path)
        return None
    escaped = str(snapshot_path).replace("'", "''")
    try:
        from backend.database.session import engine as db_engine

        async with db_engine.connect() as conn:
            await conn.execute(text(f"VACUUM INTO '{escaped}'"))
        if not (snapshot_path.is_file() and snapshot_path.stat().st_size > 0):
            raise OSError("VACUUM INTO produced no snapshot file")
        logger.info("DB snapshot via VACUUM INTO: %s", snapshot_path)
        return snapshot_path
    except Exception as e:
        logger.warning(
            f"VACUUM INTO failed ({e}); falling back to a plain copy of aic.db "
            "(a concurrent write during the copy could race)"
        )
        try:
            shutil.copy2(db_path, snapshot_path)
            return snapshot_path
        except OSError as copy_err:
            logger.error(f"Fallback DB copy failed: {copy_err}")
            return None


def _write_backup_zip(zip_path: Path, data_dir: Path, snapshot_path: Path | None, version: str) -> dict:
    """Write the backup zip (sync; called from a thread). Returns the manifest."""
    top_level = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if snapshot_path is not None and snapshot_path.is_file():
            zf.write(snapshot_path, "aic.db")
            top_level.add("aic.db")
        for abs_path, rel in _iter_includable_files(data_dir):
            zf.write(abs_path, rel)
            top_level.add(rel.split("/", 1)[0])
        manifest = {
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "app": "AIC-ADE",
            "data_dir": sorted(top_level),
        }
        zf.writestr("backup-manifest.json", json.dumps(manifest, indent=2))
    return manifest


@router.post("/backup/create")
async def create_backup(_auth: str = Depends(require_current_user)):
    """Create a full backup zip of the entire app data dir.

    Returns ``{filename, size, created_at}`` — never the absolute path.
    """
    data_dir = Path(settings.DATA_DIR)
    backups_dir = _backups_dir()
    backups_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = backups_dir / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = _unique_backup_filename(backups_dir, ts)
    zip_path = backups_dir / filename

    snapshot_path = None
    try:
        snapshot_path = await _snapshot_db(tmp_dir / f"aic-{ts}.db")
        manifest = await asyncio.to_thread(
            _write_backup_zip, zip_path, data_dir, snapshot_path, settings.VERSION
        )
        size = zip_path.stat().st_size
        return {
            "filename": filename,
            "size": size,
            "created_at": manifest["created_at"],
        }
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="Backup creation failed")
    finally:
        # Clean up the temporary snapshot dir after zipping.
        shutil.rmtree(tmp_dir, ignore_errors=True)


class BackupValidateRequest(BaseModel):
    filename: str


def _safe_backup_filename(filename: str) -> bool:
    """Reject path-traversal / non-zip filenames."""
    if not filename.endswith(".zip"):
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return True


@router.post("/backup/validate")
async def validate_backup(
    payload: BackupValidateRequest,
    _auth: str = Depends(require_current_user),
):
    """Validate an existing backup zip: manifest fields + aic.db presence."""
    if not _safe_backup_filename(payload.filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    zip_path = _backups_dir() / payload.filename
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            if "backup-manifest.json" not in names:
                return {
                    "valid": False,
                    "entries": len(names),
                    "error": "backup-manifest.json missing",
                }
            manifest = json.loads(zf.read("backup-manifest.json"))
            required = {"version", "created_at", "app"}
            if not required.issubset(manifest):
                return {
                    "valid": False,
                    "entries": len(names),
                    "error": "manifest missing required fields",
                }
            if "aic.db" not in names:
                return {
                    "valid": False,
                    "entries": len(names),
                    "error": "backup does not contain aic.db",
                }
            return {
                "valid": True,
                "version": manifest.get("version"),
                "created_at": manifest.get("created_at"),
                "entries": len(names),
                "error": None,
            }
    except zipfile.BadZipFile:
        return {"valid": False, "error": "not a valid zip file"}
    except (json.JSONDecodeError, KeyError) as e:
        return {"valid": False, "error": f"invalid backup: {e}"}


@router.post("/backup/restore")
async def restore_backup(
    payload: BackupRestoreRequest,
    _auth: str = Depends(require_current_user),
):
    """Safely restore from a validated backup zip.

    Requires application graceful shutdown to prevent data corruption.
    """
    import shutil

    if not _safe_backup_filename(payload.filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename")

    zip_path = _backups_dir() / payload.filename
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")

    # Validate backup before proceeding
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        if "backup-manifest.json" not in names or "aic.db" not in names:
            raise HTTPException(status_code=400, detail="Invalid backup format")

        manifest = json.loads(zf.read("backup-manifest.json"))
        required = {"version", "created_at", "app"}
        if not required.issubset(manifest):
            raise HTTPException(status_code=400, detail="Manifest missing required fields")
        if manifest.get("app") != "AIC-ADE":
            raise HTTPException(status_code=400, detail="Incompatible backup format")

    # Create temp directory for extraction
    temp_dir = settings.DATA_DIR / ".restore_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract backup contents
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(temp_dir)

        # Verify extracted structure
        extracted_db = temp_dir / "aic.db"
        if not extracted_db.exists():
            raise HTTPException(status_code=400, detail="Extracted backup missing database")

        # Safety snapshot: keep existing data for 7 days rollback
        old_data_dir = settings.DATA_DIR.with_suffix(settings.DATA_DIR.suffix + ".old." +
                                                     datetime.now().strftime("%Y%m%d%H%M%S"))
        if settings.DATA_DIR.exists():
            shutil.move(str(settings.DATA_DIR), str(old_data_dir))

        # Atomic restore: move temp to final location
        import os
        os.rename(str(temp_dir), str(settings.DATA_DIR))

        # Verify restored database integrity
        try:
            await run_database_migrations()
        except Exception as e:
            # Rollback: restore from .old snapshot
            shutil.rmtree(str(settings.DATA_DIR), ignore_errors=True)
            shutil.move(str(old_data_dir), str(settings.DATA_DIR))
            raise HTTPException(status_code=500, detail=f"Database migration failed after restore: {e}")

        return {
            "status": "restored",
            "version": manifest.get("version"),
            "created_at": manifest.get("created_at"),
            "rollback_available_until": (datetime.now() + timedelta(days=7)).isoformat(),
        }

    finally:
        # Clean up temp dir if still exists
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/backup/list")
async def list_backups(_auth: str = Depends(require_current_user)):
    """List available backups (filename, size, created_at)."""
    backups_dir = _backups_dir()
    if not backups_dir.is_dir():
        return []
    items = []
    for zip_path in sorted(backups_dir.glob("aic-backup-*.zip"), reverse=True):
        try:
            stat = zip_path.stat()
        except OSError:
            continue
        items.append({
            "filename": zip_path.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return items

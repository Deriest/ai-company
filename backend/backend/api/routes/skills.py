"""Skill management routes — list, toggle, assign, create custom skills."""
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.api.dependencies import require_current_user
from backend.skill_engine import (
    list_skills, toggle_skill, assign_skill_workers, seed_builtin_skills,
)
from storage.models import SkillEntry
from sqlalchemy import select

router = APIRouter(dependencies=[Depends(require_current_user)])

logger = logging.getLogger("aic.skills")


def _installed_skill_root() -> Path:
    base = os.environ.get("AIC_DATA_DIR", "").strip()
    # skills.py = backend/backend/api/routes/skills.py → parents[4] = repo root
    return Path(base) / "skills" / "github" if base else Path(__file__).resolve().parents[4] / "data" / "skills" / "github"


@router.post("/skills/install-github")
async def install_github_skill(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Install one skill or a package of skills from a public GitHub repo."""
    requested = str(payload.get("repo_url", "")).strip().rstrip("/")
    path_hint = str(payload.get("skill_path", "")).strip().strip("/")
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/[^/]+(?:/(.*))?)?", requested)
    if not match:
        raise HTTPException(status_code=400, detail="Use a GitHub repository or folder URL")
    repo_url = f"https://github.com/{match.group(1)}/{match.group(2)}.git"
    skill_path = path_hint or (match.group(3) or "")
    temp_dir = Path(tempfile.mkdtemp(prefix="aic-skill-"))
    try:
        result = await asyncio.to_thread(subprocess.run, ["git", "clone", "--depth", "1", repo_url, str(temp_dir / "repo")], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("Skill install failed (repo=%s): clone exited %s: %s",
                           repo_url, result.returncode, result.stderr[-300:])
            raise HTTPException(status_code=400, detail=f"GitHub clone failed: {result.stderr[-300:]}")
        root = (temp_dir / "repo" / skill_path).resolve()
        repo_root = (temp_dir / "repo").resolve()
        if repo_root not in root.parents and root != repo_root:
            raise HTTPException(status_code=400, detail="Invalid skill path")
        files = []
        for name in ("SKILL.md", "skill.md", "skill.yaml", "skill.yml", "skill.json"):
            files.extend(root.rglob(name))
        if not files:
            readme = root / "README.md"
            files = [readme] if readme.exists() else list(root.rglob("README.md"))[:1]
        if not files:
            raise HTTPException(status_code=400, detail="No supported skill/package file found")
        installed = []
        for skill_file in files:
            raw = skill_file.read_text(encoding="utf-8", errors="replace")
            metadata = {}
            if skill_file.suffix.lower() == ".json":
                try: metadata = json.loads(raw)
                except json.JSONDecodeError: metadata = {}
            front = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
            if front:
                for line in front.group(1).splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1); metadata[key.strip()] = value.strip().strip("'\"")
                instructions = raw[front.end():].strip()
            else:
                instructions = raw.strip()
            heading = next((line.lstrip("#").strip() for line in raw.splitlines() if line.startswith("#")), "")
            parsed_name = str(metadata.get("name") or heading or skill_file.parent.name).strip()
            skill_id = re.sub(r"[^a-z0-9-]+", "-", parsed_name.lower()).strip("-")[:80]
            if not skill_id: continue
            # Preserve the complete skill package: scripts, references,
            # templates, examples, assets, plugin metadata, and SKILL.md.
            package_dir = _installed_skill_root() / skill_id
            package_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_file.parent, package_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))
            instructions = f"{instructions}\n\n[Skill package resources: {package_dir}]"
            result = await db.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
            entry = result.scalar_one_or_none()
            if entry:
                entry.name = parsed_name; entry.description = metadata.get("description", ""); entry.instructions = instructions; entry.source = "github"; entry.category = metadata.get("category", "github")
            else:
                entry = SkillEntry(skill_id=skill_id, name=parsed_name, description=metadata.get("description", ""), category=metadata.get("category", "github"), source="github", instructions=instructions, assigned_workers=[], is_enabled=True); db.add(entry)
            installed.append(entry)
        if not installed: 
            logger.warning("Skill install failed (repo=%s): no usable skills found", repo_url)
            raise HTTPException(status_code=400, detail="No usable skills found")
        await db.commit()
        for entry in installed: await db.refresh(entry)
        logger.info(
            "Skill(s) installed from repo=%s: skill_ids=%s",
            repo_url, [e.skill_id for e in installed],
        )
        return {"installed": [{"id": e.id, "skill_id": e.skill_id, "name": e.name, "description": e.description, "category": e.category, "source": e.source, "assigned_workers": e.assigned_workers, "is_enabled": e.is_enabled, "instructions": e.instructions} for e in installed]}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/skills")
async def get_skills(enabled_only: bool = False, db: AsyncSession = Depends(get_db)):
    """List all registered skills."""
    skills = await list_skills(db, enabled_only=enabled_only)
    return skills


@router.post("/skills/{skill_id}/toggle")
async def toggle_skill_endpoint(
    skill_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Enable or disable a skill."""
    is_enabled = payload.get("enabled", True)
    success = await toggle_skill(db, skill_id, is_enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill_id": skill_id, "is_enabled": is_enabled}


@router.post("/skills/{skill_id}/assign")
async def assign_workers_endpoint(
    skill_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Update worker type assignments for a skill."""
    workers = payload.get("workers", [])
    success = await assign_skill_workers(db, skill_id, workers)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill_id": skill_id, "assigned_workers": workers}


@router.post("/skills")
async def create_custom_skill(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Create a custom user-defined skill."""
    skill_id = payload.get("skill_id", "")
    if not skill_id:
        raise HTTPException(status_code=400, detail="skill_id is required")

    # Check for duplicates
    res = await db.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Skill '{skill_id}' already exists")

    entry = SkillEntry(
        skill_id=skill_id,
        name=payload.get("name", skill_id),
        description=payload.get("description", ""),
        category=payload.get("category", "custom"),
        source="custom",
        instructions=payload.get("instructions", ""),
        assigned_workers=payload.get("assigned_workers", []),
        is_enabled=payload.get("is_enabled", True),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info("Skill created: skill_id=%s name=%s source=custom", entry.skill_id, entry.name)

    return {
        "id": entry.id,
        "skill_id": entry.skill_id,
        "name": entry.name,
        "description": entry.description,
        "category": entry.category,
        "source": entry.source,
        "assigned_workers": entry.assigned_workers,
        "is_enabled": entry.is_enabled,
        "instructions": entry.instructions,
    }


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_current_user),
):
    """Delete a custom skill (cannot delete built-in skills)."""
    res = await db.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
    skill = res.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    if skill.source == "built-in":
        raise HTTPException(status_code=403, detail="Cannot delete built-in skills")
    await db.delete(skill)
    await db.commit()
    shutil.rmtree(_installed_skill_root() / skill_id, ignore_errors=True)
    logger.info("Skill deleted: skill_id=%s name=%s", skill_id, skill.name)
    return {"status": "ok"}


@router.post("/skills/seed")
async def reseed_skills(db: AsyncSession = Depends(get_db)):
    """Re-seed built-in skills (idempotent)."""
    await seed_builtin_skills(db)
    return {"status": "ok"}

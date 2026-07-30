"""Skill management routes — list, toggle, assign, create custom skills."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.skill_engine import (
    list_skills, toggle_skill, assign_skill_workers, seed_builtin_skills,
)
from storage.models import SkillEntry
from sqlalchemy import select

router = APIRouter()


@router.get("/skills")
async def get_skills(enabled_only: bool = False, db: AsyncSession = Depends(get_db)):
    """List all registered skills."""
    skills = await list_skills(db, enabled_only=enabled_only)
    return skills


@router.post("/skills/{skill_id}/toggle")
async def toggle_skill_endpoint(skill_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Enable or disable a skill."""
    is_enabled = payload.get("enabled", True)
    success = await toggle_skill(db, skill_id, is_enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill_id": skill_id, "is_enabled": is_enabled}


@router.post("/skills/{skill_id}/assign")
async def assign_workers_endpoint(skill_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Update worker type assignments for a skill."""
    workers = payload.get("workers", [])
    success = await assign_skill_workers(db, skill_id, workers)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill_id": skill_id, "assigned_workers": workers}


@router.post("/skills")
async def create_custom_skill(payload: dict, db: AsyncSession = Depends(get_db)):
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
async def delete_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a custom skill (cannot delete built-in skills)."""
    res = await db.execute(select(SkillEntry).where(SkillEntry.skill_id == skill_id))
    skill = res.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    if skill.source == "built-in":
        raise HTTPException(status_code=403, detail="Cannot delete built-in skills")
    await db.delete(skill)
    await db.commit()
    return {"status": "ok"}


@router.post("/skills/seed")
async def reseed_skills(db: AsyncSession = Depends(get_db)):
    """Re-seed built-in skills (idempotent)."""
    await seed_builtin_skills(db)
    return {"status": "ok"}

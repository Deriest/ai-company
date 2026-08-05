"""Project management routes — CRUD, active project, scoping."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from typing import Optional

from backend.database.session import get_db
from backend.models.local_profile import LocalProfile
from backend.models.conversation import Attachment
from backend.services.attachment_store import delete_attachment
from storage.models import Project

router = APIRouter()


async def _get_active_project_id(db: AsyncSession) -> Optional[str]:
    res = await db.execute(select(LocalProfile).limit(1))
    profile = res.scalars().first()
    return profile.active_project_id if profile else None


async def _set_active_project_id(db: AsyncSession, project_id: Optional[str]) -> None:
    res = await db.execute(select(LocalProfile).limit(1))
    profile = res.scalars().first()
    if profile:
        profile.active_project_id = project_id
        await db.commit()


# ── Schemas ──────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    repo_path: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repo_path: Optional[str] = None
    status: Optional[str] = None


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description or "",
        "repo_path": p.repo_path,
        "status": p.status,
        "config": p.config or {},
        "owner_id": p.owner_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


# ── GET /projects — List all projects ───────────────────────────

@router.get("/projects")
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).offset(skip).limit(limit))
    projects = result.scalars().all()
    return [_project_dict(p) for p in projects]


# ── POST /projects — Create project ─────────────────────────────

@router.post("/projects", status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    slug = _slugify(body.name)

    existing = await db.execute(select(Project).where(Project.slug == slug))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail=f"Project with slug '{slug}' already exists")

    project = Project(
        name=body.name,
        slug=slug,
        description=body.description,
        repo_path=body.repo_path,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_dict(project)


# ── GET /projects/active — Get active project ───────────────────

@router.get("/projects/active")
async def get_active_project(db: AsyncSession = Depends(get_db)):
    active_id = await _get_active_project_id(db)
    if not active_id:
        return None

    result = await db.execute(select(Project).where(Project.id == active_id))
    project = result.scalars().first()
    if not project:
        await _set_active_project_id(db, None)
        return None

    return _project_dict(project)


# ── GET /projects/{id} — Get project detail ─────────────────────

@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_dict(project)


# ── PATCH /projects/{id} — Update project ───────────────────────

@router.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        project.name = body.name
        project.slug = _slugify(body.name)
    if body.description is not None:
        project.description = body.description
    if body.repo_path is not None:
        project.repo_path = body.repo_path
    if body.status is not None:
        project.status = body.status

    await db.commit()
    await db.refresh(project)
    return _project_dict(project)


# ── DELETE /projects/{id} — Delete project ──────────────────────

@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    active_id = await _get_active_project_id(db)
    if active_id == project_id:
        await _set_active_project_id(db, None)

    # FIX: delete child rows explicitly before the project. FK enforcement is now
    # ON, so tasks/milestones/memory_entries (FK → projects.id) must be removed
    # first; leases/approvals/workflow_states reference tasks and go first of all.
    await db.execute(text(
        "DELETE FROM leases WHERE task_id IN (SELECT id FROM tasks WHERE project_id = :pid)"
    ), {"pid": project_id})
    await db.execute(text(
        "DELETE FROM approvals WHERE task_id IN (SELECT id FROM tasks WHERE project_id = :pid)"
    ), {"pid": project_id})
    await db.execute(text(
        "DELETE FROM workflow_states WHERE task_id IN (SELECT id FROM tasks WHERE project_id = :pid)"
    ), {"pid": project_id})
    # Subtasks first (self-referential FK on tasks.parent_task_id) — a single
    # DELETE of all project tasks would also work, but deleting children first
    # is robust against cross-project parent references.
    await db.execute(text(
        "DELETE FROM tasks WHERE parent_task_id IN (SELECT id FROM tasks WHERE project_id = :pid)"
    ), {"pid": project_id})
    await db.execute(text("DELETE FROM tasks WHERE project_id = :pid"), {"pid": project_id})
    await db.execute(text("DELETE FROM milestones WHERE project_id = :pid"), {"pid": project_id})
    # Project's conversations: clear discovery_sessions, their messages'
    # attachments, and messages (FK → conversations, no ondelete) BEFORE the
    # raw-SQL delete — raw SQL bypasses the ORM cascade on Message.messages.
    # Round-6 FIX: also purge the project's FTS5 rows (search_fts) before the
    # conversations are gone — deleted project content must not stay searchable
    # via /conversations/search.
    await db.execute(text(
        "DELETE FROM search_fts WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = :pid)"
    ), {"pid": project_id})
    await db.execute(text(
        "DELETE FROM discovery_sessions WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = :pid)"
    ), {"pid": project_id})
    # Collect attachment ids BEFORE deleting the rows so their binary files can
    # be removed from DATA_DIR/attachments/ (round-4 cleanup deletes the rows;
    # this keeps the on-disk binaries in sync).
    att_res = await db.execute(text(
        "SELECT id FROM attachments WHERE message_id IN (SELECT id FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = :pid))"
    ), {"pid": project_id})
    att_ids = [row[0] for row in att_res.all()]
    await db.execute(text(
        "DELETE FROM attachments WHERE message_id IN (SELECT id FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = :pid))"
    ), {"pid": project_id})
    await db.execute(text(
        "DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id = :pid)"
    ), {"pid": project_id})
    # conversations (conversation_tags/pins cascade via DB ondelete CASCADE)
    await db.execute(text("DELETE FROM conversations WHERE project_id = :pid"), {"pid": project_id})
    await db.execute(text("DELETE FROM memory_entries WHERE project_id = :pid"), {"pid": project_id})

    await db.delete(project)
    await db.commit()
    for att_id in att_ids:
        delete_attachment(att_id)
    return None


# ── POST /projects/{id}/activate — Set active project ───────────

@router.post("/projects/{project_id}/activate")
async def activate_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await _set_active_project_id(db, project_id)
    return {"active_project_id": project_id, "name": project.name}

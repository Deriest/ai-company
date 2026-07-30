"""AIC Platform — Durable Selective Memory Engine.

Manages persistent project and organizational memory:
- Logical Scopes: user, organization, project, agent
- Categories: convention, decision, constraint, architecture
- Selective retrieval filtering out superseded entries
- Project scope isolation (Project A memory never leaks to Project B)
"""
from datetime import datetime, timezone
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import MemoryEntry

logger = logging.getLogger("aic.memory")


def _utcnow():
    return datetime.now(timezone.utc)


async def save_memory_entry(
    session: AsyncSession,
    key: str,
    value: str,
    project_id: str | None = None,
    scope: str = "project",
    category: str = "convention",
    importance: float = 1.0,
) -> MemoryEntry:
    """Save a durable memory entry into SQLite DB."""
    entry = MemoryEntry(
        project_id=project_id,
        scope=scope,
        category=category,
        key=key,
        value=value,
        importance=importance,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(entry)
    await session.commit()
    logger.info(f"Saved memory entry [{category}:{scope}] key='{key}' for project={project_id}")
    return entry


async def retrieve_project_memories(
    session: AsyncSession,
    project_id: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Retrieve active, non-superseded memory entries scoped to a project."""
    stmt = select(MemoryEntry).where(MemoryEntry.superseded_by == None)
    if project_id:
        stmt = stmt.where((MemoryEntry.project_id == project_id) | (MemoryEntry.scope == "user"))
    else:
        stmt = stmt.where(MemoryEntry.scope.in_(["user", "organization"]))

    stmt = stmt.order_by(MemoryEntry.importance.desc(), MemoryEntry.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    entries = res.scalars().all()

    output = []
    for m in entries:
        output.append({
            "id": m.id,
            "key": m.key,
            "value": m.value,
            "scope": m.scope,
            "category": m.category,
            "project_id": m.project_id,
        })
    return output


async def supersede_memory_entry(
    session: AsyncSession,
    old_memory_id: str,
    new_value: str,
) -> MemoryEntry | None:
    """Supersede an existing memory entry with updated knowledge."""
    old_entry = await session.get(MemoryEntry, old_memory_id)
    if not old_entry:
        return None

    new_entry = MemoryEntry(
        project_id=old_entry.project_id,
        scope=old_entry.scope,
        category=old_entry.category,
        key=old_entry.key,
        value=new_value,
        importance=old_entry.importance,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(new_entry)
    await session.flush()

    old_entry.superseded_by = new_entry.id
    await session.commit()
    logger.info(f"Superseded memory entry {old_memory_id} with new entry {new_entry.id}")
    return new_entry

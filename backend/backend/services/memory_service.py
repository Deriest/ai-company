"""
Memory Engine Service.

Multi-scope memory: session, conversation, workspace, project, user.
Supports CRUD, retrieval by scope/category/importance, and compression.
"""

import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func as sqlfunc, desc
from storage.models import MemoryEntry


class MemoryService:
    """Multi-scope memory management with retrieval and compression."""

    @staticmethod
    async def store(
        db: AsyncSession,
        scope: str,
        key: str,
        value: dict,
        scope_id: Optional[str] = None,
        category: Optional[str] = None,
        importance: float = 0.5,
        expires_at: Optional[datetime.datetime] = None,
    ) -> MemoryEntry:
        # Upsert: update if exists, create if not
        query = select(MemoryEntry).where(
            MemoryEntry.scope == scope,
            MemoryEntry.key == key,
            MemoryEntry.is_active == True,
        )
        if scope_id:
            query = query.where(MemoryEntry.scope_id == scope_id)

        res = await db.execute(query)
        existing = res.scalars().first()

        if existing:
            existing.value = value
            existing.importance = importance
            existing.category = category or existing.category
            # M3: SQL-side increment — immune to concurrent lost-updates
            existing.access_count = MemoryEntry.access_count + 1
            existing.accessed_at = datetime.datetime.now(datetime.timezone.utc)
            if expires_at:
                existing.expires_at = expires_at
            await db.commit()
            await db.refresh(existing)
            return existing

        entry = MemoryEntry(
            scope=scope,
            scope_id=scope_id,
            key=key,
            value=value,
            category=category,
            importance=importance,
            expires_at=expires_at,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def retrieve(
        db: AsyncSession,
        scope: str,
        key: Optional[str] = None,
        scope_id: Optional[str] = None,
        category: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        query = select(MemoryEntry).where(
            MemoryEntry.scope == scope,
            MemoryEntry.is_active == True,
            MemoryEntry.importance >= min_importance,
        )
        if key:
            query = query.where(MemoryEntry.key == key)
        if scope_id:
            query = query.where(MemoryEntry.scope_id == scope_id)
        if category:
            query = query.where(MemoryEntry.category == category)

        # Filter expired
        now = datetime.datetime.now(datetime.timezone.utc)
        query = query.where(
            (MemoryEntry.expires_at == None) | (MemoryEntry.expires_at > now)
        )

        query = query.order_by(desc(MemoryEntry.importance), desc(MemoryEntry.accessed_at)).limit(limit)
        res = await db.execute(query)
        entries = list(res.scalars().all())

        # Update access count
        for e in entries:
            e.access_count += 1
            e.accessed_at = now
        if entries:
            await db.commit()

        return entries

    @staticmethod
    async def forget(db: AsyncSession, entry_id: str):
        res = await db.execute(select(MemoryEntry).where(MemoryEntry.id == entry_id))
        entry = res.scalars().first()
        if entry:
            entry.is_active = False
            await db.commit()

    @staticmethod
    async def compress(
        db: AsyncSession, scope: str, scope_id: Optional[str] = None, threshold: float = 0.3
    ) -> Optional[MemoryEntry]:
        """Compress low-importance entries into a single summary entry."""
        query = select(MemoryEntry).where(
            MemoryEntry.scope == scope,
            MemoryEntry.is_active == True,
            MemoryEntry.importance < threshold,
        )
        if scope_id:
            query = query.where(MemoryEntry.scope_id == scope_id)

        res = await db.execute(query)
        entries = list(res.scalars().all())
        if len(entries) < 3:
            return None

        # Create compressed entry
        source_ids = [e.id for e in entries]
        combined_values = {e.key: e.value for e in entries}
        avg_importance = sum(e.importance for e in entries) / len(entries)

        compressed = MemoryEntry(
            scope=scope,
            scope_id=scope_id,
            key=f"compressed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            value={"compressed": combined_values, "source_count": len(entries)},
            category="summary",
            importance=min(avg_importance + 0.1, 1.0),
            compressed_from=source_ids,
        )
        db.add(compressed)

        # Deactivate source entries
        for e in entries:
            e.is_active = False

        await db.commit()
        await db.refresh(compressed)
        return compressed

    @staticmethod
    async def stats(db: AsyncSession, scope: Optional[str] = None) -> dict:
        query = select(
            sqlfunc.count(MemoryEntry.id),
            sqlfunc.avg(MemoryEntry.importance),
            sqlfunc.sum(MemoryEntry.access_count),
        ).where(MemoryEntry.is_active == True)
        if scope:
            query = query.where(MemoryEntry.scope == scope)

        res = await db.execute(query)
        row = res.first()
        return {
            "total_entries": row[0] or 0,
            "avg_importance": float(row[1] or 0),
            "total_accesses": row[2] or 0,
        }


memory_service = MemoryService()

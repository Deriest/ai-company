from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database.session import get_db
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)])

from backend.services.memory_service import memory_service


# ── Memory Engine Endpoints ──────────────────────────────────

@router.post("/memory")
async def store_memory(payload: dict, db: AsyncSession = Depends(get_db)):
    scope = payload.get("scope")
    key = payload.get("key")
    value = payload.get("value")
    if not scope or not key or value is None:
        raise HTTPException(status_code=400, detail="scope, key and value are required")
    entry = await memory_service.store(
        db,
        scope=scope,
        key=key,
        value=value,
        scope_id=payload.get("scope_id"),
        category=payload.get("category"),
        importance=payload.get("importance", 0.5),
    )
    return {
        "id": entry.id, "scope": entry.scope, "key": entry.key,
        "value": entry.value, "importance": entry.importance,
        "category": entry.category, "accessCount": entry.access_count,
    }

@router.get("/memory")
async def retrieve_memory(
    scope: str = Query(...),
    key: Optional[str] = Query(None),
    scope_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_importance: float = Query(0.0),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    entries = await memory_service.retrieve(db, scope, key, scope_id, category, min_importance, limit)
    return [
        {
            "id": e.id, "scope": e.scope, "key": e.key, "value": e.value,
            "importance": e.importance, "category": e.category,
            "accessCount": e.access_count, "accessedAt": e.accessed_at.isoformat() if e.accessed_at else None,
        }
        for e in entries
    ]

@router.delete("/memory/{entry_id}")
async def forget_memory(entry_id: str, db: AsyncSession = Depends(get_db)):
    await memory_service.forget(db, entry_id)
    return {"status": "ok"}

@router.post("/memory/compress")
async def compress_memory(payload: dict, db: AsyncSession = Depends(get_db)):
    scope = payload.get("scope")
    if not scope:
        raise HTTPException(status_code=400, detail="scope is required")
    result = await memory_service.compress(
        db, scope=scope,
        scope_id=payload.get("scope_id"),
        threshold=payload.get("threshold", 0.3),
    )
    if result:
        return {"id": result.id, "compressed": True}
    return {"compressed": False, "reason": "Not enough entries to compress"}

@router.get("/memory/stats")
async def memory_stats(scope: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return await memory_service.stats(db, scope)

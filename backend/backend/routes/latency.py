"""AIC-ADE — Latency Statistics API Route.

Provides aggregated latency statistics by model tier for visualization.
"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from backend.database.session import get_db
from backend.models.ai_runtime import GenerationLog

logger = logging.getLogger("aic.latency.api")

router = APIRouter(prefix="/latency", tags=["latency"])


@router.get("/stats")
async def get_latency_stats(
    days: Annotated[int, Query(description="Number of days to analyze (default 7)")] = 7,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get aggregated latency statistics by model tier.
    
    Returns averaged latency_ms grouped by model tier over the last N days.
    Useful for performance monitoring and tier comparison.
    """
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    query = (
        select(
            GenerationLog.model_tier,
            func.avg(GenerationLog.latency_ms).label("avg_latency"),
            func.min(GenerationLog.latency_ms).label("min_latency"),
            func.max(GenerationLog.latency_ms).label("max_latency"),
            func.count(GenerationLog.id).label("sample_count"),
        )
        .where(GenerationLog.created_at >= cutoff_date)
        .group_by(GenerationLog.model_tier)
        .order_by(func.avg(GenerationLog.latency_ms))
    )
    
    result = await db.execute(query)
    rows = result.fetchall()
    
    return [
        {
            "tier": row.model_tier,
            "avg_latency_ms": round(float(row.avg_latency), 2) if row.avg_latency else 0,
            "min_latency_ms": row.min_latency or 0,
            "max_latency_ms": row.max_latency or 0,
            "sample_count": row.sample_count,
        }
        for row in rows
    ]


@router.get("/recent/<int:limit>")
async def get_recent_latencies(
    limit: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get recent individual latency measurements.
    
    Returns the most recent N latency entries ordered by creation time descending.
    Useful for detailed inspection of specific requests.
    """
    if limit > 1000:
        limit = 1000  # Safety cap
        
    query = (
        select(GenerationLog)
        .order_by(GenerationLog.created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "model_id": log.model_id,
            "model_tier": log.model_tier,
            "latency_ms": log.latency_ms,
            "status": log.status,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

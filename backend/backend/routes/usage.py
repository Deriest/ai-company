"""AIC Platform — Usage API Routes.

Provides:
- Token usage statistics
- Cost statistics
- Usage by provider/model/time
"""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone

from backend.database.session import get_db
from storage.models import LLMUsageLog
from backend.models.ai_runtime import GenerationLog

logger = logging.getLogger("aic.usage.api")

router = APIRouter()


@router.get("/usage/stats")
async def get_usage_stats(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for the specified period."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    # SQLite DATETIME columns store offset-naive UTC; compare against a naive
    # threshold so the aware cutoff doesn't leak into the SQL-bound value.
    cutoff_naive = cutoff.replace(tzinfo=None)

    # Get LLM usage logs
    result = await db.execute(
        select(
            func.count(LLMUsageLog.id).label("total_requests"),
            func.sum(LLMUsageLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(LLMUsageLog.completion_tokens).label("total_completion_tokens"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.cost_estimate).label("total_cost"),
        ).where(LLMUsageLog.created_at >= cutoff_naive)
    )
    stats = result.first()

    # Get by provider
    provider_result = await db.execute(
        select(
            LLMUsageLog.provider,
            func.count(LLMUsageLog.id).label("requests"),
            func.sum(LLMUsageLog.total_tokens).label("tokens"),
            func.sum(LLMUsageLog.cost_estimate).label("cost"),
        ).where(LLMUsageLog.created_at >= cutoff_naive)
        .group_by(LLMUsageLog.provider)
    )
    by_provider = [
        {
            "provider": row.provider,
            "requests": row.requests,
            "tokens": row.tokens or 0,
            "cost": row.cost or 0.0,
        }
        for row in provider_result.all()
    ]

    # Get by model
    model_result = await db.execute(
        select(
            LLMUsageLog.model,
            func.count(LLMUsageLog.id).label("requests"),
            func.sum(LLMUsageLog.total_tokens).label("tokens"),
            func.sum(LLMUsageLog.cost_estimate).label("cost"),
        ).where(LLMUsageLog.created_at >= cutoff_naive)
        .group_by(LLMUsageLog.model)
    )
    by_model = [
        {
            "model": row.model,
            "requests": row.requests,
            "tokens": row.tokens or 0,
            "cost": row.cost or 0.0,
        }
        for row in model_result.all()
    ]

    return {
        "period_days": days,
        "total_requests": stats.total_requests or 0,
        "total_prompt_tokens": stats.total_prompt_tokens or 0,
        "total_completion_tokens": stats.total_completion_tokens or 0,
        "total_tokens": stats.total_tokens or 0,
        "total_cost": round(stats.total_cost or 0.0, 4),
        "by_provider": by_provider,
        "by_model": by_model,
    }


@router.get("/usage/daily")
async def get_daily_usage(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get daily usage statistics."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    # Compare against a naive UTC threshold (SQLite stores naive datetimes).
    cutoff_naive = cutoff.replace(tzinfo=None)

    result = await db.execute(
        select(
            func.date(LLMUsageLog.created_at).label("date"),
            func.count(LLMUsageLog.id).label("requests"),
            func.sum(LLMUsageLog.total_tokens).label("tokens"),
            func.sum(LLMUsageLog.cost_estimate).label("cost"),
        ).where(LLMUsageLog.created_at >= cutoff_naive)
        .group_by(func.date(LLMUsageLog.created_at))
        .order_by(func.date(LLMUsageLog.created_at))
    )

    daily = [
        {
            "date": str(row.date),
            "requests": row.requests,
            "tokens": row.tokens or 0,
            "cost": round(row.cost or 0.0, 4),
        }
        for row in result.all()
    ]

    return {
        "period_days": days,
        "daily": daily,
    }


@router.get("/usage/recent")
async def get_recent_usage(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get recent usage entries."""
    result = await db.execute(
        select(LLMUsageLog)
        .order_by(LLMUsageLog.created_at.desc())
        .limit(limit)
    )

    entries = [
        {
            "id": entry.id,
            "provider": entry.provider,
            "model": entry.model,
            "tier": entry.tier,
            "purpose": entry.purpose,
            "prompt_tokens": entry.prompt_tokens,
            "completion_tokens": entry.completion_tokens,
            "total_tokens": entry.total_tokens,
            "cost_estimate": entry.cost_estimate,
            "latency_ms": entry.latency_ms,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in result.scalars().all()
    ]

    return {
        "entries": entries,
        "count": len(entries),
    }


@router.get("/usage/pricing")
async def get_pricing():
    """Get provider pricing information."""
    from backend.services.pricing_service import get_pricing_service

    pricing_service = get_pricing_service()
    pricing = pricing_service.get_all_pricing()

    return {
        "pricing": pricing,
        "count": len(pricing),
    }


@router.get("/usage/session/{conversation_id}")
async def get_session_usage(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get total cost and token usage for a specific conversation session."""
    result = await db.execute(
        select(
            func.count(GenerationLog.id).label("total_requests"),
            func.sum(GenerationLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(GenerationLog.completion_tokens).label("total_completion_tokens"),
            func.sum(GenerationLog.total_tokens).label("total_tokens"),
            func.sum(GenerationLog.latency_ms).label("total_latency_ms"),
        ).where(GenerationLog.conversation_id == conversation_id)
    )
    stats = result.first()

    total_prompt = stats.total_prompt_tokens or 0
    total_completion = stats.total_completion_tokens or 0
    estimated_cost = (total_prompt * 0.000003 + total_completion * 0.000015)

    return {
        "conversation_id": conversation_id,
        "total_requests": stats.total_requests or 0,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": stats.total_tokens or 0,
        "total_latency_ms": stats.total_latency_ms or 0,
        "estimated_cost": round(estimated_cost, 6),
    }

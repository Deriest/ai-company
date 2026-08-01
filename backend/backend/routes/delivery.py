"""AIC Platform — Delivery & Continuous Improvement API Routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session

logger = logging.getLogger("aic.delivery.api")

router = APIRouter()


class DeliverRequest(BaseModel):
    brief_id: str
    plan_id: str = ""
    graph_id: str = ""
    verification_id: str = ""
    task_results: dict | None = None


@router.post("/deliver")
async def deliver(
    req: DeliverRequest,
    session: AsyncSession = Depends(get_session),
):
    """Complete delivery pipeline."""
    from delivery.engine import DeliveryEngine

    engine = DeliveryEngine(session)
    result = await engine.deliver(
        brief_id=req.brief_id,
        plan_id=req.plan_id,
        graph_id=req.graph_id,
        verification_id=req.verification_id,
        task_results=req.task_results,
    )

    return {
        "report": result.report.to_dict() if result.report else None,
        "message": result.message,
        "metadata": result.metadata,
    }


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get delivery statistics."""
    from delivery.engine import DeliveryEngine

    engine = DeliveryEngine(session)
    stats = engine.get_stats()

    return stats


@router.get("/brief/{brief_id}")
async def get_report_for_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get engineering report for a brief."""
    from storage.models import EngineeringReport

    result = await session.execute(
        select(EngineeringReport)
        .where(EngineeringReport.brief_id == brief_id)
        .order_by(EngineeringReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "No report found for this brief")

    return {
        "id": report.id,
        "brief_id": report.brief_id,
        "outcome": report.outcome,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get an engineering report by ID."""
    from storage.models import EngineeringReport

    result = await session.execute(
        select(EngineeringReport).where(EngineeringReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Engineering Report not found")

    return {
        "id": report.id,
        "brief_id": report.brief_id,
        "goal": report.goal,
        "outcome": report.outcome,
        "total_tasks": report.total_tasks,
        "successful_tasks": report.successful_tasks,
        "failed_tasks": report.failed_tasks,
        "lessons": report.lessons or [],
        "recommendations": report.recommendations or [],
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

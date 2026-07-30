"""AIC Platform — Autonomous Execution Intelligence API Routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session

logger = logging.getLogger("aic.autonomy.api")

router = APIRouter()


class DetectAnomalyRequest(BaseModel):
    anomaly_type: str
    severity: str
    description: str
    affected_component: str = ""


class HandleAnomalyRequest(BaseModel):
    anomaly_type: str
    severity: str
    description: str
    affected_component: str = ""


@router.post("/detect")
async def detect_anomaly(
    req: DetectAnomalyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Detect and record an anomaly."""
    from autonomy.engine import AutonomyEngine

    engine = AutonomyEngine(session)
    anomaly = await engine.detect_anomaly(
        anomaly_type=req.anomaly_type,
        severity=req.severity,
        description=req.description,
        affected_component=req.affected_component,
    )

    return {
        "id": anomaly.id,
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "description": anomaly.description,
        "affected_component": anomaly.affected_component,
    }


@router.post("/handle")
async def handle_anomaly(
    req: HandleAnomalyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Handle an anomaly with full recovery pipeline."""
    from autonomy.engine import AutonomyEngine

    engine = AutonomyEngine(session)
    result = await engine.handle_anomaly(
        anomaly_type=req.anomaly_type,
        severity=req.severity,
        description=req.description,
        affected_component=req.affected_component,
    )

    return {
        "id": result.id,
        "anomaly_id": result.anomaly_id,
        "action_taken": result.action_taken,
        "success": result.success,
        "details": result.details,
        "attempts": result.attempts,
    }


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get autonomy statistics."""
    from autonomy.engine import AutonomyEngine

    engine = AutonomyEngine(session)
    stats = engine.get_stats()

    return stats

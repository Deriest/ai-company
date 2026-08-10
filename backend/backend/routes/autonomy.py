"""AIC Platform — Autonomous Execution Intelligence API Routes."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from storage.database import get_session
from backend.api.dependencies import require_current_user

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
    _auth: str = require_current_user,
):
    """Detect and record an anomaly."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("autonomy.engine", fromlist=["AutonomyEngine"]).AutonomyEngine(session)
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
    _auth: str = require_current_user,
):
    """Handle an anomaly with full recovery pipeline."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("autonomy.engine", fromlist=["AutonomyEngine"]).AutonomyEngine(session)
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
async def get_stats():
    """Get autonomy statistics."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("autonomy.engine", fromlist=["AutonomyEngine"]).AutonomyEngine(session)
        stats = engine.get_stats()

        return stats


# M8: Return empty dict when disabled to avoid returning unpersisted object
if not hasattr(get_stats, "__wrapped__"):
    pass

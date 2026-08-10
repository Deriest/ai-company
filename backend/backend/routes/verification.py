"""AIC Platform — Verification Engine API Routes."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from storage.database import get_session
from backend.api.dependencies import require_current_user

logger = logging.getLogger("aic.verification.api")

router = APIRouter()


class VerifyRequest(BaseModel):
    brief_id: str
    task_results: dict | None = None


@router.post("/verify")
async def verify_output(
    req: VerifyRequest,
    _auth: str = require_current_user,
):
    """Verify output against acceptance criteria."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("verification.engine", fromlist=["VerificationEngine"]).VerificationEngine(session)
        result = await engine.verify(req.brief_id, req.task_results)

        if result.state == "error":
            raise HTTPException(400, result.message)

        return {
            "state": result.state,
            "report": result.report.to_dict() if result.report else None,
            "message": result.message,
            "metadata": result.metadata,
        }


@router.get("/{verification_id}")
async def get_verification(
    verification_id: str,
):
    """Get verification report."""
    async with get_session(auto_commit=True) as session:
        from storage.models import VerificationSession
        from sqlalchemy import select

        result = await session.execute(
            select(VerificationSession).where(VerificationSession.id == verification_id)
        )
        verification = result.scalar_one_or_none()
        if not verification:
            raise HTTPException(404, "Verification not found")

        return {
            "id": verification.id,
            "brief_id": verification.brief_id,
            "overall_status": verification.overall_status,
            "quality_score": verification.quality_score,
            "created_at": verification.created_at.isoformat() if verification.created_at else None,
        }

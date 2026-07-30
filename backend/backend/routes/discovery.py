"""AIC Platform — Engineering Discovery API Routes.

REST API for discovery session management and Engineering Brief access.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from storage.models import DiscoverySession, EngineeringBrief as EngineeringBriefModel

logger = logging.getLogger("aic.discovery.api")

router = APIRouter()


class ClarificationResponse(BaseModel):
    response: str


@router.get("/{session_id}")
async def get_discovery_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get discovery session status."""
    result = await session.execute(
        select(DiscoverySession).where(DiscoverySession.id == session_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Discovery session not found")

    return {
        "id": ds.id,
        "conversation_id": ds.conversation_id,
        "status": ds.status,
        "round_number": ds.round_number,
        "questions_asked": ds.questions_asked,
        "questions_answered": ds.questions_answered,
        "context": ds.context or {},
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


@router.get("/{session_id}/brief")
async def get_engineering_brief(
    session_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get Engineering Brief for a discovery session."""
    result = await session.execute(
        select(EngineeringBriefModel)
        .where(EngineeringBriefModel.discovery_session_id == session_id)
        .order_by(EngineeringBriefModel.version.desc())
        .limit(1)
    )
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(404, "Engineering Brief not found")

    return {
        "id": brief.id,
        "discovery_session_id": brief.discovery_session_id,
        "version": brief.version,
        "engineering_goal": brief.engineering_goal,
        "user_intent": brief.user_intent,
        "request_category": brief.request_category,
        "scope": brief.scope or {},
        "functional_requirements": brief.functional_requirements or [],
        "non_functional_requirements": brief.non_functional_requirements or [],
        "constraints": brief.constraints or [],
        "assumptions": brief.assumptions or [],
        "dependencies": brief.dependencies or [],
        "risks": brief.risks or [],
        "acceptance_criteria": brief.acceptance_criteria or [],
        "readiness_status": brief.readiness_status,
        "readiness_score": brief.readiness_score,
        "readiness_dimensions": brief.readiness_dimensions or {},
        "outstanding_unknowns": brief.outstanding_unknowns or [],
        "discovery_metadata": brief.discovery_metadata or {},
        "status": brief.status,
        "created_at": brief.created_at.isoformat() if brief.created_at else None,
        "updated_at": brief.updated_at.isoformat() if brief.updated_at else None,
    }


@router.post("/{session_id}/respond")
async def respond_to_clarification(
    session_id: str,
    req: ClarificationResponse,
    session: AsyncSession = Depends(get_session),
):
    """Respond to clarification questions."""
    from discovery.engine import DiscoveryEngine

    # Verify session exists
    result = await session.execute(
        select(DiscoverySession).where(DiscoverySession.id == session_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Discovery session not found")

    # Process response
    engine = DiscoveryEngine(session)
    discovery_result = await engine.respond_to_clarification(
        session_id, req.response
    )

    return {
        "state": discovery_result.state,
        "is_ready": discovery_result.is_ready,
        "message": discovery_result.message,
        "metadata": discovery_result.metadata,
    }


@router.get("/conversation/{conversation_id}")
async def get_discovery_for_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get all discovery sessions for a conversation."""
    result = await session.execute(
        select(DiscoverySession)
        .where(DiscoverySession.conversation_id == conversation_id)
        .order_by(DiscoverySession.created_at.desc())
    )
    sessions = result.scalars().all()

    return [
        {
            "id": ds.id,
            "status": ds.status,
            "round_number": ds.round_number,
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
        }
        for ds in sessions
    ]

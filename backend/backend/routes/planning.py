"""AIC Platform — Planning Engine API Routes.

REST API for planning session management and Engineering Plan access.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from storage.database import get_session
from backend.api.dependencies import require_current_user

logger = logging.getLogger("aic.planning.api")

from fastapi import Depends
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)])


class PlanRequest(BaseModel):
    brief_id: str
    project_context: dict | None = None


@router.post("/generate")
async def generate_plan(
    req: PlanRequest,
    _auth: str = require_current_user,
):
    """Generate an Engineering Plan from a Brief."""
    async with get_session(auto_commit=True) as session:
        engine = __import__("planning.engine", fromlist=["PlanningEngine"]).PlanningEngine(session)
        result = await engine.plan(req.brief_id, req.project_context)

        if result.state == "error":
            raise HTTPException(400, result.message)

        return {
            "state": result.state,
            "plan": result.plan.to_dict() if result.plan else None,
            "message": result.message,
            "metadata": result.metadata,
        }


@router.get("/{plan_id}")
async def get_plan(
    plan_id: str,
):
    """Get an Engineering Plan by ID."""
    async with get_session(auto_commit=True) as session:
        from storage.models import EngineeringPlan as EngineeringPlanModel

        result = await session.execute(
            select(EngineeringPlanModel).where(EngineeringPlanModel.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Engineering Plan not found")

        return {
            "id": plan.id,
            "brief_id": plan.brief_id,
            "engineering_goal": plan.engineering_goal,
            "technical_approach": plan.technical_approach,
            "implementation_strategy": plan.implementation_strategy,
            "architecture_decisions": plan.architecture_decisions or [],
            "risk_mitigations": plan.risk_mitigations or [],
            "dependency_map": plan.dependency_map or {},
            "effort_estimates": plan.effort_estimates or [],
            "acceptance_criteria": plan.acceptance_criteria or [],
            "estimated_duration": plan.estimated_duration,
            "confidence_score": plan.confidence_score,
            "status": plan.status,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }


@router.get("/brief/{brief_id}")
async def get_plan_for_brief(
    brief_id: str,
):
    """Get Engineering Plan for a Brief."""
    async with get_session(auto_commit=True) as session:
        from storage.models import EngineeringPlan as EngineeringPlanModel

        result = await session.execute(
            select(EngineeringPlanModel)
            .where(EngineeringPlanModel.brief_id == brief_id)
            .order_by(EngineeringPlanModel.created_at.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "No plan found for this brief")

        return {
            "id": plan.id,
            "brief_id": plan.brief_id,
            "engineering_goal": plan.engineering_goal,
            "technical_approach": plan.technical_approach,
            "implementation_strategy": plan.implementation_strategy,
            "status": plan.status,
            "confidence_score": plan.confidence_score,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
        }

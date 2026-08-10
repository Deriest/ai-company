"""Auto-approve configuration routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.models.local_profile import LocalProfile
from sqlalchemy.future import select
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)])


class ApprovalScope(BaseModel):
    verifications: bool = True
    lint_type_checks: bool = True
    unit_tests: bool = True
    build_success: bool = True
    security_scan_low: bool = True
    deploy_staging: bool = False
    deploy_production: bool = False


class ApprovalConfigUpdate(BaseModel):
    mode: Optional[str] = None
    scope: Optional[ApprovalScope] = None
    risk_threshold: Optional[str] = None


def default_scope() -> dict:
    return {
        "verifications": True,
        "lint_type_checks": True,
        "unit_tests": True,
        "build_success": True,
        "security_scan_low": True,
        "deploy_staging": False,
        "deploy_production": False,
    }


@router.get("/approval-config")
async def get_approval_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LocalProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return {"mode": "semi", "scope": default_scope(), "risk_threshold": "low"}
    config = profile.approval_config or {}
    return {
        "mode": config.get("mode", "semi"),
        "scope": config.get("scope", default_scope()),
        "risk_threshold": config.get("risk_threshold", "low"),
    }


@router.put("/approval-config")
async def update_approval_config(payload: ApprovalConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LocalProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")
    profile.approval_config = payload.model_dump(exclude_none=True)
    await db.commit()
    return {"status": "ok"}

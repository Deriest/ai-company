"""Local Profile API routes — replaces all auth routes."""

import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.services.profile_service import (
    get_profile, create_profile, update_profile, complete_onboarding,
)
from backend.services.crypto import encrypt

def _is_valid_github_token(token: str) -> bool:
    """Validate GitHub token format."""
    # GitHub personal access tokens start with 'ghp_' followed by 36+ characters
    # https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
    if not isinstance(token, str):
        return False
    # Check for ghp_ prefix
    if not token.startswith("ghp_"):
        return False
    # Check length (minimum 36 chars after prefix, total >= 40)
    if len(token) < 40:
        return False
    # Check for only alphanumeric characters and underscores
    if not re.match(r'^ghp_[a-zA-Z0-9_]+$', token):
        return False
    return True

router = APIRouter(dependencies=[Depends(require_current_user)])dependencies=[Depends(require_current_user)])


@router.get("/profile")
async def read_profile(db: AsyncSession = Depends(get_db)):
    """Get the local profile. Returns 404 if not created yet (first launch)."""
    profile = await get_profile(db)
    if not profile:
        raise HTTPException(status_code=404, detail="No profile — first launch")
    return {
        "id": profile.id,
        "displayName": profile.display_name,
        "deviceId": profile.device_id,
        "appVersion": profile.app_version,
        "onboardingCompleted": profile.onboarding_completed,
        # GHP: never return the token — mask as "***" whenever one is stored
        # (mirrors the providers.py apiKey masking pattern).
        "githubToken": "***" if profile.github_token else "",
        "createdAt": profile.created_at.isoformat() if profile.created_at else None,
        "lastSeen": profile.last_seen.isoformat() if profile.last_seen else None,
    }


@router.post("/profile")
async def create_new_profile(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create local profile on first launch."""
    existing = await get_profile(db)
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists")
    name = payload.get("displayName", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="displayName is required")
    profile = await create_profile(db, name)

    # GHP: persist the GitHub personal token encrypted during setup/onboarding.
    github_token = payload.get("github_token")
    if github_token and github_token != "***":
        # Validate GitHub token format
        if not _is_valid_github_token(github_token):
            raise HTTPException(status_code=400, detail="Invalid GitHub token format. Expected format: ghp_ followed by 36+ characters.")
        profile.github_token = encrypt(github_token)
        await db.commit()
        await db.refresh(profile)

    return {
        "id": profile.id,
        "displayName": profile.display_name,
        "onboardingCompleted": profile.onboarding_completed,
        "githubToken": "***" if profile.github_token else "",
    }


@router.patch("/profile")
async def update_local_profile(payload: dict, db: AsyncSession = Depends(get_db)):
    """Update the local profile."""
    profile = await get_profile(db)
    if not profile:
        raise HTTPException(status_code=404, detail="No profile")

    # GHP: persist the GitHub personal token encrypted (Fernet). A masked "***"
    # value means "leave unchanged" and is skipped (mirrors provider_manage.py);
    # an empty string clears the stored token.
    github_token = payload.get("github_token")
    if github_token is not None and github_token != "***":
        profile.github_token = encrypt(github_token) if github_token else ""

    await update_profile(
        db,
        display_name=payload.get("displayName"),
        app_version=payload.get("appVersion"),
    )
    await db.refresh(profile)

    return {
        "id": profile.id,
        "displayName": profile.display_name,
        "onboardingCompleted": profile.onboarding_completed,
        "githubToken": "***" if profile.github_token else "",
    }


@router.post("/profile/complete-onboarding")
async def finish_onboarding(db: AsyncSession = Depends(get_db)):
    """Mark onboarding as complete."""
    profile = await complete_onboarding(db)
    if not profile:
        raise HTTPException(status_code=404, detail="No profile")
    return {
        "id": profile.id,
        "displayName": profile.display_name,
        "onboardingCompleted": True,
    }

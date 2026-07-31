"""
Local Profile service.

Desktop-first: no authentication, no passwords, no email.
Single local profile stored in SQLite.
"""

import uuid
import platform
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.local_profile import LocalProfile

logger = logging.getLogger(__name__)

CURRENT_VERSION = "2.4.7"


def _generate_device_id() -> str:
    """Generate a deterministic device ID based on machine info."""
    node = platform.node()
    system = platform.system()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{node}-{system}-aic-ade"))


async def get_profile(db: AsyncSession) -> LocalProfile | None:
    """Get the local profile (there's only one)."""
    res = await db.execute(select(LocalProfile).limit(1))
    return res.scalars().first()


async def create_profile(db: AsyncSession, display_name: str) -> LocalProfile:
    """Create the local profile on first launch."""
    profile = LocalProfile(
        display_name=display_name,
        device_id=_generate_device_id(),
        app_version=CURRENT_VERSION,
        onboarding_completed=False,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    logger.info(f"Local profile created: {display_name}")
    return profile


async def update_profile(db: AsyncSession, **kwargs) -> LocalProfile | None:
    """Update the local profile."""
    profile = await get_profile(db)
    if not profile:
        return None
    for key, value in kwargs.items():
        if hasattr(profile, key) and value is not None:
            setattr(profile, key, value)
    profile.last_seen = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return profile


async def complete_onboarding(db: AsyncSession) -> LocalProfile | None:
    """Mark onboarding as complete."""
    return await update_profile(db, onboarding_completed=True)


async def touch_profile(db: AsyncSession):
    """Update last_seen timestamp."""
    profile = await get_profile(db)
    if profile:
        profile.last_seen = datetime.now(timezone.utc)
        await db.commit()

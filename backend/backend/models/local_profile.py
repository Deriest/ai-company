"""
Local Profile model — replaces User/Session authentication.

Desktop-first: no email, no password, no authentication.
Single user stored locally in SQLite.
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from backend.database.session import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class LocalProfile(Base):
    """Single local user profile. Created on first launch."""
    __tablename__ = "local_profile"

    id = Column(String, primary_key=True, default=generate_uuid)
    display_name = Column(String, nullable=False)
    device_id = Column(String, unique=True, nullable=False)
    app_version = Column(String, nullable=True)
    onboarding_completed = Column(Boolean, default=False)
    active_project_id = Column(String, nullable=True)
    # Hybrid workspace resolution (Option C): remembers the last folder a user
    # worked in, so a later task_confirm with no pinned folder auto-resolves to
    # it (and is surfaced in chat for confirmation) instead of asking again.
    last_used_repo_path = Column(String, nullable=True)
    approval_config = Column(JSON, nullable=True)
    # GitHub personal token (GHP) — stored ENCRYPTED via backend.services.crypto
    # (Fernet, per-install key). The API only ever returns "***" when set.
    github_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

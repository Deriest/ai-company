"""Shared FastAPI dependencies — per-install identity token enforcement."""
import logging
import os
from typing import Optional, Set

from fastapi import Depends, HTTPException, Request, status

from backend.api.routes.auth import oauth2_scheme
from auth.security import decode_access_token

logger = logging.getLogger(__name__)

# Test mode flag
_AIC_TESTING = os.environ.get("AIC_TESTING") == "1"
_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """Return authenticated username or None if unauthenticated."""
    if not token and _AIC_TESTING:
        return "test-user"
    if not token:
        return None
    payload = decode_access_token(token)
    if payload and payload.get("sub"):
        return payload["sub"]
    return None


def require_current_user(
    user: Optional[str] = Depends(get_optional_current_user),
) -> str:
    """Guard for sensitive endpoints: 401 when no valid token is present."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers=_AUTH_HEADERS,
        )
    return user


# ── Ownership Validation (GAP-8 Fix) ────────────────────────

from sqlalchemy import select

from storage.models import Conversation, Project, Task

# Resource type to (model_class, owner_column_name) mapping
# Owner column names confirmed from storage/models.py:
#   - Task.created_by → references users.id
#   - Conversation.user_id → references users.id  
#   - Project.owner_id → references users.id
_OWNERSHIP_MODELS = {
    "task": (Task, "created_by"),
    "conversation": (Conversation, "user_id"),
    "project": (Project, "owner_id"),
}


async def validate_ownership(
    db, resource_id: str, resource_type: str, user_id: str,
) -> bool:
    """Defense-in-depth ownership check.
    
    Currently not wired into route handlers; router-level authentication
    is the primary gate for this single-user desktop app.
    
    Validates that the authenticated user owns the specified resource before
    mutation operations. Supports: task, conversation, project.
    
    Args:
        db: Database session (injected by caller)
        resource_id: ID of resource to validate
        resource_type: Type string ('task', 'conversation', 'project')
        user_id: Current authenticated user's ID
        
    Returns:
        True if user owns resource
        
    Raises:
        HTTPException 403 if user doesn't own resource
    """
    try:
        if resource_type not in _OWNERSHIP_MODELS:
            logger.debug(f"Ownership validation skipped: unknown type '{resource_type}'")
            return True
        
        ModelClass, owner_col_name = _OWNERSHIP_MODELS[resource_type]
        
        # Build query with real SQLAlchemy model class
        stmt = select(ModelClass).where(
            ModelClass.id == resource_id,
            getattr(ModelClass, owner_col_name) == user_id
        )
        
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            # No record found or record doesn't belong to user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to modify this {resource_type}",
            )
        
        return True
    except HTTPException:
        # Re-raise HTTP exceptions (ownership violations)
        raise
    except Exception as e:
        # Fail open on infrastructure errors - log warning but allow operation
        logger.warning(f"Ownership validation skipped due to error: {e}")
        return False

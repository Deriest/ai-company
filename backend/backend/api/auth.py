"""Role-based authentication and authorization."""

from enum import Enum
from typing import Set


class Role(str, Enum):
    """User role hierarchy (lowest to highest)."""
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"
    SUPERUSER = "superuser"


def require_roles(*allowed_roles: Role):
    """Authorization decorator requiring user has one of allowed roles.

    Wired to require_current_user so the JWT is validated first; on single-user
    desktop every authenticated caller has Role.USER. Sensitive routers (backup,
    provider config) should depend on require_roles(Role.ADMIN) once multi-user
    lands — the seam is kept here so wiring is a one-line change per router.
    """
    from fastapi import Depends, HTTPException, status, Request
    from backend.api.dependencies import require_current_user

    async def role_checker(
        request: Request,
        current_user: str = Depends(require_current_user),
    ) -> str:
        # Placeholder - in production this checks database for user roles
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # For now, authenticated users have at least USER role
        user_roles: Set[Role] = {Role.USER}

        if any(role in user_roles for role in allowed_roles):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role(s): {', '.join([r.value for r in allowed_roles])}",
        )

    return role_checker

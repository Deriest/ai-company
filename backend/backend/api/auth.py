"""Role-based authentication and authorization."""

from enum import Enum
from typing import Optional, Set


class Role(str, Enum):
    """User role hierarchy (lowest to highest)."""
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"
    SUPERUSER = "superuser"


def require_roles(*allowed_roles: Role):
    """Authorization decorator requiring user has one of allowed roles."""
    from fastapi import Depends, HTTPException, status, Request
    
    async def role_checker(
        request: Request,
        current_user: Optional[str] = None,
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

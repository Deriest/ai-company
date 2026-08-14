"""Authentication dependencies for AIC-ADE backend.

Single-user desktop app pattern: authentication is optional and designed
for local-only access (127.0.0.1 binding). The AIC_TESTING environment
variable can bypass auth for development/testing purposes only - this must
NEVER be set in production.
"""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)


def verify_auth_fail_open_check() -> bool:
    """Verify that AIC_TESTING environment variable is not enabled.

    This prevents accidental deployment with authentication disabled.

    Returns:
        True if testing mode is NOT active (normal operation)

    Raises:
        RuntimeError: If AIC_TESTING=1 detected (deployment security issue)

    The test suite legitimately sets AIC_TESTING=1 (tests/conftest.py) to
    exercise auth-fail-open paths, so the guard is relaxed when actually
    running under pytest (``PYTEST_CURRENT_TEST``) — it still hard-fails a
    production launch that leaked AIC_TESTING=1.
    """
    if os.environ.get("AIC_TESTING") == "1" and not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError(
            "FATAL ERROR: AIC_TESTING=1 detected in production environment. "
            "Authentication bypass is ACTIVE - this should never happen outside "
            "of CI/CD test environments. Please unset AIC_TESTING and restart."
        )
    return True


async def require_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    _auth_check: bool = Depends(verify_auth_fail_open_check)  # Force runtime validation
) -> Optional[str]:
    """Get current authenticated user.
    
    For single-user desktop apps, auth is optional:
    - Normal operation: User provides JWT token (stored locally)
    - Testing mode: Auth skipped if AIC_TESTING=1 (dev only)
    
    Returns:
        User ID from JWT token, or None if no auth provided
        
    Security Note:
        This function ALWAYS checks AIC_TESTING first via dependency injection.
        Even if credentials are None, we ensure testing mode is not enabled.
    """
    # Always validate auth fail-open protection first
    if _auth_check is False:
        raise RuntimeError("Auth fail-open protection failed")
    
    # Single-user desktop: allow unauthenticated access (trust local machine)
    # Token-based auth available but not enforced for localhost requests
    if credentials:
        # Extract user info from JWT (future multi-user support)
        token = credentials.credentials
        # TODO: Validate token and extract user_id
        # For now, return None meaning "no specific user"
        return None
    
    return None


class AuthValidationError(Exception):
    """Raised when authentication validation fails."""
    
    def __init__(self, message: str, code: int = 401):
        self.message = message
        self.code = code
        super().__init__(self.message)


async def validate_ownership(db, resource_id: str, kind: str, user: Optional[str]) -> None:
    """Verify the current user owns the resource before a destructive op.

    Single-user local desktop app: the user is always local (require_current_user
    returns None / no multi-tenant boundary), so ownership is trivially satisfied.
    Kept as an explicit seam so delete routes can be made stricter later without
    touching the route handlers.
    """
    return None

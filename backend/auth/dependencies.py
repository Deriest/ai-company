"""AIC Platform — FastAPI auth dependencies."""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from auth.rbac import has_permission  # noqa: F401  (re-exported for callers)
from auth.security import decode_access_token
from storage.database import get_session
from storage.models import Role, User

# Auto-defines a dependency reading the Authorization: Bearer <token> header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def _to_role(value: str) -> Role | None:
    try:
        return Role(value)
    except ValueError:
        return None


async def _fetch_user(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract user from JWT Bearer token. Raises 401 on missing/invalid/inactive."""
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_exc
    payload = decode_access_token(token)
    if payload is None:
        raise creds_exc
    user_id = payload.get("sub")
    if not user_id:
        raise creds_exc
    user = await _fetch_user(session, user_id)
    if user is None or not user.is_active:
        raise creds_exc
    return user


async def get_current_user_optional(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Like get_current_user but returns None instead of raising — for public endpoints."""
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await _fetch_user(session, user_id)


def require_roles(*roles: Role) -> Callable:
    """Return a dependency that 403s unless the user's role is in `roles`."""
    allowed = {r.value for r in roles}

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return user

    return _check


def require_permission(permission: str) -> Callable:
    """Return a dependency that 403s unless the user's role grants `permission`."""
    async def _check(user: User = Depends(get_current_user)) -> User:
        role = _to_role(user.role)
        if role is None or not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _check


async def get_user_from_api_key(
    api_key: str = Depends(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract user from X-API-Key header. Validates against user.api_keys list."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    # ponytail: linear scan over users; index api_keys in a KV store if many users.
    # api_keys is JSON list of {"key": "...", ...} — scan for match, validate active user.
    result = await session.execute(
        select(User).where(User.is_active.is_(True))
    )
    for user in result.scalars():
        keys = user.api_keys or []
        if isinstance(keys, list) and any(
            isinstance(k, dict) and k.get("key") == api_key for k in keys
        ):
            return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )

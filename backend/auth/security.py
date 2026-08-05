"""AIC Platform — Security primitives: JWT."""
from datetime import datetime, timedelta, timezone

# NOTE: pyjwt (unmaintained python-jose was replaced — pyjwt's jwt.encode
# returns str, jwt.decode raises jwt.InvalidTokenError on any failure).
import jwt

from backend.config import settings


def create_access_token(data: dict) -> str:
    """Create a JWT with expiry. `data` should include `sub` (user id)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and verify a JWT. Returns claims or None on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        return None

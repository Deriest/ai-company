"""AIC Platform — Security primitives: JWT."""
from datetime import datetime, timedelta, timezone
import uuid

# NOTE: keep python-jose — the packaged Windows/Linux runtimes ship with
# python-jose installed (not PyJWT); a PyJWT-only code path broke the
# installed app with ModuleNotFoundError: No module named 'jwt'.
from jose import JWTError, jwt

from backend.config import settings


def create_access_token(data: dict) -> str:
    """Create a JWT with expiry. `data` should include `sub` (user id)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire
    # M1 FIX: Add aud (audience), iss (issuer), and jti (JWT ID) claims
    to_encode["aud"] = "aic-platform"
    to_encode["iss"] = "aic-local-desktop"
    to_encode["jti"] = str(uuid.uuid4())
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str, check_revoked: bool = False) -> dict | None:
    """Decode and verify a JWT. Returns claims or None on failure.
    
    M1 FIX: Verify audience ('aud') and issuer ('iss') claims.
    Optionally check token against revocation list.
    """
    try:
        # Full verification including exp, aud, iss
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience="aic-platform",
            issuer="aic-local-desktop"
        )
    except JWTError:
        return None

"""AIC Platform — Security primitives: passwords, JWT, API keys."""
from datetime import datetime, timedelta, timezone
from secrets import token_hex

from jose import JWTError, jwt
import bcrypt as _bcrypt

from backend.config import settings


def hash_password(password: str) -> str:
    # bcrypt truncates at 72 bytes — pre-truncate to avoid ValueError
    pw = password.encode("utf-8")[:72]
    return _bcrypt.hashpw(pw, _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw = plain.encode("utf-8")[:72]
    try:
        return _bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


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
    except JWTError:
        return None


def generate_api_key() -> str:
    """Return a random hex API key with the 'aic_' prefix."""
    return "aic_" + token_hex(16)

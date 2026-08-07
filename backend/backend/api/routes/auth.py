"""AIC-ADE — Authentication endpoints for the local desktop identity.

The Electron main process generates a per-install random credential
(identity.json in userData) and passes it to the backend via
AIC_IDENTITY_FILE. The desktop app auto-authenticates silently — these
endpoints only ever serve the local sidecar on 127.0.0.1.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging
import secrets

from backend.config import settings
# NOTE: plaintext compare — the identity file stores a random hex password,
# not a bcrypt hash, so auth.security.verify_password (bcrypt) is not applicable.
from auth.security import create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("aic.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Authenticate against the per-install desktop identity."""
    # Timing-safe comparison: plaintext `!=` leaks the correct length/prefix via
    # short-circuit timing. compare_digest runs in constant time regardless of
    # how many bytes match. Both sides are the per-install random hex credential,
    # so we compare the raw strings (encode to utf-8 bytes). If this ever becomes
    # a hashed password, compare the hash digests with compare_digest instead.
    # TODO(future work): add per-username brute-force lockout / rate limiting here
    # (e.g. exponential backoff after N failed attempts) — not added yet to avoid
    # disrupting the existing test suite.
    if (
        not secrets.compare_digest(
            body.username.encode("utf-8"), settings.IDENTITY_USERNAME.encode("utf-8")
        )
        or not secrets.compare_digest(
            body.password.encode("utf-8"), settings.IDENTITY_PASSWORD.encode("utf-8")
        )
    ):
        # Log the failed username (never the password) for brute-force visibility.
        logger.warning("Login failed: username=%s", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
    logger.info("Login success: username=%s", body.username)
    token = create_access_token({"sub": body.username})
    response = LoginResponse(access_token=token, username=body.username)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me")
async def me(token: str = Depends(oauth2_scheme)):
    """Return the authenticated username from a valid Bearer token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
    payload = decode_access_token(token)
    if payload is None or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
    response = {"username": payload["sub"]}
    return response
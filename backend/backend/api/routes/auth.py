"""AIC-ADE — Authentication endpoints for the local desktop identity.

The Electron main process generates a per-install random credential
(identity.json in userData) and passes it to the backend via
AIC_IDENTITY_FILE. The desktop app auto-authenticates silently — these
endpoints only ever serve the local sidecar on 127.0.0.1.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import asyncio
import logging
import secrets
import time

from backend.config import settings
# NOTE: plaintext compare — the identity file stores a random hex password,
# not a bcrypt hash, so auth.security.verify_password (bcrypt) is not applicable.
from auth.security import create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("aic.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ── P5: Brute-force lockout ──────────────────────────────
# Exponential lockout after 3 consecutive failures per client:
# 3 fails → 5 min lock, 6 fails → 10 min, 9 fails → 20 min, capped at 24 h.
# The per-install credential is a random 32-byte hex string, so brute force is
# infeasible in practice — this is defense-in-depth and keeps logs quiet.
_LOCK_MAX_ATTEMPTS = 3
_LOCK_BASE_SECONDS = 300  # 5 minutes
_LOCK_MAX_SECONDS = 24 * 3600  # cap at 24 hours

# client_id → {"fails": int, "locked_until": float}
_login_lockout: dict[str, dict] = {}
_lockout_guard = asyncio.Lock()


def _client_key(request: Request) -> str:
    """Best-effort client identifier (local app — client.host is 127.0.0.1)."""
    return request.client.host if request.client else "unknown"


def _lockout_seconds(fails: int) -> int:
    """Exponential backoff: 5min, 10min, 20min, ... capped."""
    levels = fails // _LOCK_MAX_ATTEMPTS - 1
    return min(_LOCK_BASE_SECONDS * (2 ** max(levels, 0)), _LOCK_MAX_SECONDS)


def _reset_lockout_for_tests() -> None:
    """Test helper — clear all lockout state."""
    _login_lockout.clear()


async def _check_lockout(key: str) -> None:
    """Raise 429 if this client is still inside a lockout window."""
    async with _lockout_guard:
        rec = _login_lockout.get(key)
        if rec and rec["locked_until"] > time.monotonic():
            retry_after = int(rec["locked_until"] - time.monotonic()) + 1
            logger.warning("Login locked out: client=%s retry_after=%ss", key, retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Retry in {retry_after} seconds.",
                headers={
                    "Retry-After": str(retry_after),
                    "Cache-Control": "no-store",
                },
            )


async def _record_failure(key: str) -> None:
    async with _lockout_guard:
        rec = _login_lockout.setdefault(key, {"fails": 0, "locked_until": 0.0})
        rec["fails"] += 1
        if rec["fails"] % _LOCK_MAX_ATTEMPTS == 0:
            wait = _lockout_seconds(rec["fails"])
            rec["locked_until"] = time.monotonic() + wait
            logger.warning(
                "Login lockout engaged: client=%s fails=%s lock=%ss", key, rec["fails"], wait
            )


async def _record_success(key: str) -> None:
    async with _lockout_guard:
        _login_lockout.pop(key, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest, response: Response):
    """Authenticate against the per-install desktop identity."""
    # P5 FIX: Check lockout before attempting authentication
    client_key = _client_key(request)
    await _check_lockout(client_key)
    
    # Timing-safe comparison: plaintext `!=` leaks the correct length/prefix via
    # short-circuit timing. compare_digest runs in constant time regardless of
    # how many bytes match. Both sides are the per-install random hex credential,
    # so we compare the raw strings (encode to utf-8 bytes). If this ever becomes
    # a hashed password, compare the hash digests with compare_digest instead.
    if (
        not secrets.compare_digest(
            body.username.encode("utf-8"), settings.IDENTITY_USERNAME.encode("utf-8")
        )
        or not secrets.compare_digest(
            body.password.encode("utf-8"), settings.IDENTITY_PASSWORD.encode("utf-8")
        )
    ):
        # Record failure for lockout tracking
        await _record_failure(client_key)
        # Log the failed username (never the password) for brute-force visibility.
        logger.warning("Login failed: username=%s", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
    # Record successful auth — clears any lockout history
    await _record_success(client_key)
    logger.info("Login success: username=%s", body.username)
    token = create_access_token({"sub": body.username})
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(access_token=token, username=body.username)


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
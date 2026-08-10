"""Shared FastAPI dependencies — per-install identity token enforcement.

The desktop app authenticates silently via a Bearer token (issued by the
Electron main process through ``POST /auth/login``). Sensitive / mutating
endpoints that can execute code, install artifacts, or mutate provider config
guard themselves with :func:`require_current_user`.

TEST-ONLY NOTE: this module's fail-open behavior is strictly for the automated
test suite and must NEVER be enabled in production. The test suite drives the
app with httpx ``ASGITransport`` using ``base_url="http://test"`` and no token.
To let those token-less tests pass without opening a Host-header backdoor in
production, the dependency fail-opens ONLY when BOTH the ``AIC_TESTING`` environment
flag AND ``AIC_ALLOW_TEST_AUTH`` are set (pytest sets both in ``tests/conftest.py``). 
If these flags are ever set in a real deployment, EVERY guard here silently
authenticates any unauthenticated caller, so the app logs a loud startup WARNING 
when it is detected (see ``backend/main.py`` lifespan). In production neither flag 
is present, so a missing/invalid token always yields ``None`` and ``require_current_user``
raises 401.
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from backend.api.routes.auth import oauth2_scheme
from auth.security import decode_access_token

# H1: Require DUAL flags for test auth bypass - prevents accidental exposure
# AIC_TESTING set by pytest
_AIC_TESTING = os.environ.get("AIC_TESTING") == "1"
# AIC_ALLOW_TEST_AUTH - explicit opt-in flag
_AIC_ALLOW_TEST_AUTH = os.environ.get("AIC_ALLOW_TEST_AUTH", "").lower() == "true"

# Combined check - both must be true to bypass auth in test mode
_AIC_TEST_MODE = _AIC_TESTING and _AIC_ALLOW_TEST_AUTH

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """Return the authenticated username, or ``None`` when unauthenticated.

    Reads the ``Authorization: Bearer <token>`` header via ``oauth2_scheme``
    (``auto_error=False`` so a missing header yields ``None`` rather than an
    automatic 401) and validates it with :func:`decode_access_token`. In test
    mode (``AIC_TESTING=1 AND AIC_ALLOW_TEST_AUTH=true``) a missing token
    fail-opens to ``"test-user"`` so the token-less suite keeps passing;
    otherwise a missing/invalid token yields ``None``.
    """
    if not token and _AIC_TEST_MODE:
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
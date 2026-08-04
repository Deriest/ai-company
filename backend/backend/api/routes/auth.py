"""AIC-ADE — Authentication endpoints for the local desktop identity.

The Electron main process generates a per-install random credential
(identity.json in userData) and passes it to the backend via
AIC_IDENTITY_FILE. The desktop app auto-authenticates silently — these
endpoints only ever serve the local sidecar on 127.0.0.1.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from backend.config import settings
# NOTE: plaintext compare — the identity file stores a random hex password,
# not a bcrypt hash, so auth.security.verify_password (bcrypt) is not applicable.
from auth.security import create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

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
    if (
        body.username != settings.IDENTITY_USERNAME
        or body.password != settings.IDENTITY_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": body.username})
    return LoginResponse(access_token=token, username=body.username)


@router.get("/me")
async def me(token: str = Depends(oauth2_scheme)):
    """Return the authenticated username from a valid Bearer token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": payload["sub"]}
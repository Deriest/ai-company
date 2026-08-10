"""Release signing endpoints for secure update manifests."""

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

# ── Signing Infrastructure ──────────────────────────────

SECRET_KEY_PATH = Path(__file__).parent.parent.parent.parent / "secrets" / "release_private_key.pem"
PUBLIC_KEY_PUB_PATH = Path(__file__).parent.parent.parent.parent / "secrets" / "release_public_key.pub"


def _load_signing_keys() -> tuple:
    """Load Ed25519 signing keys. Raises if not configured."""
    if not SECRET_KEY_PATH.exists():
        raise RuntimeError(
            "Release signing private key not found. "
            "Generate with: ./scripts/generate_release_key.sh"
        )
    
    try:
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )
        
        with open(SECRET_KEY_PATH, "rb") as f:
            private_key = load_pem_private_key(f.read(), password=None)
        
        return private_key
    except Exception as e:
        raise RuntimeError(f"Failed to load signing key: {e}")


def _generate_ed25519_signature(data: bytes) -> str:
    """Sign data using Ed25519 and return base64-encoded signature."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    
    private_key = _load_signing_keys()
    signature = private_key.sign(data)
    return base64.b64encode(signature).decode("ascii")


router = APIRouter(prefix="/release", tags=["release"])


@router.get("/manifest/{version}")
async def get_signed_manifest(version: str) -> Dict[str, Any]:
    """Get signed manifest for a specific version.
    
    Returns manifest with cryptographic signature for client verification.
    """
    # In production, this would fetch from S3/CDN
    # For development, generate mock manifest
    
    manifest_data = {
        "version": version,
        "name": "AIC ADE Platform",
        "description": "AI Code Development Environment",
        "releaseDate": datetime.now(timezone.utc).isoformat(),
        "mandatory": False,
        "platforms": {
            "win32-x64": {
                "name": "Windows 64-bit",
                "url": f"https://example.com/releases/aic-ade-{version}-win.exe",
                "sha256": hashlib.sha256(f"mock-content-{version}".encode()).hexdigest(),
            },
            "linux-x64": {
                "name": "Linux 64-bit",
                "url": f"https://example.com/releases/aic-ade-{version}-linux.AppImage",
                "sha256": hashlib.sha256(f"mock-content-{version}".encode()).hexdigest(),
            },
            "darwin-x64": {
                "name": "macOS Intel",
                "url": f"https://example.com/releases/aic-ade-{version}-mac.dmg",
                "sha256": hashlib.sha256(f"mock-content-{version}".encode()).hexdigest(),
            },
            "darwin-arm64": {
                "name": "macOS Apple Silicon",
                "url": f"https://example.com/releases/aic-ade-{version}-mac-arm64.dmg",
                "sha256": hashlib.sha256(f"mock-content-{version}".encode()).hexdigest(),
            },
        },
        "notes": f"Release {version} with new features and security fixes.",
    }
    
    # Sign the manifest
    manifest_json = json.dumps(manifest_data, sort_keys=True, separators=(",", ":"))
    signature = _generate_ed25519_signature(manifest_json.encode("utf-8"))
    
    return {
        "manifest": manifest_data,
        "signature": signature,
        "algorithm": "Ed25519-SHA256",
    }


@router.get("/latest-manifest")
async def get_latest_signed_manifest() -> Dict[str, Any]:
    """Get signed manifest for latest version."""
    # Return latest version's signed manifest
    return await get_signed_manifest("v2.4.89")


@router.post("/sign")
async def sign_release_data(payload: Dict[str, str]) -> Dict[str, Any]:
    """Manually sign release data for testing purposes.
    
    Args:
        payload: {"version": "...", "notes": "...", "urls": {...}}
    
    Returns:
        Signed manifest with signature
    """
    try:
        data = {
            "version": payload.get("version", "unknown"),
            "notes": payload.get("notes", ""),
            "urls": payload.get("urls", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        data_json = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = _generate_ed25519_signature(data_json)
        
        return {
            "signed_data": data,
            "signature": signature,
            "hash": hashlib.sha256(data_json).hexdigest(),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing failed: {e}")


@router.get("/public-key")
async def get_public_key() -> Dict[str, str]:
    """Get public key for client-side verification."""
    if not PUBLIC_KEY_PUB_PATH.exists():
        raise HTTPException(status_code=404, detail="Public key not found")
    
    with open(PUBLIC_KEY_PUB_PATH, "r") as f:
        public_key = f.read().strip()
    
    return {
        "key": public_key,
        "algorithm": "Ed25519",
    }

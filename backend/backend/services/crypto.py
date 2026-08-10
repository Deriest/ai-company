"""
Cryptographic utilities for AIC-ADE.

Generates installation-specific encryption keys on first run.
Maintains backward compatibility with legacy hardcoded keys.
"""

import os
import tempfile
import base64
import secrets
import json
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Migration support for legacy installations
# These values are used only when migrating from older versions that stored keys in plaintext
_LEGACY_SECRET = os.getenv("AIC_LEGACY_SECRET", "")
_LEGACY_SALT = base64.b64decode(os.getenv("AIC_LEGACY_SALT_B64", "")) if os.getenv("AIC_LEGACY_SALT_B64") else b""

_secrets_file: Path | None = None
_fernet: Fernet | None = None
_legacy_fernet: Fernet | None = None


def _get_data_dir() -> Path:
    data_dir = os.getenv("AIC_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir)
    return Path("/tmp/aic-data")


def _get_secrets_path() -> Path:
    global _secrets_file
    if _secrets_file is None:
        _secrets_file = _get_data_dir() / ".aic-secrets.json"
    return _secrets_file


def _derive_fernet(secret: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return Fernet(key)


def _load_or_generate_secrets() -> tuple[str, bytes]:
    """Load installation-specific secrets or generate on first run."""
    path = _get_secrets_path()

    if path.exists():
        try:
            data = json.loads(path.read_text())
            secret = data["secret"]
            salt = base64.b64decode(data["salt"])
            return secret, salt
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Corrupt secrets file, regenerating: {e}")

    # Generate new installation-specific secrets
    secret = secrets.token_urlsafe(48)
    salt = secrets.token_bytes(32)

    path.parent.mkdir(parents=True, exist_ok=True)
    
    # M7 FIX: Use atomic write pattern - temp file + os.replace
    # This prevents corruption if process crashes during write
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({
                "secret": secret,
                "salt": base64.b64encode(salt).decode(),
                "version": 1,
            }, f)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise e
    
    logger.info(f"Generated new encryption secrets at {path}")
    return secret, salt


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    secret, salt = _load_or_generate_secrets()
    _fernet = _derive_fernet(secret, salt)
    return _fernet


def _get_legacy_fernet() -> Fernet:
    global _legacy_fernet
    if _legacy_fernet is not None:
        return _legacy_fernet
    _legacy_fernet = _derive_fernet(_LEGACY_SECRET, _LEGACY_SALT)
    return _legacy_fernet


def encrypt(text: str) -> str:
    """Encrypt plaintext. Uses installation-specific key."""
    if not text:
        return ""
    return _get_fernet().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    """
    Decrypt ciphertext. Tries installation-specific key first,
    falls back to legacy key for backward compatibility.

    M5 FIX: never echo the input back as-is. Undecryptable values raise
    ValueError instead of silently returning the ciphertext, which would
    let corrupt/plaintext secrets masquerade as valid API keys.
    """
    if not text:
        return ""

    # Try current key
    try:
        return _get_fernet().decrypt(text.encode()).decode()
    except Exception as e:
        # B3 FIX: log the failure (including key-load OSErrors) so an unrelated
        # error never silently falls through to the legacy key. A decrypt
        # failure is expected for legacy values, so only log at debug level.
        logger.debug("Current-key decrypt failed: %s", e)

    # Try legacy key (migration path)
    try:
        decrypted = _get_legacy_fernet().decrypt(text.encode()).decode()
        logger.warning("Decrypted with legacy key — consider re-encrypting")
        return decrypted
    except Exception as e:
        logger.debug("Legacy-key decrypt failed: %s", e)

    raise ValueError("Unable to decrypt value (not encrypted with current or legacy key)")


def re_encrypt(text: str) -> str:
    """Re-encrypt a value with the current key (for migration)."""
    if not text:
        return ""
    # Decrypt with whatever key works
    plaintext = decrypt(text)
    # Re-encrypt with current key
    return encrypt(plaintext)

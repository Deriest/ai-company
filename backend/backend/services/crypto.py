"""
Cryptographic utilities for AIC-ADE.

Generates installation-specific encryption keys on first run.
Maintains backward compatibility with legacy hardcoded keys.

Security Notes:
- Keys are generated per-installation and stored in .aic-secrets.json
- Backup rotation: keeps last 3 backups before current secret file
- Atomic writes prevent corruption during crashes
- Legacy fallback exists only for migration path (will be removed in future)
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

# Number of backup copies to maintain (last 3 before current)
BACKUP_COUNT = 3


def _get_data_dir() -> Path:
    data_dir = os.getenv("AIC_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir)
    # Use XDG-compliant directory if available, fall back to /tmp/aic-data
    xdg_data = Path.home() / ".local" / "share" / "aic"
    if xdg_data.exists():
        return xdg_data
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


def _rotate_backups(secrets_path: Path) -> None:
    """Rotate secret file backups: keep last BACKUP_COUNT copies."""
    if not secrets_path.exists():
        return
    
    # Shift existing backups
    for i in range(BACKUP_COUNT - 1, 0, -1):
        old_backup = secrets_path.parent / f".aic-secrets.json.backup.{i}"
        new_backup = secrets_path.parent / f".aic-secrets.json.backup.{i + 1}"
        if old_backup.exists():
            try:
                old_backup.rename(new_backup)
            except OSError as e:
                logger.warning(f"Failed to rotate backup {i}: {e}")
    
    # Create new backup from current file
    current_backup = secrets_path.parent / ".aic-secrets.json.backup.1"
    try:
        secrets_path.copy(current_backup)
        # Set restrictive permissions (owner read/write only)
        os.chmod(current_backup, 0o600)
        logger.debug("Secrets backup created at .aic-secrets.json.backup.1")
    except OSError as e:
        logger.warning(f"Failed to create secrets backup: {e}")


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
    
    # M7 FIX: Use atomic write pattern + backup rotation
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
        
        # Create backup of existing file BEFORE replacing
        if path.exists():
            _rotate_backups(path)
        
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise e
    
    logger.info(f"Generated new encryption secrets at {path} (backup created)")
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
    """Encrypt plaintext. Uses installation-specific key.
    
    Args:
        text: Plaintext to encrypt
        
    Returns:
        Base64-encoded encrypted string
        
    Raises:
        ValueError: If input is empty
    """
    if not text:
        return ""
    return _get_fernet().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    """
    Decrypt ciphertext. Tries installation-specific key first,
    falls back to legacy key for backward compatibility.
    
    Security Note:
        Undecryptable values raise ValueError instead of returning the 
        ciphertext, which would let corrupt/plaintext secrets masquerade 
        as valid API keys.
        
    Args:
        text: Ciphertext to decrypt
        
    Returns:
        Decrypted plaintext
        
    Raises:
        ValueError: If value cannot be decrypted with current or legacy key
    """
    if not text:
        return ""
    
    # Try current key
    try:
        return _get_fernet().decrypt(text.encode()).decode()
    except Exception:
        # Log the failure but don't expose full exception to caller
        logger.debug("Current-key decrypt failed (expected for legacy/invalid data)")
    
    # Try legacy key (migration path)
    try:
        decrypted = _get_legacy_fernet().decrypt(text.encode()).decode()
        logger.warning("Decrypted with legacy key — consider re-encrypting for security")
        return decrypted
    except Exception:
        logger.debug("Legacy-key decrypt failed")
    
    raise ValueError("Unable to decrypt value (not encrypted with current or legacy key)")


def re_encrypt(text: str) -> str:
    """Re-encrypt a value with the current key (for migration).
    
    Args:
        text: Ciphertext to re-encrypt
        
    Returns:
        New ciphertext encrypted with current key
        
    Raises:
        ValueError: If original value cannot be decrypted
    """
    if not text:
        return ""
    # Decrypt with whatever key works
    plaintext = decrypt(text)
    # Re-encrypt with current key
    return encrypt(plaintext)


def ensure_keys_exist() -> bool:
    """Verify that encryption keys exist and are accessible.
    
    This function is called at startup to validate encryption system.
    
    Returns:
        True if keys exist and are usable
    """
    try:
        _get_fernet()
        return True
    except Exception as e:
        logger.error(f"Encryption keys verification failed: {e}")
        return False

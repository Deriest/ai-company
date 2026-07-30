"""Unit tests for crypto service."""
import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture(autouse=True)
def setup_crypto(tmp_path):
    """Set up crypto with temp data dir."""
    os.environ["AIC_DATA_DIR"] = str(tmp_path)
    # Reset cached state
    import backend.services.crypto as crypto_mod
    crypto_mod._fernet = None
    crypto_mod._legacy_fernet = None
    crypto_mod._secrets_file = None
    yield
    os.environ.pop("AIC_DATA_DIR", None)


def test_encrypt_decrypt_roundtrip():
    from backend.services.crypto import encrypt, decrypt
    plaintext = "my-secret-api-key-12345"
    encrypted = encrypt(plaintext)
    assert encrypted != plaintext
    assert decrypt(encrypted) == plaintext


def test_encrypt_empty_string():
    from backend.services.crypto import encrypt, decrypt
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_different_encryptions_produce_different_ciphertext():
    from backend.services.crypto import encrypt
    e1 = encrypt("hello")
    e2 = encrypt("hello")
    # Fernet uses random IV, so ciphertexts should differ
    assert e1 != e2


def test_secrets_file_created(tmp_path):
    from backend.services.crypto import encrypt
    encrypt("test")  # triggers key generation
    secrets_file = tmp_path / ".aic-secrets.json"
    assert secrets_file.exists()


def test_backward_compatibility_with_legacy_key():
    """Verify that data encrypted with legacy key can still be decrypted."""
    from backend.services.crypto import encrypt, decrypt, _get_legacy_fernet
    # Encrypt with legacy key
    legacy_fernet = _get_legacy_fernet()
    plaintext = "legacy-encrypted-value"
    legacy_encrypted = legacy_fernet.encrypt(plaintext.encode()).decode()
    # Should decrypt using fallback
    assert decrypt(legacy_encrypted) == plaintext


def test_re_encrypt_migrates_to_new_key():
    from backend.services.crypto import encrypt, decrypt, re_encrypt, _get_legacy_fernet
    # Encrypt with legacy
    legacy_fernet = _get_legacy_fernet()
    plaintext = "migrate-me"
    legacy_encrypted = legacy_fernet.encrypt(plaintext.encode()).decode()
    # Re-encrypt
    new_encrypted = re_encrypt(legacy_encrypted)
    # Should decrypt with current key
    assert decrypt(new_encrypted) == plaintext

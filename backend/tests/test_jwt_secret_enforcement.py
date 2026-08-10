"""Tests for GAP-1 fix: JWT secret environment variable enforcement."""

import os
import pytest
from pathlib import Path


def test_jwt_secret_missing_raises_error(monkeypatch):
    """Backend should fail closed if AIC_JWT_SECRET is not set."""
    monkeypatch.delenv("AIC_JWT_SECRET", raising=False)
    monkeypatch.setenv("AIC_TESTING", "1")
    monkeypatch.setenv("AIC_IDENTITY_USERNAME", "test")
    monkeypatch.setenv("AIC_IDENTITY_PASSWORD", "testpass")
    
    # Import config module fresh to trigger error
    import importlib
    import backend.config
    
    # Force reload without env var
    importlib.reload(backend.config)
    
    # Should raise ValueError about missing JWT secret
    with pytest.raises(ValueError, match="AIC_JWT_SECRET"):
        backend.config.settings.ensure_dirs()


def test_jwt_secret_too_short_raises_error(monkeypatch):
    """Backend should reject JWT secrets shorter than 32 characters."""
    monkeypatch.setenv("AIC_JWT_SECRET", "short_key_12345")
    monkeypatch.setenv("AIC_TESTING", "1")
    monkeypatch.setenv("AIC_IDENTITY_USERNAME", "test")
    monkeypatch.setenv("AIC_IDENTITY_PASSWORD", "testpass")
    
    import importlib
    import backend.config
    importlib.reload(backend.config)
    
    with pytest.raises(ValueError, match="minimum 32 characters"):
        backend.config.settings.ensure_dirs()


def test_jwt_secret_valid_accepted(monkeypatch):
    """Backend should accept valid JWT secrets of 32+ chars."""
    import secrets
    
    test_secret = secrets.token_hex(32)  # 64 chars
    monkeypatch.setenv("AIC_JWT_SECRET", test_secret)
    monkeypatch.setenv("AIC_TESTING", "1")
    monkeypatch.setenv("AIC_IDENTITY_USERNAME", "test")
    monkeypatch.setenv("AIC_IDENTITY_PASSWORD", "testpass")
    
    import importlib
    import backend.config
    importlib.reload(backend.config)
    
    # Should succeed without errors
    backend.config.settings.ensure_dirs()
    assert backend.config.settings.SECRET_KEY == test_secret
    assert len(backend.config.settings.SECRET_KEY) >= 32


def test_no_jwt_secret_file_creation(monkeypatch, tmp_path):
    """Backend should NOT create .jwt_secret file anymore."""
    import secrets
    
    monkeypatch.setenv("AIC_JWT_SECRET", secrets.token_hex(32))
    monkeypatch.setenv("AIC_TESTING", "1")
    monkeypatch.setenv("AIC_IDENTITY_USERNAME", "test")
    monkeypatch.setenv("AIC_IDENTITY_PASSWORD", "testpass")
    monkeypatch.setenv("AIC_DATA_DIR", str(tmp_path))
    
    import importlib
    import backend.config
    importlib.reload(backend.config)
    
    backend.config.settings.ensure_dirs()
    
    # Verify no .jwt_secret file was created
    jwt_file = Path(tmp_path) / ".jwt_secret"
    assert not jwt_file.exists(), "JWT secret file should not be created"

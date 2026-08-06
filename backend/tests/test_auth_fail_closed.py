"""Auth fail-CLOSED tests.

The global ``tests/conftest.py`` sets ``AIC_TESTING=1`` which makes the auth
dependency in ``backend/api/dependencies.py`` fail-OPEN (missing token ==
authenticated). These tests deliberately remove ``AIC_TESTING`` and reload the
module so the *production* fail-closed behavior is verified:

* ``get_optional_current_user`` returns ``None`` without a token
* ``require_current_user`` raises HTTP 401 when the token is missing

It also covers the DNS-rebinding Host-header guard in ``backend/main.py``:
the exact-host parsing must reject ``127.0.0.1.evil.com`` while allowing
``localhost`` / ``127.0.0.1`` / ``::1``.
"""
import sys
import importlib

import pytest
from fastapi import HTTPException


def _reload_dependencies(monkeypatch, testing: bool):
    """Set/clear AIC_TESTING then reload backend.api.dependencies fresh."""
    if testing:
        monkeypatch.setenv("AIC_TESTING", "1")
    else:
        monkeypatch.delenv("AIC_TESTING", raising=False)
    mod = importlib.import_module("backend.api.dependencies")
    return importlib.reload(mod)


def test_get_optional_current_user_returns_none_without_token(monkeypatch):
    deps = _reload_dependencies(monkeypatch, testing=False)
    assert deps._AIC_TESTING is False
    assert deps.get_optional_current_user(request=None, token=None) is None


def test_get_optional_current_user_fail_open_when_testing_flag_set(monkeypatch):
    """Sanity check: with AIC_TESTING=1 the module fail-opens to test-user."""
    deps = _reload_dependencies(monkeypatch, testing=True)
    assert deps._AIC_TESTING is True
    assert deps.get_optional_current_user(request=None, token=None) == "test-user"


def test_require_current_user_raises_401_when_token_missing(monkeypatch):
    deps = _reload_dependencies(monkeypatch, testing=False)
    with pytest.raises(HTTPException) as exc:
        deps.require_current_user(user=None)
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


def test_require_current_user_returns_user_when_present(monkeypatch):
    deps = _reload_dependencies(monkeypatch, testing=False)
    assert deps.require_current_user(user="admin") == "admin"


# ── Host-header DNS-rebinding guard (backend.main) ────────────────────────

@pytest.fixture(scope="module")
def host_is_localhost():
    """Import backend.main once and return its localhost-check helper."""
    import backend.main as main
    return main._host_header_is_localhost


@pytest.mark.parametrize("host,expected", [
    # Allowed local hosts (exact match on the host part, port stripped).
    ("127.0.0.1", True),
    ("127.0.0.1:8000", True),
    ("localhost", True),
    ("localhost:8000", True),
    ("[::1]", True),
    ("[::1]:8000", True),
    # DNS-rebinding / attacker-controlled hosts must be rejected.
    ("127.0.0.1.evil.com", False),
    ("123.127.0.0.1.nip.io", False),
    ("evil.com", False),
    ("localhost.evil.com", False),
    ("", False),
])
def test_host_header_is_localhost_rejects_dns_rebinding(host_is_localhost, host, expected):
    assert host_is_localhost(host) is expected
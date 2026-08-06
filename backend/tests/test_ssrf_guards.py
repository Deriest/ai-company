"""SSRF guard tests — provider URL validation, web_fetch guard, ProviderClient.

Covers the previously-untested outbound-fetch hardening:

* ``backend.api.routes.providers._validate_provider_url`` rejects private /
  loopback / link-local / metadata / IPv6-ULA resolved addresses.
* ``workers.tools._validate_web_url`` rejects private/internal targets and
  HTTPS->HTTP redirect downgrades.
* ``ProviderClient`` pins ``follow_redirects=False`` (no redirect-follow to
  internal IPs) and surfaces private-target connects as connection errors.
* Valid public URLs pass validation.

DNS resolution is monkeypatched so behavior is deterministic and offline.
"""
import ipaddress

import httpx
import pytest
from fastapi import HTTPException


# ── Helpers ───────────────────────────────────────────────────────────────

def _fake_getaddrinfo(ips):
    """Return a getaddrinfo-like function resolving *host* to *ips* (strings)."""
    def getaddrinfo(host, port, *args, **kwargs):
        out = []
        for ip in ips:
            addr = ipaddress.ip_address(ip)
            if addr.version == 4:
                out.append((2, 1, 6, "", (str(addr), port or 80)))
            else:
                out.append((10, 1, 6, "", (str(addr), port or 80, 0, 0)))
        return out
    return getaddrinfo


# ── _validate_provider_url ────────────────────────────────────────────────

@pytest.mark.parametrize("ip", [
    "10.0.0.1",      # RFC1918 10/8
    "172.16.0.1",    # RFC1918 172.16/12
    "192.168.1.1",   # RFC1918 192.168/16
    "127.0.0.1",     # loopback
    "169.254.169.254",  # cloud metadata
])
def test_validate_provider_url_blocks_private_ip(monkeypatch, ip):
    from backend.api.routes.providers import _validate_provider_url
    monkeypatch.setattr(
        "backend.api.routes.providers.socket.getaddrinfo",
        _fake_getaddrinfo([ip]),
    )
    with pytest.raises(HTTPException) as exc:
        _validate_provider_url(f"http://example.com")
    assert exc.value.status_code == 400
    assert "blocked" in exc.value.detail


def test_validate_provider_url_blocks_ipv6_ula(monkeypatch):
    """_validate_provider_url blocks IPv6 ULA fc00::1.

    providers.py uses ``ip.is_private`` (which covers fc00::/7 on all Python
    versions) plus an explicit ``ip in ipaddress.ip_network("fc00::/7")`` check.
    The previous implementation used ``getattr(ip, "is_unique_local", False)``,
    but that attribute only exists on Python 3.13+, so on 3.11/3.12 it returned
    False and let fc00::/7 through. This test asserts the fixed behavior so the
    gap is not silently re-introduced.
    """
    from backend.api.routes.providers import _validate_provider_url
    monkeypatch.setattr(
        "backend.api.routes.providers.socket.getaddrinfo",
        _fake_getaddrinfo(["fc00::1"]),
    )
    # Now correctly blocked — IPv6 unique-local must be rejected.
    with pytest.raises(HTTPException) as exc:
        _validate_provider_url("https://example.com")
    assert exc.value.status_code == 400
    assert "blocked" in exc.value.detail


def test_validate_provider_url_rejects_non_http_scheme(monkeypatch):
    from backend.api.routes.providers import _validate_provider_url
    monkeypatch.setattr(
        "backend.api.routes.providers.socket.getaddrinfo",
        _fake_getaddrinfo(["93.184.216.34"]),
    )
    with pytest.raises(HTTPException) as exc:
        _validate_provider_url("ftp://example.com/file")
    assert exc.value.status_code == 400


def test_validate_provider_url_allows_public(monkeypatch):
    from backend.api.routes.providers import _validate_provider_url
    monkeypatch.setattr(
        "backend.api.routes.providers.socket.getaddrinfo",
        _fake_getaddrinfo(["93.184.216.34"]),
    )
    # Should not raise.
    assert _validate_provider_url("https://example.com") is None


def test_validate_provider_url_unresolvable_host_passes(monkeypatch):
    """An unresolvable host is left to the provider client to surface the error."""
    from backend.api.routes.providers import _validate_provider_url

    def raise_oserror(host, port, *a, **k):
        raise OSError("getaddrinfo failed")

    monkeypatch.setattr("backend.api.routes.providers.socket.getaddrinfo", raise_oserror)
    assert _validate_provider_url("https://does-not-exist.invalid") is None


# ── web_fetch guard (workers.tools) ───────────────────────────────────────

@pytest.mark.parametrize("ip", [
    "10.0.0.1",
    "127.0.0.1",
    "169.254.169.254",
    "fc00::1",
])
def test_validate_web_url_blocks_private_internal(monkeypatch, ip):
    from workers.tools import _validate_web_url
    monkeypatch.setattr(
        "workers.tools.socket.getaddrinfo",
        _fake_getaddrinfo([ip]),
    )
    with pytest.raises(ValueError):
        _validate_web_url(f"http://internal.example")


def test_validate_web_url_blocks_bad_scheme():
    from workers.tools import _validate_web_url
    with pytest.raises(ValueError):
        _validate_web_url("file:///etc/passwd")


def test_validate_web_url_blocks_https_downgrade_redirect():
    from workers.tools import _validate_web_url
    # previous_scheme="https" -> http downgrade must be rejected before any
    # DNS resolution happens.
    with pytest.raises(ValueError) as exc:
        _validate_web_url("http://example.com", previous_scheme="https")
    assert "downgrade" in str(exc.value)


def test_validate_web_url_allows_public(monkeypatch):
    from workers.tools import _validate_web_url
    monkeypatch.setattr(
        "workers.tools.socket.getaddrinfo",
        _fake_getaddrinfo(["93.184.216.34"]),
    )
    assert _validate_web_url("https://example.com") is None


# ── ProviderClient ────────────────────────────────────────────────────────

def test_provider_client_pins_follow_redirects_false():
    from backend.services.provider_client import ProviderClient
    client = ProviderClient("https://example.com", "key")
    try:
        assert client.client.follow_redirects is False
    finally:
        # close without a real open request
        import asyncio
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(client.close())


@pytest.mark.asyncio
async def test_provider_client_private_target_raises_connection_error():
    from backend.services.provider_client import ProviderClient, ProviderConnectionError

    def handler(request):
        raise httpx.ConnectError("Connection refused to internal IP", request=request)

    client = ProviderClient("http://10.0.0.1", "key")
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    try:
        with pytest.raises(ProviderConnectionError):
            await client.test_connection()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_provider_client_valid_public_url_works():
    from backend.services.provider_client import ProviderClient

    def handler(request):
        return httpx.Response(
            200,
            json={"data": [{
                "id": "gpt-test",
                "object": "model",
                "owned_by": "test",
            }]},
        )

    client = ProviderClient("https://example.com", "key")
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    try:
        res = await client.test_connection()
        assert res["status"] == "connected"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_provider_client_does_not_follow_redirect_to_internal():
    """A public endpoint that 302s to an internal IP must NOT be followed."""
    from backend.services.provider_client import ProviderClient, ProviderConnectionError

    def handler(request):
        # Redirect to a private IP. Because follow_redirects=False, httpx
        # returns the 302 as-is (no follow) rather than reaching 10.0.0.1.
        return httpx.Response(302, headers={"Location": "http://10.0.0.1/models"})

    client = ProviderClient("https://example.com", "key")
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    try:
        # fetch_models sees a 302; because follow_redirects=False httpx does NOT
        # follow to 10.0.0.1, so it bails with a redirect HTTPStatusError instead
        # of ever connecting to the internal IP.
        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_models()
    finally:
        await client.close()
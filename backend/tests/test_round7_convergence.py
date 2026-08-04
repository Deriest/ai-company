"""Round-7 convergence audit fixes — functional verification tests.

Covers:
- Item 1: POST /providers/config with empty/missing provider_name or base_url
  returns 400 BEFORE creating any Provider row (no junk "default" row, no 500).
- Item 2: DELETE /providers/{id} deregisters the provider from provider_manager
  so it stops serving requests without a restart.

Note: the positive /providers/config path is intentionally NOT exercised here —
it mutates the process env and writes the repo `.env`/engine_config.json, which
would leak state into the rest of the suite. It is verified by a one-off manual
script instead.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield


# ── Item 1: POST /providers/config validates before creating a row ────────

async def _count_providers() -> int:
    from sqlalchemy.future import select
    from sqlalchemy import func
    from backend.models.schema import Provider
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(Provider))).scalar_one()
    return total


@pytest.mark.asyncio
async def test_providers_config_empty_body_returns_400_no_junk_row():
    """Apply-to-Engine with no provider configured returns 400 and creates no row."""
    before = await _count_providers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/providers/config", json={})
    assert resp.status_code == 400
    assert "provider_name and base_url are required" in resp.json()["detail"]
    after = await _count_providers()
    assert after == before, "no Provider row may be created on a validation failure"


@pytest.mark.asyncio
async def test_providers_config_missing_base_url_returns_400():
    """A provider_name without base_url is rejected before any DB write."""
    before = await _count_providers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/providers/config", json={"provider_name": "default"})
    assert resp.status_code == 400
    assert "provider_name and base_url are required" in resp.json()["detail"]
    assert await _count_providers() == before


@pytest.mark.asyncio
async def test_providers_config_missing_name_returns_400():
    """A base_url without a provider_name is rejected before any DB write."""
    before = await _count_providers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/providers/config", json={"base_url": "https://api.test.com"})
    assert resp.status_code == 400
    assert "provider_name and base_url are required" in resp.json()["detail"]
    assert await _count_providers() == before


# ── Item 2: DELETE /providers/{id} deregisters from provider_manager ─────

@pytest.mark.asyncio
async def test_delete_provider_deregisters_from_manager():
    """Deleting a provider removes it from provider_manager so it is no longer
    served (health llm_configured / active) without a restart."""
    from llm.provider import provider_manager

    name = "Round7 Del Provider"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post("/providers", json={
            "name": name,
            "endpoint": "https://api.test.com",
            "apiKey": "test-key",
        })
        assert create.status_code == 200
        provider_id = create.json()["id"]

    # Registered and served by the manager after creation.
    assert provider_manager.get_provider(name) is not None, (
        "provider must be registered in provider_manager after creation"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        delete = await ac.delete(f"/providers/{provider_id}")
    assert delete.status_code == 200

    # No longer served after deletion.
    assert provider_manager.get_provider(name) is None, (
        "deleted provider must be deregistered from provider_manager"
    )
    assert provider_manager._active != name, (
        "deleted provider must not remain the active provider"
    )
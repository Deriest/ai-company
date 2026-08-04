import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_login_flow():
    """Login works against the correct /auth/login route (was /api/auth/login)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200
        assert "access_token" in res.json()

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_feedback_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login
        res = await ac.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Report submit
        res = await ac.post("/api/feedback/report", json={
            "severity": "high",
            "category": "provider",
            "error_message": "Failed to list models from endpoint",
            "current_worker": "hermes"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "submitted"
        assert "issue_id" in data
        
        # 2. Engineering Inbox
        res = await ac.get("/api/feedback/inbox", headers=headers)
        assert res.status_code == 200
        inbox_data = res.json()
        assert inbox_data["total_reports"] >= 1
        assert len(inbox_data["inbox"]) >= 1
        
        # 3. Support Bundle
        res = await ac.get("/api/feedback/support-bundle", headers=headers)
        assert res.status_code == 200
        bundle_data = res.json()
        assert bundle_data["status"] == "generated"
        assert "bundle_file" in bundle_data

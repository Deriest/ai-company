"""Unit tests for automation service."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal, engine, Base
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_hook_create_and_fire():
    """Create a hook, fire the event, verify it was triggered."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create hook
        res = await ac.post("/hooks", json={
            "event_type": "test.event",
            "name": "Test Hook",
            "action_type": "notify",
            "action_config": {"message": "Test fired"},
        })
        assert res.status_code == 200
        hook_id = res.json()["id"]

        # Fire event
        res = await ac.post("/hooks/fire/test.event")
        assert res.status_code == 200
        assert res.json()["fired"] == 1

        # Verify notification created
        res = await ac.get("/notifications")
        assert res.status_code == 200
        notifs = res.json()
        assert len(notifs) >= 1
        assert "Test fired" in notifs[0]["message"]


@pytest.mark.asyncio
async def test_hook_delete():
    """Deleting a hook should remove it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/hooks", json={
            "event_type": "x", "name": "X", "action_type": "notify", "action_config": {},
        })
        hook_id = res.json()["id"]

        await ac.delete(f"/hooks/{hook_id}")
        res = await ac.get("/hooks")
        assert len(res.json()) == 0


@pytest.mark.asyncio
async def test_trigger_create_and_list():
    """Create a trigger and list it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/triggers", json={
            "name": "High CPU",
            "condition": {"field": "cpu", "op": "gt", "value": "90"},
            "action": {"type": "notify", "config": {"message": "CPU high!"}},
        })
        assert res.status_code == 200

        res = await ac.get("/triggers")
        assert len(res.json()) == 1
        assert res.json()[0]["name"] == "High CPU"


@pytest.mark.asyncio
async def test_notification_mark_read():
    """Mark a notification as read."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a hook and fire it to generate a notification
        await ac.post("/hooks", json={
            "event_type": "read.test", "name": "Read Test",
            "action_type": "notify", "action_config": {"message": "Read me"},
        })
        await ac.post("/hooks/fire/read.test")

        res = await ac.get("/notifications?is_read=false")
        notifs = res.json()
        assert len(notifs) >= 1

        # Mark read
        await ac.patch(f"/notifications/{notifs[0]['id']}/read")
        res = await ac.get("/notifications?is_read=true")
        assert len(res.json()) >= 1


@pytest.mark.asyncio
async def test_notification_mark_all_read():
    """Mark all notifications as read."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/hooks", json={
            "event_type": "multi.test", "name": "Multi",
            "action_type": "notify", "action_config": {"message": "Multi"},
        })
        await ac.post("/hooks/fire/multi.test")
        await ac.post("/hooks/fire/multi.test")

        res = await ac.get("/notifications?is_read=false")
        assert len(res.json()) >= 2

        await ac.post("/notifications/read-all")
        res = await ac.get("/notifications?is_read=false")
        assert len(res.json()) == 0

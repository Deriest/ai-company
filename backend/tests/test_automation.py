import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
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
        # FK-fallout cleanup: storage tables (messages, conversations, …) are
        # not part of the backend Base — drop them too so no child rows survive
        # the teardown. FK enforcement is relaxed only for the DROP (cross-
        # metadata FK references make a pure FK-ordered drop impossible) and
        # re-enabled before the connection returns to the pool.
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        from storage.models import Base as StorageBase
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("PRAGMA foreign_keys=ON"))
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_automation_hooks_and_notifications():
    """v2.3.8: Event hooks, triggers, notifications."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create event hook
        h_res = await ac.post("/hooks", json={
            "event_type": "job.completed",
            "name": "Notify on job complete",
            "action_type": "notify",
            "action_config": {"message": "A job completed!", "level": "success"},
        })
        assert h_res.status_code == 200
        hook_id = h_res.json()["id"]

        # 2. List hooks
        l_res = await ac.get("/hooks")
        assert l_res.status_code == 200
        assert len(l_res.json()) == 1

        # 3. Fire event
        f_res = await ac.post("/hooks/fire/job.completed")
        assert f_res.status_code == 200
        assert f_res.json()["fired"] == 1

        # 4. Check notification was created
        n_res = await ac.get("/notifications")
        assert n_res.status_code == 200
        notifs = n_res.json()
        assert len(notifs) >= 1
        assert notifs[0]["title"] == "Event: job.completed"

        # 5. Create trigger
        t_res = await ac.post("/triggers", json={
            "name": "High error rate",
            "condition": {"field": "error_rate", "op": "gt", "value": "0.1"},
            "action": {"type": "notify", "config": {"message": "Error rate high!"}},
        })
        assert t_res.status_code == 200

        # 6. List triggers
        lt = await ac.get("/triggers")
        assert lt.status_code == 200
        assert len(lt.json()) == 1

        # 7. Mark notification read
        notif_id = notifs[0]["id"]
        r_res = await ac.patch(f"/notifications/{notif_id}/read")
        assert r_res.status_code == 200
        assert r_res.json()["isRead"] is True

        # 8. Mark all read
        await ac.post("/notifications/read-all")

        # 9. Delete hook
        d_res = await ac.delete(f"/hooks/{hook_id}")
        assert d_res.status_code == 200

        l2 = await ac.get("/hooks")
        assert len(l2.json()) == 0

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
async def test_job_scheduler_crud():
    """v2.3.4: Job creation, listing, detail, cancel, pause, resume."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create jobs with different priorities
        j1 = await ac.post("/jobs", json={
            "title": "High priority task",
            "job_type": "custom",
            "payload": {"action": "test"},
            "priority": 1,
        })
        assert j1.status_code == 200
        assert j1.json()["priority"] == 1
        assert j1.json()["status"] == "queued"

        j2 = await ac.post("/jobs", json={
            "title": "Low priority task",
            "job_type": "custom",
            "payload": {"action": "test2"},
            "priority": 10,
        })
        assert j2.status_code == 200

        # 2. List jobs — should be ordered by priority
        l_res = await ac.get("/jobs")
        assert l_res.status_code == 200
        jobs = l_res.json()
        assert len(jobs) == 2
        assert jobs[0]["priority"] <= jobs[1]["priority"]

        # 3. Get job detail with logs
        d_res = await ac.get(f"/jobs/{j1.json()['id']}")
        assert d_res.status_code == 200
        assert "logs" in d_res.json()
        assert len(d_res.json()["logs"]) >= 1  # creation log

        # 4. Pause job
        p_res = await ac.post(f"/jobs/{j2.json()['id']}/pause")
        assert p_res.status_code == 200
        assert p_res.json()["status"] == "paused"

        # 5. Resume job
        r_res = await ac.post(f"/jobs/{j2.json()['id']}/resume")
        assert r_res.status_code == 200
        assert r_res.json()["status"] == "queued"

        # 6. Cancel job
        c_res = await ac.post(f"/jobs/{j1.json()['id']}/cancel")
        assert c_res.status_code == 200
        assert c_res.json()["status"] == "cancelled"

        # 7. Filter by status
        f_res = await ac.get("/jobs?status=cancelled")
        assert f_res.status_code == 200
        assert len(f_res.json()) == 1

        # 8. Cannot cancel already cancelled
        c2 = await ac.post(f"/jobs/{j1.json()['id']}/cancel")
        assert c2.status_code == 400


@pytest.mark.asyncio
async def test_job_scheduler_priority_ordering():
    """v2.3.4: Jobs should be ordered by priority."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create jobs in reverse priority order
        for p in [10, 5, 1, 8, 3]:
            await ac.post("/jobs", json={
                "title": f"Priority {p}",
                "job_type": "custom",
                "payload": {},
                "priority": p,
            })

        l_res = await ac.get("/jobs")
        jobs = l_res.json()
        priorities = [j["priority"] for j in jobs]
        assert priorities == sorted(priorities)

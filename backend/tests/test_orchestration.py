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
    # Clean up: drop and recreate using BOTH StorageBase and Base
    # StorageBase has conversations.user_id; Base has backend-only tables
    from storage.models import Base as StorageBase
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_orchestration_sequential():
    """v2.3.2: Sequential orchestration with task routing and shared context."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create conversation
        c_res = await ac.post("/conversations", json={"title": "Orchestration Test"})
        assert c_res.status_code == 200
        conv_id = c_res.json()["id"]

        # 2. Create orchestration session
        s_res = await ac.post("/orchestration/sessions", json={
            "conversation_id": conv_id,
            "mode": "sequential",
        })
        assert s_res.status_code == 200
        session = s_res.json()
        session_id = session["id"]
        assert session["status"] == "pending"
        assert session["mode"] == "sequential"

        # 3. Add tasks
        t1 = await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
            "worker_role": "planner",
            "title": "Plan the architecture",
            "description": "Design a REST API for a todo app",
        })
        assert t1.status_code == 200
        assert t1.json()["workerRole"] == "planner"

        t2 = await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
            "worker_role": "crafter",
            "title": "Implement the API",
            "description": "Write the FastAPI code",
            "depends_on": [t1.json()["id"]],
        })
        assert t2.status_code == 200

        t3 = await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
            "worker_role": "reviewer",
            "title": "Review the code",
            "description": "Check for bugs and security issues",
            "depends_on": [t2.json()["id"]],
        })
        assert t3.status_code == 200

        # 4. Execute session
        e_res = await ac.post(f"/orchestration/sessions/{session_id}/execute")
        assert e_res.status_code == 200
        assert e_res.json()["status"] in ("completed", "failed")  # may fail without real provider

        # 5. Get session detail
        d_res = await ac.get(f"/orchestration/sessions/{session_id}")
        assert d_res.status_code == 200
        detail = d_res.json()
        assert len(detail["tasks"]) == 3
        assert detail["sharedContext"] is not None

        # 6. List sessions
        l_res = await ac.get(f"/orchestration/sessions?conversation_id={conv_id}")
        assert l_res.status_code == 200
        assert len(l_res.json()) >= 1


@pytest.mark.asyncio
async def test_orchestration_parallel():
    """v2.3.2: Parallel orchestration with independent tasks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        c_res = await ac.post("/conversations", json={"title": "Parallel Test"})
        conv_id = c_res.json()["id"]

        s_res = await ac.post("/orchestration/sessions", json={
            "conversation_id": conv_id,
            "mode": "parallel",
        })
        session_id = s_res.json()["id"]

        # Add 3 independent tasks (no depends_on)
        for role in ["thinker", "crafter", "reviewer"]:
            await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
                "worker_role": role,
                "title": f"Task for {role}",
            })

        e_res = await ac.post(f"/orchestration/sessions/{session_id}/execute")
        assert e_res.status_code == 200

        d_res = await ac.get(f"/orchestration/sessions/{session_id}")
        tasks = d_res.json()["tasks"]
        assert len(tasks) == 3


@pytest.mark.asyncio
async def test_orchestration_cancel():
    """v2.3.2: Cancel a running or pending session."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        c_res = await ac.post("/conversations", json={"title": "Cancel Test"})
        conv_id = c_res.json()["id"]

        s_res = await ac.post("/orchestration/sessions", json={
            "conversation_id": conv_id,
            "mode": "sequential",
        })
        session_id = s_res.json()["id"]

        await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
            "worker_role": "thinker",
            "title": "Some task",
        })

        cancel_res = await ac.post(f"/orchestration/sessions/{session_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # Execute should fail on cancelled session
        e_res = await ac.post(f"/orchestration/sessions/{session_id}/execute")
        assert e_res.status_code == 400


@pytest.mark.asyncio
async def test_orchestration_approval():
    """v2.3.2: Approval chain for tasks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        c_res = await ac.post("/conversations", json={"title": "Approval Test"})
        conv_id = c_res.json()["id"]

        s_res = await ac.post("/orchestration/sessions", json={
            "conversation_id": conv_id,
            "mode": "sequential",
        })
        session_id = s_res.json()["id"]

        t_res = await ac.post(f"/orchestration/sessions/{session_id}/tasks", json={
            "worker_role": "crafter",
            "title": "Deploy to production",
        })
        task_id = t_res.json()["id"]

        # Request approval
        a_res = await ac.post(f"/orchestration/tasks/{task_id}/approval?reason=Needs review before deploy")
        assert a_res.status_code == 200
        approval_id = a_res.json()["id"]
        assert a_res.json()["status"] == "pending"

        # Resolve approval
        r_res = await ac.patch(f"/orchestration/approvals/{approval_id}", json={
            "approved": True,
            "notes": "Looks good, approved",
        })
        assert r_res.status_code == 200
        assert r_res.json()["status"] == "approved"

        # Check approvals in session detail
        d_res = await ac.get(f"/orchestration/sessions/{session_id}")
        assert len(d_res.json()["approvals"]) == 1
        assert d_res.json()["approvals"][0]["status"] == "approved"

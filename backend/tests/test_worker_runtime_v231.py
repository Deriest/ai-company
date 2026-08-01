import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db(monkeypatch):
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    # Mock _get_provider_config to return None, triggering graceful fallback
    from backend.services.chat_service import ChatService
    async def _mock_config(*args, **kwargs):
        return None
    monkeypatch.setattr(ChatService, "_get_provider_config", _mock_config)
    yield
    # Clean up: drop and recreate to isolate tests.
    # Use StorageBase (includes conversations.user_id) AND Base so the
    # next test sees the same schema init_db() produces.
    from backend.database.session import engine, Base
    from storage.models import Base as StorageBase
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_worker_runtime_v231():
    """v2.3.1 Worker Runtime: profiles, system prompts, metrics, enable/disable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. List workers — should auto-create all 5 defaults
        w_res = await ac.get("/runtime/workers")
        assert w_res.status_code == 200
        workers = w_res.json()
        assert len(workers) == 5
        roles = {w["role"] for w in workers}
        assert roles == {"thinker", "crafter", "reviewer", "planner", "manager"}

        # 2. Verify new fields exist
        thinker = next(w for w in workers if w["role"] == "thinker")
        assert thinker["label"] == "Thinker"
        assert "Reasoning" in thinker["description"]
        assert len(thinker["systemPrompt"]) > 10
        assert thinker["isEnabled"] is True
        assert "metrics" in thinker

        # 3. Update system prompt
        p_res = await ac.patch(f"/runtime/workers/thinker", json={
            "systemPrompt": "Custom thinker prompt for testing",
            "temperature": 0.1,
        })
        assert p_res.status_code == 200
        updated = p_res.json()
        assert updated["systemPrompt"] == "Custom thinker prompt for testing"
        assert updated["temperature"] == 0.1

        # 4. Disable a worker
        d_res = await ac.patch("/runtime/workers/reviewer", json={"isEnabled": False})
        assert d_res.status_code == 200
        assert d_res.json()["isEnabled"] is False

        # 5. Re-list — disabled worker should still appear
        l2 = await ac.get("/runtime/workers")
        assert l2.status_code == 200
        reviewer = next(w for w in l2.json() if w["role"] == "reviewer")
        assert reviewer["isEnabled"] is False

        # 6. Enable back
        e_res = await ac.patch("/runtime/workers/reviewer", json={"isEnabled": True})
        assert e_res.status_code == 200
        assert e_res.json()["isEnabled"] is True

        # 7. Metrics should have valid structure
        for w in workers:
            assert "totalExecutions" in w["metrics"]
            assert "currentlyRunning" in w["metrics"]
            assert isinstance(w["metrics"]["totalExecutions"], int)

        # 8. Test chat uses system prompt from worker
        c_res = await ac.post("/conversations", json={"title": "Worker Test"})
        assert c_res.status_code == 200
        conv_id = c_res.json()["id"]

        chat_res = await ac.post("/chat", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "Hello"}],
            "worker_role": "thinker",
            "model_id": "test-model",
        })
        assert chat_res.status_code == 200
        assert chat_res.json()["role"] == "assistant"

        # 9. After chat, metrics should reflect execution
        m_res = await ac.get("/runtime/workers")
        assert m_res.status_code == 200
        thinker_m = next(w for w in m_res.json() if w["role"] == "thinker")
        assert thinker_m["metrics"]["totalExecutions"] >= 1

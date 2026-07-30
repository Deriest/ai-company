import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal
from backend.services.search_service import init_fts5

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield

@pytest.mark.asyncio
async def test_ai_runtime_mvp():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create conversation
        c_res = await ac.post("/conversations", json={"title": "AI Runtime Test"})
        assert c_res.status_code == 200
        conv_id = c_res.json()["id"]

        # 2. Test Tool Dispatcher
        t_res = await ac.post("/tools/execute", json={
            "tool_name": "current_time",
            "arguments": {}
        })
        assert t_res.status_code == 200
        t_data = t_res.json()
        assert "current_time" in t_data["result"]

        # 3. Test Workers List & Patch
        w_res = await ac.get("/workers")
        assert w_res.status_code == 200
        workers = w_res.json()
        assert len(workers) >= 5
        thinker = next(w for w in workers if w["role"] == "thinker")
        
        p_res = await ac.patch(f"/workers/{thinker['id']}", json={"temperature": 0.5})
        assert p_res.status_code == 200
        assert p_res.json()["temperature"] == 0.5

        # 4. Test Chat Completion (Mock Fallback)
        chat_res = await ac.post("/chat", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "Write some python code"}],
            "model_id": "test-model"
        })
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert chat_data["role"] == "assistant"
        assert chat_data["content"] != ""

        # 5. Test Artifact Extraction
        # Note: Chat Completion mock response does not include a python markdown block naturally.
        # We manually test extraction in isolation or inject it here.
        mock_response = "Here is the code ```python\nprint('hello')\n```"
        from backend.services.artifact_service import artifact_service
        from backend.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db_session:
            extracted = await artifact_service.extract_and_store(db_session, conv_id, chat_data["id"], mock_response)
            assert len(extracted) >= 1
            assert extracted[0].language == "python"

        # 6. Test Chat Streaming (SSE)
        stream_res = await ac.post("/chat/stream", json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "Hello"}],
            "model_id": "test-model",
            "stream": True
        })
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers["content-type"]

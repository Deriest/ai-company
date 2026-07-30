import pytest
import pytest_asyncio
import os
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
async def test_conversation_engine_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Folder
        f_res = await ac.post("/folders", json={"name": "Projects"})
        assert f_res.status_code == 200
        folder = f_res.json()
        assert folder["name"] == "Projects"
        
        # 2. Create Conversation
        c_res = await ac.post("/conversations", json={
            "title": "Build Architecture",
            "folder_id": folder["id"],
            "tags": ["design", "arch"]
        })
        assert c_res.status_code == 200
        conv = c_res.json()
        assert conv["title"] == "Build Architecture"
        assert "design" in conv["tags"]
        
        # 3. Create Message
        m_res = await ac.post(f"/conversations/{conv['id']}/messages", json={
            "role": "user",
            "content": "Let's design the database schema.",
            "token_count": 10
        })
        assert m_res.status_code == 200
        msg = m_res.json()
        assert msg["role"] == "user"
        assert msg["content"] == "Let's design the database schema."
        
        # 4. Search FTS
        s_res = await ac.get("/conversations/search?q=database")
        assert s_res.status_code == 200
        results = s_res.json()
        assert len(results) > 0
        assert results[0]["target_type"] == "message"
        
        # 5. Duplicate Conversation
        d_res = await ac.post(f"/conversations/{conv['id']}/duplicate")
        assert d_res.status_code == 200
        dup = d_res.json()
        assert dup["title"] == "Build Architecture (Copy)"
        
        # 6. Export / Import
        e_res = await ac.get(f"/conversations/{conv['id']}/export?format=json")
        assert e_res.status_code == 200
        exported = e_res.json()
        assert exported["title"] == "Build Architecture"
        
        i_res = await ac.post("/conversations/import", json=exported)
        assert i_res.status_code == 200
        imported = i_res.json()
        assert imported["title"] == "Build Architecture"
        
        # 7. List Conversations
        l_res = await ac.get("/conversations")
        assert l_res.status_code == 200
        all_convs = l_res.json()
        assert len(all_convs) >= 3 # orig, dup, imported

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
        # FK-fallout cleanup: storage tables are not part of the backend Base —
        # drop them too so no child rows survive the teardown. FK enforcement is
        # relaxed only for the DROP and re-enabled before the pool returns.
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
async def test_mcp_framework():
    """v2.3.5: MCP registry, tool discovery, tool execution, approval."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register MCP server
        s_res = await ac.post("/mcp/servers", json={
            "name": "test-server",
            "endpoint": "stdio:///tmp/test-mcp",
            "description": "Test MCP server",
        })
        assert s_res.status_code == 200
        server_id = s_res.json()["id"]

        # 2. Discover tools
        d_res = await ac.post(f"/mcp/servers/{server_id}/discover", json={
            "tools": [
                {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object"}},
                {"name": "current_time", "description": "Get current time"},
            ],
        })
        assert d_res.status_code == 200
        tools = d_res.json()
        assert len(tools) == 2

        # 3. List tools
        l_res = await ac.get("/mcp/tools")
        assert l_res.status_code == 200
        assert len(l_res.json()) == 2

        # 4. Execute tool
        tool_id = tools[0]["id"]
        e_res = await ac.post(f"/mcp/tools/{tool_id}/execute", json={
            "arguments": {"path": "/tmp/test"},
        })
        assert e_res.status_code == 200
        # May fail (file doesn't exist) but should return structured response
        assert "status" in e_res.json()

        # 5. List executions
        ex_res = await ac.get("/mcp/executions")
        assert ex_res.status_code == 200
        assert len(ex_res.json()) >= 1

        # 6. Toggle tool
        t_res = await ac.patch(f"/mcp/servers/{server_id}", json={"is_enabled": False})
        assert t_res.status_code == 200


@pytest.mark.asyncio
async def test_memory_engine():
    """v2.3.6: Memory store, retrieve, forget, compress, stats."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Store memories at different scopes
        for i in range(5):
            await ac.post("/memory", json={
                "scope": "user",
                "key": f"pref_{i}",
                "value": {"setting": f"value_{i}"},
                "category": "preference",
                "importance": 0.3 + (i * 0.1),
            })

        await ac.post("/memory", json={
            "scope": "conversation",
            "scope_id": "conv-123",
            "key": "topic",
            "value": {"topic": "AI engineering"},
            "category": "context",
            "importance": 0.9,
        })

        # 2. Retrieve by scope
        r_res = await ac.get("/memory?scope=user")
        assert r_res.status_code == 200
        assert len(r_res.json()) == 5

        # 3. Retrieve by scope + scope_id
        r2 = await ac.get("/memory?scope=conversation&scope_id=conv-123")
        assert r2.status_code == 200
        assert len(r2.json()) == 1

        # 4. Retrieve by category
        r3 = await ac.get("/memory?scope=user&category=preference")
        assert r3.status_code == 200
        assert len(r3.json()) == 5

        # 5. Stats
        stats = await ac.get("/memory/stats?scope=user")
        assert stats.status_code == 200
        assert stats.json()["total_entries"] == 5

        # 6. Compress low-importance entries
        comp = await ac.post("/memory/compress", json={
            "scope": "user",
            "threshold": 0.5,
        })
        assert comp.status_code == 200

        # 7. Forget an entry
        entries = await ac.get("/memory?scope=user")
        if entries.json():
            entry_id = entries.json()[0]["id"]
            f_res = await ac.delete(f"/memory/{entry_id}")
            assert f_res.status_code == 200

        # 8. Stats after operations
        final_stats = await ac.get("/memory/stats?scope=user")
        assert final_stats.status_code == 200

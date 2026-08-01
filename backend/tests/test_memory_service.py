"""Unit tests for memory service."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal, engine, Base
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # Pre-cleanup: ensure clean state before test (handles cross-file isolation)
    from storage.models import Base as StorageBase
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield
    # Post-cleanup: drop and recreate using BOTH StorageBase and Base
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_memory_store_and_retrieve():
    """Store a memory entry and retrieve it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Store
        res = await ac.post("/memory", json={
            "scope": "user",
            "key": "favorite_color",
            "value": {"color": "blue"},
            "category": "preference",
            "importance": 0.8,
        })
        assert res.status_code == 200
        entry = res.json()
        assert entry["key"] == "favorite_color"
        assert entry["importance"] == 0.8

        # Retrieve
        res = await ac.get("/memory?scope=user")
        assert res.status_code == 200
        entries = res.json()
        assert len(entries) == 1
        assert entries[0]["value"]["color"] == "blue"


@pytest.mark.asyncio
async def test_memory_upsert():
    """Storing same key+scope should update, not duplicate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/memory", json={"scope": "user", "key": "x", "value": {"v": 1}})
        await ac.post("/memory", json={"scope": "user", "key": "x", "value": {"v": 2}})

        res = await ac.get("/memory?scope=user")
        entries = res.json()
        assert len(entries) == 1
        assert entries[0]["value"]["v"] == 2


@pytest.mark.asyncio
async def test_memory_forget():
    """Deleting a memory entry should remove it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/memory", json={"scope": "user", "key": "temp", "value": {}})
        entry_id = res.json()["id"]

        await ac.delete(f"/memory/{entry_id}")
        res = await ac.get("/memory?scope=user")
        assert len(res.json()) == 0


@pytest.mark.asyncio
async def test_memory_compress():
    """Compress low-importance entries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(5):
            await ac.post("/memory", json={
                "scope": "user",
                "key": f"low_{i}",
                "value": {"i": i},
                "importance": 0.1,
            })

        res = await ac.post("/memory/compress", json={"scope": "user", "threshold": 0.5})
        assert res.status_code == 200
        assert res.json()["compressed"] is True

        # Should have fewer active entries now
        res = await ac.get("/memory?scope=user")
        assert len(res.json()) < 5


@pytest.mark.asyncio
async def test_memory_stats():
    """Memory statistics should be accurate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(3):
            await ac.post("/memory", json={"scope": "user", "key": f"k{i}", "value": {}})

        res = await ac.get("/memory/stats?scope=user")
        assert res.status_code == 200
        stats = res.json()
        assert stats["total_entries"] == 3


@pytest.mark.asyncio
async def test_memory_scope_isolation():
    """Different scopes should be isolated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/memory", json={"scope": "user", "key": "x", "value": {}})
        await ac.post("/memory", json={"scope": "project", "key": "x", "value": {}})

        res = await ac.get("/memory?scope=user")
        assert len(res.json()) == 1
        res = await ac.get("/memory?scope=project")
        assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_memory_retrieval_by_category():
    """Retrieve memories filtered by category."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/memory", json={"scope": "user", "key": "a", "value": {}, "category": "fact"})
        await ac.post("/memory", json={"scope": "user", "key": "b", "value": {}, "category": "preference"})

        res = await ac.get("/memory?scope=user&category=fact")
        assert len(res.json()) == 1
        assert res.json()[0]["category"] == "fact"

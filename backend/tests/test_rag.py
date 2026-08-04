import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database.session import init_db, AsyncSessionLocal, engine, Base
from backend.services.search_service import init_fts5


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # Drop BOTH StorageBase (storage.models — rag_documents/rag_chunks live
    # here) and Base (backend tables) so the persistent data/aic.db never
    # accumulates rows across runs. Previously only Base was dropped, so
    # rag data leaked between runs and the count assertions became flaky.
    from storage.models import Base as StorageBase
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    async with AsyncSessionLocal() as db:
        await init_fts5(db)
    yield
    # Post-cleanup: drop and recreate both, leaving a clean DB for other tests.
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await init_fts5(db)


@pytest.mark.asyncio
async def test_rag_engine():
    """v2.3.7: RAG document loading, chunking, retrieval, context building."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Load documents
        d1 = await ac.post("/rag/documents", json={
            "title": "Python Guide",
            "content": "Python is a high-level programming language. " * 50,
            "content_type": "text",
            "chunk_size": 100,
        })
        assert d1.status_code == 200
        assert d1.json()["status"] == "ready"
        assert d1.json()["chunkCount"] > 0

        d2 = await ac.post("/rag/documents", json={
            "title": "FastAPI Guide",
            "content": "FastAPI is a modern web framework for Python. " * 50,
            "content_type": "text",
            "chunk_size": 100,
        })
        assert d2.status_code == 200

        # 2. List documents
        l_res = await ac.get("/rag/documents")
        assert l_res.status_code == 200
        assert len(l_res.json()) == 2

        # 3. Retrieve
        r_res = await ac.post("/rag/retrieve", json={"query": "Python programming", "top_k": 3})
        assert r_res.status_code == 200
        results = r_res.json()
        assert len(results) > 0
        assert all("similarity" in r for r in results)

        # 4. Build context
        c_res = await ac.post("/rag/context", json={
            "query": "web framework",
            "top_k": 3,
            "max_tokens": 500,
        })
        assert c_res.status_code == 200
        ctx = c_res.json()
        assert "context" in ctx
        assert "citations" in ctx
        assert ctx["chunksUsed"] > 0

        # 5. Delete document
        doc_id = d1.json()["id"]
        del_res = await ac.delete(f"/rag/documents/{doc_id}")
        assert del_res.status_code == 200

        l2 = await ac.get("/rag/documents")
        assert len(l2.json()) == 1

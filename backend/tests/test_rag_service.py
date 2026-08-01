"""Unit tests for RAG service."""
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
async def test_rag_load_and_list():
    """Load a document and list it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/rag/documents", json={
            "title": "Python Guide",
            "content": "Python is a programming language. " * 10,
            "chunk_size": 100,
        })
        assert res.status_code == 200
        doc = res.json()
        assert doc["status"] == "ready"
        assert doc["chunkCount"] > 0

        res = await ac.get("/rag/documents")
        assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_rag_retrieve():
    """Retrieve should return chunks with similarity scores."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/rag/documents", json={
            "title": "Test",
            "content": "The quick brown fox jumps over the lazy dog. " * 10,
            "chunk_size": 200,
        })

        res = await ac.post("/rag/retrieve", json={"query": "quick brown fox", "top_k": 3})
        assert res.status_code == 200
        results = res.json()
        assert len(results) > 0
        assert all("similarity" in r for r in results)
        assert all("content" in r for r in results)


@pytest.mark.asyncio
async def test_rag_context_builder():
    """Context should include citations and token count."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/rag/documents", json={
            "title": "Context Test",
            "content": "Machine learning is a subset of artificial intelligence. " * 10,
        })

        res = await ac.post("/rag/context", json={"query": "machine learning", "top_k": 2, "max_tokens": 500})
        assert res.status_code == 200
        ctx = res.json()
        assert "context" in ctx
        assert "citations" in ctx
        assert "totalTokens" in ctx
        assert ctx["chunksUsed"] > 0


@pytest.mark.asyncio
async def test_rag_delete_document():
    """Deleting a document should remove it and its chunks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/rag/documents", json={
            "title": "Delete Me",
            "content": "This will be deleted. " * 5,
        })
        doc_id = res.json()["id"]

        await ac.delete(f"/rag/documents/{doc_id}")
        res = await ac.get("/rag/documents")
        assert len(res.json()) == 0


@pytest.mark.asyncio
async def test_rag_multiple_documents():
    """Multiple documents should be searchable independently."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/rag/documents", json={
            "title": "Python",
            "content": "Python is great for data science. " * 5,
        })
        await ac.post("/rag/documents", json={
            "title": "JavaScript",
            "content": "JavaScript is used for web development. " * 5,
        })

        res = await ac.get("/rag/documents")
        assert len(res.json()) == 2

        # Search should return results from both
        res = await ac.post("/rag/retrieve", json={"query": "programming", "top_k": 5})
        assert len(res.json()) > 0

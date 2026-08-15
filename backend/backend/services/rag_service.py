"""
RAG Engine Service.

Document loading, chunking, embedding, retrieval, and context building.
Uses in-memory cosine similarity for vector search (no external vector DB dependency).
"""

import asyncio
import math
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from storage.models import Document, DocumentChunk
from backend.services.embedding_provider import embed_single, embed_texts

logger = logging.getLogger(__name__)

# PERF-FIX: numpy vectorized scoring when available (venv has numpy 2.x).
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover — packaged Python may omit numpy
    np = None
    _HAS_NUMPY = False

# Cap the number of chunks scanned per retrieval (full-table scan guard).
_SCAN_LIMIT = 2000

# QA-R5 FIX: maximum number of chunks a single retrieve() may return — an
# unbounded top_k (e.g. 2000) would balloon the response and client payload.
MAX_TOP_K = 20


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cosine_similarities_vectorized(query: list[float], embeddings: list[list[float]]) -> list[float]:
    """Vectorized cosine similarity (numpy) — one pass instead of a Python loop."""
    q = np.asarray(query, dtype=np.float64)
    m = np.asarray(embeddings, dtype=np.float64)
    if m.shape[0] == 0:
        return []
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return [0.0] * m.shape[0]
    m_norm = np.linalg.norm(m, axis=1)
    denom = m_norm * q_norm
    denom[denom == 0] = 1.0  # avoid division by zero
    return (m @ q / denom).tolist()


class RAGService:
    """Document ingestion, chunking, embedding, and retrieval."""

    @staticmethod
    async def load_document(
        db: AsyncSession,
        title: str,
        content: str,
        source: str = "",
        content_type: str = "text",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> Document:
        doc = Document(
            title=title,
            source=source,
            content_type=content_type,
            content=content,
            status="chunking",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Chunk the document
        chunks = RAGService._chunk_text(content, chunk_size, chunk_overlap)
        doc.chunk_count = len(chunks)
        doc.status = "embedding"
        await db.commit()

        # Embed each chunk — batch in a single thread offload (P1 #10: embed_*
        # is sync and may load a model / run a blocking probe). One to_thread
        # dispatch avoids N interleaved await points against the DB session.
        for i, (chunk_text, embedding) in enumerate(
            zip(chunks, await asyncio.to_thread(embed_texts, chunks))
        ):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_text,
                embedding=embedding,
                token_count=len(chunk_text.split()),
            )
            db.add(chunk)

        doc.status = "ready"
        from backend.services.embedding_provider import get_embedding_provider; doc.embedding_model = await asyncio.to_thread(get_embedding_provider, )
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap
            if start >= len(words):
                break
        return chunks if chunks else [text]

    @staticmethod
    async def list_documents(db: AsyncSession) -> list[Document]:
        res = await db.execute(select(Document).order_by(Document.created_at.desc()))
        return list(res.scalars().all())

    @staticmethod
    async def get_document(db: AsyncSession, doc_id: str) -> Optional[Document]:
        res = await db.execute(select(Document).where(Document.id == doc_id))
        return res.scalars().first()

    @staticmethod
    async def delete_document(db: AsyncSession, doc_id: str):
        doc = await RAGService.get_document(db, doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        # FIX: delete chunks explicitly so retrieve() never returns results for a
        # deleted document (titled "Unknown").
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        await db.delete(doc)
        await db.commit()

    @staticmethod
    async def retrieve(
        db: AsyncSession, query: str, top_k: int = 5
    ) -> list[dict]:
        """Retrieve top-k most similar chunks to the query."""
        # QA-R5 FIX: clamp top_k — callers may pass an unbounded value (or a
        # non-numeric one); neither should blow up retrieval or the response.
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, MAX_TOP_K))

        # P1 #10: embed_single is sync — run in a thread to avoid blocking the loop.
        query_embedding = await asyncio.to_thread(embed_single, query)

        # PERF-FIX: cap the scan (full-table guard) and use numpy vectorized
        # scoring instead of a pure-Python cosine loop over every chunk.
        res = await db.execute(
            select(DocumentChunk).order_by(DocumentChunk.created_at.desc()).limit(_SCAN_LIMIT)
        )
        all_chunks = res.scalars().all()

        scored = []
        if all_chunks:
            embedded_chunks = [c for c in all_chunks if c.embedding]
            if embedded_chunks:
                embeddings = [c.embedding for c in embedded_chunks]
                if _HAS_NUMPY:
                    sims = _cosine_similarities_vectorized(query_embedding, embeddings)
                else:  # pragma: no cover — pure-Python fallback
                    sims = [_cosine_similarity(query_embedding, e) for e in embeddings]
                scored = list(zip(sims, embedded_chunks))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, chunk in scored[:top_k]:
            doc = await RAGService.get_document(db, chunk.document_id)
            results.append({
                "chunkId": chunk.id,
                "documentId": chunk.document_id,
                "documentTitle": doc.title if doc else "Unknown",
                "content": chunk.content,
                "similarity": round(sim, 4),
                "chunkIndex": chunk.chunk_index,
                "tokenCount": chunk.token_count,
            })
        return results

    @staticmethod
    async def build_context(
        db: AsyncSession, query: str, top_k: int = 5, max_tokens: int = 2000
    ) -> dict:
        """Build a context string from retrieved chunks with citations."""
        results = await RAGService.retrieve(db, query, top_k)

        context_parts = []
        citations = []
        total_tokens = 0

        for i, r in enumerate(results):
            chunk_tokens = r.get("tokenCount", 0)
            if total_tokens + chunk_tokens > max_tokens:
                break
            context_parts.append(r["content"])
            citations.append({
                "index": i + 1,
                "documentTitle": r["documentTitle"],
                "chunkIndex": r["chunkIndex"],
                "similarity": r["similarity"],
            })
            total_tokens += chunk_tokens

        return {
            "context": "\n\n---\n\n".join(context_parts),
            "citations": citations,
            "totalTokens": total_tokens,
            "chunksUsed": len(context_parts),
        }


rag_service = RAGService()

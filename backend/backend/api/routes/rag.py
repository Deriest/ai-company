from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import json

from backend.database.session import get_db
from backend.api.dependencies import require_current_user

router = APIRouter(dependencies=[Depends(require_current_user)])

from backend.services.rag_service import rag_service


# ── RAG Engine Endpoints ─────────────────────────────────────

@router.post("/rag/documents")
async def load_rag_document(payload: dict, db: AsyncSession = Depends(get_db)):
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")
    doc = await rag_service.load_document(
        db,
        title=title,
        content=content,
        source=payload.get("source", ""),
        content_type=payload.get("content_type", "text"),
        chunk_size=payload.get("chunk_size", 500),
        chunk_overlap=payload.get("chunk_overlap", 50),
    )
    return {
        "id": doc.id, "title": doc.title, "status": doc.status,
        "chunkCount": doc.chunk_count, "embeddingModel": doc.embedding_model,
    }

@router.get("/rag/documents")
async def list_rag_documents(db: AsyncSession = Depends(get_db)):
    docs = await rag_service.list_documents(db)
    return [
        {"id": d.id, "title": d.title, "source": d.source, "contentType": d.content_type,
         "chunkCount": d.chunk_count, "status": d.status, "createdAt": d.created_at.isoformat()}
        for d in docs
    ]

@router.delete("/rag/documents/{doc_id}")
async def delete_rag_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await rag_service.delete_document(db, doc_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/rag/retrieve")
async def rag_retrieve(payload: dict, db: AsyncSession = Depends(get_db)):
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    results = await rag_service.retrieve(db, query, payload.get("top_k", 5))
    return results

@router.post("/rag/context")
async def rag_build_context(payload: dict, db: AsyncSession = Depends(get_db)):
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    context = await rag_service.build_context(
        db, query,
        top_k=payload.get("top_k", 5),
        max_tokens=payload.get("max_tokens", 2000),
    )
    return context

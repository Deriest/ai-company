"""AIC Platform — Context & Knowledge Intelligence API Routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_session
from backend.api.dependencies import require_current_user

logger = logging.getLogger("aic.context.api")

router = APIRouter()


class AddKnowledgeRequest(BaseModel):
    domain: str
    key: str
    value: str
    source: str = "manual"


class RecordDecisionRequest(BaseModel):
    decision: str
    rationale: str
    context: str = ""


class SearchRequest(BaseModel):
    query: str
    domain: str | None = None


@router.get("/{project_id}")
async def get_context(
    project_id: str,
    domain: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Get project context."""
    from context.engine import ContextEngine

    engine = ContextEngine(session)
    context = await engine.get_context(project_id, domain)

    return context.to_dict()


@router.post("/knowledge")
async def add_knowledge(
    req: AddKnowledgeRequest,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
):
    """Add a knowledge entry."""
    from context.engine import ContextEngine

    engine = ContextEngine(session)
    entry = await engine.add_knowledge(
        domain=req.domain,
        key=req.key,
        value=req.value,
        source=req.source,
    )

    return {
        "id": entry.id,
        "domain": entry.domain,
        "key": entry.key,
        "value": entry.value,
        "source": entry.source,
    }


@router.post("/decisions")
async def record_decision(
    req: RecordDecisionRequest,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
):
    """Record an engineering decision."""
    from context.engine import ContextEngine

    engine = ContextEngine(session)
    record = await engine.record_decision(
        decision=req.decision,
        rationale=req.rationale,
        context=req.context,
    )

    return {
        "id": record.id,
        "decision": record.decision,
        "rationale": record.rationale,
    }


@router.post("/search")
async def search_knowledge(
    req: SearchRequest,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
):
    """Search knowledge entries."""
    from context.engine import ContextEngine

    engine = ContextEngine(session)
    results = await engine.search_knowledge(req.query, req.domain)

    return [
        {
            "id": e.id,
            "domain": e.domain,
            "key": e.key,
            "value": e.value,
        }
        for e in results
    ]


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get knowledge base statistics."""
    from context.engine import ContextEngine

    engine = ContextEngine(session)
    stats = engine.get_stats()

    return stats


@router.post("/assemble")
async def assemble_context(
    req: SearchRequest,
    conversation_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    _auth: str = Depends(require_current_user),
):
    """Assemble context for a query."""
    from context.builder import create_builder

    builder = create_builder(
        session,
        conversation_id=conversation_id,
        token_budget=4000,
    )

    assembly = await builder.build(req.query)

    return {
        "chunks": len(assembly.chunks),
        "total_tokens": assembly.total_tokens,
        "sources_used": assembly.sources_used,
        "context": builder.format_for_prompt(assembly),
        "metadata": assembly.metadata,
    }


@router.get("/sources")
async def get_sources(
    session: AsyncSession = Depends(get_session),
):
    """Get available context sources."""
    from context.pipeline import create_default_pipeline

    pipeline = create_default_pipeline(session)
    sources = pipeline.get_sources()

    return {
        "sources": sources,
        "count": len(sources),
    }

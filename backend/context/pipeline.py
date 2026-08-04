"""Context Pipeline — Orchestrates context assembly from multiple sources.

Provides structured context assembly with:
- Source orchestration
- Token budget management
- Context merging
- Context formatting
- Context persistence
"""

import logging
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from context.sources import (
    ContextSource, ContextChunk, SourceResult,
    create_default_sources,
)

logger = logging.getLogger("aic.context.pipeline")


@dataclass
class ContextAssembly:
    """Result of a context pipeline assembly."""
    chunks: list[ContextChunk] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 4000
    assembly_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str | None = None  # Database ID after persistence

    @property
    def budget_used_pct(self) -> float:
        """Percentage of token budget used."""
        if self.token_budget == 0:
            return 0.0
        return (self.total_tokens / self.token_budget) * 100

    @property
    def is_within_budget(self) -> bool:
        """Whether assembly is within token budget."""
        return self.total_tokens <= self.token_budget

    def to_prompt_context(self) -> str:
        """Convert assembly to prompt-ready context string."""
        if not self.chunks:
            return ""

        parts = []
        for chunk in self.chunks:
            if chunk.source == "rag":
                parts.append(f"[Document Context]\n{chunk.content}")
            elif chunk.source == "knowledge":
                parts.append(f"[Knowledge Base]\n{chunk.content}")
            elif chunk.source == "memory":
                parts.append(f"[Memory]\n{chunk.content}")
            elif chunk.source == "conversation":
                parts.append(f"[Conversation History]\n{chunk.content}")
            elif chunk.source == "workspace":
                parts.append(f"[Workspace]\n{chunk.content}")
            else:
                parts.append(chunk.content)

        return "\n\n---\n\n".join(parts)

    def copy(self) -> "ContextAssembly":
        """Return a deep copy so cached assemblies can never be mutated by callers."""
        return copy.deepcopy(self)


class ContextPipeline:
    """Orchestrates context assembly from multiple sources."""

    def __init__(
        self,
        sources: list[ContextSource] | None = None,
        token_budget: int = 4000,
        conversation_id: str | None = None,
        cache: Any = None,
    ):
        self.sources = sources or []
        self.token_budget = token_budget
        self.conversation_id = conversation_id
        self.cache = cache  # optional ContextCache; None disables caching

    async def assemble(
        self,
        query: str,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ContextAssembly:
        """Assemble context from all sources.

        Args:
            query: Search query or context description
            max_tokens: Override token budget
            **kwargs: Additional parameters passed to sources

        Returns:
            ContextAssembly with merged context
        """
        import time
        start = time.time()

        budget = max_tokens or self.token_budget

        # PERF-FIX: serve repeat assemblies from the TTL/LRU context cache,
        # keyed by (conversation_id, query, budget). A deep copy is returned so
        # callers can freely mutate the assembly.
        cache = self.cache
        if cache is not None and self.conversation_id:
            cached = cache.get(query, conversation_id=self.conversation_id, budget=budget)
            if cached is not None:
                logger.debug(f"Context cache hit for conversation {self.conversation_id}")
                return cached.copy()

        all_chunks: list[ContextChunk] = []
        sources_used: list[str] = []
        total_tokens = 0

        # Collect from all sources
        for source in self.sources:
            if not await source.is_available():
                continue

            try:
                result = await source.retrieve(
                    query,
                    max_tokens=budget - total_tokens,
                    **kwargs,
                )

                if result.chunks:
                    all_chunks.extend(result.chunks)
                    sources_used.append(result.source)
                    total_tokens += result.total_tokens

                    logger.debug(
                        f"Source {result.source}: "
                        f"{len(result.chunks)} chunks, "
                        f"{result.total_tokens} tokens, "
                        f"{result.query_time_ms:.1f}ms"
                    )

                # Stop if budget exhausted
                if total_tokens >= budget:
                    logger.debug(f"Token budget exhausted at source {result.source}")
                    break

            except Exception as e:
                logger.warning(f"Source {source.name} failed: {e}")
                continue

        # Sort by relevance (highest first)
        all_chunks.sort(key=lambda c: c.relevance, reverse=True)

        # Trim to budget if over
        trimmed_chunks: list[ContextChunk] = []
        trimmed_tokens = 0
        for chunk in all_chunks:
            if trimmed_tokens + chunk.token_count > budget:
                break
            trimmed_chunks.append(chunk)
            trimmed_tokens += chunk.token_count

        elapsed = (time.time() - start) * 1000

        assembly = ContextAssembly(
            chunks=trimmed_chunks,
            sources_used=sources_used,
            total_tokens=trimmed_tokens,
            token_budget=budget,
            assembly_time_ms=elapsed,
            metadata={
                "query": query,
                "sources_available": len(self.sources),
                "sources_used": len(sources_used),
                "chunks_total": len(all_chunks),
                "chunks_trimmed": len(all_chunks) - len(trimmed_chunks),
            },
        )

        logger.info(
            f"Context assembled: {len(trimmed_chunks)} chunks, "
            f"{trimmed_tokens}/{budget} tokens, "
            f"{elapsed:.1f}ms, "
            f"sources: {sources_used}"
        )

        if cache is not None and self.conversation_id:
            cache.set(query, assembly, conversation_id=self.conversation_id, budget=budget)

        return assembly

    def add_source(self, source: ContextSource) -> None:
        """Add a source to the pipeline."""
        self.sources.append(source)
        self.sources.sort(key=lambda s: s.priority)

    def remove_source(self, name: str) -> None:
        """Remove a source by name."""
        self.sources = [s for s in self.sources if s.name != name]

    def get_sources(self) -> list[dict[str, Any]]:
        """Get list of configured sources."""
        return [
            {
                "name": s.name,
                "priority": s.priority,
            }
            for s in self.sources
        ]

    async def persist(
        self,
        assembly: ContextAssembly,
        db: Any,
        conversation_id: str | None = None,
    ) -> str:
        """Persist assembly to database for audit trail.

        Args:
            assembly: Context assembly to persist
            db: Database session
            conversation_id: Optional conversation ID

        Returns:
            Database record ID
        """
        from storage.models import ContextAssemblyRecord
        from uuid import uuid4

        record_id = str(uuid4())
        record = ContextAssemblyRecord(
            id=record_id,
            conversation_id=conversation_id,
            query=assembly.metadata.get("query", ""),
            sources_used=assembly.sources_used,
            chunks_count=len(assembly.chunks),
            total_tokens=assembly.total_tokens,
            token_budget=assembly.token_budget,
            assembly_time_ms=assembly.assembly_time_ms,
            extra_metadata=assembly.metadata,
        )

        db.add(record)
        await db.flush()
        assembly.id = record_id

        logger.info(f"Context assembly persisted: {record_id}")
        return record_id


def create_default_pipeline(
    db: Any,
    conversation_id: str | None = None,
    project_id: str | None = None,
    token_budget: int = 4000,
) -> ContextPipeline:
    """Create a default context pipeline.

    Args:
        db: Database session
        conversation_id: Optional conversation ID
        project_id: Optional project ID
        token_budget: Token budget for assembly

    Returns:
        Configured ContextPipeline
    """
    sources = create_default_sources(db, conversation_id, project_id)
    # PERF-FIX: wire the global TTL/LRU context cache keyed by conversation.
    from context.cache import get_context_cache
    return ContextPipeline(
        sources=sources,
        token_budget=token_budget,
        conversation_id=conversation_id,
        cache=get_context_cache() if conversation_id else None,
    )

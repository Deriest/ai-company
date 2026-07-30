"""Context Builder — Structured context assembly with formatting.

Provides:
- Context formatting for different use cases
- Source prioritization and merging
- Context optimization
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from context.pipeline import ContextPipeline, ContextAssembly
from context.sources import ContextChunk

logger = logging.getLogger("aic.context.builder")


@dataclass
class BuildConfig:
    """Configuration for context building."""
    token_budget: int = 4000
    include_sources: list[str] = field(default_factory=lambda: [
        "conversation", "rag", "knowledge", "memory"
    ])
    format_style: str = "structured"  # structured, raw, compact
    include_metadata: bool = False
    deduplicate: bool = True


class ContextBuilder:
    """Builds structured context for LLM prompts."""

    def __init__(self, pipeline: ContextPipeline, config: BuildConfig | None = None):
        self.pipeline = pipeline
        self.config = config or BuildConfig()

    async def build(
        self,
        query: str,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ContextAssembly:
        """Build context for a query.

        Args:
            query: Search query or context description
            max_tokens: Override token budget
            **kwargs: Additional parameters

        Returns:
            ContextAssembly with built context
        """
        # Assemble from pipeline
        assembly = await self.pipeline.assemble(
            query,
            max_tokens=max_tokens or self.config.token_budget,
            **kwargs,
        )

        # Filter sources if configured
        if self.config.include_sources:
            assembly.chunks = [
                c for c in assembly.chunks
                if c.source in self.config.include_sources
            ]

        # Deduplicate if configured
        if self.config.deduplicate:
            assembly.chunks = self._deduplicate(assembly.chunks)

        # Recalculate tokens after filtering
        assembly.total_tokens = sum(c.token_count for c in assembly.chunks)

        logger.info(
            f"Context built: {len(assembly.chunks)} chunks, "
            f"{assembly.total_tokens} tokens"
        )

        return assembly

    def _deduplicate(self, chunks: list[ContextChunk]) -> list[ContextChunk]:
        """Remove duplicate content from chunks."""
        seen: set[str] = set()
        unique: list[ContextChunk] = []

        for chunk in chunks:
            # Use first 100 chars as dedup key
            key = chunk.content[:100]
            if key not in seen:
                seen.add(key)
                unique.append(chunk)

        return unique

    def format_for_prompt(
        self,
        assembly: ContextAssembly,
        style: str | None = None,
    ) -> str:
        """Format assembly for LLM prompt.

        Args:
            assembly: Context assembly
            style: Format style override

        Returns:
            Formatted context string
        """
        format_style = style or self.config.format_style

        if format_style == "raw":
            return self._format_raw(assembly)
        elif format_style == "compact":
            return self._format_compact(assembly)
        else:
            return self._format_structured(assembly)

    def _format_structured(self, assembly: ContextAssembly) -> str:
        """Format with clear source sections."""
        if not assembly.chunks:
            return ""

        sections: dict[str, list[str]] = {}
        for chunk in assembly.chunks:
            source_label = self._source_label(chunk.source)
            if source_label not in sections:
                sections[source_label] = []
            sections[source_label].append(chunk.content)

        parts = []
        for label, contents in sections.items():
            parts.append(f"[{label}]\n" + "\n---\n".join(contents))

        return "\n\n".join(parts)

    def _format_raw(self, assembly: ContextAssembly) -> str:
        """Format as raw concatenated text."""
        return "\n\n".join(c.content for c in assembly.chunks)

    def _format_compact(self, assembly: ContextAssembly) -> str:
        """Format with minimal whitespace."""
        return " ".join(c.content for c in assembly.chunks)

    def _source_label(self, source: str) -> str:
        """Get human-readable source label."""
        labels = {
            "conversation": "Conversation History",
            "rag": "Document Context",
            "knowledge": "Knowledge Base",
            "memory": "Memory",
            "workspace": "Workspace",
        }
        return labels.get(source, source.title())


def create_builder(
    db: Any,
    conversation_id: str | None = None,
    project_id: str | None = None,
    token_budget: int = 4000,
) -> ContextBuilder:
    """Create a default context builder.

    Args:
        db: Database session
        conversation_id: Optional conversation ID
        project_id: Optional project ID
        token_budget: Token budget

    Returns:
        Configured ContextBuilder
    """
    from context.pipeline import create_default_pipeline

    pipeline = create_default_pipeline(db, conversation_id, project_id, token_budget)
    config = BuildConfig(token_budget=token_budget)
    return ContextBuilder(pipeline=pipeline, config=config)

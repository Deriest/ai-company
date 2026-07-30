"""Context Runtime Events — Event emission for context operations.

Provides:
- Context assembly events
- Context cache events
- Context compression events
"""

import logging
from typing import Any

logger = logging.getLogger("aic.context.events")


class ContextEventEmitter:
    """Emits context-related events to the event bus."""

    def __init__(self, event_bus: Any = None):
        self.event_bus = event_bus

    async def emit_assembled(
        self,
        assembly_id: str,
        sources_used: list[str],
        total_tokens: int,
        assembly_time_ms: float,
    ) -> None:
        """Emit context.assembled event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "context.assembled",
                data={
                    "assembly_id": assembly_id,
                    "sources_used": sources_used,
                    "total_tokens": total_tokens,
                    "assembly_time_ms": assembly_time_ms,
                },
            )
            logger.debug(f"Emitted context.assembled event: {assembly_id}")
        except Exception as e:
            logger.warning(f"Failed to emit context.assembled event: {e}")

    async def emit_cached(
        self,
        query: str,
        cache_hit: bool,
    ) -> None:
        """Emit context.cached event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "context.cached",
                data={
                    "query": query[:100],  # Truncate for privacy
                    "cache_hit": cache_hit,
                },
            )
            logger.debug(f"Emitted context.cached event: hit={cache_hit}")
        except Exception as e:
            logger.warning(f"Failed to emit context.cached event: {e}")

    async def emit_compressed(
        self,
        original_tokens: int,
        compressed_tokens: int,
        compression_ratio: float,
        strategy: str,
    ) -> None:
        """Emit context.compressed event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "context.compressed",
                data={
                    "original_tokens": original_tokens,
                    "compressed_tokens": compressed_tokens,
                    "compression_ratio": compression_ratio,
                    "strategy": strategy,
                },
            )
            logger.debug(
                f"Emitted context.compressed event: "
                f"{original_tokens} -> {compressed_tokens} tokens"
            )
        except Exception as e:
            logger.warning(f"Failed to emit context.compressed event: {e}")

    async def emit_source_query(
        self,
        source: str,
        query: str,
        chunks_found: int,
        tokens: int,
        query_time_ms: float,
    ) -> None:
        """Emit context.source.query event."""
        if not self.event_bus:
            return

        try:
            await self.event_bus.publish(
                "context.source.query",
                data={
                    "source": source,
                    "query": query[:100],  # Truncate for privacy
                    "chunks_found": chunks_found,
                    "tokens": tokens,
                    "query_time_ms": query_time_ms,
                },
            )
            logger.debug(
                f"Emitted context.source.query event: "
                f"{source} -> {chunks_found} chunks"
            )
        except Exception as e:
            logger.warning(f"Failed to emit context.source.query event: {e}")


# Global emitter instance
_context_emitter = ContextEventEmitter()


def get_context_emitter() -> ContextEventEmitter:
    """Get the global context event emitter."""
    return _context_emitter


def set_context_event_bus(event_bus: Any) -> None:
    """Set the event bus for context events."""
    _context_emitter.event_bus = event_bus

"""Context Cache — Caching for context assembly.

Provides:
- Context caching with TTL
- Cache invalidation
- Cache statistics
"""

import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("aic.context.cache")


@dataclass
class CacheEntry:
    """A cached context assembly."""
    key: str
    value: Any
    conversation_id: str = ""
    created_at: float = field(default_factory=time.time)
    ttl: float = 300.0  # 5 minutes default
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Whether entry has expired."""
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Record a cache hit."""
        self.hits += 1


class ContextCache:
    """In-memory cache for context assemblies."""

    def __init__(self, max_size: int = 100, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def _make_key(self, query: str, **kwargs: Any) -> str:
        """Create cache key from query and parameters."""
        key_parts = [query]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, **kwargs: Any) -> Any | None:
        """Get cached assembly.

        Args:
            query: Query string
            **kwargs: Additional parameters

        Returns:
            Cached assembly or None
        """
        key = self._make_key(query, **kwargs)
        entry = self._cache.get(key)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        entry.touch()
        self._stats["hits"] += 1
        return entry.value

    def set(
        self,
        query: str,
        value: Any,
        ttl: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Cache an assembly.

        Args:
            query: Query string
            value: Assembly to cache
            ttl: Time to live in seconds
            **kwargs: Additional parameters
        """
        # Evict if at capacity
        if len(self._cache) >= self.max_size:
            self._evict()

        key = self._make_key(query, **kwargs)
        conversation_id = kwargs.pop("conversation_id", "")
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            conversation_id=conversation_id,
            ttl=ttl or self.default_ttl,
        )

    def invalidate_conversation(self, conversation_id: str) -> int:
        """Remove every cached entry for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of entries removed
        """
        if not conversation_id:
            return 0
        keys = [k for k, e in self._cache.items() if e.conversation_id == conversation_id]
        for k in keys:
            del self._cache[k]
        if keys:
            logger.debug(f"Invalidated {len(keys)} context cache entries for conversation {conversation_id}")
        return len(keys)

    def invalidate(self, query: str, **kwargs: Any) -> bool:
        """Invalidate a cached entry.

        Args:
            query: Query string
            **kwargs: Additional parameters

        Returns:
            True if entry was found and removed
        """
        key = self._make_key(query, **kwargs)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def _evict(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with fewest hits
        lru_key = min(self._cache, key=lambda k: self._cache[k].hits)
        del self._cache[lru_key]
        self._stats["evictions"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests
            if total_requests > 0
            else 0.0
        )

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": round(hit_rate, 3),
        }


# Global cache instance
_context_cache = ContextCache()


def get_context_cache() -> ContextCache:
    """Get the global context cache."""
    return _context_cache

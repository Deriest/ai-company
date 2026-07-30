"""AIC-ADE — Context Cache Tests."""

import pytest
import time
from context.cache import ContextCache, CacheEntry, get_context_cache


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_create_entry(self):
        entry = CacheEntry(key="test", value="data")
        assert entry.key == "test"
        assert entry.value == "data"
        assert entry.hits == 0

    def test_is_expired(self):
        entry = CacheEntry(key="test", value="data", ttl=0.0)
        time.sleep(0.01)
        assert entry.is_expired is True

    def test_not_expired(self):
        entry = CacheEntry(key="test", value="data", ttl=300.0)
        assert entry.is_expired is False

    def test_touch(self):
        entry = CacheEntry(key="test", value="data")
        entry.touch()
        assert entry.hits == 1


class TestContextCache:
    """Test ContextCache class."""

    def test_create_cache(self):
        cache = ContextCache(max_size=50, default_ttl=60.0)
        assert cache.max_size == 50
        assert cache.default_ttl == 60.0

    def test_set_and_get(self):
        cache = ContextCache()
        cache.set("query", "value")
        result = cache.get("query")
        assert result == "value"

    def test_get_miss(self):
        cache = ContextCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_get_expired(self):
        cache = ContextCache(default_ttl=0.0)
        cache.set("query", "value")
        time.sleep(0.01)
        result = cache.get("query")
        assert result is None

    def test_invalidate(self):
        cache = ContextCache()
        cache.set("query", "value")
        result = cache.invalidate("query")
        assert result is True
        assert cache.get("query") is None

    def test_invalidate_missing(self):
        cache = ContextCache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_clear(self):
        cache = ContextCache()
        cache.set("query1", "value1")
        cache.set("query2", "value2")
        cache.clear()
        assert cache.get("query1") is None
        assert cache.get("query2") is None

    def test_eviction(self):
        cache = ContextCache(max_size=2)
        cache.set("query1", "value1")
        cache.set("query2", "value2")
        cache.set("query3", "value3")  # Should evict query1
        assert cache.get("query1") is None
        assert cache.get("query2") == "value2"

    def test_stats(self):
        cache = ContextCache()
        cache.set("query", "value")
        cache.get("query")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_hit_rate(self):
        cache = ContextCache()
        cache.set("query", "value")
        cache.get("query")  # Hit
        cache.get("query")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.667, abs=0.01)


class TestGetContextCache:
    """Test get_context_cache function."""

    def test_returns_cache(self):
        cache = get_context_cache()
        assert isinstance(cache, ContextCache)

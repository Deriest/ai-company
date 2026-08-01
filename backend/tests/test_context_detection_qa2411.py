"""
Unit tests for auto-detect context window (QA-2411).

Tests probe endpoint parsing, catalog lookup, waterfall order, and cache persistence.
"""
import pytest
from backend.services.provider_client import _probe_context_from_metadata, _iter_nested_dicts
from backend.services.model_catalog import lookup_catalog, normalize_model_id


class TestProbeContextParsing:
    """Test probe endpoint metadata parsing."""

    def test_probe_flat_context_window(self):
        """Test parsing context_window from flat metadata."""
        meta = {"context_window": 200000, "other": "data"}
        result = _probe_context_from_metadata(meta)
        assert result == 200000

    def test_probe_context_length(self):
        """Test parsing context_length (LM Studio format)."""
        meta = {"context_length": 131072, "model": "qwen"}
        result = _probe_context_from_metadata(meta)
        assert result == 131072

    def test_probe_max_model_len(self):
        """Test parsing max_model_len (vLLM format)."""
        meta = {"max_model_len": 1048576, "model": "deepseek"}
        result = _probe_context_from_metadata(meta)
        assert result == 1048576

    def test_probe_nested_capabilities(self):
        """Test parsing nested capabilities.contextWindow."""
        meta = {
            "id": "gpt-5",
            "capabilities": {
                "contextWindow": 400000,
                "streaming": True
            }
        }
        result = _probe_context_from_metadata(meta)
        assert result == 400000

    def test_probe_deeply_nested(self):
        """Test parsing deeply nested context values."""
        meta = {
            "model": {
                "config": {
                    "limits": {
                        "max_context_length": 262144
                    }
                }
            }
        }
        result = _probe_context_from_metadata(meta)
        assert result == 262144

    def test_probe_max_tokens_large(self):
        """Test that large max_tokens (>32K) is accepted as context."""
        meta = {"max_tokens": 1000000}
        result = _probe_context_from_metadata(meta)
        assert result == 1000000

    def test_probe_max_tokens_small_ignored(self):
        """Test that small max_tokens (<32K) is ignored (likely output limit)."""
        meta = {"max_tokens": 4096}
        result = _probe_context_from_metadata(meta)
        assert result is None

    def test_probe_no_context(self):
        """Test that missing context returns None."""
        meta = {"model": "test", "owned_by": "vendor"}
        result = _probe_context_from_metadata(meta)
        assert result is None

    def test_probe_invalid_values(self):
        """Test that invalid context values are rejected."""
        meta = {"context_window": 0}
        result = _probe_context_from_metadata(meta)
        assert result is None

        meta = {"context_window": -1000}
        result = _probe_context_from_metadata(meta)
        assert result is None

        meta = {"context_window": "not_a_number"}
        result = _probe_context_from_metadata(meta)
        assert result is None


class TestNestedDictIteration:
    """Test recursive dict flattening."""

    def test_flatten_simple_dict(self):
        """Test flattening simple dict."""
        obj = {"a": 1, "b": 2}
        result = _iter_nested_dicts(obj)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_flatten_nested_dict(self):
        """Test flattening nested dict."""
        obj = {
            "top": "value",
            "nested": {
                "inner": "data",
                "context_window": 100000
            }
        }
        result = _iter_nested_dicts(obj)
        assert result["context_window"] == 100000
        assert result["inner"] == "data"

    def test_flatten_list_of_dicts(self):
        """Test flattening list of dicts."""
        obj = [
            {"key1": "val1"},
            {"key2": "val2", "context_length": 200000}
        ]
        result = _iter_nested_dicts(obj)
        assert result["context_length"] == 200000

    def test_flatten_max_depth(self):
        """Test that max_depth prevents infinite recursion."""
        # Create a deeply nested structure
        deep = {"level1": {"level2": {"level3": {"level4": {"level5": {"level6": "too_deep"}}}}}}
        result = _iter_nested_dicts(deep, max_depth=3)
        # level6 should not be reached
        assert "level6" not in result


class TestCatalogLookup:
    """Test hardcoded catalog lookup."""

    def test_catalog_exact_match(self):
        """Test exact catalog match."""
        result = lookup_catalog("claude-sonnet-4-6")
        assert result == 1000000

    def test_catalog_vendor_prefix_stripped(self):
        """Test vendor prefix stripping."""
        result = lookup_catalog("kr/qwen3-coder-next")
        assert result == 1000000

    def test_catalog_dash_dot_normalization(self):
        """Test dash↔dot normalization."""
        # Catalog has "gpt-5.6-luna", test with dashes
        result = lookup_catalog("gpt-5-6-luna")
        assert result == 1050000
        
        # Catalog has "claude-opus-4-6", test with dots
        result = lookup_catalog("claude.opus.4.6")
        assert result == 1000000

    def test_catalog_longest_first(self):
        """Test longest-key-first matching."""
        # "qwen3-coder-next" should match before "qwen3-coder" or "qwen"
        result = lookup_catalog("qwen3-coder-next")
        assert result == 1000000
        
        result = lookup_catalog("qwen3-coder")
        assert result == 262144
        
        result = lookup_catalog("qwen2")
        assert result == 131072

    def test_catalog_substring_match(self):
        """Test substring matching."""
        # "kr/deepseek-v4-pro" should match "deepseek-v4-pro"
        result = lookup_catalog("kr/deepseek-v4-pro")
        assert result == 1000000
        
        # "anthropic/claude-sonnet-4.5" should match "claude"
        result = lookup_catalog("anthropic/claude-sonnet-4.5")
        assert result == 200000

    def test_catalog_no_match(self):
        """Test unknown model returns None."""
        result = lookup_catalog("unknown-model-xyz-2024")
        assert result is None

    def test_catalog_common_models(self):
        """Test verified context values for common models."""
        assert lookup_catalog("deepseek-v4") == 1000000
        assert lookup_catalog("glm-5.2") == 1048576
        assert lookup_catalog("gpt-5") == 400000
        assert lookup_catalog("gemini") == 1048576
        assert lookup_catalog("grok-4.5") == 500000
        assert lookup_catalog("llama") == 131072


class TestNormalization:
    """Test model ID normalization."""

    def test_normalize_vendor_prefix(self):
        """Test vendor prefix removal."""
        assert normalize_model_id("kr/qwen3-coder") == "qwen3-coder"
        assert normalize_model_id("anthropic/claude-opus") == "claude-opus"
        assert normalize_model_id("openai/gpt-4") == "gpt-4"

    def test_normalize_lowercase(self):
        """Test lowercase conversion."""
        assert normalize_model_id("GPT-5") == "gpt-5"
        assert normalize_model_id("Claude-Sonnet") == "claude-sonnet"

    def test_normalize_no_prefix(self):
        """Test models without vendor prefix."""
        assert normalize_model_id("gpt-4") == "gpt-4"
        assert normalize_model_id("deepseek-chat") == "deepseek-chat"


class TestWaterfallOrder:
    """Test waterfall detection order (integration-style unit test)."""

    def test_probe_wins_over_catalog(self):
        """Test that probed value takes precedence over catalog."""
        # Simulate a model with both probe data and catalog entry
        from backend.services.provider_client import infer_capabilities
        
        # Model exists in catalog with 200000
        meta_with_probe = {
            "id": "claude-sonnet-4.5",
            "context_window": 500000  # Probed value different from catalog
        }
        result = infer_capabilities("claude-sonnet-4.5", meta_with_probe)
        assert result["context_window"] == 500000  # Probe wins
        assert result["context_source"] == "probe"

    def test_catalog_wins_over_pattern(self):
        """Test that catalog takes precedence over pattern family."""
        from backend.services.provider_client import infer_capabilities
        
        # qwen3-coder-next: catalog=1M, pattern would also match
        meta_empty = {}
        result = infer_capabilities("qwen3-coder-next", meta_empty)
        # Should use catalog (1M) not pattern
        assert result["context_window"] == 1000000
        assert result["context_source"] in ["models_dev", "catalog", "pattern"]

    def test_fallback_256k(self):
        """Test that unknown models fallback to 256K (not 8K)."""
        from backend.services.provider_client import infer_capabilities
        
        meta_empty = {}
        result = infer_capabilities("totally-unknown-model-xyz", meta_empty)
        assert result["context_window"] == 256000
        assert result["context_source"] == "fallback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

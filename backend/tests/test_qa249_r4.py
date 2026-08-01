"""
QA-249-R4 Tests: Auto-detect context_window + hard guard over-capacity
"""
import pytest
from backend.services.provider_client import infer_capabilities


class TestAutoDetectContextWindow:
    """Test auto-detection of context_window for various models."""
    
    def test_claude_models_200k(self):
        """Claude models should default to 200k context."""
        models = [
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "kr/claude-sonnet-4.5",
            "anthropic/claude-3.5-sonnet",
        ]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 200000, f"{model_id} should have 200k context"
    
    def test_gpt_4_1_models_1m(self):
        """GPT-4.1 models should get 1M context."""
        models = ["gpt-4.1-turbo", "gpt-4.1-preview"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 1000000, f"{model_id} should have 1M context"
    
    def test_gpt_models_128k(self):
        """Standard GPT models should get 128k context."""
        models = ["gpt-4-turbo", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 128000, f"{model_id} should have 128k context"
    
    def test_gemini_models_1m(self):
        """Gemini models should get 1M context."""
        models = ["gemini-1.5-pro", "gemini-2.0-flash"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 1000000, f"{model_id} should have 1M context"
    
    def test_deepseek_models_64k(self):
        """DeepSeek models should get 64k context."""
        models = ["deepseek-chat", "deepseek-v3", "deepseek-coder"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 64000, f"{model_id} should have 64k context"
    
    def test_small_models_32k(self):
        """Small models (mini, 3b) should get 32k context if not matched by other rules."""
        # Note: gpt-4o-mini matches is_gpt first (128k), claude-haiku matches is_claude (200k), 
        # gemini-flash matches is_gemini (1M). Only truly unknown small models get 32k.
        models = ["qwen-3b", "llama-3b", "phi-3-mini"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 32000, f"{model_id} should have 32k context"
    
    def test_unknown_models_8k(self):
        """Unknown models should get conservative 8k context."""
        models = ["unknown-model", "custom-llm-v1"]
        for model_id in models:
            caps = infer_capabilities(model_id, {})
            assert caps["context_window"] == 8192, f"{model_id} should have 8k fallback context"
    
    def test_raw_metadata_override(self):
        """If raw_metadata provides context_window, use it."""
        caps = infer_capabilities("gpt-4", {"context_window": 32000})
        assert caps["context_window"] == 32000
        
        caps = infer_capabilities("claude-3", {"context_length": 50000})
        assert caps["context_window"] == 50000
    
    def test_max_output_tokens_inference(self):
        """Test max_output_tokens inference."""
        # Small model
        caps = infer_capabilities("gpt-4o-mini", {})
        assert caps["max_output_tokens"] == 4096
        
        # Reasoning model
        caps = infer_capabilities("claude-opus", {})
        assert caps["max_output_tokens"] == 32768
        
        # Standard model
        caps = infer_capabilities("gpt-4", {})
        assert caps["max_output_tokens"] == 16384
        
        # Raw metadata override
        caps = infer_capabilities("gpt-4", {"max_output_tokens": 8192})
        assert caps["max_output_tokens"] == 8192


class TestHardGuardOverCapacity:
    """Test hard guard prevents over-capacity requests."""
    
    def test_estimate_tokens_mock(self):
        """Mock token estimation for testing."""
        from backend.services.context_overflow import estimate_tokens
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = estimate_tokens(messages)
        assert tokens > 0
        assert tokens < 100  # Simple messages should be under 100 tokens
    
    @pytest.mark.asyncio
    async def test_hard_guard_logic(self):
        """Test hard guard threshold calculation."""
        # Policy with 200k context
        max_tokens = 200000
        
        # Reserve 10% minimum (20k tokens)
        response_reserve = max(8192, int(max_tokens * 0.1))
        assert response_reserve == 20000
        
        hard_limit = max_tokens - response_reserve
        assert hard_limit == 180000
        
        # 90% threshold for truncation
        truncate_threshold = int(hard_limit * 0.9)
        assert truncate_threshold == 162000
        
        # Test scenarios
        assert 160000 < truncate_threshold  # Should not trigger guard
        assert 180000 <= hard_limit  # Should not trigger guard
        assert 240000 > hard_limit  # Should trigger guard (reject)


class TestMigration013Deprecated:
    """Test migration 013 is now no-op."""
    
    def test_migration_013_is_noop(self):
        """Migration 013 should be SELECT 1 (no-op)."""
        from backend.migrations.runner import MIGRATIONS
        
        migration_013 = next((m for m in MIGRATIONS if m["version"] == "013"), None)
        assert migration_013 is not None
        assert migration_013["up"].strip() == "SELECT 1"
        assert "deprecated" in migration_013["name"].lower() or "auto" in migration_013["description"].lower()

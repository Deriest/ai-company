"""Test embedding provider validation and production mode."""
import pytest
import os
from backend.services.embedding_provider import (
    get_embedding_provider,
    validate_embedding_provider,
    embed_single,
    _embedding_provider
)


def test_sentencetransformers_available():
    """Test that SentenceTransformers is available as default provider."""
    # Reset provider state
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None
    
    # Clear env to trigger auto-detection
    old_val = os.environ.get("AIC_EMBEDDING_PROVIDER")
    if "AIC_EMBEDDING_PROVIDER" in os.environ:
        del os.environ["AIC_EMBEDDING_PROVIDER"]
    
    try:
        provider = get_embedding_provider()
        # Should be sentencetransformers (installed) or hash (fallback)
        assert provider in ("sentencetransformers", "hash")
        
        if provider == "sentencetransformers":
            # Verify it actually works
            emb = embed_single("test text")
            assert isinstance(emb, list)
            assert len(emb) == 384  # all-MiniLM-L6-v2 dimension
    finally:
        if old_val:
            os.environ["AIC_EMBEDDING_PROVIDER"] = old_val
        ep._embedding_provider = None


def test_production_mode_blocks_hash():
    """Test that production mode raises error if only hash available."""
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None
    
    # Force hash fallback by clearing env and setting production mode
    old_provider = os.environ.get("AIC_EMBEDDING_PROVIDER")
    old_prod = os.environ.get("AIC_PRODUCTION_MODE")
    old_openai = os.environ.get("OPENAI_API_KEY")
    
    if "AIC_EMBEDDING_PROVIDER" in os.environ:
        del os.environ["AIC_EMBEDDING_PROVIDER"]
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    
    os.environ["AIC_PRODUCTION_MODE"] = "1"
    
    try:
        # Should raise if SentenceTransformers not available
        try:
            from sentence_transformers import SentenceTransformer
            # SentenceTransformers IS available, production mode should work
            provider = get_embedding_provider()
            assert provider == "sentencetransformers"
        except ImportError:
            # SentenceTransformers NOT available, production mode should raise
            with pytest.raises(RuntimeError, match="No embedding provider available in production mode"):
                get_embedding_provider()
    finally:
        if old_provider:
            os.environ["AIC_EMBEDDING_PROVIDER"] = old_provider
        elif "AIC_EMBEDDING_PROVIDER" in os.environ:
            del os.environ["AIC_EMBEDDING_PROVIDER"]
        
        if old_prod:
            os.environ["AIC_PRODUCTION_MODE"] = old_prod
        elif "AIC_PRODUCTION_MODE" in os.environ:
            del os.environ["AIC_PRODUCTION_MODE"]
        
        if old_openai:
            os.environ["OPENAI_API_KEY"] = old_openai
        
        ep._embedding_provider = None


def test_validate_embedding_provider():
    """Test embedding provider validation function."""
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None
    
    old_prod = os.environ.get("AIC_PRODUCTION_MODE")
    if "AIC_PRODUCTION_MODE" in os.environ:
        del os.environ["AIC_PRODUCTION_MODE"]
    
    try:
        validation = validate_embedding_provider()
        
        assert "provider" in validation
        assert "production_ready" in validation
        assert "warning" in validation
        
        # Provider should be sentencetransformers (if installed) or hash
        assert validation["provider"] in ("sentencetransformers", "hash", "openai", "ollama")
        
        # Hash is not production ready
        if validation["provider"] == "hash":
            assert validation["production_ready"] is False
            assert validation["warning"] is not None
        else:
            assert validation["production_ready"] is True
    finally:
        if old_prod:
            os.environ["AIC_PRODUCTION_MODE"] = old_prod
        ep._embedding_provider = None


def test_hash_fallback_dev_mode():
    """Test that hash fallback works in dev mode with warning."""
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None
    
    # Force hash by setting explicit provider
    old_val = os.environ.get("AIC_EMBEDDING_PROVIDER")
    old_prod = os.environ.get("AIC_PRODUCTION_MODE")
    
    os.environ["AIC_EMBEDDING_PROVIDER"] = "hash"
    if "AIC_PRODUCTION_MODE" in os.environ:
        del os.environ["AIC_PRODUCTION_MODE"]
    
    try:
        provider = get_embedding_provider()
        assert provider == "hash"
        
        # Should work in dev mode
        emb = embed_single("test")
        assert isinstance(emb, list)
        assert len(emb) == 384
        
        # Validation should warn
        validation = validate_embedding_provider()
        assert validation["production_ready"] is False
        assert "hash fallback" in validation["warning"].lower()
    finally:
        if old_val:
            os.environ["AIC_EMBEDDING_PROVIDER"] = old_val
        elif "AIC_EMBEDDING_PROVIDER" in os.environ:
            del os.environ["AIC_EMBEDDING_PROVIDER"]
        
        if old_prod:
            os.environ["AIC_PRODUCTION_MODE"] = old_prod
        
        ep._embedding_provider = None

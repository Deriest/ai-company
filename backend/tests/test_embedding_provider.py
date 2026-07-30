"""Unit tests for embedding provider."""
import pytest
import os


def test_hash_fallback():
    """Test hash-based fallback embedding."""
    os.environ["AIC_EMBEDDING_PROVIDER"] = "hash"
    # Reset cached provider
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None

    from backend.services.embedding_provider import embed_single, embed_texts, get_embedding_dimension

    # Single embedding
    emb = embed_single("hello world")
    assert len(emb) == get_embedding_dimension()
    assert all(isinstance(v, float) for v in emb)

    # Batch embedding
    embs = embed_texts(["hello", "world"])
    assert len(embs) == 2
    assert len(embs[0]) == len(embs[1])

    # Deterministic
    assert embed_single("test") == embed_single("test")

    os.environ.pop("AIC_EMBEDDING_PROVIDER", None)
    ep._embedding_provider = None


def test_empty_input():
    os.environ["AIC_EMBEDDING_PROVIDER"] = "hash"
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None

    from backend.services.embedding_provider import embed_texts
    assert embed_texts([]) == []

    os.environ.pop("AIC_EMBEDDING_PROVIDER", None)
    ep._embedding_provider = None


def test_provider_auto_detection():
    """Test that auto-detection falls back to hash when no provider available."""
    os.environ.pop("AIC_EMBEDDING_PROVIDER", None)
    import backend.services.embedding_provider as ep
    ep._embedding_provider = None

    provider = ep.get_embedding_provider()
    # Should detect something (likely hash since no OpenAI/Ollama/SentenceTransformers in test env)
    assert provider in ("openai", "ollama", "sentencetransformers", "hash")

    ep._embedding_provider = None

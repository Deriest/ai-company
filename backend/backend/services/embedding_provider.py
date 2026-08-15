"""
Embedding provider abstraction for RAG engine.

Supports multiple backends:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Ollama (local models)
- SentenceTransformers (local, no API key needed, DEFAULT)

Provider is selected via AIC_EMBEDDING_PROVIDER env var or auto-detected.

Production mode (AIC_PRODUCTION_MODE=1): Hash fallback disabled, fails fast if no real provider.
Development mode (default): Hash fallback allowed with warning.
"""

import os
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_embedding_provider: Optional[str] = None
_client = None


def get_embedding_provider() -> str:
    """Determine which embedding provider to use."""
    global _embedding_provider
    if _embedding_provider is not None:
        return _embedding_provider

    env_provider = os.getenv("AIC_EMBEDDING_PROVIDER", "").strip().lower()

    if env_provider:
        _embedding_provider = env_provider
    else:
        # Auto-detect: try providers in order (SentenceTransformers now preferred)
        try:
            import openai
            if os.getenv("OPENAI_API_KEY"):
                _embedding_provider = "openai"
                return _embedding_provider
        except ImportError:
            pass

        try:
            import httpx
            # Check if Ollama is running
            resp = httpx.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                _embedding_provider = "ollama"
                return _embedding_provider
        except Exception:
            pass

        try:
            from sentence_transformers import SentenceTransformer
            _embedding_provider = "sentencetransformers"
            logger.info("Using SentenceTransformers for embeddings (local, no API key needed)")
            return _embedding_provider
        except ImportError:
            pass

        # Production mode: fail fast instead of hash fallback
        is_production = os.getenv("AIC_PRODUCTION_MODE", "").strip() == "1"
        if is_production:
            raise RuntimeError(
                "No embedding provider available in production mode. "
                "Install sentence-transformers or configure OpenAI/Ollama."
            )

        _embedding_provider = "hash"
        logger.warning("No embedding provider found, using hash fallback (DEV MODE ONLY, not production-quality)")

    return _embedding_provider


def _embed_openai(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed using OpenAI API."""
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]


def _embed_ollama(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    """Embed using Ollama local API."""
    import httpx
    embeddings = []
    for text in texts:
        resp = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        embeddings.append(resp.json()["embedding"])
    return embeddings


_st_model = None

def _embed_sentencetransformers(texts: list[str], model: str = "all-MiniLM-L6-v2") -> list[list[float]]:
    """Embed using SentenceTransformers (local)."""
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer(model)
        logger.info(f"Loaded SentenceTransformer model: {model}")
    embeddings = _st_model.encode(texts, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


def _embed_hash(texts: list[str], dim: int = 384) -> list[list[float]]:
    """Fallback: deterministic hash-based pseudo-embedding. NOT production quality."""
    results = []
    for text in texts:
        h = hashlib.sha256(text.encode()).hexdigest()
        values = []
        for i in range(0, min(len(h), dim * 2), 2):
            values.append(int(h[i:i+2], 16) / 255.0)
        while len(values) < dim:
            values.append(0.0)
        results.append(values[:dim])
    return results


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the configured provider.
    Returns list of embedding vectors.
    """
    if not texts:
        return []

    provider = get_embedding_provider()

    try:
        if provider == "openai":
            return _embed_openai(texts)
        elif provider == "ollama":
            return _embed_ollama(texts)
        elif provider == "sentencetransformers":
            return _embed_sentencetransformers(texts)
        else:
            return _embed_hash(texts)
    except Exception as e:
        logger.error(f"Embedding provider '{provider}' failed: {e}, falling back to hash")
        return _embed_hash(texts)


def embed_single(text: str) -> list[float]:
    """Embed a single text."""
    return embed_texts([text])[0]


def validate_embedding_provider() -> dict:
    """Validate embedding provider and return status info.
    
    Returns dict with:
        - provider: str (openai/ollama/sentencetransformers/hash)
        - production_ready: bool
        - warning: str (if any)
    """
    try:
        provider = get_embedding_provider()
        is_production = os.getenv("AIC_PRODUCTION_MODE", "").strip() == "1"
        
        result = {
            "provider": provider,
            "production_ready": provider != "hash",
            "warning": None
        }
        
        if provider == "hash":
            if is_production:
                result["warning"] = "CRITICAL: Hash fallback in production mode"
            else:
                result["warning"] = "Using hash fallback (dev mode only)"
        
        return result
    except Exception as e:
        return {
            "provider": "none",
            "production_ready": False,
            "warning": f"Validation failed: {e}"
        }


def get_embedding_dimension() -> int:
    """Return the dimension of embeddings from the current provider."""
    provider = get_embedding_provider()
    if provider == "openai":
        return 1536  # text-embedding-3-small
    elif provider == "ollama":
        return 768  # nomic-embed-text default
    elif provider == "sentencetransformers":
        return 384  # all-MiniLM-L6-v2
    else:
        return 384  # hash fallback

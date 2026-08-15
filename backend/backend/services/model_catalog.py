"""Hardcoded model context window catalog.

This catalog provides verified context window values for major model families.
It mirrors the Hermes Agent catalog for accuracy and serves as a fallback when
probe/cache/models.dev lookups don't yield results.

Lookup logic:
- Normalize dash↔dot (e.g., "claude-opus-4.6" and "claude-opus-4-6" both match)
- Strip vendor prefix (e.g., "kr/qwen3-coder-next" → "qwen3-coder-next")
- Longest-key-first substring match for best specificity
"""
import logging
import re

logger = logging.getLogger(__name__)

# Context window catalog (in tokens) - verified values from production endpoints
MODEL_CONTEXT_CATALOG = {
    # Claude family
    "claude-fable-5": 1000000,
    "claude-opus-4-8": 1000000,
    "claude-opus-4-7": 1000000,
    "claude-opus-4-6": 1000000,
    "claude-sonnet-4-6": 1000000,
    "claude-sonnet-4-5": 200000,
    "claude": 200000,

    # GPT-5 family
    "gpt-5.6-luna": 1050000,
    "gpt-5.6-terra": 1050000,
    "gpt-5.6-sol": 1050000,
    "gpt-5.5": 1050000,
    "gpt-5.4": 1050000,
    "gpt-5.4-mini": 400000,
    "gpt-5.4-nano": 400000,
    "gpt-5": 400000,

    # GPT-4 family
    "gpt-4.1": 1047576,
    "gpt-4": 128000,

    # Gemini/Gemma family
    "gemini": 1048576,
    "gemma-4": 256000,
    "gemma-3": 131072,
    "gemma": 8192,

    # DeepSeek family
    "deepseek-v4-pro": 1000000,
    "deepseek-v4-flash": 1000000,
    "deepseek-v4": 1000000,
    "deepseek-chat": 1000000,
    "deepseek-reasoner": 1000000,
    "deepseek": 128000,

    # Llama family
    "llama": 131072,

    # Qwen family
    "qwen3.6-plus": 1048576,
    "qwen3-coder-plus": 1000000,
    "qwen3-coder-next": 1000000,
    "qwen3-coder": 262144,
    "qwen": 131072,

    # Minimax family
    "minimax-m3": 1000000,
    "minimax": 204800,

    # GLM family
    "glm-5.2": 1048576,
    "glm": 202752,

    # Grok family
    "grok-4.5": 500000,
    "grok-4.3": 1000000,
    "grok-4": 256000,
    "grok-3": 131072,
    "grok": 131072,

    # Kimi family
    "kimi": 262144,

    # Nemotron family
    "nemotron": 131072,

    # Mimo family
    "mimo-v2.5-pro": 1048576,
    "mimo-v2.5": 1048576,
    "mimo-v2-omni": 262144,
    "mimo-v2-flash": 262144,
}


def normalize_model_id(model_id: str) -> str:
    """Normalize model ID for catalog lookup.

    - Strip vendor prefix (e.g., "kr/qwen3-coder" → "qwen3-coder")
    - Convert to lowercase
    - Normalize dash↔dot (e.g., "4-6" ↔ "4.6")

    Returns the normalized base model ID.
    """
    # Strip vendor prefix
    base = model_id.split("/")[-1] if "/" in model_id else model_id
    # Convert to lowercase
    base = base.lower()
    return base


def lookup_catalog(model_id: str) -> int | None:
    """Lookup context window in the hardcoded catalog.

    Uses longest-key-first substring matching for best specificity.
    For example, "qwen3-coder-next" will match "qwen3-coder-next" before "qwen3-coder" or "qwen".

    Args:
        model_id: Model identifier (may include vendor prefix like "kr/qwen3-coder-next")

    Returns:
        Context window in tokens if found, None otherwise
    """
    normalized = normalize_model_id(model_id)

    # Also create dash↔dot variant for flexible matching.
    # Catalog keys use dash form (e.g. "claude-opus-4-6"). To match a dotted
    # input like "claude.opus.4.6" we need the FULL dot→dash conversion,
    # not just digit pairs — a regex on (\d)\.(\d) leaves "claude.opus.4-6".
    normalized_dot = re.sub(r"(\d)-(\d)", r"\1.\2", normalized)
    normalized_dash = normalized.replace(".", "-")

    # Sort catalog keys by length (longest first) for most specific match
    sorted_keys = sorted(MODEL_CONTEXT_CATALOG.keys(), key=len, reverse=True)

    for catalog_key in sorted_keys:
        catalog_key_lower = catalog_key.lower()

        # Try exact substring match with original, dot variant, and dash variant
        if (catalog_key_lower in normalized or
            catalog_key_lower in normalized_dot or
            catalog_key_lower in normalized_dash):
            context = MODEL_CONTEXT_CATALOG[catalog_key]
            logger.debug(
                f"Catalog match: {model_id} → {catalog_key} → {context} tokens"
            )
            return context

    logger.debug(f"No catalog match for model: {model_id}")
    return None

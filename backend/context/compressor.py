"""Context Compression — Intelligent context compression and summarization.

Provides:
- Context compression for long contexts
- Text summarization
- Smart truncation
"""

import logging
import re
from typing import Any

logger = logging.getLogger("aic.context.compressor")


def compress_whitespace(text: str) -> str:
    """Compress whitespace in text.

    Args:
        text: Text to compress

    Returns:
        Compressed text
    """
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def remove_redundancy(text: str) -> str:
    """Remove redundant lines from text.

    Args:
        text: Text to deduplicate

    Returns:
        Deduplicated text
    """
    lines = text.split('\n')
    seen: set[str] = set()
    unique_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            unique_lines.append(line)

    return '\n'.join(unique_lines)


def extract_key_sentences(text: str, max_sentences: int = 5) -> str:
    """Extract key sentences from text.

    Args:
        text: Text to extract from
        max_sentences: Maximum sentences to extract

    Returns:
        Extracted sentences
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= max_sentences:
        return text

    # Take first N sentences (could be improved with TF-IDF)
    selected = sentences[:max_sentences]
    return '. '.join(selected) + '.'


def compress_context(
    text: str,
    target_tokens: int,
    strategy: str = "balanced",
) -> tuple[str, dict[str, Any]]:
    """Compress context to target token count.

    Args:
        text: Text to compress
        target_tokens: Target token count
        strategy: Compression strategy (aggressive, balanced, conservative)

    Returns:
        Tuple of (compressed_text, metadata)
    """
    from context.tokens import count_tokens

    original_tokens = count_tokens(text)

    if original_tokens <= target_tokens:
        return text, {
            "original_tokens": original_tokens,
            "compressed_tokens": original_tokens,
            "compression_ratio": 1.0,
            "strategy": strategy,
        }

    # Apply compression based on strategy
    if strategy == "aggressive":
        compressed = _compress_aggressive(text, target_tokens)
    elif strategy == "conservative":
        compressed = _compress_conservative(text, target_tokens)
    else:
        compressed = _compress_balanced(text, target_tokens)

    compressed_tokens = count_tokens(compressed)

    return compressed, {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": round(compressed_tokens / original_tokens, 3),
        "strategy": strategy,
    }


def _compress_aggressive(text: str, target_tokens: int) -> str:
    """Aggressive compression — maximize reduction."""
    # Remove all whitespace redundancy
    text = compress_whitespace(text)
    # Remove redundancy
    text = remove_redundancy(text)
    # Truncate to target
    from context.tokens import truncate_to_budget
    text, _ = truncate_to_budget(text, target_tokens)
    return text


def _compress_balanced(text: str, target_tokens: int) -> str:
    """Balanced compression — maintain readability."""
    # Compress whitespace
    text = compress_whitespace(text)
    # Remove redundancy
    text = remove_redundancy(text)
    # Extract key sentences if still too long
    from context.tokens import count_tokens
    if count_tokens(text) > target_tokens:
        text = extract_key_sentences(text, max_sentences=10)
    # Truncate if still too long
    from context.tokens import truncate_to_budget
    if count_tokens(text) > target_tokens:
        text, _ = truncate_to_budget(text, target_tokens)
    return text


def _compress_conservative(text: str, target_tokens: int) -> str:
    """Conservative compression — minimal loss."""
    # Only compress whitespace
    text = compress_whitespace(text)
    # Truncate from end if needed
    from context.tokens import truncate_to_budget
    text, _ = truncate_to_budget(text, target_tokens)
    return text


def summarize_chunks(chunks: list[str], max_tokens: int = 500) -> str:
    """Summarize multiple chunks into a concise summary.

    Args:
        chunks: List of text chunks
        max_tokens: Maximum tokens for summary

    Returns:
        Summarized text
    """
    if not chunks:
        return ""

    # Combine all chunks
    combined = '\n\n---\n\n'.join(chunks)

    # Compress to target
    summary, _ = compress_context(combined, max_tokens, strategy="balanced")

    return summary

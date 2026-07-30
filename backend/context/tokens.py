"""Context Token Counting — Token budget management for context assembly.

Provides:
- Token counting for context
- Token budget management
- Context truncation
"""

import logging
from typing import Any

logger = logging.getLogger("aic.context.tokens")


def count_tokens(text: str) -> int:
    """Count tokens in text using simple word-based approximation.

    Args:
        text: Text to count tokens for

    Returns:
        Approximate token count
    """
    if not text:
        return 0
    # Simple approximation: ~1.3 tokens per word
    words = len(text.split())
    return int(words * 1.3)


def count_tokens_precise(text: str) -> int:
    """Count tokens more precisely (character-based approximation).

    Args:
        text: Text to count tokens for

    Returns:
        Approximate token count
    """
    if not text:
        return 0
    # ~4 characters per token for English text
    return len(text) // 4


def truncate_to_budget(
    text: str,
    max_tokens: int,
    from_end: bool = True,
) -> tuple[str, int]:
    """Truncate text to fit within token budget.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        from_end: If True, truncate from end; if False, from beginning

    Returns:
        Tuple of (truncated_text, actual_token_count)
    """
    current_tokens = count_tokens(text)
    if current_tokens <= max_tokens:
        return text, current_tokens

    # Calculate target character count
    target_chars = max_tokens * 4  # ~4 chars per token

    if from_end:
        truncated = text[:target_chars]
        # Try to break at word boundary
        last_space = truncated.rfind(' ')
        if last_space > target_chars * 0.8:
            truncated = truncated[:last_space]
    else:
        truncated = text[-target_chars:]
        # Try to break at word boundary
        first_space = truncated.find(' ')
        if first_space < target_chars * 0.2:
            truncated = truncated[first_space:]

    actual_tokens = count_tokens(truncated)
    return truncated, actual_tokens


def split_by_tokens(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into chunks by token count.

    Args:
        text: Text to split
        chunk_size: Target tokens per chunk
        overlap: Token overlap between chunks

    Returns:
        List of text chunks
    """
    if not text:
        return []

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        # Calculate chunk boundaries
        end = start + int(chunk_size / 1.3)  # Convert tokens to words
        chunk_words = words[start:end]

        if not chunk_words:
            break

        chunks.append(' '.join(chunk_words))

        # Move start forward with overlap
        start = end - int(overlap / 1.3)
        if start >= len(words):
            break

    return chunks


class TokenBudget:
    """Manages token budget for context assembly."""

    def __init__(self, total: int = 4000):
        self.total = total
        self.used = 0
        self.allocations: dict[str, int] = {}

    @property
    def remaining(self) -> int:
        """Remaining tokens in budget."""
        return max(0, self.total - self.used)

    @property
    def is_exhausted(self) -> bool:
        """Whether budget is exhausted."""
        return self.used >= self.total

    def allocate(self, source: str, tokens: int) -> bool:
        """Allocate tokens from budget.

        Args:
            source: Source name
            tokens: Tokens to allocate

        Returns:
            True if allocation successful, False if budget exceeded
        """
        if self.used + tokens > self.total:
            logger.warning(
                f"Token budget exhausted: {self.used}/{self.total}, "
                f"requested {tokens} for {source}"
            )
            return False

        self.used += tokens
        self.allocations[source] = self.allocations.get(source, 0) + tokens
        return True

    def get_allocation(self, source: str) -> int:
        """Get tokens allocated to a source."""
        return self.allocations.get(source, 0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "used": self.used,
            "remaining": self.remaining,
            "allocations": self.allocations,
        }

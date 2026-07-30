"""AIC-ADE — Context Token Counting Tests."""

import pytest
from context.tokens import (
    count_tokens, count_tokens_precise, truncate_to_budget,
    split_by_tokens, TokenBudget,
)


class TestCountTokens:
    """Test token counting functions."""

    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        assert count_tokens("hello") == 1

    def test_multiple_words(self):
        result = count_tokens("hello world test")
        assert result > 0
        assert result == int(3 * 1.3)

    def test_long_text(self):
        text = "word " * 100
        result = count_tokens(text)
        assert result > 100


class TestCountTokensPrecise:
    """Test precise token counting."""

    def test_empty_string(self):
        assert count_tokens_precise("") == 0

    def test_short_text(self):
        result = count_tokens_precise("hello")
        assert result == 1  # 5 chars / 4 = 1

    def test_longer_text(self):
        text = "a" * 100
        result = count_tokens_precise(text)
        assert result == 25  # 100 / 4 = 25


class TestTruncateToBudget:
    """Test text truncation."""

    def test_no_truncation_needed(self):
        text = "short text"
        result, tokens = truncate_to_budget(text, 1000)
        assert result == text

    def test_truncate_from_end(self):
        text = "word " * 1000
        result, tokens = truncate_to_budget(text, 10, from_end=True)
        assert len(result) < len(text)

    def test_truncate_from_beginning(self):
        text = "word " * 1000
        result, tokens = truncate_to_budget(text, 10, from_end=False)
        assert len(result) < len(text)


class TestSplitByTokens:
    """Test text splitting."""

    def test_empty_text(self):
        assert split_by_tokens("") == []

    def test_short_text(self):
        text = "short text"
        chunks = split_by_tokens(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text(self):
        text = "word " * 1000
        chunks = split_by_tokens(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1


class TestTokenBudget:
    """Test TokenBudget class."""

    def test_create_budget(self):
        budget = TokenBudget(4000)
        assert budget.total == 4000
        assert budget.used == 0
        assert budget.remaining == 4000

    def test_allocate_success(self):
        budget = TokenBudget(4000)
        result = budget.allocate("memory", 100)
        assert result is True
        assert budget.used == 100
        assert budget.remaining == 3900

    def test_allocate_exhausted(self):
        budget = TokenBudget(100)
        budget.allocate("source1", 100)
        result = budget.allocate("source2", 1)
        assert result is False
        assert budget.used == 100

    def test_is_exhausted(self):
        budget = TokenBudget(100)
        assert budget.is_exhausted is False
        budget.allocate("source", 100)
        assert budget.is_exhausted is True

    def test_get_allocation(self):
        budget = TokenBudget(4000)
        budget.allocate("memory", 500)
        assert budget.get_allocation("memory") == 500
        assert budget.get_allocation("unknown") == 0

    def test_to_dict(self):
        budget = TokenBudget(4000)
        budget.allocate("memory", 500)
        result = budget.to_dict()
        assert result["total"] == 4000
        assert result["used"] == 500
        assert result["remaining"] == 3500
        assert result["allocations"]["memory"] == 500

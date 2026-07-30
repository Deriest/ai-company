"""AIC-ADE — Context Compression Tests."""

import pytest
from context.compressor import (
    compress_whitespace, remove_redundancy, extract_key_sentences,
    compress_context, summarize_chunks,
)


class TestCompressWhitespace:
    """Test whitespace compression."""

    def test_multiple_spaces(self):
        assert compress_whitespace("hello   world") == "hello world"

    def test_tabs_and_newlines(self):
        assert compress_whitespace("hello\t\tworld\n\n") == "hello world"

    def test_leading_trailing(self):
        assert compress_whitespace("  hello  ") == "hello"


class TestRemoveRedundancy:
    """Test redundancy removal."""

    def test_duplicate_lines(self):
        text = "line1\nline2\nline1\nline3"
        result = remove_redundancy(text)
        assert result.count("line1") == 1

    def test_empty_lines(self):
        text = "line1\n\n\nline2"
        result = remove_redundancy(text)
        assert "line1" in result
        assert "line2" in result


class TestExtractKeySentences:
    """Test key sentence extraction."""

    def test_short_text(self):
        text = "First sentence. Second sentence."
        result = extract_key_sentences(text, max_sentences=5)
        assert result == text

    def test_long_text(self):
        text = " ".join([f"Sentence {i}." for i in range(20)])
        result = extract_key_sentences(text, max_sentences=3)
        assert "Sentence 0" in result
        assert "Sentence 1" in result
        assert "Sentence 2" in result


class TestCompressContext:
    """Test context compression."""

    def test_no_compression_needed(self):
        text = "short text"
        result, metadata = compress_context(text, 1000)
        assert result == text
        assert metadata["compression_ratio"] == 1.0

    def test_aggressive_compression(self):
        text = "word " * 1000
        result, metadata = compress_context(text, 100, strategy="aggressive")
        assert metadata["compressed_tokens"] <= 150  # Allow some margin

    def test_balanced_compression(self):
        text = "word " * 1000
        result, metadata = compress_context(text, 100, strategy="balanced")
        assert metadata["compressed_tokens"] <= 150  # Allow some margin

    def test_conservative_compression(self):
        text = "word " * 1000
        result, metadata = compress_context(text, 100, strategy="conservative")
        assert metadata["compressed_tokens"] <= 150  # Allow some margin

    def test_metadata_structure(self):
        text = "word " * 100
        _, metadata = compress_context(text, 50)
        assert "original_tokens" in metadata
        assert "compressed_tokens" in metadata
        assert "compression_ratio" in metadata
        assert "strategy" in metadata


class TestSummarizeChunks:
    """Test chunk summarization."""

    def test_empty_chunks(self):
        assert summarize_chunks([]) == ""

    def test_single_chunk(self):
        result = summarize_chunks(["single chunk"])
        assert "single chunk" in result

    def test_multiple_chunks(self):
        chunks = ["chunk1", "chunk2", "chunk3"]
        result = summarize_chunks(chunks, max_tokens=1000)
        assert "chunk1" in result
        assert "chunk2" in result
        assert "chunk3" in result

"""AIC-ADE — Context Source Adapters Tests."""

import pytest
from context.sources import (
    ContextChunk, SourceResult, ContextSource,
    MemorySource, RAGSource, KnowledgeSource,
    ConversationSource, WorkspaceSource,
    create_default_sources,
)


class TestContextChunk:
    """Test ContextChunk dataclass."""

    def test_create_chunk(self):
        chunk = ContextChunk(
            source="memory",
            content="test content",
            relevance=0.8,
            token_count=10,
        )
        assert chunk.source == "memory"
        assert chunk.content == "test content"
        assert chunk.relevance == 0.8
        assert chunk.token_count == 10
        assert chunk.metadata == {}

    def test_chunk_defaults(self):
        chunk = ContextChunk(source="test", content="content")
        assert chunk.relevance == 1.0
        assert chunk.token_count == 0
        assert chunk.metadata == {}


class TestSourceResult:
    """Test SourceResult dataclass."""

    def test_create_result(self):
        result = SourceResult(
            source="memory",
            chunks=[],
            total_tokens=0,
            query_time_ms=10.5,
        )
        assert result.source == "memory"
        assert result.chunks == []
        assert result.total_tokens == 0
        assert result.query_time_ms == 10.5

    def test_result_defaults(self):
        result = SourceResult(source="test")
        assert result.chunks == []
        assert result.total_tokens == 0
        assert result.query_time_ms == 0.0


class TestWorkspaceSource:
    """Test WorkspaceSource (stub)."""

    def test_name(self):
        source = WorkspaceSource()
        assert source.name == "workspace"

    def test_priority(self):
        source = WorkspaceSource()
        assert source.priority == 25

    @pytest.mark.asyncio
    async def test_is_available(self):
        source = WorkspaceSource()
        assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_retrieve(self):
        source = WorkspaceSource()
        result = await source.retrieve("test query")
        assert result.source == "workspace"
        assert result.chunks == []
        assert result.total_tokens == 0


class TestCreateDefaultSources:
    """Test create_default_sources function."""

    def test_creates_sources(self):
        sources = create_default_sources(None)
        assert len(sources) == 6
        assert all(isinstance(s, ContextSource) for s in sources)

    def test_sorted_by_priority(self):
        sources = create_default_sources(None)
        priorities = [s.priority for s in sources]
        assert priorities == sorted(priorities)

    def test_includes_all_types(self):
        sources = create_default_sources(None)
        names = {s.name for s in sources}
        assert "conversation" in names
        assert "rag" in names
        assert "knowledge" in names
        assert "memory" in names
        assert "workspace" in names


class TestMemorySourceStructure:
    """Test MemorySource structure."""

    def test_name(self):
        source = MemorySource(None)
        assert source.name == "memory"

    def test_priority(self):
        source = MemorySource(None)
        assert source.priority == 20

    @pytest.mark.asyncio
    async def test_is_available_no_db(self):
        source = MemorySource(None)
        assert await source.is_available() is False


class TestRAGSourceStructure:
    """Test RAGSource structure."""

    def test_name(self):
        source = RAGSource(None)
        assert source.name == "rag"

    def test_priority(self):
        source = RAGSource(None)
        assert source.priority == 10

    @pytest.mark.asyncio
    async def test_is_available_no_db(self):
        source = RAGSource(None)
        assert await source.is_available() is False


class TestKnowledgeSourceStructure:
    """Test KnowledgeSource structure."""

    def test_name(self):
        source = KnowledgeSource(None)
        assert source.name == "knowledge"

    def test_priority(self):
        source = KnowledgeSource(None)
        assert source.priority == 15

    @pytest.mark.asyncio
    async def test_is_available_no_db(self):
        source = KnowledgeSource(None)
        assert await source.is_available() is False


class TestConversationSourceStructure:
    """Test ConversationSource structure."""

    def test_name(self):
        source = ConversationSource(None)
        assert source.name == "conversation"

    def test_priority(self):
        source = ConversationSource(None)
        assert source.priority == 5

    @pytest.mark.asyncio
    async def test_is_available_no_db(self):
        source = ConversationSource(None)
        assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_is_available_no_conversation(self):
        source = ConversationSource("db")
        assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_retrieve_no_conversation(self):
        source = ConversationSource("db")
        result = await source.retrieve("test")
        assert result.source == "conversation"
        assert result.chunks == []

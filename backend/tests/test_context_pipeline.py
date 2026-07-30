"""AIC-ADE — Context Pipeline Tests."""

import pytest
from context.pipeline import ContextAssembly, ContextPipeline, create_default_pipeline
from context.sources import ContextSource, ContextChunk, SourceResult


class MockSource(ContextSource):
    """Mock context source for testing."""

    def __init__(self, name: str, priority: int, chunks: list[ContextChunk] | None = None):
        self._name = name
        self._priority = priority
        self._chunks = chunks or []
        self._available = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def retrieve(self, query: str, max_tokens: int = 2000, **kwargs) -> SourceResult:
        chunks = []
        total_tokens = 0
        for chunk in self._chunks:
            if total_tokens + chunk.token_count > max_tokens:
                break
            chunks.append(chunk)
            total_tokens += chunk.token_count
        return SourceResult(
            source=self._name,
            chunks=chunks,
            total_tokens=total_tokens,
            query_time_ms=1.0,
        )

    async def is_available(self) -> bool:
        return self._available


class TestContextAssembly:
    """Test ContextAssembly dataclass."""

    def test_create_assembly(self):
        assembly = ContextAssembly(
            chunks=[],
            sources_used=["memory"],
            total_tokens=100,
            token_budget=4000,
        )
        assert assembly.total_tokens == 100
        assert assembly.token_budget == 4000

    def test_budget_used_pct(self):
        assembly = ContextAssembly(total_tokens=2000, token_budget=4000)
        assert assembly.budget_used_pct == 50.0

    def test_is_within_budget(self):
        assembly = ContextAssembly(total_tokens=100, token_budget=4000)
        assert assembly.is_within_budget is True

        assembly2 = ContextAssembly(total_tokens=5000, token_budget=4000)
        assert assembly2.is_within_budget is False

    def test_to_prompt_context_empty(self):
        assembly = ContextAssembly()
        assert assembly.to_prompt_context() == ""

    def test_to_prompt_context_with_chunks(self):
        chunks = [
            ContextChunk(source="memory", content="memory content", token_count=2),
            ContextChunk(source="rag", content="rag content", token_count=2),
        ]
        assembly = ContextAssembly(chunks=chunks)
        context = assembly.to_prompt_context()
        assert "[Memory]" in context
        assert "[Document Context]" in context
        assert "memory content" in context
        assert "rag content" in context


class TestContextPipeline:
    """Test ContextPipeline."""

    def test_create_pipeline(self):
        pipeline = ContextPipeline()
        assert pipeline.sources == []
        assert pipeline.token_budget == 4000

    @pytest.mark.asyncio
    async def test_assemble_empty(self):
        pipeline = ContextPipeline()
        result = await pipeline.assemble("test query")
        assert result.chunks == []
        assert result.total_tokens == 0

    @pytest.mark.asyncio
    async def test_assemble_with_sources(self):
        source = MockSource("test", 10, [
            ContextChunk(source="test", content="content", token_count=5),
        ])
        pipeline = ContextPipeline(sources=[source])
        result = await pipeline.assemble("test query")
        assert len(result.chunks) == 1
        assert result.total_tokens == 5
        assert "test" in result.sources_used

    @pytest.mark.asyncio
    async def test_assemble_respects_budget(self):
        source = MockSource("test", 10, [
            ContextChunk(source="test", content="a " * 100, token_count=100),
            ContextChunk(source="test", content="b " * 100, token_count=100),
        ])
        pipeline = ContextPipeline(sources=[source], token_budget=50)
        result = await pipeline.assemble("test query")
        assert result.total_tokens <= 50

    @pytest.mark.asyncio
    async def test_assemble_multiple_sources(self):
        source1 = MockSource("source1", 10, [
            ContextChunk(source="source1", content="content1", token_count=5),
        ])
        source2 = MockSource("source2", 20, [
            ContextChunk(source="source2", content="content2", token_count=5),
        ])
        pipeline = ContextPipeline(sources=[source1, source2])
        result = await pipeline.assemble("test query")
        assert len(result.chunks) == 2
        assert "source1" in result.sources_used
        assert "source2" in result.sources_used

    @pytest.mark.asyncio
    async def test_assemble_skips_unavailable(self):
        source1 = MockSource("available", 10, [
            ContextChunk(source="available", content="content", token_count=5),
        ])
        source2 = MockSource("unavailable", 20)
        source2._available = False
        pipeline = ContextPipeline(sources=[source1, source2])
        result = await pipeline.assemble("test query")
        assert len(result.chunks) == 1
        assert "unavailable" not in result.sources_used

    def test_add_source(self):
        pipeline = ContextPipeline()
        source = MockSource("test", 10)
        pipeline.add_source(source)
        assert len(pipeline.sources) == 1

    def test_remove_source(self):
        source = MockSource("test", 10)
        pipeline = ContextPipeline(sources=[source])
        pipeline.remove_source("test")
        assert len(pipeline.sources) == 0

    def test_get_sources(self):
        source = MockSource("test", 10)
        pipeline = ContextPipeline(sources=[source])
        sources = pipeline.get_sources()
        assert len(sources) == 1
        assert sources[0]["name"] == "test"


class TestCreateDefaultPipeline:
    """Test create_default_pipeline function."""

    def test_creates_pipeline(self):
        pipeline = create_default_pipeline(None)
        assert isinstance(pipeline, ContextPipeline)
        assert len(pipeline.sources) > 0

    def test_custom_budget(self):
        pipeline = create_default_pipeline(None, token_budget=8000)
        assert pipeline.token_budget == 8000

"""AIC-ADE — Context Builder Tests."""

import pytest
from context.builder import ContextBuilder, BuildConfig, create_builder
from context.pipeline import ContextPipeline, ContextAssembly
from context.sources import ContextSource, ContextChunk, SourceResult


class MockSource(ContextSource):
    """Mock context source for testing."""

    def __init__(self, name: str, priority: int, chunks: list[ContextChunk] | None = None):
        self._name = name
        self._priority = priority
        self._chunks = chunks or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def retrieve(self, query: str, max_tokens: int = 2000, **kwargs) -> SourceResult:
        return SourceResult(
            source=self._name,
            chunks=self._chunks[:3],
            total_tokens=sum(c.token_count for c in self._chunks[:3]),
            query_time_ms=1.0,
        )

    async def is_available(self) -> bool:
        return True


class TestBuildConfig:
    """Test BuildConfig dataclass."""

    def test_default_config(self):
        config = BuildConfig()
        assert config.token_budget == 4000
        assert "conversation" in config.include_sources
        assert config.format_style == "structured"
        assert config.deduplicate is True

    def test_custom_config(self):
        config = BuildConfig(token_budget=8000, format_style="raw")
        assert config.token_budget == 8000
        assert config.format_style == "raw"


class TestContextBuilder:
    """Test ContextBuilder."""

    def test_create_builder(self):
        pipeline = ContextPipeline()
        builder = ContextBuilder(pipeline)
        assert builder.pipeline is pipeline

    @pytest.mark.asyncio
    async def test_build_empty(self):
        pipeline = ContextPipeline()
        builder = ContextBuilder(pipeline)
        result = await builder.build("test query")
        assert result.chunks == []
        assert result.total_tokens == 0

    @pytest.mark.asyncio
    async def test_build_with_sources(self):
        source = MockSource("memory", 10, [
            ContextChunk(source="memory", content="content", token_count=5),
        ])
        pipeline = ContextPipeline(sources=[source])
        builder = ContextBuilder(pipeline)
        result = await builder.build("test query")
        assert len(result.chunks) == 1

    @pytest.mark.asyncio
    async def test_build_deduplicate(self):
        chunks = [
            ContextChunk(source="memory", content="duplicate content", token_count=5),
            ContextChunk(source="memory", content="duplicate content", token_count=5),
            ContextChunk(source="memory", content="unique content", token_count=5),
        ]
        source = MockSource("memory", 10, chunks)
        pipeline = ContextPipeline(sources=[source])
        builder = ContextBuilder(pipeline, BuildConfig(deduplicate=True))
        result = await builder.build("test query")
        assert len(result.chunks) == 2

    @pytest.mark.asyncio
    async def test_build_filter_sources(self):
        source1 = MockSource("memory", 10, [
            ContextChunk(source="memory", content="memory", token_count=5),
        ])
        source2 = MockSource("rag", 20, [
            ContextChunk(source="rag", content="rag", token_count=5),
        ])
        pipeline = ContextPipeline(sources=[source1, source2])
        config = BuildConfig(include_sources=["memory"])
        builder = ContextBuilder(pipeline, config)
        result = await builder.build("test query")
        assert all(c.source == "memory" for c in result.chunks)

    def test_format_structured(self):
        chunks = [
            ContextChunk(source="memory", content="memory content", token_count=2),
            ContextChunk(source="rag", content="rag content", token_count=2),
        ]
        assembly = ContextAssembly(chunks=chunks)
        pipeline = ContextPipeline()
        builder = ContextBuilder(pipeline, BuildConfig(format_style="structured"))
        result = builder.format_for_prompt(assembly)
        assert "[Memory]" in result
        assert "[Document Context]" in result

    def test_format_raw(self):
        chunks = [
            ContextChunk(source="test", content="content1", token_count=2),
            ContextChunk(source="test", content="content2", token_count=2),
        ]
        assembly = ContextAssembly(chunks=chunks)
        pipeline = ContextPipeline()
        builder = ContextBuilder(pipeline, BuildConfig(format_style="raw"))
        result = builder.format_for_prompt(assembly)
        assert "content1" in result
        assert "content2" in result

    def test_format_compact(self):
        chunks = [
            ContextChunk(source="test", content="content1", token_count=2),
            ContextChunk(source="test", content="content2", token_count=2),
        ]
        assembly = ContextAssembly(chunks=chunks)
        pipeline = ContextPipeline()
        builder = ContextBuilder(pipeline, BuildConfig(format_style="compact"))
        result = builder.format_for_prompt(assembly)
        assert "content1 content2" == result


class TestCreateBuilder:
    """Test create_builder function."""

    def test_creates_builder(self):
        builder = create_builder(None)
        assert isinstance(builder, ContextBuilder)

    def test_custom_budget(self):
        builder = create_builder(None, token_budget=8000)
        assert builder.config.token_budget == 8000

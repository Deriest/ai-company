"""AIC-ADE — Context Runtime Events Tests."""

import pytest
from context.events import ContextEventEmitter, get_context_emitter, set_context_event_bus


class MockEventBus:
    """Mock event bus for testing."""

    def __init__(self):
        self.events = []

    async def publish(self, event_type: str, data: dict = None):
        self.events.append({"type": event_type, "data": data})


class TestContextEventEmitter:
    """Test ContextEventEmitter class."""

    def test_create_emitter(self):
        emitter = ContextEventEmitter()
        assert emitter.event_bus is None

    @pytest.mark.asyncio
    async def test_emit_assembled_no_bus(self):
        emitter = ContextEventEmitter()
        # Should not raise
        await emitter.emit_assembled("id", ["memory"], 100, 10.0)

    @pytest.mark.asyncio
    async def test_emit_assembled_with_bus(self):
        bus = MockEventBus()
        emitter = ContextEventEmitter(bus)
        await emitter.emit_assembled("id", ["memory"], 100, 10.0)
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "context.assembled"

    @pytest.mark.asyncio
    async def test_emit_cached_no_bus(self):
        emitter = ContextEventEmitter()
        await emitter.emit_cached("query", True)

    @pytest.mark.asyncio
    async def test_emit_cached_with_bus(self):
        bus = MockEventBus()
        emitter = ContextEventEmitter(bus)
        await emitter.emit_cached("query", True)
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "context.cached"

    @pytest.mark.asyncio
    async def test_emit_compressed_no_bus(self):
        emitter = ContextEventEmitter()
        await emitter.emit_compressed(1000, 500, 0.5, "balanced")

    @pytest.mark.asyncio
    async def test_emit_compressed_with_bus(self):
        bus = MockEventBus()
        emitter = ContextEventEmitter(bus)
        await emitter.emit_compressed(1000, 500, 0.5, "balanced")
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "context.compressed"

    @pytest.mark.asyncio
    async def test_emit_source_query_no_bus(self):
        emitter = ContextEventEmitter()
        await emitter.emit_source_query("memory", "query", 5, 100, 10.0)

    @pytest.mark.asyncio
    async def test_emit_source_query_with_bus(self):
        bus = MockEventBus()
        emitter = ContextEventEmitter(bus)
        await emitter.emit_source_query("memory", "query", 5, 100, 10.0)
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "context.source.query"


class TestGetContextEmitter:
    """Test get_context_emitter function."""

    def test_returns_emitter(self):
        emitter = get_context_emitter()
        assert isinstance(emitter, ContextEventEmitter)


class TestSetContextEventBus:
    """Test set_context_event_bus function."""

    def test_sets_event_bus(self):
        bus = MockEventBus()
        set_context_event_bus(bus)
        emitter = get_context_emitter()
        assert emitter.event_bus is bus

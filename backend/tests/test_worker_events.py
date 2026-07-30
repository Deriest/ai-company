"""AIC-ADE — Worker Events Tests."""

import pytest
from dispatcher.events import WorkerEventEmitter, get_worker_emitter, set_worker_event_bus


class MockEventBus:
    """Mock event bus for testing."""

    def __init__(self):
        self.events = []

    async def publish(self, event_type: str, data: dict = None):
        self.events.append({"type": event_type, "data": data})


class TestWorkerEventEmitter:
    """Test WorkerEventEmitter class."""

    def test_create_emitter(self):
        emitter = WorkerEventEmitter()
        assert emitter.event_bus is None

    @pytest.mark.asyncio
    async def test_emit_started_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_started("exec-1", "backend", "conv-1")

    @pytest.mark.asyncio
    async def test_emit_started_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_started("exec-1", "backend", "conv-1")
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.started"

    @pytest.mark.asyncio
    async def test_emit_completed_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_completed("exec-1", "backend", 100.0)

    @pytest.mark.asyncio
    async def test_emit_completed_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_completed("exec-1", "backend", 100.0)
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.completed"

    @pytest.mark.asyncio
    async def test_emit_failed_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_failed("exec-1", "backend", "error")

    @pytest.mark.asyncio
    async def test_emit_failed_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_failed("exec-1", "backend", "error")
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.failed"

    @pytest.mark.asyncio
    async def test_emit_progress_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_progress("exec-1", "backend", 0.5, "Half done")

    @pytest.mark.asyncio
    async def test_emit_progress_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_progress("exec-1", "backend", 0.5, "Half done")
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.progress"

    @pytest.mark.asyncio
    async def test_emit_queued_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_queued("task-1", "backend", 5)

    @pytest.mark.asyncio
    async def test_emit_queued_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_queued("task-1", "backend", 5)
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.queued"

    @pytest.mark.asyncio
    async def test_emit_dispatched_no_bus(self):
        emitter = WorkerEventEmitter()
        await emitter.emit_dispatched("task-1", "backend", "exec-1")

    @pytest.mark.asyncio
    async def test_emit_dispatched_with_bus(self):
        bus = MockEventBus()
        emitter = WorkerEventEmitter(bus)
        await emitter.emit_dispatched("task-1", "backend", "exec-1")
        assert len(bus.events) == 1
        assert bus.events[0]["type"] == "worker.dispatched"


class TestGetWorkerEmitter:
    """Test get_worker_emitter function."""

    def test_returns_emitter(self):
        emitter = get_worker_emitter()
        assert isinstance(emitter, WorkerEventEmitter)


class TestSetWorkerEventBus:
    """Test set_worker_event_bus function."""

    def test_sets_event_bus(self):
        bus = MockEventBus()
        set_worker_event_bus(bus)
        emitter = get_worker_emitter()
        assert emitter.event_bus is bus

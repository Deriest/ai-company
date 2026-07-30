"""AIC-ADE — Worker Queue Tests."""

import pytest
from dispatcher.queue import WorkerQueue, QueueTask, get_worker_queue


class TestQueueTask:
    """Test QueueTask dataclass."""

    def test_create_task(self):
        task = QueueTask(
            worker_role="backend",
            priority=5,
            task_type="code",
        )
        assert task.worker_role == "backend"
        assert task.priority == 5
        assert task.status == "pending"

    def test_task_comparison(self):
        task1 = QueueTask(priority=1)
        task2 = QueueTask(priority=5)
        assert task1 < task2


class TestWorkerQueue:
    """Test WorkerQueue class."""

    def test_create_queue(self):
        queue = WorkerQueue(max_size=100)
        assert queue.max_size == 100
        assert queue.size == 0

    def test_enqueue(self):
        queue = WorkerQueue()
        task = QueueTask(worker_role="backend")
        result = queue.enqueue(task)
        assert result is True
        assert queue.size == 1

    def test_enqueue_full(self):
        queue = WorkerQueue(max_size=1)
        queue.enqueue(QueueTask())
        result = queue.enqueue(QueueTask())
        assert result is False

    def test_dequeue(self):
        queue = WorkerQueue()
        task = QueueTask(worker_role="backend")
        queue.enqueue(task)
        result = queue.dequeue()
        assert result is not None
        assert result.worker_role == "backend"
        assert result.status == "scheduled"

    def test_dequeue_empty(self):
        queue = WorkerQueue()
        result = queue.dequeue()
        assert result is None

    def test_priority_order(self):
        queue = WorkerQueue()
        queue.enqueue(QueueTask(priority=5))
        queue.enqueue(QueueTask(priority=1))
        queue.enqueue(QueueTask(priority=3))

        task = queue.dequeue()
        assert task.priority == 1

    def test_peek(self):
        queue = WorkerQueue()
        task = QueueTask(priority=1)
        queue.enqueue(task)
        result = queue.peek()
        assert result is task

    def test_cancel(self):
        queue = WorkerQueue()
        task = QueueTask()
        queue.enqueue(task)
        result = queue.cancel(task.id)
        assert result is True
        assert queue.size == 0

    def test_get_pending(self):
        queue = WorkerQueue()
        queue.enqueue(QueueTask(status="pending"))
        queue.enqueue(QueueTask(status="pending"))
        pending = queue.get_pending()
        assert len(pending) == 2

    def test_get_by_role(self):
        queue = WorkerQueue()
        queue.enqueue(QueueTask(worker_role="backend"))
        queue.enqueue(QueueTask(worker_role="frontend"))
        backend_tasks = queue.get_by_role("backend")
        assert len(backend_tasks) == 1

    def test_get_stats(self):
        queue = WorkerQueue()
        queue.enqueue(QueueTask(worker_role="backend", priority=1))
        queue.enqueue(QueueTask(worker_role="frontend", priority=5))
        stats = queue.get_stats()
        assert stats["size"] == 2
        assert stats["by_role"]["backend"] == 1

    def test_clear(self):
        queue = WorkerQueue()
        queue.enqueue(QueueTask())
        queue.clear()
        assert queue.size == 0


class TestGetWorkerQueue:
    """Test get_worker_queue function."""

    def test_returns_queue(self):
        queue = get_worker_queue()
        assert isinstance(queue, WorkerQueue)

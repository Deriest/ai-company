"""AIC-ADE — Worker Progress Tests."""

import pytest
from dispatcher.progress import ProgressTracker, ProgressUpdate, get_progress_tracker


class TestProgressUpdate:
    """Test ProgressUpdate dataclass."""

    def test_create_update(self):
        update = ProgressUpdate(
            execution_id="exec-1",
            progress=0.5,
            message="Half done",
        )
        assert update.execution_id == "exec-1"
        assert update.progress == 0.5
        assert update.message == "Half done"


class TestProgressTracker:
    """Test ProgressTracker class."""

    def test_create_tracker(self):
        tracker = ProgressTracker()
        assert tracker.get_progress("exec-1") == 0.0

    def test_update_progress(self):
        tracker = ProgressTracker()
        update = tracker.update("exec-1", 0.5, "Half done")
        assert update.progress == 0.5
        assert tracker.get_progress("exec-1") == 0.5

    def test_get_message(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.5, "Half done")
        assert tracker.get_message("exec-1") == "Half done"

    def test_get_history(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.25, "Quarter")
        tracker.update("exec-1", 0.5, "Half")
        history = tracker.get_history("exec-1")
        assert len(history) == 2

    def test_complete(self):
        tracker = ProgressTracker()
        update = tracker.complete("exec-1", "Done")
        assert update.progress == 1.0

    def test_fail(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.5, "Working")
        update = tracker.fail("exec-1", "Error")
        assert update.message == "Error"

    def test_clear(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.5)
        tracker.clear("exec-1")
        assert tracker.get_progress("exec-1") == 0.0

    def test_get_all_progress(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.5)
        tracker.update("exec-2", 0.75)
        all_progress = tracker.get_all_progress()
        assert len(all_progress) == 2

    def test_get_stats(self):
        tracker = ProgressTracker()
        tracker.update("exec-1", 0.5)
        tracker.update("exec-2", 1.0)
        stats = tracker.get_stats()
        assert stats["total"] == 2
        assert stats["completed"] == 1
        assert stats["in_progress"] == 1


class TestGetProgressTracker:
    """Test get_progress_tracker function."""

    def test_returns_tracker(self):
        tracker = get_progress_tracker()
        assert isinstance(tracker, ProgressTracker)

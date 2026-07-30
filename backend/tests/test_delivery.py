"""AIC Platform — Delivery & Continuous Improvement Tests."""

import pytest
from delivery.config import DeliveryConfig, delivery_config
from delivery.models import EngineeringReport, LessonLearned, DeliveryResult
from delivery.engine import DeliveryEngine


# ============================================================
# Configuration Tests
# ============================================================

class TestDeliveryConfig:
    """Test delivery configuration."""

    def test_default_config(self):
        config = DeliveryConfig()
        assert config.enabled is True
        assert config.generate_reports is True
        assert config.extract_lessons is True

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_DELIVERY_ENABLED", "false")
        config = DeliveryConfig.from_env()
        assert config.enabled is False


# ============================================================
# Model Tests
# ============================================================

class TestDeliveryModels:
    """Test delivery data models."""

    def test_lesson_learned(self):
        lesson = LessonLearned(
            lesson="Always test edge cases",
            category="verification",
            impact="high",
        )
        assert lesson.id.startswith("LESSON-")
        assert lesson.lesson == "Always test edge cases"

    def test_engineering_report(self):
        report = EngineeringReport(
            brief_id="BRIEF-TEST",
            goal="Test goal",
            outcome="success",
        )
        assert report.report_id.startswith("RPT-")
        assert report.outcome == "success"

    def test_engineering_report_to_dict(self):
        report = EngineeringReport(
            brief_id="BRIEF-TEST",
            lessons=[
                LessonLearned(lesson="Test lesson"),
            ],
        )
        data = report.to_dict()
        assert "report_id" in data
        assert "lessons" in data


# ============================================================
# Engine Tests
# ============================================================

class TestDeliveryEngine:
    """Test delivery engine."""

    @pytest.fixture
    def engine(self):
        return DeliveryEngine()

    async def test_generate_report(self, engine):
        report = await engine.generate_report(
            brief_id="BRIEF-TEST",
            task_results={
                "N1": {"status": "completed"},
                "N2": {"status": "completed"},
            },
        )
        assert report.outcome == "success"
        assert report.total_tasks == 2

    async def test_generate_report_partial(self, engine):
        report = await engine.generate_report(
            brief_id="BRIEF-TEST",
            task_results={
                "N1": {"status": "completed"},
                "N2": {"status": "failed"},
            },
        )
        assert report.outcome == "partial"

    async def test_deliver(self, engine):
        result = await engine.deliver(
            brief_id="BRIEF-TEST",
            task_results={"N1": {"status": "completed"}},
        )
        assert result.report is not None
        assert result.report.outcome == "success"

    async def test_get_stats(self, engine):
        await engine.generate_report("BRIEF-1")
        stats = engine.get_stats()
        assert stats["total_reports"] >= 1

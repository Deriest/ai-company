"""AIC Platform — Autonomous Execution Intelligence Tests."""

import pytest
from autonomy.config import AutonomyConfig, autonomy_config
from autonomy.models import AnomalyDetection, RecoveryAction, HealingResult
from autonomy.engine import AutonomyEngine


# ============================================================
# Configuration Tests
# ============================================================

class TestAutonomyConfig:
    """Test autonomy configuration."""

    def test_default_config(self):
        config = AutonomyConfig()
        assert config.enabled is True
        assert config.max_recovery_attempts == 3
        assert config.self_healing_enabled is True

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("AIC_AUTONOMY_ENABLED", "false")
        config = AutonomyConfig.from_env()
        assert config.enabled is False


# ============================================================
# Model Tests
# ============================================================

class TestAutonomyModels:
    """Test autonomy data models."""

    def test_anomaly_detection(self):
        anomaly = AnomalyDetection(
            anomaly_type="timeout",
            severity="medium",
            description="Task timed out",
        )
        assert anomaly.id.startswith("ANOM-")
        assert anomaly.anomaly_type == "timeout"

    def test_recovery_action(self):
        action = RecoveryAction(
            action_type="retry",
            target="task-1",
        )
        assert action.id.startswith("REC-")
        assert action.action_type == "retry"

    def test_healing_result(self):
        result = HealingResult(
            anomaly_id="ANOM-TEST",
            action_taken="retry",
            success=True,
        )
        assert result.id.startswith("HEAL-")
        assert result.success is True


# ============================================================
# Engine Tests
# ============================================================

class TestAutonomyEngine:
    """Test autonomy engine."""

    @pytest.fixture
    def engine(self):
        return AutonomyEngine()

    async def test_detect_anomaly(self, engine):
        anomaly = await engine.detect_anomaly(
            anomaly_type="timeout",
            severity="medium",
            description="Task timed out",
        )
        assert anomaly.anomaly_type == "timeout"

    async def test_plan_recovery(self, engine):
        anomaly = await engine.detect_anomaly("timeout", "medium", "Test")
        action = await engine.plan_recovery(anomaly)
        assert action.action_type == "retry"

    async def test_execute_recovery(self, engine):
        action = RecoveryAction(action_type="retry", target="test")
        result = await engine.execute_recovery(action)
        assert result.success is True

    async def test_handle_anomaly(self, engine):
        result = await engine.handle_anomaly(
            anomaly_type="timeout",
            severity="medium",
            description="Task timed out",
        )
        assert result.success is True

    async def test_get_stats(self, engine):
        await engine.handle_anomaly("timeout", "medium", "Test")
        stats = engine.get_stats()
        assert stats["total_anomalies"] >= 1
        assert stats["total_healings"] >= 1

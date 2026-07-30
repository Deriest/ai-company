"""AIC Platform — Context, Autonomy, Delivery API Route Tests."""

import pytest
from context.config import ContextConfig
from autonomy.config import AutonomyConfig
from delivery.config import DeliveryConfig


# ============================================================
# Context API Tests
# ============================================================

class TestContextConfig:
    """Test context configuration for API routes."""

    def test_context_enabled(self):
        config = ContextConfig()
        assert config.enabled is True

    def test_context_max_entries(self):
        config = ContextConfig()
        assert config.max_knowledge_entries == 10000


# ============================================================
# Autonomy API Tests
# ============================================================

class TestAutonomyConfig:
    """Test autonomy configuration for API routes."""

    def test_autonomy_enabled(self):
        config = AutonomyConfig()
        assert config.enabled is True

    def test_autonomy_max_recovery(self):
        config = AutonomyConfig()
        assert config.max_recovery_attempts == 3


# ============================================================
# Delivery API Tests
# ============================================================

class TestDeliveryConfig:
    """Test delivery configuration for API routes."""

    def test_delivery_enabled(self):
        config = DeliveryConfig()
        assert config.enabled is True

    def test_delivery_reports(self):
        config = DeliveryConfig()
        assert config.generate_reports is True


# ============================================================
# Integration Tests
# ============================================================

class TestAPIRoutesExist:
    """Test that all API routes are registered."""

    def test_context_routes_importable(self):
        from backend.routes.context import router
        assert router is not None

    def test_autonomy_routes_importable(self):
        from backend.routes.autonomy import router
        assert router is not None

    def test_delivery_routes_importable(self):
        from backend.routes.delivery import router
        assert router is not None

"""AIC-ADE — Pricing Service Tests."""

import pytest
from backend.services.pricing_service import (
    ModelPricing, PricingService, get_pricing_service,
)


class TestModelPricing:
    """Test ModelPricing dataclass."""

    def test_create_pricing(self):
        pricing = ModelPricing(
            model_id="gpt-4o",
            provider="openai",
            prompt_price_per_1k=0.005,
            completion_price_per_1k=0.015,
        )
        assert pricing.model_id == "gpt-4o"
        assert pricing.provider == "openai"

    def test_calculate_cost(self):
        pricing = ModelPricing(
            model_id="test",
            provider="test",
            prompt_price_per_1k=0.01,
            completion_price_per_1k=0.03,
        )
        cost = pricing.calculate_cost(1000, 1000)
        assert cost == pytest.approx(0.04)

    def test_calculate_cost_with_cached(self):
        pricing = ModelPricing(
            model_id="test",
            provider="test",
            prompt_price_per_1k=0.01,
            completion_price_per_1k=0.03,
            cached_price_per_1k=0.005,
        )
        cost = pricing.calculate_cost(1000, 1000, 500)
        assert cost == pytest.approx(0.0425)


class TestPricingService:
    """Test PricingService class."""

    def test_create_service(self):
        service = PricingService()
        assert len(service._pricing) > 0

    def test_get_pricing(self):
        service = PricingService()
        pricing = service.get_pricing("openai", "gpt-4o")
        assert pricing is not None
        assert pricing.model_id == "gpt-4o"

    def test_get_pricing_not_found(self):
        service = PricingService()
        pricing = service.get_pricing("unknown", "unknown")
        assert pricing is None

    def test_calculate_cost(self):
        service = PricingService()
        cost = service.calculate_cost("openai", "gpt-4o", 1000, 1000)
        assert cost > 0

    def test_calculate_cost_unknown_model(self):
        service = PricingService()
        cost = service.calculate_cost("unknown", "unknown", 1000, 1000)
        assert cost == 0.0

    def test_add_pricing(self):
        service = PricingService()
        service.add_pricing(ModelPricing(
            model_id="test-model",
            provider="test-provider",
            prompt_price_per_1k=0.01,
            completion_price_per_1k=0.03,
        ))
        pricing = service.get_pricing("test-provider", "test-model")
        assert pricing is not None

    def test_get_all_pricing(self):
        service = PricingService()
        all_pricing = service.get_all_pricing()
        assert len(all_pricing) > 0
        assert "provider" in all_pricing[0]

    def test_get_pricing_for_provider(self):
        service = PricingService()
        openai_pricing = service.get_pricing_for_provider("openai")
        assert len(openai_pricing) > 0


class TestGetPricingService:
    """Test get_pricing_service function."""

    def test_returns_service(self):
        service = get_pricing_service()
        assert isinstance(service, PricingService)

"""Provider Pricing — Pricing information for LLM providers.

Provides:
- Provider pricing table
- Cost calculation
- Usage aggregation
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("aic.pricing")


@dataclass
class ModelPricing:
    """Pricing for a specific model."""
    model_id: str
    provider: str
    prompt_price_per_1k: float  # Price per 1000 prompt tokens
    completion_price_per_1k: float  # Price per 1000 completion tokens
    cached_price_per_1k: float = 0.0  # Price per 1000 cached tokens
    currency: str = "USD"

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """Calculate cost for token usage.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cached_tokens: Number of cached tokens

        Returns:
            Total cost in currency units
        """
        prompt_cost = (prompt_tokens / 1000) * self.prompt_price_per_1k
        completion_cost = (completion_tokens / 1000) * self.completion_price_per_1k
        cached_cost = (cached_tokens / 1000) * self.cached_price_per_1k

        return prompt_cost + completion_cost + cached_cost


class PricingService:
    """Service for provider pricing and cost calculation."""

    def __init__(self):
        self._pricing: dict[str, ModelPricing] = {}
        self._load_default_pricing()

    def _load_default_pricing(self) -> None:
        """Load default pricing for common models."""
        # OpenAI models
        self.add_pricing(ModelPricing(
            model_id="gpt-4o",
            provider="openai",
            prompt_price_per_1k=0.005,
            completion_price_per_1k=0.015,
            cached_price_per_1k=0.0025,
        ))
        self.add_pricing(ModelPricing(
            model_id="gpt-4o-mini",
            provider="openai",
            prompt_price_per_1k=0.00015,
            completion_price_per_1k=0.0006,
            cached_price_per_1k=0.000075,
        ))
        self.add_pricing(ModelPricing(
            model_id="gpt-4-turbo",
            provider="openai",
            prompt_price_per_1k=0.01,
            completion_price_per_1k=0.03,
            cached_price_per_1k=0.005,
        ))

        # Anthropic models
        self.add_pricing(ModelPricing(
            model_id="claude-3-opus",
            provider="anthropic",
            prompt_price_per_1k=0.015,
            completion_price_per_1k=0.075,
        ))
        self.add_pricing(ModelPricing(
            model_id="claude-3-sonnet",
            provider="anthropic",
            prompt_price_per_1k=0.003,
            completion_price_per_1k=0.015,
        ))
        self.add_pricing(ModelPricing(
            model_id="claude-3-haiku",
            provider="anthropic",
            prompt_price_per_1k=0.00025,
            completion_price_per_1k=0.00125,
        ))

        # DeepSeek models
        self.add_pricing(ModelPricing(
            model_id="deepseek-chat",
            provider="deepseek",
            prompt_price_per_1k=0.00014,
            completion_price_per_1k=0.00028,
        ))
        self.add_pricing(ModelPricing(
            model_id="deepseek-coder",
            provider="deepseek",
            prompt_price_per_1k=0.00014,
            completion_price_per_1k=0.00028,
        ))

    def add_pricing(self, pricing: ModelPricing) -> None:
        """Add pricing for a model.

        Args:
            pricing: Model pricing information
        """
        key = f"{pricing.provider}/{pricing.model_id}"
        self._pricing[key] = pricing
        logger.info(f"Added pricing for {key}")

    def get_pricing(self, provider: str, model_id: str) -> ModelPricing | None:
        """Get pricing for a model.

        Args:
            provider: Provider name
            model_id: Model ID

        Returns:
            Model pricing or None if not found
        """
        key = f"{provider}/{model_id}"
        return self._pricing.get(key)

    def calculate_cost(
        self,
        provider: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """Calculate cost for token usage.

        Args:
            provider: Provider name
            model_id: Model ID
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cached_tokens: Number of cached tokens

        Returns:
            Total cost in USD
        """
        pricing = self.get_pricing(provider, model_id)
        if not pricing:
            logger.warning(f"No pricing found for {provider}/{model_id}")
            return 0.0

        return pricing.calculate_cost(prompt_tokens, completion_tokens, cached_tokens)

    def get_all_pricing(self) -> list[dict[str, Any]]:
        """Get all pricing information.

        Returns:
            List of pricing information
        """
        return [
            {
                "provider": p.provider,
                "model_id": p.model_id,
                "prompt_price_per_1k": p.prompt_price_per_1k,
                "completion_price_per_1k": p.completion_price_per_1k,
                "cached_price_per_1k": p.cached_price_per_1k,
                "currency": p.currency,
            }
            for p in self._pricing.values()
        ]

    def get_pricing_for_provider(self, provider: str) -> list[ModelPricing]:
        """Get all pricing for a provider.

        Args:
            provider: Provider name

        Returns:
            List of model pricing
        """
        return [p for p in self._pricing.values() if p.provider == provider]


# Global pricing service instance
_pricing_service = PricingService()


def get_pricing_service() -> PricingService:
    """Get the global pricing service."""
    return _pricing_service

"""
MiniMax M2.7 API Integration for BYOK Handler

Provides cost-effective standard tier routing via OpenAI-compatible API.
MiniMax M2.7 is the latest flagship model with 204K context window.

Available models:
- MiniMax-M2.7: Latest flagship, 204K context
- MiniMax-M2.7-highspeed: Optimized for lower latency, 204K context

Integration:
- Tier: STANDARD (quality score 90)
- Vision: Not supported (text-only reasoning model)
- Tools: Native agent support via OpenAI-compatible function calling
- Cache: No prompt caching
- Pricing: Pay-as-you-go (no minimum commitment)
- Temperature: Must be in (0.0, 1.0] — clamped automatically
"""

import asyncio
import logging
from typing import Dict, Optional

import httpx

from core.llm.cognitive_tier_system import CognitiveTier

logger = logging.getLogger(__name__)


# Available MiniMax models with context windows
MINIMAX_MODELS = {
    "MiniMax-M2.7": {"context_window": 204000, "description": "Latest flagship model"},
    "MiniMax-M2.7-highspeed": {"context_window": 204000, "description": "Optimized for lower latency"},
    "MiniMax-M2.5": {"context_window": 204000, "description": "Previous generation"},
    "MiniMax-M2.5-highspeed": {"context_window": 204000, "description": "Previous generation, low latency"},
}

DEFAULT_MODEL = "MiniMax-M2.7"


def clamp_temperature(temperature: float) -> float:
    """Clamp temperature to MiniMax's accepted range (0.0, 1.0].

    MiniMax API rejects temperature=0.0. Values at or below 0 are
    nudged to 0.01; values above 1.0 are capped at 1.0.
    """
    if temperature <= 0.0:
        return 0.01
    return min(temperature, 1.0)


class RateLimitedError(Exception):
    """Raised when MiniMax API rate limit is exceeded (HTTP 429)"""
    pass


class MiniMaxIntegration:
    """
    MiniMax M2.7 API wrapper for cost-effective standard tier routing.

    Pricing:
    - Input: ~$1/M tokens
    - Output: ~$1/M tokens
    - Context: 204K tokens (all models)

    Capabilities:
    - Quality Score: 90
    - Vision: No (text-only reasoning)
    - Tools: Yes (native agent / function calling support)
    - Cache: No
    """

    BASE_URL = "https://api.minimax.io/v1"

    ESTIMATED_PRICING = {
        "input_cost_per_token": 0.000001,   # ~$1/M tokens
        "output_cost_per_token": 0.000001,  # ~$1/M tokens
        "max_tokens": 204000,
    }

    CAPABILITIES = {
        "quality_score": 90,
        "supports_vision": False,
        "supports_tools": True,
        "supports_cache": False,
        "tier": CognitiveTier.STANDARD,
    }

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        """
        Initialize MiniMax API client.

        Args:
            api_key: MiniMax API key (from MINIMAX_API_KEY env var or user config)
            model: Model to use (default: MiniMax-M2.7)
        """
        self.api_key = api_key
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info(f"MiniMaxIntegration initialized with model={model}")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate response using MiniMax model.

        Args:
            prompt: User prompt
            temperature: Sampling temperature, clamped to (0.0, 1.0]
            max_tokens: Maximum tokens to generate (default 1000)
            model: Override model for this request (optional)

        Returns:
            Generated text or None if API call fails

        Raises:
            RateLimitedError: If API returns 429 (rate limit exceeded)
        """
        effective_model = model or self.model
        clamped_temp = clamp_temperature(temperature)

        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": effective_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": clamped_temp,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"MiniMax rate limit exceeded: {e}")
                raise RateLimitedError("MiniMax rate limit exceeded")
            else:
                logger.error(f"MiniMax generation failed: {e}")
                return None
        except Exception as e:
            logger.error(f"MiniMax generation failed: {e}")
            return None

    def get_pricing(self) -> Dict[str, float]:
        """
        Get pricing information for cost calculations.

        Returns:
            Dictionary with input_cost_per_token, output_cost_per_token, max_tokens
        """
        return self.ESTIMATED_PRICING.copy()

    async def test_connection(self) -> bool:
        """
        Test API key validity and API availability.

        Returns:
            True if API is accessible (HTTP 200), False otherwise
        """
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                    "temperature": 0.01,
                },
            )
            is_valid = response.status_code == 200
            logger.info(f"MiniMax API connection test: {is_valid}")
            return is_valid
        except Exception as e:
            logger.warning(f"MiniMax API connection failed: {e}")
            return False

    def get_capabilities(self) -> Dict:
        """
        Get model capabilities for tier routing.

        Returns:
            Dictionary with quality_score, supports_vision, supports_tools,
            supports_cache, tier
        """
        return self.CAPABILITIES.copy()

    @staticmethod
    def get_available_models() -> Dict[str, Dict]:
        """Return all available MiniMax models with metadata."""
        return MINIMAX_MODELS.copy()

    async def close(self):
        """Close the HTTP client (call when done)"""
        await self.client.aclose()
        logger.debug("MiniMaxIntegration client closed")

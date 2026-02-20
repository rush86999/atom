"""
MiniMax M2.5 API Integration for BYOK Handler

Provides cost-effective standard tier routing with ~$1/M token pricing.
MiniMax M2.5 (launched Feb 12, 2026) offers competitive reasoning with native agent support.

Note: As of Feb 2026, M2.5 API access is closed. This implementation uses estimated pricing
based on research ($1/M tokens). Will update when official pricing is announced.

Integration:
- Tier: STANDARD (quality score 88, between gemini-2.0-flash and deepseek-chat)
- Vision: Not supported (text-only reasoning model)
- Tools: Native agent support
- Cache: No prompt caching (as of Feb 2026)
- Pricing: Pay-as-you-go (no minimum commitment)
"""

import asyncio
import logging
from typing import Dict, Optional

import httpx

from core.llm.cognitive_tier_system import CognitiveTier

logger = logging.getLogger(__name__)


class RateLimitedError(Exception):
    """Raised when MiniMax API rate limit is exceeded (HTTP 429)"""
    pass


class MiniMaxIntegration:
    """
    MiniMax M2.5 API wrapper for cost-effective standard tier routing.

    Pricing (estimate, will update when official pricing announced):
    - Input: $1/M tokens
    - Output: $1/M tokens
    - Context: 128k tokens

    Capabilities:
    - Quality Score: 88 (between gemini-2.0-flash @ 86 and deepseek-chat @ 80)
    - Vision: No (text-only reasoning)
    - Tools: Yes (native agent support)
    - Cache: No (as of Feb 2026)

    API access currently closed - graceful fallback to next provider.
    """

    BASE_URL = "https://api.minimaxi.com/v1"

    # Estimated pricing (will update when official pricing announced)
    ESTIMATED_PRICING = {
        "input_cost_per_token": 0.000001,  # $1/M tokens
        "output_cost_per_token": 0.000001,  # $1/M tokens
        "max_tokens": 128000,
    }

    # Model capabilities based on research
    CAPABILITIES = {
        "quality_score": 88,  # Between gemini-2.0-flash (86) and deepseek-chat (80)
        "supports_vision": False,
        "supports_tools": True,  # Native agent support
        "supports_cache": False,
        "tier": CognitiveTier.STANDARD,
    }

    def __init__(self, api_key: str):
        """
        Initialize MiniMax API client.

        Args:
            api_key: MiniMax API key (from MINIMAX_API_KEY env var or user config)

        Note: As of Feb 2026, API access is closed. Client initialization will succeed
        but API calls will gracefully fail until access opens.
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info(f"MiniMaxIntegration initialized (API access may be closed)")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> Optional[str]:
        """
        Generate response using MiniMax M2.5 model.

        Args:
            prompt: User prompt
            temperature: Sampling temperature (0-1, default 0.7)
            max_tokens: Maximum tokens to generate (default 1000)

        Returns:
            Generated text or None if API call fails

        Raises:
            RateLimitedError: If API returns 429 (rate limit exceeded)

        Example:
            >>> minimax = MiniMaxIntegration(api_key="sk-...")
            >>> response = await minimax.generate("Explain quantum computing")
            >>> print(response)
        """
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": "m2.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
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

        Note: Pricing is estimated ($1/M) until official pricing announced.
        """
        return self.ESTIMATED_PRICING.copy()

    async def test_connection(self) -> bool:
        """
        Test API key validity and API availability.

        Returns:
            True if API is accessible (HTTP 200), False otherwise

        Note: As of Feb 2026, returns False for all keys (API access closed).
        """
        try:
            response = await self.client.get("/models")
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

    async def close(self):
        """Close the HTTP client (call when done)"""
        await self.client.aclose()
        logger.debug("MiniMaxIntegration client closed")

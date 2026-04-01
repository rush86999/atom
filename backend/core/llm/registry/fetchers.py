"""Model Metadata Fetchers for LLM Registry

This module provides fetchers for retrieving model metadata from external sources:
- LiteLLM pricing database (GitHub-hosted JSON)
- OpenRouter models API

Fetchers use async HTTP with proper error handling and timeout management.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx

from .rate_limiter import APIClientWithRetry, RateLimiter

logger = logging.getLogger(__name__)

# LiteLLM pricing database URL (regularly maintained)
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# OpenRouter models endpoint
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30


class ModelMetadataFetcher:
    """
    Fetches model metadata from LiteLLM and OpenRouter APIs.

    This class provides async methods to retrieve model information including
    pricing, context windows, and capabilities from external sources.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, use_retry: bool = True):
        """
        Initialize the fetcher with an HTTP client.

        Args:
            timeout: HTTP request timeout in seconds (default: 30)
            use_retry: Enable retry logic with exponential backoff (default: True)
        """
        self.timeout = timeout
        self.use_retry = use_retry
        self._client: Optional[httpx.AsyncClient] = None
        self._retry_client: Optional[APIClientWithRetry] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create the async HTTP client.

        Returns:
            httpx.AsyncClient instance configured with timeout
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _get_retry_client(self) -> Optional[APIClientWithRetry]:
        """
        Get or create the retry client with exponential backoff.

        Returns:
            APIClientWithRetry instance if use_retry is True, None otherwise
        """
        if self._retry_client is None and self.use_retry:
            self._retry_client = APIClientWithRetry()
        return self._retry_client

    async def close(self):
        """Close the HTTP client if it's open."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._retry_client is not None:
            await self._retry_client.close()
            self._retry_client = None

    async def fetch_litellm_models(self) -> Dict[str, Any]:
        """
        Fetch model metadata from LiteLLM's GitHub-hosted pricing database.

        The LiteLLM database is the authoritative source for model pricing
        and context windows across 100+ providers.

        Returns:
            Dictionary mapping model_name -> model_data with pricing and context info

        Example:
            {
                "gpt-4": {
                    "input_cost_per_token": 0.00003,
                    "output_cost_per_token": 0.00006,
                    "max_tokens": 8192,
                    "litellm_provider": "openai",
                    ...
                },
                ...
            }
        """
        try:
            if self.use_retry:
                client = await self._get_retry_client()
                logger.info(f"Fetching LiteLLM models from {LITELLM_PRICING_URL} with retry")
                response = await client.get(LITELLM_PRICING_URL, provider='litellm')
            else:
                client = await self._get_client()
                logger.info(f"Fetching LiteLLM models from {LITELLM_PRICING_URL}")
                response = await client.get(LITELLM_PRICING_URL)
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                logger.error(f"LiteLLM response is not a dict: {type(data)}")
                return {}

            logger.info(f"Successfully fetched {len(data)} models from LiteLLM")
            return data

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching LiteLLM models: {e}")
            return {}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching LiteLLM models: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching LiteLLM models: {e}", exc_info=True)
            return {}

    async def fetch_openrouter_models(self) -> Dict[str, Any]:
        """
        Fetch model metadata from OpenRouter's models API.

        OpenRouter provides a unified API for many models with additional
        metadata like descriptions and architecture notes.

        Returns:
            Dictionary mapping model_id -> model_data with pricing and metadata

        Example:
            {
                "openai/gpt-4": {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "context_length": 8192,
                    "pricing": {"prompt": 0.00003, "completion": 0.00006},
                    ...
                },
                ...
            }
        """
        try:
            if self.use_retry:
                client = await self._get_retry_client()
                logger.info(f"Fetching OpenRouter models from {OPENROUTER_MODELS_URL} with retry")
                response = await client.get(OPENROUTER_MODELS_URL, provider='openrouter')
            else:
                client = await self._get_client()
                logger.info(f"Fetching OpenRouter models from {OPENROUTER_MODELS_URL}")
                response = await client.get(OPENROUTER_MODELS_URL)
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict) or "data" not in data:
                logger.error(f"OpenRouter response missing 'data' field")
                return {}

            models = data["data"]
            if not isinstance(models, list):
                logger.error(f"OpenRouter data is not a list: {type(models)}")
                return {}

            # Convert list to dict keyed by model_id for easier lookup
            model_dict = {}
            for model in models:
                model_id = model.get("id")
                if model_id:
                    model_dict[model_id] = model

            logger.info(f"Successfully fetched {len(model_dict)} models from OpenRouter")
            return model_dict

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching OpenRouter models: {e}")
            return {}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching OpenRouter models: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching OpenRouter models: {e}", exc_info=True)
            return {}

    async def fetch_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch models from all sources concurrently.

        This method calls both fetchers in parallel using asyncio.gather()
        and merges the results with source annotations.

        Returns:
            Dictionary with structure:
            {
                "litellm": {model_name: model_data, ...},
                "openrouter": {model_id: model_data, ...},
                "metadata": {
                    "fetched_at": "ISO timestamp",
                    "litellm_count": 123,
                    "openrouter_count": 456
                }
            }

        Example:
            >>> fetcher = ModelMetadataFetcher()
            >>> result = await fetcher.fetch_all()
            >>> print(f"Fetched {result['metadata']['litellm_count']} LiteLLM models")
            >>> print(f"Fetched {result['metadata']['openrouter_count']} OpenRouter models")
        """
        logger.info("Starting concurrent fetch from all sources")

        try:
            # Fetch from both sources concurrently
            litellm_results, openrouter_results = await asyncio.gather(
                self.fetch_litellm_models(),
                self.fetch_openrouter_models(),
                return_exceptions=True
            )

            # Handle exceptions from gather
            if isinstance(litellm_results, Exception):
                logger.error(f"LiteLLM fetch failed: {litellm_results}")
                litellm_results = {}
            if isinstance(openrouter_results, Exception):
                logger.error(f"OpenRouter fetch failed: {openrouter_results}")
                openrouter_results = {}

            # Build merged result
            result = {
                "litellm": litellm_results if isinstance(litellm_results, dict) else {},
                "openrouter": openrouter_results if isinstance(openrouter_results, dict) else {},
                "metadata": {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "litellm_count": len(litellm_results) if isinstance(litellm_results, dict) else 0,
                    "openrouter_count": len(openrouter_results) if isinstance(openrouter_results, dict) else 0
                }
            }

            total_count = result["metadata"]["litellm_count"] + result["metadata"]["openrouter_count"]
            logger.info(f"Fetch complete: {total_count} total models ({result['metadata']['litellm_count']} LiteLLM, {result['metadata']['openrouter_count']} OpenRouter)")

            return result

        except Exception as e:
            logger.error(f"Unexpected error in fetch_all: {e}", exc_info=True)
            # Return empty result rather than raising
            return {
                "litellm": {},
                "openrouter": {},
                "metadata": {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "litellm_count": 0,
                    "openrouter_count": 0,
                    "error": str(e)
                }
            }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures client is closed."""
        await self.close()


# Convenience function for one-shot fetches
async def fetch_model_metadata(timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Dict[str, Any]]:
    """
    Fetch model metadata from all sources.

    This is a convenience function that creates a fetcher, fetches data,
    and cleans up. For multiple fetches, create and reuse a ModelMetadataFetcher
    instance instead.

    Args:
        timeout: HTTP request timeout in seconds

    Returns:
        Dictionary with litellm, openrouter, and metadata keys

    Example:
        >>> result = await fetch_model_metadata()
        >>> litellm_models = result["litellm"]
        >>> openrouter_models = result["openrouter"]
    """
    async with ModelMetadataFetcher(timeout=timeout) as fetcher:
        return await fetcher.fetch_all()

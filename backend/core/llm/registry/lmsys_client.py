"""LMSYS Chatbot Arena API client.

Fetches quality benchmark scores from the LMSYS Chatbot Arena leaderboard.
Provides fuzzy matching to map LMSYS model names to registry model names.
"""
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import re

import httpx

from core.cache import UniversalCacheService

logger = logging.getLogger(__name__)

# LMSYS Chatbot Arena API endpoints
LMSYS_LEADERBOARD_URL = "https://lmarena-arena.lmsys.org/api/leaderboard"
LMSYS_MODEL_INFO_URL = "https://lmarena-arena.lmsys.org/api/model_info"

# Cache TTL: 24 hours (LMSYS updates daily)
LMSYS_CACHE_TTL = 86400

# Model name normalization patterns
PROVIDER_ALIASES = {
    'openai': ['openai', 'gpt'],
    'anthropic': ['anthropic', 'claude'],
    'google': ['google', 'gemini', 'bard'],
    'meta': ['meta', 'llama', 'lama'],
    'mistral': ['mistral', 'mistralai'],
    'deepseek': ['deepseek'],
    'alibaba': ['alibaba', 'qwen', 'tongyi'],
    'xai': ['xai', 'grok'],
    'cohere': ['cohere', 'command'],
}

MODEL_PATTERNS = [
    # Remove "chat-" prefix variations
    (r'^chat[-_]?', ''),
    # Remove "turbo", "pro", "plus" suffixes for matching
    (r'[-_]?(turbo|pro|plus|lite|mini|base)$', ''),
    # Normalize version separators
    (r'[-_.]', '-'),
    # Lowercase for matching
]


class LMSYSClient:
    """Client for fetching LMSYS Chatbot Arena leaderboard data.

    Usage:
        client = LMSYSClient()
        scores = await client.fetch_leaderboard()
        # {'gpt-4': 1250.5, 'claude-3-opus': 1248.3, ...}
    """

    def __init__(self, cache_service: Optional[UniversalCacheService] = None):
        """Initialize client with optional cache.

        Args:
            cache_service: Optional cache service for caching results
        """
        self.cache = cache_service or UniversalCacheService()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    'User-Agent': 'ATOM-SaaS-Registry/1.0',
                    'Accept': 'application/json'
                }
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_leaderboard(
        self,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, float]:
        """Fetch current LMSYS Chatbot Arena leaderboard.

        Args:
            use_cache: Use cached data if available (default True)
            force_refresh: Force API call even if cache exists

        Returns:
            Dict mapping model names to ELO scores:
            {
                'gpt-4o': 1287.5,
                'claude-3-5-sonnet': 1281.3,
                'gemini-1.5-pro': 1264.8,
                ...
            }

        Raises:
            httpx.HTTPError: On API failure
            ValueError: On invalid response
        """
        cache_key = 'lmsys:leaderboard:v1'

        # Try cache first
        if use_cache and not force_refresh:
            cached = await self.cache.get_async(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass

        # Fetch from API
        client = await self._get_client()
        try:
            response = await client.get(LMSYS_LEADERBOARD_URL)
            response.raise_for_status()

            data = response.json()
            scores = self._parse_leaderboard_response(data)

            # Cache the result
            await self.cache.set_async(
                cache_key,
                json.dumps(scores),
                LMSYS_CACHE_TTL
            )

            logger.info(f"Fetched {len(scores)} model scores from LMSYS")
            return scores

        except Exception as e:
            logger.error(f"Failed to fetch LMSYS leaderboard: {e}")

            # Return cached data as fallback
            if use_cache:
                cached = await self.cache.get_async(cache_key)
                if cached:
                    try:
                        fallback = json.loads(cached)
                        logger.warning("Using cached LMSYS data due to API failure")
                        return fallback
                    except json.JSONDecodeError:
                        pass

            raise

    def _parse_leaderboard_response(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Parse LMSYS leaderboard API response.

        Args:
            data: Raw API response JSON

        Returns:
            Dict of model_name -> ELO score

        Expected response format (varies by API version):
        {
            "leaderboard": [
                {"name": "gpt-4o", "score": 1287.5, "ci": "+4/-3", ...},
                {"name": "claude-3-5-sonnet", "score": 1281.3, ...},
                ...
            ]
        }
        """
        scores = {}

        # Handle different response formats
        leaderboard = data.get('leaderboard', data.get('models', data.get('data', [])))

        for entry in leaderboard:
            if not isinstance(entry, dict):
                continue

            # Try different field names for model name
            model_name = entry.get('name') or entry.get('model') or entry.get('id')
            score = entry.get('score') or entry.get('elo') or entry.get('rating')

            if model_name and score is not None:
                try:
                    scores[model_name] = float(score)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid score for {model_name}: {score}")

        return scores

    def normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for fuzzy matching.

        Args:
            model_name: Raw model name from LMSYS

        Returns:
            Normalized name for matching
        """
        name = model_name.lower().strip()

        # Apply normalization patterns
        for pattern, replacement in MODEL_PATTERNS:
            name = re.sub(pattern, replacement, name)

        return name

    def map_model_name(
        self,
        lmsys_name: str,
        registry_models: List[str]
    ) -> Optional[str]:
        """Map LMSYS model name to registry model name using fuzzy matching.

        Args:
            lmsys_name: Model name from LMSYS leaderboard
            registry_models: List of model names in registry

        Returns:
            Best matching registry model name, or None if no match
        """
        # Direct match (case-insensitive)
        lmsys_lower = lmsys_name.lower()
        for model in registry_models:
            if model.lower() == lmsys_lower:
                return model

        # Normalize and match
        lmsys_normalized = self.normalize_model_name(lmsys_name)

        # Try exact normalized match
        for model in registry_models:
            if self.normalize_model_name(model) == lmsys_normalized:
                return model

        # Try prefix match (e.g., "gpt-4" matches "gpt-4-turbo")
        for model in registry_models:
            model_normalized = self.normalize_model_name(model)
            if model_normalized.startswith(lmsys_normalized):
                return model

            # Try the other direction
            if lmsys_normalized.startswith(model_normalized):
                return model

        # No match found
        return None

    async def map_scores_to_registry(
        self,
        lmsys_scores: Dict[str, float],
        registry_models: List[str]
    ) -> Dict[str, float]:
        """Map LMSYS scores to registry model names.

        Args:
            lmsys_scores: Dict from LMSYS name to score
            registry_models: List of registry model names

        Returns:
            Dict from registry model name to score
        """
        mapped = {}

        for lmsys_name, score in lmsys_scores.items():
            registry_name = self.map_model_name(lmsys_name, registry_models)
            if registry_name:
                mapped[registry_name] = score

        logger.info(
            f"Mapped {len(mapped)}/{len(lmsys_scores)} LMSYS scores to registry models"
        )
        return mapped

    def elo_to_quality_score(self, elo: float) -> float:
        """Convert LMSYS ELO score to 0-100 quality score.

        LMSYS ELO typically ranges from ~800 (weak) to ~1300 (strong).
        Map to 0-100 scale for quality_score column.

        Args:
            elo: LMSYS ELO score

        Returns:
            Quality score from 0-100
        """
        # ELO range: 800 -> 0, 1300 -> 100
        min_elo, max_elo = 800, 1300
        normalized = (elo - min_elo) / (max_elo - min_elo)
        return max(0, min(100, normalized * 100))


async def fetch_lmsys_scores(
    use_cache: bool = True
) -> Dict[str, float]:
    """Convenience function to fetch LMSYS scores.

    Args:
        use_cache: Use cached data if available

    Returns:
        Dict of model names to ELO scores
    """
    client = LMSYSClient()
    try:
        return await client.fetch_leaderboard(use_cache=use_cache)
    finally:
        await client.close()

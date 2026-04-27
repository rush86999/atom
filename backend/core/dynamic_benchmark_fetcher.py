"""
Dynamic Benchmark Fetcher
Fetches real-time benchmark scores from multiple external sources.

Sources:
1. LMSYS Chatbot Arena - Live ELO scores
2. Artificial Analysis - Multi-benchmark aggregator
3. Benchmark.moe - Comprehensive benchmark database
4. Hugging Face Leaderboard - Model evaluation results

Combines scores from multiple sources using weighted averaging.
Falls back to static benchmarks if all sources fail.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
import json

from core.llm.registry.lmsys_client import LMSYSClient
from core.cache import UniversalCacheService

logger = logging.getLogger(__name__)

# Cache file path
BENCHMARK_CACHE_PATH = Path("./data/benchmark_cache.json")

# Cache duration (6 hours for benchmarks, they change less frequently than pricing)
CACHE_DURATION_HOURS = 6

# Benchmark source URLs
# Updated: 2026-04-26 - Fixed incorrect endpoints
# Note: These APIs may require authentication or have changed
ARTIFICIAL_ANALYSIS_URL = "https://artificialanalysis.ai/api/v1/models"
BENCHMARK_MOE_URL = "https://benchmark.moe/api/v1/models"


class DynamicBenchmarkFetcher:
    """
    Fetches and caches AI model benchmark scores from multiple sources.

    Priority order for sources:
    1. LMSYS Chatbot Arena (most reliable, real-time)
    2. Artificial Analysis (multi-benchmark aggregator)
    3. Benchmark.moe (comprehensive database)
    4. Static benchmarks fallback (core/benchmarks.py)

    Usage:
        fetcher = DynamicBenchmarkFetcher()
        scores = await fetcher.refresh_benchmarks()
        # {'gpt-4o': 92.5, 'claude-3.5-sonnet': 91.2, ...}
    """

    def __init__(self, cache_service: Optional[UniversalCacheService] = None):
        """Initialize benchmark fetcher.

        Args:
            cache_service: Optional cache service for caching results
        """
        self.benchmark_cache: Dict[str, float] = {}
        self.last_fetch: Optional[datetime] = None
        self.cache = cache_service or UniversalCacheService()
        self._client: Optional[httpx.AsyncClient] = None

        # Import LMSYS client for Chatbot Arena data
        self.lmsys_client = LMSYSClient(cache_service=cache_service)

        self._load_cache()

    def _load_cache(self):
        """Load benchmarks from local cache file"""
        try:
            if BENCHMARK_CACHE_PATH.exists():
                with open(BENCHMARK_CACHE_PATH, 'r') as f:
                    data = json.load(f)
                    self.benchmark_cache = data.get("benchmarks", {})
                    last_fetch_str = data.get("last_fetch")
                    if last_fetch_str:
                        self.last_fetch = datetime.fromisoformat(last_fetch_str)
                    logger.info(f"Loaded {len(self.benchmark_cache)} benchmark scores from cache")
        except Exception as e:
            logger.warning(f"Could not load benchmark cache: {e}")

    def _save_cache(self):
        """Save benchmarks to local cache file"""
        try:
            BENCHMARK_CACHE_PATH.parent.mkdir(exist_ok=True)
            data = {
                "benchmarks": self.benchmark_cache,
                "last_fetch": self.last_fetch.isoformat() if self.last_fetch else None,
                "source": "multi_source"
            }
            with open(BENCHMARK_CACHE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.benchmark_cache)} benchmark scores to cache")
        except Exception as e:
            logger.error(f"Could not save benchmark cache: {e}")

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self.last_fetch or not self.benchmark_cache:
            return False
        age = datetime.now() - self.last_fetch
        return age < timedelta(hours=CACHE_DURATION_HOURS)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    'User-Agent': 'ATOM-Benchmark-Fetcher/1.0',
                    'Accept': 'application/json'
                }
            )
        return self._client

    async def _get_client_no_ssl(self) -> httpx.AsyncClient:
        """Get or create HTTP client with SSL verification disabled for problematic APIs."""
        return httpx.AsyncClient(
            timeout=30.0,
            verify=False,  # Disable SSL verification for benchmark.moe
            headers={
                'User-Agent': 'ATOM-Benchmark-Fetcher/1.0',
                'Accept': 'application/json'
            }
        )

    async def close(self):
        """Close HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await self.lmsys_client.close()

    async def fetch_from_lmsys(self) -> Dict[str, float]:
        """Fetch benchmark scores from LMSYS Chatbot Arena.

        LMSYS provides ELO scores which we convert to 0-100 quality scores.
        This is our most reliable source for real-time model quality.

        Returns:
            Dict mapping model names to quality scores (0-100)
        """
        try:
            lmsys_scores = await self.lmsys_client.fetch_leaderboard(use_cache=True)

            # Convert ELO to quality scores
            quality_scores = {}
            for model_name, elo in lmsys_scores.items():
                quality_scores[model_name] = self.lmsys_client.elo_to_quality_score(elo)

            logger.info(f"Fetched {len(quality_scores)} benchmark scores from LMSYS")
            return quality_scores

        except Exception as e:
            logger.error(f"Failed to fetch LMSYS benchmarks: {e}")
            return {}

    async def fetch_from_artificial_analysis(self) -> Dict[str, float]:
        """Fetch benchmark scores from Artificial Analysis API.

        Artificial Analysis aggregates multiple benchmarks (MMLU, GSM8K, etc.)
        and provides unified quality scores.

        Returns:
            Dict mapping model names to quality scores (0-100)
        """
        client = await self._get_client()
        try:
            response = await client.get(ARTIFICIAL_ANALYSIS_URL)
            response.raise_for_status()
            data = response.json()

            scores = {}
            for model in data.get("models", []):
                model_name = model.get("name", "")
                # Artificial Analysis provides various metrics
                # We'll use the overall rating if available
                rating = model.get("rating") or model.get("score") or model.get("performance")

                if model_name and rating is not None:
                    try:
                        # Normalize to 0-100 scale if needed
                        score = float(rating)
                        if score > 100:  # If score is on different scale, normalize it
                            score = min(100, score / 10)  # Assuming 0-1000 scale
                        scores[model_name] = score
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid score for {model_name}: {rating}")

            logger.info(f"Fetched {len(scores)} benchmark scores from Artificial Analysis")
            return scores

        except Exception as e:
            logger.error(f"Failed to fetch Artificial Analysis benchmarks: {e}")
            return {}

    async def fetch_from_benchmark_moe(self) -> Dict[str, float]:
        """Fetch benchmark scores from Benchmark.moe API.

        Benchmark.moe provides comprehensive benchmark data across multiple tasks.

        Returns:
            Dict mapping model names to quality scores (0-100)
        """
        # Use client with SSL verification disabled due to known SSL issues
        client = await self._get_client_no_ssl()
        try:
            response = await client.get(BENCHMARK_MOE_URL)
            response.raise_for_status()
            data = response.json()

            scores = {}
            for model in data.get("models", []):
                model_name = model.get("id") or model.get("name", "")
                # Benchmark.moe provides various benchmark scores
                # We'll average the available benchmarks
                benchmarks = model.get("benchmarks", {})

                if benchmarks:
                    # Get numeric benchmark values
                    values = []
                    for bench_name, bench_value in benchmarks.items():
                        if isinstance(bench_value, (int, float)):
                            values.append(bench_value)

                    if values:
                        # Average benchmarks and normalize to 0-100
                        avg_score = sum(values) / len(values)
                        # Most benchmarks are 0-100, but some are different
                        normalized = min(100, max(0, avg_score))
                        scores[model_name] = normalized

            logger.info(f"Fetched {len(scores)} benchmark scores from Benchmark.moe")
            return scores

        except Exception as e:
            logger.error(f"Failed to fetch Benchmark.moe data: {e}")
            return {}

    def merge_benchmark_scores(
        self,
        sources: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """Merge benchmark scores from multiple sources.

        Uses weighted averaging with source priorities:
        - LMSYS: 0.6 weight (most reliable for chat quality)
        - Artificial Analysis: 0.3 weight (good aggregator)
        - Benchmark.moe: 0.1 weight (supplementary)

        Args:
            sources: List of benchmark score dicts from different sources

        Returns:
            Merged benchmark scores dict
        """
        if not sources:
            return {}

        # Weights for each source (in priority order)
        weights = [0.6, 0.3, 0.1]

        # Collect all model names
        all_models = set()
        for source in sources:
            all_models.update(source.keys())

        # Calculate weighted average for each model
        merged = {}
        for model_name in all_models:
            scores = []
            total_weight = 0

            for i, source in enumerate(sources):
                if model_name in source:
                    weight = weights[i] if i < len(weights) else 0.1
                    scores.append(source[model_name] * weight)
                    total_weight += weight

            if scores and total_weight > 0:
                merged[model_name] = sum(scores) / total_weight

        logger.info(f"Merged benchmark scores for {len(merged)} models from {len(sources)} sources")
        return merged

    async def refresh_benchmarks(
        self,
        force: bool = False,
        use_static_fallback: bool = True
    ) -> Dict[str, float]:
        """Refresh benchmark data from external sources.

        Strategy: Try LMSYS first (most reliable), fall back to static if needed.
        Artificial Analysis and Benchmark.moe are temporarily disabled due to API issues.

        Args:
            force: Force API calls even if cache is valid
            use_static_fallback: Fall back to static benchmarks if all APIs fail

        Returns:
            Dict mapping model names to quality scores (0-100)
        """
        # Check cache first
        if not force and self._is_cache_valid():
            logger.info("Using cached benchmark data")
            return self.benchmark_cache

        # Try LMSYS first (most reliable source)
        logger.info("Fetching benchmarks from LMSYS...")
        lmsys_scores = await self.fetch_from_lmsys()

        if lmsys_scores and len(lmsys_scores) > 10:
            # LMSYS worked, use it
            self.benchmark_cache = lmsys_scores
            self.last_fetch = datetime.now()
            self._save_cache()
            logger.info(f"Successfully fetched {len(lmsys_scores)} benchmark scores from LMSYS")
            return self.benchmark_cache

        # LMSYS failed, try other sources in parallel
        logger.warning("LMSYS fetch failed, trying alternative sources...")
        tasks = [
            self.fetch_from_artificial_analysis(),
            self.fetch_from_benchmark_moe()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed requests
        sources = []
        for result in results:
            if isinstance(result, dict) and result:
                sources.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Alternative benchmark source failed: {result}")

        # Merge results from successful alternative sources
        if sources:
            self.benchmark_cache = self.merge_benchmark_scores(sources)
            self.last_fetch = datetime.now()
            self._save_cache()
            logger.info(f"Successfully fetched {len(self.benchmark_cache)} benchmark scores from alternative sources")
            return self.benchmark_cache

        # All sources failed, fall back to static benchmarks
        logger.error("All external benchmark sources failed")
        if use_static_fallback:
            logger.info("Falling back to static benchmarks")
            self.benchmark_cache = self._get_static_benchmarks()
            self.last_fetch = datetime.now()  # Mark as updated even though using static
            self._save_cache()
            return self.benchmark_cache

        # No fallback available
        return {}

    def _get_static_benchmarks(self) -> Dict[str, float]:
        """Load static benchmarks from core/benchmarks.py as fallback.

        Returns:
            Static benchmark scores dict
        """
        try:
            from core.benchmarks import MODEL_QUALITY_SCORES
            logger.info(f"Loaded {len(MODEL_QUALITY_SCORES)} static benchmark scores")
            return MODEL_QUALITY_SCORES.copy()
        except ImportError:
            logger.error("Could not import static benchmarks")
            return {}

    def get_benchmark_score(self, model_name: str) -> Optional[float]:
        """Get benchmark score for a specific model.

        Args:
            model_name: Model identifier

        Returns:
            Quality score (0-100) or None if not found
        """
        # Try exact match first
        if model_name in self.benchmark_cache:
            return self.benchmark_cache[model_name]

        # Try partial match
        model_lower = model_name.lower()
        for cached_model, score in self.benchmark_cache.items():
            if model_lower in cached_model.lower() or cached_model.lower() in model_lower:
                return score

        return None

    def get_capability_score(
        self,
        model_name: str,
        capability: str
    ) -> Optional[float]:
        """Get capability-specific benchmark score.

        For now, returns general quality score.
        In the future, this could be extended to fetch capability-specific benchmarks.

        Args:
            model_name: Model identifier
            capability: Capability name (e.g., "vision", "tools", "computer_use")

        Returns:
            Capability score (0-100) or None if not found
        """
        # Start with general quality score
        base_score = self.get_benchmark_score(model_name)

        # Check if we have capability-specific adjustments
        # These could be fetched from specialized benchmarks in the future
        capability_adjustments = {
            "computer_use": {"lux-1.0": +5, "claude-3.5-sonnet": +3},
            "vision": {"gpt-4o": +5, "claude-3.5-sonnet": +4, "gemini-2.0-flash": +3},
            "tools": {"claude-3.5-sonnet": +4, "gpt-4o": +3},
        }

        if capability in capability_adjustments:
            for cap_model, adjustment in capability_adjustments[capability].items():
                if cap_model.lower() in model_name.lower():
                    return min(100, max(0, (base_score or 70) + adjustment))

        return base_score

    def get_top_models(
        self,
        limit: int = 10,
        min_score: float = 80.0
    ) -> List[tuple[str, float]]:
        """Get top models by benchmark score.

        Args:
            limit: Maximum number of models to return
            min_score: Minimum benchmark score (0-100)

        Returns:
            List of (model_name, score) tuples sorted by score DESC
        """
        models = [
            (name, score)
            for name, score in self.benchmark_cache.items()
            if score >= min_score
        ]

        models.sort(key=lambda x: x[1], reverse=True)
        return models[:limit]


# Singleton instance
_benchmark_fetcher: Optional[DynamicBenchmarkFetcher] = None


def get_benchmark_fetcher() -> DynamicBenchmarkFetcher:
    """Get the singleton benchmark fetcher instance"""
    global _benchmark_fetcher
    if _benchmark_fetcher is None:
        _benchmark_fetcher = DynamicBenchmarkFetcher()
    return _benchmark_fetcher


async def refresh_benchmark_cache(force: bool = False) -> Dict[str, float]:
    """Convenience function to refresh benchmark cache

    Args:
        force: Force API calls even if cache is valid

    Returns:
        Dict of model names to benchmark scores
    """
    fetcher = get_benchmark_fetcher()
    return await fetcher.refresh_benchmarks(force=force)

"""
BYOK Cache Pre-seeding Service

Pre-warms all BYOK-related caches during deployment or on-demand:
- Pricing cache (LiteLLM + OpenRouter)
- Cognitive tier model availability
- Governance decisions (common agent actions)
- Cache-aware router history (baseline probabilities)

Usage:
    # Pre-seed all caches
    await preseed_all_caches()

    # Pre-seed specific caches
    await preseed_pricing_cache()
    await preseed_cognitive_models()
    await preseed_governance_cache()

Environment Variables:
    PRESEED_CACHE_ON_STARTUP: Pre-seed caches on application startup (default: false)
    PRESEED_PRICING_SOURCE: Source for pricing data (litellm, openrouter, both, default: both)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
import os

from core.dynamic_pricing_fetcher import get_pricing_fetcher, refresh_pricing_cache
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.governance_cache import get_governance_cache
from core.llm.cache_aware_router import CacheAwareRouter
from core.database import SessionLocal
from core.models import AgentRegistry, AgentStatus, User, UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Common workspace ID for pre-seeding
DEFAULT_WORKSPACE_ID = "default"

# Sample prompts for cache hit probability pre-seeding
SAMPLE_PROMPTS = [
    "Hello, how can you help me?",
    "Summarize this document",
    "Write a Python function to",
    "Compare and contrast these options",
    "What is the capital of France?",
    "Analyze the following data",
    "Create a marketing strategy for",
    "Debug this code",
    "Explain this concept",
    "Translate this to Spanish",
]

# Common agent actions for governance pre-seeding
COMMON_AGENT_ACTIONS = [
    "stream_chat",
    "present_chart",
    "present_markdown",
    "present_form",
    "browser_automation",
]

# Common directories for governance pre-seeding
COMMON_DIRECTORIES = [
    "/tmp",
    "/Users/test/projects",
    "/home/user/documents",
]


# =============================================================================
# Pre-seeding Functions
# =============================================================================

async def preseed_all_caches(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    verbose: bool = True
) -> Dict[str, any]:
    """
    Pre-seed all BYOK caches.

    Args:
        workspace_id: Workspace ID for context
        verbose: Enable detailed logging

    Returns:
        Dict with pre-seeding results for each cache type

    Example:
        >>> result = await preseed_all_caches()
        >>> print(result["pricing"]["models_loaded"])
        1523
        >>> print(result["cognitive"]["tiers_loaded"])
        5
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting BYOK Cache Pre-seeding (All Caches)")
    logger.info("=" * 60)

    results = {
        "started_at": start_time.isoformat(),
        "workspace_id": workspace_id,
        "pricing": {},
        "cognitive": {},
        "governance": {},
        "cache_aware": {},
    }

    try:
        # 1. Pre-seed pricing cache
        if verbose:
            logger.info("Step 1/4: Pre-seeding pricing cache...")
        results["pricing"] = await preseed_pricing_cache(verbose=verbose)

        # 2. Pre-seed cognitive tier models
        if verbose:
            logger.info("Step 2/4: Pre-seeding cognitive tier models...")
        results["cognitive"] = await preseed_cognitive_models(verbose=verbose)

        # 3. Pre-seed governance cache
        if verbose:
            logger.info("Step 3/4: Pre-seeding governance cache...")
        results["governance"] = await preseed_governance_cache(
            workspace_id=workspace_id,
            verbose=verbose
        )

        # 4. Pre-seed cache-aware router
        if verbose:
            logger.info("Step 4/4: Pre-seeding cache-aware router...")
        results["cache_aware"] = await preseed_cache_aware_router(
            workspace_id=workspace_id,
            verbose=verbose
        )

    except Exception as e:
        logger.error(f"Error during pre-seeding: {e}", exc_info=True)
        results["error"] = str(e)

    # Calculate duration
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["completed_at"] = end_time.isoformat()
    results["duration_seconds"] = duration

    logger.info("=" * 60)
    logger.info(f"BYOK Cache Pre-seeding Complete ({duration:.2f}s)")
    logger.info("=" * 60)

    return results


async def preseed_pricing_cache(
    force_refresh: bool = True,
    verbose: bool = True
) -> Dict[str, any]:
    """
    Pre-seed pricing cache with latest model prices.

    Fetches pricing from:
    - LiteLLM GitHub repository (primary)
    - OpenRouter API (fallback)

    Args:
        force_refresh: Force refresh even if cache is valid
        verbose: Enable detailed logging

    Returns:
        Dict with pricing cache pre-seeding results

    Example:
        >>> result = await preseed_pricing_cache()
        >>> print(result["models_loaded"])
        1523
        >>> print(result["providers"])
        ["openai", "anthropic", "deepseek", "gemini", "minimax"]
    """
    start_time = datetime.now()

    if verbose:
        logger.info("Fetching pricing data from LiteLLM and OpenRouter...")

    try:
        # Refresh pricing cache
        pricing_cache = await refresh_pricing_cache(force=force_refresh)

        # Analyze results
        providers = set()
        models_with_cache_support = 0
        models_with_tools = 0
        models_with_vision = 0

        for model_name, pricing in pricing_cache.items():
            provider = pricing.get("litellm_provider", "unknown")
            providers.add(provider)

            if pricing.get("supports_cache", False):
                models_with_cache_support += 1
            if pricing.get("supports_tools", False):
                models_with_tools += 1
            if pricing.get("supports_vision", False):
                models_with_vision += 1

        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "success": True,
            "models_loaded": len(pricing_cache),
            "providers": sorted(list(providers)),
            "models_with_cache_support": models_with_cache_support,
            "models_with_tools_support": models_with_tools,
            "models_with_vision_support": models_with_vision,
            "duration_seconds": duration,
        }

        if verbose:
            logger.info(f"✓ Loaded {len(pricing_cache)} models from {len(providers)} providers")
            logger.info(f"  - Cache support: {models_with_cache_support} models")
            logger.info(f"  - Tools support: {models_with_tools} models")
            logger.info(f"  - Vision support: {models_with_vision} models")
            logger.info(f"  Duration: {duration:.2f}s")

        return result

    except Exception as e:
        logger.error(f"Failed to pre-seed pricing cache: {e}")
        return {
            "success": False,
            "error": str(e),
            "models_loaded": 0,
        }


async def preseed_cognitive_models(
    verbose: bool = True
) -> Dict[str, any]:
    """
    Pre-seed cognitive tier model availability.

    Validates that recommended models for each tier are available
    in the pricing cache and have valid pricing data.

    Args:
        verbose: Enable detailed logging

    Returns:
        Dict with cognitive tier pre-seeding results

    Example:
        >>> result = await preseed_cognitive_models()
        >>> print(result["tiers_loaded"])
        5
        >>> print(result["models_validated"])
        22
    """
    start_time = datetime.now()

    if verbose:
        logger.info("Validating cognitive tier models...")

    try:
        classifier = CognitiveClassifier()
        fetcher = get_pricing_fetcher()

        tiers_loaded = 0
        models_validated = 0
        models_missing = 0
        tier_summary = {}

        for tier in CognitiveTier:
            models = classifier.get_tier_models(tier)

            tier_valid = 0
            tier_missing = []

            for model in models:
                pricing = fetcher.get_model_price(model)
                if pricing:
                    tier_valid += 1
                    models_validated += 1
                else:
                    tier_missing.append(model)
                    models_missing += 1

            tier_summary[tier.value] = {
                "total": len(models),
                "available": tier_valid,
                "missing": tier_missing,
            }

            if tier_valid > 0:
                tiers_loaded += 1

        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "success": True,
            "tiers_loaded": tiers_loaded,
            "models_validated": models_validated,
            "models_missing": models_missing,
            "tier_summary": tier_summary,
            "duration_seconds": duration,
        }

        if verbose:
            logger.info(f"✓ Validated {models_validated} models across {tiers_loaded} tiers")
            if models_missing > 0:
                logger.warning(f"  ⚠ {models_missing} models missing from pricing cache")
            logger.info(f"  Duration: {duration:.2f}s")

        return result

    except Exception as e:
        logger.error(f"Failed to pre-seed cognitive models: {e}")
        return {
            "success": False,
            "error": str(e),
            "tiers_loaded": 0,
            "models_validated": 0,
        }


async def preseed_governance_cache(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    verbose: bool = True
) -> Dict[str, any]:
    """
    Pre-seed governance cache with common agent permissions.

    Loads common governance decisions into cache to warm up the system:
    - Common agent actions (stream_chat, present_chart, etc.)
    - Common directory access permissions
    - Sample agent permission checks

    Args:
        workspace_id: Workspace ID for context
        verbose: Enable detailed logging

    Returns:
        Dict with governance cache pre-seeding results

    Example:
        >>> result = await preseed_governance_cache()
        >>> print(result["actions_cached"])
        6
        >>> print(result["directories_cached"])
        3
    """
    start_time = datetime.now()

    if verbose:
        logger.info("Warming up governance cache...")

    try:
        cache = get_governance_cache()
        db = SessionLocal()

        # Get sample agents for different maturity levels
        agents = db.query(AgentRegistry).limit(10).all()

        if not agents:
            # Create dummy agents for pre-seeding if none exist
            logger.warning("No agents found in database, using dummy agents for pre-seeding")
            agents = [
                AgentRegistry(
                    id=f"dummy-agent-{i}",
                    status=AgentStatus.SUPERVISED,
                    user_id="dummy-user",
                )
                for i in range(3)
            ]

        actions_cached = 0
        directories_cached = 0

        # Cache common agent actions
        for agent in agents:
            for action in COMMON_AGENT_ACTIONS:
                # Pre-seed cache with sample decision
                cache.set(
                    agent_id=agent.id,
                    action_type=action,
                    data={
                        "allowed": agent.status in [AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS],
                        "cached_at": datetime.now().isoformat(),
                    }
                )
                actions_cached += 1

        # Cache common directory permissions
        for agent in agents:
            for directory in COMMON_DIRECTORIES:
                cache.cache_directory(
                    agent_id=agent.id,
                    directory=directory,
                    permission_data={
                        "allowed": True,
                        "reason": "Pre-seeded directory permission",
                        "cached_at": datetime.now().isoformat(),
                    }
                )
                directories_cached += 1

        db.close()

        # Get cache stats
        stats = cache.get_stats()
        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "success": True,
            "actions_cached": actions_cached,
            "directories_cached": directories_cached,
            "cache_size": stats["size"],
            "cache_hit_rate": stats["hit_rate"],
            "duration_seconds": duration,
        }

        if verbose:
            logger.info(f"✓ Cached {actions_cached} actions and {directories_cached} directories")
            logger.info(f"  Cache size: {stats['size']} entries")
            logger.info(f"  Duration: {duration:.2f}s")

        return result

    except Exception as e:
        logger.error(f"Failed to pre-seed governance cache: {e}")
        return {
            "success": False,
            "error": str(e),
            "actions_cached": 0,
            "directories_cached": 0,
        }


async def preseed_cache_aware_router(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    verbose: bool = True
) -> Dict[str, any]:
    """
    Pre-seed cache-aware router with baseline probabilities.

    Records sample cache hit outcomes for common prompts to establish
    baseline probabilities (defaults to 50% without historical data).

    Args:
        workspace_id: Workspace ID for context
        verbose: Enable detailed logging

    Returns:
        Dict with cache-aware router pre-seeding results

    Example:
        >>> result = await preseed_cache_aware_router()
        >>> print(result["prompts_seeded"])
        10
        >>> print(result["baseline_probability"])
        0.5
    """
    start_time = datetime.now()

    if verbose:
        logger.info("Seeding cache-aware router history...")

    try:
        fetcher = get_pricing_fetcher()
        router = CacheAwareRouter(fetcher)

        # Import hashlib for prompt hashing
        import hashlib

        prompts_seeded = 0

        # Seed sample prompts with baseline probability
        for prompt in SAMPLE_PROMPTS:
            # Create hash of prompt prefix (first 1k tokens equivalent)
            prompt_prefix = prompt[:100]  # First 100 chars as prefix
            prompt_hash = hashlib.md5(prompt_prefix.encode()).hexdigest()

            # Record baseline cache hit probability (50%)
            # This gives the router some initial data to work with
            router.cache_hit_history[f"{workspace_id}:{prompt_hash[:16]}"] = [5, 10]
            prompts_seeded += 1

        duration = (datetime.now() - start_time).total_seconds()

        result = {
            "success": True,
            "prompts_seeded": prompts_seeded,
            "baseline_probability": 0.5,
            "cache_history_size": len(router.cache_hit_history),
            "duration_seconds": duration,
        }

        if verbose:
            logger.info(f"✓ Seeded {prompts_seeded} prompts with 50% baseline probability")
            logger.info(f"  Duration: {duration:.2f}s")

        return result

    except Exception as e:
        logger.error(f"Failed to pre-seed cache-aware router: {e}")
        return {
            "success": False,
            "error": str(e),
            "prompts_seeded": 0,
        }


# =============================================================================
# Startup Hook
# =============================================================================

async def maybe_preseed_on_startup() -> Optional[Dict[str, any]]:
    """
    Pre-seed caches on startup if environment variable is set.

    Checks PRESEED_CACHE_ON_STARTUP environment variable.
    If set to 'true' or '1', pre-seeds all caches.

    This is intended to be called from the FastAPI lifespan handler.

    Returns:
        Pre-seeding results if executed, None if skipped

    Example:
        >>> # In main_api_app.py lifespan handler
        >>> await maybe_preseed_on_startup()
    """
    preseed_enabled = os.getenv("PRESEED_CACHE_ON_STARTUP", "false").lower() in ["true", "1"]

    if not preseed_enabled:
        logger.info("Cache pre-seeding skipped (PRESEED_CACHE_ON_STARTUP=false)")
        return None

    logger.info("Cache pre-seeding enabled (PRESEED_CACHE_ON_STARTUP=true)")

    try:
        results = await preseed_all_caches(verbose=True)
        return results
    except Exception as e:
        logger.error(f"Startup cache pre-seeding failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# CLI Integration Helper
# =============================================================================

def print_preseed_results(results: Dict[str, any]):
    """
    Print pre-seeding results in a human-readable format.

    Args:
        results: Results dict from preseed_all_caches()
    """
    print("\n" + "=" * 60)
    print("BYOK Cache Pre-seeding Results")
    print("=" * 60)

    # Pricing
    pricing = results.get("pricing", {})
    if pricing.get("success"):
        print(f"\n✓ Pricing Cache:")
        print(f"  Models loaded: {pricing['models_loaded']}")
        print(f"  Providers: {', '.join(pricing['providers'])}")
        print(f"  Duration: {pricing['duration_seconds']:.2f}s")
    else:
        print(f"\n✗ Pricing Cache: {pricing.get('error', 'Unknown error')}")

    # Cognitive
    cognitive = results.get("cognitive", {})
    if cognitive.get("success"):
        print(f"\n✓ Cognitive Models:")
        print(f"  Tiers loaded: {cognitive['tiers_loaded']}")
        print(f"  Models validated: {cognitive['models_validated']}")
        print(f"  Duration: {cognitive['duration_seconds']:.2f}s")
    else:
        print(f"\n✗ Cognitive Models: {cognitive.get('error', 'Unknown error')}")

    # Governance
    governance = results.get("governance", {})
    if governance.get("success"):
        print(f"\n✓ Governance Cache:")
        print(f"  Actions cached: {governance['actions_cached']}")
        print(f"  Directories cached: {governance['directories_cached']}")
        print(f"  Cache size: {governance['cache_size']} entries")
        print(f"  Duration: {governance['duration_seconds']:.2f}s")
    else:
        print(f"\n✗ Governance Cache: {governance.get('error', 'Unknown error')}")

    # Cache-aware
    cache_aware = results.get("cache_aware", {})
    if cache_aware.get("success"):
        print(f"\n✓ Cache-Aware Router:")
        print(f"  Prompts seeded: {cache_aware['prompts_seeded']}")
        print(f"  Baseline probability: {cache_aware['baseline_probability']}")
        print(f"  Duration: {cache_aware['duration_seconds']:.2f}s")
    else:
        print(f"\n✗ Cache-Aware Router: {cache_aware.get('error', 'Unknown error')}")

    # Summary
    if "error" not in results:
        print(f"\n{'=' * 60}")
        print(f"Total Duration: {results.get('duration_seconds', 0):.2f}s")
        print(f"Status: COMPLETE")
        print(f"{'=' * 60}\n")
    else:
        print(f"\n{'=' * 60}")
        print(f"Status: FAILED")
        print(f"Error: {results.get('error', 'Unknown error')}")
        print(f"{'=' * 60}\n")

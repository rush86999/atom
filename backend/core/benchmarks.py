"""
Curated Quality Scores for AI Models
Normalized 0-100 scale based on MMLU, GSM8K, HumanEval, and LMSYS Chatbot Arena.
Used for "Benchmark-Price-Capability" (BPC) routing logic.

UPDATED: Now fetches live benchmark data from external APIs (LMSYS, Artificial Analysis, Benchmark.moe)
Falls back to static scores if all external sources fail.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Quality scores (0-100) - Updated Jan 2026
# STATIC FALLBACK - Used only when all external sources fail
MODEL_QUALITY_SCORES = {
    # absolute frontier (early 2026)
    "gemini-3-pro": 100,
    "gpt-5.2": 100,
    "gpt-5": 99,
    "o3": 99,
    "claude-4-opus": 99,
    "claude-3.5-opus": 97, # older opus
    "o4-mini": 96,
    "deepseek-r2": 97,
    "deepseek-v3.2-speciale": 99, # User Feedback: Frontier reasoning at low cost
    "qwen-3-max": 96,
    
    # High Reasoning / Complex
    "o3-mini": 94,
    "gpt-4.5": 95,
    "gemini-3-flash": 93,
    "deepseek-v3": 89, # demoted
    "deepseek-v3.2": 89, # demoted
    "qwen-2.5-72b-instruct": 88, # demoted
    "llama-4-70b": 92,
    "llama-3.3-70b-instruct": 89,
    
    # Balanced / Moderate
    "o1": 92, # demoted
    "deepseek-reasoner": 91, # demoted (R1)
    "gpt-4o": 90, # demoted
    "claude-3.5-sonnet": 92, # demoted
    "gpt-4o-mini": 85,
    "gemini-2.0-flash": 86,
    "gemini-1.5-flash": 84,
    "minimax-m2.5": 88,  # Standard tier, between gemini-2.0-flash and deepseek-chat
    "MiniMax-M2.7": 90,  # Latest flagship model, 204K context
    "MiniMax-M2.7-highspeed": 89,  # Low-latency variant, 204K context
    "lux-1.0": 88,  # LUX Computer Use (Claude 3.5 Sonnet based) - Phase 226.2-01

    # Efficiency / Simple
    "deepseek-chat": 80,
    "kimi-k1-5": 79,
    "qwen-3-7b": 82,
}

def get_quality_score(model_id: str) -> int:
    """
    Get the normalized quality score for a model.

    PRIORITY:
    1. Dynamic benchmark fetcher (LMSYS, Artificial Analysis, Benchmark.moe)
    2. Static fallback scores
    3. Heuristics for unknown models
    """
    # Try dynamic benchmark fetcher first
    try:
        from core.dynamic_benchmark_fetcher import get_benchmark_fetcher
        fetcher = get_benchmark_fetcher()
        dynamic_score = fetcher.get_benchmark_score(model_id)
        if dynamic_score is not None:
            logger.debug(f"Using dynamic benchmark score for {model_id}: {dynamic_score}")
            return int(dynamic_score)
    except ImportError:
        logger.debug("Dynamic benchmark fetcher not available, using static scores")
    except Exception as e:
        logger.debug(f"Failed to get dynamic benchmark: {e}, using static scores")

    # Fallback to static scores
    # Exact match
    if model_id in MODEL_QUALITY_SCORES:
        return MODEL_QUALITY_SCORES[model_id]

    # Partial match
    model_lower = model_id.lower()
    for key, score in MODEL_QUALITY_SCORES.items():
        if key.lower() in model_lower:
            return score

    # Heuristics for unknown models
    if "reasoner" in model_lower or "thinking" in model_lower or "-o1" in model_lower:
        return 95
    if "flash" in model_lower or "haiku" in model_lower or "mini" in model_lower:
        return 80
    if "70b" in model_lower or "72b" in model_lower:
        return 88
    if "8b" in model_lower or "7b" in model_lower:
        return 75

    return 70  # Default floor for unspecified models


# Capability-specific quality scores (0-100)
# Used for specialized routing when models excel at specific tasks
MODEL_CAPABILITY_SCORES = {
    "computer_use": {
        "lux-1.0": 95,  # Specialized for computer use
        "claude-3.5-sonnet": 85,  # Good but not specialized
        "gpt-4o": 80,
    },
    "vision": {
        "gpt-4o": 95,
        "claude-3.5-sonnet": 90,
        "gemini-2.0-flash": 88,
        "lux-1.0": 85,  # Has vision but not specialized for it
    },
    "tools": {
        "claude-3.5-sonnet": 93,
        "gpt-4o": 91,
        "gemini-2.0-flash": 85,
    },
}


def get_capability_score(model_id: str, capability: str) -> int:
    """
    Get the capability-specific quality score for a model.

    PRIORITY:
    1. Dynamic benchmark fetcher (capability-aware)
    2. Static capability scores
    3. General quality score fallback

    Args:
        model_id: Model identifier
        capability: Capability name (e.g., "computer_use", "vision", "tools")

    Returns:
        Capability-specific quality score (0-100)
    """
    # Try dynamic benchmark fetcher first (capability-aware)
    try:
        from core.dynamic_benchmark_fetcher import get_benchmark_fetcher
        fetcher = get_benchmark_fetcher()
        dynamic_score = fetcher.get_capability_score(model_id, capability)
        if dynamic_score is not None:
            logger.debug(f"Using dynamic capability score for {model_id}/{capability}: {dynamic_score}")
            return int(dynamic_score)
    except ImportError:
        logger.debug("Dynamic benchmark fetcher not available, using static scores")
    except Exception as e:
        logger.debug(f"Failed to get dynamic capability score: {e}, using static scores")

    # Check static capability-specific scores
    if capability in MODEL_CAPABILITY_SCORES:
        capability_scores = MODEL_CAPABILITY_SCORES[capability]

        # Exact match
        if model_id in capability_scores:
            return capability_scores[model_id]

        # Partial match
        model_lower = model_id.lower()
        for key, score in capability_scores.items():
            if key.lower() in model_lower:
                return score

    # Fallback to general quality score
    return get_quality_score(model_id)

"""
Cost configuration for LLM providers.

Defines model tier restrictions, BYOK-enabled plans, and cost calculation functions.
"""

from typing import Dict, List, Optional

# Model tier restrictions by plan
# Format: plan_name -> list of allowed models (or "*" for all models)
MODEL_TIER_RESTRICTIONS: Dict[str, List[str]] = {
    "free": [
        "gpt-4o-mini",
        "claude-3-haiku",
        "deepseek-chat",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
    ],
    "pro": [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-5-sonnet",
        "claude-3-haiku",
        "deepseek-chat",
        "deepseek-v3.2",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
    ],
    "enterprise": "*",  # All models available
    "trial": [
        "gpt-4o-mini",
        "claude-3-haiku",
        "deepseek-chat",
    ],
}

# Plans that enable BYOK (Bring Your Own Key)
BYOK_ENABLED_PLANS: List[str] = [
    "enterprise",
    "pro",  # Pro plans can also use BYOK
]

# Static cost per token by model (USD)
# Used as fallback when dynamic pricing is unavailable
MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.00003, "output": 0.00006},
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006},
    "claude-3-5-sonnet": {"input": 0.000015, "output": 0.000075},
    "claude-3-haiku": {"input": 0.0000004, "output": 0.000002},
    "deepseek-chat": {"input": 0.00000014, "output": 0.00000028},
    "deepseek-v3.2": {"input": 0.00000055, "output": 0.0000022},
    "gemini-1.5-pro": {"input": 0.000007, "output": 0.000028},
    "gemini-1.5-flash": {"input": 0.0000003, "output": 0.0000015},
    "gemini-2.0-flash": {"input": 0.00000025, "output": 0.000001},
}


def get_llm_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """
    Calculate LLM cost using static pricing table.

    Args:
        model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Total cost in USD, or None if model pricing not found
    """
    # Normalize model name (handle version suffixes)
    model_key = model
    for known_model in MODEL_COSTS:
        if known_model in model:
            model_key = known_model
            break

    if model_key not in MODEL_COSTS:
        return None

    costs = MODEL_COSTS[model_key]
    input_cost = input_tokens * costs["input"]
    output_cost = output_tokens * costs["output"]
    total_cost = input_cost + output_cost

    return total_cost


def get_model_tier(plan: str) -> List[str]:
    """
    Get allowed models for a given plan tier.

    Args:
        plan: Plan name (e.g., "free", "pro", "enterprise")

    Returns:
        List of allowed model names, or "*" for all models
    """
    plan_lower = plan.lower()
    return MODEL_TIER_RESTRICTIONS.get(plan_lower, MODEL_TIER_RESTRICTIONS["free"])


def is_byok_enabled(plan: str) -> bool:
    """
    Check if BYOK is enabled for a given plan.

    Args:
        plan: Plan name

    Returns:
        True if BYOK is enabled for this plan
    """
    plan_lower = plan.lower()
    return plan_lower in [p.lower() for p in BYOK_ENABLED_PLANS]

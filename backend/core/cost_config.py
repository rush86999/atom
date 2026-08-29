"""
Cost configuration for LLM providers.

Defines model tier restrictions, BYOK-enabled plans, and cost calculation functions.
"""

from typing import Dict, List, Optional

# Model tier restrictions by plan
# Format: plan_name -> list of allowed models (or "*" for all models)
MODEL_TIER_RESTRICTIONS: Dict[str, List[str]] = {
    # Legacy entries kept for direct-API/BYOK deployments; current-gen
    # OpenCode Go gateway models appended so the plan gate doesn't empty
    # the ranked candidates on gateway-only deployments (the catalog moved
    # to opencode-go but this allowlist had none of its models — every
    # free-plan tenant got zero ranked models).
    # Matching is substring-based: "deepseek-v4-flash" also admits the
    # "-free" billing variant, etc.
    "free": [
        "gpt-4o-mini",
        "claude-3-haiku",
        "deepseek-chat",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-3.5-flash",
        "qwen-plus",
        # OpenCode Go value models
        "deepseek-v4-flash",
        "gemini-3-flash",
        "glm-5.1",
        "kimi-k2.5",
        "minimax-m2.7",
        "qwen3.6-plus",
        # OpenRouter gateway defaults — COST_EFFICIENT_MODELS routes
        # openrouter COMPLEX/ADVANCED to anthropic/claude-sonnet-5; without
        # these entries the plan gate zeroed out free-plan ranking on
        # openrouter-only deployments (same failure class as the OpenCode Go
        # round above).
        "claude-sonnet-5",
        "claude-3.5-sonnet",
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
        "gemini-3.5-flash",
        "qwen-plus",
        "qwen-max",
        "xiaomi/mimo-v2.5-pro",
        # OpenCode Go current-gen models
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "gemini-3-flash",
        "gemini-3.1-pro",
        "glm-5.1",
        "glm-5.2",
        "kimi-k2.5",
        "kimi-k2.7-code",
        "minimax-m2.7",
        "minimax-m3",
        "qwen3.6-plus",
        "claude-sonnet-4",
        "grok-4.6",
        "gpt-5.3-codex-spark",
    ],
    "enterprise": "*",  # All models available
    "trial": [
        "gpt-4o-mini",
        "claude-3-haiku",
        "deepseek-chat",
        "deepseek-v4-flash",
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
    "gemini-3.5-flash": {"input": 0.0000003, "output": 0.0000015},
    "xiaomi/mimo-v2.5-pro": {"input": 0.0000005, "output": 0.0000015},
    # 2026 frontier models (per-token fallback)
    "kimi-k3": {"input": 0.0000029, "output": 0.000014},
    "gpt-5.6-sol": {"input": 0.000005, "output": 0.00003},
    "claude-mythos-5": {"input": 0.00001, "output": 0.00005},
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

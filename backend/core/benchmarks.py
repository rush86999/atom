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
    # OpenRouter-hosted Chinese models — VETTED for BPC value ranking.
    # Exact-ID entries only: the partial matcher crosses model families
    # wildly on openrouter IDs (a roleplay finetune scored 92 while
    # deepseek-v4-flash scored 42), so get_ranked_providers restricts
    # openrouter candidates to this vetted set and ranks the rest out.
    # Scores align with their bare-ID siblings; pricing per OpenRouter
    # catalog (Aug 2026), all tool-capable.
    # Scores are RECALL-CALIBRATED (Aug 30): measured against a
    # follow-up-recall task with the full transcript in context —
    # minimax-m3 answered correctly; both flash models ignored the
    # assistant turn and claimed no access, so they score below the
    # conversational floor (85) regardless of their general aptitude.
    "deepseek/deepseek-v4-flash": 84,   # $0.08/$0.16 per M — see 0731 note
    "deepseek/deepseek-v4-pro": 96,     # $0.51/$1.02 per M — flagship
    "qwen/qwen3-max": 90,               # $0.78/$3.90 per M — demoted from 94
        # (Sept 6 tier battery: WORST composite of the vetted pool — failed
        # olympiad-integer, capacity-math and a moderate arithmetic item,
        # all deterministic-answer — see bpc_tier_benchmark_results.json.
        # 90 keeps it ADVANCED-eligible as a fallback; value ranking already
        # placed it last, so routing is unchanged — bookkeeping only.)
    "moonshotai/kimi-k2.5": 92,         # $0.60/$3.00 per M
    "minimax/minimax-m3": 89,           # $0.30/$1.20 per M — recall ✓
    "qwen/qwen3.7-flash": 76,           # $0.03/$0.13 per M — ultra-budget

    # Flash-tier expansion (Sept 2026) — ADVANCED floor recalibrated 94 -> 90
    # (byok_handler MIN_QUALITY_BY_COMPLEXITY): the 2026 flash tier now
    # benchmarks at last-gen-flagship level, so reserving ADVANCED for 94+
    # frontier models just bought qwen3-max at 2-14x the price for the same
    # work. Every entry below was measured on the transcript-recall probe
    # (scripts/bpc_recall_probe_sept2026_v2.py, Sept 6): with a
    # production-like completion budget (2K tokens; prod default is 6000)
    # ALL candidates pass — v1's "failures" were an artifact of a 200-token
    # budget that starved reasoning models into empty answers, not model
    # behavior. Scores are capability-calibrated against external
    # benchmarks (Artificial Analysis / SWE-bench / Terminal-Bench coverage,
    # see commit message for sources) on the repo's 0-100 anchor scale.
    # Cross-check: the repo's own tier battery
    # (scripts/bpc_tier_battery.json + bpc_tier_benchmark.py — original
    # tasks with deterministic checkers, per-BPC-tier) measured the whole
    # vetted pool on Sept 6: with valid items the flash tier saturated the
    # battery while qwen3-max (then 94) scored worst — see
    # bpc_tier_benchmark_results.json. Re-run the battery before further
    # score moves; upward deltas on a saturated battery are meaningless.
    "google/gemini-3-flash-preview": 93,  # $0.50/$3.00 per M — "frontier-
        # class at flash pricing": beats o3/GPT-5 on a medical accuracy
        # battery (PMC12894337), most cost-efficient frontier model
    "z-ai/glm-5.3-flash": 92,             # $0.075/$0.25 per M — #3 open-
        # weight (BenchmarkList), beats full GLM-5.3 on Toolathlon/GDPval-AA;
        # DeepSWE 63.4, Terminal-Bench 84.3; recall probe ✓
    "openai/gpt-5-mini": 91,              # $0.25/$2.00 per M — 99.3% of
        # gpt-5 quality at 4.2x lower cost (Wolfia); recall probe ✓
    "qwen/qwen3.8-flash": 90,             # $0.15/$0.47 per M — beats
        # minimax-m3 on NL2Repo + SWE-Bench Pro; best grad-science of the
        # flash tier (91.7); recall probe ✓
    "deepseek/deepseek-v4-flash-0731": 88,  # $0.05/$0.10 per M (OpenRouter
        # catalog) — SWE-bench Verified 79.0 vs v4-pro's 80.6, BEATS
        # v4-pro-preview on Terminal-Bench 2.1; recall probe ✓. The sibling
        # bare-ID entry above stays 84: its cache row carries DeepSeek-DIRECT
        # pricing/attribution (the ID collides with the deepseek namespace),
        # so it serves a different, pricier route — do not "align" blindly.

    # absolute frontier (early 2026)
    "gemini-3-pro": 100,
    "gpt-5.2": 100,
    "gpt-5": 99,
    "gpt-5.6-sol": 98,
    "claude-mythos-5": 99,
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
    "gemini-3.5-flash": 93,
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
    "minimax-m2.5": 88,  # Standard tier, between gemini-2.0-flash and deepseek-chat (legacy)
    "MiniMax-M3": 92,  # Latest flagship model, 512K context, image input
    "MiniMax-M3-highspeed": 91,  # Low-latency variant, 512K context
    "MiniMax-M2.7": 90,  # Previous flagship model, 204K context
    "MiniMax-M2.7-highspeed": 89,  # Previous low-latency variant, 204K context
    "lux-1.0": 88,  # LUX Computer Use (Claude 3.5 Sonnet based) - Phase 226.2-01

    # Efficiency / Simple
    "deepseek-chat": 80,
    "kimi-k1-5": 79,
    "qwen-3-7b": 82,

    # OpenCode Zen / OpenCode Go gateway models (Aug 2026)
    # Served via https://opencode.ai/zen/v1 — tested+verified open coding models
    "deepseek-v4-pro": 96,
    "deepseek-v4-flash": 88,
    "kimi-k2.7-code": 97,
    "kimi-k3": 94,

    # Zhipu AI GLM family (2026)
    "glm-5.2": 97,   # June 2026 flagship — 1M context, long-horizon reasoning
    "glm-5": 96,
    "glm-4.6": 90,
    "glm-4.5": 88,

    # Kimi K2 (Moonshot AI, 2026) — 256K context, vision
    "kimi-k2.6": 93,
    "kimi-k2-thinking": 91,
    "kimi-k2": 89,

    # Mistral (OpenAI-compatible)
    "mistral-large-latest": 90,
    "mistral-large": 90,
    "mistral-medium": 82,
    "mistral-small": 78,
    "mistral-nemo": 76,

    # Groq (ultra-fast inference)
    "llama-3.3-70b-versatile": 88,
    "llama-3.1-70b-versatile": 87,
    "llama-3.1-8b-instant": 75,
    "mixtral-8x7b-32768": 84,

    # Xiaomi
    "xiaomi/mimo-v2.5-pro": 88,
}

def get_quality_score(model_id: str) -> int:
    """
    Get the normalized quality score for a model.

    PRIORITY:
    1. Static EXACT match (curated table wins outright — the dynamic
       fetcher's partial matcher is substring-based and crosses model
       GENERATIONS: a cached ``deepseek-chat-v3-0324`` entry (scored 15.2)
       used to shadow the current ``deepseek-chat``'s exact table score of
       80, demoting a flagship model below every cognitive-tier floor)
    2. Dynamic benchmark fetcher (LMSYS, Artificial Analysis, Benchmark.moe)
       — fresh scores for models the table doesn't know exactly
    3. Static partial match (longest key wins)
    4. Heuristics for unknown models
    """
    # Exact curated score wins outright — see PRIORITY note above.
    if model_id in MODEL_QUALITY_SCORES:
        return MODEL_QUALITY_SCORES[model_id]

    # Dynamic benchmark fetcher for models the table doesn't pin exactly
    try:
        from core.dynamic_benchmark_fetcher import get_benchmark_fetcher
        fetcher = get_benchmark_fetcher()
        dynamic_score = fetcher.get_benchmark_score(model_id)
        if dynamic_score is not None:
            logger.debug(f"Using dynamic benchmark score for {model_id}: {dynamic_score}")
            # round() rather than int() — int() truncates toward zero, biasing
            # every dynamic score down by up to ~1 point and discarding the
            # sub-integer resolution the BPC value_score (quality^2/cost) is
            # sensitive to. Clamp to the valid [0, 100] range.
            return max(0, min(100, int(round(dynamic_score))))
    except ImportError:
        logger.debug("Dynamic benchmark fetcher not available, using static scores")
    except Exception as e:
        logger.debug(f"Failed to get dynamic benchmark: {e}, using static scores")

    # Fallback to static scores
    # Partial match — prefer the LONGEST matching key (most specific). A plain
    # first-match loop returned whichever key happened to iterate first: for
    # "gpt-4o-mini-2024-07-18" it matched "gpt-4o" (90) instead of the more
    # specific "gpt-4o-mini" (85), purely due to dict insertion order.
    model_lower = model_id.lower()
    best_key = None
    best_score = None
    for key, score in MODEL_QUALITY_SCORES.items():
        kl = key.lower()
        if kl in model_lower and (best_key is None or len(kl) > len(best_key)):
            best_key = kl
            best_score = score
    if best_score is not None:
        return best_score

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

        # Partial match — prefer the longest (most specific) key, matching
        # get_quality_score's behavior (see comment there).
        model_lower = model_id.lower()
        best_key = None
        best_score = None
        for key, score in capability_scores.items():
            kl = key.lower()
            if kl in model_lower and (best_key is None or len(kl) > len(best_key)):
                best_key = kl
                best_score = score
        if best_score is not None:
            return best_score

    # Fallback to general quality score
    return get_quality_score(model_id)

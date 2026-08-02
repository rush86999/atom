"""Per-request routing overrides parsed from x-atom-* HTTP headers.

Provides programmatic per-call control over LLM routing without env-flag
changes. Headers are advisory: budget enforcement and capability filters
still apply downstream. Invalid values are logged-and-ignored (never 400)
so a malformed header cannot break a chat request.

Headers:
    x-atom-tier:    force a cognitive tier (micro|standard|versatile|heavy|complex)
    x-atom-model:   force a specific model id (bypasses auto-routing)
    x-atom-intent:  force an intent label (coding|data_analysis|web_browsing|
                    creative_writing|reasoning|conversation)
"""
from __future__ import annotations

import logging
from typing import Dict, Mapping, Optional

logger = logging.getLogger(__name__)

HEADER_TIER = "x-atom-tier"
HEADER_MODEL = "x-atom-model"
HEADER_INTENT = "x-atom-intent"


def parse_routing_overrides(headers: Mapping[str, str]) -> Dict[str, str]:
    """Extract validated routing overrides from request headers.

    Args:
        headers: A header mapping (e.g. ``fastapi.Request.headers``). Header
            lookup is case-insensitive (HTTP headers are case-insensitive;
            Starlette's Headers supports both ``.get()`` and item access).

    Returns:
        A dict with zero or more of the keys ``tier``, ``model``, ``intent``.
        Invalid/unrecognized values are dropped with a debug log — the caller
        never sees a bad value, so downstream routing is unaffected.
    """
    overrides: Dict[str, str] = {}

    # Helper that works for both Starlette ``Headers`` (case-insensitive) and
    # plain dicts (case-sensitive lookup — try lowercased keys as a fallback).
    def _get(name: str) -> Optional[str]:
        if hasattr(headers, "get"):
            val = headers.get(name)
            if val is None and isinstance(headers, Mapping):
                # Plain dict fallback: HTTP headers are case-insensitive.
                lower = name.lower()
                for k, v in headers.items():
                    if k.lower() == lower:
                        return v
            return val
        return None

    # --- Tier ---
    raw_tier = _get(HEADER_TIER)
    if raw_tier:
        tier = raw_tier.strip().lower()
        if _is_valid_tier(tier):
            overrides["tier"] = tier
        else:
            logger.debug(
                f"Ignoring invalid {HEADER_TIER} header value: {raw_tier!r} "
                f"(expected one of micro|standard|versatile|heavy|complex)"
            )

    # --- Model ---
    raw_model = _get(HEADER_MODEL)
    if raw_model:
        model = raw_model.strip()
        if model and _is_known_model(model):
            overrides["model"] = model
        elif model:
            logger.debug(
                f"Ignoring unknown {HEADER_MODEL} header value: {raw_model!r} "
                f"(not in model registry)"
            )

    # --- Intent ---
    raw_intent = _get(HEADER_INTENT)
    if raw_intent:
        intent = raw_intent.strip().lower()
        if _is_valid_intent(intent):
            overrides["intent"] = intent
        else:
            logger.debug(
                f"Ignoring invalid {HEADER_INTENT} header value: {raw_intent!r}"
            )

    return overrides


# --- Validators (kept lightweight; lazy imports to avoid circular deps) -----


def _is_valid_tier(value: str) -> bool:
    try:
        from core.llm.cognitive_tier_system import CognitiveTier
        return value in {t.value for t in CognitiveTier}
    except Exception:
        return False


def _is_valid_intent(value: str) -> bool:
    try:
        from core.llm.intent_detector import is_valid_intent
        return is_valid_intent(value)
    except Exception:
        return False


def _is_known_model(model_id: str) -> bool:
    """Check whether ``model_id`` is a recognized model.

    Accepts both registry model ids (e.g. ``gpt-4o``) and provider-prefixed
    names. Falls back to True (accept) when the registry cannot be loaded,
    so a transient registry failure never blocks a legitimate override.
    """
    try:
        from core.llm.byok_handler import BYOKHandler
        registry = getattr(BYOKHandler, "_model_registry", None) or {}
        # Registry keys are model ids; also accept by model_name field.
        if model_id in registry:
            return True
        for spec in registry.values():
            name = getattr(spec, "model_name", None) or getattr(spec, "model_id", None)
            if name == model_id:
                return True
        # Also accept well-known provider model name patterns so headers like
        # x-atom-model: gpt-4o work even before the registry is populated.
        known_prefixes = ("gpt-", "claude-", "gemini-", "deepseek", "o1", "o3", "o4")
        if any(model_id.startswith(p) for p in known_prefixes):
            return True
        return False
    except Exception:
        # Fail open: if we can't validate, accept the override rather than
        # silently dropping a legitimate request. The downstream handler will
        # reject a truly invalid model id with its normal fallback.
        return True

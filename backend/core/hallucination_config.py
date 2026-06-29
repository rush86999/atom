"""Hallucination Mitigation Phase 2 — feature-flag resolvers.

Three evidence-backed mitigations, each independently flag-gated and
default-off (guaranteed no-op when unset):

  * **Cascade routing** — on schema-validation failure inside
    ``BYOKHandler.generate_structured_response``, retries once on a
    frontier model in the *same provider family*.
  * **Self-consistency voting** — 3-sample majority vote on the structured
    action plan for irreversible actions, executed exactly once.
  * **Verified graduation gate** — (SaaS-only; relies on
    ``AgentCapabilityRegistry`` which this edition does not have. Ported
    separately in SaaS. See ``docs/architecture/CONTEXT_MEMORY.md`` for
    upstream's string-tri-state verified-outcome approach.)

Resolution: env var only. This is the Personal / single-tenant edition;
per-tenant overrides are a SaaS concern and live in the SaaS fork.

This module has no database surface and no side effects. It is safe to
import from anywhere, including the voter module.
"""
from __future__ import annotations

import os
import re
from typing import Any


# ---------------------------------------------------------------------------
# Public toggles (env-var only)
# ---------------------------------------------------------------------------


def is_cascade_routing_enabled() -> bool:
    """Cascade routing on schema-validation failure (Workstream B)."""
    return _flag("ATOM_CASCADE_ROUTING")


def is_self_consistency_enabled() -> bool:
    """Self-consistency voting for irreversible actions (Workstream C)."""
    return _flag("ATOM_SELF_CONSISTENCY")


def _flag(env_var: str) -> bool:
    return os.getenv(env_var, "false").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Numeric tunables
# ---------------------------------------------------------------------------


def get_self_consistency_samples() -> int:
    """Number of samples drawn by the self-consistency voter (default 3)."""
    try:
        n = int(os.getenv("ATOM_SELF_CONSISTENCY_SAMPLES", "3"))
    except (TypeError, ValueError):
        n = 3
    return max(1, n)


def get_temperature_spread(n: int) -> list[float]:
    """Return ``n`` distinct temperatures centered around the model default.

    Wang et al. self-consistency samples at varying temperatures to surface
    the modal answer. We spread symmetrically around 0.7 in 0.1 increments:
        n=3 → [0.6, 0.7, 0.8]
        n=5 → [0.5, 0.6, 0.7, 0.8, 0.9]
    Odd counts are preferred (clean majority). Even counts are still
    well-defined; the caller's tie-break handles them.
    """
    if n <= 0:
        return [0.7]
    if n == 1:
        return [0.7]
    half = (n - 1) / 2.0
    return [round(0.7 + (i - half) * 0.1, 2) for i in range(n)]


# ---------------------------------------------------------------------------
# Frontier model registry (Workstream B)
# ---------------------------------------------------------------------------

# Frontier flagships by provider family. The "is this already frontier?"
# check uses base-id matching (snapshot suffix stripped) so version tails
# like ``-20240229`` are handled without an exhaustive list.
FRONTIER_MODELS: set[str] = {
    # OpenAI
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4",
    # Anthropic
    "claude-3-opus",
    "claude-3-5-sonnet",
    "claude-3.5-sonnet",
    "claude-sonnet-4",
    "claude-opus-4",
    # Google
    "gemini-1.5-pro",
    "gemini-2",
    # DeepSeek
    "deepseek-reasoner",
    # MiniMax
    "minimax-m2.7",
    "minimax-m2",
}

# Per-provider flagship for cascade escalation. The escalation target MUST
# stay in the same provider family as the original model — otherwise BYOK
# credentials and rate limits silently shift under the caller.
_FRONTIER_BY_PROVIDER: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet",
    "deepseek": "deepseek-reasoner",
    "gemini": "gemini-1.5-pro",
    "minimax": "minimax-m2.7",
    "mistral": "mistral-large-latest",
    "qwen": "qwen-max",
    "groq": "llama-3.3-70b-versatile",
    "cohere": "command-r-plus",
    "ollama": "llama3:70b",  # local fallback
    "lux": "gpt-4o",  # Lux joins OpenAI family for escalation
}


def _model_base(model: str) -> str:
    """Strip the dated snapshot suffix from a model id.

    Handles both the dashed (``-2024-08-06``) and compact (``-20240229``)
    Anthropic style, plus OpenAI preview tags:

        claude-3-opus-20240229  → claude-3-opus
        claude-3-5-sonnet-20241022 → claude-3-5-sonnet
        gpt-4o-2024-08-06       → gpt-4o
        deepseek-reasoner       → deepseek-reasoner  (unchanged)
    """
    return re.sub(
        r"-(20\d{2}(-?\d{2}(-?\d{2})?)?)([.-].*)?$",
        "",
        model,
    )


def is_frontier_model(model: str | None) -> bool:
    """Return True if ``model`` matches a known frontier flagship.

    Matches on the *base* model id (snapshot suffix stripped), so
    ``claude-3-opus-20240229`` registers as frontier but
    ``gpt-4o-mini`` does NOT (its base is ``gpt-4o-mini``, distinct from
    ``gpt-4o``).
    """
    if not model:
        return False
    base = _model_base(model.lower())
    return base in {f.lower() for f in FRONTIER_MODELS}


def get_frontier_model_for_provider(provider: str | None) -> str | None:
    """Return the flagship model for a provider family.

    ``provider`` may be a string ("openai") or an ``LLMProvider`` enum
    value. Returns ``None`` for unknown providers — callers must treat that
    as "do not escalate".
    """
    if provider is None:
        return None
    key = str(provider).lower().strip('"')
    if key.startswith("llmprovider."):
        key = key.split(".", 1)[1]
    return _FRONTIER_BY_PROVIDER.get(key)

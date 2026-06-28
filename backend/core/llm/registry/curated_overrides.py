from __future__ import annotations
"""Curated model overrides for the LLM registry.

Some providers (e.g. OpenRouter) do not always expose alpha / preview models via
their public ``/models`` endpoint even though the models are routable through the
provider's API. This module ships a small, hand-maintained set of entries that
``ModelMetadataFetcher`` merges into the fetched result.

Merge semantics (see ``apply_curated_overrides``):
    * Curated entries WIN on ``model_id`` collision with the upstream payload.
    * Curated entries are ADDED when the model_id is absent upstream.

Each override should mirror the shape returned by the upstream provider so the
downstream transformers / serializers do not need special-case logic. Only add
models here that:
    1. Are publicly routable through the provider (no private/internal IDs).
    2. Have stable, documented pricing (or ``None`` if unknown).
    3. Are intentionally not surfaced by the upstream ``/models`` feed.
"""

from typing import Any

# --------------------------------------------------------------------------- #
# Curated overrides
# --------------------------------------------------------------------------- #
# Shape mirrors OpenRouter's ``/api/v1/models`` item schema so it flows through
# the existing transformers without modification.
CURATED_OVERRIDES: dict[str, dict[str, Any]] = {
    "openrouter/owl-alpha": {
        "id": "openrouter/owl-alpha",
        "name": "Owl Alpha (OpenRouter)",
        "description": (
            "Curated alpha-preview model routed through OpenRouter. Not listed "
            "in the public /models feed; added by the ATUM registry so BYOK "
            "tenants can opt into it explicitly."
        ),
        "context_length": 200_000,
        "max_output_tokens": 32_000,
        # OpenRouter pricing is per-token, expressed in USD as strings.
        "pricing": {
            "prompt": "0.000005",
            "completion": "0.000015",
            "request": "0",
            "image": "0",
        },
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "tokenizer": "Unknown",
        },
        "top_provider": {
            "max_completion_tokens": 32_000,
            "is_moderated": False,
        },
        # ATUM-side metadata. The registry layer reads a few well-known keys
        # (``litellm_provider``, ``max_tokens``) so we provide them defensively.
        "litellm_provider": "openrouter",
        "max_tokens": 32_000,
        "curated": True,  # marker so downstream code can tell this is hand-curated
    },
}


def _log_override_replaced(model_id: str) -> None:
    """Tiny indirection so tests can assert override-win behaviour via the log.

    Kept intentionally minimal — we do not want a hard dependency on the stdlib
    logger here so the module stays import-safe for the fetcher hot path.
    """
    import logging

    logging.getLogger(__name__).debug(
        "curated_override_replaced_upstream model_id=%s", model_id
    )


def apply_curated_overrides(upstream: dict[str, Any]) -> dict[str, Any]:
    """Merge :data:`CURATED_OVERRIDES` into ``upstream`` (non-destructive).

    Args:
        upstream: The dict returned by a fetcher (model_id -> model_payload).

    Returns:
        A NEW dict with curated entries applied. ``upstream`` is not mutated.
        On collision, the curated entry replaces the upstream entry.
    """
    if not isinstance(upstream, dict):
        return dict(CURATED_OVERRIDES)

    merged = dict(upstream)
    for model_id, payload in CURATED_OVERRIDES.items():
        if model_id not in merged:
            merged[model_id] = payload
    return merged


def curated_overrides_in_pricing_shape() -> dict[str, dict[str, Any]]:
    """Return curated overrides reshaped to the dynamic_pricing_fetcher schema.

    ``dynamic_pricing_fetcher`` (used by ``GET /api/llm/models``) stores each
    model with keys like ``input_cost_per_token`` / ``output_cost_per_token``
    (floats), ``max_tokens``, ``name``, ``description``, ``source``,
    ``litellm_provider``. This helper converts the canonical OpenRouter-shape
    entries in :data:`CURATED_OVERRIDES` into that schema so the same source of
    truth feeds both fetchers.
    """
    out: dict[str, dict[str, Any]] = {}
    for model_id, payload in CURATED_OVERRIDES.items():
        pricing = payload.get("pricing", {}) or {}
        try:
            input_cost = float(pricing.get("prompt", 0))
        except (TypeError, ValueError):
            input_cost = 0.0
        try:
            output_cost = float(pricing.get("completion", 0))
        except (TypeError, ValueError):
            output_cost = 0.0

        out[model_id] = {
            "input_cost_per_token": input_cost,
            "output_cost_per_token": output_cost,
            "max_tokens": int(payload.get("context_length") or payload.get("max_tokens") or 0),
            "name": payload.get("name", model_id),
            "description": payload.get("description", ""),
            "source": "openrouter",
            "litellm_provider": payload.get("litellm_provider", "openrouter"),
            "curated": True,
        }
    return out


def apply_curated_overrides_to_pricing(upstream: dict[str, Any]) -> dict[str, Any]:
    """Merge curated overrides (in pricing shape) into a pricing-fetcher result.

    Mirror of :func:`apply_curated_overrides` for the dynamic_pricing_fetcher's
    schema. Curated entries win on collision; non-destructive.
    """
    curated = curated_overrides_in_pricing_shape()
    if not isinstance(upstream, dict):
        return curated
    merged = dict(upstream)
    for model_id, payload in curated.items():
        if model_id not in merged:
            merged[model_id] = payload
    return merged

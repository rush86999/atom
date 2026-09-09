"""BPC frontier-reserved gate tests (Sept 2026).

Pins FRONTIER_RESERVED_MIN_COMPLEXITY: gpt-6-astra ($10/$50 per MTok, the
priciest OpenAI model) must ONLY serve the top of the difficulty ladder.
Value ranking alone can't express this — a 100-quality model passes every
min_quality floor, so without the gate a thin cheap pool lets the flagship
win routine turns at 10-30x the going rate.

Covers all three enforcement points:
1. Dynamic BPC pool: astra excluded below QueryComplexity.ADVANCED.
2. Cognitive-tier steering: astra only at the top CognitiveTier (COMPLEX).
3. Static COST_EFFICIENT_MODELS fallback: misconfigured slots are skipped
   by the same invariant.
"""

import os
os.environ["TESTING"] = "1"

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.llm.byok_handler import (
    COST_EFFICIENT_MODELS,
    BYOKHandler,
    QueryComplexity,
)
from core.llm.cognitive_tier_system import CognitiveTier


# blended $/M per model — mirrors the live catalogs (astra: (10+50)/2).
_BLENDS = {
    "gpt-6-astra": 30.0,
    "google/gemini-3-flash-preview": 1.75,
    "z-ai/glm-5.3-flash": 0.1625,
    "minimax/minimax-m3": 0.75,
}


def _fetcher():
    fetcher = MagicMock()
    fetcher.pricing_cache = {
        mid: {
            "litellm_provider": "openai" if mid == "gpt-6-astra" else "openrouter",
            "input_cost_per_token": blend / 2e6,
            "output_cost_per_token": blend / 2e6,
            "max_input_tokens": 1_000_000,
        }
        for mid, blend in _BLENDS.items()
    }
    return fetcher


@contextmanager
def _handler_cm():
    from core.models import Tenant, Workspace

    workspace = SimpleNamespace(tenant_id="t-1")
    tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value="pro"))

    def _query(model):
        q = MagicMock()
        if model is Workspace:
            q.filter.return_value.first.return_value = workspace
        elif model is Tenant:
            q.filter.return_value.first.return_value = tenant
        else:
            q.filter.return_value.first.return_value = None
            q.all.return_value = []
        return q

    session = MagicMock()
    session.query.side_effect = _query
    ctx = SimpleNamespace(__enter__=lambda s: session, __exit__=lambda s, *a: None)

    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session", return_value=ctx), \
         patch("core.database.get_db_session", return_value=ctx):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")

    # Unbind nothing here — we call the real BPC directly.
    handler.clients = {"openai": MagicMock(), "openrouter": MagicMock()}
    handler.env_key_providers = {"openai", "openrouter"}  # BYOK: no plan gating
    handler.rate_tracker.get_headroom = MagicMock(return_value=1.0)
    handler.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
    handler.rate_tracker.get_model_weight = MagicMock(return_value=1.0)
    handler.rate_tracker.get_max_context = MagicMock(return_value=None)
    handler.cache_router.calculate_effective_cost = MagicMock(
        side_effect=lambda model, provider, estimated_tokens, turn_index=0, **kw:
            _BLENDS[model] / 1e6
    )
    handler.excluded_models = set()
    yield handler


def _rank(handler, complexity, **kw):
    with patch(
        "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
        return_value=_fetcher(),
    ):
        return list(
            handler.get_ranked_providers(complexity, is_managed_service=False, **kw)
        )


class TestFrontierReservedGate:
    def test_astra_absent_below_advanced(self):
        # Quality 100 clears every complexity floor (85/80/88) — only the
        # frontier-reserved gate keeps it out of routine turns.
        for complexity in (QueryComplexity.SIMPLE, QueryComplexity.MODERATE,
                           QueryComplexity.COMPLEX):
            with _handler_cm() as handler:
                result = _rank(handler, complexity)
            models = [m for _, m in result]
            assert "gpt-6-astra" not in models, complexity
            # The cheap frontier-class pool still serves these tiers.
            assert "google/gemini-3-flash-preview" in models, complexity

    def test_astra_rankable_at_advanced(self):
        with _handler_cm() as handler:
            result = _rank(handler, QueryComplexity.ADVANCED)
        assert ("openai", "gpt-6-astra") in result

    def test_cognitive_tier_steering_gate(self):
        # Phase 68: when a cognitive tier is passed, the cognitive ladder
        # carries the difficulty signal. COMPLEX (top) may serve astra;
        # HEAVY may not — even though astra's quality clears the HEAVY
        # floor (90) and the cheaper flash model passes it.
        with _handler_cm() as handler:
            result = _rank(
                handler, QueryComplexity.ADVANCED, cognitive_tier=CognitiveTier.COMPLEX
            )
        assert ("openai", "gpt-6-astra") in result

        with _handler_cm() as handler:
            result = _rank(
                handler, QueryComplexity.ADVANCED, cognitive_tier=CognitiveTier.HEAVY
            )
        models = [m for _, m in result]
        assert "gpt-6-astra" not in models
        assert "google/gemini-3-flash-preview" in models  # 93 >= HEAVY floor 90


class TestStaticFallbackGate:
    def test_misconfigured_cost_efficient_slot_skipped(self):
        with _handler_cm() as handler:
            original = dict(COST_EFFICIENT_MODELS["openai"])
            COST_EFFICIENT_MODELS["openai"][QueryComplexity.COMPLEX] = "gpt-6-astra"
            try:
                with patch(
                    "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                    side_effect=RuntimeError("pricing down"),
                ):
                    result = list(handler.get_ranked_providers(
                        QueryComplexity.COMPLEX, is_managed_service=False
                    ))
            finally:
                COST_EFFICIENT_MODELS["openai"].clear()
                COST_EFFICIENT_MODELS["openai"].update(original)
        # The gate skipped the misplaced astra slot instead of routing a
        # COMPLEX turn to the flagship.
        assert "gpt-6-astra" not in [m for _, m in result]

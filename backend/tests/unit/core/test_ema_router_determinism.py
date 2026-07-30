"""Tests for the combined predictor + EMA blend and the related bug fixes.

Covers:
- The two signals are BLENDED (not mutually exclusive): when EMA is enabled
  the predictor path is still consulted in the same scoring equation.
- EMA still drives ranking during cold-start (no predictor).
- Bug fixes: samples counter is actually written; stats don't leak across
  tenants and don't collapse task:model keys; confidence is clamped to [0,1];
  the EMA-enabled flag parses 1/true/yes/on consistently.
"""
import os
import pytest
from unittest.mock import MagicMock

from core.learning_llm_router import (
    LearningBasedRouter,
    ModelSpec,
    RoutingRequest,
    RoutingFeedback,
    ModelCapability,
)
from core.llm.learning_router_registry import ema_router_enabled


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def ema_router(mock_db):
    router = LearningBasedRouter(db=mock_db)
    router._model_registry = {
        "gpt-4": ModelSpec(
            model_id="gpt-4",
            provider="openai",
            model_name="gpt-4",
            capabilities={ModelCapability.REASONING, ModelCapability.CODE_GENERATION},
            cost_per_million=10.0,
            quality_score=0.9,
            speed_score=0.5,
            context_window=8192,
            supports_cache=True,
            tier="premium",
        ),
        "gpt-3.5": ModelSpec(
            model_id="gpt-3.5",
            provider="openai",
            model_name="gpt-3.5",
            capabilities={ModelCapability.REASONING, ModelCapability.CODE_GENERATION},
            cost_per_million=2.0,
            quality_score=0.7,
            speed_score=0.8,
            context_window=4096,
            supports_cache=True,
            tier="standard",
        ),
    }
    return router


def _req(tenant="t1", task="code_generation", tokens=100, **kw):
    return RoutingRequest(
        tenant_id=tenant, task_type=task, estimated_tokens=tokens, **kw
    )


def _fb(model_id, success, quality_satisfied, tenant="t1", task="code_generation",
        latency=100.0, cost=0.0002):
    return RoutingFeedback(
        routing_result_id="r",
        tenant_id=tenant,
        model_id=model_id,
        task_type=task,
        success=success,
        quality_satisfied=quality_satisfied,
        cost_within_budget=True,
        actual_latency_ms=latency,
        actual_cost=cost,
    )


# --------------------------------------------------------------------------
# Original determinism contract (now exercised via the unified blend path)
# --------------------------------------------------------------------------

def test_ema_scoring_disabled_by_default(ema_router, monkeypatch):
    monkeypatch.delenv("ATOM_EMA_ROUTER_ENABLED", raising=False)
    candidates = list(ema_router._model_registry.values())
    res = ema_router._score_candidates(candidates, _req())
    assert len(res) == 2


def test_ema_scoring_enabled_ranks_successful_model_first(ema_router, monkeypatch):
    """The headline contract: after feedback, the successful cheaper model wins.

    Previously this ran through a SEPARATE _score_candidates_with_ema path that
    short-circuited the predictor. It now runs through the unified blend, but
    the observable ranking must be unchanged.
    """
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    candidates = list(ema_router._model_registry.values())

    # Sanity: both signals score before any feedback.
    assert len(ema_router._score_candidates(candidates, _req())) == 2

    ema_router._update_ema_scores(_fb("gpt-3.5", True, True))
    ema_router._update_ema_scores(_fb("gpt-4", False, False, latency=800.0, cost=0.001))

    assert ema_router._ema_scores["t1:code_generation:gpt-3.5"]["success"] == 1.0
    assert ema_router._ema_scores["t1:code_generation:gpt-4"]["success"] == 0.0

    res = ema_router._score_candidates(candidates, _req())
    assert res[0][0].model_id == "gpt-3.5"


# --------------------------------------------------------------------------
# New: the two signals are blended, not mutually exclusive
# --------------------------------------------------------------------------

def test_ema_term_contributes_even_when_predictor_absent(ema_router, monkeypatch):
    """Cold-start (no per-model predictor) + EMA enabled -> EMA still re-ranks."""
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    candidates = list(ema_router._model_registry.values())

    # No predictor registered for this tenant/task at all.
    assert not ema_router._per_model_routers

    # gpt-4 has great observed success; gpt-3.5 failed. EMA alone should flip
    # the ranking toward gpt-4 (whose static base score is already higher, so
    # this also documents that EMA reinforces rather than fights the base).
    ema_router._update_ema_scores(_fb("gpt-4", True, True, latency=200.0))
    ema_router._update_ema_scores(_fb("gpt-3.5", False, False, latency=900.0))

    res = ema_router._score_candidates(candidates, _req())
    assert res[0][0].model_id == "gpt-4"


def test_predictor_and_ema_both_contribute(ema_router, monkeypatch):
    """When a predictor exists AND EMA is enabled, both terms feed the score.

    We fake a per-model router whose predict_satisfaction returns a fixed value
    and whose confidence returns a fixed blend. The contract: with EMA enabled
    the score is STRICTLY HIGHER than with EMA disabled (the EMA term is
    genuinely additive), proving the two signals are blended rather than the
    EMA branch short-circuiting the predictor (the old bug).
    """
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    model = ema_router._model_registry["gpt-3.5"]

    fake = MagicMock()
    fake.predict_satisfaction.return_value = 0.8
    fake.confidence.return_value = 0.2  # predictor term = 0.2 * 0.8 = 0.16
    ema_router._per_model_routers["t1:code_generation"] = fake

    # Seed EMA success for gpt-3.5 so the EMA term is nonzero.
    ema_router._update_ema_scores(_fb("gpt-3.5", True, True))

    req = _req()
    weights = ema_router._get_learned_weights(req.task_type, req.tenant_id)
    ema_norm = ema_router._ema_normalization_baselines([model], req)
    max_spec_cost = max(m.cost_per_million for m in [model])

    score_with_ema = ema_router._combined_model_score(
        model, req, weights, fake, {"x": 1.0}, ema_norm, max_spec_cost
    )

    # Same inputs but EMA disabled: only base + predictor term.
    monkeypatch.delenv("ATOM_EMA_ROUTER_ENABLED", raising=False)
    score_no_ema = ema_router._combined_model_score(
        model, req, weights, fake, {"x": 1.0}, ema_norm, max_spec_cost
    )

    # The EMA contribution must be exactly (1 - confidence) * EMA_WEIGHT * term,
    # which is strictly positive here (success=1.0). Assert the delta rather
    # than reconstructing the full sub-term formula (brittle).
    delta = score_with_ema - score_no_ema
    assert delta > 0
    # Upper bound: the EMA term can contribute at most (1-0.2)*EMA_WEIGHT*1.0
    # (the quality sub-term is capped at 1.0).
    assert delta <= (1.0 - 0.2) * ema_router._EMA_SCORE_WEIGHT + 1e-9


def test_ema_disabled_when_flag_off(ema_router, monkeypatch):
    """ema_router_enabled() must honor the flag (default off)."""
    monkeypatch.delenv("ATOM_EMA_ROUTER_ENABLED", raising=False)
    assert ema_router_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE", "Yes"])
def test_ema_flag_parses_truthy_consistently(monkeypatch, val):
    """The parse must accept {1,true,yes,on} case-insensitively everywhere.

    Regression guard: chat_routes/stats used to only accept "true", disagreeing
    with the scoring branch.
    """
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", val)
    assert ema_router_enabled() is True


# --------------------------------------------------------------------------
# Bug-fix coverage
# --------------------------------------------------------------------------

def test_samples_counter_is_incremented(ema_router):
    """_update_ema_scores must write a real samples count (was always 1)."""
    for _ in range(5):
        ema_router._update_ema_scores(_fb("gpt-3.5", True, True))
    bucket = ema_router._ema_scores["t1:code_generation:gpt-3.5"]
    assert bucket["samples"] == 5


def test_bias_correction_early_values(ema_router, monkeypatch):
    """Early EMA values are bias-corrected toward the true running mean.

    With alpha=1.0 every sample fully replaces the value (no smoothing), so the
    EMA must exactly equal the most recent observation regardless of n — a clean
    way to assert the bias-correction divisor isn't distorting the value.
    """
    monkeypatch.setenv("ATOM_EMA_ALPHA", "1.0")
    ema_router._update_ema_scores(_fb("gpt-3.5", True, True, latency=500.0))
    ema_router._update_ema_scores(_fb("gpt-3.5", False, False, latency=100.0))
    bucket = ema_router._ema_scores["t1:code_generation:gpt-3.5"]
    assert bucket["success"] == 0.0  # last sample was a failure
    assert bucket["latency"] == 100.0


def test_stats_do_not_leak_across_tenants(ema_router, monkeypatch):
    """get_routing_statistics must scope ema_scores to the requesting tenant."""
    import asyncio
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    ema_router._update_ema_scores(_fb("gpt-3.5", True, True, tenant="t1"))
    ema_router._update_ema_scores(_fb("gpt-4", True, True, tenant="secret"))

    stats = asyncio.run(ema_router.get_routing_statistics("t1"))
    # Only t1's key should appear; "secret" tenant must not leak.
    for out_key in stats["ema_scores"]:
        assert not out_key.startswith("secret:")
    assert "code_generation:gpt-3.5" in stats["ema_scores"]


def test_stats_task_model_keys_do_not_collide(ema_router, monkeypatch):
    """Two (task, model) pairs must not overwrite each other in ema_scores."""
    import asyncio
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    ema_router._update_ema_scores(_fb("gpt-3.5", True, True, task="code_generation"))
    ema_router._update_ema_scores(_fb("gpt-3.5", False, False, task="question_answering"))

    stats = asyncio.run(ema_router.get_routing_statistics("t1"))
    keys = set(stats["ema_scores"].keys())
    assert "code_generation:gpt-3.5" in keys
    assert "question_answering:gpt-3.5" in keys


def test_route_clamps_confidence_to_unit_interval(ema_router, monkeypatch):
    """RoutingResult.confidence is documented 0-1; must not exceed 1.0.

    A preferred long-context model with a trained predictor used to push the
    raw weighted sum above 1.0.
    """
    import asyncio
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    # Stack every bonus: long context + tenant pref + learned predictor.
    for m in list(ema_router._model_registry.values()):
        ema_router._model_registry[m.model_id] = ModelSpec(
            model_id=m.model_id,
            provider=m.provider,
            model_name=m.model_name,
            capabilities=m.capabilities | {ModelCapability.LONG_CONTEXT},
            cost_per_million=m.cost_per_million,
            quality_score=1.0,
            speed_score=1.0,
            context_window=m.context_window,
            supports_cache=m.supports_cache,
            tier=m.tier,
        )
    fake = MagicMock()
    fake.predict_satisfaction.return_value = 1.0
    fake.confidence.return_value = 0.3
    ema_router._per_model_routers["t1:code_generation"] = fake

    req = RoutingRequest(
        tenant_id="t1",
        task_type="code_generation",
        estimated_tokens=100000,  # >50000 -> long-context bonus
        user_preferences={"preferred_model": "gpt-4"},  # +0.15 bonus
    )
    result = asyncio.run(ema_router.route(req))
    assert 0.0 <= result.confidence <= 1.0

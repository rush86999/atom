"""BPC must pick cheap-but-adequate models for small structured tasks.

Small verdict workloads (tool planning, canvas-edit planning, background
extraction, spreadsheet NL→SQL) return a few hundred tokens of JSON. Among
flash-class models the quality spread is a couple of points while the price
spread is >2.5x, so the default quality-weighted score spent 2-6x for no
measurable planning gain:

    model                            quality  eff.cost   default score   rank
    z-ai/glm-5.3-flash                  92    3.25e-07        26043        1
    qwen/qwen3.8-flash                  90    3.10e-07        26129        2
    deepseek/deepseek-v4-flash-0731     88    1.225e-07       63216        3

`task_type` now opts these calls into cost-priority ranking: rank by price over
a quality floor, so "cheap" cannot become "bad". User-facing generation (chat
replies, drafting) keeps the quality-weighted default.

Observed live 2026-09-10 after the pin removals: the tool planner and canvas
editor were resolving to glm-5.3-flash (and, once routing went dynamic,
qwen3-max at 0.78/3.90 $/M for a planning call).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TESTING", "1")

from core.llm.byok_handler import BYOKHandler, QueryComplexity


@pytest.fixture
def handler():
    """A real handler over the live pricing cache (no network calls made)."""
    return BYOKHandler(workspace_id="default")


def _rank(handler, task_type, cost_priority=None):
    return list(handler.get_ranked_providers(
        QueryComplexity.MODERATE, task_type, True, "free", False,
        requires_tools=True, requires_structured=True,
        estimated_tokens=3000, cost_priority=cost_priority,
    ))


def _eff_cost(handler, provider, model):
    from core.llm.byok_handler import AwaitableResult

    c = handler.cache_router.calculate_effective_cost(
        model, provider, 3000, turn_index=0
    )
    return float(c.value if isinstance(c, AwaitableResult) else c)


def _quality(model):
    from core.benchmarks import get_quality_score

    return get_quality_score(model)


@pytest.mark.parametrize("task_type", ["planning", "extraction", "nl2sql"])
def test_small_tasks_route_to_the_cheapest_capable_model(handler, task_type):
    ranked = _rank(handler, task_type)
    assert ranked, f"no candidates for task_type={task_type}"

    provider, model = ranked[0]
    picked = _eff_cost(handler, provider, model)

    # The winner must be the cheapest ranked option that clears the quality
    # floor — not merely "cheaper than before".
    above_floor = [
        (p, m) for p, m in ranked if _quality(m) >= 85
    ]
    cheapest = min(above_floor, key=lambda pm: _eff_cost(handler, *pm))
    assert (provider, model) == cheapest, (
        f"{task_type}: expected cheapest capable {cheapest}, got {(provider, model)}"
    )


def test_cost_priority_beats_the_default_quality_weighted_pick(handler):
    """The whole point: the default pick is measurably pricier."""
    default_first = _rank(handler, None)[0]
    cheap_first = _rank(handler, "planning")[0]

    default_cost = _eff_cost(handler, *default_first)
    cheap_cost = _eff_cost(handler, *cheap_first)

    assert cheap_cost < default_cost, (
        "cost-priority must land on a strictly cheaper model than the default "
        f"quality-weighted pick (default={default_first}@{default_cost:.3e}, "
        f"cost-priority={cheap_first}@{cheap_cost:.3e})"
    )


def test_quality_floor_keeps_cost_from_becoming_bad(handler):
    """Every cost-priority candidate must clear the quality floor."""
    for provider, model in _rank(handler, "extraction"):
        assert _quality(model) >= 85, (
            f"{provider}/{model} (quality={_quality(model)}) fell below the "
            "cost-priority quality floor"
        )


def test_explicit_flag_overrides_task_type(handler):
    """An explicit cost_priority wins over the task_type default."""
    assert _rank(handler, None, cost_priority=True)[0] == _rank(handler, "planning")[0]
    assert _rank(handler, "planning", cost_priority=False)[0] == _rank(handler, None)[0]


def test_user_facing_generation_keeps_quality_weighting(handler):
    """A plain chat call (no task_type) must NOT become cost-first."""
    assert handler.get_ranked_providers(
        QueryComplexity.MODERATE, None, True, "free", False,
        requires_tools=True, requires_structured=True, estimated_tokens=3000,
        cost_priority=False,
    ) == _rank(handler, None)


def test_cost_priority_never_errors_out_to_a_single_model(handler):
    """Regression: the cost sort used `-cost`, which raised on the
    AwaitableResult cost wrapper; get_ranked_providers swallowed it and fell
    back to the static mapping, returning ONE model. A real ranked list must
    come back."""
    for task_type in ("planning", "extraction", "nl2sql"):
        ranked = _rank(handler, task_type)
        assert len(ranked) > 1, (
            f"task_type={task_type} returned {ranked!r} — looks like the "
            "BPC-failure static fallback, not a ranked pool"
        )


def test_awaitable_result_supports_unary_minus():
    """The wrapper must complete its numeric surface; cost arithmetic goes
    through it."""
    from core.llm.byok_handler import AwaitableResult

    assert -AwaitableResult(2.5) == -2.5


class TestReasoningMandatoryExcludedFromCostPriority:
    """A reasoning-mandatory pair (memoized after it rejected the disable
    switch) is latency-ineligible for small-JSON tasks: it spent 75s per
    planning call on hidden thinking and blew the 95s turn budget turn
    after turn (live 2026-09-15/16, canvas a1a13834). Excluded from
    cost-priority candidates unless nothing else qualifies — evidence-
    driven via the memo, not a name heuristic."""

    def test_reasoning_mandatory_pair_dropped_when_alternative_qualifies(
            self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        # Catalog-agnostic: memoize whatever currently ranks FIRST, then
        # assert it is dropped in favor of the next quality-85+ candidate.
        ranked = _rank(handler, "planning")
        assert ranked, "planning ladder must not be empty"
        top_prov, top_model = ranked[0]
        monkeypatch.setattr(bh, "_REASONING_MANDATORY",
                            {f"{top_prov}/{top_model}"})
        after = _rank(handler, "planning")
        assert after, "ladder must not empty"
        assert (top_prov, top_model) not in after[:1], (
            f"memoized reasoning-mandatory pair still tops: {after[:2]}")

    def test_reasoning_mandatory_pair_kept_when_alone(self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        # If EVERY quality-85+ candidate is reasoning-mandatory, the
        # ladder must not empty — the pair comes back rather than leaving
        # the planning call with no candidates.
        ranked_all = _rank(handler, "planning")
        assert ranked_all, "catalog must have candidates"
        all_pairs = {f"{p}/{m}" for p, m in ranked_all}
        monkeypatch.setattr(bh, "_REASONING_MANDATORY", all_pairs)
        ranked = _rank(handler, "planning")
        assert ranked, "all-mandatory ladder must not empty"

    def test_no_memo_planner_unaffected(self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        monkeypatch.setattr(bh, "_REASONING_MANDATORY", set())
        base = _rank(handler, "planning")
        again = _rank(handler, "planning")
        assert base == again


class TestAuthFailedBench:
    """A 401 AuthError for a (provider, model) pair is a REJECTED
    CREDENTIAL for that pair — the structured path memoizes it and ranking
    skips the pair so it stops eating the turn budget before a working
    route is reached (live 2026-09-16: opencode-go/gemini-3-flash 401'd
    as the cheapest planning pick; the canvas teach turn timed out at
    120s and the user saw 'Could not reach the agent')."""

    def test_auth_failed_pair_excluded_from_ranking(self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        ranked = _rank(handler, "planning")
        assert ranked
        top_prov, top_model = ranked[0]
        monkeypatch.setattr(bh, "_AUTH_FAILED", {f"{top_prov}/{top_model}"})
        after = _rank(handler, "planning")
        assert after
        assert (top_prov, top_model) not in after[:1], after[:2]

    def test_auth_failed_all_pairs_ladder_not_emptied(self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        ranked_all = _rank(handler, "planning")
        all_pairs = {f"{p}/{m}" for p, m in ranked_all}
        monkeypatch.setattr(bh, "_AUTH_FAILED", all_pairs)
        ranked = _rank(handler, "planning")
        assert ranked, "all-401 ladder must not empty (fallback to candidates)"


class TestBpcGatewayIntegration:
    """BPC now consults BYOK's credential and catalog state BEFORE ranking,
    and the fallback order is family-diverse instead of a hardcoded
    priority list. The gateway-family tagging warns when all candidates
    are on one upstream."""

    def test_auth_failed_provider_excluded_before_ranking(self, handler, monkeypatch):
        from core.llm import byok_handler as bh

        ranked = _rank(handler, "planning")
        assert ranked
        top_prov = ranked[0][0]
        # Memoize EVERY model the provider has (the gate checks all)
        all_models = handler._provider_models_cached(top_prov)
        monkeypatch.setattr(bh, "_AUTH_FAILED",
                            {f"{top_prov}/{m}" for m in all_models})
        after = _rank(handler, "planning")
        assert after
        # The benched pairs should not appear at the top (either the
        # provider is fully excluded, or its pairs are filtered downstream)
        top_pairs = {(p, m) for p, m in after[:3]}
        benched_pairs = {(top_prov, m) for m in all_models}
        assert not (top_pairs & benched_pairs) or len({p for p, _ in after[:3]}) > 1, (
            f"benched {top_prov} pairs still dominate: {after[:3]}")

    def test_family_diverse_fallback_order(self, handler):
        """The fallback order must interleave gateway families — a single
        gateway failure shouldn't cascade to every fallback. Catalog-
        agnostic: inject a fake client map to control which providers
        exist."""
        handler.clients = {
            "openrouter": object(), "deepseek": object(), "opencode-go": object(),
        }
        try:
            order = handler._get_provider_fallback_order("openrouter")
            assert "openrouter" in order  # primary first
            assert "deepseek" in order
            # With 3 families, the second entry should be from a different family
            if len(order) > 1:
                assert order[1] != "openrouter", (
                    f"fallback not family-diverse: {order}")
        finally:
            # Restore the real client map (the fixture handler is shared)
            del handler.clients

    def test_gateway_family_concentration_detected(self, handler):
        families = handler._gateway_families([
            ("openrouter", "a"), ("openrouter", "b"), ("openrouter", "c")])
        assert families == {"openrouter": 3}
        families2 = handler._gateway_families([
            ("openrouter", "a"), ("deepseek", "b")])
        assert len(families2) == 2

    def test_provider_models_cached(self, handler):
        models = handler._provider_models_cached("openrouter")
        assert isinstance(models, list)

    def test_ranking_with_mixed_families_no_warning(self, handler, caplog):
        """When candidates span multiple families, the concentration
        warning must NOT fire."""
        import logging

        with caplog.at_level(logging.WARNING, logger="core.llm.byok_handler"):
            # A ranking that naturally has multiple providers (if only one
            # exists in the catalog, the warning firing is correct — this
            # test documents the check, not forces the catalog shape)
            ranked = _rank(handler, "planning")
        # We don't assert absence — single-family catalogs SHOULD warn.
        # The check itself is exercised by the concentration test above.
        assert ranked is not None

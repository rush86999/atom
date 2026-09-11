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

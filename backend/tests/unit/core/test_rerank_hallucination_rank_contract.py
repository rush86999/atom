"""The live BPC re-rank must let OBSERVED HALLUCINATION change the order.

Root cause this file locks down (found by probing the running app, not by unit
test): a model's EMA term in ``BYOKHandler._rerank_with_learning`` was only
added when it HAD history, and a model without history scored exactly ``0.0``
via a ``-(idx * 0.001)`` placeholder — the same score a model observed to
fabricate on every turn received (success EMA 0.0). Two candidates with equal
scores keep BPC order, so:

* the fabricator tied with every unobserved candidate and kept its BPC position;
* EMA state is rebuilt from DB history on process start, so a restart silently
  PROMOTED the fabricator back to the front.

The contract enforced here: observed-good > unobserved > observed-bad. A model
with zero success observations must sort strictly below one with none.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND = Path(__file__).resolve().parents[3]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.llm.byok_handler import BYOKHandler  # noqa: E402

TASK = "question_answering"
CANDIDATES = [("prov", "probe/fab"), ("prov", "probe/safe"), ("prov", "probe/new")]


class _FakeLearningRouter:
    """The subset of LearningBasedRouter that the re-rank path reads."""

    _EMA_SCORE_WEIGHT = 0.3

    def __init__(self, ema_scores=None):
        self._ema_scores = dict(ema_scores or {})
        self._per_model_routers = {}
        self.stashed = []

    # -- helpers used by the tests -------------------------------------------
    def key(self, model):
        return f"default:{TASK}:{model}"

    def set_success(self, model, success, samples=3):
        self._ema_scores[self.key(model)] = {
            "samples": samples,
            "success": success,
            "success_n": samples,
        }

    # -- the path under test reads/creates these ------------------------------
    def _extract_request_features(self, _request):
        return {f"f{i}": 0.0 for i in range(16)}

    def stash_decision(self, _features):
        decision_id = f"decision-{len(self.stashed)}"
        self.stashed.append(decision_id)
        return decision_id


def _handler(router: _FakeLearningRouter):
    """Bare handler with only the attributes the re-rank path touches."""
    handler = BYOKHandler.__new__(BYOKHandler)
    handler.tenant_id = "default"
    handler._pending_routing_result_id = None
    return handler, router


async def _rank(handler, options=None):
    out = await BYOKHandler._rerank_with_learning(
        handler, list(options or CANDIDATES), "how many units shipped?", "chat"
    )
    return [model for _provider, model in out]


@pytest.fixture
def ema_on(monkeypatch):
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "1")
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "1")


@pytest.mark.asyncio
async def test_fabricator_ranks_below_unobserved_model(ema_on):
    """Observed-bad must lose to no-evidence — the restart-promotion bug."""
    router = _FakeLearningRouter()
    router.set_success("probe/fab", 0.0)
    router.set_success("probe/safe", 1.0)
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    # observed-good, then the unobserved candidate, then the proven fabricator.
    assert order == ["probe/safe", "probe/new", "probe/fab"]


@pytest.mark.asyncio
async def test_unobserved_keeps_bpc_order_relative_to_peers(ema_on):
    """Two unobserved candidates must not be reordered against each other.

    Order is the full contract: observed-good > unobserved > observed-bad. With
    only negative evidence on record, the two unobserved candidates stay in BPC
    order and the fabricator goes last (it is the only PROVEN harm).
    """
    router = _FakeLearningRouter()
    router.set_success("probe/fab", 0.0)  # only the fabricator has history
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    assert order == ["probe/safe", "probe/new", "probe/fab"]


@pytest.mark.asyncio
async def test_zero_success_observation_counts_as_learned_signal(ema_on):
    """A 0.0 EMA term is still EVIDENCE — otherwise BPC order silently wins.

    The trap this guards: treating a zero term as "no signal" (the old code did)
    makes a fabricator tie with every unobserved candidate, so the sort falls
    back to BPC order and the fabrication changes nothing.
    """
    router = _FakeLearningRouter()
    router.set_success("probe/fab", 0.0)
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    assert order != [model for _p, model in CANDIDATES]
    assert order[-1] == "probe/fab"


@pytest.mark.asyncio
async def test_no_history_at_all_leaves_bpc_order_untouched(ema_on):
    """With zero telemetry the path must be a no-op (never a random reshuffle)."""
    router = _FakeLearningRouter()
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    assert order == [model for _p, model in CANDIDATES]


@pytest.mark.asyncio
async def test_ema_flag_off_is_a_no_op_even_with_fabrication_history(monkeypatch):
    """The EMA switch stays the only switch: flag off -> BPC order preserved."""
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "0")
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "1")
    router = _FakeLearningRouter()
    router.set_success("probe/fab", 0.0)
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    assert order == [model for _p, model in CANDIDATES]


@pytest.mark.asyncio
async def test_latency_and_cost_never_outvote_fabrication(ema_on):
    """A fast/cheap model that invents figures is still a model that invents figures."""
    router = _FakeLearningRouter()
    # Bad success but BEST possible latency/cost telemetry.
    router._ema_scores[router.key("probe/fab")] = {
        "samples": 4, "success": 0.0, "latency": 1.0, "cost": 0.0,
    }
    router._ema_scores[router.key("probe/safe")] = {"samples": 4, "success": 1.0}
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        order = await _rank(handler)

    assert order.index("probe/safe") < order.index("probe/fab")


@pytest.mark.asyncio
async def test_learned_signal_mints_a_decision_for_outcome_feedback(ema_on):
    """Train/serve consistency: a real re-rank stashes features for feedback."""
    router = _FakeLearningRouter()
    router.set_success("probe/safe", 1.0)
    handler, _ = _handler(router)

    with patch(
        "core.llm.learning_router_registry.get_learning_router_instance",
        return_value=router,
    ):
        await _rank(handler)

    assert handler._pending_routing_result_id is not None

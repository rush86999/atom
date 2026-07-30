"""Tests for the round-3 router bug fixes.

Covers:
- Bug 1: PerModelRouter.train honors TrainingExample.weight (preference
  weighting was dropped — fit was called without sample_weight).
- Bug 8: _routing_decisions mutations are thread-safe (stash_decision /
  consume_decision under a lock); concurrent stashes don't crash or lose data.
- Bug 9: load_feedback_from_db EMA replay uses per-metric bias correction
  (post-restart EMA matches the live EMA for the same data).
- Bug 11: a sub-1s max_latency_ms no longer adds a hard FAST_RESPONSE capability
  gate that empties the candidate set; _filter_by_latency does the work.
"""
import asyncio
import threading

import pytest
from unittest.mock import MagicMock

from core.learning_llm_router import (
    LearningBasedRouter,
    ModelSpec,
    RoutingRequest,
    RoutingFeedback,
    ModelCapability,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def router(mock_db):
    r = LearningBasedRouter(db=mock_db)
    r._model_registry = {
        "fast-model": ModelSpec(
            model_id="fast-model",
            provider="openai",
            model_name="fast-model",
            capabilities={ModelCapability.CODE_GENERATION, ModelCapability.FAST_RESPONSE},
            cost_per_million=2.0,
            quality_score=0.7,
            speed_score=0.95,  # ~105ms estimated
            context_window=8192,
            supports_cache=True,
            tier="standard",
        ),
        "slow-premium": ModelSpec(
            model_id="slow-premium",
            provider="openai",
            model_name="slow-premium",
            # NOTE: deliberately NOT FAST_RESPONSE — the old hard gate would
            # have dropped it for any sub-1s budget.
            capabilities={ModelCapability.CODE_GENERATION, ModelCapability.HIGH_QUALITY},
            cost_per_million=10.0,
            quality_score=0.95,
            speed_score=0.6,  # ~167ms estimated — still within a 200ms budget
            context_window=8192,
            supports_cache=True,
            tier="premium",
        ),
    }
    return r


# --------------------------------------------------------------------------
# Bug 11: latency filter is soft (speed-score), not a hard capability gate
# --------------------------------------------------------------------------

def test_sub_second_latency_budget_keeps_non_fast_models(router):
    """max_latency_ms < 1000 must not drop non-FAST_RESPONSE models.

    The old code added a FAST_RESPONSE capability requirement in
    _filter_by_capabilities whenever max_latency_ms < 1000, which ran BEFORE
    _filter_by_latency and removed slow-premium (no FAST_RESPONSE) even though
    its speed_score (0.6 -> ~167ms) satisfies a 200ms budget.
    """
    req = RoutingRequest(
        tenant_id="t1",
        task_type="code_generation",
        estimated_tokens=100,
        requires_quality=False,  # don't require HIGH_QUALITY — tests latency gate only
        max_latency_ms=200,  # < 1000, used to trigger the hard gate
    )
    candidates = router._filter_by_capabilities(req)
    ids = {c.model_id for c in candidates}
    # Both models survive the capability filter; the latency filter (below)
    # is the one that decides based on speed_score.
    assert "slow-premium" in ids, "non-FAST model wrongly dropped by latency budget"
    assert "fast-model" in ids

    # _filter_by_latency then keeps both (both estimate under 200ms).
    latency_filtered = router._filter_by_latency(candidates, 200)
    assert {c.model_id for c in latency_filtered} == {"fast-model", "slow-premium"}


def test_latency_filter_still_drops_too_slow_models(router):
    """A genuinely too-slow model is still dropped by the speed-score filter."""
    candidates = list(router._model_registry.values())
    # 100ms budget: fast-model (~105ms) drops, slow-premium (~167ms) drops.
    kept = router._filter_by_latency(candidates, 100)
    # fast-model at 0.95 -> 105ms > 100ms, so even it drops here.
    assert "slow-premium" not in {c.model_id for c in kept}


# --------------------------------------------------------------------------
# Bug 1: PerModelRouter.train honors sample weights
# --------------------------------------------------------------------------

def test_per_model_train_honors_sample_weight(tmp_path):
    """A high-weight negative example must shift the predictor toward 'bad'.

    Two training sets with identical features/labels but DIFFERENT weight
    distributions must produce different predictions — proving sample_weight is
    actually passed to fit (previously it was dropped, so both sets gave the
    same result).
    """
    from core.llm.routing import (
        PerModelRouter, TrainingConfig, ModelType, TrainingExample,
    )
    import math

    cfg = lambda: TrainingConfig(
        model_type=ModelType.RANDOM_FOREST,
        model_path=str(tmp_path / "models"),
        n_estimators=25, max_depth=4, random_seed=7,
    )

    def ex(satisfied, weight):
        return TrainingExample(
            estimated_tokens=800, task_type="code_generation",
            prompt_features={
                "log_tokens": math.log2(801), "token_bucket": 1.0,
                "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
                "task_chat": 0.0, "task_general": 0.0, "has_code": 1.0,
                "has_numbers": 0.0, "avg_word_length": 5.0,
            },
            user_satisfaction=(0.9 if satisfied else 0.1),
            weight=weight,
        )

    feats = {
        "log_tokens": math.log2(801), "token_bucket": 1.0,
        "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
        "task_chat": 0.0, "task_general": 0.0, "has_code": 1.0,
        "has_numbers": 0.0, "avg_word_length": 5.0,
    }

    # Set A: 4 satisfied (weight 1) + 1 unsatisfied (weight 1) -> mostly good.
    pmr_a = PerModelRouter(cfg())
    pmr_a.train("m1", [ex(True, 1.0)] * 4 + [ex(False, 1.0)])

    # Set B: 4 satisfied (weight 1) + 1 unsatisfied (weight 50) -> the single
    # bad example dominates, so the predictor should lean more negative.
    pmr_b = PerModelRouter(cfg())
    pmr_b.train("m1", [ex(True, 1.0)] * 4 + [ex(False, 50.0)])

    pred_a = pmr_a.predict_satisfaction("m1", feats)
    pred_b = pmr_b.predict_satisfaction("m1", feats)
    assert pred_a is not None and pred_b is not None
    # The heavily-weighted negative set must predict LOWER satisfaction.
    assert pred_b < pred_a, (
        f"sample_weight appears ignored: pred_a={pred_a}, pred_b={pred_b}")


# --------------------------------------------------------------------------
# Bug 8: thread-safe _routing_decisions stash/consume
# --------------------------------------------------------------------------

def test_stash_and_consume_decision_roundtrip(router):
    """stash_decision returns an id that consume_decision resolves."""
    feats = {"log_tokens": 6.0, "has_code": 1.0}
    did = router.stash_decision(feats)
    assert router.consume_decision(did) == feats


def test_consume_decision_returns_none_for_unknown_id(router):
    assert router.consume_decision("does-not-exist") is None


def test_concurrent_stashes_do_not_lose_data(router):
    """Many threads stashing concurrently must all land (no lost updates)."""
    N = 200
    results = []
    barrier = threading.Barrier(N)

    def stash(i):
        barrier.wait()
        did = router.stash_decision({"idx": float(i)})
        results.append(did)

    threads = [threading.Thread(target=stash, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every id must be present and resolve to its stashed features.
    assert len(results) == N
    assert len(set(results)) == N, "duplicate ids generated under concurrency"
    for did in results:
        assert router.consume_decision(did) is not None


def test_stash_decision_respects_cap(router):
    """Eviction under the cap must not crash under concurrent stashes."""
    router._max_routing_decisions = 50
    # Stash well over the cap from many threads; must not raise and must stay
    # within the cap (eviction is FIFO under the lock).
    N = 300

    def stash(i):
        router.stash_decision({"i": float(i)})

    threads = [threading.Thread(target=stash, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(router._routing_decisions) <= router._max_routing_decisions


# --------------------------------------------------------------------------
# Bug 9: load_feedback_from_db EMA replay uses per-metric bias correction
# --------------------------------------------------------------------------

def test_ema_replay_matches_live_update(monkeypatch, tmp_path):
    """Replaying history must yield the same EMA as updating it live.

    This locks in the Bug 7/9 fix: per-metric bias correction applied
    identically whether the data arrives live or via restart hydration.
    """
    import core.learning_llm_router as llr
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from contextlib import contextmanager
    from core.models import LLMRoutingFeedback

    engine = create_engine(f"sqlite:///{tmp_path / 'ema.db'}")
    LLMRoutingFeedback.__table__.create(engine, checkfirst=True)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_get_db_session():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(llr, "get_db_session", test_get_db_session)

    # Insert rows directly with EXPLICIT, distinct created_at. _persist_feedback
    # relies on the column's server default for created_at, so a tight insert
    # loop would tie timestamps and make load_feedback_from_db's oldest-first
    # replay order non-deterministic. Inserting directly mirrors what a real
    # spaced-out feedback stream looks like and makes the replay deterministic.
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seq = [
        # (success, quality_satisfied, latency, cost, created_at offset seconds)
        (True, True, 200.0, 0.001, 0),    # EMA success contribution = 1.0
        (True, False, 400.0, 0.001, 60),  # success AND quality_satisfied = False -> 0.0
        (False, False, 900.0, 0.002, 120),# -> 0.0
    ]
    with test_get_db_session() as db:
        for i, (succ, qs, lat, cost, off) in enumerate(seq):
            db.add(LLMRoutingFeedback(
                routing_result_id=f"r{i}",
                tenant_id="t1", model_id="gpt-4o", task_type="code_generation",
                success=succ, quality_satisfied=qs, cost_within_budget=True,
                user_satisfaction=0.5, actual_cost=cost, actual_latency_ms=lat,
                created_at=base + timedelta(seconds=off),
            ))

    # "Live" EMA: apply the same sequence directly (the in-memory path).
    live = llr.LearningBasedRouter(MagicMock())
    live._min_samples_per_model = 10_000_000
    for succ, qs, lat, cost, off in seq:
        live._update_ema_scores(llr.RoutingFeedback(
            "x", "t1", "gpt-4o", "code_generation", succ, qs, True, 0.5, cost, lat))

    # "Restarted" router: empty state, hydrate from DB (replays oldest-first).
    restarted = llr.LearningBasedRouter(MagicMock())
    restarted._min_samples_per_model = 10_000_000
    restarted.load_feedback_from_db()

    live_bucket = live._ema_scores["t1:code_generation:gpt-4o"]
    rest_bucket = restarted._ema_scores["t1:code_generation:gpt-4o"]
    for metric in ("success", "latency", "cost", "samples"):
        assert live_bucket[metric] == pytest.approx(rest_bucket[metric], rel=1e-9), (
            f"EMA {metric} diverges after replay: live={live_bucket[metric]} rest={rest_bucket[metric]}")

    # Sanity: success EMA must be a valid probability in [0,1] (the old
    # write-time bias correction produced values > 1.0).
    assert 0.0 <= live_bucket["success"] <= 1.0

    engine.dispose()

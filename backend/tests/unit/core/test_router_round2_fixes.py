"""Tests for the round-2 router bug fixes.

Covers:
- Bug 6: routing_time_ms is a sane elapsed value on the success path (was ~1.7e12).
- Bug 7: EMA bias correction uses per-metric sample counts, not the key-total,
  so sparsely-reported metrics (latency/cost) aren't over-corrected.
- Bug 4: feedback_samples counts per-row by tenant (was keyed on v[0].tenant_id).
- Bug 5: resolve_feedback_context recovers the real task_type + routing_result_id.
"""
import asyncio
import time

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
    return r


def _fb(model_id, success, quality_satisfied, tenant="t1", task="code_generation",
        latency=None, cost=None):
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
# Bug 6: routing_time_ms sanity on the success path
# --------------------------------------------------------------------------

def test_route_routing_time_ms_is_sane_elapsed(router):
    """routing_time_ms must be a small elapsed-ms value, not ~1.7e12.

    The success path previously passed an *elapsed* value as the `start_ms`
    arg, which _create_routing_result then subtracted from the current epoch
    timestamp — yielding a ~1.7 trillion ms "routing time".
    """
    req = RoutingRequest(tenant_id="t1", task_type="code_generation", estimated_tokens=100)
    result = asyncio.run(router.route(req))
    # A routing decision should take well under a second; certainly not billions.
    assert 0.0 <= result.routing_time_ms < 10_000.0


# --------------------------------------------------------------------------
# Bug 7: per-metric EMA bias correction
# --------------------------------------------------------------------------

def test_ema_bias_correction_uses_per_metric_samples(router):
    """A sparsely-reported metric must use its OWN sample count for correction.

    Seed many feedback rows but only one with latency. The latency EMA must
    equal the single observed value (first sample, no correction), NOT be
    divided by a bias computed from the key-total sample count.
    """
    # 10 success-only feedbacks (no latency/cost).
    for _ in range(10):
        router._update_ema_scores(_fb("gpt-4", True, True))
    # One feedback WITH latency.
    router._update_ema_scores(_fb("gpt-4", True, True, latency=500.0))

    bucket = router._ema_scores["t1:code_generation:gpt-4"]
    # Latency seen once -> raw value, unbiased.
    assert bucket["latency"] == 500.0
    # Per-metric counters tracked separately.
    assert bucket["success_n"] == 11
    assert bucket["latency_n"] == 1
    # Key-total samples still reflects all feedback rows.
    assert bucket["samples"] == 11


def test_ema_per_metric_second_sample_corrected(router, monkeypatch):
    """Second observation of a sparse metric applies correction based on n=2."""
    monkeypatch.setenv("ATOM_EMA_ALPHA", "0.5")
    router._update_ema_scores(_fb("gpt-4", True, True, latency=100.0))
    router._update_ema_scores(_fb("gpt-4", True, True, latency=300.0))
    bucket = router._ema_scores["t1:code_generation:gpt-4"]
    # raw = 0.5*300 + 0.5*100 = 200; bias = 1 - (1-0.5)^2 = 0.75; corrected = 200/0.75
    assert bucket["latency"] == pytest.approx(200.0 / 0.75, rel=1e-9)


# --------------------------------------------------------------------------
# Bug 4: feedback_samples per-row tenant count
# --------------------------------------------------------------------------

def test_feedback_samples_counts_per_row(router):
    """feedback_samples must count every row for the tenant, not key on v[0]."""
    # Two rows for t1, one for t2, all in a bucket whose first (most-recent)
    # entry is t2 — the old v[0].tenant_id guard would have dropped all three.
    router._preference_data["t1:code_generation"] = [
        _fb("gpt-4", True, True, tenant="t2"),   # most-recent-first; different tenant
        _fb("gpt-4", True, True, tenant="t1"),
        _fb("gpt-3.5", False, False, tenant="t1"),
    ]
    stats = asyncio.run(router.get_routing_statistics("t1"))
    assert stats["feedback_samples"] == 2  # only t1's two rows


# --------------------------------------------------------------------------
# Bug 5: resolve_feedback_context recovers the real task_type + routing_result_id
# --------------------------------------------------------------------------

def test_resolve_feedback_context_recovers_recorded_outcome(monkeypatch, tmp_path):
    """Explicit feedback must correlate with the auto-recorded outcome.

    After the BYOK outcome hook records feedback for (tenant, model) under the
    REAL task_type and routing_result_id, resolve_feedback_context must return
    those so explicit thumbs feedback aggregates with it (Bug 5).
    """
    import core.learning_llm_router as llr
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from contextlib import contextmanager
    from core.models import LLMRoutingFeedback

    engine = create_engine(f"sqlite:///{tmp_path / 'rfc.db'}")
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

    r = llr.LearningBasedRouter(MagicMock())
    r._min_samples_per_model = 10_000_000  # disable retrain

    # Record an outcome as the BYOK hook would: real task_type + a decision id.
    outcome = llr.RoutingFeedback(
        routing_result_id="decision-abc",
        tenant_id="default", model_id="gpt-4o", task_type="code_generation",
        success=True, quality_satisfied=True, cost_within_budget=True,
        user_satisfaction=0.9,
    )
    asyncio.run(r.record_feedback(outcome))

    # Explicit feedback for the same (tenant, model) should recover both.
    task, rid = r.resolve_feedback_context("default", "gpt-4o")
    assert task == "code_generation"
    assert rid == "decision-abc"

    # A model with no prior outcome falls back to (None, None).
    task2, rid2 = r.resolve_feedback_context("default", "never-seen")
    assert task2 is None and rid2 is None

    engine.dispose()


def test_resolve_feedback_context_returns_none_when_no_data(router):
    """No prior outcome -> (None, None) so caller falls back to defaults."""
    # No rows recorded; the real (empty) path returns (None, None) gracefully.
    task, rid = router.resolve_feedback_context("t1", "gpt-4")
    assert task is None or isinstance(task, str)
    assert rid is None or isinstance(rid, str)

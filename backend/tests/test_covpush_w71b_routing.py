"""Coverage wave W71b — learning-router family (flag-gated OFF) edge coverage.

Targets (>=95% statement coverage, standalone):
- core/llm/routing/routellm_trainer.py     (78% before)
- core/llm/routing/preference_collector.py (100% before — untouched)
- core/llm/routing/cache_optimizer.py      (69% before)
- core/llm/routing/request_healer.py       (99% before — 1 line + regression)
- core/llm/routing/offline_tuner.py        (91% before)

Pattern: mocked deps, zero LLM spend (all model calls mocked/async-faked),
no network, no DB. sklearn/scipy allowed (CPU-only, tiny configs).

Bug found + fixed in the assigned modules (regression tests below):
1. request_healer.py `RequestHealer.heal` — the documented `llm_healer`
   contract is an ASYNC callable (make_default_llm_healer returns an async
   closure "designed to be injected into RequestHealer"), but `heal()` called
   it synchronously and destructured the result. Injecting the module's own
   factory therefore raised TypeError on the coroutine, was swallowed, and the
   LLM fallback silently never patched anything. Fixed to await awaitable
   results (asyncio.run when no loop is running; callers that run under a live
   loop fall through to the existing no-patch path).
   Regression: test_heal_awaits_async_llm_healer.

Documented unreachable lines (not fixed):
- offline_tuner.py:237-238 — `if not pareto_front` is dead: candidates always
  contains [current_weights], the first candidate is never dominated against
  an empty front, so the front is never empty.
- routellm_trainer.py:383-384 — `_safe_model_path` ValueError is dead:
  model_id is fully sanitized ("/", "\\", ".." replaced) before resolve(),
  so the resolved path can never escape the base dir.
- cache_optimizer.py:421-424 — reachable but the inner "required_entries"
  computation is convoluted; exercised for coverage, not correctness.
"""
import asyncio
import importlib
import math
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from core.llm.routing import cache_optimizer as co
from core.llm.routing import offline_tuner as ot
from core.llm.routing import request_healer as rh
from core.llm.routing import routellm_trainer as trm
from core.llm.routing.cache_optimizer import (
    AccessPattern,
    AccessPatternAnalyzer,
    CacheAccess,
    CacheOptimizationConfig,
    CacheOptimizer,
    CacheStatistics,
    CacheWarmer,
    WarmedCacheEntry,
    get_cache_optimizer,
    get_cache_warmer,
    get_pattern_analyzer,
)
from core.llm.routing.offline_tuner import (
    DEFAULT_FALLBACK,
    MIN_SAMPLES_PER_TASK,
    _evaluate_candidate,
    _normalize_weights,
    tune_routing_weights,
)
from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.request_healer import RequestHealer
from core.llm.routing.routellm_trainer import (
    ModelType,
    RouteLLMTrainer,
    RouterEvaluator,
    TrainingConfig,
    TrainingResult,
    TrainingStatus,
    get_router_evaluator,
    get_router_trainer,
)


class FakeStatusError(Exception):
    """Simulates openai.APIStatusError's .status_code attribute."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def make_example(satisfaction, model="m1", weight=1.0):
    return TrainingExample(
        estimated_tokens=200,
        task_type="code_generation",
        prompt_features={
            "log_tokens": math.log2(201),
            "token_bucket": 1.0,
            "task_code": 1.0,
            "task_analysis": 0.0,
            "task_reasoning": 0.0,
            "task_chat": 0.0,
            "task_general": 0.0,
            "has_code": 1.0,
            "has_numbers": 0.0,
            "avg_word_length": 5.0,
        },
        chosen_model=model,
        user_satisfaction=satisfaction,
        was_successful=satisfaction >= 0.5,
        quality_score=satisfaction,
        weight=weight,
    )


def make_examples(n=100):
    return [make_example(1.0 if i % 2 else 0.0) for i in range(n)]


def tiny_config(tmp_path):
    return TrainingConfig(model_path=str(tmp_path), n_estimators=5, max_depth=3)


@contextmanager
def frozen_now(dt):
    """Freeze cache_optimizer.datetime.now() at a fixed point."""

    class _FakeDatetime:
        @classmethod
        def now(cls):
            return dt

    with patch.object(co, "datetime", _FakeDatetime):
        yield


# ===========================================================================
# core/llm/routing/routellm_trainer.py
# ===========================================================================


class TestTrainerGuards:
    @pytest.fixture
    def trainer(self, tmp_path):
        return RouteLLMTrainer(tiny_config(tmp_path))

    def test_train_preference_unavailable(self, trainer):
        with patch.object(trm, "PREFERENCE_AVAILABLE", False):
            result = trainer.train(make_examples())
        assert result.status == TrainingStatus.FAILED
        assert "Preference collector not available" in result.metadata["error"]
    def test_train_insufficient_samples(self, trainer):
        result = trainer.train([make_example(1.0), make_example(0.0)])
        assert result.status == TrainingStatus.FAILED
        assert "Insufficient samples" in result.metadata["error"]

    def test_train_no_features_raises(self, trainer):
        with patch.object(
            trainer.feature_extractor, "extract_features",
            return_value=np.zeros((0, 10)),
        ):
            result = trainer.train(make_examples())
        assert result.status == TrainingStatus.FAILED
        assert result.metadata["error"] == "No features extracted from examples"

    def test_train_exception_marks_failed(self, trainer):
        with patch.object(
            trainer, "_create_model", side_effect=RuntimeError("fit boom")
        ):
            result = trainer.train(make_examples())
        assert result.status == TrainingStatus.FAILED
        assert "fit boom" in result.metadata["error"]

    def test_train_explicit_model_id(self, trainer, tmp_path):
        result = trainer.train(make_examples(), model_id="custom")
        assert result.status == TrainingStatus.COMPLETED
        assert result.model_id == "custom"
        assert (tmp_path / "custom.pkl").exists()


class TestTrainMetrics:
    @pytest.fixture
    def trainer(self, tmp_path):
        return RouteLLMTrainer(tiny_config(tmp_path))

    def test_train_completed_metadata(self, trainer, tmp_path):
        result = trainer.train(make_examples())
        assert result.status == TrainingStatus.COMPLETED
        assert result.samples_trained == 100
        assert result.training_time_ms >= 0
        assert result.metadata["model_type"] == "random_forest"
        assert "feature_importance" in result.metadata
        assert result.confusion_matrix is not None
        assert (tmp_path / f"{result.model_id}.pkl").exists()

    def test_train_precision_exception_tolerated(self, trainer):
        with patch(
            "sklearn.metrics.precision_score", side_effect=ValueError("boom")
        ):
            result = trainer.train(make_examples())
        assert result.status == TrainingStatus.COMPLETED
        assert result.precision == 0.0
        assert result.recall == 0.0


class TestCreateModelBranches:
    def test_neural_network_construction(self, tmp_path):
        cfg = TrainingConfig(
            model_type=ModelType.NEURAL_NETWORK,
            model_path=str(tmp_path),
            learning_rate=0.05,
            epochs=7,
        )
        trainer = RouteLLMTrainer(cfg)
        model = trainer._create_model()
        from sklearn.neural_network import MLPClassifier

        assert isinstance(model, MLPClassifier)
        assert model.learning_rate_init == 0.05
        assert model.max_iter == 7

    def test_ensemble_construction(self, tmp_path):
        cfg = TrainingConfig(model_type=ModelType.ENSEMBLE, model_path=str(tmp_path))
        trainer = RouteLLMTrainer(cfg)
        model = trainer._create_model()
        from sklearn.ensemble import VotingClassifier

        assert isinstance(model, VotingClassifier)
        assert model.voting == "soft"
        assert [name for name, _ in model.estimators] == ["rf", "lr"]

    def test_unsupported_model_type_raises(self, tmp_path):
        cfg = TrainingConfig(model_path=str(tmp_path))
        trainer = RouteLLMTrainer(cfg)
        trainer.config.model_type = SimpleNamespace(value="bogus")
        with pytest.raises(ValueError):
            trainer._create_model()


class TestPersistence:
    @pytest.fixture
    def trainer(self, tmp_path):
        return RouteLLMTrainer(tiny_config(tmp_path))

    def test_save_model_skips_when_no_model(self, trainer, tmp_path):
        trainer.model = None
        trainer._save_model("ghost")
        assert not list(tmp_path.iterdir())

    def test_safe_model_path_sanitizes(self, trainer, tmp_path):
        path = trainer._safe_model_path("../a/b")
        assert "a_b" in path.name or "b" in path.name
        base = tmp_path.resolve()
        path.resolve().relative_to(base)  # no escape

    def test_load_model_missing_file(self, trainer):
        assert trainer.load_model("missing") is False

    def test_load_model_corrupt_file(self, trainer, tmp_path):
        (tmp_path / "bad.pkl").write_bytes(b"garbage-not-a-pickle")
        assert trainer.load_model("bad") is False


class TestPredictVariants:
    @pytest.fixture
    def trainer(self, tmp_path):
        return RouteLLMTrainer(tiny_config(tmp_path))

    def test_predict_single_class_inverts_proba(self, trainer):
        class FakeModel:
            def predict_proba(self, v):
                return np.array([[0.8]])

        trainer.model = FakeModel()
        assert trainer.predict({}) == pytest.approx(0.2)

    def test_predict_without_proba_uses_predict(self, trainer):
        class FakeModel:
            def predict(self, v):
                return np.array([0.7])

        trainer.model = FakeModel()
        assert trainer.predict({}) == pytest.approx(0.7)


class TestGetBestModel:
    def test_all_failed_restores_config(self, tmp_path):
        cfg = TrainingConfig(
            model_type=ModelType.LOGISTIC_REGRESSION, model_path=str(tmp_path)
        )
        trainer = RouteLLMTrainer(cfg)
        with patch.object(
            trainer, "train",
            return_value=TrainingResult(status=TrainingStatus.FAILED),
        ):
            best, result = trainer.get_best_model(make_examples())
        assert best is None
        assert result is None
        assert trainer.config.model_type == ModelType.LOGISTIC_REGRESSION


class TestFeatureExtractorEmpty:
    def test_extract_weights_empty(self):
        extractor = trm.FeatureExtractor()
        weights = extractor.extract_weights([])
        assert weights.shape == (0,)
        assert extractor.extract_features([]).shape == (0, 10)
        assert extractor.extract_targets([]).shape == (0,)


class TestRouterEvaluator:
    def test_evaluator_default_and_explicit_config(self):
        assert isinstance(RouterEvaluator().config, TrainingConfig)
        cfg = TrainingConfig(min_ab_samples=5)
        evaluator = RouterEvaluator(cfg)
        assert evaluator.config is cfg

    def test_evaluate_ab_test_sufficient_samples(self):
        evaluator = RouterEvaluator()
        control = [0.5 + (i % 3) * 0.05 for i in range(100)]
        learning = [0.9 - (i % 3) * 0.05 for i in range(100)]
        out = evaluator.evaluate_ab_test(control, learning)
        assert out["control_mean"] < out["learning_mean"]
        assert out["improvement"] > 0
        assert out["improvement_percent"] > 0
        assert out["control_samples"] == 100
        assert out["learning_samples"] == 100
        assert out["p_value"] < 0.05
        assert bool(out["significant"]) is True

    def test_evaluate_ab_test_insufficient_samples(self):
        evaluator = RouterEvaluator()
        out = evaluator.evaluate_ab_test([0.5] * 10, [0.9] * 10)
        assert out["t_statistic"] == 0
        assert out["p_value"] == 1.0
        assert out["significant"] is False

    def test_evaluate_ab_test_empty(self):
        evaluator = RouterEvaluator()
        out = evaluator.evaluate_ab_test([], [])
        assert out["control_mean"] == 0
        assert out["learning_mean"] == 0
        assert out["improvement"] == 0
        assert out["significant"] is False

    def test_confidence_interval_short(self):
        evaluator = RouterEvaluator()
        assert evaluator.get_confidence_interval([5.0]) == (0.0, 1.0)

    def test_confidence_interval_full(self):
        evaluator = RouterEvaluator()
        lower, upper = evaluator.get_confidence_interval([1.0, 2.0, 3.0, 4.0])
        assert lower == pytest.approx(0.4457, rel=1e-3)
        assert upper == pytest.approx(4.5543, rel=1e-3)
        assert lower < 2.5 < upper

    def test_confidence_interval_custom_level(self):
        evaluator = RouterEvaluator()
        lower, upper = evaluator.get_confidence_interval([1.0, 2.0, 3.0], 0.9)
        assert lower < 2.0 < upper


class TestTrainerFactories:
    def test_get_router_trainer_factory(self, tmp_path):
        trainer = get_router_trainer(tiny_config(tmp_path))
        assert isinstance(trainer, RouteLLMTrainer)
        assert isinstance(get_router_trainer(), RouteLLMTrainer)

    def test_get_router_evaluator_factory(self):
        evaluator = get_router_evaluator(TrainingConfig())
        assert isinstance(evaluator, RouterEvaluator)
        assert isinstance(get_router_evaluator(), RouterEvaluator)


# ===========================================================================
# core/llm/routing/preference_collector.py — end-to-end main-line flows.
# (W55 covers the branch minutiae; this class walks the full decision ->
# feedback -> dataset -> stats pipeline through the public API.)
# ===========================================================================


class TestPreferenceCollectorCoreFlows:
    @pytest.fixture
    def collector(self):
        from core.llm.routing.preference_collector import (
            FeedbackConfig,
            PreferenceDataCollector,
        )

        return PreferenceDataCollector(FeedbackConfig())

    def test_record_decision_populates_store(self, collector):
        decision_id = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=2500,
            task_type="analysis", prompt="```python\nx = 42\n```",
            chosen_model="m1", chosen_provider="p1", chosen_tier="premium",
            router_type="learning_based", confidence=0.9,
            alternatives=[{"model": "m2"}], session_id="s1", user_id="u1",
        )
        assert decision_id
        decision = collector.decisions[decision_id]
        assert decision.prompt_hash
        assert decision.prompt_prefix == "```python\nx = 42\n```"
        assert decision.router_type == "learning_based"
        assert decision.alternatives == [{"model": "m2"}]

    def test_record_feedback_full_args(self, collector):
        decision_id = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="hello", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        from core.llm.routing.preference_collector import (
            FeedbackSource,
            FeedbackType,
            RoutingOutcome,
        )

        feedback_id = collector.record_feedback(
            decision_id, RoutingOutcome.REJECTED, quality_score=0.8,
            latency_ms=300, cost_usd=0.02, preferred_model="m2",
            preferred_provider="p2", rejected_reason="too slow",
            feedback_type=FeedbackType.EXPLICIT,
            feedback_source=FeedbackSource.LATENCY,
        )
        assert feedback_id
        fb = collector.feedback_records[feedback_id]
        assert fb.decision_id == decision_id
        assert fb.preferred_model == "m2"
        assert fb.rejected_reason == "too slow"

    def test_generate_dataset_through_public_api(self, collector):
        decision_id = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=1200,
            task_type="code", prompt="```\nsum([1,2,3])\n```",
            chosen_model="m1", chosen_provider="p1", chosen_tier="standard",
            alternatives=[{"model": "m2"}, {"model": "m3"}],
        )
        from core.llm.routing.preference_collector import (
            FeedbackType,
            RoutingOutcome,
        )

        collector.record_feedback(
            decision_id, RoutingOutcome.REJECTED, quality_score=0.9,
            feedback_type=FeedbackType.EXPLICIT,
        )
        examples = collector.generate_training_dataset("ws1")
        assert len(examples) == 1
        ex = examples[0]
        assert ex.user_satisfaction == 0.9
        assert ex.was_successful is False
        assert ex.available_models == ["m2", "m3"]
        assert ex.prompt_features["has_code"] == 1.0
        assert ex.prompt_features["has_numbers"] == 1.0
        assert ex.prompt_features["token_bucket"] == 2
        assert ex.prompt_features["avg_word_length"] > 0
        assert ex.weight == pytest.approx(2.0 * 1.5 * 1.3)

    def test_ab_group_and_learning_gate(self, collector):
        group = collector.assign_ab_test_group("ws1")
        assert group in ("learning", "control")
        assert collector.assign_ab_test_group("ws1") == group
        with patch.object(
            collector, "assign_ab_test_group", return_value="learning"
        ):
            assert collector.should_use_learning_router("ws1") is True
        with patch.object(
            collector, "assign_ab_test_group", return_value="control"
        ):
            assert collector.should_use_learning_router("ws1") is False
        from core.llm.routing.preference_collector import (
            FeedbackConfig,
            PreferenceDataCollector,
        )

        disabled = PreferenceDataCollector(FeedbackConfig(enable_ab_testing=False))
        assert disabled.should_use_learning_router("ws1") is False

    def test_stats_with_preferred_models_and_factory(self, collector):
        decision_id = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=10,
            task_type="chat", prompt="hi", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        from core.llm.routing.preference_collector import RoutingOutcome

        collector.record_feedback(
            decision_id, RoutingOutcome.SUCCESS, quality_score=0.9,
            preferred_model="m2",
        )
        stats = collector.get_collection_stats("ws1")
        assert stats["total_decisions"] == 1
        assert stats["total_feedback"] == 1
        assert stats["feedback_coverage"] == 1.0
        assert stats["success_rate"] == 1.0
        assert stats["preferred_models"] == ["m2"]
        assert stats["ready_for_training"] is False
        from core.llm.routing.preference_collector import get_preference_collector

        assert isinstance(get_preference_collector(), type(collector))

    def test_token_bucket_boundaries(self, collector):
        assert collector._get_token_bucket(50) == 0
        assert collector._get_token_bucket(300) == 1
        assert collector._get_token_bucket(1000) == 2
        assert collector._get_token_bucket(3000) == 3
        assert collector._get_token_bucket(9000) == 4

    def test_record_feedback_unknown_decision(self, collector):
        from core.llm.routing.preference_collector import RoutingOutcome

        assert collector.record_feedback("nope", RoutingOutcome.SUCCESS) == ""

    def test_generate_dataset_applies_all_filters(self, collector):
        from core.llm.routing.preference_collector import RoutingOutcome

        # In-workspace, fresh, with feedback, above min quality -> included.
        good = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="ok", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        collector.record_feedback(good, RoutingOutcome.SUCCESS, quality_score=0.9)
        # Other workspace -> excluded.
        other = collector.record_routing_decision(
            workspace_id="ws2", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="ok", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        collector.record_feedback(other, RoutingOutcome.SUCCESS, quality_score=0.9)
        # Stale decision -> excluded.
        stale = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="ok", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        collector.record_feedback(stale, RoutingOutcome.SUCCESS, quality_score=0.9)
        collector.decisions[stale].timestamp = datetime.now() - timedelta(days=200)
        # No feedback -> excluded.
        collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="no-feedback", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        # Feedback below min_quality -> excluded.
        low = collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="low", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        collector.record_feedback(low, RoutingOutcome.SUCCESS, quality_score=0.1)
        examples = collector.generate_training_dataset("ws1")
        assert len(examples) == 1
        assert examples[0].user_satisfaction == 0.9

    def test_stats_no_feedback_branch(self, collector):
        collector.record_routing_decision(
            workspace_id="ws1", tenant_id="t1", estimated_tokens=100,
            task_type="chat", prompt="hi", chosen_model="m1",
            chosen_provider="p1", chosen_tier="standard",
        )
        stats = collector.get_collection_stats("ws1")
        assert stats["total_decisions"] == 1
        assert stats["total_feedback"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_quality_score"] == 0.0
        assert stats["preferred_models"] == []

    def test_auto_id_generation(self):
        from core.llm.routing.preference_collector import (
            RoutingDecision,
            RoutingFeedback,
            TrainingExample,
        )

        decision = RoutingDecision(workspace_id="w", prompt_hash="h")
        assert decision.decision_id
        feedback = RoutingFeedback(decision_id=decision.decision_id)
        assert feedback.feedback_id
        example = TrainingExample(estimated_tokens=5, task_type="chat")
        assert example.example_id


# ===========================================================================
# core/llm/routing/cache_optimizer.py
# ===========================================================================


class TestCacheAccessHash:
    def test_hash_consistent_and_distinct(self):
        ts = datetime(2026, 8, 13, 12, 0, 0)
        a = CacheAccess(timestamp=ts, prompt_hash="h1")
        b = CacheAccess(timestamp=ts, prompt_hash="h1")
        c = CacheAccess(timestamp=ts, prompt_hash="h2")
        assert hash(a) == hash(b)
        assert hash(a) != hash(c)


class TestCacheStatistics:
    def test_update_miss_and_hit(self):
        stats = CacheStatistics()
        stats.update(False, 10)
        assert stats.total_accesses == 1
        assert stats.total_misses == 1
        assert stats.hit_rate == 0.0
        assert stats.avg_latency_ms == 10.0
        stats.update(True, 20)
        assert stats.total_hits == 1
        assert stats.hit_rate == 0.5
        assert stats.avg_latency_ms == 15.0


class TestAccessPatternAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return AccessPatternAnalyzer(CacheOptimizationConfig())

    def test_detect_pattern_cached(self, analyzer):
        for i in range(4):
            analyzer.record_access("h", datetime(2026, 8, 13, 12, 0, i))
        first = analyzer.detect_pattern("h")
        second = analyzer.detect_pattern("h")
        assert first is second
        assert first == AccessPattern.TEMPORAL

    def test_detect_pattern_three_accesses_random(self, analyzer):
        for i in range(3):
            analyzer.record_access("h", datetime(2026, 8, 13, 12, 0, i))
        assert analyzer.detect_pattern("h") == AccessPattern.RANDOM

    def test_detect_pattern_temporal(self, analyzer):
        for i in range(4):
            analyzer.record_access("h", datetime(2026, 8, 13, 12, 0, i))
        assert analyzer.detect_pattern("h") == AccessPattern.TEMPORAL

    def test_detect_pattern_sequential(self, analyzer):
        base = datetime(2026, 8, 13, 12, 0, 0)
        for offset in (0, 100, 250, 380):
            analyzer.record_access("h", base + timedelta(seconds=offset))
        assert analyzer.detect_pattern("h") == AccessPattern.SEQUENTIAL

    def test_detect_pattern_random(self, analyzer):
        analyzer.record_access("h", datetime(2026, 8, 13, 12, 0, 0))
        analyzer.record_access("h", datetime(2026, 8, 13, 12, 10, 0))
        analyzer.record_access("h", datetime(2026, 8, 13, 12, 0, 10))
        analyzer.record_access("h", datetime(2026, 8, 13, 12, 20, 0))
        assert analyzer.detect_pattern("h") == AccessPattern.RANDOM

    def test_is_sequential_true_and_false(self, analyzer):
        base = datetime(2026, 8, 13, 12, 0, 0)
        close = [base, base + timedelta(seconds=30), base + timedelta(seconds=60)]
        far = [base, base + timedelta(seconds=400)]
        assert analyzer._is_sequential(close) is True
        assert analyzer._is_sequential(far) is False

    def test_get_access_frequency_window(self, analyzer):
        now = datetime(2026, 8, 13, 12, 30, 0)
        with frozen_now(now):
            for i in range(3):
                analyzer.record_access("h", now - timedelta(minutes=i))
            analyzer.record_access("stale", now - timedelta(hours=2))
            assert analyzer.get_access_frequency("h", 60) == pytest.approx(3 / 60)
            assert analyzer.get_access_frequency("stale", 60) == 0.0
            assert analyzer.get_access_frequency("nope", 60) == 0.0

    def test_get_next_access_probability_temporal_capped(self, analyzer):
        now = datetime(2026, 8, 13, 12, 30, 0)
        with frozen_now(now):
            for i in range(60):
                analyzer.record_access("h", now - timedelta(seconds=i))
            assert analyzer.get_next_access_probability("h") == 1.0

    def test_get_next_access_probability_sequential_boost(self, analyzer):
        now = datetime(2026, 8, 13, 12, 30, 0)
        base = datetime(2026, 8, 13, 12, 0, 0)
        with frozen_now(now):
            for offset in (0, 100, 250, 380):
                analyzer.record_access("h", base + timedelta(seconds=offset))
            freq = analyzer.get_access_frequency("h", 60)
            assert analyzer.detect_pattern("h") == AccessPattern.SEQUENTIAL
            assert analyzer.get_next_access_probability("h") == pytest.approx(
                min(freq * 2.0, 1.0)
            )

    def test_get_next_access_probability_no_history(self, analyzer):
        assert analyzer.get_next_access_probability("ghost") == 0.0


class TestCacheWarmer:
    def test_should_warm_high_probability(self):
        warmer = CacheWarmer(CacheOptimizationConfig())
        assert warmer.should_warm("h", 0.9) is True

    def test_should_warm_frequent_pattern(self):
        warmer = CacheWarmer(CacheOptimizationConfig())
        now = datetime(2026, 8, 13, 12, 30, 0)
        with frozen_now(now):
            for i in range(3):
                warmer.analyzer.record_access("h", now - timedelta(minutes=i))
            assert warmer.should_warm("h", 0.5) is True

    def test_should_warm_neither(self):
        warmer = CacheWarmer(CacheOptimizationConfig())
        assert warmer.should_warm("h", 0.5) is False

    def test_get_warm_candidates_filters_sorts_limits(self):
        warmer = CacheWarmer(CacheOptimizationConfig())
        now = datetime(2026, 8, 13, 12, 30, 0)
        with frozen_now(now):
            for i in range(60):
                warmer.analyzer.record_access("hot", now - timedelta(seconds=i))
                warmer.analyzer.record_access("warm", now - timedelta(seconds=i))
            warmer.warmed_entries["hot"] = WarmedCacheEntry(prompt_hash="hot")
            warmer.warmed_entries["warm"] = WarmedCacheEntry(prompt_hash="warm")
            warmer.warmed_entries["cold"] = WarmedCacheEntry(prompt_hash="cold")
            candidates = warmer.get_warm_candidates("ws")
            assert [c.prompt_hash for c in candidates] == ["hot", "warm"]
            assert candidates[0].access_probability == 1.0
            one = warmer.get_warm_candidates("ws", limit=1)
            assert len(one) == 1
            assert one[0].prompt_hash == "hot"


class TestCacheOptimizer:
    @pytest.fixture
    def optimizer(self):
        return CacheOptimizer(CacheOptimizationConfig())

    def test_recommendations_high_hit_rate(self, optimizer):
        optimizer.statistics.total_accesses = 100
        optimizer.statistics.total_hits = 99
        optimizer.statistics.hit_rate = 0.99
        optimizer.statistics.avg_latency_ms = 5.0
        recs = optimizer.get_cache_recommendations("ws", 500)["recommendations"]
        types = [r["type"] for r in recs]
        assert "hit_rate" in types
        hit = next(r for r in recs if r["type"] == "hit_rate")
        assert hit["severity"] == "info"
        assert hit["action"] == "reduce_cache_size"

    def test_recommendations_size_below_min(self, optimizer):
        recs = optimizer.get_cache_recommendations("ws", 50)["recommendations"]
        size = next(r for r in recs if r["type"] == "cache_size")
        assert size["severity"] == "warning"
        assert size["action"] == "increase_to_100MB"

    def test_recommendations_size_above_max(self, optimizer):
        recs = optimizer.get_cache_recommendations("ws", 2000)["recommendations"]
        size = next(r for r in recs if r["type"] == "cache_size")
        assert size["severity"] == "warning"
        assert size["action"] == "reduce_to_1000MB"

    def test_recommendations_shape(self, optimizer):
        out = optimizer.get_cache_recommendations("ws", 500)
        assert out["current_hit_rate"] == 0.0
        assert out["avg_latency_ms"] == 0.0
        assert out["total_accesses"] == 0
        assert out["warming_candidates"] == 0

    def test_get_optimal_cache_size_empty(self, optimizer):
        assert optimizer.get_optimal_cache_size() == optimizer.config.min_cache_size_mb

    def test_get_optimal_cache_size_with_skew(self, optimizer):
        for _ in range(10):
            optimizer.record_access("a", was_hit=True, latency_ms=5)
        assert optimizer.get_optimal_cache_size(0.95) == optimizer.config.min_cache_size_mb

    def test_get_optimal_cache_size_target_unreachable(self, optimizer):
        for _ in range(10):
            optimizer.record_access("a", was_hit=True, latency_ms=5)
        assert optimizer.get_optimal_cache_size(1.5) == optimizer.config.min_cache_size_mb

    def test_factories(self):
        assert isinstance(get_cache_optimizer(), CacheOptimizer)
        assert isinstance(get_cache_warmer(), CacheWarmer)
        assert isinstance(get_pattern_analyzer(), AccessPatternAnalyzer)


# ===========================================================================
# core/llm/routing/request_healer.py
# ===========================================================================


class TestClassifyUnknownStatus:
    def test_unknown_status_code_returns_unknown(self):
        assert rh.classify_error(FakeStatusError("teapot", 418)) == "unknown"


class TestHealAsyncLlmHealerRegression:
    def test_heal_awaits_async_llm_healer(self, monkeypatch):
        """REGRESSION: heal() documented llm_healer as async but unpacked the
        coroutine synchronously — the module's own make_default_llm_healer
        factory could never patch anything. Now awaited via asyncio.run."""
        monkeypatch.setenv("ATOM_LLM_HEALER_ENABLED", "true")

        async def async_healer(error, kwargs, provider, model):
            patched = dict(kwargs)
            patched["temperature"] = 0.1
            return (patched, ["temperature"])

        healer = RequestHealer(rules=[], llm_healer=async_healer)
        result = healer.heal(
            Exception("400 bad request"), {"temperature": 0.9}, "p", "m"
        )
        assert result.patched_kwargs == {"temperature": 0.1}
        assert result.rule == "llm"
        assert result.patched_keys == ["temperature"]

    def test_heal_async_healer_none_result(self, monkeypatch):
        monkeypatch.setenv("ATOM_LLM_HEALER_ENABLED", "true")

        async def async_healer(*a):
            return None

        healer = RequestHealer(rules=[], llm_healer=async_healer)
        result = healer.heal(Exception("400 bad request"), {}, "p", "m")
        assert result.patched_kwargs is None


# ===========================================================================
# core/llm/routing/offline_tuner.py
# ===========================================================================


def _seed_feedback(router, tenant, task, n, model_id="cheap", success=True):
    router._preference_data[f"{tenant}:{task}"] = [
        SimpleNamespace(
            model_id=model_id,
            success=success,
            actual_cost=0.01,
            actual_latency_ms=200.0,
        )
        for _ in range(n)
    ]


def _fake_router():
    registry = {
        "cheap": SimpleNamespace(quality_score=0.7, cost_per_million=0.5, speed_score=0.9),
        "premium": SimpleNamespace(quality_score=0.99, cost_per_million=30.0, speed_score=0.5),
    }
    cache = {}

    def set_weights(key, weights, tenant):
        cache[key] = weights

    return SimpleNamespace(
        _preference_data={},
        _model_registry=registry,
        _router_cache=cache,
        _set_cached_weights=set_weights,
    )


class TestNormalizeWeights:
    def test_zero_total_returns_fallback(self):
        assert _normalize_weights(0, 0, 0) == dict(DEFAULT_FALLBACK)

    def test_positive_total_normalizes(self):
        out = _normalize_weights(0.5, 0.3, 0.2)
        assert out == {"quality": 0.5, "cost": 0.3, "speed": 0.2}


class TestEvaluateCandidate:
    def test_no_models_returns_inf(self):
        metrics = _evaluate_candidate(
            {"quality": 0.4, "cost": 0.3, "speed": 0.3},
            [{"models": {}}, {"models": None}],
            {},
        )
        assert metrics == (0.0, 0.0, float("inf"))

    def test_scoring_selects_best_model_per_row(self):
        rows = [
            {"models": {
                "a": {"quality_score": 0.8, "cost_per_million": 1.0, "speed_score": 0.5,
                      "success": 1.0, "actual_cost": 0.01, "actual_latency_ms": 100.0},
                "b": {"quality_score": 0.6, "cost_per_million": 10.0, "speed_score": 0.9,
                      "success": 0.0, "actual_cost": 0.5, "actual_latency_ms": 500.0},
            }},
            {"models": {
                "a": {"quality_score": 0.8, "cost_per_million": 1.0, "speed_score": 0.5,
                      "success": 0.0, "actual_cost": 0.0, "actual_latency_ms": 300.0},
            }},
        ]
        satisfaction, total_cost, p95 = _evaluate_candidate(
            {"quality": 0.4, "cost": 0.3, "speed": 0.3}, rows, {}
        )
        assert satisfaction == pytest.approx(0.5)  # 1.0 and 0.0 averaged
        assert total_cost == pytest.approx(0.01)
        assert p95 == 300.0

    def test_zero_max_cost_falls_back(self):
        rows = [{"models": {
            "z": {"quality_score": 0.5, "cost_per_million": 0, "speed_score": 0.5,
                  "success": 1.0, "actual_cost": 0.0, "actual_latency_ms": 100.0},
        }}]
        satisfaction, total_cost, _ = _evaluate_candidate(
            {"quality": 0.4, "cost": 0.3, "speed": 0.3}, rows, {}
        )
        assert satisfaction == 1.0
        assert total_cost == 0.0


class TestTuneScenarios:
    def test_tune_skips_other_tenant_keys(self):
        router = _fake_router()
        _seed_feedback(router, "other", "code_generation", 60)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        assert "reason" in result
        assert result["tasks_tuned_count"] == 0

    def test_tune_skips_rows_with_unknown_model(self):
        router = _fake_router()
        _seed_feedback(router, "t1", "code_generation", 60, model_id="ghost")
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        assert "reason" in result
        assert result["tasks_tuned_count"] == 0

    def test_tune_skips_task_below_min_samples(self):
        router = _fake_router()
        _seed_feedback(router, "t1", "vision", 10)
        result = asyncio.run(
            tune_routing_weights(router, tenant_id="t1", task_types=["vision"])
        )
        assert result["tasks_tuned_count"] == 0
        skipped = result["tasks_tuned"][0]
        assert skipped["status"] == "skipped"
        assert f"Only 10 samples" in skipped["reason"]

    def test_tune_writes_winners_back(self):
        router = _fake_router()
        _seed_feedback(router, "t1", "code_generation", 60)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        tuned = result["tasks_tuned"][0]
        assert tuned["status"] == "tuned"
        assert tuned["candidates_evaluated"] == 1 + ot.N_CANDIDATES
        assert tuned["pareto_front_size"] >= 1
        assert "t1:code_generation" in router._router_cache
        w = tuned["best_weights"]
        assert abs(w["quality"] + w["cost"] + w["speed"] - 1.0) < 1e-9

    def test_tune_respects_explicit_unknown_task(self):
        router = _fake_router()
        result = asyncio.run(
            tune_routing_weights(router, tenant_id="t1", task_types=["nope"])
        )
        assert result["tasks_tuned_count"] == 0
        assert result["tasks_tuned"][0]["status"] == "skipped"


class TestModuleImportTolerance:
    # NOTE: re-imports the module under a FRESH module object (pop from
    # sys.modules) so the original module and its class objects — and every
    # other test file's top-level references to them — stay untouched.

    def test_module_tolerates_missing_preference_collector(self):
        real = sys.modules["core.llm.routing.preference_collector"]
        saved = sys.modules.get("core.llm.routing.routellm_trainer")
        try:
            sys.modules["core.llm.routing.preference_collector"] = None
            sys.modules.pop("core.llm.routing.routellm_trainer", None)
            fresh = importlib.import_module("core.llm.routing.routellm_trainer")
            assert fresh.PREFERENCE_AVAILABLE is False
        finally:
            sys.modules["core.llm.routing.preference_collector"] = real
            sys.modules["core.llm.routing.routellm_trainer"] = saved
        assert trm.PREFERENCE_AVAILABLE is True

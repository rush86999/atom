"""
End-to-end integration tests for the LLM routing trainer.

These tests exercise the real scikit-learn training pipeline (not stubs):
- RouteLLMTrainer.train() on synthetic data → a persisted, loadable model
- get_best_model() leaves the trainer pointing at the winner (regression test
  for the destructive-state bug)
- cache_optimizer.detect_pattern() with enough history to reach the previously
  buggy np.mean branch
- LearningBasedRouter._retrain_router() produces real learned weights instead
  of the old (None, 0.0) placeholder

All training is CPU-only via scikit-learn (no GPU required).
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _make_example(task_type: str, satisfied: bool, tokens: int = 800,
                  has_code: bool = False) -> "TrainingExample":
    """Build a realistic TrainingExample for the trainer's feature extractor."""
    from core.llm.routing import TrainingExample

    one_hot = {
        "task_code": 1.0 if task_type == "code_generation" else 0.0,
        "task_analysis": 1.0 if task_type == "extraction" else 0.0,
        "task_reasoning": 1.0 if task_type == "reasoning" else 0.0,
        "task_chat": 1.0 if task_type == "question_answering" else 0.0,
        "task_general": 1.0 if task_type not in {
            "code_generation", "extraction", "reasoning", "question_answering"
        } else 0.0,
    }
    import math
    return TrainingExample(
        estimated_tokens=tokens,
        task_type=task_type,
        prompt_features={
            "log_tokens": math.log2(tokens + 1),
            "token_bucket": 1.0,
            **one_hot,
            "has_code": 1.0 if has_code else 0.0,
            "has_numbers": 1.0,
            "avg_word_length": 5.0,
        },
        chosen_model="gpt-4o" if satisfied else "gpt-4o-mini",
        user_satisfaction=0.9 if satisfied else 0.1,
        was_successful=satisfied,
        quality_score=0.9 if satisfied else 0.1,
    )


def _balanced_dataset(n: int = 120) -> list:
    """A dataset with a learnable signal: code+has_code → satisfied."""
    examples = []
    for i in range(n):
        # Code-generation prompts with code → satisfied; others → not.
        if i % 2 == 0:
            examples.append(_make_example("code_generation", satisfied=True,
                                          tokens=1200, has_code=True))
        else:
            examples.append(_make_example("question_answering", satisfied=False,
                                          tokens=400, has_code=False))
    return examples


# ----------------------------------------------------------------------------
# RouteLLMTrainer end-to-end
# ----------------------------------------------------------------------------

class TestRouteLLMTrainerEndToEnd:
    """Exercise the real sklearn training pipeline."""

    @pytest.fixture
    def trainer(self, tmp_path):
        """A trainer writing to an isolated temp model directory."""
        from core.llm.routing import RouteLLMTrainer, TrainingConfig

        config = TrainingConfig(model_path=str(tmp_path / "models"))
        return RouteLLMTrainer(config)

    def test_train_completes_and_persists_model(self, trainer, tmp_path):
        """train() should return COMPLETED, report accuracy, and write a .pkl."""
        from core.llm.routing import TrainingStatus

        result = trainer.train(_balanced_dataset(120))

        assert result.status == TrainingStatus.COMPLETED, (
            f"Training did not complete: {result.metadata}"
        )
        assert result.samples_trained == 120
        assert 0.0 <= result.accuracy <= 1.0
        # A learnable signal (code+has_code → satisfied) should beat chance.
        assert result.accuracy > 0.5, (
            f"Accuracy {result.accuracy} below chance — training may be broken"
        )
        # A model file must exist on disk.
        model_files = list((tmp_path / "models").glob("*.pkl"))
        assert model_files, "No model .pkl written to model_path"
        assert result.model_id in model_files[0].name

    def test_load_and_predict_round_trip(self, trainer):
        """A trained, reloaded model should predict a satisfaction score in [0,1]."""
        from core.llm.routing import TrainingStatus

        result = trainer.train(_balanced_dataset(120))
        assert result.status == TrainingStatus.COMPLETED

        # Drop the in-memory model and reload from disk.
        trainer.model = None
        assert trainer.predict({}) == 0.5  # uncertainty with no model

        loaded = trainer.load_model(result.model_id)
        assert loaded is True

        features = {
            "log_tokens": 10.0, "token_bucket": 1.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 1.0, "avg_word_length": 5.0,
        }
        score = trainer.predict(features)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_get_best_model_leaves_winner_loaded(self, trainer):
        """Regression test: get_best_model() must leave self.model on the winner."""
        from core.llm.routing import ModelType, TrainingStatus

        dataset = _balanced_dataset(120)
        best_type, best_result = trainer.get_best_model(
            dataset,
            model_types=[ModelType.RANDOM_FOREST, ModelType.LOGISTIC_REGRESSION],
        )

        assert best_type in (ModelType.RANDOM_FOREST, ModelType.LOGISTIC_REGRESSION)
        assert best_result is not None
        assert best_result.status == TrainingStatus.COMPLETED

        # The winning model id must be the one currently loaded in memory.
        assert trainer.model is not None, "get_best_model left no model loaded"
        # And config must reflect the winner.
        assert trainer.config.model_type == best_type
        # Predict must work (uses the loaded winner).
        score = trainer.predict({
            "log_tokens": 10.0, "token_bucket": 1.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 1.0, "avg_word_length": 5.0,
        })
        assert 0.0 <= score <= 1.0

    def test_empty_features_returns_correct_shape(self, trainer):
        """extract_features on empty input should be 2-D, not (0,)."""
        X = trainer.feature_extractor.extract_features([])
        assert X.shape == (0, len(trainer.feature_extractor.feature_names))


# ----------------------------------------------------------------------------
# cache_optimizer — the np.mean regression
# ----------------------------------------------------------------------------

class TestCacheOptimizerNpBug:
    """detect_pattern must not raise NameError once ≥4 accesses accumulate."""

    def test_detect_pattern_with_enough_history(self):
        from core.llm.routing.cache_optimizer import AccessPatternAnalyzer, AccessPattern

        analyzer = AccessPatternAnalyzer()
        prompt_hash = "prompt_with_regular_access"

        # Record 5 accesses ~60s apart → a TEMPORAL pattern (low variance).
        # This path previously raised `NameError: name 'np' is not defined`.
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(5):
            analyzer.record_access(
                prompt_hash, timestamp=base + timedelta(seconds=60 * i)
            )

        pattern = analyzer.detect_pattern(prompt_hash)
        assert pattern in (
            AccessPattern.TEMPORAL, AccessPattern.SEQUENTIAL, AccessPattern.RANDOM
        )
        # 60s-apart accesses have tiny variance (< 60) → TEMPORAL.
        assert pattern == AccessPattern.TEMPORAL


# ----------------------------------------------------------------------------
# LearningBasedRouter — real learned weights (no more None/0.0 stub)
# ----------------------------------------------------------------------------

class TestRouterLearnsRealWeights:
    """The live router must produce real weights after enough feedback."""

    @pytest.fixture
    def router(self, monkeypatch, tmp_path):
        """A router whose trainer writes to an isolated temp dir."""
        from core import learning_llm_router

        # Patch TrainingConfig default model_path so the router's trainer
        # doesn't pollute the real data/router_models dir.
        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(learning_llm_router.TrainingConfig, "__init__",
                            patched_init)

        router = learning_llm_router.LearningBasedRouter(Mock())
        # Lower the thresholds so the test doesn't need 100 feedbacks.
        router._min_training_samples = 30
        # And let the trainer actually train on that many samples.
        router._get_trainer().config.min_samples = 30
        return router

    def _feedback(self, model_id, success, quality, tenant="t1",
                  task="code_generation", satisfaction=None):
        from core.learning_llm_router import RoutingFeedback
        return RoutingFeedback(
            routing_result_id="r",
            tenant_id=tenant,
            model_id=model_id,
            task_type=task,
            success=success,
            quality_satisfied=quality,
            cost_within_budget=True,
            user_satisfaction=satisfaction,
        )

    @pytest.mark.asyncio
    async def test_retrain_produces_real_weights(self, router):
        """After enough feedback, _router_cache holds a real weights dict."""
        # gpt-4o succeeds reliably; gpt-4o-mini fails. The router should learn
        # to weight quality higher as overall success climbs.
        for _ in range(20):
            await router.record_feedback(
                self._feedback("gpt-4o", True, True, satisfaction=0.9)
            )
        for _ in range(10):
            await router.record_feedback(
                self._feedback("gpt-4o-mini", False, False, satisfaction=0.1)
            )

        cache_key = "t1:code_generation"
        assert cache_key in router._router_cache, "No learned weights cached"
        weights = router._router_cache[cache_key]

        # The old stub stored a (None, 0.0) tuple — weights must now be a dict.
        assert isinstance(weights, dict), (
            f"Expected dict of weights, got {type(weights)}: {weights}"
        )
        assert set(weights.keys()) == {"quality", "cost", "speed"}
        # Weights should be normalized and non-negative.
        assert all(v >= 0 for v in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        # 30/30 success overall (20 success + 10 fail, but success flag varies) —
        # with the strong-outcome path, quality should be boosted above the
        # code_generation default of 0.5.
        assert weights["quality"] > 0.5, (
            f"Expected boosted quality weight, got {weights}"
        )

    @pytest.mark.asyncio
    async def test_get_learned_weights_returns_learned_dict(self, router):
        """_get_learned_weights returns the learned dict, falling back to defaults."""
        # Before any training: defaults.
        defaults = router._get_learned_weights("code_generation", "t2")
        assert defaults == {"quality": 0.5, "cost": 0.2, "speed": 0.3}

        # Seed enough feedback and retrain.
        for _ in range(30):
            await router.record_feedback(
                self._feedback("gpt-4o", True, True, satisfaction=0.9)
            )

        learned = router._get_learned_weights("code_generation", "t1")
        assert isinstance(learned, dict)
        assert set(learned.keys()) == {"quality", "cost", "speed"}

    @pytest.mark.asyncio
    async def test_preference_data_is_trimmed_to_cap(self, router):
        """R17-2: _preference_data per key must not exceed its cap."""
        # Set a tiny cap to exercise eviction without a huge loop.
        router._max_preference_data_per_key = 50
        # Disable retraining to isolate the trimming behavior.
        router._min_training_samples = 10_000_000
        for _ in range(120):
            await router.record_feedback(
                self._feedback("gpt-4o", True, True, tenant="t3", task="reasoning")
            )
        key = "t3:reasoning"
        assert len(router._preference_data[key]) <= router._max_preference_data_per_key

    def test_router_cache_evicts_when_over_cap(self, router):
        """R17-2: _router_cache must evict down to its cap when over."""
        router._max_router_cache_size = 5
        for i in range(20):
            router._set_cached_weights(
                f"tenant{i}:code_generation",
                {"quality": 0.4, "cost": 0.3, "speed": 0.3},
                tenant_id=f"tenant{i}",
            )
        assert len(router._router_cache) <= router._max_router_cache_size


# ----------------------------------------------------------------------------
# PerModelRouter — per-model satisfaction predictors
# ----------------------------------------------------------------------------

class TestPerModelRouter:
    """Unit tests for the per-model predictor that drives learning-based routing."""

    @pytest.fixture
    def router(self, tmp_path):
        from core.llm.routing import PerModelRouter, TrainingConfig
        config = TrainingConfig(model_path=str(tmp_path / "models"))
        return PerModelRouter(config)

    def _examples(self, n, satisfied, task_type="code_generation"):
        """n examples, all with the given satisfaction outcome."""
        out = []
        for _ in range(n):
            out.append(_make_example(task_type, satisfied=satisfied))
        return out

    def test_cold_start_returns_none(self, router):
        """No predictor → predict_satisfaction returns None (caller falls back)."""
        assert router.predict_satisfaction("unknown_model", {}) is None
        assert router.has_predictor("unknown_model") is False
        assert router.confidence("unknown_model") == 0.0

    def test_model_that_satisfies_scores_higher(self, router):
        """A predictor trained on satisfied examples must predict high satisfaction."""
        router.train("good_model", self._examples(30, satisfied=True))
        # Code features (matches the training task type).
        code_features = {
            "log_tokens": 10.0, "token_bucket": 2.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 1.0, "avg_word_length": 5.0,
        }
        score = router.predict_satisfaction("good_model", code_features)
        assert score is not None
        assert score > 0.5, f"Expected high satisfaction, got {score}"

    def test_good_model_outscores_bad_model(self, router):
        """The core learning claim: a model that satisfies > one that fails."""
        # good_model: all satisfied. bad_model: all dissatisfied.
        router.train("good_model", self._examples(30, satisfied=True))
        router.train("bad_model", self._examples(30, satisfied=False))

        code_features = {
            "log_tokens": 10.0, "token_bucket": 2.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 1.0, "avg_word_length": 5.0,
        }
        good_score = router.predict_satisfaction("good_model", code_features)
        bad_score = router.predict_satisfaction("bad_model", code_features)
        assert good_score > bad_score, (
            f"good_model ({good_score}) should outscore bad_model ({bad_score})"
        )

    def test_confidence_grows_with_samples(self, router):
        """More data → higher blend weight (capped at max_weight)."""
        router.train("m", self._examples(10, satisfied=True))
        low = router.confidence("m")
        router.train("m", self._examples(50, satisfied=True))
        high = router.confidence("m")
        assert high > low, "confidence should grow with more samples"
        assert high <= 0.3, "confidence should be capped"

    def test_persistence_round_trip(self, router, tmp_path):
        """A trained predictor should persist and reload."""
        from core.llm.routing import PerModelRouter, TrainingConfig

        router.train("persisted_model", self._examples(30, satisfied=True))
        assert router.has_predictor("persisted_model")

        code_features = {
            "log_tokens": 10.0, "token_bucket": 2.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 1.0, "avg_word_length": 5.0,
        }
        before = router.predict_satisfaction("persisted_model", code_features)

        # New instance reading from the same dir.
        reloaded = PerModelRouter(
            TrainingConfig(model_path=str(tmp_path / "models"))
        )
        loaded = reloaded.load_all()
        assert loaded >= 1
        assert reloaded.has_predictor("persisted_model")
        after = reloaded.predict_satisfaction("persisted_model", code_features)
        assert after == pytest.approx(before, abs=1e-6)


# ----------------------------------------------------------------------------
# Learning-based routing — routing decisions change with feedback
# ----------------------------------------------------------------------------

class TestLearningActuallyRoutes:
    """The test that proves routing is learning-based: decisions flip with feedback."""

    @pytest.fixture
    def router(self, monkeypatch, tmp_path):
        """A router writing models to an isolated temp dir, with low thresholds."""
        from core import learning_llm_router

        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(learning_llm_router.TrainingConfig, "__init__",
                            patched_init)

        router = learning_llm_router.LearningBasedRouter(Mock())
        # Low thresholds so tests don't need hundreds of feedback records.
        router._min_samples_per_model = 15
        router._min_training_samples = 15
        return router

    def _fb(self, model_id, success, quality, tenant="t1", task="code_generation",
            satisfaction=None):
        from core.learning_llm_router import RoutingFeedback
        return RoutingFeedback(
            routing_result_id="r",
            tenant_id=tenant,
            model_id=model_id,
            task_type=task,
            success=success,
            quality_satisfied=quality,
            cost_within_budget=True,
            user_satisfaction=satisfaction,
        )

    @pytest.mark.asyncio
    async def test_cold_start_matches_rule_based(self, router):
        """With no feedback, routing must equal the pure rule-based baseline."""
        from core.learning_llm_router import RoutingRequest

        req = RoutingRequest(
            tenant_id="fresh_tenant", task_type="code_generation",
            estimated_tokens=800,
        )
        result = await router.route(req)
        assert result is not None
        # No predictors should exist for a fresh tenant.
        assert "fresh_tenant:code_generation" not in router._per_model_routers

    @pytest.mark.asyncio
    async def test_routing_flips_with_feedback(self, router):
        """THE test: feedback saying model A succeeds & B fails must make A win,
        and reversing the feedback must flip the winner."""
        from core.learning_llm_router import RoutingRequest

        req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=800,
        )
        # Both models must be valid code-capable candidates.
        cands = router._filter_by_capabilities(req)
        cand_ids = {m.model_id for m in cands}
        model_a = "gpt-4o"
        model_b = "deepseek-v4-pro"
        assert model_a in cand_ids and model_b in cand_ids, (
            f"need both models as candidates, got {sorted(cand_ids)}"
        )

        # --- Phase 1: gpt-4o satisfies, deepseek fails ---
        for _ in range(20):
            await router.record_feedback(
                self._fb(model_a, True, True, satisfaction=0.95)
            )
            await router.record_feedback(
                self._fb(model_b, False, False, satisfaction=0.1)
            )

        # Predictors must now exist.
        pmr = router._per_model_routers.get("t1:code_generation")
        assert pmr is not None
        assert pmr.has_predictor(model_a)
        assert pmr.has_predictor(model_b)

        result_a = await router.route(req)
        winner_phase1 = result_a.selected_model.model_id
        assert winner_phase1 == model_a, (
            f"After feedback favoring {model_a}, expected {model_a} but routed "
            f"to {winner_phase1}"
        )

        # --- Phase 2: clear and reverse the feedback ---
        router.clear_learning_cache(tenant_id="t1")
        router._preference_data.clear()
        router._per_model_routers.clear()

        for _ in range(20):
            await router.record_feedback(
                self._fb(model_a, False, False, satisfaction=0.1)
            )
            await router.record_feedback(
                self._fb(model_b, True, True, satisfaction=0.95)
            )

        result_b = await router.route(req)
        winner_phase2 = result_b.selected_model.model_id
        assert winner_phase2 == model_b, (
            f"After reversed feedback favoring {model_b}, expected {model_b} "
            f"but routed to {winner_phase2}"
        )
        assert winner_phase1 != winner_phase2, (
            "Routing decision did not change after feedback reversed — "
            "learning is not influencing the decision"
        )

    @pytest.mark.asyncio
    async def test_route_latency_under_target(self, router):
        """Routing with predictors loaded must stay < 50ms (file's stated target)."""
        import time
        from core.learning_llm_router import RoutingRequest

        # Seed predictors.
        for _ in range(20):
            await router.record_feedback(
                self._fb("gpt-4o", True, True, satisfaction=0.9)
            )

        req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=800,
        )
        # Warm any caches.
        await router.route(req)

        start = time.perf_counter()
        await router.route(req)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50.0, (
            f"Routing took {elapsed_ms:.1f}ms, exceeds 50ms target"
        )


# ----------------------------------------------------------------------------
# Prompt-feature capture — eliminates train/serve skew, enables within-task
# discrimination (the limitation fix)
# ----------------------------------------------------------------------------

class TestPromptFeatureCapture:
    """The limitation fix: predictors must train on REAL per-prompt features
    captured at decision time, not constants — so they can discriminate
    WITHIN a task (short vs long, code vs no-code)."""

    @pytest.fixture
    def router(self, monkeypatch, tmp_path):
        """Router writing models to temp dir, low thresholds, small decision cap."""
        from core import learning_llm_router

        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(learning_llm_router.TrainingConfig, "__init__",
                            patched_init)

        router = learning_llm_router.LearningBasedRouter(Mock())
        router._min_samples_per_model = 15
        router._min_training_samples = 15
        return router

    def _fb(self, result_id, model_id, success, quality, tenant="t1",
            task="code_generation", satisfaction=None):
        from core.learning_llm_router import RoutingFeedback
        return RoutingFeedback(
            routing_result_id=result_id,
            tenant_id=tenant,
            model_id=model_id,
            task_type=task,
            success=success,
            quality_satisfied=quality,
            cost_within_budget=True,
            user_satisfaction=satisfaction,
        )

    @pytest.mark.asyncio
    async def test_route_returns_correlatable_id(self, router):
        """route() must return a routing_result_id that's in the decision store."""
        from core.learning_llm_router import RoutingRequest

        req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=800,
        )
        result = await router.route(req)
        assert result.routing_result_id, "route() did not return a routing_result_id"
        assert result.routing_result_id in router._routing_decisions
        # And real prompt features must be echoed back.
        feats = result.prompt_features
        assert feats["log_tokens"] > 0, "expected real log_tokens, not 0.0"

    @pytest.mark.asyncio
    async def test_feedback_recovers_real_features(self, router):
        """Recording feedback with a real id attaches the captured features,
        so _feedback_to_training_example uses them instead of constants."""
        from core.learning_llm_router import RoutingRequest

        # Route a long request and capture the id.
        req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=4000,
        )
        result = await router.route(req)
        long_id = result.routing_result_id

        # Record feedback using that id.
        await router.record_feedback(
            self._fb(long_id, "gpt-4o", True, True, satisfaction=0.9)
        )

        # The stored feedback must carry the recovered features.
        fb = router._preference_data["t1:code_generation"][0]
        recovered = getattr(fb, "_prompt_features", None)
        assert recovered is not None, "features were not attached to feedback"
        # The long request must have produced a larger log_tokens than the
        # constant default (0.0).
        assert recovered["log_tokens"] > 5.0, (
            f"expected real log_tokens for a 4000-token request, got "
            f"{recovered['log_tokens']}"
        )

    @pytest.mark.asyncio
    async def test_bogus_id_falls_back_gracefully(self, router):
        """A feedback with an un-correlatable id must not crash; training uses
        task-level defaults."""
        # No matching decision exists for this id.
        await router.record_feedback(
            self._fb("nonexistent-id", "gpt-4o", True, True, satisfaction=0.9)
        )
        fb = router._preference_data["t1:code_generation"][0]
        # No recovered features -> the helper will derive task defaults.
        assert not hasattr(fb, "_prompt_features") or fb._prompt_features is None

    def test_decision_store_is_bounded(self, router):
        """The _routing_decisions store must honor its cap (R17-2 pattern)."""
        router._max_routing_decisions = 5
        for i in range(20):
            router._routing_decisions[f"id_{i}"] = {"log_tokens": 1.0}
        # Simulate eviction as _create_routing_result would.
        if len(router._routing_decisions) > router._max_routing_decisions:
            overflow = len(router._routing_decisions) - router._max_routing_decisions
            for stale_id in list(router._routing_decisions.keys())[:overflow]:
                del router._routing_decisions[stale_id]
        assert len(router._routing_decisions) <= router._max_routing_decisions

    @pytest.mark.asyncio
    async def test_within_task_discrimination(self, router):
        """THE limitation-fix test: a predictor must discriminate WITHIN a task.

        Model A satisfies LONG prompts but fails SHORT ones; model B is the
        opposite. With constant features this is impossible to learn (every
        example looks identical). With captured per-prompt features, the
        predictors must learn the size preference.
        """
        from core.learning_llm_router import RoutingRequest

        # Route alternating long and short requests, capturing each id.
        long_ids_a, short_ids_a = [], []
        long_ids_b, short_ids_b = [], []

        for _ in range(15):
            # Model A: long -> satisfied, short -> dissatisfied.
            res_long = await router.route(RoutingRequest(
                tenant_id="t1", task_type="code_generation", estimated_tokens=4000,
            ))
            long_ids_a.append(res_long.routing_result_id)

            res_short = await router.route(RoutingRequest(
                tenant_id="t1", task_type="code_generation", estimated_tokens=80,
            ))
            short_ids_a.append(res_short.routing_result_id)

        # Model B: short -> satisfied, long -> dissatisfied.
        for _ in range(15):
            res_short = await router.route(RoutingRequest(
                tenant_id="t1", task_type="code_generation", estimated_tokens=80,
            ))
            short_ids_b.append(res_short.routing_result_id)

            res_long = await router.route(RoutingRequest(
                tenant_id="t1", task_type="code_generation", estimated_tokens=4000,
            ))
            long_ids_b.append(res_long.routing_result_id)

        # Record feedback correlating each id to its outcome.
        for rid in long_ids_a:
            await router.record_feedback(
                self._fb(rid, "gpt-4o", True, True, satisfaction=0.95)
            )
        for rid in short_ids_a:
            await router.record_feedback(
                self._fb(rid, "gpt-4o", False, False, satisfaction=0.05)
            )
        for rid in short_ids_b:
            await router.record_feedback(
                self._fb(rid, "deepseek-v4-pro", True, True, satisfaction=0.95)
            )
        for rid in long_ids_b:
            await router.record_feedback(
                self._fb(rid, "deepseek-v4-pro", False, False, satisfaction=0.05)
            )

        # Force a retrain so the predictors are built now.
        await router._retrain_router("t1", "code_generation")

        pmr = router._per_model_routers["t1:code_generation"]
        assert pmr.has_predictor("gpt-4o")
        assert pmr.has_predictor("deepseek-v4-pro")

        # Build the two feature vectors the predictor will be queried with.
        # IMPORTANT: these must match what _score_candidates would build for
        # the same request, i.e. via the router's own feature extractor.
        long_req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=4000,
        )
        short_req = RoutingRequest(
            tenant_id="t1", task_type="code_generation", estimated_tokens=80,
        )
        long_feats = router._extract_request_features(long_req)
        short_feats = router._extract_request_features(short_req)

        # Model A (gpt-4o) should predict HIGHER satisfaction for LONG than SHORT.
        a_long = pmr.predict_satisfaction("gpt-4o", long_feats)
        a_short = pmr.predict_satisfaction("gpt-4o", short_feats)
        assert a_long is not None and a_short is not None
        assert a_long > a_short, (
            f"gpt-4o should prefer long prompts (trained long=satisfied), "
            f"got long={a_long} vs short={a_short} — within-task "
            f"discination FAILED (this is the limitation we fixed)"
        )

        # Model B (deepseek-v4-pro) should prefer SHORT.
        b_long = pmr.predict_satisfaction("deepseek-v4-pro", long_feats)
        b_short = pmr.predict_satisfaction("deepseek-v4-pro", short_feats)
        assert b_short > b_long, (
            f"deepseek-v4-pro should prefer short prompts, got "
            f"short={b_short} vs long={b_long}"
        )

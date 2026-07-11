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

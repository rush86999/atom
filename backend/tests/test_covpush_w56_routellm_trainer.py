"""Coverage wave 56 — core/llm/routing/routellm_trainer.py (78% → 90%+).

FeatureExtractor edge cases (empty targets/weights), trainer (unavailable
flag, insufficient samples, training success with precision/recall, training
failure, all 4 model types + unsupported), save/load (no-model skip, missing
file, load failure), predict (no model, proba single-class invert, non-proba),
get_best_model (winner selection + all-fail restore), evaluator (A/B with
significance + insufficient samples, confidence interval + short data),
factories.
"""
import numpy as np
import pytest

from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.routellm_trainer import (
    FeatureExtractor,
    ModelType,
    RouteLLMTrainer,
    RouterEvaluator,
    TrainingConfig,
    TrainingStatus,
    get_router_evaluator,
    get_router_trainer,
)


def _ex(seed, satisfied=True, weight=1.0):
    return TrainingExample(
        example_id=f"e{seed}", estimated_tokens=100, task_type="chat",
        prompt_features={"length": float(seed % 5)},
        user_satisfaction=1.0 if satisfied else 0.0,
        chosen_model="m1", weight=weight,
    )


@pytest.fixture
def trainer(tmp_path):
    config = TrainingConfig(model_path=str(tmp_path), min_samples=10,
                            n_estimators=10, max_depth=4)
    return RouteLLMTrainer(config)


class TestFeatureExtractorEdges:
    def test_empty_targets(self):
        assert FeatureExtractor().extract_targets([]).size == 0

    def test_empty_weights(self):
        assert FeatureExtractor().extract_weights([]).size == 0


class TestTrain:
    def test_preference_unavailable(self, trainer):
        import core.llm.routing.routellm_trainer as rt
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(rt, "PREFERENCE_AVAILABLE", False)
            result = trainer.train([])
        assert result.status == TrainingStatus.FAILED

    def test_insufficient_samples(self, trainer):
        result = trainer.train([_ex(0), _ex(1)])
        assert result.status == TrainingStatus.FAILED
        assert "Insufficient" in result.metadata["error"]

    def test_train_success(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        result = trainer.train(examples)
        assert result.status == TrainingStatus.COMPLETED
        assert result.samples_trained == 30
        assert result.model_id
        assert result.metadata["model_type"] == "random_forest"

    def test_train_failure(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(trainer.feature_extractor, "extract_features",
                       lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
            result = trainer.train(examples)
        assert result.status == TrainingStatus.FAILED


class TestModelTypes:
    def _train_type(self, tmp_path, model_type):
        config = TrainingConfig(model_path=str(tmp_path), min_samples=10,
                                model_type=model_type, n_estimators=5,
                                max_depth=3, epochs=2)
        t = RouteLLMTrainer(config)
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        return t, t.train(examples)

    def test_logistic_regression(self, tmp_path):
        t, result = self._train_type(tmp_path, ModelType.LOGISTIC_REGRESSION)
        assert result.status == TrainingStatus.COMPLETED

    def test_neural_network(self, tmp_path):
        t, result = self._train_type(tmp_path, ModelType.NEURAL_NETWORK)
        assert result.status == TrainingStatus.COMPLETED

    def test_ensemble(self, tmp_path):
        t, result = self._train_type(tmp_path, ModelType.ENSEMBLE)
        assert result.status == TrainingStatus.COMPLETED

    def test_unsupported_type(self, tmp_path):
        config = TrainingConfig(model_path=str(tmp_path))
        t = RouteLLMTrainer(config)
        t.config.model_type = "bogus"
        with pytest.raises(ValueError):
            t._create_model()


class TestPersistenceAndPredict:
    def test_save_no_model_skips(self, trainer):
        trainer.model = None
        trainer._save_model("m1")  # must not raise

    def test_save_load_roundtrip(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        trainer.train(examples, model_id="saved")
        trainer2 = RouteLLMTrainer(
            TrainingConfig(model_path=str(trainer.config.model_path)))
        assert trainer2.load_model("saved") is True
        assert trainer2.model is not None

    def test_load_missing_returns_false(self, trainer):
        assert trainer.load_model("ghost") is False

    def test_load_corrupt_returns_false(self, trainer, tmp_path):
        from pathlib import Path
        Path(tmp_path, "bad.pkl").write_bytes(b"not a pickle")
        assert trainer.load_model("bad") is False

    def test_predict_no_model_default(self, trainer):
        assert trainer.predict({}) == 0.5

    def test_predict_trained(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        trainer.train(examples)
        prob = trainer.predict({"length": 1.0})
        assert 0.0 <= prob <= 1.0

    def test_predict_single_class_invert(self, trainer, tmp_path):
        from sklearn.dummy import DummyClassifier
        config = TrainingConfig(model_path=str(tmp_path), min_samples=10)
        t = RouteLLMTrainer(config)
        t.model = DummyClassifier(strategy="most_frequent")
        # all-negative target -> classes_ == [0]; single proba column inverted
        t.model.fit(np.zeros((10, 1)), np.zeros(10))
        prob = t.predict({})
        assert prob == 0.0

    def test_predict_no_proba(self, trainer, tmp_path):
        from sklearn.svm import SVC
        config = TrainingConfig(model_path=str(tmp_path), min_samples=10)
        t = RouteLLMTrainer(config)
        t.model = SVC()
        n_feats = len(t.feature_extractor.feature_names)
        t.model.fit(np.zeros((10, n_feats)), np.array([0, 1] * 5))
        prob = t.predict({})
        assert prob in (0.0, 1.0)


class TestGetBestModel:
    def test_best_model_selected(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        best_type, result = trainer.get_best_model(examples)
        assert result.status == TrainingStatus.COMPLETED
        assert best_type in (ModelType.RANDOM_FOREST, ModelType.LOGISTIC_REGRESSION)

    def test_all_fail_restores_config(self, trainer):
        examples = [_ex(i, i % 2 == 0) for i in range(30)]
        original = trainer.config.model_type
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(trainer, "train",
                       lambda examples: type("R", (), {
                           "status": TrainingStatus.FAILED,
                           "accuracy": 0.0, "model_id": "x"})())
            best, result = trainer.get_best_model(examples)
        assert best is None
        assert trainer.config.model_type == original


class TestEvaluator:
    def test_ab_test_significant(self):
        ev = RouterEvaluator(TrainingConfig(min_ab_samples=30))
        control = [0.5] * 30
        learning = [0.8] * 30
        result = ev.evaluate_ab_test(control, learning)
        assert result["improvement"] > 0
        assert bool(result["significant"]) is True
        assert result["control_samples"] == 30

    def test_ab_test_insufficient(self):
        ev = RouterEvaluator()
        result = ev.evaluate_ab_test([0.5], [0.8])
        assert result["significant"] is False
        assert result["t_statistic"] == 0.0

    def test_confidence_interval(self):
        ev = RouterEvaluator()
        lo, hi = ev.get_confidence_interval([0.5, 0.6, 0.7, 0.8])
        assert lo < hi

    def test_confidence_interval_short_data(self):
        ev = RouterEvaluator()
        assert ev.get_confidence_interval([0.5]) == (0.0, 1.0)

    def test_factories(self, tmp_path):
        assert isinstance(get_router_trainer(), RouteLLMTrainer)
        assert isinstance(get_router_evaluator(), RouterEvaluator)


class TestRestrictedPickle:
    def test_restricted_loads_allowed_and_forbidden(self):
        import io
        import pickle as pkl
        from core.llm.routing.restricted_pickle import (
            restricted_load, restricted_loads)
        data = pkl.dumps({"a": [1, 2, 3]})
        assert restricted_loads(data) == {"a": [1, 2, 3]}
        assert restricted_load(io.BytesIO(data)) == {"a": [1, 2, 3]}

        class Evil:
            def __reduce__(self):
                return (eval, ("1+1",))

        with pytest.raises(pkl.UnpicklingError):
            restricted_loads(pkl.dumps(Evil()))

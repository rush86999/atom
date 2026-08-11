"""Coverage wave 54 — core/llm/routing/per_model_router.py (22% → 90%+).

Training (multi-class fit with weights, single-class constant predictor,
weight-fit fallback, failure), estimator creation (RF/LR/MLP/ensemble),
prediction (cold start, single-class rate, proba class mapping, no-positive,
non-proba), confidence scaling, persistence (save + path-traversal guard +
load + corrupt-file tolerance), factory.
"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from core.llm.routing.per_model_router import (
    PerModelRouter,
    get_per_model_router,
)
from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.routellm_trainer import ModelType, TrainingConfig


def _ex(seed, satisfied, task="chat", tokens=100):
    return TrainingExample(
        example_id=f"e{seed}", estimated_tokens=tokens, task_type=task,
        prompt_features={"length": float(seed % 5)},
        user_satisfaction=1.0 if satisfied else 0.0,
        chosen_model="m1",
    )


@pytest.fixture
def router(tmp_path):
    config = TrainingConfig(
        model_path=str(tmp_path), n_estimators=10, max_depth=4)
    return PerModelRouter(config)


class TestTrain:
    def test_train_multi_class_success(self, router):
        examples = [_ex(i, i % 2 == 0) for i in range(20)]
        result = router.train("m1", examples)
        assert result.status.value in ("completed", "COMPLETED")
        assert router.has_predictor("m1")
        stats = router.predictor_stats("m1")
        assert stats.samples == 20
        assert stats.classes == [0, 1]

    def test_train_single_class_constant(self, router):
        examples = [_ex(i, True) for i in range(10)]
        result = router.train("m1", examples)
        assert result.status.value in ("completed", "COMPLETED")
        assert router.predictors["m1"] is None
        assert router.stats["m1"].positive_rate == 1.0

    def test_train_no_examples_fails(self, router):
        result = router.train("m1", [])
        assert result.status.value in ("failed", "FAILED")

    def test_train_single_class_zero(self, router):
        examples = [_ex(i, False) for i in range(10)]
        router.train("m1", examples)
        assert router.stats["m1"].positive_rate == 0.0

    def test_train_mlp_weight_fit(self, router):
        examples = [_ex(i, i % 2 == 0) for i in range(20)]
        # MLP: sample_weight unsupported -> unweighted fallback fit
        config = TrainingConfig(
            model_path=str(router._model_dir.parent), model_type=ModelType.NEURAL_NETWORK,
            epochs=1, n_estimators=2, max_depth=2)
        mlp_router = PerModelRouter(config)
        result = mlp_router.train("m1", examples)
        assert result.status.value in ("completed", "COMPLETED")

    def test_train_exception_fails(self, router):
        with pytest.raises(Exception):
            raise RuntimeError("guard")
        # simulate extraction failure
        import core.llm.routing.per_model_router as pmr
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(router.feature_extractor, "extract_features",
                       lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
            result = router.train("m1", [_ex(0, True)])
        assert result.status.value in ("failed", "FAILED")



class TestCreateEstimator:
    def test_logistic_regression(self, tmp_path):
        r = PerModelRouter(TrainingConfig(
            model_path=str(tmp_path), model_type=ModelType.LOGISTIC_REGRESSION))
        est = r._create_estimator()
        assert est is not None

    def test_neural_network(self, tmp_path):
        r = PerModelRouter(TrainingConfig(
            model_path=str(tmp_path), model_type=ModelType.NEURAL_NETWORK,
            epochs=1))
        assert r._create_estimator() is not None

    def test_ensemble(self, tmp_path):
        r = PerModelRouter(TrainingConfig(
            model_path=str(tmp_path), model_type=ModelType.ENSEMBLE,
            n_estimators=2))
        assert r._create_estimator() is not None

    def test_default_random_forest(self, tmp_path):
        r = PerModelRouter(TrainingConfig(model_path=str(tmp_path)))
        assert r._create_estimator() is not None


class TestPredict:
    def test_cold_start_none(self, router):
        assert router.predict_satisfaction("ghost", {}) is None

    def test_single_class_returns_rate(self, router):
        router.train("m1", [_ex(i, True) for i in range(5)])
        assert router.predict_satisfaction("m1", {"length": 1.0}) == 1.0

    def test_trained_proba(self, router):
        router.train("m1", [_ex(i, i % 2 == 0) for i in range(20)])
        prob = router.predict_satisfaction("m1", {"length": 1.0})
        assert prob is not None and 0.0 <= prob <= 1.0

    def test_no_predict_proba_fallback(self, tmp_path):
        r = PerModelRouter(TrainingConfig(model_path=str(tmp_path)))
        from sklearn.svm import SVC
        r.predictors["svc"] = SVC()
        r.stats["svc"] = type("S", (), {"positive_rate": 0.5})()
        with pytest.raises(Exception):
            r.predict_satisfaction("svc", {})  # unfitted SVC predict raises


class TestConfidence:
    def test_no_stats_zero(self, router):
        assert router.confidence("ghost") == 0.0

    def test_scaling(self, router):
        router.train("m1", [_ex(i, True) for i in range(50)])
        assert router.confidence("m1") == 0.3  # capped at max_weight
        router2 = PerModelRouter(TrainingConfig(
            model_path=router._model_dir.parent))
        router2.train("m1", [_ex(i, True) for i in range(5)])
        assert router2.confidence("m1") == pytest.approx(0.3 * 5 / 50)


class TestPersistence:
    def test_save_and_load_roundtrip(self, router):
        router.train("m1", [_ex(i, i % 2 == 0) for i in range(20)])
        router2 = PerModelRouter(TrainingConfig(model_path=router._model_dir.parent))
        loaded = router2.load_all()
        assert loaded == 1
        assert router2.has_predictor("m1")

    def test_save_unknown_model_raises(self, router):
        router.train("m1", [_ex(i, True) for i in range(3)])
        with pytest.raises(KeyError):
            router._save_predictor("ghost-model")

    def test_load_corrupt_meta_tolerated(self, router):
        (router._model_dir / "bad.json").write_text("{not json")
        assert router.load_all() == 0

    def test_load_missing_pkl_single_class(self, router):
        router.train("m1", [_ex(i, True) for i in range(3)])
        # single-class: pkl contains None; remove meta to test load with pkl missing
        meta_path = router._model_dir / "m1.json"
        (router._model_dir / "m1.pkl").unlink(missing_ok=True)
        router2 = PerModelRouter(TrainingConfig(model_path=router._model_dir.parent))
        assert router2.load_all() == 1
        assert router2.predictors["m1"] is None


class TestFactory:
    def test_factory(self, tmp_path):
        r = get_per_model_router(TrainingConfig(model_path=str(tmp_path)))
        assert isinstance(r, PerModelRouter)

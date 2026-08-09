# -*- coding: utf-8 -*-
"""Coverage wave 9 — LLM learning-router stragglers.

Pushes core/llm/routing/per_model_router.py (97% -> 100%) and
core/llm/learning_router_registry.py (97% -> 100%) to full coverage:

- per_model_router 135-136: weighted-fit fallback (estimators that reject
  ``sample_weight``, e.g. MLPClassifier).
- per_model_router 298-299: path-traversal containment in ``_save_predictor``
  (pre-existing symlink inside the model dir pointing outside).
- learning_router_registry 69: double-checked-locking inner hit.

Also realigns the stale R97 contract in the pre-existing suites (3-part
``{tenant}:{task}:{intent}`` predictor keys were removed 2026-08-09; the live
path now keys per-model predictors under ``{tenant}:{task}``).
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.llm.learning_router_registry import (
    ema_router_enabled,
    get_learning_router_instance,
    learning_router_enabled,
    reset_learning_router_instance,
)
from core.llm.routing.per_model_router import (
    PerModelRouter,
    PredictorStats,
    get_per_model_router,
)
from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.routellm_trainer import TrainingConfig, TrainingStatus


def make_example(satisfaction, model="m1", weight=1.0):
    return TrainingExample(
        estimated_tokens=200,
        task_type="code_generation",
        prompt_features={
            "log_tokens": 5.0,
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


class RejectsSampleWeight:
    """Estimator whose fit() raises when sample_weight is passed (MLP-style)."""

    def fit(self, X, y, **kwargs):
        if "sample_weight" in kwargs:
            raise TypeError("MLPClassifier does not accept sample_weight")
        self.fitted_ = True
        return self

    def score(self, X, y):
        return 0.75


# ---------------------------------------------------------------------------
# per_model_router
# ---------------------------------------------------------------------------

class TestPerModelWeightedFitFallback:
    def test_sample_weight_rejected_falls_back_to_unweighted_fit(self, tmp_path):
        router = PerModelRouter(
            TrainingConfig(model_path=str(tmp_path))
        )
        with patch.object(router, "_create_estimator", return_value=RejectsSampleWeight()):
            result = router.train(
                "gpt-4o",
                [
                    make_example(1.0, weight=3.0),
                    make_example(1.0, weight=2.0),
                    make_example(0.0, weight=1.0),
                ],
            )
        assert result.status == TrainingStatus.COMPLETED
        assert result.accuracy == 0.75
        assert "gpt-4o" in router.predictors
        assert router.stats["gpt-4o"].accuracy == 0.75

    def test_sample_weight_accepted_normal_path(self, tmp_path):
        router = PerModelRouter(
            TrainingConfig(model_path=str(tmp_path))
        )
        result = router.train(
            "gpt-4o",
            [
                make_example(1.0, weight=3.0),
                make_example(1.0, weight=2.0),
                make_example(0.0, weight=1.0),
            ],
        )
        assert result.status == TrainingStatus.COMPLETED
        assert result.samples_trained == 3


class TestPerModelSaveTraversalGuard:
    def _router_with_dir(self, tmp_path):
        router = PerModelRouter(
            TrainingConfig(model_path=str(tmp_path))
        )
        router.predictors["m1"] = None  # single-class estimators persist as None
        router.stats["m1"] = PredictorStats(
            model_id="m1",
            samples=3,
            accuracy=1.0,
            trained_at="2026-08-09T00:00:00",
            positive_rate=1.0,
            classes=[1],
        )
        return router

    def test_save_writes_through_none_estimator_and_meta(self, tmp_path):
        router = self._router_with_dir(tmp_path)
        router._save_predictor("m1")
        meta = json.loads((router._model_dir / "m1.json").read_text())
        assert meta["model_id"] == "m1"
        assert meta["samples"] == 3
        assert (router._model_dir / "m1.pkl").exists()

    def test_traversal_sanitized_into_model_dir(self, tmp_path):
        router = self._router_with_dir(tmp_path)
        router.stats["../../evil"] = PredictorStats(
            model_id="../../evil", samples=3, accuracy=1.0,
            trained_at="2026-08-09T00:00:00", positive_rate=1.0, classes=[1],
        )
        router._save_predictor("../../evil")
        # "../" is neutralized by the sanitizer — files land INSIDE the dir.
        assert router.stats["../../evil"].model_id == "../../evil"
        names = {p.name for p in router._model_dir.iterdir()}
        assert all(".." not in n for n in names)
        assert {Path(n).suffix for n in names} == {".pkl", ".json"}

    def test_symlink_escaping_model_dir_raises(self, tmp_path):
        router = self._router_with_dir(tmp_path)
        outside = tmp_path / "outside.pkl"
        outside.write_bytes(b"boom")
        # A pre-existing symlink inside the model dir pointing outside.
        (router._model_dir / "m1.pkl").symlink_to(outside)
        with pytest.raises(ValueError, match="outside model dir"):
            router._save_predictor("m1")

    def test_roundtrip_save_and_load(self, tmp_path):
        router = self._router_with_dir(tmp_path)
        router._save_predictor("m1")
        loader = get_per_model_router(TrainingConfig(model_path=str(tmp_path)))
        assert loader.load_all() == 1
        assert loader.stats["m1"].samples == 3

    def test_load_all_empty_dir_returns_zero(self, tmp_path):
        loader = get_per_model_router(TrainingConfig(model_path=str(tmp_path)))
        assert loader.load_all() == 0

    def test_load_all_corrupt_meta_skipped(self, tmp_path):
        router = self._router_with_dir(tmp_path)
        router._save_predictor("m1")
        (router._model_dir / "m1.json").write_text("{not json")
        loader = get_per_model_router(TrainingConfig(model_path=str(tmp_path)))
        assert loader.load_all() == 0


# ---------------------------------------------------------------------------
# learning_router_registry
# ---------------------------------------------------------------------------

class TestRegistryFlags:
    def test_learning_router_enabled_variants(self, monkeypatch):
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        assert learning_router_enabled() is False
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        assert learning_router_enabled() is True
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "TRUE")
        assert learning_router_enabled() is True

    def test_ema_enabled_broad_truthy_set(self, monkeypatch):
        monkeypatch.delenv("ATOM_EMA_ROUTER_ENABLED", raising=False)
        assert ema_router_enabled() is False
        monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "yes")
        assert ema_router_enabled() is True
        monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "on")
        assert ema_router_enabled() is True
        monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "maybe")
        assert ema_router_enabled() is False


class TestRegistrySingleton:
    def teardown_method(self):
        reset_learning_router_instance()

    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        assert get_learning_router_instance() is None

    def test_instantiation_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        with patch(
            "core.llm.learning_router_registry.learning_router_enabled",
            return_value=True,
        ), patch(
            "core.learning_llm_router.get_learning_router",
            side_effect=RuntimeError("boom"),
        ):
            assert get_learning_router_instance() is None

    def test_hydration_failure_still_returns_router(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        fake = type("FakeRouter", (), {"load_feedback_from_db": lambda self: 1 / 0})()
        with patch(
            "core.llm.learning_router_registry.learning_router_enabled",
            return_value=True,
        ), patch("core.learning_llm_router.get_learning_router", return_value=fake):
            assert get_learning_router_instance() is fake

    def test_singleton_cached_across_calls(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        fake = type("FakeRouter", (), {"load_feedback_from_db": lambda self: 0})()
        with patch(
            "core.llm.learning_router_registry.learning_router_enabled",
            return_value=True,
        ), patch("core.learning_llm_router.get_learning_router", return_value=fake):
            first = get_learning_router_instance()
            second = get_learning_router_instance()
        assert first is second is fake

    def test_double_checked_locking_inner_hit(self, monkeypatch):
        # _SINGLETON already built (e.g. by another thread between the first
        # check and the lock): the inner check returns it without re-instantiating.
        import threading

        import core.llm.learning_router_registry as reg

        sentinel = object()

        class SetOnAcquire:
            def __init__(self):
                self._lock = threading.Lock()

            def __enter__(self):
                self._lock.acquire()
                reg._SINGLETON = sentinel
                return self

            def __exit__(self, *exc):
                self._lock.release()
                return False

        monkeypatch.setattr(reg, "_LOCK", SetOnAcquire())
        with patch("core.llm.learning_router_registry.learning_router_enabled",
                   return_value=True):
            assert get_learning_router_instance() is sentinel

    def test_reset_drops_singleton(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        fake = type("FakeRouter", (), {"load_feedback_from_db": lambda self: 0})()
        with patch(
            "core.llm.learning_router_registry.learning_router_enabled",
            return_value=True,
        ), patch("core.learning_llm_router.get_learning_router", return_value=fake):
            assert get_learning_router_instance() is fake
            reset_learning_router_instance()
            assert get_learning_router_instance() is fake  # rebuilt fresh

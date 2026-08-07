"""
Coverage-push tests for core/learning_llm_router.py,
core/llm/routing/per_model_router.py and core/llm/response_quality.py.

Covers the EMA/scoring blend, decision stash/consume, DB hydration,
per-model predictor training/inference/persistence, and quality assessment.
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.learning_llm_router import (
    LearningBasedRouter,
    ModelCapability,
    ModelSpec,
    RoutingFeedback,
    RoutingRequest,
    _check_cost_within_budget,
    get_learning_router,
)
from core.llm.response_quality import assess_response_quality
from core.llm.routing.per_model_router import PerModelRouter, get_per_model_router
from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.routellm_trainer import (
    ModelType,
    TrainingConfig,
    TrainingStatus,
)


def make_request(**over):
    return RoutingRequest(
        tenant_id=over.get("tenant_id", "tenant-1"),
        task_type=over.get("task_type", "question_answering"),
        estimated_tokens=over.get("estimated_tokens", 1000),
        requires_quality=over.get("requires_quality", False),
        requires_reasoning=over.get("requires_reasoning", False),
        requires_vision=over.get("requires_vision", False),
        max_latency_ms=over.get("max_latency_ms"),
        budget_limit=over.get("budget_limit"),
        user_preferences=over.get("user_preferences", {}),
        conversation_context=over.get("conversation_context", {}),
    )


def make_feedback(**over):
    return RoutingFeedback(
        routing_result_id=over.get("routing_result_id", "rid-1"),
        tenant_id=over.get("tenant_id", "tenant-1"),
        model_id=over.get("model_id", "gpt-4o"),
        task_type=over.get("task_type", "question_answering"),
        success=over.get("success", True),
        quality_satisfied=over.get("quality_satisfied", True),
        cost_within_budget=over.get("cost_within_budget", True),
        user_satisfaction=over.get("user_satisfaction", 1.0),
        actual_cost=over.get("actual_cost"),
        actual_latency_ms=over.get("actual_latency_ms"),
        timestamp=over.get("timestamp", datetime.now(timezone.utc)),
    )


def make_example(satisfaction, model="m1", weight=1.0, task="code_generation"):
    return TrainingExample(
        estimated_tokens=200,
        task_type=task,
        prompt_features={
            "log_tokens": math.log2(201),
            "token_bucket": 1.0,
            "task_code": 1.0 if task == "code_generation" else 0.0,
            "task_analysis": 0.0,
            "task_reasoning": 0.0,
            "task_chat": 0.0,
            "task_general": 0.0,
            "has_code": 1.0 if task == "code_generation" else 0.0,
            "has_numbers": 0.0,
            "avg_word_length": 5.0,
        },
        chosen_model=model,
        user_satisfaction=satisfaction,
        was_successful=satisfaction >= 0.5,
        quality_score=satisfaction,
        weight=weight,
    )


class TestCheckCostWithinBudget:
    """Module-level budget check."""

    def test_none_cost_within_budget(self):
        assert _check_cost_within_budget("t", None) is True

    def test_tracker_says_exceeded(self):
        tracker = Mock()
        tracker.is_budget_exceeded.return_value = True
        with patch.dict("sys.modules", {"core.llm_usage_tracker": SimpleNamespace(
            llm_usage_tracker=tracker
        )}):
            assert _check_cost_within_budget("t", 0.5) is False

    def test_tracker_unavailable_returns_true(self):
        with patch.dict("sys.modules", {"core.llm_usage_tracker": None}):
            assert _check_cost_within_budget("t", 0.5) is True


class TestRouteFallbacks:
    """route() fallback and constraint paths."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    async def test_no_candidates_falls_back_to_cheapest(self, router):
        with patch.object(router, "_filter_by_capabilities", return_value=[]):
            result = await router.route(make_request())
        assert result.selected_model.model_id == "gemini-2.5-flash"
        assert result.confidence == 0.3
        assert "fallback" in result.reasoning

    async def test_no_candidates_after_cost_filter(self, router):
        request = make_request(requires_quality=True, budget_limit=1e-12)
        result = await router.route(request)
        assert result.selected_model is not None
        assert result.confidence == 0.4

    async def test_no_candidates_after_latency_filter(self, router):
        request = make_request(requires_quality=True, max_latency_ms=10)
        result = await router.route(request)
        assert result.confidence == 0.4

    async def test_latency_filter_skips_zero_speed(self, router):
        model = ModelSpec(
            model_id="zero", provider="x", model_name="zero",
            capabilities=set(), cost_per_million=1.0, quality_score=0.5,
            speed_score=0.0, context_window=100, supports_cache=False,
            tier="standard",
        )
        assert router._filter_by_latency([model], 500) == []

    async def test_route_success_sets_alternatives_and_elapsed(self, router):
        request = make_request()
        with patch.object(router, "_score_candidates", return_value=[
            (router._model_registry["gpt-4o"], 0.99),
            (router._model_registry["gpt-4o-mini"], 0.5),
            (router._model_registry["gemini-2.5-flash"], 0.4),
            (router._model_registry["deepseek-chat"], 0.3),
        ]), patch.object(router, "_create_routing_result", wraps=router._create_routing_result):
            result = await router.route(request)
        assert result.selected_model.model_id == "gpt-4o"
        assert result.confidence == 0.99
        assert len(result.alternatives) == 3
        assert result.routing_time_ms < 10000
        assert result.routing_result_id
        assert result.prompt_features["task_general"] == 0.0


class TestScoringBlend:
    """EMA normalization, quality term, combined score."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    def test_ema_alpha_env_and_clamps(self, router):
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "0.5"}):
            assert router._ema_alpha() == 0.5
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "bogus"}):
            assert router._ema_alpha() == 0.2
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "0"}):
            assert router._ema_alpha() == 0.2
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "5"}):
            assert router._ema_alpha() == 1.0

    def test_ema_update_metric_seed_and_step(self, router):
        key = "t:t:m"
        router._ema_update_metric(key, "success", 1.0, 0.2)
        assert router._ema_scores[key]["success"] == 1.0
        assert router._ema_scores[key]["success_n"] == 1
        router._ema_update_metric(key, "success", 0.0, 0.2)
        assert router._ema_scores[key]["success"] == pytest.approx(0.8)
        assert router._ema_scores[key]["success_n"] == 2
        assert router._ema_corrected(router._ema_scores[key], "success", 0.2) == pytest.approx(0.8)
        assert router._ema_corrected({}, "missing", 0.2) is None

    def test_ema_record_key_eviction(self, router):
        router._max_ema_keys = 2
        router._update_ema_scores(make_feedback(model_id="a"))
        router._update_ema_scores(make_feedback(model_id="b"))
        router._update_ema_scores(make_feedback(model_id="c"))
        keys = list(router._ema_scores.keys())
        assert "tenant-1:question_answering:a" not in keys
        assert len(keys) == 2

    def test_update_ema_scores_with_and_without_metrics(self, router):
        router._update_ema_scores(make_feedback(actual_latency_ms=150.0, actual_cost=0.01))
        router._update_ema_scores(make_feedback(actual_latency_ms=None, actual_cost=None))
        key = "tenant-1:question_answering:gpt-4o"
        assert router._ema_scores[key]["samples"] == 2
        assert router._ema_scores[key]["latency_n"] == 1
        assert router._ema_scores[key]["cost_n"] == 1
        assert router._ema_scores[key]["success"] == 1.0

    def test_ema_normalization_cold_fleet(self, router):
        models = [router._model_registry["gpt-4o"], router._model_registry["gemini-2.5-flash"]]
        norm = router._ema_normalization_baselines(models, make_request())
        assert norm["max_latency"] > 0
        assert norm["max_cost"] > 0

    def test_ema_normalization_observed_fleet(self, router):
        models = [router._model_registry["gpt-4o"], router._model_registry["gemini-2.5-flash"]]
        router._update_ema_scores(make_feedback(model_id="gpt-4o", actual_latency_ms=300.0, actual_cost=0.02))
        norm = router._ema_normalization_baselines(models, make_request())
        assert norm["max_latency"] == pytest.approx(300.0)
        assert norm["max_cost"] == pytest.approx(0.02)

    def test_ema_quality_term_cold_returns_none(self, router):
        model = router._model_registry["gpt-4o"]
        norm = router._ema_normalization_baselines([model], make_request())
        assert router._ema_quality_term(model, make_request(), norm) is None

    def test_ema_quality_term_hot(self, router):
        model = router._model_registry["gpt-4o"]
        router._update_ema_scores(make_feedback(model_id="gpt-4o", success=True,
                                                quality_satisfied=True,
                                                actual_latency_ms=100.0, actual_cost=0.01))
        request = make_request()
        norm = router._ema_normalization_baselines([model], request)
        term = router._ema_quality_term(model, request, norm)
        assert term is not None
        assert 0.0 <= term <= 1.0

    def test_combined_score_predictor_term(self, router):
        per_model = Mock()
        per_model.predict_satisfaction.return_value = 0.9
        per_model.confidence.return_value = 0.3
        model = router._model_registry["gpt-4o"]
        request = make_request()
        base = router._combined_model_score(
            model, request, {"quality": 0.4, "cost": 0.3, "speed": 0.3},
            per_model, {"x": 1.0}, {"max_latency": 1.0, "max_cost": 1.0}, 2.5,
        )
        with patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False):
            no_ema = router._combined_model_score(
                model, request, {"quality": 0.4, "cost": 0.3, "speed": 0.3},
                per_model, {"x": 1.0}, {"max_latency": 1.0, "max_cost": 1.0}, 2.5,
            )
        assert base == no_ema
        with patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=True), \
             patch.object(router, "_ema_quality_term", return_value=0.8):
            with_ema = router._combined_model_score(
                model, request, {"quality": 0.4, "cost": 0.3, "speed": 0.3},
                per_model, {"x": 1.0}, {"max_latency": 1.0, "max_cost": 1.0}, 2.5,
            )
        assert with_ema > base
        assert with_ema == pytest.approx(
            base + (1.0 - 0.3) * router._EMA_SCORE_WEIGHT * 0.8
        )

    def test_combined_score_capability_and_preference_bonuses(self, router):
        model = router._model_registry["gpt-4o"]
        request = make_request(
            estimated_tokens=100000, user_preferences={"preferred_model": "GPT-4O"},
        )
        with patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False):
            score = router._combined_model_score(
                model, request, {"quality": 0.4, "cost": 0.3, "speed": 0.3},
                None, None, {"max_latency": 1.0, "max_cost": 1.0}, 2.5,
            )
            score_no_bonus = router._combined_model_score(
                model, make_request(estimated_tokens=1000),
                {"quality": 0.4, "cost": 0.3, "speed": 0.3},
                None, None, {"max_latency": 1.0, "max_cost": 1.0}, 2.5,
            )
        assert score > score_no_bonus

    def test_score_candidates_sorts_descending(self, router):
        router._update_ema_scores(make_feedback(model_id="gpt-4o", success=True))
        models = [router._model_registry["gpt-4o"], router._model_registry["gpt-4o-mini"]]
        with patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False):
            scored = router._score_candidates(models, make_request())
        assert scored[0][1] >= scored[1][1]
        assert scored[0][0].model_id in {"gpt-4o", "gpt-4o-mini"}


class TestStashAndConsume:
    """Decision feature stash/consume with bounds."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    def test_stash_generates_id(self, router):
        fid = router.stash_decision({"a": 1.0})
        assert fid
        assert router.consume_decision(fid) == {"a": 1.0}
        assert router.consume_decision("missing") is None

    def test_stash_with_explicit_id(self, router):
        assert router.stash_decision({"a": 1.0}, decision_id="fixed") == "fixed"
        assert router.consume_decision("fixed") == {"a": 1.0}

    def test_stash_evicts_overflow(self, router):
        router._max_routing_decisions = 3
        router.stash_decision({"a": 1.0}, decision_id="1")
        router.stash_decision({"a": 1.0}, decision_id="2")
        router.stash_decision({"a": 1.0}, decision_id="3")
        router.stash_decision({"a": 1.0}, decision_id="4")
        assert router.consume_decision("1") is None
        assert router.consume_decision("4") == {"a": 1.0}

    def test_create_routing_result_stashes(self, router):
        model = router._model_registry["gpt-4o"]
        request = make_request(estimated_tokens=2000)
        result = router._create_routing_result(model, request, 0.9, "why", [], 0.0)
        assert result.routing_result_id
        assert router.consume_decision(result.routing_result_id)["log_tokens"] > 0

    def test_generate_reasoning_variants(self, router):
        model = router._model_registry["gpt-4o"]
        r1 = router._generate_reasoning(model, make_request(requires_quality=True), 0.8)
        assert "high quality" in r1
        r2 = router._generate_reasoning(
            model, make_request(budget_limit=10.0, max_latency_ms=5000), 0.5
        )
        assert "within budget" in r2
        assert "meets latency" in r2


class TestFeedbackPipeline:
    """record_feedback -> retrain -> weights."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    async def test_record_feedback_recovered_features_and_retrain(self, router):
        router.stash_decision({"log_tokens": 10.0, "avg_word_length": 6.0},
                              decision_id="rid-1")
        fb = make_feedback(routing_result_id="rid-1")
        with patch.object(router, "_persist_feedback", return_value=None), \
             patch.object(router, "_retrain_router", AsyncMock()) as retrain:
            await router.record_feedback(fb)
        assert getattr(fb, "_prompt_features", None) == {"log_tokens": 10.0, "avg_word_length": 6.0}
        retrain.assert_not_awaited()  # under _min_samples_per_model

    async def test_record_feedback_preference_cap(self, router):
        router._max_preference_data_per_key = 2
        for i in range(3):
            await router.record_feedback(make_feedback(routing_result_id=f"r{i}"))
        key = "tenant-1:question_answering"
        assert len(router._preference_data[key]) == 2
        assert router._preference_data[key][0].routing_result_id == "r1"

    async def test_retrain_trains_predictors_and_weights(self, router):
        router._min_samples_per_model = 2
        for i in range(2):
            await router.record_feedback(make_feedback(model_id="gpt-4o"))
        key = "tenant-1:question_answering"
        per_model = router._per_model_routers[key]
        with patch.object(per_model, "train") as train:
            await router._retrain_router("tenant-1", "question_answering")
        train.assert_called_once()
        assert key in router._router_cache

    async def test_retrain_no_feedback_returns(self, router):
        await router._retrain_router("t", "noop")
        assert "t:noop" not in router._router_cache

    async def test_retrain_per_model_failure_logged(self, router):
        router._min_samples_per_model = 1
        await router.record_feedback(make_feedback(model_id="gpt-4o"))
        key = "tenant-1:question_answering"
        per_model = router._per_model_routers[key]
        with patch.object(per_model, "train", side_effect=RuntimeError("train boom")):
            await router._retrain_router("tenant-1", "question_answering")
        assert key in router._router_cache

    def test_derive_weights_from_success(self, router):
        w = router._derive_weights_from_success(
            {"m1": {"success": 2, "total": 2}}, "code_generation"
        )
        assert w["quality"] > 0.5
        assert abs(w["quality"] + w["cost"] + w["speed"] - 1.0) < 1e-9
        w2 = router._derive_weights_from_success({}, "question_answering")
        assert w2 == {"quality": 0.4, "cost": 0.3, "speed": 0.3}
        w3 = router._derive_weights_from_success(
            {"m1": {"success": 0, "total": 2}}, "reasoning"
        )
        assert w3["quality"] < 0.6

    def test_set_cached_weights_evicts(self, router):
        router._max_router_cache_size = 2
        router._set_cached_weights("a:t", {"q": 1}, "a")
        router._set_cached_weights("b:t", {"q": 1}, "b")
        router._set_cached_weights("c:t", {"q": 1}, "c")
        assert len(router._router_cache) == 2
        assert "a:t" not in router._router_cache

    def test_get_learned_weights_cached(self, router):
        router._router_cache["tenant-1:code_generation"] = {"quality": 0.9}
        assert router._get_learned_weights("code_generation", "tenant-1")["quality"] == 0.9
        assert router._get_learned_weights("unknown_task", "t")["quality"] == 0.4


class TestPersistence:
    """DB write-through and hydration."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    def test_persist_feedback_db_failure_swallowed(self, router):
        class Boom:
            def __enter__(self):
                raise RuntimeError("db down")

            def __exit__(self, *a):
                return False

        with patch("core.learning_llm_router.get_db_session", return_value=Boom()):
            router._persist_feedback(make_feedback(), {"a": 1.0})

    def test_resolve_feedback_context_found(self, router):
        row = SimpleNamespace(task_type="code_generation", routing_result_id="rid-9")
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = row
        db.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            task, rid = router.resolve_feedback_context("t", "m")
        assert (task, rid) == ("code_generation", "rid-9")

    def test_resolve_feedback_context_missing_and_error(self, router):
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = None
        db.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            assert router.resolve_feedback_context("t", "m") == (None, None)
        cm.__enter__.side_effect = RuntimeError("secret")
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            assert router.resolve_feedback_context("t", "m") == (None, None)

    def _make_row(self, **over):
        return SimpleNamespace(
            routing_result_id=over.get("routing_result_id", "rid"),
            tenant_id=over.get("tenant_id", "tenant-1"),
            task_type=over.get("task_type", "question_answering"),
            model_id=over.get("model_id", "gpt-4o"),
            success=over.get("success", True),
            quality_satisfied=over.get("quality_satisfied", True),
            cost_within_budget=True,
            user_satisfaction=0.9,
            actual_cost=0.01,
            actual_latency_ms=100.0,
            created_at=datetime.now(timezone.utc),
            prompt_features=over.get("prompt_features"),
        )

    def test_load_feedback_from_db(self, router):
        rows = [
            self._make_row(routing_result_id="r1", model_id="gpt-4o",
                           prompt_features={"log_tokens": 5.0}),
            self._make_row(routing_result_id="r2", model_id="deepseek-chat"),
        ]
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = rows
        db.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            loaded = router.load_feedback_from_db("tenant-1")
        assert loaded == 2
        key = "tenant-1:question_answering"
        assert len(router._preference_data[key]) == 2
        assert getattr(router._preference_data[key][0], "_prompt_features") == {"log_tokens": 5.0}
        ema_key = "tenant-1:question_answering:gpt-4o"
        assert router._ema_scores[ema_key]["samples"] == 1

    def test_load_feedback_from_db_empty_and_error(self, router):
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            assert router.load_feedback_from_db() == 0
        cm.__enter__.side_effect = RuntimeError("secret")
        with patch("core.learning_llm_router.get_db_session", return_value=cm):
            assert router.load_feedback_from_db() == 0

    def test_get_per_model_router_lazy_and_bounded(self, router):
        with patch("core.learning_llm_router.PerModelRouter") as PMR:
            pmr = PMR.return_value
            assert router._get_per_model_router("t:task") is pmr
            assert router._get_per_model_router("t:task") is pmr
            PMR.assert_called_once()
            pmr.load_all.assert_called_once()
        router._max_per_model_routers = 1
        with patch("core.learning_llm_router.PerModelRouter") as PMR:
            PMR.return_value.load_all.side_effect = RuntimeError("no pkls")
            router._per_model_routers["t2:task"] = Mock()
            router._get_per_model_router("t3:task")
            assert "t2:task" not in router._per_model_routers

    def test_get_per_model_router_load_error_tolerated(self, router):
        with patch("core.learning_llm_router.PerModelRouter") as PMR:
            PMR.return_value.load_all.side_effect = RuntimeError("corrupt")
            assert router._get_per_model_router("t:task") is not None


class TestFeatureExtraction:
    """Prompt feature extraction helpers."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    def test_extract_request_features_defaults(self, router):
        f = router._extract_request_features(make_request(task_type="reasoning",
                                                          estimated_tokens=1000,
                                                          requires_reasoning=True))
        assert f["log_tokens"] == pytest.approx(math.log2(1001))
        assert f["task_reasoning"] == 1.0
        assert f["has_numbers"] == 1.0
        assert f["avg_word_length"] == 5.0
        assert f["token_bucket"] == 2.0

    def test_extract_request_features_from_context(self, router):
        request = make_request(
            task_type="question_answering",
            conversation_context={
                "prompt_text": "```python\nx=1\n```",
                "has_code": 1.0, "has_numbers": 0.0,
                "avg_word_length": 4.2,
            },
        )
        f = router._extract_request_features(request)
        assert f["has_code"] == 1.0
        assert f["has_numbers"] == 0.0
        assert f["avg_word_length"] == 4.2
        request2 = make_request(
            task_type="question_answering",
            conversation_context={"prompt_text": "write me a script please thanks"},
        )
        f2 = router._extract_request_features(request2)
        assert f2["has_code"] == 0.0
        assert f2["avg_word_length"] > 4.0

    def test_token_bucket_boundaries(self, router):
        assert router._token_bucket(1) == 0.0
        assert router._token_bucket(100) == 1.0
        assert router._token_bucket(500) == 2.0
        assert router._token_bucket(2000) == 3.0
        assert router._token_bucket(5000) == 4.0

    def test_task_default_features(self, router):
        f = router._task_default_features("extraction")
        assert f["task_analysis"] == 1.0
        assert f["token_bucket"] == 1.0
        f2 = router._task_default_features("bogus")
        assert f2["task_general"] == 1.0

    def test_feedback_to_training_example(self, router):
        fb = make_feedback(user_satisfaction=0.8)
        fb._prompt_features = {"log_tokens": 6.0, "avg_word_length": 5.0}
        ex = router._feedback_to_training_example(fb, "question_answering")
        assert ex.user_satisfaction == 0.8
        assert ex.estimated_tokens == 63
        assert ex.chosen_model == "gpt-4o"
        fb2 = make_feedback(user_satisfaction=None, success=False, quality_satisfied=False)
        ex2 = router._feedback_to_training_example(fb2, "code_generation")
        assert ex2.user_satisfaction == 0.0
        assert ex2.prompt_features["task_code"] == 1.0
        assert ex2.estimated_tokens == 0


class TestStatisticsAndExport:
    """Statistics, export, registry updates."""

    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    async def test_get_routing_statistics_full(self, router):
        await router.record_feedback(make_feedback())
        await router.record_feedback(make_feedback(tenant_id="other-tenant"))
        with patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=True):
            stats = await router.get_routing_statistics("tenant-1")
        assert stats["feedback_samples"] == 1
        assert stats["ema_enabled"] is True
        assert "question_answering:gpt-4o" in stats["ema_scores"]
        assert "other-tenant" not in json.dumps(stats["ema_scores"])
        assert stats["model_success_rates"]["gpt-4o"] == 1.0

    async def test_export_routing_data_filters_old(self, router):
        old = datetime.now(timezone.utc) - timedelta(days=400)
        await router.record_feedback(make_feedback(routing_result_id="old", timestamp=old))
        await router.record_feedback(make_feedback(routing_result_id="new"))
        export = await router.export_routing_data("tenant-1", days=30)
        assert len(export["routing_feedback"]) == 1
        assert export["routing_feedback"][0]["model_id"] == "gpt-4o"
        export2 = await router.export_routing_data("other", days=30)
        assert export2["routing_feedback"] == []

    def test_update_model_registry_variants(self, router):
        assert router.update_model_registry([{"provider": "x"}]) == 0
        added = router.update_model_registry([{
            "model_id": "new-model",
            "provider": "x",
            "capabilities": ["code_generation", "bogus_cap"],
            "cost_per_million": 0.1,
        }])
        assert added == 1
        assert ModelCapability.CODE_GENERATION in router._model_registry["new-model"].capabilities
        updated = router.update_model_registry([{
            "model_id": "new-model", "provider": "y",
            "cost_per_million": 0.2,
        }])
        assert updated == 0
        assert router._model_registry["new-model"].provider == "y"

    def test_load_local_models_into_registry(self, router):
        provider = SimpleNamespace(id="p1", provider_type="ollama", name="Local",
                                   workspace_id="default", is_active=True)
        cap = SimpleNamespace(model_id="llama3", supports_tools=True,
                              supports_vision=False, supports_reasoning=True,
                              quality_score=0.6, speed_score=0.7,
                              context_window=8192)
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = [provider]
        db.query.return_value = q
        q2 = Mock()
        q2.filter.return_value = q2
        q2.all.side_effect = [[cap], [provider], []]
        db2 = Mock()
        db2.query.side_effect = [q, q2]
        cm = MagicMock()
        cm.__enter__.return_value = db2
        # load_local_models_into_registry imports get_db_session locally.
        with patch("core.database.get_db_session", return_value=cm):
            n = router.load_local_models_into_registry()
        assert n >= 1
        assert "llama3" in router._model_registry

    def test_load_local_models_error_and_no_providers(self, router):
        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("secret")
        with patch("core.database.get_db_session", return_value=cm):
            assert router.load_local_models_into_registry() == 0

    def test_get_learning_router_factory(self):
        router = get_learning_router(Mock())
        assert isinstance(router, LearningBasedRouter)


class TestPerModelRouter:
    """Per-model satisfaction predictors: train/infer/persist."""

    @pytest.fixture
    def config(self, tmp_path):
        return TrainingConfig(model_path=str(tmp_path), n_estimators=5, max_depth=3)

    def test_init_creates_model_dir(self, config, tmp_path):
        router = PerModelRouter(config)
        assert (tmp_path / "per_model").exists()
        assert router.config is config

    def test_train_random_forest_multi_class(self, config):
        router = PerModelRouter(config)
        examples = [make_example(1.0), make_example(1.0), make_example(0.0),
                    make_example(0.0), make_example(1.0), make_example(0.0)]
        result = router.train("m1", examples)
        assert result.status == TrainingStatus.COMPLETED
        assert result.accuracy > 0.0
        assert router.has_predictor("m1")
        stats = router.predictor_stats("m1")
        assert stats.samples == 6
        assert stats.classes == [0, 1]

    def test_train_single_class_uses_observed_rate(self, config):
        router = PerModelRouter(config)
        examples = [make_example(1.0) for _ in range(5)]
        result = router.train("allgood", examples)
        assert result.status == TrainingStatus.COMPLETED
        assert router.predictors["allgood"] is None
        assert router.predict_satisfaction("allgood", {}) == 1.0

    def test_train_single_class_zeros(self, config):
        router = PerModelRouter(config)
        examples = [make_example(0.0) for _ in range(4)]
        result = router.train("allbad", examples)
        assert result.status == TrainingStatus.COMPLETED
        assert router.predict_satisfaction("allbad", {}) == 0.0

    def test_train_empty_examples_fails(self, config):
        router = PerModelRouter(config)
        result = router.train("m", [])
        assert result.status == TrainingStatus.FAILED

    def test_train_logistic(self, config):
        cfg_lr = TrainingConfig(model_type=ModelType.LOGISTIC_REGRESSION,
                                model_path=str(config.model_path))
        router = PerModelRouter(cfg_lr)
        examples = [make_example(1.0), make_example(0.0)] * 6
        assert router.train("lr", examples).status == TrainingStatus.COMPLETED

    def test_create_estimator_variants(self, config):
        """Every _create_estimator branch constructs the right estimator.

        NOTE: we assert on construction, not fit: fitting MLP/Voting under
        coverage instrumentation trips a numpy 2.x dtype-pickle incompat
        (see pre-existing test_routing_db_persistence crash tests), so the
        fit paths are exercised only in non-coverage runs.
        """
        from sklearn.ensemble import RandomForestClassifier, VotingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.neural_network import MLPClassifier

        base = str(config.model_path)
        rf = PerModelRouter(TrainingConfig(model_path=base))
        assert isinstance(rf._create_estimator(), RandomForestClassifier)
        lr = PerModelRouter(TrainingConfig(model_type=ModelType.LOGISTIC_REGRESSION,
                                           model_path=base))
        assert isinstance(lr._create_estimator(), LogisticRegression)
        mlp = PerModelRouter(TrainingConfig(model_type=ModelType.NEURAL_NETWORK,
                                            model_path=base))
        assert isinstance(mlp._create_estimator(), MLPClassifier)
        ens = PerModelRouter(TrainingConfig(model_type=ModelType.ENSEMBLE,
                                            model_path=base))
        assert isinstance(ens._create_estimator(), VotingClassifier)

    def test_predict_satisfaction_cold_start(self, config):
        router = PerModelRouter(config)
        assert router.predict_satisfaction("nope", {}) is None
        assert router.confidence("nope") == 0.0

    def test_predict_satisfaction_proba_path(self, config):
        router = PerModelRouter(config)
        examples = [make_example(1.0), make_example(0.0)] * 6
        router.train("m", examples)
        proba = router.predict_satisfaction("m", {"avg_word_length": 5.0})
        assert proba is not None
        assert 0.0 <= proba <= 1.0

    def test_predict_satisfaction_no_positive_class(self, config):
        router = PerModelRouter(config)
        class Fake:
            classes_ = [0]

            def predict_proba(self, v):
                return [[0.9, 0.1]]

        router.predictors["m"] = Fake()
        router.stats["m"] = SimpleNamespace(positive_rate=0.5)
        assert router.predict_satisfaction("m", {}) == 0.0

    def test_predict_satisfaction_without_proba(self, config):
        router = PerModelRouter(config)
        class Fake:
            classes_ = [0, 1]

            def predict(self, v):
                return [1]

        router.predictors["m"] = Fake()
        router.stats["m"] = SimpleNamespace(positive_rate=0.5)
        assert router.predict_satisfaction("m", {}) == 1.0

    def test_confidence_scales_with_samples(self, config):
        router = PerModelRouter(config)
        router.stats["m"] = SimpleNamespace(samples=50)
        assert router.confidence("m") == pytest.approx(0.3)
        router.stats["m"].samples = 10
        assert router.confidence("m") == pytest.approx(0.06)

    def test_save_and_load_roundtrip(self, config):
        router = PerModelRouter(config)
        examples = [make_example(1.0), make_example(0.0)] * 6
        router.train("roundtrip", examples)
        router2 = PerModelRouter(config)
        loaded = router2.load_all()
        assert loaded == 1
        assert router2.has_predictor("roundtrip")
        proba = router2.predict_satisfaction("roundtrip", {"avg_word_length": 5.0})
        assert proba is not None

    def test_load_all_handles_corrupt_meta(self, config):
        router = PerModelRouter(config)
        (Path(config.model_path) / "per_model" / "bad.json").write_text("{not json")
        assert router.load_all() == 0

    def test_factory(self, config):
        assert isinstance(get_per_model_router(config), PerModelRouter)


class TestResponseQualityExtra:
    """Remaining response_quality branches."""

    def test_exception_classification_variants(self):
        assert "context_length" in assess_response_quality(
            content=None, exception=Exception("maximum context length exceeded")
        ).issues
        assert "auth_error" in assess_response_quality(
            content=None, exception=PermissionError("invalid api key")
        ).issues
        assert "network_error" in assess_response_quality(
            content=None, exception=ConnectionError("network unreachable")
        ).issues
        assert "provider_error" in assess_response_quality(
            content=None, exception=ValueError("something odd")
        ).issues

    def test_long_content_diminishes_score(self):
        q = assess_response_quality(content="x" * 9000, finish_reason="stop")
        assert q.quality_score == pytest.approx(0.78)

    def test_truncation_empty_content_scoring(self):
        assert assess_response_quality(content="", finish_reason="length").quality_score == 0.1
        assert assess_response_quality(content="some", finish_reason="length").quality_score == 0.3

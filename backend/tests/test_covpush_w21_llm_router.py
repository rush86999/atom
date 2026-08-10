"""Coverage wave 21 — core/learning_llm_router uncovered branches (TDD).

Covers missed lines after the pre-existing router suite:
- _check_cost_within_budget edge paths
- route() fallback paths (no candidates / no constraint match)
- EMA family: _ema_alpha env edge, _ema_update_metric init/step,
  _ema_corrected miss, _ema_record_key eviction, _update_ema_scores
  latency/cost absence, _ema_quality_term cold/history paths,
  _ema_normalization_baselines cold/observed paths, _combined_model_score
  tenant-pref + long-context + budget boosts
- stash/consume decisions (overflow eviction, explicit id)
- record_feedback recovery + preference cap
- _retrain_router train success/skip paths
- _persist_feedback failure tolerance
- resolve_feedback_context / load_feedback_from_db (tenant filter, empty)
- _get_per_model_router lazy-create + eviction
- _extract_request_features content-signal branches
- _token_bucket all buckets, _task_default_features
- _feedback_to_training_example recovered/default + satisfaction fallback
- _derive_weights_from_success (zero samples, scaled quality)
- _set_cached_weights eviction
- get_routing_statistics EMA scoping + tenant filtering
- update_model_registry (missing id, enum-value caps, update path)
- load_local_models_into_registry (caps path, no-caps path, error)
- export_routing_data tenant + cutoff filtering
- get_learning_router factory
"""
import os
from datetime import datetime, timedelta, timezone
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


@pytest.fixture
def router():
    r = LearningBasedRouter(Mock())
    r._preference_data.clear()
    r._ema_scores.clear()
    r._ema_key_order.clear()
    r._router_cache.clear()
    r._routing_decisions.clear()
    r._per_model_routers.clear()
    return r


def _request(**kw):
    defaults = dict(
        tenant_id="tenant-1", task_type="question_answering", estimated_tokens=1000
    )
    defaults.update(kw)
    return RoutingRequest(**defaults)


def _feedback(**kw):
    defaults = dict(
        routing_result_id="r1", tenant_id="tenant-1", model_id="gpt-4o-mini",
        task_type="question_answering", success=True, quality_satisfied=True,
        cost_within_budget=True,
    )
    defaults.update(kw)
    return RoutingFeedback(**defaults)


class TestBudgetCheck:
    def test_budget_check_within(self):
        assert _check_cost_within_budget("t1", 0.01) is True

    def test_budget_check_none_cost(self):
        assert _check_cost_within_budget("t1", None) is True

    def test_budget_check_over(self, router):
        with patch("core.llm_usage_tracker.llm_usage_tracker.is_budget_exceeded", return_value=True):
            assert _check_cost_within_budget("t1", 100.0) is False

    def test_budget_check_tracker_unavailable(self, router):
        with patch("core.llm_usage_tracker.llm_usage_tracker.is_budget_exceeded", side_effect=RuntimeError("no tracker")):
            assert _check_cost_within_budget("t1", 100.0) is True


class TestRouteFallbacks:
    async def test_route_no_candidates_fallback(self, router):
        with patch.object(router, "_filter_by_capabilities", return_value=[]):
            result = await router.route(_request(requires_vision=True))
        assert result.selected_model is not None
        assert result.confidence == 0.3

    async def test_route_constraint_empties_candidates(self, router):
        candidates = list(router._model_registry.values())
        with patch.object(router, "_filter_by_capabilities", return_value=candidates):
            with patch.object(router, "_filter_by_latency", return_value=[]):
                result = await router.route(_request(max_latency_ms=1))
        assert result.selected_model is not None
        assert result.confidence == 0.4

    async def test_route_score_clamped_and_reasoning(self, router):
        request = _request(
            requires_quality=True, budget_limit=0.5, max_latency_ms=5000,
            estimated_tokens=100000,
            conversation_context={"prompt_text": "```python\nx=1\n``` with 123"},
        )
        result = await router.route(request)
        assert 0.0 <= result.confidence <= 1.0
        assert result.routing_time_ms >= 0
        assert result.routing_result_id
        assert result.prompt_features["has_code"] == 1.0

    async def test_route_tenant_preference_boost(self, router):
        request = _request(user_preferences={"preferred_model": "gpt-4o-mini"})
        result = await router.route(request)
        assert result.selected_model is not None


class TestEmaFamily:
    def test_ema_alpha_env_valid(self, router):
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "0.7"}, clear=False):
            assert router._ema_alpha() == 0.7

    def test_ema_alpha_env_invalid(self, router):
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "abc"}, clear=False):
            assert router._ema_alpha() == 0.2

    def test_ema_alpha_env_zero(self, router):
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "0"}, clear=False):
            assert router._ema_alpha() == 0.2

    def test_ema_alpha_env_over_one(self, router):
        with patch.dict(os.environ, {"ATOM_EMA_ALPHA": "5"}, clear=False):
            assert router._ema_alpha() == 1.0

    def test_ema_update_metric_init(self, router):
        router._ema_scores["k"] = {}
        router._ema_update_metric("k", "success", 1.0, 0.2)
        assert router._ema_scores["k"]["success"] == 1.0
        assert router._ema_scores["k"]["success_n"] == 1

    def test_ema_update_metric_step(self, router):
        router._ema_scores["k"] = {"success": 1.0, "success_n": 1}
        router._ema_update_metric("k", "success", 0.0, 0.2)
        assert router._ema_scores["k"]["success"] == 0.8
        assert router._ema_scores["k"]["success_n"] == 2

    def test_ema_corrected_missing(self, router):
        assert router._ema_corrected({}, "latency", 0.2) is None

    def test_ema_record_key_eviction(self, router):
        for i in range(router._max_ema_keys + 5):
            router._ema_record_key(f"key-{i}")
        assert len(router._ema_scores) <= router._max_ema_keys
        assert "key-0" not in router._ema_scores

    def test_update_ema_scores_without_latency_cost(self, router):
        router._update_ema_scores(_feedback(actual_latency_ms=None, actual_cost=None))
        key = "tenant-1:question_answering:gpt-4o-mini"
        assert router._ema_scores[key]["samples"] == 1
        assert "latency" not in router._ema_scores[key]
        assert "cost" not in router._ema_scores[key]

    def test_update_ema_scores_full(self, router):
        router._update_ema_scores(_feedback(actual_latency_ms=150.0, actual_cost=0.01))
        key = "tenant-1:question_answering:gpt-4o-mini"
        assert router._ema_scores[key]["latency"] == 150.0
        assert router._ema_scores[key]["cost"] == 0.01
        assert router._ema_scores[key]["success"] == 1.0

    def test_ema_quality_term_cold_returns_none(self, router):
        model = router._model_registry["gpt-4o-mini"]
        term = router._ema_quality_term(
            model, _request(), {"max_latency": 1000.0, "max_cost": 0.1}
        )
        assert term is None

    def test_ema_quality_term_with_history(self, router):
        model = router._model_registry["gpt-4o-mini"]
        key = f"tenant-1:question_answering:{model.model_id}"
        router._ema_scores[key] = {
            "samples": 2, "success": 0.8, "latency": 200.0, "cost": 0.02,
        }
        term = router._ema_quality_term(
            model, _request(), {"max_latency": 1000.0, "max_cost": 0.1}
        )
        assert term is not None
        assert 0.0 <= term <= 1.0

    def test_ema_normalization_baselines_cold(self, router):
        request = _request(estimated_tokens=1000)
        result = router._ema_normalization_baselines(
            list(router._model_registry.values()), request
        )
        assert result["max_latency"] > 0
        assert result["max_cost"] > 0

    def test_ema_normalization_baselines_observed(self, router):
        request = _request(estimated_tokens=1000)
        model = router._model_registry["gpt-4o-mini"]
        key = f"tenant-1:question_answering:{model.model_id}"
        router._ema_scores[key] = {"samples": 1, "latency": 300.0, "cost": 0.05}
        result = router._ema_normalization_baselines(
            [model, router._model_registry["gpt-4o"]], request
        )
        assert result["max_latency"] == 300.0
        assert result["max_cost"] == 0.05

    def test_combined_score_boosts(self, router):
        model = router._model_registry["gpt-4o"]
        request = _request(
            requires_quality=True, budget_limit=0.5, max_latency_ms=5000,
            estimated_tokens=100000,
            user_preferences={"preferred_model": "gpt-4o"},
        )
        weights = {"quality": 0.4, "cost": 0.3, "speed": 0.2}
        score = router._combined_model_score(
            model, request, weights, None, None,
            {"max_latency": 1000.0, "max_cost": 0.5}, 2.5,
        )
        assert score > 0.5


class TestDecisionStore:
    def test_stash_decision_generates_id(self, router):
        rid = router.stash_decision({"a": 1.0})
        assert rid
        assert router._routing_decisions[rid] == {"a": 1.0}

    def test_stash_decision_eviction(self, router):
        for i in range(router._max_routing_decisions + 3):
            router.stash_decision({"i": float(i)})
        assert len(router._routing_decisions) <= router._max_routing_decisions

    def test_consume_decision_missing(self, router):
        assert router.consume_decision("nope") is None

    def test_consume_decision_found(self, router):
        router.stash_decision({"b": 2.0}, decision_id="abc")
        assert router.consume_decision("abc") == {"b": 2.0}


class TestFeedbackPipeline:
    async def test_record_feedback_recovers_features(self, router):
        router.stash_decision({"log_tokens": 10.0}, decision_id="r1")
        await router.record_feedback(_feedback(routing_result_id="r1"))
        key = "tenant-1:question_answering"
        assert router._preference_data[key][0]._prompt_features["log_tokens"] == 10.0

    async def test_record_feedback_cap_eviction(self, router):
        router._max_preference_data_per_key = 3
        for i in range(6):
            await router.record_feedback(_feedback(routing_result_id=f"r{i}"))
        key = "tenant-1:question_answering"
        assert len(router._preference_data[key]) == 3

    async def test_retrain_trains_predictor(self, router):
        router._min_samples_per_model = 3
        for i in range(3):
            await router.record_feedback(_feedback(
                model_id="gpt-4o-mini", routing_result_id=f"r{i}",
                success=True, quality_satisfied=True,
            ))
        cache_key = "tenant-1:question_answering"
        assert cache_key in router._router_cache
        assert cache_key in router._per_model_routers

    async def test_retrain_skips_model_below_threshold(self, router):
        router._preference_data["tenant-1:code_generation"] = [
            _feedback(model_id="m1", task_type="code_generation") for _ in range(1)
        ]
        router._min_samples_per_model = 5
        router._router_cache.clear()
        await router._retrain_router("tenant-1", "code_generation")
        assert "tenant-1:code_generation" in router._router_cache

    async def test_retrain_no_feedback_returns(self, router):
        await router._retrain_router("tenant-1", "empty")
        assert "tenant-1:empty" not in router._router_cache

    def test_persist_feedback_error_tolerated(self, router):
        with patch("core.learning_llm_router.get_db_session", side_effect=RuntimeError("boom")):
            router._persist_feedback(_feedback(), {"log_tokens": 1.0})
        # no exception -> passes

    def test_build_feedback_maps_quality(self, router):
        quality = SimpleNamespace(
            success=True, quality_satisfied=True, quality_score=0.8,
        )
        fb = router.build_feedback("rid", "t1", "m1", "task", quality,
                                   actual_cost=0.01, actual_latency_ms=100.0)
        assert fb.user_satisfaction == 0.8
        assert fb.success is True
        assert fb.actual_latency_ms == 100.0

    def test_resolve_feedback_context_found(self, router):
        row = SimpleNamespace(task_type="code_generation", routing_result_id="xyz")
        with patch("core.learning_llm_router.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
            task_type, rid = router.resolve_feedback_context("t1", "m1")
        assert (task_type, rid) == ("code_generation", "xyz")

    def test_resolve_feedback_context_missing(self, router):
        with patch("core.learning_llm_router.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
            task_type, rid = router.resolve_feedback_context("t1", "m1")
        assert (task_type, rid) == (None, None)

    def test_resolve_feedback_context_error(self, router):
        with patch("core.learning_llm_router.get_db_session", side_effect=RuntimeError("boom")):
            task_type, rid = router.resolve_feedback_context("t1", "m1")
        assert (task_type, rid) == (None, None)

    def test_load_feedback_from_db_tenant_filter(self, router):
        row = SimpleNamespace(
            routing_result_id="rid", tenant_id="t1", model_id="m1",
            task_type="code_generation", success=True, quality_satisfied=True,
            cost_within_budget=True, user_satisfaction=0.9,
            actual_cost=0.01, actual_latency_ms=100.0,
            created_at=datetime.now(timezone.utc), prompt_features={"log_tokens": 8.0},
        )
        with patch("core.learning_llm_router.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]
            loaded = router.load_feedback_from_db("t1")
        assert loaded == 1
        assert "t1:code_generation" in router._preference_data

    def test_load_feedback_from_db_error(self, router):
        with patch("core.learning_llm_router.get_db_session", side_effect=RuntimeError("boom")):
            loaded = router.load_feedback_from_db()
        assert loaded == 0

    def test_get_per_model_router_lazy_create(self, router):
        pmr = router._get_per_model_router("t1:task")
        assert pmr is router._get_per_model_router("t1:task")

    def test_get_per_model_router_eviction(self, router):
        router._max_per_model_routers = 2
        router._get_per_model_router("t1:a")
        router._get_per_model_router("t1:b")
        router._get_per_model_router("t1:c")
        assert len(router._per_model_routers) <= 2


class TestFeatures:
    def test_extract_features_content_signals(self, router):
        f = router._extract_request_features(_request(
            task_type="question_answering", estimated_tokens=250,
            conversation_context={"has_code": 0.0, "has_numbers": 1.0, "avg_word_length": 4.2},
        ))
        assert f["has_code"] == 0.0
        assert f["has_numbers"] == 1.0
        assert f["avg_word_length"] == 4.2
        assert f["token_bucket"] == 1.0
        assert f["log_tokens"] > 0

    def test_extract_features_prompt_text(self, router):
        f = router._extract_request_features(_request(
            conversation_context={"prompt_text": "```\ncode\n```"},
        ))
        assert f["has_code"] == 1.0

    def test_token_bucket_all(self, router):
        assert router._token_bucket(50) == 0.0
        assert router._token_bucket(250) == 1.0
        assert router._token_bucket(1000) == 2.0
        assert router._token_bucket(3000) == 3.0
        assert router._token_bucket(9000) == 4.0

    def test_task_default_features(self, router):
        f = router._task_default_features("code_generation")
        assert f["task_code"] == 1.0
        assert f["has_code"] == 1.0
        g = router._task_default_features("other")
        assert g["task_general"] == 1.0

    def test_feedback_to_training_example_defaults(self, router):
        example = router._feedback_to_training_example(
            _feedback(user_satisfaction=None, success=False, quality_satisfied=True),
            "code_generation",
        )
        assert example.user_satisfaction == 0.0
        assert example.prompt_features["task_code"] == 1.0

    def test_feedback_to_training_example_recovered(self, router):
        fb = _feedback(user_satisfaction=0.7)
        fb._prompt_features = {"log_tokens": 10.0}
        example = router._feedback_to_training_example(fb, "code_generation")
        assert example.user_satisfaction == 0.7
        assert example.estimated_tokens == int(2**10 - 1)

    def test_derive_weights_zero_samples(self, router):
        w = router._derive_weights_from_success({}, "reasoning")
        assert w == {"quality": 0.6, "cost": 0.1, "speed": 0.3}

    def test_derive_weights_scaled(self, router):
        w = router._derive_weights_from_success(
            {"m1": {"success": 10, "total": 10}}, "reasoning"
        )
        assert w["quality"] > 0.6
        assert abs(sum(w.values()) - 1.0) < 0.001

    def test_set_cached_weights_eviction(self, router):
        router._max_router_cache_size = 3
        for i in range(6):
            router._set_cached_weights(f"t{i}:task", {"quality": 0.4}, "t0")
        assert len(router._router_cache) <= 3


class TestStatsAndRegistry:
    async def test_statistics_tenant_scoping(self, router):
        await router.record_feedback(_feedback(tenant_id="tenant-1", model_id="gpt-4o"))
        await router.record_feedback(_feedback(tenant_id="tenant-2", model_id="gpt-4o"))
        stats = await router.get_routing_statistics("tenant-1")
        assert stats["feedback_samples"] == 1
        assert stats["model_success_rates"]["gpt-4o"] == 1.0

    async def test_statistics_ema_scoping(self, router):
        router._update_ema_scores(_feedback(tenant_id="tenant-1", model_id="gpt-4o"))
        router._update_ema_scores(_feedback(tenant_id="tenant-2", model_id="gpt-4o"))
        stats = await router.get_routing_statistics("tenant-1")
        assert len(stats["ema_scores"]) == 1
        assert "question_answering:gpt-4o" in stats["ema_scores"]

    def test_update_registry_missing_id_skipped(self, router):
        added = router.update_model_registry([{"provider": "x"}])
        assert added == 0

    def test_update_registry_enum_values(self, router):
        added = router.update_model_registry([{
            "model_id": "m-new", "capabilities": ["vision", "not-a-cap"],
            "cost_per_million": 0.1,
        }])
        assert added == 1
        assert ModelCapability.VISION in router._model_registry["m-new"].capabilities

    def test_update_registry_existing_updates(self, router):
        before = router._model_registry["gpt-4o"].cost_per_million
        added = router.update_model_registry([{
            "model_id": "gpt-4o", "cost_per_million": 0.0,
        }])
        assert added == 0
        assert router._model_registry["gpt-4o"].cost_per_million != before

    def test_load_local_models_with_caps(self, router):
        cap = SimpleNamespace(
            model_id="local-1", supports_tools=True, supports_vision=False,
            supports_reasoning=False, quality_score=0.6, speed_score=0.8,
            context_window=4096,
        )
        provider = SimpleNamespace(id="p1", provider_type="ollama", name="Local")
        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value.__enter__.return_value = db

            def query_side(model):
                if model.__name__ == "LocalModelCapabilities":
                    return Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[cap]))))
                return Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[provider]))))
            db.query.side_effect = query_side
            added = router.load_local_models_into_registry("default")
        assert added >= 1
        assert "local-1" in router._model_registry

    def test_load_local_models_error(self, router):
        with patch("core.learning_llm_router.get_db_session", side_effect=RuntimeError("boom")):
            added = router.load_local_models_into_registry("default")
        assert added == 0

    async def test_export_routing_data_filters(self, router):
        await router.record_feedback(_feedback(
            tenant_id="tenant-1", timestamp=datetime.now(timezone.utc),
        ))
        await router.record_feedback(_feedback(
            tenant_id="tenant-2", timestamp=datetime.now(timezone.utc),
        ))
        await router.record_feedback(_feedback(
            tenant_id="tenant-1",
            timestamp=datetime.now(timezone.utc) - timedelta(days=60),
        ))
        export = await router.export_routing_data("tenant-1", days=30)
        assert len(export["routing_feedback"]) == 1

    def test_get_learning_router_factory(self):
        r = get_learning_router(Mock())
        assert isinstance(r, LearningBasedRouter)

"""TDD tests: intent-as-features in the learning router + EMA verification.

Three bug/feature areas, written red-first:

1. **Intent one-hot features** — the predictor feature vector gains 6 intent
   one-hots (coding, data_analysis, web_browsing, creative_writing, reasoning,
   conversation) so per-model predictors can learn intent-specific satisfaction
   within a tenant/task bucket (train/serve consistent via the decision stash).

2. **Live-path dead bug** — ``_rerank_with_learning`` / ``_stash_decision_features``
   build a synthetic RoutingRequest without ``conversation_context``, which
   ``_extract_request_features`` accessed directly -> AttributeError -> swallowed
   -> the live re-rank and feature stash silently no-oped in production (same
   class of bug as the R97 3D-key fix).

3. **EMA value + cold-start gating** — ``_rerank_with_learning`` early-returns
   when no predictor bucket exists, so the EMA signal can never steer during
   full cold start; and the EMA success signal must decay correctly across
   regime shifts (outage) so it routes traffic around failing models.
"""
import math
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from core.learning_llm_router import (
    LearningBasedRouter,
    RoutingFeedback,
    RoutingRequest,
)
from core.llm.intent_detector import INTENT_CATEGORIES
from core.llm.routing.per_model_router import PerModelRouter
from core.llm.routing.preference_collector import TrainingExample
from core.llm.routing.routellm_trainer import (
    FeatureExtractor,
    ModelType,
    TrainingConfig,
)

INTENT_FEATURE_NAMES = [f"intent_{c}" for c in INTENT_CATEGORIES]


def _make_handler(clients=("openai",), async_clients=("openai",)):
    from core.llm.byok_handler import BYOKHandler

    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {p: MagicMock() for p in clients}
    handler.async_clients = {p: MagicMock() for p in async_clients}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


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
        intent=over.get("intent"),
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
    )


def make_example(satisfied, model="m1", task="code_generation", intent=None):
    feats = {
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
    }
    for c in INTENT_CATEGORIES:
        feats[f"intent_{c}"] = 1.0 if intent == c else 0.0
    return TrainingExample(
        estimated_tokens=200,
        task_type=task,
        prompt_features=feats,
        chosen_model=model,
        user_satisfaction=1.0 if satisfied else 0.0,
        was_successful=satisfied,
        quality_score=1.0 if satisfied else 0.0,
    )


# =========================================================================== #
# Intent one-hots in _extract_request_features
# =========================================================================== #
class TestExtractRequestFeaturesIntent:
    def test_intent_one_hots_present(self):
        router = LearningBasedRouter(Mock())
        f = router._extract_request_features(
            make_request(task_type="code_generation", intent="coding")
        )
        assert f["intent_coding"] == 1.0
        for c in ("data_analysis", "web_browsing", "creative_writing", "reasoning", "conversation"):
            assert f[f"intent_{c}"] == 0.0
        assert len(f) == 16

    def test_intent_from_conversation_context(self):
        router = LearningBasedRouter(Mock())
        f = router._extract_request_features(
            make_request(conversation_context={"intent": "reasoning"})
        )
        assert f["intent_reasoning"] == 1.0

    def test_no_intent_all_zero(self):
        router = LearningBasedRouter(Mock())
        f = router._extract_request_features(make_request())
        for name in INTENT_FEATURE_NAMES:
            assert f[name] == 0.0

    def test_unknown_intent_all_zero_no_crash(self):
        router = LearningBasedRouter(Mock())
        f = router._extract_request_features(make_request(intent="bogus_category"))
        for name in INTENT_FEATURE_NAMES:
            assert f[name] == 0.0

    def test_task_default_features_include_intent_zeros(self):
        router = LearningBasedRouter(Mock())
        f = router._task_default_features("code_generation")
        for name in INTENT_FEATURE_NAMES:
            assert f[name] == 0.0

    def test_synthetic_request_without_context_does_not_raise(self):
        # The live byok_handler paths build a bare object without
        # conversation_context; _extract_request_features must not blow up.
        router = LearningBasedRouter(Mock())
        fake = SimpleNamespace(
            task_type="code_generation", estimated_tokens=500,
            requires_reasoning=False,
        )
        f = router._extract_request_features(fake)
        assert f["intent_coding"] == 0.0
        assert len(f) == 16


# =========================================================================== #
# FeatureExtractor contract + old-data backward compat
# =========================================================================== #
class TestFeatureContract:
    def test_feature_names_include_intent_features(self):
        names = FeatureExtractor().feature_names
        assert len(names) == 16
        assert names[10:] == INTENT_FEATURE_NAMES

    def test_old_style_dict_gets_zero_intent_columns(self):
        # Rows persisted before this change carry only the 10 baseline keys.
        fe = FeatureExtractor()
        old = {
            "log_tokens": 3.0, "token_bucket": 1.0,
            "task_code": 1.0, "task_analysis": 0.0, "task_reasoning": 0.0,
            "task_chat": 0.0, "task_general": 0.0,
            "has_code": 1.0, "has_numbers": 0.0, "avg_word_length": 5.0,
        }
        ex = TrainingExample(
            estimated_tokens=100, task_type="code_generation",
            prompt_features=old, chosen_model="m1", user_satisfaction=1.0,
        )
        X = fe.extract_features([ex])
        assert X.shape == (1, 16)
        assert list(X[0, 10:]) == [0.0] * 6


class TestPerModelRouterCompat:
    def test_predict_truncates_to_estimator_dim(self, tmp_path):
        # A predictor persisted BEFORE the intent features were added expects
        # 10 features; predict must truncate the current 16-name contract to
        # the estimator's own n_features_in_ (graceful downgrade, no crash).
        router = PerModelRouter(TrainingConfig(model_path=str(tmp_path)))
        old_names = router.feature_extractor.feature_names[:10]
        router.feature_extractor.feature_names = old_names
        examples = [make_example(i % 2 == 0) for i in range(20)]
        # Strip intent keys so the fit sees exactly the old 10 dims.
        for ex in examples:
            for name in INTENT_FEATURE_NAMES:
                ex.prompt_features.pop(name, None)
        router.train("m-legacy", examples)
        assert router.predictors["m-legacy"].n_features_in_ == 10
        # Restore the full contract; predict must truncate, not raise.
        router.feature_extractor.feature_names = FeatureExtractor().feature_names
        full_feats = {name: 0.0 for name in router.feature_extractor.feature_names}
        full_feats["intent_coding"] = 1.0
        p = router.predict_satisfaction("m-legacy", full_feats)
        assert p is not None and 0.0 <= p <= 1.0

    def test_new_predictor_accepts_full_features(self, tmp_path):
        router = PerModelRouter(TrainingConfig(model_path=str(tmp_path)))
        examples = [
            make_example(i % 2 == 0, intent="coding" if i % 2 else "conversation")
            for i in range(20)
        ]
        router.train("m-new", examples)
        p = router.predict_satisfaction(
            "m-new", {**make_example(True).prompt_features, "intent_coding": 1.0}
        )
        assert p is not None and 0.0 <= p <= 1.0


# =========================================================================== #
# Intent value: a predictor can learn intent-specific satisfaction
# =========================================================================== #
class TestIntentLearningValue:
    def _intent_aware_router(self, tmp_path):
        cfg = TrainingConfig(
            model_path=str(tmp_path), model_type=ModelType.LOGISTIC_REGRESSION,
        )
        router = PerModelRouter(cfg)
        examples = []
        for i in range(30):
            examples.append(make_example(True, model="m", intent="coding"))
            examples.append(make_example(False, model="m", intent="conversation"))
        router.train("m", examples)
        return router

    def test_predictor_distinguishes_intents(self, tmp_path):
        router = self._intent_aware_router(tmp_path)
        base = make_example(True).prompt_features
        p_coding = router.predict_satisfaction(
            "m", {**base, "intent_coding": 1.0}
        )
        p_conv = router.predict_satisfaction(
            "m", {**base, "intent_conversation": 1.0}
        )
        assert p_coding is not None and p_conv is not None
        assert p_coding - p_conv > 0.2

    def test_intent_blind_predictor_cannot_distinguish(self, tmp_path):
        # Same model, but trained on feature dicts WITHOUT intent keys
        # (intent-blind): both prompts produce identical feature vectors, so
        # the predictor must be near-indifferent. This is the contrast that
        # proves intent-as-features adds signal.
        cfg = TrainingConfig(
            model_path=str(tmp_path), model_type=ModelType.LOGISTIC_REGRESSION,
        )
        router = PerModelRouter(cfg)
        examples = []
        for i in range(30):
            ex = make_example(True if i % 2 else False, model="m")
            for name in INTENT_FEATURE_NAMES:
                ex.prompt_features.pop(name, None)
            examples.append(ex)
        router.train("m", examples)
        base = make_example(True).prompt_features
        p1 = router.predict_satisfaction("m", {**base, "intent_coding": 1.0})
        p2 = router.predict_satisfaction("m", {**base, "intent_conversation": 1.0})
        assert p1 is not None and p2 is not None
        assert abs(p1 - p2) < 0.05


# =========================================================================== #
# Live path: synthetic request must not kill re-rank / stash
# =========================================================================== #
class TestRerankLivePath:
    @pytest.fixture
    def handler(self):
        return _make_handler()

    def _ema_router(self, tmp_path, with_bucket=True):
        router = LearningBasedRouter(Mock())
        if with_bucket:
            pmr = PerModelRouter(TrainingConfig(model_path=str(tmp_path)))
            router._per_model_routers["default:question_answering"] = pmr
        router._ema_scores = {
            "default:question_answering:m1": {"success": 0.9, "samples": 10},
            "default:question_answering:m2": {"success": 0.2, "samples": 10},
        }
        return router

    @pytest.mark.asyncio
    async def test_rerank_not_dead_on_synthetic_request(self, handler, tmp_path):
        # RED: previously the synthetic request lacked conversation_context ->
        # AttributeError -> swallowed -> options returned unchanged.
        router = self._ema_router(tmp_path)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.learning_router_registry.ema_router_enabled",
                 return_value=True,
             ):
            out = await handler._rerank_with_learning(
                [("a", "m2"), ("b", "m1")], "debug this python function", "chat"
            )
        assert out[0] == ("b", "m1")  # healthier EMA first
        assert handler._pending_routing_result_id

    @pytest.mark.asyncio
    async def test_ema_steers_without_predictor_bucket(self, handler, tmp_path):
        # RED: per_model None early-returned BEFORE the EMA term was evaluated,
        # so EMA could never route during full cold start (the documented
        # "cold-start handoff" was dead on the live path).
        router = self._ema_router(tmp_path, with_bucket=False)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.learning_router_registry.ema_router_enabled",
                 return_value=True,
             ):
            out = await handler._rerank_with_learning(
                [("a", "m2"), ("b", "m1")], "summarize this", "chat"
            )
        assert out[0] == ("b", "m1")
        assert handler._pending_routing_result_id

    @pytest.mark.asyncio
    async def test_rerank_passes_intent_into_stashed_features(
        self, handler, tmp_path
    ):
        router = self._ema_router(tmp_path)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.learning_router_registry.ema_router_enabled",
                 return_value=True,
             ):
            out = await handler._rerank_with_learning(
                [("a", "m1"), ("b", "m2")],
                "write a recursive fibonacci in rust",
                "chat",
                intent="coding",
            )
        assert out[0] == ("a", "m1")
        did = handler._pending_routing_result_id
        stashed = router.consume_decision(did)
        assert stashed is not None
        assert stashed["intent_coding"] == 1.0

    @pytest.mark.asyncio
    async def test_ema_flag_off_leaves_cold_bucket_unchanged(self, handler, tmp_path):
        router = self._ema_router(tmp_path, with_bucket=False)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.learning_router_registry.ema_router_enabled",
                 return_value=False,
             ):
            out = await handler._rerank_with_learning(
                [("a", "m2"), ("b", "m1")], "hello", "chat"
            )
        assert out == [("a", "m2"), ("b", "m1")]


# =========================================================================== #
# _stash_decision_features: intent explicit + detection fallback
# =========================================================================== #
class TestStashDecisionFeatures:
    @pytest.fixture
    def handler(self):
        return _make_handler()

    @pytest.mark.asyncio
    async def test_stash_with_explicit_intent(self, handler):
        router = LearningBasedRouter(Mock())
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ):
            did = handler._stash_decision_features(
                "write a poem about autumn", "chat", intent="creative_writing"
            )
        assert did
        feats = router.consume_decision(did)
        assert feats["intent_creative_writing"] == 1.0

    @pytest.mark.asyncio
    async def test_stash_detects_intent_when_not_given(self, handler):
        router = LearningBasedRouter(Mock())
        detector = Mock()
        detector.detect = Mock(
            return_value=SimpleNamespace(category="coding", confidence=0.9)
        )
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.intent_detector.get_intent_detector",
                 return_value=detector,
             ):
            did = handler._stash_decision_features(
                "debug my stack trace in python", "chat"
            )
        assert did
        feats = router.consume_decision(did)
        assert feats["intent_coding"] == 1.0


# =========================================================================== #
# EMA correctness + value
# =========================================================================== #
class TestEmaValue:
    @pytest.fixture
    def router(self):
        return LearningBasedRouter(Mock())

    def test_ema_decays_on_regime_shift(self, router):
        # 10 clean successes, then an outage: 5 sustained failures.
        for _ in range(10):
            router._update_ema_scores(make_feedback(model_id="m"))
        for _ in range(5):
            router._update_ema_scores(
                make_feedback(model_id="m", success=False, quality_satisfied=False)
            )
        s = router._ema_scores["tenant-1:question_answering:m"]["success"]
        # after 10 ones EMA ~= 1 - 0.8^10 = 0.893; after 5 zeros -> *0.8^5 = 0.293
        assert 0.2 < s < 0.45

    def test_ema_success_requires_quality_satisfied(self, router):
        router._update_ema_scores(
            make_feedback(model_id="m", success=True, quality_satisfied=False)
        )
        assert router._ema_scores["tenant-1:question_answering:m"]["success"] == 0.0

    def test_ema_alpha_clamp(self, monkeypatch):
        router = LearningBasedRouter(Mock())
        for raw, expected in (("0", 0.2), ("2.5", 1.0), ("abc", 0.2), ("0.5", 0.5)):
            monkeypatch.setenv("ATOM_EMA_ALPHA", raw)
            assert router._ema_alpha() == pytest.approx(expected)

    def test_ema_term_cold_fleet_returns_none(self):
        router = LearningBasedRouter(Mock())
        request = make_request()
        spec = router._model_registry["gpt-4o"]
        term = router._ema_quality_term(
            spec, request, {"max_latency": 1000.0, "max_cost": 0.1}
        )
        assert term is None


# =========================================================================== #
# Train/serve loop: feedback trains on the stashed intent features
# =========================================================================== #
class TestTrainServeLoop:
    @pytest.mark.asyncio
    async def test_record_feedback_recovers_intent_features(self):
        router = LearningBasedRouter(Mock())
        feats = router._extract_request_features(
            make_request(task_type="code_generation", intent="coding")
        )
        did = router.stash_decision(feats)
        fb = make_feedback(
            routing_result_id=did, task_type="code_generation",
            model_id="m", success=True, quality_satisfied=True,
        )
        with patch("core.learning_llm_router.get_db_session"):
            await router.record_feedback(fb)
        ex = router._feedback_to_training_example(fb, "code_generation")
        assert ex.prompt_features["intent_coding"] == 1.0
        assert ex.prompt_features["intent_conversation"] == 0.0

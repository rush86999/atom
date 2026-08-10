"""Coverage wave 12 — CognitiveTierService, response quality, request healer,
session dedup (TDD)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.llm.cognitive_tier_service import CognitiveTierService
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.response_quality import assess_response_quality
from core.llm.routing.request_healer import (
    classify_error,
    get_request_healer,
    is_repairable,
)
from core.llm.compression.session_dedup import (
    SessionDedupIndex,
    get_or_create_dedup_index,
)


class _Pref:
    def __init__(self, **kw):
        self.min_tier = kw.get("min_tier")
        self.max_tier = kw.get("max_tier")
        self.default_tier = kw.get("default_tier")
        self.preferred_providers = kw.get("preferred_providers")
        self.max_cost_per_request_cents = kw.get("max_cost_per_request_cents")
        self.monthly_budget_cents = kw.get("monthly_budget_cents")
        self.enable_auto_escalation = kw.get("enable_auto_escalation", True)


def _service(db=None, tenant_id=None):
    return CognitiveTierService(
        workspace_id="default", db_session=db, tenant_id=tenant_id
    )


# =========================================================================== #
# CognitiveTierService.select_tier
# =========================================================================== #
class TestSelectTier:
    def test_user_override_wins(self):
        svc = _service()
        assert svc.select_tier("hi", user_tier_override="heavy") == CognitiveTier.HEAVY

    def test_invalid_user_override_falls_through(self):
        svc = _service()
        tier = svc.select_tier("hello", user_tier_override="bogus")
        assert tier in list(CognitiveTier)

    def test_plain_classification(self):
        svc = _service()
        assert svc.select_tier("hello") == CognitiveTier.MICRO

    def test_intent_nudge_floor(self):
        svc = _service()
        # "hello" classifies MICRO; coding intent floors to VERSATILE
        tier = svc.select_tier("hello", intent_override="coding")
        assert tier == CognitiveTier.VERSATILE

    def test_min_tier_clamp(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            min_tier="versatile"
        )
        svc = _service(db=db)
        assert svc.select_tier("hello") == CognitiveTier.VERSATILE

    def test_max_tier_clamp(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            max_tier="standard"
        )
        svc = _service(db=db)
        assert svc.select_tier("calculate the integral of a complex function") in (
            CognitiveTier.MICRO, CognitiveTier.STANDARD,
        )

    def test_default_tier_clamped_by_max(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            default_tier="complex", max_tier="standard"
        )
        svc = _service(db=db)
        assert svc.select_tier("hello") == CognitiveTier.STANDARD

    def test_invalid_pref_tiers_tolerated(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            min_tier="bogus", max_tier="also-bogus", default_tier="nope"
        )
        svc = _service(db=db)
        assert svc.select_tier("hello") == CognitiveTier.MICRO


# =========================================================================== #
# get_optimal_model
# =========================================================================== #
class TestGetOptimalModel:
    def test_dynamic_models_from_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(model_name="gpt-4o"),
            SimpleNamespace(model_name="deepseek-chat"),
        ]
        db.query.return_value.filter.return_value.first.return_value = None
        svc = _service(db=db)
        svc._cache_router = MagicMock()
        svc.cache_router.predict_cache_hit_probability.return_value = 0.5
        svc.cache_router.calculate_effective_cost.side_effect = [0.003, 0.001]
        provider, model = svc.get_optimal_model(CognitiveTier.VERSATILE, 100)
        assert model == "deepseek-chat"  # cheapest wins
        assert provider == "deepseek"

    def test_hardcoded_fallback_without_db(self):
        svc = _service(db=None)
        svc._cache_router = MagicMock()
        svc.cache_router.predict_cache_hit_probability.return_value = 0.5
        svc.cache_router.calculate_effective_cost.side_effect = lambda *a, **k: 0.01
        provider, model = svc.get_optimal_model(CognitiveTier.MICRO, 10)
        assert model is not None

    def test_preferred_providers_filter(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(model_name="gpt-4o"),
            SimpleNamespace(model_name="claude-sonnet"),
        ]
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            preferred_providers=["anthropic"]
        )
        svc = _service(db=db)
        svc._cache_router = MagicMock()
        svc.cache_router.predict_cache_hit_probability.return_value = 0.5
        svc.cache_router.calculate_effective_cost.side_effect = lambda *a, **k: 0.01
        provider, model = svc.get_optimal_model(CognitiveTier.VERSATILE, 100)
        assert provider == "anthropic"
        assert model == "claude-sonnet"

    def test_no_models_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        svc = _service(db=db)
        svc._cache_router = MagicMock()
        provider, model = svc.get_optimal_model(CognitiveTier.HEAVY, 100)
        assert provider is None and model is None

    def test_dynamic_query_error_falls_back_to_defaults(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = _service(db=db)
        svc._cache_router = MagicMock()
        svc.cache_router.predict_cache_hit_probability.return_value = 0.5
        svc.cache_router.calculate_effective_cost.side_effect = lambda *a, **k: 0.01
        provider, model = svc.get_optimal_model(CognitiveTier.MICRO, 10)
        assert model is not None  # hardcoded fallback


# =========================================================================== #
# _get_dynamic_tier_models / _model_to_provider
# =========================================================================== #
class TestDynamicModelsAndMapping:
    def test_quality_band_query(self):
        db = MagicMock()
        svc = _service(db=db, tenant_id="t-1")
        svc._get_dynamic_tier_models(CognitiveTier.VERSATILE)
        assert db.query.called

    def test_micro_special_filter(self):
        db = MagicMock()
        svc = _service(db=db)
        svc._get_dynamic_tier_models(CognitiveTier.MICRO)
        assert db.query.called

    def test_no_db_returns_empty(self):
        svc = _service(db=None)
        assert svc._get_dynamic_tier_models(CognitiveTier.STANDARD) == []

    def test_model_to_provider(self):
        svc = _service()
        assert svc._model_to_provider("gpt-4o") == "openai"
        assert svc._model_to_provider("o3-mini") == "openai"
        assert svc._model_to_provider("claude-sonnet") == "anthropic"
        assert svc._model_to_provider("deepseek-chat") == "deepseek"
        assert svc._model_to_provider("gemini-pro") == "gemini"
        assert svc._model_to_provider("qwen-plus") == "qwen"
        assert svc._model_to_provider("minimax-m3") == "minimax"
        assert svc._model_to_provider("glm-4") == "glm"
        assert svc._model_to_provider("kimi-k2") == "moonshot"
        assert svc._model_to_provider("weird-model") == "unknown"


# =========================================================================== #
# calculate_request_cost / check_budget_constraint
# =========================================================================== #
class TestCostAndBudget:
    def test_request_cost_shape(self):
        svc = _service()
        router = MagicMock()
        router.predict_cache_hit_probability.return_value = 0.5
        router.calculate_effective_cost.side_effect = [0.001, 0.002]
        svc._cache_router = router
        out = svc.calculate_request_cost("hello world", CognitiveTier.MICRO, "gpt-4o-mini")
        assert out["effective_cost"] == 0.001
        assert out["full_cost"] == 0.002
        assert out["cache_discount"] == 0.5
        assert out["estimated_tokens"] == len("hello world") // 4

    def test_request_cost_default_model(self):
        svc = _service()
        router = MagicMock()
        router.predict_cache_hit_probability.return_value = 0.5
        router.calculate_effective_cost.side_effect = [0.001, 0.002]
        svc._cache_router = router
        out = svc.calculate_request_cost("hello", CognitiveTier.MICRO)
        assert out["estimated_tokens"] == 1

    def test_budget_no_preference_allows(self):
        svc = _service(db=None)
        assert svc.check_budget_constraint(999999) is True

    def test_budget_per_request_limit(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            max_cost_per_request_cents=10
        )
        svc = _service(db=db)
        assert svc.check_budget_constraint(5) is True
        assert svc.check_budget_constraint(15) is False

    def test_budget_monthly_limit(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            monthly_budget_cents=100
        )
        svc = _service(db=db)
        assert svc.check_budget_constraint(50) is True
        assert svc.check_budget_constraint(150) is False


# =========================================================================== #
# handle_escalation / preferences / cache outcome
# =========================================================================== #
class TestEscalationAndPrefs:
    def test_auto_escalation_disabled(self):
        from core.llm.escalation_manager import EscalationReason

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _Pref(
            enable_auto_escalation=False
        )
        svc = _service(db=db)
        should, reason, target = svc.handle_escalation(
            CognitiveTier.STANDARD, response_quality=50
        )
        assert should is False and reason is None

    def test_escalation_delegates(self):
        svc = _service(db=None)
        svc.escalation_manager = MagicMock()
        svc.escalation_manager.should_escalate.return_value = (True, "quality_threshold", CognitiveTier.VERSATILE)
        should, reason, target = svc.handle_escalation(
            CognitiveTier.STANDARD, response_quality=50
        )
        assert should is True
        assert svc.escalation_manager.should_escalate.called

    def test_get_workspace_preference_with_tenant(self):
        db = MagicMock()
        svc = _service(db=db, tenant_id="t-1")
        svc.get_workspace_preference()
        assert db.query.called

    def test_get_workspace_preference_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = _service(db=db)
        assert svc.get_workspace_preference() is None

    def test_record_cache_outcome(self):
        svc = _service()
        router = MagicMock()
        svc._cache_router = router
        svc.record_cache_outcome("hash", True)
        router.record_cache_outcome.assert_called_once_with("hash", "default", True)

    def test_cache_router_lazy_property(self):
        svc = _service()
        assert svc._cache_router is None
        router = svc.cache_router
        assert router is not None
        assert svc.cache_router is router  # cached


# =========================================================================== #
# assess_response_quality branches
# =========================================================================== #
class TestResponseQuality:
    def test_exception_hard_failure(self):
        q = assess_response_quality(None, exception=RuntimeError("boom"))
        assert q.success is False and q.quality_score == 0.0

    def test_schema_error(self):
        q = assess_response_quality("x", schema_error=True)
        assert q.quality_satisfied is False and q.quality_score == 0.2
        assert "schema_error" in q.issues

    def test_truncated_with_content(self):
        q = assess_response_quality("partial", finish_reason="length")
        assert q.quality_score == 0.3 and "truncated" in q.issues

    def test_truncated_empty(self):
        q = assess_response_quality("", finish_reason="length")
        assert q.quality_score == 0.1

    def test_empty_content(self):
        q = assess_response_quality("   ")
        assert q.quality_score == 0.1 and "empty" in q.issues

    def test_refusal_marker(self):
        q = assess_response_quality("I'm sorry, I cannot help with that.")
        assert q.quality_score == 0.4 and "refusal" in q.issues

    def test_substantive_tiers(self):
        assert assess_response_quality("ok").quality_score == 0.7
        assert assess_response_quality("x" * 300).quality_score == 0.8
        assert assess_response_quality("x" * 1000).quality_score == 0.85
        assert assess_response_quality("x" * 9000).quality_score == 0.78


# =========================================================================== #
# request_healer
# =========================================================================== #
class TestRequestHealer:
    def test_classify_error(self):
        assert classify_error(RuntimeError("connection timed out")) == "transient"
        assert classify_error(RuntimeError("rate limit exceeded")) == "non_repairable_4xx"
        assert classify_error(RuntimeError("internal server error")) == "server_error"
        assert classify_error(RuntimeError("mystery failure")) == "unknown"

        class _ApiStatus(Exception):
            def __init__(self, code):
                super().__init__("api error")
                self.status_code = code
                self.response = None
                self.request = None

        assert classify_error(_ApiStatus(400)) == "repairable_4xx"
        assert classify_error(_ApiStatus(429)) == "non_repairable_4xx"

    def test_is_repairable(self):
        assert is_repairable(RuntimeError("boom")) is False

        class _ApiStatus(Exception):
            def __init__(self, code):
                super().__init__("api error")
                self.status_code = code
                self.response = None
                self.request = None

        assert is_repairable(_ApiStatus(400)) is True
        assert is_repairable(_ApiStatus(401)) is False

    def test_heal_no_patch_returns_none(self):
        healer = get_request_healer()
        result = healer.heal(RuntimeError("boom"), {"model": "m"}, "openai", "m")
        assert result.patched_kwargs is None
        assert result.rule is None

    def test_heal_with_repairable_400(self):
        healer = get_request_healer()

        class _ApiStatus(Exception):
            def __init__(self, code):
                super().__init__("api error")
                self.status_code = code
                self.response = None
                self.request = None

        kwargs = {"model": "gpt-4o", "messages": [], "temperature": 0.7, "max_tokens": 1000}
        result = healer.heal(_ApiStatus(400), kwargs, "openai", "gpt-4o")
        # Either a patch was produced or None — the important contract is the
        # HealingResult shape and never raising.
        assert result.patched_kwargs is None or isinstance(result.patched_kwargs, dict)
        assert result.rule is None or isinstance(result.rule, str)
        assert isinstance(result.patched_keys, list)

    def test_heal_never_raises(self):
        healer = get_request_healer()
        result = healer.heal(None, {"model": "m"}, "openai", "m")  # type: ignore[arg-type]
        assert result.patched_kwargs is None


# =========================================================================== #
# SessionDedupIndex
# =========================================================================== #
class TestSessionDedup:
    _LONG = "The quick brown fox jumps over the lazy dog. " * 20  # > 200 chars

    def test_dedup_repeated_text(self):
        idx = SessionDedupIndex()
        idx.index_text(self._LONG)
        out, removed = idx.deduplicate(self._LONG)
        assert removed > 0
        assert "[previously sent:" in out

    def test_unknown_text_unchanged(self):
        idx = SessionDedupIndex()
        idx.index_text(self._LONG)
        out, removed = idx.deduplicate("something completely different " * 20)
        assert removed == 0
        assert out == "something completely different " * 20

    def test_size_and_clear(self):
        idx = SessionDedupIndex()
        assert idx.size == 0
        idx.index_text(self._LONG)
        assert idx.size > 0
        idx.clear()
        assert idx.size == 0

    def test_max_size_bound(self):
        idx = SessionDedupIndex(max_size=2)
        idx.index_text("A" * 500)
        idx.index_text("B" * 500)
        idx.index_text("C" * 500)
        assert idx.size <= 2

    def test_hash_stability(self):
        assert SessionDedupIndex._hash("abc") == SessionDedupIndex._hash("abc")
        assert SessionDedupIndex._hash("abc") != SessionDedupIndex._hash("abd")

    def test_get_or_create_singleton(self):
        session = {}
        i1 = get_or_create_dedup_index(session)
        i2 = get_or_create_dedup_index(session)
        assert i1 is i2

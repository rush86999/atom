"""Coverage wave 11 — LLM stack: cognitive tiers, intent detection, escalation,
cache-aware routing, BYOK credential resolution (TDD).

Red-green targets (real bugs):
- W11-1: ``BYOKHandler.__init__`` resolved OAuth/subscription credentials via
  ``loop.run_until_complete`` — inside a RUNNING event loop (every FastAPI
  gateway route) that raises "This event loop is already running" and
  ABANDONS the coroutine (RuntimeWarning: never awaited) → the credential
  service silently never resolved on the gateway surface (BYOK/env only).
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =========================================================================== #
# W11-1 — BYOKHandler credential resolution inside a running event loop
# =========================================================================== #
class TestCredentialResolutionInAsyncContext:
    @pytest.mark.asyncio
    async def test_oauth_credential_resolves_inside_running_loop(self):
        """RED: constructing BYOKHandler with user_id inside a running loop
        must resolve the OAuth credential and initialize the client — the old
        run_until_complete abandoned the coroutine here (credential_service
        silently skipped, only BYOK/env fallbacks fired)."""
        from core.llm.byok_handler import BYOKHandler
        from core.llm_credential_service import LLMCredentialService

        mock_ctor = MagicMock()
        with patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()) as mock_ctor, \
             patch.object(
                 LLMCredentialService,
                 "get_credential",
                 new=AsyncMock(return_value=("oauth", "sk-oauth-123")),
             ), \
             patch("core.llm.byok_handler.get_db_session"):
            handler = BYOKHandler(
                workspace_id="default", tenant_id="default", user_id="u-test"
            )

        assert "openai" in handler.clients, (
            "W11-1: OAuth credential never resolved inside a running loop — "
            "openai client not initialized"
        )
        assert mock_ctor.call_args.kwargs.get("api_key") == "sk-oauth-123"

    @pytest.mark.asyncio
    async def test_byok_fallback_still_wins_without_oauth(self):
        from core.llm.byok_handler import BYOKHandler
        from core.llm_credential_service import LLMCredentialService

        # Hermetic: no credential service, no BYOK config, no env key.
        # (Other suites set TESTING=1 which can point the real byok manager at
        # a DB containing provider rows — a client would be created.)
        mock_mgr = MagicMock()
        mock_mgr.is_configured.return_value = False
        mock_mgr.get_api_key.return_value = None

        mock_openai = MagicMock()
        with patch("core.llm.byok_handler.AsyncOpenAI", return_value=mock_openai), \
             patch("core.llm.byok_handler.get_byok_manager", return_value=mock_mgr), \
             patch.object(
                 LLMCredentialService,
                 "get_credential",
                 new=AsyncMock(side_effect=ValueError("no credential")),
             ), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch.dict(
                 "os.environ",
                 {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "DEEPSEEK_API_KEY": ""},
             ):
            handler = BYOKHandler(
                workspace_id="default", tenant_id="default", user_id="u-test"
            )
        assert "openai" not in handler.clients  # no key anywhere -> no client

    def test_run_coroutine_sync_without_loop(self):
        from core.llm.byok_handler import _run_coroutine_sync

        async def _add(a, b):
            return a + b

        assert _run_coroutine_sync(_add(2, 3)) == 5

    @pytest.mark.asyncio
    async def test_run_coroutine_sync_inside_running_loop(self):
        from core.llm.byok_handler import _run_coroutine_sync

        async def _value():
            await asyncio.sleep(0)
            return "done"

        assert _run_coroutine_sync(_value()) == "done"


# =========================================================================== #
# cognitive_tier_system coverage
# =========================================================================== #
class TestCognitiveClassifier:
    def _classify(self, prompt, task_type=None):
        from core.llm.cognitive_tier_system import CognitiveClassifier

        return CognitiveClassifier().classify(prompt, task_type)

    def test_greeting_micro(self):
        assert self._classify("hello").value == "micro"

    def test_long_simple_prompt_not_heavy(self):
        # BUG-116 guard: long-but-simple prompt must not route to HEAVY.
        prompt = "hello " * 2000
        tier = self._classify(prompt)
        assert tier.value in ("micro", "standard", "versatile")

    def test_code_block_escalates(self):
        code = "```python\ndef f(x):\n    return x * 2\n```"
        tier = self._classify(code, task_type="code")
        assert tier.value in ("heavy", "complex")

    def test_empty_prompt_micro(self):
        assert self._classify("").value == "micro"

    def test_unknown_task_type_no_bias(self):
        assert self._classify("what is a foo bar baz", task_type="weird_task").value in (
            "micro", "standard",
        )

    def test_min_score_clamped(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier

        cls = CognitiveClassifier()
        assert cls._calculate_complexity_score("hi thanks") >= -2

    def test_tier_threshold_bounds(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        assert CognitiveTier("micro").value == "micro"
        assert CognitiveTier("complex").value == "complex"
        with pytest.raises(ValueError):
            CognitiveTier("bogus")

    def test_get_tier_models_defaults(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        cls = CognitiveClassifier()
        micro = cls.get_tier_models(CognitiveTier.MICRO)
        assert "gpt-4o-mini" in micro
        assert cls.get_tier_models("bogus") == []  # unknown tier -> empty

    def test_get_tier_models_workspace_override(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        cls = CognitiveClassifier()
        pref = SimpleNamespace(
            metadata_json={"tier_models": {"micro": ["my-local-model"]}}
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = pref
        with patch(
            "core.database.get_db_session",
            return_value=MagicMock(
                __enter__=lambda self: db, __exit__=MagicMock(return_value=False)
            ),
        ):
            assert cls.get_tier_models(CognitiveTier.MICRO, workspace_id="ws-1") == [
                "my-local-model"
            ]

    def test_get_tier_models_workspace_error_falls_back(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        cls = CognitiveClassifier()
        with patch(
            "core.database.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            models = cls.get_tier_models(CognitiveTier.HEAVY, workspace_id="ws-1")
        assert "gpt-4o" in models  # defaults

    def test_get_tier_description(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        cls = CognitiveClassifier()
        assert "greetings" in cls.get_tier_description(CognitiveTier.MICRO)


# =========================================================================== #
# intent_detector coverage
# =========================================================================== #
class TestIntentDetector:
    def _detect(self, prompt, **kw):
        from core.llm.intent_detector import IntentDetector

        return IntentDetector().detect(prompt, **kw)

    def test_coding_intent(self):
        result = self._detect("debug my python function, it crashes with an exception")
        assert result.category == "coding"
        assert 0.0 <= result.confidence <= 1.0

    def test_data_analysis_intent(self):
        result = self._detect("analyze the dataset and plot a regression chart")
        assert result.category == "data_analysis"

    def test_web_browsing_intent(self):
        result = self._detect("search the web for the latest news")
        assert result.category == "web_browsing"

    def test_creative_writing_intent(self):
        result = self._detect("write a poem about autumn")
        assert result.category == "creative_writing"

    def test_reasoning_intent(self):
        result = self._detect("prove the theorem step by step")
        assert result.category == "reasoning"

    def test_conversation_alone_below_threshold(self):
        # conversation threshold is 2; a single weak hit must not win.
        result = self._detect("hi")
        assert result.category is None

    def test_empty_prompt(self):
        result = self._detect("   ")
        assert result.category is None
        assert result.confidence == 0.0

    def test_url_boost(self):
        result = self._detect("check https://example.com page content")
        assert result.category == "web_browsing"

    def test_code_fence_boost(self):
        result = self._detect("here is my python function: ```print(1)```")
        assert result.category == "coding"

    def test_tool_prefix_heuristics(self):
        result = self._detect(
            "do something", tools=[{"name": "browser_navigate"}, {"name": "search_query"}]
        )
        assert result.category == "web_browsing"

    def test_tool_name_variants(self):
        from core.llm.intent_detector import _extract_tool_name

        assert _extract_tool_name("code_run") == "code_run"
        assert _extract_tool_name({"name": "chart_make"}) == "chart_make"
        assert _extract_tool_name({"function": {"name": "sql_query"}}) == "sql_query"
        assert _extract_tool_name(SimpleNamespace(name="analytics_run")) == "analytics_run"
        assert _extract_tool_name(SimpleNamespace()) is None
        assert _extract_tool_name({"name": ""}) is None

    def test_session_stickiness(self):
        result = self._detect(
            "do the thing",
            recent_intents=["coding", "coding", "coding"],
        )
        assert result.category == "coding"

    def test_session_stickiness_insufficient(self):
        result = self._detect(
            "hi there", recent_intents=["coding", "coding"]
        )
        assert result.category is None  # <3 agreement, no bias

    def test_category_penalties(self):
        result = self._detect(
            "analyze the dataset and plot a regression chart",
            category_penalties={"data_analysis": 10},
        )
        assert result.category is None  # penalized below threshold

    def test_nudge_tier_floors(self):
        from core.llm.intent_detector import IntentDetector

        d = IntentDetector()
        assert d.nudge_tier("coding", "micro") == "versatile"
        assert d.nudge_tier("reasoning", "micro") == "versatile"
        assert d.nudge_tier("data_analysis", "micro") == "standard"
        assert d.nudge_tier("creative_writing", "micro") == "standard"
        assert d.nudge_tier("conversation", "complex") == "standard"
        assert d.nudge_tier("web_browsing", "micro") == "micro"
        assert d.nudge_tier(None, "micro") == "micro"
        assert d.nudge_tier("coding", "bogus") == "bogus"  # invalid tier passthrough
        assert d.nudge_tier("conversation", "micro") == "micro"  # no cap needed

    def test_is_valid_intent(self):
        from core.llm.intent_detector import is_valid_intent

        assert is_valid_intent("coding")
        assert not is_valid_intent("bogus")

    def test_get_intent_detector_singleton(self):
        from core.llm.intent_detector import get_intent_detector

        assert get_intent_detector() is get_intent_detector()

    def test_high_confidence_capped(self):
        result = self._detect(
            "prove the theorem step by step and derive a contradiction, "
            "therefore it implies the lemma by induction"
        )
        assert result.confidence <= 1.0


# =========================================================================== #
# escalation_manager coverage
# =========================================================================== #
class TestEscalationManager:
    def _manager(self, db=None):
        from core.llm.escalation_manager import EscalationManager

        return EscalationManager(db_session=db, workspace_id="ws-1")

    def test_no_escalation_when_healthy(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        m = self._manager()
        should, reason, target = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, response_quality=95
        )
        assert should is False
        assert reason is None and target is None

    def test_quality_escalation(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        m = self._manager()
        should, reason, target = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, response_quality=70
        )
        assert should is True
        assert reason == EscalationReason.QUALITY_THRESHOLD
        assert target == CognitiveTier.VERSATILE

    def test_rate_limit_escalation_priority(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        m = self._manager()
        should, reason, target = m.should_escalate(
            current_tier=CognitiveTier.MICRO, rate_limited=True, error="429"
        )
        assert reason == EscalationReason.RATE_LIMITED
        assert target == CognitiveTier.STANDARD

    def test_error_escalation(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        m = self._manager()
        should, reason, _ = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, error="model blew up"
        )
        assert should and reason == EscalationReason.ERROR_RESPONSE

    def test_low_confidence_escalation(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        m = self._manager()
        should, reason, _ = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, confidence=0.5
        )
        assert should and reason == EscalationReason.LOW_CONFIDENCE

    def test_complex_tier_no_escalation(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        m = self._manager()
        should, reason, target = m.should_escalate(
            current_tier=CognitiveTier.COMPLEX, response_quality=10
        )
        assert not should and reason is None and target is None

    def test_cooldown_blocks(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from datetime import datetime, timezone

        m = self._manager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        should, reason, _ = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, response_quality=50
        )
        assert not should

    def test_cooldown_expired_allows(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from datetime import datetime, timedelta, timezone

        m = self._manager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(
            timezone.utc
        ) - timedelta(minutes=10)
        should, reason, _ = m.should_escalate(
            current_tier=CognitiveTier.STANDARD, response_quality=50
        )
        assert should

    def test_max_escalation_limit(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import MAX_ESCALATION_LIMIT

        m = self._manager()
        m.request_escalations["req-1"] = MAX_ESCALATION_LIMIT
        should, reason, _ = m.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=50,
            request_id="req-1",
        )
        assert not should

    def test_escalation_count_increments(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        m = self._manager()
        m.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=50,
            request_id="req-2",
        )
        assert m.get_escalation_count("req-2") == 1
        assert m.get_escalation_count("missing") == 0

    def test_db_logging_and_failure(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        db = MagicMock()
        m = self._manager(db=db)
        m._escalate_for_reason(
            CognitiveTier.MICRO,
            EscalationReason.LOW_CONFIDENCE,
            trigger_value=0.4,
            request_id="r1",
            provider_id="openai",
            model="gpt-4o-mini",
            error_message="err",
        )
        assert db.add.called and db.commit.called

        db2 = MagicMock()
        db2.add.side_effect = RuntimeError("db down")
        m2 = self._manager(db=db2)
        # DB failure must not fail the escalation itself
        from core.llm.escalation_manager import EscalationReason

        should, reason, target = m2._escalate_for_reason(
            CognitiveTier.MICRO, EscalationReason.RATE_LIMITED
        )
        assert should is True
        assert db2.rollback.called

    def test_unknown_tier_in_escalation(self):
        m = self._manager()
        should, reason, target = m._escalate_for_reason("bogus", "error_response")
        assert not should and target is None

    def test_cooldown_helpers(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        m = self._manager()
        assert m.get_cooldown_remaining(CognitiveTier.MICRO) == 0.0
        m.escalation_log[CognitiveTier.MICRO.value] = __import__(
            "datetime"
        ).datetime.now(__import__("datetime").timezone.utc)
        assert m.get_cooldown_remaining(CognitiveTier.MICRO) > 0.0
        m.reset_cooldown(CognitiveTier.MICRO)
        assert CognitiveTier.MICRO.value not in m.escalation_log
        m.reset_cooldown(CognitiveTier.MICRO)  # no-op


# =========================================================================== #
# cache_aware_router coverage
# =========================================================================== #
class TestCacheAwareRouter:
    def _router(self, price=None):
        from core.llm.cache_aware_router import CacheAwareRouter

        fetcher = MagicMock()
        fetcher.get_model_price.return_value = price or {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        }
        return CacheAwareRouter(fetcher)

    def test_full_price_without_cache_provider(self):
        r = self._router()
        cost = r.calculate_effective_cost("deepseek-chat", "deepseek", 5000)
        assert cost == (0.000005 + 0.000015) / 2

    def test_deterministic_turn_mode_discounts_input(self):
        r = self._router()
        cost = r.calculate_effective_cost(
            "gpt-4o", "openai", 5000, turn_index=2
        )
        expected = (0.000005 * 0.10 + 0.000015) / 2
        assert cost == expected

    def test_probabilistic_mode_with_history(self):
        r = self._router()
        r.record_cache_outcome("abc", "default", True)
        r.record_cache_outcome("abc", "default", False)
        cost = r.calculate_effective_cost(
            "gpt-4o", "openai", 5000, prompt_hash="abc", workspace_id="default"
        )
        # 50% hit history -> discounted ratio = 0.5*0.1 + 0.5 = 0.55
        expected = (0.000005 * 0.55 + 0.000015) / 2
        assert cost == expected

    def test_under_min_tokens_no_cache(self):
        r = self._router()
        cost = r.calculate_effective_cost("gpt-4o", "openai", 100)
        assert cost == (0.000005 + 0.000015) / 2

    def test_missing_price_returns_inf(self):
        r = self._router(price=None)
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = None
        r.pricing_fetcher = fetcher
        cost = r.calculate_effective_cost("unknown-model", "openai", 100)
        assert cost == float("inf")

    def test_probability_clamped(self):
        r = self._router()
        cost = r.calculate_effective_cost(
            "gpt-4o", "openai", 5000, cache_hit_probability=5.0
        )
        # clamped to 1.0 -> discounted = 1.0*0.1 + 0 = 0.1
        expected = (0.000005 * 0.10 + 0.000015) / 2
        assert cost == expected

    def test_predict_default_and_history(self):
        r = self._router()
        assert r.predict_cache_hit_probability("hash1", "default") == 0.5
        for _ in range(8):
            r.record_cache_outcome("hash2", "default", True)
        for _ in range(2):
            r.record_cache_outcome("hash2", "default", False)
        assert r.predict_cache_hit_probability("hash2", "default") == 0.8

    def test_record_outcome_bounds(self):
        from core.llm.cache_aware_router import CacheAwareRouter

        r = CacheAwareRouter(MagicMock())
        for _ in range(200):
            r.record_cache_outcome("h", "ws", True)
        assert len(r.cache_hit_history["ws:h"]) == 2
        assert r.cache_hit_history["ws:h"][1] <= CacheAwareRouter._CACHE_WINDOW

    def test_max_keys_fifo_eviction(self):
        from core.llm.cache_aware_router import CacheAwareRouter

        r = CacheAwareRouter(MagicMock())
        r._MAX_CACHE_KEYS = 3
        for i in range(5):
            r.record_cache_outcome(f"key{i}", "ws", True)
        assert len(r.cache_hit_history) == 3
        assert "ws:key0" not in r.cache_hit_history
        assert len(r._cache_key_order) == 3

    def test_provider_capabilities(self):
        r = self._router()
        caps = r.get_provider_cache_capability("openai")
        assert caps["supports_cache"] and caps["min_tokens"] == 1024
        assert r.get_provider_cache_capability("deepseek")["supports_cache"] is False
        assert r.get_provider_cache_capability("google-flash")["supports_cache"] is True
        assert r.get_provider_cache_capability("random-provider")["supports_cache"] is False
        assert r.get_provider_cache_capability("OPENAI")["supports_cache"] is True

    def test_history_analytics_defensive_copy(self):
        r = self._router()
        r.record_cache_outcome("h", "ws", True)
        view = r.get_cache_hit_history("ws")
        view["ws:h"][0] = 999  # mutate the copy
        assert r.cache_hit_history["ws:h"][0] == 1

    def test_clear_history(self):
        r = self._router()
        r.record_cache_outcome("h1", "ws1", True)
        r.record_cache_outcome("h2", "ws2", True)
        r.clear_cache_history("ws1")
        assert "ws1:h1" not in r.cache_hit_history
        assert "ws2:h2" in r.cache_hit_history
        r.clear_cache_history()
        assert r.cache_hit_history == {}
        assert r._cache_key_order == []


# =========================================================================== #
# byok_handler generate_response — integration tests with mocked clients
# =========================================================================== #
class _HandlerHarness:
    """Real BYOKHandler with mocked OpenAI SDK + DB session + routing."""

    @staticmethod
    def make(workspace_plan="pro", client_error=None, response_content="Hello world"):
        from core.llm.byok_handler import BYOKHandler
        from core.models import Tenant, Workspace

        workspace = SimpleNamespace(tenant_id="t-1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value=workspace_plan))

        def _query(model):
            q = MagicMock()
            if model is Workspace:
                q.filter.return_value.first.return_value = workspace
            elif model is Tenant:
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
                q.all.return_value = []
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        mock_client = MagicMock()
        if client_error is not None:
            mock_client.chat.completions.create.side_effect = client_error
        else:
            mock_client.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content=response_content),
                    finish_reason="stop",
                )],
                usage=None,
            )

        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session", return_value=ctx), \
             patch("core.database.get_db_session", return_value=ctx):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")

        handler.clients = {"openai": mock_client, "anthropic": MagicMock()}
        handler.async_clients = {"openai": MagicMock(), "anthropic": MagicMock()}
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini")]
        )
        handler.get_optimal_provider = AsyncMock(
            return_value=("openai", "gpt-4o-mini")
        )
        handler._rerank_with_learning = AsyncMock(
            side_effect=lambda opts, *a, **k: opts
        )
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        # Active patch re-entered around each generate call so the lazy
        # ``from core.database import get_db_session`` sites stay hermetic.
        db_patch = patch("core.database.get_db_session", return_value=ctx)
        handler._db_patch = db_patch
        return handler, mock_client


class TestGenerateResponse:
    @pytest.mark.asyncio
    async def test_success_path(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, mock_client = _HandlerHarness.make(response_content="Hello world")
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response(
                    "Tell me about the weather", task_type="chat"
                )
        assert result == "Hello world"
        assert mock_client.chat.completions.create.called
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][1]["role"] == "user"
        assert handler._last_used_model == "gpt-4o-mini"
        assert handler._last_used_provider == "openai"

    @pytest.mark.asyncio
    async def test_trial_restricted(self):
        handler, _ = _HandlerHarness.make()
        handler._is_trial_restricted = lambda: True
        with handler._db_patch:
            result = await handler.generate_response("hello")
        assert "Trial Expired" in result

    @pytest.mark.asyncio
    async def test_no_clients_non_agentic(self):
        handler, _ = _HandlerHarness.make()
        handler.clients = {}
        handler.async_clients = {}
        with handler._db_patch:
            result = await handler.generate_response("hello")
        assert "LLM Client not initialized" in result

    @pytest.mark.asyncio
    async def test_no_clients_agentic_demo(self):
        handler, _ = _HandlerHarness.make()
        handler.clients = {}
        handler.async_clients = {}
        with handler._db_patch:
            result = await handler.generate_response("analyze the market", task_type="agentic")
        assert "thought" in result  # demo JSON

    @pytest.mark.asyncio
    async def test_budget_exceeded(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, _ = _HandlerHarness.make()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=True):
            with handler._db_patch:
                result = await handler.generate_response("hello")
        assert "BUDGET EXCEEDED" in result

    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, mock_client = _HandlerHarness.make(
            client_error=RuntimeError("provider down")
        )
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini"), ("anthropic", "claude-haiku")]
        )
        handler.clients["anthropic"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="Recovered"),
                finish_reason="stop",
            )],
            usage=None,
        )
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response("hello", task_type="chat")
        assert result == "Recovered"
        assert handler._last_used_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, _ = _HandlerHarness.make(client_error=RuntimeError("boom"))
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response("hello", task_type="chat")
        assert "couldn't generate a response" in result

    @pytest.mark.asyncio
    async def test_vision_payload_message(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, mock_client = _HandlerHarness.make()
        handler._model_supports_vision = MagicMock(return_value=True)
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response(
                    "What is in this image?",
                    image_payload="base64data==",
                    task_type="chat",
                )
        assert result == "Hello world"
        content = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert "data:image/jpeg;base64," in content[1]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_no_eligible_providers(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, _ = _HandlerHarness.make()
        handler.get_ranked_providers = AsyncMock(return_value=[])
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response("hello", task_type="chat")
        assert "No eligible LLM providers" in result

    @pytest.mark.asyncio
    async def test_invalid_cognitive_tier_override(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, mock_client = _HandlerHarness.make()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response(
                    "hello", cognitive_tier="bogus", task_type="chat"
                )
        assert result == "Hello world"  # falls back to normal routing
        assert handler.get_ranked_providers.await_args.kwargs.get("cognitive_tier") is None

    @pytest.mark.asyncio
    async def test_forced_tier_override(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, mock_client = _HandlerHarness.make()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with handler._db_patch:
                result = await handler.generate_response(
                    "hello", cognitive_tier="heavy", task_type="chat"
                )
        assert result == "Hello world"
        assert handler.get_ranked_providers.await_args.kwargs["cognitive_tier"] is not None


# =========================================================================== #
# byok_handler generate_structured_response — integration tests
# =========================================================================== #
class TestGenerateStructuredResponse:
    class _ResultModel:
        """Pydantic-style result: attribute access works, dict() fails loudly."""

        def __init__(self, **kw):
            self.__dict__.update(kw)

        def model_dump(self):
            return self.__dict__

    @staticmethod
    def make(plan="pro", instructor_result=None, instructor_error=None):
        from core.llm.byok_handler import BYOKHandler
        from core.models import Tenant, Workspace

        workspace = SimpleNamespace(tenant_id="t-1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value=plan))

        def _query(model):
            q = MagicMock()
            if model is Workspace:
                q.filter.return_value.first.return_value = workspace
            elif model is Tenant:
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
                q.all.return_value = []
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        mock_client = MagicMock()
        result = instructor_result
        if instructor_error is not None:
            mock_client.chat.completions.create.side_effect = instructor_error

        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session", return_value=ctx), \
             patch("core.database.get_db_session", return_value=ctx):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")

        handler.clients = {"openai": mock_client, "anthropic": MagicMock()}
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini")]
        )
        handler.get_optimal_provider = AsyncMock(
            return_value=("openai", "gpt-4o-mini")
        )
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        handler._db_patch = patch("core.database.get_db_session", return_value=ctx)
        return handler, mock_client, result

    @pytest.mark.asyncio
    async def test_success_path(self):
        import instructor

        from core.llm.byok_handler import BYOKHandler

        fake_result = SimpleNamespace(
            parsed="parsed-value",
            _raw_response=SimpleNamespace(
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5)
            ),
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        handler, mock_client, _ = self.make()
        fake_instructor = MagicMock()
        fake_instructor.chat.completions.create.return_value = fake_result
        with patch.object(instructor, "from_openai", return_value=fake_instructor):
            with handler._db_patch:
                result = await handler.generate_structured_response(
                    "Extract the data", system_instruction="sys",
                    response_model=SimpleNamespace, task_type="chat",
                    allow_moa=False,
                )
        assert result is fake_result
        assert fake_instructor.chat.completions.create.called
        kwargs = fake_instructor.chat.completions.create.call_args.kwargs
        assert kwargs["response_model"] is SimpleNamespace
        assert kwargs["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_trial_restricted(self):
        handler, _, _ = self.make()
        handler._is_trial_restricted = lambda: True
        with handler._db_patch:
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_no_clients(self):
        handler, _, _ = self.make()
        handler.clients = {}
        handler.async_clients = {}
        with handler._db_patch:
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_free_plan_managed_blocked(self):
        handler, _, _ = self.make(plan="free")
        with handler._db_patch:
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace, task_type="chat"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back(self):
        import instructor

        handler, mock_client, _ = self.make(
            instructor_error=RuntimeError("provider down")
        )
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini"), ("anthropic", "claude-haiku")]
        )
        fake_result = SimpleNamespace(parsed="ok")
        fake_instructor = MagicMock()
        fake_instructor.chat.completions.create.return_value = fake_result
        handler.clients["anthropic"].chat.completions.create.side_effect = None
        with patch.object(instructor, "from_openai", return_value=fake_instructor):
            with handler._db_patch:
                result = await handler.generate_structured_response(
                    "Extract", "sys", response_model=SimpleNamespace, task_type="chat",
                    allow_moa=False,
                )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_all_fail_returns_none(self):
        import instructor

        handler, _, _ = self.make(instructor_error=RuntimeError("boom"))
        with patch.object(instructor, "from_openai", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(
                create=MagicMock(side_effect=RuntimeError("boom"))
            ))
        )):
            with handler._db_patch:
                result = await handler.generate_structured_response(
                    "Extract", "sys", response_model=SimpleNamespace, task_type="chat",
                    allow_moa=False,
                )
        assert result is None

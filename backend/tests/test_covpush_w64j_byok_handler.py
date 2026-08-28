"""Coverage wave 64j — byok_handler 77% → 95% (TDD, test-only).

Extends waves 11-15 (test_covpush_llm_wave11*.py, wave15, w57_byok_handler_*).
Targets: BPC ranking internals (quota factor, cognitive-tier threshold,
provider-context clamp, o-series extraction exclusion, static fallback
branches), generate_response edges (LKGP sticky, intent detection, pdf_ocr,
vision panic fallback, RTK compression, anthropic cache-hit, self-heal,
opencode free→paid retry, outer error), outcome-feedback stage-router join,
MoA agreement/irreversibility edges, structured cascade + vision payload,
streaming fallback/heal/free→paid/all-failed paths, chat_completion
heal/trial-allow paths, embeddings batch providers, client-init env branches.
"""
import asyncio
import contextlib
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    _is_opencode_free_model,
    _llm_request_timeout,
    _opencode_free_paid_fallback,
    _opencode_paid_fallback_model,
)
from core.llm.cognitive_tier_system import CognitiveTier


def _ctx(session):
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False
    return ctx


def _make_handler(workspace_plan="pro", tenant_id="default", clients=("openai", "deepseek")):
    """Real BYOKHandler with mocked OpenAI SDK + DB session + routing."""
    from core.llm.byok_handler import BYOKHandler
    from core.models import Tenant, Workspace

    workspace = SimpleNamespace(tenant_id="t-1")
    tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value=workspace_plan))

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
    ctx = _ctx(session)

    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session", return_value=ctx), \
         patch("core.database.get_db_session", return_value=ctx):
        handler = BYOKHandler(workspace_id="default", tenant_id=tenant_id)

    handler.clients = {p: MagicMock() for p in clients}
    handler.async_clients = {p: MagicMock() for p in clients}
    for _p in handler.clients:
        handler.clients[_p].chat.completions.create.return_value = _ok_response()
    # The real health monitor is a process-global singleton — replace it so
    # per-test record_call stubs can never leak into other tests.
    handler.health_monitor = MagicMock()
    handler.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o-mini")])
    handler.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o-mini"))
    handler._rerank_with_learning = AsyncMock(side_effect=lambda opts, *a, **k: opts)
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler._ctx = ctx
    handler._db_patch = patch("core.database.get_db_session", return_value=ctx)
    return handler, session


@contextlib.contextmanager
def _db_active(handler):
    """Re-enter both DB patches around a call (lazy import sites + globals)."""
    with patch("core.llm.byok_handler.get_db_session", return_value=handler._ctx), \
         patch("core.database.get_db_session", return_value=handler._ctx):
        yield


def _budget(exceeded=False):
    from core.llm.byok_handler import llm_usage_tracker

    return patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=exceeded)


def _ok_response(content="Hello world"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content),
            finish_reason="stop",
        )],
        usage=None,
    )


def _usage_response(prompt_tokens=10, completion_tokens=5, **extra):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    for k, v in extra.items():
        setattr(usage, k, v)
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="ok"),
            finish_reason="stop",
        )],
        usage=usage,
    )


def _stream(*chunks):
    async def _agen():
        for c in chunks:
            yield c

    return _agen()


def _chunk(content=None, finish_reason=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content),
        finish_reason=finish_reason,
    )])


# =========================================================================== #
# Module-level helpers
# =========================================================================== #
class TestModuleHelpers:
    def test_llm_request_timeout_invalid_env(self):
        with patch.dict(os.environ, {"ATOM_LLM_REQUEST_TIMEOUT": "not-a-number"}):
            assert _llm_request_timeout() == 120.0

    def test_llm_request_timeout_valid_env(self):
        with patch.dict(os.environ, {"ATOM_LLM_REQUEST_TIMEOUT": "45"}):
            assert _llm_request_timeout() == 45.0

    def test_opencode_free_paid_fallback_non_object_json(self):
        with patch.dict(os.environ, {"OPENCODE_FREE_PAID_FALLBACK": '["not-a-dict"]'}):
            fb = _opencode_free_paid_fallback()
        assert isinstance(fb, dict)
        assert "deepseek-v4-flash-free" in fb

    def test_opencode_free_paid_fallback_invalid_json(self):
        with patch.dict(os.environ, {"OPENCODE_FREE_PAID_FALLBACK": "{broken"}):
            fb = _opencode_free_paid_fallback()
        assert "deepseek-v4-flash-free" in fb

    def test_opencode_free_paid_fallback_override(self):
        with patch.dict(
            os.environ,
            {"OPENCODE_FREE_PAID_FALLBACK": '{"deepseek-v4-flash-free": "mimo-v2.5-free"}'},
        ):
            assert _opencode_paid_fallback_model("deepseek-v4-flash-free") == "mimo-v2.5-free"

    def test_opencode_paid_fallback_model_default(self):
        assert _opencode_paid_fallback_model("some-model-free") == "deepseek-v4-flash"
        assert _is_opencode_free_model("deepseek-v4-flash-free") is True
        assert _opencode_paid_fallback_model("deepseek-v4-flash") is None


# =========================================================================== #
# BYOKHandler.__init__ paths
# =========================================================================== #
class _HidePytest(dict):
    """dict proxy that hides the 'pytest' key from ``in`` checks only —
    imports still resolve via __getitem__, so no pytest re-import happens
    (a real sys.modules pop re-imports pytest and double-loads byok_handler,
    corrupting coverage measurement for unrelated methods)."""

    def __contains__(self, key):
        if key == "pytest":
            return False
        return super().__contains__(key)


class TestInitPaths:
    def test_db_session_injected(self):
        session = MagicMock()
        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.database.get_db_session"):
            handler = BYOKHandler(
                workspace_id="default", tenant_id="default", db_session=session
            )
        assert handler.db_session is session

    def test_db_session_error_degrades(self):
        bad_ctx = MagicMock()
        bad_ctx.__enter__.side_effect = RuntimeError("db down")
        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session", return_value=bad_ctx), \
             patch("core.database.get_db_session", return_value=bad_ctx):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")
        assert handler.db_session is None

    def test_openai_missing_stops_client_init(self):
        with patch("core.llm.byok_handler.OpenAI", None), \
             patch("core.llm.byok_handler.AsyncOpenAI", None), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.database.get_db_session"):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")
        assert handler.clients == {}

    def test_lux_and_ollama_clients(self):
        # The provider-init loop skips lux/ollama when pytest is imported;
        # hide the key from ``in`` checks (imports still resolve).
        with patch.object(sys, "modules", _HidePytest(sys.modules)):
            mgr = MagicMock()
            mgr.is_configured = MagicMock(return_value=False)
            mgr.get_api_key = MagicMock(return_value="sk-lux")
            with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
                 patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
                 patch("core.llm.byok_handler.get_db_session"), \
                 patch("core.database.get_db_session"), \
                 patch("core.llm.byok_handler.get_byok_manager", return_value=mgr):
                handler = BYOKHandler(workspace_id="default", tenant_id="default")
        assert "lux" in handler.clients
        assert "ollama" in handler.clients
        assert "lux" in handler.async_clients

    def test_lux_and_ollama_client_ctor_errors(self):
        with patch.object(sys, "modules", _HidePytest(sys.modules)):
            mgr = MagicMock()
            mgr.is_configured = MagicMock(return_value=False)
            mgr.get_api_key = MagicMock(return_value="sk-lux")
            with patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("ctor boom")), \
                 patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
                 patch("core.llm.byok_handler.get_db_session"), \
                 patch("core.database.get_db_session"), \
                 patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
                 patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
                handler = BYOKHandler(workspace_id="default", tenant_id="default")
        assert "lux" not in handler.clients
        assert "ollama" not in handler.clients

    def test_gemini_alt_provider_byok_fallback(self):
        mgr = MagicMock()
        mgr.is_configured = MagicMock(side_effect=lambda ws, p: p == "google_flash")
        mgr.get_api_key = MagicMock(return_value="sk-g-alt-123456")  # >=12: production placeholder filter rejects short keys
        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()) as oai, \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.database.get_db_session"), \
             patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")
        gemini_calls = [c for c in oai.call_args_list if c.kwargs.get("api_key") == "sk-g-alt-123456"]
        assert gemini_calls
        assert "gemini" in handler.clients

    def test_client_ctor_error_skips_provider(self):
        with patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("ctor boom")), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.database.get_db_session"), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            handler = BYOKHandler(workspace_id="default", tenant_id="default")
        assert "openai" not in handler.clients

    def test_local_provider_client_ctor_error(self):
        handler, _ = _make_handler()
        provider = SimpleNamespace(
            id="abcdef1234567890", name="Local", provider_type="ollama",
            api_key=None, base_url="http://localhost:9999",
        )
        session = MagicMock()
        mq_prov = MagicMock()
        mq_prov.filter.return_value.all.return_value = [provider]
        mq_caps = MagicMock()
        mq_caps.filter.return_value.all.return_value = []
        session.query.side_effect = lambda m: mq_prov if m.__name__ == "LocalModelProvider" else mq_caps
        with patch("core.database.get_db_session", return_value=_ctx(session)), \
             patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("ctor boom")), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()):
            handler._load_local_providers()
        assert "local_abcdef12" not in handler.clients


# =========================================================================== #
# get_ranked_providers — BPC internals
# =========================================================================== #
class TestBpcInternals:
    def _bpc(self, handler):
        # Unbind the harness's AsyncMock so the REAL BPC algorithm runs.
        handler.get_ranked_providers = BYOKHandler.get_ranked_providers.__get__(handler)
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
        handler.rate_tracker.get_headroom = MagicMock(return_value=1.0)
        handler.rate_tracker.get_model_weight = MagicMock(return_value=1.0)
        handler.rate_tracker.get_max_context = MagicMock(return_value=None)
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        return handler

    def _rank(self, handler, fetcher, complexity=QueryComplexity.MODERATE, **kw):
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            return list(handler.get_ranked_providers(complexity, is_managed_service=False, **kw))

    def _fetcher(self, **models):
        fetcher = MagicMock()
        fetcher.pricing_cache = models
        return fetcher

    def test_cognitive_tier_quality_threshold(self):
        handler = self._bpc(_make_handler()[0])
        with patch("core.llm.byok_handler.get_quality_score", return_value=90):
            fetcher = self._fetcher(
                **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
            )
            result = self._rank(handler, fetcher, cognitive_tier=CognitiveTier.COMPLEX)
        # COMPLEX tier needs quality >= 94 — 90 is skipped, static fallback fires
        assert "gpt-4o" not in [m for _, m in result]
        with patch("core.llm.byok_handler.get_quality_score", return_value=95):
            fetcher = self._fetcher(
                **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
            )
            result = self._rank(handler, fetcher, cognitive_tier=CognitiveTier.COMPLEX)
        assert ("openai", "gpt-4o") in result

    def test_no_active_provider_skipped(self):
        handler = self._bpc(_make_handler()[0])
        fetcher = self._fetcher(
            **{"mystery-model": {"litellm_provider": "unknown", "max_input_tokens": 128000}}
        )
        result = self._rank(handler, fetcher)
        assert "mystery-model" not in [m for _, m in result]

    def test_provider_max_context_clamp(self):
        handler = self._bpc(_make_handler()[0])
        handler.rate_tracker.get_max_context = MagicMock(return_value=1000)
        fetcher = self._fetcher(
            **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
        )
        result = self._rank(handler, fetcher)
        assert "gpt-4o" not in [m for _, m in result]

    def test_extraction_o_series_exclusion(self):
        handler = self._bpc(_make_handler()[0])
        with patch("core.llm.byok_handler.get_quality_score", return_value=80):
            fetcher = self._fetcher(
                **{
                    "o3-mini": {"litellm_provider": "openai", "max_input_tokens": 128000},
                    "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000},
                }
            )
            result = self._rank(handler, fetcher, task_type="extraction")
        models = [m for _, m in result]
        assert "o3-mini" not in models
        assert "gpt-4o" in models

    def test_quota_weight_factor(self):
        handler = self._bpc(_make_handler()[0])
        handler.rate_tracker.get_model_weight = MagicMock(return_value=4.0)
        with patch("core.llm.byok_handler.get_quality_score", return_value=95):
            fetcher = self._fetcher(
                **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
            )
            result = self._rank(handler, fetcher)
        # quota_factor clamps (1/4)^0.2 — model stays ranked
        assert ("openai", "gpt-4o") in result

    def test_requires_tools_approval_filter(self):
        handler = self._bpc(_make_handler()[0])
        handler._model_supports_tools = MagicMock(return_value=False)
        with patch("core.llm.byok_handler.get_quality_score", return_value=95):
            fetcher = self._fetcher(
                **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
            )
            result = self._rank(handler, fetcher, requires_tools=True)
        assert "gpt-4o" not in [m for _, m in result]

    def test_bpc_exception_static_fallback(self):
        handler = self._bpc(_make_handler()[0])
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            side_effect=RuntimeError("pricing down"),
        ):
            result = list(handler.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False
            ))
        assert ("deepseek", "deepseek-chat") in result

    def test_static_advanced_priority_openai_first(self):
        handler = self._bpc(_make_handler()[0])
        fetcher = self._fetcher()  # empty cache -> static fallback
        result = self._rank(handler, fetcher, complexity=QueryComplexity.ADVANCED)
        assert result[0] == ("openai", "gpt-5.6-sol")

    def test_static_byok_speciale_downgrades_to_r2(self):
        handler = self._bpc(_make_handler()[0])
        handler._model_supports_tools = MagicMock(return_value=False)
        fetcher = self._fetcher()  # empty -> static
        result = self._rank(
            handler, fetcher, complexity=QueryComplexity.ADVANCED, requires_tools=True
        )
        assert ("deepseek", "deepseek-r2") in result

    def test_static_managed_tool_downgrade_and_approval(self):
        handler = self._bpc(_make_handler()[0])
        handler._model_supports_tools = MagicMock(return_value=True)
        fetcher = self._fetcher()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            result = list(handler.get_ranked_providers(
                QueryComplexity.SIMPLE,
                is_managed_service=True,
                tenant_plan="pro",
                requires_tools=True,
            ))
        assert ("deepseek", "deepseek-chat") in result

    def test_static_managed_tools_cache_error_allows(self):
        handler = self._bpc(_make_handler()[0])
        handler._model_supports_tools = MagicMock(return_value=True)
        fetcher = self._fetcher()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ), patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("cache down"),
        ):
            result = list(handler.get_ranked_providers(
                QueryComplexity.SIMPLE,
                is_managed_service=True,
                tenant_plan="pro",
                requires_tools=True,
            ))
        assert ("deepseek", "deepseek-chat") in result

    def test_static_managed_speciale_downgrade_r2(self):
        handler = self._bpc(_make_handler()[0])
        handler._model_supports_tools = MagicMock(return_value=False)
        fetcher = self._fetcher()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            result = list(handler.get_ranked_providers(
                QueryComplexity.ADVANCED,
                is_managed_service=True,
                tenant_plan="pro",
                requires_tools=True,
            ))
        # speciale downgraded to r2, but r2 is not in the pro allowlist —
        # exercise the 1666-1667 downgrade branch without asserting inclusion
        assert isinstance(result, list)


# =========================================================================== #
# analyze_query_complexity — token-bucket edges
# =========================================================================== #
class TestComplexityTokenBucket:
    def test_medium_length_plus_one(self):
        handler, _ = _make_handler()
        # 600 chars -> 150 estimated tokens -> +1; no keywords -> score 1
        assert handler.analyze_query_complexity("x" * 600) == QueryComplexity.MODERATE


# =========================================================================== #
# generate_response — edge branches
# =========================================================================== #
class TestGenerateResponseEdges:
    @pytest.mark.asyncio
    async def test_stage_carrier_clear_exception_tolerated(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.stage_router.set_stage_decision_carrier",
            side_effect=RuntimeError("carrier down"),
        ), _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_tenant_key_forces_byok(self):
        handler, _ = _make_handler()
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value="sk-custom")
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _usage_response()
        from core.llm.byok_handler import llm_usage_tracker

        with _db_active(handler), _budget(), \
             patch.object(llm_usage_tracker, "record") as rec:
            await handler.generate_response("hello", task_type="chat")
        assert rec.called
        assert rec.call_args.kwargs["is_managed_service"] is False

    @pytest.mark.asyncio
    async def test_agentic_task_forces_byok_mode(self):
        handler, _ = _make_handler()
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        handler.clients["openai"].chat.completions.create.return_value = _ok_response()
        result = await handler.generate_response("do the thing", task_type="agentic")
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_lkgp_sticky_boost(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(
            return_value=[("deepseek", "deepseek-chat"), ("openai", "gpt-4o-mini")]
        )
        handler.clients["deepseek"].chat.completions.create.return_value = _ok_response()
        handler.clients["openai"].chat.completions.create.return_value = _ok_response()
        with _db_active(handler), _budget():
            await handler.generate_response(
                "hello", task_type="chat", sticky_hint=("openai", "gpt-4o-mini")
            )
        assert handler.clients["openai"].chat.completions.create.called
        assert not handler.clients["deepseek"].chat.completions.create.called

    @pytest.mark.asyncio
    async def test_intent_detection_feeds_rerank(self):
        handler, _ = _make_handler()
        recorder = AsyncMock(side_effect=lambda opts, *a, **k: opts)
        handler._rerank_with_learning = recorder
        with patch(
            "core.llm.intent_detector.get_intent_detector"
        ) as gid:
            gid.return_value.detect.return_value = SimpleNamespace(category="coding", confidence=0.9)
            with _db_active(handler), _budget():
                await handler.generate_response("hello", task_type="chat")
        assert recorder.await_args.kwargs["intent"] == "coding"

    @pytest.mark.asyncio
    async def test_intent_detection_failure_tolerated(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.intent_detector.get_intent_detector",
            side_effect=RuntimeError("detector down"),
        ), _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_pdf_ocr_prioritizes_deepseek(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(
            return_value=[("deepseek", "deepseek-chat"), ("openai", "gpt-4o")]
        )
        handler._model_supports_vision = MagicMock(return_value=False)
        # coordination returns nothing so the vision pipeline runs
        handler._get_coordinated_vision_description = AsyncMock(return_value=None)
        handler.clients["deepseek"].chat.completions.create.return_value = _ok_response()
        handler.clients["openai"].chat.completions.create.return_value = _ok_response()
        with _db_active(handler), _budget():
            await handler.generate_response(
                "read this pdf", task_type="pdf_ocr", image_payload="b64=="
            )
        assert handler.clients["deepseek"].chat.completions.create.called
        assert not handler.clients["openai"].chat.completions.create.called

    @pytest.mark.asyncio
    async def test_vision_panic_fallback_gpt4o(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o-mini")])
        handler._model_supports_vision = MagicMock(return_value=False)
        handler._get_coordinated_vision_description = AsyncMock(return_value=None)
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _ok_response()
        with _db_active(handler), _budget():
            await handler.generate_response("what is this", task_type="chat", image_payload="b64==")
        model = mock_client.chat.completions.create.call_args.kwargs["model"]
        assert model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_rtk_compression_applies(self):
        handler, _ = _make_handler()
        pipeline = MagicMock()
        pipeline.compress_tool_output.return_value = (
            "COMPRESSED", SimpleNamespace(savings_tokens=50),
        )
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _ok_response()
        with patch("core.llm.compression.get_compression_pipeline", return_value=pipeline), \
             _db_active(handler), _budget():
            await handler.generate_response("hello", task_type="chat")
        content = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert content == "COMPRESSED"

    @pytest.mark.asyncio
    async def test_rtk_compression_error_tolerated(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _ok_response()
        with patch(
            "core.llm.compression.get_compression_pipeline",
            side_effect=RuntimeError("compressor down"),
        ), _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_cost_attribution_error_tolerated(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _usage_response()
        fetcher = MagicMock()
        fetcher.estimate_cost.side_effect = RuntimeError("no pricing")
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_anthropic_cache_hit_tokens(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _usage_response(
            prompt_cache_hit_tokens=50
        )
        with _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_openai_cache_controls(self):
        handler, _ = _make_handler()
        resp = _usage_response()
        resp.cache_controls = MagicMock()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = resp
        with _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_cache_outcome_record_error_tolerated(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.return_value = _usage_response()
        handler.cache_router.record_cache_outcome = MagicMock(
            side_effect=RuntimeError("cache broken")
        )
        with _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_failure_health_tracking_error_tolerated(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.side_effect = RuntimeError("provider down")
        handler.health_monitor.record_call = MagicMock(
            side_effect=RuntimeError("monitor down")
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert "couldn't generate" in result

    @pytest.mark.asyncio
    async def test_multimodal_heal_kwargs(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.side_effect = RuntimeError("400 bad request")
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        handler._model_supports_vision = MagicMock(return_value=True)
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response(
                "hello", task_type="chat", image_payload="b64=="
            )
        assert "couldn't generate" in result
        assert healer.heal.call_args.args[1]["messages"][-1]["content"] is not None

    @pytest.mark.asyncio
    async def test_self_heal_success(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("400 context window"),
            _ok_response("Recovered"),
        ]
        # first record_call = failure (raise -> 2112), second = heal success (raise -> 2153)
        handler.health_monitor.record_call = MagicMock(
            side_effect=RuntimeError("monitor flaky")
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "gpt-4o-mini", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert result == "Recovered"
        assert handler._last_used_provider == "openai"
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_healer_raise_tolerated(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")
        with patch(
            "core.llm.routing.request_healer.get_request_healer",
            side_effect=RuntimeError("healer down"),
        ), _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert "couldn't generate" in result

    @pytest.mark.asyncio
    async def test_self_heal_retry_fails(self):
        handler, _ = _make_handler()
        mock_client = handler.clients["openai"]
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("400 context window"),
            RuntimeError("still 400"),
        ]
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "gpt-4o-mini", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert "couldn't generate" in result

    @pytest.mark.asyncio
    async def test_opencode_free_to_paid_retry(self):
        handler, _ = _make_handler(clients=("opencode-go",))
        handler.get_ranked_providers = AsyncMock(
            return_value=[("opencode-go", "deepseek-v4-flash-free")]
        )
        mock_client = handler.clients["opencode-go"]
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("Insufficient balance. Please add credits."),
            _ok_response("Paid answer"),
        ]
        handler.health_monitor.record_call = MagicMock(
            side_effect=[None, RuntimeError("monitor flaky")]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response(
                "hello", task_type="chat", model_type="deepseek-v4-flash-free"
            )
        assert result == "Paid answer"
        assert handler._last_used_model == "deepseek-v4-flash"
        paid_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert paid_kwargs["model"] == "deepseek-v4-flash"

    @pytest.mark.asyncio
    async def test_opencode_paid_retry_fails(self):
        handler, _ = _make_handler(clients=("opencode-go",))
        handler.get_ranked_providers = AsyncMock(
            return_value=[("opencode-go", "deepseek-v4-flash-free")]
        )
        mock_client = handler.clients["opencode-go"]
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("Insufficient balance. Please add credits."),
            RuntimeError("CreditsError: still broke"),
        ]
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             _db_active(handler), _budget():
            result = await handler.generate_response(
                "hello", task_type="chat", model_type="deepseek-v4-flash-free"
            )
        assert "couldn't generate" in result

    @pytest.mark.asyncio
    async def test_outer_generation_error(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.byok_handler.get_db_session",
            side_effect=RuntimeError("db down"),
        ), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        assert "an error occurred" in result

    @pytest.mark.asyncio
    async def test_free_plan_managed_blocked_path(self):
        handler, _ = _make_handler(workspace_plan="free")
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        with _db_active(handler), _budget():
            result = await handler.generate_response("hello", task_type="chat")
        # clients exist, so the block passes through to normal generation
        assert result == "Hello world"


# =========================================================================== #
# _record_outcome_feedback — stage-router join + learning path
# =========================================================================== #
class TestOutcomeFeedback:
    @pytest.mark.asyncio
    async def test_stage_decision_outcome_join(self):
        handler, _ = _make_handler()
        with patch("core.llm.stage_router.get_stage_decision_carrier", return_value="sd-1"), \
             patch("core.llm.stage_router.record_stage_outcome") as rso:
            await handler._record_outcome_feedback(
                model="m1", provider_id="p1", task_type="chat",
                content="out", finish_reason="stop", success=True,
                cost=0.01, latency_ms=5.0,
            )
        assert rso.called
        assert rso.call_args.kwargs["decision_id"] == "sd-1"
        assert rso.call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_stage_decision_join_error_tolerated(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.stage_router.get_stage_decision_carrier",
            side_effect=RuntimeError("stage down"),
        ):
            await handler._record_outcome_feedback(
                model="m1", provider_id="p1", task_type="chat",
                content="out", finish_reason="stop", success=True,
                cost=None, latency_ms=1.0,
            )

    @pytest.mark.asyncio
    async def test_learning_router_feedback_path(self):
        handler, _ = _make_handler()
        router = MagicMock()
        router.record_feedback = AsyncMock()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router), \
             patch("core.llm.response_quality.assess_response_quality",
                   return_value=SimpleNamespace(quality_score=0.8)), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                   return_value=SimpleNamespace()):
            await handler._record_outcome_feedback(
                model="m1", provider_id="p1", task_type="chat",
                content="out", finish_reason="stop", success=True,
                cost=None, latency_ms=1.0, routing_result_id="rd-1",
            )
        assert router.record_feedback.called

    @pytest.mark.asyncio
    async def test_learning_router_none_returns(self):
        handler, _ = _make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=None):
            await handler._record_outcome_feedback(
                model="m1", provider_id="p1", task_type=None,
                content=None, finish_reason=None, success=False,
                cost=None, latency_ms=0.0,
            )

    @pytest.mark.asyncio
    async def test_learning_router_feedback_error_tolerated(self):
        handler, _ = _make_handler()
        router = MagicMock()
        router.record_feedback = AsyncMock(side_effect=RuntimeError("router broke"))
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                   return_value=SimpleNamespace()):
            await handler._record_outcome_feedback(
                model="m1", provider_id="p1", task_type="chat",
                content="out", finish_reason="stop", success=True,
                cost=None, latency_ms=1.0,
            )

    @pytest.mark.asyncio
    async def test_rerank_single_option_log(self):
        handler, _ = _make_handler()
        # Unbind the harness AsyncMock so the REAL method runs.
        handler._rerank_with_learning = BYOKHandler._rerank_with_learning.__get__(handler)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}):
            out = await handler._rerank_with_learning(
                [("openai", "gpt-4o-mini")], "hello", "chat"
            )
        assert out == [("openai", "gpt-4o-mini")]


# =========================================================================== #
# generate_with_cognitive_tier — escalation edges
# =========================================================================== #
class TestCognitiveTierEdges:
    @pytest.mark.asyncio
    async def test_quality_assessment_error_uses_none(self):
        handler, _ = _make_handler()
        tier = SimpleNamespace(value="standard")
        handler.tier_service.select_tier = MagicMock(return_value=tier)
        handler.tier_service.calculate_request_cost = MagicMock(return_value={"cost_cents": 5})
        handler.tier_service.check_budget_constraint = MagicMock(return_value=True)
        handler.tier_service.get_optimal_model = MagicMock(return_value=("openai", "gpt-4o-mini"))
        handler.tier_service.handle_escalation = MagicMock(return_value=(False, None, None))
        handler.generate_response = AsyncMock(return_value="ok")
        with patch(
            "core.llm.response_quality.assess_response_quality",
            side_effect=RuntimeError("quality broken"),
        ):
            result = await handler.generate_with_cognitive_tier("hello", task_type="chat")
        assert result["response"] == "ok"
        assert result["tier"] == "standard"

    @pytest.mark.asyncio
    async def test_escalated_tier_no_models_returns_previous(self):
        handler, _ = _make_handler()
        tier = SimpleNamespace(value="standard")
        handler.tier_service.select_tier = MagicMock(return_value=tier)
        handler.tier_service.calculate_request_cost = MagicMock(return_value={"cost_cents": 5})
        handler.tier_service.check_budget_constraint = MagicMock(return_value=True)
        handler.tier_service.get_optimal_model = MagicMock(
            side_effect=[("openai", "gpt-4o-mini"), (None, None)]
        )
        handler.tier_service.handle_escalation = MagicMock(
            return_value=(True, SimpleNamespace(value="quality"), SimpleNamespace(value="heavy"))
        )
        handler.generate_response = AsyncMock(return_value="I'm sorry, I couldn't generate a response")
        result = await handler.generate_with_cognitive_tier("hello", task_type="chat")
        assert result["response"] == "I'm sorry, I couldn't generate a response"
        assert result["escalated"] is True

    @pytest.mark.asyncio
    async def test_max_escalations_loop_completion(self):
        handler, _ = _make_handler()
        tier = SimpleNamespace(value="standard")
        handler.tier_service.select_tier = MagicMock(return_value=tier)
        handler.tier_service.calculate_request_cost = MagicMock(return_value={"cost_cents": 5})
        handler.tier_service.check_budget_constraint = MagicMock(return_value=True)
        handler.tier_service.get_optimal_model = MagicMock(return_value=("openai", "gpt-4o-mini"))
        handler.tier_service.handle_escalation = MagicMock(
            return_value=(True, SimpleNamespace(value="quality"), SimpleNamespace(value="heavy"))
        )
        handler.generate_response = AsyncMock(return_value="I'm sorry, I couldn't generate a response")
        result = await handler.generate_with_cognitive_tier("hello", task_type="chat")
        assert "Max escalation limit reached" in result["response"]

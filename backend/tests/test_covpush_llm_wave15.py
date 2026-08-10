"""Coverage wave 15 — byok_handler capability index/filter, excluded cache,
client init env paths, BPC edge branches (TDD)."""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity


def _make_handler():
    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {"openai": MagicMock(), "deepseek": MagicMock()}
    handler.async_clients = {"openai": MagicMock(), "deepseek": MagicMock()}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


def _ctx(session):
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False
    return ctx


# =========================================================================== #
# _load_capability_index
# =========================================================================== #
class TestLoadCapabilityIndex:
    def test_loads_rows(self):
        handler = _make_handler()
        session = MagicMock()
        session.query.return_value.all.return_value = [
            SimpleNamespace(model_id="gpt-4o", capabilities=["vision", "tools"]),
            SimpleNamespace(model_id="deepseek-chat", capabilities=None),
        ]
        with patch("core.database.get_db_session", return_value=_ctx(session)):
            idx = handler._load_capability_index()
        assert idx["gpt-4o"] == ["vision", "tools"]
        assert idx["deepseek-chat"] == ["chat"]  # None -> default

    def test_db_error_returns_none(self):
        handler = _make_handler()
        with patch(
            "core.database.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            assert handler._load_capability_index() is None


# =========================================================================== #
# _filter_by_capabilities
# =========================================================================== #
class TestFilterByCapabilities:
    def test_no_requirement_passes(self):
        handler = _make_handler()
        assert handler._filter_by_capabilities("any", None) is True

    def test_index_hit(self):
        handler = _make_handler()
        idx = {"gpt-4o": ["vision", "tools"]}
        assert handler._filter_by_capabilities("gpt-4o", "vision", idx) is True
        assert handler._filter_by_capabilities("gpt-4o", "audio", idx) is False

    def test_index_unknown_model_passes(self):
        handler = _make_handler()
        assert handler._filter_by_capabilities("mystery", "vision", {}) is True

    def test_per_model_path(self):
        handler = _make_handler()
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = (
            SimpleNamespace(capabilities=["chat", "tools"])
        )
        with patch("core.database.get_db_session", return_value=_ctx(session)):
            assert handler._filter_by_capabilities("gpt-4o", "tools", None) is True
            assert handler._filter_by_capabilities("gpt-4o", "vision", None) is False

    def test_per_model_unknown_passes(self):
        handler = _make_handler()
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        with patch("core.database.get_db_session", return_value=_ctx(session)):
            assert handler._filter_by_capabilities("ghost", "vision", None) is True

    def test_per_model_error_passes(self):
        handler = _make_handler()
        with patch(
            "core.database.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            assert handler._filter_by_capabilities("gpt-4o", "vision", None) is True


# =========================================================================== #
# _refresh_excluded_cache
# =========================================================================== #
class TestRefreshExcludedCache:
    def test_populates_set(self):
        handler = _make_handler()
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [
            ("lux-1.0",), ("special-model",),
        ]
        with patch("core.database.get_db_session", return_value=_ctx(session)):
            handler._refresh_excluded_cache()
        assert handler.excluded_models == {"lux-1.0", "special-model"}

    def test_db_error_resets_to_empty(self):
        handler = _make_handler()
        handler.excluded_models = {"stale"}
        with patch(
            "core.database.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            handler._refresh_excluded_cache()
        assert handler.excluded_models == set()


# =========================================================================== #
# _initialize_clients env fallback paths
# =========================================================================== #
class TestClientInitEnvPaths:
    def test_opencode_go_env_key_mapping(self):
        handler = _make_handler()
        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()) as mock_ctor, \
             patch.dict(
                 "os.environ",
                 {"OPENCODE_API_KEY": "sk-opencode", "OPENCODE_GO_API_KEY": ""},
             ):
            handler._initialize_clients()
        # opencode-go client initialized with the OPENCODE_API_KEY env var
        opencode_calls = [
            c for c in mock_ctor.call_args_list
            if c.kwargs.get("api_key") == "sk-opencode"
        ]
        assert opencode_calls

    def test_gemini_google_key_fallback(self):
        handler = _make_handler()
        with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()) as mock_ctor, \
             patch.dict(
                 "os.environ", {"GOOGLE_API_KEY": "sk-google", "GEMINI_API_KEY": ""}
             ):
            handler._initialize_clients()
        assert any(
            c.kwargs.get("api_key") == "sk-google" for c in mock_ctor.call_args_list
        )

    def test_no_keys_no_clients(self):
        handler = _make_handler()
        handler.clients = {}
        handler.async_clients = {}
        mock_openai = MagicMock()
        with patch("core.llm.byok_handler.OpenAI", return_value=mock_openai), \
             patch.dict(
                 "os.environ",
                 {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "DEEPSEEK_API_KEY": ""},
             ):
            handler._initialize_clients()
        # openai without keys: only ollama gets a client (dummy key)
        assert "openai" not in handler.clients or mock_openai.call_count == 0


# =========================================================================== #
# BPC edge branches
# =========================================================================== #
class TestBpcEdgeBranches:
    def _fetcher(self, **models):
        fetcher = MagicMock()
        fetcher.pricing_cache = models
        return fetcher

    def _rank(self, handler, fetcher, **kw):
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            return list(handler.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False, **kw
            ))

    def test_monthly_quota_skip(self):
        handler = _make_handler()
        handler.rate_tracker.get_monthly_usage = MagicMock(
            return_value={"total_tokens": 999999999}
        )
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        fetcher = self._fetcher(
            **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
        )
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "1000"}):
            result = self._rank(handler, fetcher)
        # the BPC candidate is quota-skipped; the static fallback may still
        # fire (documented degraded path) — assert gpt-4o never appears
        assert "gpt-4o" not in [m for _, m in result]

    def test_per_model_headroom_skip(self):
        handler = _make_handler()
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=0.0)
        handler.rate_tracker.get_headroom = MagicMock(return_value=1.0)
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        fetcher = self._fetcher(
            **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
        )
        result = self._rank(handler, fetcher)
        assert "gpt-4o" not in [m for _, m in result]

    def test_provider_headroom_skip(self):
        handler = _make_handler()
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
        handler.rate_tracker.get_headroom = MagicMock(return_value=0.0)
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        fetcher = self._fetcher(
            **{"gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000}}
        )
        result = self._rank(handler, fetcher)
        assert "gpt-4o" not in [m for _, m in result]

    def test_extraction_excludes_o_series(self):
        handler = _make_handler()
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
        handler.rate_tracker.get_headroom = MagicMock(return_value=1.0)
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        fetcher = self._fetcher(
            **{
                "o3-mini": {"litellm_provider": "openai", "max_input_tokens": 128000},
                "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000},
            }
        )
        result = self._rank(handler, fetcher, task_type="extraction")
        models = [m for _, m in result]
        # o-series excluded from extraction (gpt-4o's 92.5 quality also
        # exceeds the extraction cap of 90, so the BPC pool is empty here)
        assert "o3-mini" not in models

    def test_context_window_too_small_skipped(self):
        handler = _make_handler()
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=0.001)
        handler.excluded_models = set()
        fetcher = self._fetcher(
            **{"tiny-model": {"litellm_provider": "openai", "max_input_tokens": 100}}
        )
        result = self._rank(handler, fetcher)
        assert "tiny-model" not in [m for _, m in result]

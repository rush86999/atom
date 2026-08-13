"""Coverage wave 64d — core/dynamic_pricing_fetcher.py (TDD, mocked httpx,
no network, no real cache files).

Covers: cache load/save/validity (incl. corrupt file, missing file, IO
errors, expiry), fetch_litellm_pricing (dict/non-dict entries, fallback
model families present/absent, HTTP/json/network errors), fetch_openrouter
(entries, empty data, curated-overrides passthrough, errors),
fetch_opencode (bare list + envelope payloads, missing ids, defaults,
empty payload -> static fallback, exception -> static fallback),
_static fallback shape, refresh_pricing (cache hit, force, merge
precedence, capabilities merge, save), get_model_price (exact,
case-insensitive, unknown), get_provider_models (name/provider match,
sorting), get_cheapest_models (zero-cost skip, sort, limit),
compare_providers (field provider + name-inference branches, zero-cost
skip), estimate_cost, model_supports_cache (explicit field, provider
inference, unknown), _infer_provider (every branch), _infer_capabilities
(tools/vision/reasoning matrix), get_model_capabilities, cache min tokens,
is_pricing_estimated, and the module-level singleton/initialized/sync/
refresh helpers (both running-loop and no-loop sync paths).
"""
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import core.dynamic_pricing_fetcher as dpf


# ---------------------------------------------------------------------------
# httpx mocking helpers
# ---------------------------------------------------------------------------


def make_httpx(response=None, client=None, aenter_error=None):
    """Build a MagicMock replacement for httpx.AsyncClient.

    Returns (client_mock, cls_mock); patch
    ``core.dynamic_pricing_fetcher.httpx.AsyncClient`` with ``cls_mock``.
    """
    if client is None:
        client = MagicMock()
        client.get = AsyncMock(return_value=response if response is not None else MagicMock())
    cls_mock = MagicMock()
    enter = MagicMock()
    enter.__aenter__ = AsyncMock(return_value=client)
    enter.__aexit__ = AsyncMock(return_value=False)
    if aenter_error:
        enter.__aenter__ = AsyncMock(side_effect=aenter_error)
    cls_mock.return_value = enter
    return client, cls_mock


def json_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


@pytest.fixture
def fetcher(tmp_path, monkeypatch):
    """Fresh fetcher with a temp cache path and reset module singletons."""
    cache_file = tmp_path / "ai_pricing_cache.json"
    monkeypatch.setattr(dpf, "PRICING_CACHE_PATH", cache_file)
    monkeypatch.setattr(dpf, "_pricing_fetcher", None)
    monkeypatch.setattr(dpf, "_pricing_initialized", False)
    return dpf.DynamicPricingFetcher()


# ===========================================================================
# Cache load/save/validity
# ===========================================================================


class TestCacheLoad:
    def test_load_missing_file_is_empty(self, fetcher):
        assert fetcher.pricing_cache == {}
        assert fetcher.last_fetch is None

    def test_load_valid_file(self, fetcher, tmp_path):
        stamp = "2026-08-01T12:00:00+00:00"
        (tmp_path / "ai_pricing_cache.json").write_text(json.dumps({
            "pricing": {"gpt-4o": {"input_cost_per_token": 0.01}},
            "last_fetch": stamp,
            "source": "litellm+openrouter",
        }))
        f = dpf.DynamicPricingFetcher()
        assert f.pricing_cache == {"gpt-4o": {"input_cost_per_token": 0.01}}
        assert f.last_fetch == datetime.fromisoformat(stamp)

    def test_load_without_last_fetch(self, fetcher, tmp_path):
        (tmp_path / "ai_pricing_cache.json").write_text(json.dumps({
            "pricing": {"m": {}},
        }))
        f = dpf.DynamicPricingFetcher()
        assert f.last_fetch is None
        assert f.pricing_cache == {"m": {}}

    def test_load_corrupt_json_tolerated(self, fetcher, tmp_path):
        (tmp_path / "ai_pricing_cache.json").write_text("{not json")
        f = dpf.DynamicPricingFetcher()  # must not raise
        assert f.pricing_cache == {}

    def test_load_read_error_tolerated(self, fetcher, tmp_path):
        (tmp_path / "ai_pricing_cache.json").write_text("{}")
        with patch("builtins.open", side_effect=OSError("denied")):
            f = dpf.DynamicPricingFetcher()
        assert f.pricing_cache == {}


class TestCacheSave:
    def test_save_writes_file(self, fetcher, tmp_path):
        fetcher.pricing_cache = {"a": {"x": 1}}
        fetcher.last_fetch = datetime(2026, 8, 1, 12, 0, 0)
        fetcher._save_cache()
        data = json.loads((tmp_path / "ai_pricing_cache.json").read_text())
        assert data["pricing"] == {"a": {"x": 1}}
        assert data["last_fetch"] == "2026-08-01T12:00:00"
        assert data["source"] == "litellm+openrouter"

    def test_save_without_last_fetch(self, fetcher, tmp_path):
        fetcher.pricing_cache = {}
        fetcher.last_fetch = None
        fetcher._save_cache()
        data = json.loads((tmp_path / "ai_pricing_cache.json").read_text())
        assert data["last_fetch"] is None

    def test_save_mkdir_failure_tolerated(self, fetcher):
        with patch("pathlib.Path.mkdir", side_effect=OSError("no space")):
            fetcher._save_cache()  # must not raise

    def test_save_write_failure_tolerated(self, fetcher):
        with patch("builtins.open", side_effect=OSError("readonly")):
            fetcher._save_cache()  # must not raise


class TestCacheValidity:
    def test_no_last_fetch_invalid(self, fetcher):
        fetcher.pricing_cache = {"m": {}}
        assert fetcher._is_cache_valid() is False

    def test_no_pricing_invalid(self, fetcher):
        fetcher.last_fetch = datetime.now()
        assert fetcher._is_cache_valid() is False

    def test_fresh_cache_valid(self, fetcher):
        fetcher.last_fetch = datetime.now()
        fetcher.pricing_cache = {"m": {}}
        assert fetcher._is_cache_valid() is True

    def test_expired_cache_invalid(self, fetcher):
        fetcher.last_fetch = datetime.now() - timedelta(hours=25)
        fetcher.pricing_cache = {"m": {}}
        assert fetcher._is_cache_valid() is False


# ===========================================================================
# fetch_litellm_pricing
# ===========================================================================


LITELLM_PAYLOAD = {
    "gpt-4o": {
        "input_cost_per_token": 0.01, "output_cost_per_token": 0.02,
        "max_tokens": 1000, "max_input_tokens": 2000,
        "max_output_tokens": 3000, "litellm_provider": "openai",
        "mode": "chat", "supports_cache": True,
    },
    "claude-3-5-sonnet": {
        "input_cost_per_token": 0.005, "output_cost_per_token": 0.01,
    },
    "MiniMax-M3": {"input_cost_per_token": 9.9},  # present -> skip fallback
    "glm-5.2": {"input_cost_per_token": 9.9},      # present -> skip fallback
    "kimi-k2.6": {"input_cost_per_token": 9.9},    # present -> skip fallback
    "lux-1.0": {"input_cost_per_token": 9.9},      # present -> skip fallback
    "not-a-dict": "just a string",                 # non-dict entry -> skipped
}


class TestFetchLitellm:
    @pytest.mark.asyncio
    async def test_success_transform_and_fallbacks(self, fetcher):
        resp = json_response(LITELLM_PAYLOAD)
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()

        # transformed entry
        assert pricing["gpt-4o"] == {
            "input_cost_per_token": 0.01, "output_cost_per_token": 0.02,
            "max_tokens": 1000, "max_input_tokens": 2000,
            "max_output_tokens": 3000, "litellm_provider": "openai",
            "mode": "chat", "source": "litellm", "supports_cache": True,
        }
        # defaults for missing keys
        assert pricing["claude-3-5-sonnet"]["litellm_provider"] == "unknown"
        assert pricing["claude-3-5-sonnet"]["mode"] == "chat"
        assert pricing["claude-3-5-sonnet"]["supports_cache"] is False
        # non-dict entry skipped
        assert "not-a-dict" not in pricing
        # MiniMax-M3 present -> not overridden with estimate
        assert pricing["MiniMax-M3"]["input_cost_per_token"] == 9.9
        # MiniMax-M3-highspeed absent -> estimated fallback added
        assert pricing["MiniMax-M3-highspeed"]["source"] == "estimated"
        assert pricing["MiniMax-M3-highspeed"]["max_tokens"] == 512000
        # M2.7 fallbacks
        assert pricing["MiniMax-M2.7"]["max_tokens"] == 204000
        assert pricing["MiniMax-M2.7-highspeed"]["source"] == "estimated"
        # GLM: glm-5.2 present; glm-5/4.6/4.5 added
        assert pricing["glm-5"]["input_cost_per_token"] == 0.0000015
        assert pricing["glm-4.6"]["max_tokens"] == 128000
        assert pricing["glm-4.5"]["litellm_provider"] == "glm"
        assert pricing["glm-5.2"]["input_cost_per_token"] == 9.9
        # Kimi: k2.6 present; others added
        assert pricing["kimi-k2-thinking"]["supports_cache"] is True
        assert pricing["kimi-k2"]["input_cost_per_token"] == 0.0000007
        assert pricing["kimi-k3"]["max_tokens"] == 1000000
        assert pricing["kimi-k2.6"]["input_cost_per_token"] == 9.9
        # LUX: lux-1.0 present -> not re-added with estimate
        assert pricing["lux-1.0"]["input_cost_per_token"] == 9.9

    @pytest.mark.asyncio
    async def test_fallbacks_added_when_absent(self, fetcher):
        resp = json_response({})
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()
        assert pricing["MiniMax-M3"]["source"] == "estimated"
        assert pricing["lux-1.0"]["input_cost_per_token"] == 0.000003
        assert pricing["lux-1.0"]["output_cost_per_token"] == 0.000015
        assert pricing["lux-1.0"]["litellm_provider"] == "lux"
        assert pricing["glm-5.2"]["source"] == "estimated"
        assert pricing["kimi-k3"]["litellm_provider"] == "moonshot"

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, fetcher):
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", dpf.LITELLM_PRICING_URL),
            response=httpx.Response(500, request=httpx.Request("GET", dpf.LITELLM_PRICING_URL)),
        )
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()
        assert pricing == {}

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self, fetcher):
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        _, cls = make_httpx(client=client)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()
        assert pricing == {}

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_empty(self, fetcher):
        resp = MagicMock()
        resp.json.side_effect = ValueError("bad json")
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()
        assert pricing == {}

    @pytest.mark.asyncio
    async def test_client_enter_failure_returns_empty(self, fetcher):
        _, cls = make_httpx(aenter_error=httpx.ConnectError("down"))
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_litellm_pricing()
        assert pricing == {}


# ===========================================================================
# fetch_openrouter_pricing
# ===========================================================================


class TestFetchOpenRouter:
    @pytest.mark.asyncio
    async def test_success(self, fetcher):
        payload = {"data": [
            {"id": "openai/gpt-4o", "pricing": {"prompt": "0.01", "completion": "0.02"},
             "context_length": 128000, "name": "GPT-4o", "description": "d"},
            {"id": "mistral/m", "pricing": {},
             "context_length": 0},
        ]}
        resp = json_response(payload)
        client, cls = make_httpx(resp)
        applied = []

        def fake_apply(pricing):
            applied.append(pricing)
            return {**pricing, "openai/gpt-4o": {**pricing["openai/gpt-4o"], "x": 1}}

        with patch.object(dpf.httpx, "AsyncClient", cls), \
             patch("core.llm.registry.curated_overrides.apply_curated_overrides_to_pricing",
                   side_effect=fake_apply):
            pricing = await fetcher.fetch_openrouter_pricing()

        entry = pricing["openai/gpt-4o"]
        assert entry["input_cost_per_token"] == 0.01
        assert entry["output_cost_per_token"] == 0.02
        assert entry["max_tokens"] == 128000
        assert entry["name"] == "GPT-4o"
        assert entry["description"] == "d"
        assert entry["litellm_provider"] == "openrouter"
        assert entry["x"] == 1  # curated override applied
        assert pricing["mistral/m"]["litellm_provider"] == "openrouter"
        assert pricing["mistral/m"]["name"] == "mistral/m"
        assert pricing["mistral/m"]["description"] == ""
        assert len(applied) == 1

    @pytest.mark.asyncio
    async def test_empty_data(self, fetcher):
        resp = json_response({"data": []})
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls), \
             patch("core.llm.registry.curated_overrides.apply_curated_overrides_to_pricing",
                   side_effect=lambda p: p):
            pricing = await fetcher.fetch_openrouter_pricing()
        assert pricing == {}

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, fetcher):
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.ConnectTimeout("slow")
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_openrouter_pricing()
        assert pricing == {}


# ===========================================================================
# _opencode_static_fallback / fetch_opencode_pricing
# ===========================================================================


class TestOpencodeFallback:
    def test_static_fallback_shape(self, fetcher):
        table = fetcher._opencode_static_fallback()
        assert table["deepseek-v4-flash"]["input_cost_per_token"] == pytest.approx(0.14 / 1e6)
        assert table["deepseek-v4-flash"]["output_cost_per_token"] == pytest.approx(0.28 / 1e6)
        assert table["deepseek-v4-flash"]["max_input_tokens"] == 200000
        assert table["deepseek-v4-flash"]["litellm_provider"] == "opencode-go"
        assert table["deepseek-v4-flash"]["source"] == "opencode-zen"
        assert table["deepseek-v4-pro"]["input_cost_per_token"] == pytest.approx(1.74 / 1e6)
        assert "qwen3.7-max" in table
        assert len(table) == 11


class TestFetchOpencode:
    @pytest.mark.asyncio
    async def test_bare_list_payload(self, fetcher):
        payload = [
            {"id": "deepseek-v4-flash", "input_cost": 0.14, "output_cost": 0.28,
             "context_length": 200000, "name": "DeepSeek V4 Flash",
             "supports_cache": True},
            {"model": "minimax-m3", "prompt": "0.30", "completion": "1.20",
             "context": 100000},
            {"name": "no-id-model"},  # no id/model -> skipped
        ]
        resp = json_response(payload)
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_opencode_pricing()
        assert pricing["deepseek-v4-flash"]["litellm_provider"] == "opencode-go"
        assert pricing["deepseek-v4-flash"]["input_cost_per_token"] == pytest.approx(0.14 / 1e6)
        assert pricing["deepseek-v4-flash"]["supports_cache"] is True
        assert pricing["minimax-m3"]["input_cost_per_token"] == pytest.approx(0.30 / 1e6)
        assert pricing["minimax-m3"]["max_input_tokens"] == 100000
        assert pricing["minimax-m3"]["name"] == "minimax-m3"
        assert pricing["minimax-m3"]["supports_cache"] is False
        assert "no-id-model" not in pricing

    @pytest.mark.asyncio
    async def test_envelope_payload(self, fetcher):
        payload = {"data": [{"id": "kimi-k2.7-code", "input_cost": 0.95}]}
        resp = json_response(payload)
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_opencode_pricing()
        assert pricing["kimi-k2.7-code"]["input_cost_per_token"] == pytest.approx(0.95 / 1e6)
        assert pricing["kimi-k2.7-code"]["max_input_tokens"] == 200000

    @pytest.mark.asyncio
    async def test_dict_without_data_falls_back(self, fetcher):
        resp = json_response({"foo": "bar"})
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_opencode_pricing()
        assert pricing["deepseek-v4-flash"]["source"] == "opencode-zen"

    @pytest.mark.asyncio
    async def test_empty_list_falls_back(self, fetcher):
        resp = json_response([])
        client, cls = make_httpx(resp)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_opencode_pricing()
        assert "deepseek-v4-flash" in pricing

    @pytest.mark.asyncio
    async def test_network_error_falls_back(self, fetcher):
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        _, cls = make_httpx(client=client)
        with patch.object(dpf.httpx, "AsyncClient", cls):
            pricing = await fetcher.fetch_opencode_pricing()
        assert pricing["kimi-k2.7-code"]["litellm_provider"] == "opencode-go"


# ===========================================================================
# refresh_pricing
# ===========================================================================


class TestRefreshPricing:
    @pytest.mark.asyncio
    async def test_uses_cache_when_valid(self, fetcher):
        fetcher.pricing_cache = {"cached": {"input_cost_per_token": 1.0}}
        fetcher.last_fetch = datetime.now()
        with patch.object(fetcher, "fetch_litellm_pricing", new=AsyncMock()) as m1, \
             patch.object(fetcher, "fetch_openrouter_pricing", new=AsyncMock()) as m2, \
             patch.object(fetcher, "fetch_opencode_pricing", new=AsyncMock()) as m3, \
             patch.object(fetcher, "_save_cache", new=MagicMock()) as save:
            out = await fetcher.refresh_pricing(force=False)
        assert out == {"cached": {"input_cost_per_token": 1.0}}
        m1.assert_not_awaited()
        m2.assert_not_awaited()
        m3.assert_not_awaited()
        save.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_merges_all_sources(self, fetcher):
        fetcher.pricing_cache = {"cached": {"x": 1}}
        fetcher.last_fetch = datetime.now()
        litellm = {"shared": {"src": "litellm"}, "l1": {"src": "litellm"}}
        openrouter = {"shared": {"src": "openrouter"}, "r1": {"src": "openrouter"}}
        opencode = {"shared": {"src": "opencode"}, "o1": {"src": "opencode"}}
        with patch.object(fetcher, "fetch_litellm_pricing", new=AsyncMock(return_value=litellm)), \
             patch.object(fetcher, "fetch_openrouter_pricing", new=AsyncMock(return_value=openrouter)), \
             patch.object(fetcher, "fetch_opencode_pricing", new=AsyncMock(return_value=opencode)), \
             patch.object(fetcher, "_infer_capabilities", return_value={}) as infer, \
             patch.object(fetcher, "_save_cache", new=MagicMock()) as save:
            out = await fetcher.refresh_pricing(force=True)
        # merge precedence: litellm wins over openrouter over opencode
        assert out["shared"]["src"] == "litellm"
        assert out["l1"] == {"src": "litellm"}
        assert out["r1"] == {"src": "openrouter"}
        assert out["o1"] == {"src": "opencode"}
        assert "cached" not in out  # replaced wholesale
        infer.assert_called_once()
        save.assert_called_once()
        assert fetcher.last_fetch is not None

    @pytest.mark.asyncio
    async def test_capabilities_merged_into_cache(self, fetcher):
        with patch.object(fetcher, "fetch_litellm_pricing", new=AsyncMock(return_value={"m1": {}})), \
             patch.object(fetcher, "fetch_openrouter_pricing", new=AsyncMock(return_value={})), \
             patch.object(fetcher, "fetch_opencode_pricing", new=AsyncMock(return_value={})), \
             patch.object(fetcher, "_infer_capabilities",
                          return_value={"m1": {"supports_tools": True, "supports_vision": False,
                                               "supports_reasoning": False}}) as infer, \
             patch.object(fetcher, "_save_cache", new=MagicMock()):
            out = await fetcher.refresh_pricing(force=True)
        assert out["m1"]["supports_tools"] is True
        assert out["m1"]["supports_vision"] is False
        infer.assert_called_once()


# ===========================================================================
# Query helpers
# ===========================================================================


class TestGetModelPrice:
    def test_exact_match(self, fetcher):
        fetcher.pricing_cache = {"gpt-4o": {"input_cost_per_token": 1.0}}
        assert fetcher.get_model_price("gpt-4o") == {"input_cost_per_token": 1.0}

    def test_case_insensitive_match(self, fetcher):
        fetcher.pricing_cache = {"GPT-4O": {"input_cost_per_token": 1.0}}
        assert fetcher.get_model_price("gpt-4o") == {"input_cost_per_token": 1.0}

    def test_unknown_returns_none(self, fetcher):
        fetcher.pricing_cache = {"gpt-4o": {}}
        assert fetcher.get_model_price("claude-x") is None


class TestGetProviderModels:
    def _cache(self):
        return {
            "openai/gpt-4o": {"litellm_provider": "openai", "input_cost_per_token": 0.02},
            "claude-3-5-sonnet": {"litellm_provider": "anthropic", "input_cost_per_token": 0.01},
            "deepseek-chat": {"litellm_provider": "deepseek", "input_cost_per_token": 0.03},
            "no-provider-model": {"input_cost_per_token": 0.05},
        }

    def test_match_by_provider_and_name(self, fetcher):
        fetcher.pricing_cache = self._cache()
        # provider matches litellm_provider and model-name substring
        out = fetcher.get_provider_models("deepseek")
        assert [m["model"] for m in out] == ["deepseek-chat"]
        out = fetcher.get_provider_models("openai")
        assert [m["model"] for m in out] == ["openai/gpt-4o"]

    def test_sorted_by_input_cost(self, fetcher):
        fetcher.pricing_cache = self._cache()
        out = fetcher.get_provider_models("")
        assert [m["model"] for m in out] == [
            "claude-3-5-sonnet", "openai/gpt-4o", "deepseek-chat", "no-provider-model",
        ]

    def test_case_insensitive_provider(self, fetcher):
        fetcher.pricing_cache = self._cache()
        out = fetcher.get_provider_models("ANTHROPIC")
        assert [m["model"] for m in out] == ["claude-3-5-sonnet"]


class TestGetCheapestModels:
    def test_skips_fully_free_and_sorts(self, fetcher):
        fetcher.pricing_cache = {
            "free": {"input_cost_per_token": 0, "output_cost_per_token": 0},
            "mid": {"input_cost_per_token": 0.01, "output_cost_per_token": 0.02},
            "cheap": {"input_cost_per_token": 0.001, "output_cost_per_token": 0.002},
            "output-only": {"input_cost_per_token": 0, "output_cost_per_token": 0.5},
        }
        out = fetcher.get_cheapest_models(limit=10)
        names = [m["model"] for m in out]
        assert "free" not in names  # both costs zero -> skipped
        assert names[0] == "cheap"
        # output-only entry is kept (either cost > 0 keeps the model)
        assert "output-only" in names
        assert out[0]["avg_cost"] == pytest.approx(0.0015)

    def test_limit_applied(self, fetcher):
        fetcher.pricing_cache = {
            f"m{i}": {"input_cost_per_token": i, "output_cost_per_token": i}
            for i in range(1, 6)
        }
        assert len(fetcher.get_cheapest_models(limit=2)) == 2

    def test_empty_cache(self, fetcher):
        assert fetcher.get_cheapest_models() == []


class TestCompareProviders:
    def test_grouped_by_field_provider(self, fetcher):
        fetcher.pricing_cache = {
            "a": {"litellm_provider": "openai", "input_cost_per_token": 0.01,
                  "output_cost_per_token": 0.02},
            "b": {"litellm_provider": "openai", "input_cost_per_token": 0.03,
                  "output_cost_per_token": 0.04},
            "c": {"litellm_provider": "anthropic", "input_cost_per_token": 0.05,
                  "output_cost_per_token": 0.06},
            "zero": {"litellm_provider": "openai", "input_cost_per_token": 0,
                     "output_cost_per_token": 0},
        }
        out = fetcher.compare_providers()
        assert out["openai"]["model_count"] == 2
        assert out["openai"]["avg_cost_per_token"] == pytest.approx((0.015 + 0.035) / 2)
        assert out["openai"]["min_cost_per_token"] == pytest.approx(0.015)
        assert out["openai"]["max_cost_per_token"] == pytest.approx(0.035)
        assert out["anthropic"]["model_count"] == 1
        assert "zero" not in out["openai"]  # zero input cost skipped

    def test_provider_inferred_from_model_name(self, fetcher):
        # Name inference only runs when litellm_provider is explicitly falsy.
        fetcher.pricing_cache = {
            "gpt-4o-x": {"litellm_provider": "", "input_cost_per_token": 0.01,
                         "output_cost_per_token": 0},
            "openai-special": {"litellm_provider": "", "input_cost_per_token": 0.01,
                               "output_cost_per_token": 0},
            "claude-x": {"litellm_provider": "", "input_cost_per_token": 0.01,
                         "output_cost_per_token": 0},
            "anthropic-x": {"litellm_provider": "", "input_cost_per_token": 0.01,
                            "output_cost_per_token": 0},
            "deepseek-chat": {"litellm_provider": "", "input_cost_per_token": 0.01,
                              "output_cost_per_token": 0},
            "gemini-pro": {"litellm_provider": "", "input_cost_per_token": 0.01,
                           "output_cost_per_token": 0},
            "mystery-model": {"litellm_provider": "", "input_cost_per_token": 0.01,
                              "output_cost_per_token": 0},
        }
        out = fetcher.compare_providers()
        assert set(out.keys()) == {"openai", "anthropic", "deepseek", "google", "other"}
        assert out["openai"]["model_count"] == 2
        assert out["other"]["model_count"] == 1

    def test_zero_input_cost_only_models_empty(self, fetcher):
        fetcher.pricing_cache = {
            "x": {"litellm_provider": "openai", "input_cost_per_token": 0,
                  "output_cost_per_token": 0.5},
        }
        assert fetcher.compare_providers() == {}


class TestEstimateCost:
    def test_computes_cost(self, fetcher):
        fetcher.pricing_cache = {
            "gpt-4o": {"input_cost_per_token": 0.01, "output_cost_per_token": 0.02},
        }
        assert fetcher.estimate_cost("gpt-4o", 100, 50) == pytest.approx(1.0 + 1.0)

    def test_unknown_model_returns_none(self, fetcher):
        assert fetcher.estimate_cost("nope", 100, 50) is None


class TestModelSupportsCache:
    def test_explicit_true(self, fetcher):
        fetcher.pricing_cache = {"m": {"supports_cache": True}}
        assert fetcher.model_supports_cache("m") is True

    def test_explicit_false(self, fetcher):
        fetcher.pricing_cache = {"m": {"supports_cache": False}}
        assert fetcher.model_supports_cache("m") is False

    def test_inferred_openai(self, fetcher):
        fetcher.pricing_cache = {"gpt-4o": {"input_cost_per_token": 0.01}}
        assert fetcher.model_supports_cache("gpt-4o") is True

    def test_inferred_anthropic(self, fetcher):
        fetcher.pricing_cache = {"claude-3-5-sonnet": {"input_cost_per_token": 0.01}}
        assert fetcher.model_supports_cache("claude-3-5-sonnet") is True

    def test_inferred_google(self, fetcher):
        fetcher.pricing_cache = {"gemini-pro": {"input_cost_per_token": 0.01}}
        assert fetcher.model_supports_cache("gemini-pro") is True

    def test_inferred_deepseek_false(self, fetcher):
        fetcher.pricing_cache = {"deepseek-chat": {"input_cost_per_token": 0.01}}
        assert fetcher.model_supports_cache("deepseek-chat") is False

    def test_unknown_model_false(self, fetcher):
        assert fetcher.model_supports_cache("totally-unknown") is False


class TestInferProvider:
    @pytest.mark.parametrize("name,expected", [
        ("gpt-4o", "openai"),
        ("openai-o3", "openai"),
        ("claude-3-5-sonnet", "anthropic"),
        ("anthropic-test", "anthropic"),
        ("deepseek-chat", "deepseek"),
        ("gemini-pro", "google"),
        ("google-palm", "google"),
        ("minimax-m3", "minimax"),
        ("glm-4.6", "glm"),
        ("kimi-k2", "moonshot"),
        ("moonshot-v1", "moonshot"),
        ("mistral-7b", "mistral"),
        ("groq-llama", "groq"),
        ("llama-3-70b", "meta"),
        ("lux-1.0", "lux"),
        ("unknown-model-42", "unknown"),
    ])
    def test_inference_branches(self, fetcher, name, expected):
        assert fetcher._infer_provider(name) == expected


class TestInferCapabilities:
    def _model(self, **kw):
        return {"input_cost_per_token": 0.01, **kw}

    def test_full_matrix(self, fetcher):
        data = {
            # tools
            "reasoning-o3": self._model(mode="reasoning"),
            "haiku-fast": {},
            "mini-lite": {},
            "tiny-small": {},
            "speciale-x": {},
            "plain-chat": {},
            # vision
            "vision-model": self._model(mode="vision"),
            "name-vision": {},
            "name-vl": {},
            "name-multimodal": {},
            "gpt-4o-v": {},
            "gemini-2.5-pro": {},
            "gemini-2-flash": {},
            "gemini-3-flash": {},
            "gemini-3.5-flash": {},
            "gemini-1.5-flash": {},
            "gemini-1.5-pro": {},
            "claude-3.5-sonnet-x": {},
            "claude-3-opus-x": {},
            "claude-mythos": {},
            "claude-fable": {},
            "kimi-k3-x": {},
            "gpt-5.6-x": {},
            # reasoning
            "o3-whatever": {},
            "o1-whatever": {},
            "x-reasoner": {},
            "y-thinking": {},
            "z-r1": {},
        }
        caps = fetcher._infer_capabilities(data)

        assert caps["reasoning-o3"] == {"supports_tools": False,
                                        "supports_vision": False,
                                        "supports_reasoning": True}
        assert caps["haiku-fast"]["supports_tools"] is False
        assert caps["mini-lite"]["supports_tools"] is False
        assert caps["tiny-small"]["supports_tools"] is False
        assert caps["speciale-x"] == {"supports_tools": False,
                                      "supports_vision": False,
                                      "supports_reasoning": True}
        assert caps["plain-chat"] == {"supports_tools": True,
                                      "supports_vision": False,
                                      "supports_reasoning": False}
        for vision_name in ["vision-model", "name-vision", "name-vl",
                            "name-multimodal", "gpt-4o-v", "gemini-2.5-pro",
                            "gemini-2-flash", "gemini-3-flash", "gemini-3.5-flash",
                            "gemini-1.5-flash", "gemini-1.5-pro",
                            "claude-3.5-sonnet-x", "claude-3-opus-x",
                            "claude-mythos", "claude-fable", "kimi-k3-x",
                            "gpt-5.6-x"]:
            assert caps[vision_name]["supports_vision"] is True, vision_name
        for reasoning_name in ["o3-whatever", "o1-whatever", "x-reasoner",
                               "y-thinking", "z-r1"]:
            assert caps[reasoning_name]["supports_reasoning"] is True, reasoning_name
        # sanity: plain chat doesn't get vision/reasoning
        assert caps["gpt-4o-v"]["supports_reasoning"] is False
        assert caps["o3-whatever"]["supports_tools"] is True

    def test_empty_input(self, fetcher):
        assert fetcher._infer_capabilities({}) == {}


class TestGetModelCapabilities:
    def test_cached_capabilities(self, fetcher):
        fetcher.pricing_cache = {"m": {"supports_tools": True}}
        out = fetcher.get_model_capabilities("m")
        assert out == {"supports_tools": True, "supports_vision": False,
                       "supports_reasoning": False}

    def test_unknown_model_defaults(self, fetcher):
        out = fetcher.get_model_capabilities("nope")
        assert out == {"supports_tools": False, "supports_vision": False,
                       "supports_reasoning": False}


class TestCacheMinTokens:
    def test_no_cache_support_zero(self, fetcher):
        fetcher.pricing_cache = {"deepseek-chat": {"supports_cache": False}}
        assert fetcher.get_cache_min_tokens("deepseek-chat") == 0

    def test_unknown_model_zero(self, fetcher):
        assert fetcher.get_cache_min_tokens("nope") == 0

    def test_openai_1024(self, fetcher):
        fetcher.pricing_cache = {"gpt-4o": {}}
        assert fetcher.get_cache_min_tokens("gpt-4o") == 1024

    def test_anthropic_2048(self, fetcher):
        fetcher.pricing_cache = {"claude-3-5-sonnet": {}}
        assert fetcher.get_cache_min_tokens("claude-3-5-sonnet") == 2048

    def test_google_1024(self, fetcher):
        fetcher.pricing_cache = {"gemini-pro": {}}
        assert fetcher.get_cache_min_tokens("gemini-pro") == 1024

    def test_other_provider_with_cache_support_zero(self, fetcher):
        fetcher.pricing_cache = {"mistral-x": {"supports_cache": True}}
        assert fetcher.get_cache_min_tokens("mistral-x") == 0


class TestIsPricingEstimated:
    def test_estimated(self, fetcher):
        fetcher.pricing_cache = {"m": {"source": "estimated"}}
        assert fetcher.is_pricing_estimated("m") is True

    def test_official_source(self, fetcher):
        fetcher.pricing_cache = {"m": {"source": "litellm"}}
        assert fetcher.is_pricing_estimated("m") is False

    def test_unknown_model(self, fetcher):
        assert fetcher.is_pricing_estimated("nope") is False


# ===========================================================================
# Module-level helpers
# ===========================================================================


class TestModuleHelpers:
    def test_get_pricing_fetcher_singleton(self, fetcher):
        a = dpf.get_pricing_fetcher()
        b = dpf.get_pricing_fetcher()
        assert a is b
        assert isinstance(a, dpf.DynamicPricingFetcher)

    @pytest.mark.asyncio
    async def test_initialized_refreshes_when_empty(self, fetcher):
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            out = await dpf.get_pricing_fetcher_initialized()
        refresh.assert_awaited_once_with(force=False)
        assert out is fetcher
        assert dpf._pricing_initialized is True

    @pytest.mark.asyncio
    async def test_initialized_force_refresh(self, fetcher):
        fetcher.pricing_cache = {"m": {}}
        dpf._pricing_initialized = True
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            await dpf.get_pricing_fetcher_initialized(force_refresh=True)
        refresh.assert_awaited_once_with(force=True)

    @pytest.mark.asyncio
    async def test_initialized_auto_refresh_on_empty_cache(self, fetcher):
        fetcher.pricing_cache = {}
        dpf._pricing_initialized = True
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            await dpf.get_pricing_fetcher_initialized(auto_refresh=True)
        refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialized_skips_when_ready(self, fetcher):
        fetcher.pricing_cache = {"m": {}}
        dpf._pricing_initialized = True
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            out = await dpf.get_pricing_fetcher_initialized()
        refresh.assert_not_awaited()
        assert out is fetcher

    def test_initialized_sync_no_running_loop(self, fetcher):
        """RuntimeError from get_running_loop -> asyncio.run path."""
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            out = dpf.get_pricing_fetcher_initialized_sync()
        refresh.assert_awaited_once_with(force=False)
        assert out is fetcher
        assert dpf._pricing_initialized is True

    def test_initialized_sync_skips_when_ready(self, fetcher):
        fetcher.pricing_cache = {"m": {}}
        dpf._pricing_initialized = True
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            dpf.get_pricing_fetcher_initialized_sync()
        refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_initialized_sync_with_running_loop(self, fetcher):
        """Running-loop path (lines 740-741): refresh via thread executor."""
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock()) as refresh:
            out = dpf.get_pricing_fetcher_initialized_sync()
        refresh.assert_awaited_once()
        assert out is fetcher

    @pytest.mark.asyncio
    async def test_refresh_pricing_cache_helper(self, fetcher):
        with patch.object(dpf, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(fetcher, "refresh_pricing", new=AsyncMock(return_value={"m": 1})) as refresh:
            out = await dpf.refresh_pricing_cache(force=True)
        assert out == {"m": 1}
        refresh.assert_awaited_once_with(force=True)

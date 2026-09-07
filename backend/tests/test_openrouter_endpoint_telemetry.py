"""
OpenRouter endpoint telemetry + benchmark enrichment tests (Phase 5').

Covers:
1. core.llm.openrouter_endpoints.OpenRouterEndpointMonitor — slug parsing,
   best-endpoint selection, TTL, fail-open on transport errors, kill switch.
2. BPC wiring in byok_handler.get_ranked_providers — measured uptime gates
   candidates, measured p50 latency penalizes value score, non-openrouter
   providers unaffected, flag off restores exact prior behavior.
3. DynamicBenchmarkFetcher.fetch_from_openrouter — Artificial Analysis
   indices from the /api/v1/models payload feed quality floors as a
   supplement (never overrides an existing score).
"""

import os
os.environ["TESTING"] = "1"

import time

import httpx
import pytest
from unittest.mock import AsyncMock, Mock, patch

from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.dynamic_pricing_fetcher import DynamicPricingFetcher


# ============================================================================
# Helpers / fixtures
# ============================================================================

def _endpoint_payload(endpoints):
    return {"data": {"id": "x", "endpoints": endpoints}}


def _ep(provider="Anthropic", status=0, uptime="99.90", p50=800):
    return {
        "provider": provider,
        "status": status,
        "uptime_30m": uptime,
        "latency_30m_ms": {"p50": p50, "p75": 1200, "p99": 5000},
        "throughput_30m_tokens_per_sec": {"p50": 45},
    }


@pytest.fixture
def fresh_monitor():
    from core.llm.openrouter_endpoints import OpenRouterEndpointMonitor
    return OpenRouterEndpointMonitor(ttl_seconds=600)


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setenv("ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED", "true")
    monkeypatch.delenv("ATOM_OPENROUTER_MIN_UPTIME_30M", raising=False)
    monkeypatch.delenv("ATOM_OPENROUTER_MAX_LATENCY_P50_MS", raising=False)


@pytest.fixture
def mock_byok_manager():
    manager = Mock()
    manager.is_configured.return_value = False
    manager.get_api_key.return_value = None
    return manager


@pytest.fixture
def byok_handler(mock_byok_manager):
    with patch("core.llm.byok_handler.get_byok_manager", return_value=mock_byok_manager), \
         patch("core.llm.byok_handler.get_db_session", return_value=Mock()):
        return BYOKHandler()


def _seed_monitor(monkeypatch, healths):
    """Replace the process-global monitor with one pre-seeded with healths."""
    import core.llm.openrouter_endpoints as ore
    monitor = ore.OpenRouterEndpointMonitor(ttl_seconds=600)
    for slug, health in healths.items():
        monitor._cache[slug] = health
        monitor._fetched_at[slug] = time.time()
    monkeypatch.setattr(ore, "_monitor", monitor)
    return monitor


# ============================================================================
# 1. Monitor unit behavior
# ============================================================================

class TestSlugParsing:
    def test_strips_variant_suffix(self):
        from core.llm.openrouter_endpoints import slug_from_model_id
        assert slug_from_model_id("anthropic/claude-opus-5:batch") == "anthropic/claude-opus-5"

    def test_plain_model_id_passthrough(self):
        from core.llm.openrouter_endpoints import slug_from_model_id
        assert slug_from_model_id("anthropic/claude-opus-5") == "anthropic/claude-opus-5"

    def test_no_author_rejected(self):
        from core.llm.openrouter_endpoints import slug_from_model_id
        assert slug_from_model_id("deepseek-v4-flash") is None


class TestEndpointSelection:
    @pytest.mark.asyncio
    async def test_prefers_operational_lowest_latency(self, fresh_monitor):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, json=_endpoint_payload([
                _ep(provider="Slow", status=0, uptime=99.0, p50=9000),
                _ep(provider="Fast", status=0, uptime=99.9, p50=300),
                _ep(provider="Degraded", status=2, uptime=100.0, p50=10),
            ]))

        fresh_monitor._transport_for_test = None
        fresh_monitor._make_client = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler))
        await fresh_monitor.refresh(["anthropic/claude-opus-5"], force=True)
        h = fresh_monitor.get_health("anthropic/claude-opus-5:batch")
        assert h is not None
        assert h.provider_name == "Fast"
        assert h.latency_ms_p50 == 300
        assert h.uptime_30m == pytest.approx(99.9)
        assert "/anthropic/claude-opus-5/endpoints" in calls[0]

    @pytest.mark.asyncio
    async def test_transport_error_failopen(self, fresh_monitor):
        def handler(request):
            raise httpx.ConnectError("boom")

        fresh_monitor._make_client = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler))
        await fresh_monitor.refresh(["anthropic/claude-opus-5"], force=True)
        assert fresh_monitor.get_health("anthropic/claude-opus-5") is None

    @pytest.mark.asyncio
    async def test_ttl_prevents_refetch(self, fresh_monitor):
        count = {"n": 0}

        def handler(request):
            count["n"] += 1
            return httpx.Response(200, json=_endpoint_payload([_ep()]))

        fresh_monitor._make_client = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler))
        await fresh_monitor.refresh(["anthropic/a"], force=True)
        await fresh_monitor.refresh(["anthropic/a", "openrouter/b"])
        # Second pass: fresh 'a' skipped, only stale 'b' fetched.
        assert count["n"] == 2
        # Third pass: nothing stale — zero additional fetches.
        await fresh_monitor.refresh(["anthropic/a", "openrouter/b"])
        assert count["n"] == 2

    @pytest.mark.asyncio
    async def test_empty_endpoints_yields_none(self, fresh_monitor):
        fresh_monitor._make_client = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=_endpoint_payload([]))))
        await fresh_monitor.refresh(["anthropic/a"], force=True)
        assert fresh_monitor.get_health("anthropic/a") is None


class TestKillSwitch:
    def test_telemetry_disabled(self, monkeypatch):
        from core.llm.openrouter_endpoints import telemetry_enabled
        monkeypatch.setenv("ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED", "false")
        assert telemetry_enabled() is False
        monkeypatch.setenv("ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED", "true")
        assert telemetry_enabled() is True


# ============================================================================
# 2. BPC wiring
# ============================================================================

def _fetcher_with_openrouter_models(extra=None):
    fetcher = DynamicPricingFetcher()

    def m(mid, cost):
        return {
            "litellm_provider": "openrouter",
            "input_cost_per_token": cost / 1e6,
            "output_cost_per_token": cost * 3 / 1e6,
            "max_input_tokens": 200000,
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": False,
        }

    fetcher.pricing_cache = {
        "alpha/model-good": m("good", 1.0),
        "beta/model-bad": m("bad", 1.0),
    }
    if extra:
        fetcher.pricing_cache.update(extra)
    return fetcher


def _vet_fake_models(monkeypatch):
    """Vet the fake IDs into MODEL_QUALITY_SCORES at 90.

    The openrouter candidate gate (exact table membership) and the SIMPLE
    recall floor (85, Aug 30) postdate these tests: unvetted fake IDs fell
    out of ranking entirely and every gating test degraded to the fail-open
    minimax fallback. 90 clears the floor so the telemetry behavior under
    test is what decides the outcome. Reverted automatically per-test.
    """
    from core.benchmarks import MODEL_QUALITY_SCORES as _MQS
    monkeypatch.setitem(_MQS, "alpha/model-good", 90)
    monkeypatch.setitem(_MQS, "beta/model-bad", 90)


class TestBpcEndpointGating:
    def test_uptime_below_floor_excludes_candidate(self, byok_handler, clean_env, monkeypatch):
        from core.llm.openrouter_endpoints import EndpointHealth
        _vet_fake_models(monkeypatch)
        _seed_monitor(monkeypatch, {
            "alpha/model-good": EndpointHealth("alpha/model-good", "A", 99.9, 500, 45, 0),
            "beta/model-bad": EndpointHealth("beta/model-bad", "B", 40.0, 500, 45, 0),
        })
        byok_handler.clients = {"openrouter": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=_fetcher_with_openrouter_models()):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        models = [m for _, m in ranked]
        assert "alpha/model-good" in models
        assert "beta/model-bad" not in models

    def test_latency_degraded_ranks_lower(self, byok_handler, clean_env, monkeypatch):
        from core.llm.openrouter_endpoints import EndpointHealth
        _vet_fake_models(monkeypatch)
        _seed_monitor(monkeypatch, {
            "alpha/model-good": EndpointHealth("alpha/model-good", "A", 99.9, 400, 45, 0),
            "beta/model-bad": EndpointHealth("beta/model-bad", "B", 99.9, 90000, 45, 0),
        })
        byok_handler.clients = {"openrouter": Mock()}
        # Identical quality/cost — only the measured-latency penalty differs.
        # Score 90 clears the SIMPLE recall floor (85).
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=_fetcher_with_openrouter_models()), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        assert [m for _, m in ranked][0] == "alpha/model-good"

    def test_flag_off_restores_prior_behavior(self, byok_handler, monkeypatch):
        from core.llm.openrouter_endpoints import EndpointHealth
        monkeypatch.setenv("ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED", "false")
        _vet_fake_models(monkeypatch)
        _seed_monitor(monkeypatch, {
            "beta/model-bad": EndpointHealth("beta/model-bad", "B", 1.0, 999999, 1, 2),
        })
        byok_handler.clients = {"openrouter": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=_fetcher_with_openrouter_models()):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        assert ("openrouter", "beta/model-bad") in ranked

    def test_non_openrouter_provider_unaffected(self, byok_handler, clean_env, monkeypatch):
        from core.llm.openrouter_endpoints import EndpointHealth
        _seed_monitor(monkeypatch, {
            "deepseek-chat": EndpointHealth("deepseek-chat", "D", 1.0, 999999, 1, 2),
        })
        byok_handler.clients = {"deepseek": Mock(), "openrouter": Mock()}
        fetcher = _fetcher_with_openrouter_models()
        fetcher.pricing_cache["deepseek-chat"] = {
            "litellm_provider": "deepseek",
            "input_cost_per_token": 0.27 / 1e6,
            "output_cost_per_token": 1.10 / 1e6,
            "max_input_tokens": 65536,
            "supports_tools": True,
        }
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        assert ("deepseek", "deepseek-chat") in ranked

    def test_unknown_health_is_pass_through(self, byok_handler, clean_env, monkeypatch):
        _vet_fake_models(monkeypatch)
        _seed_monitor(monkeypatch, {})
        byok_handler.clients = {"openrouter": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=_fetcher_with_openrouter_models()):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        assert len(ranked) == 2


# ============================================================================
# 3. Benchmark enrichment
# ============================================================================

def _benchmark_fetcher(tmp_path):
    with patch("core.dynamic_benchmark_fetcher.BENCHMARK_CACHE_PATH",
               tmp_path / "bench.json"), \
         patch("core.dynamic_benchmark_fetcher.LMSYSClient"), \
         patch("core.dynamic_benchmark_fetcher.UniversalCacheService"):
        from core.dynamic_benchmark_fetcher import DynamicBenchmarkFetcher
        return DynamicBenchmarkFetcher(cache_service=Mock())


class TestOpenRouterBenchmarkSource:
    @pytest.mark.asyncio
    async def test_parses_artificial_analysis_indices(self, tmp_path):
        fetcher = _benchmark_fetcher(tmp_path)
        payload = {"data": [
            {"id": "anthropic/claude-opus-5",
             "benchmarks": {"artificial_analysis": {
                 "intelligence_index": 63.1, "coding_index": 78}}},
            {"id": "z-ai/glm-5.3",
             "benchmarks": {"artificial_analysis": {"intelligence_index": 150}}},
            {"id": "no/benchmarks"},
            {"id": "bad/value", "benchmarks": {"artificial_analysis":
             {"intelligence_index": "not-a-number"}}},
        ]}

        def handler(request):
            return httpx.Response(200, json=payload)

        fetcher._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        scores = await fetcher.fetch_from_openrouter()
        assert scores["anthropic/claude-opus-5"] == pytest.approx(63.1)
        assert scores["z-ai/glm-5.3"] == 100  # clamped
        assert "no/benchmarks" not in scores
        assert "bad/value" not in scores

    @pytest.mark.asyncio
    async def test_refresh_merges_as_supplement(self, tmp_path, monkeypatch):
        fetcher = _benchmark_fetcher(tmp_path)
        lmsys_scores = {f"arena-model-{i}": 80.0 + i for i in range(20)}
        lmsys_scores["shared-model"] = 99.0

        async def fake_lmsys():
            return lmsys_scores

        async def fake_or():
            return {"shared-model": 51.0, "anthropic/claude-opus-5": 63.1}

        monkeypatch.setattr(fetcher, "fetch_from_lmsys", fake_lmsys)
        monkeypatch.setattr(fetcher, "fetch_from_openrouter", fake_or)
        monkeypatch.setattr(fetcher, "_save_cache", lambda: None)

        result = await fetcher.refresh_benchmarks(force=True)
        assert result["shared-model"] == 99.0  # existing source wins
        assert result["anthropic/claude-opus-5"] == pytest.approx(63.1)  # added
        assert len(result) > 20

    @pytest.mark.asyncio
    async def test_source_failure_never_breaks_refresh(self, tmp_path, monkeypatch):
        fetcher = _benchmark_fetcher(tmp_path)

        async def fake_lmsys():
            return {f"m-{i}": 85.0 for i in range(15)}

        async def boom():
            raise RuntimeError("network down")

        monkeypatch.setattr(fetcher, "fetch_from_lmsys", fake_lmsys)
        monkeypatch.setattr(fetcher, "fetch_from_openrouter", boom)
        monkeypatch.setattr(fetcher, "_save_cache", lambda: None)

        result = await fetcher.refresh_benchmarks(force=True)
        assert len(result) == 15

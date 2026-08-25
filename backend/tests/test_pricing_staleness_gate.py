"""
Phase M measurement gate: pricing-cache staleness instrumentation.

Decides — with numbers, not vibes — whether the server-side query-param
candidate path (plan v2 Phases 1–4) should ever be built:

- What gets measured:
  1. Per-refresh diff of the openrouter slice of the pricing cache
     (models added / removed / serving-past-expiration at refresh time).
  2. BPC-side counter of candidates considered whose OpenRouter payload
     marks them expired (measurement ONLY — routing unchanged by design,
     since expiration_date means "may be removed", not "is removed").
  3. Authed route GET /api/ai/pricing/staleness-stats exposing both.

Decision rule (documented in TESTED_FILES_TRACKER): if stale-serving or
availability-lag numbers are boring over a review window, Phases 1–3 stay
dead and TTL tuning remains the whole story.
"""

import os
os.environ["TESTING"] = "1"

from datetime import datetime, timedelta

import pytest
from unittest.mock import Mock, patch


# ============================================================================
# 1. Transform carries freshness fields + expiry parsing
# ============================================================================

class TestFreshnessFields:
    @pytest.mark.asyncio
    async def test_openrouter_transform_carries_expiration_and_created(self):
        import httpx

        from core.dynamic_pricing_fetcher import DynamicPricingFetcher
        fetcher = DynamicPricingFetcher()
        payload = {"data": [{
            "id": "anthropic/claude-opus-5",
            "name": "Claude",
            "context_length": 200000,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "expiration_date": "2026-12-01",
            "created": 1755000000,
        }]}

        def handler(request):
            return httpx.Response(200, json=payload)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch("core.dynamic_pricing_fetcher.httpx.AsyncClient", return_value=client):
            result = await fetcher.fetch_openrouter_pricing()
        await client.aclose()

        entry = result["anthropic/claude-opus-5"]
        assert entry["expiration_date"] == "2026-12-01"
        assert entry["created"] == 1755000000
        assert entry["source"] == "openrouter"

    def test_is_expiration_past_matrix(self):
        from core.dynamic_pricing_fetcher import is_expiration_past
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        assert is_expiration_past(past) is True
        assert is_expiration_past(future) is False
        assert is_expiration_past(None) is False
        assert is_expiration_past("") is False
        assert is_expiration_past("not-a-date") is False


# ============================================================================
# 2. Refresh-time diff stats
# ============================================================================

class TestStalenessStats:
    def _or(self, mid, exp=None):
        return {"source": "openrouter", "litellm_provider": "openrouter",
                "input_cost_per_token": 1e-6, "output_cost_per_token": 3e-6,
                "max_tokens": 100000, "expiration_date": exp}

    def test_diff_math(self):
        from core.dynamic_pricing_fetcher import compute_staleness_stats
        past = "2026-01-01"
        prev = {"a/m1": self._or("a/m1"), "a/gone": self._or("a/gone"),
                "x/litellm-only": {"source": "litellm"}}
        curr = {"a/m1": self._or("a/m1", exp=past),      # still cached, expired
                "a/new": self._or("a/new"),               # added
                "x/new-litellm": {"source": "litellm"}}   # ignored (not openrouter)
        stats = compute_staleness_stats(prev, curr)
        assert set(stats["added"]) == {"a/new"}
        assert set(stats["removed"]) == {"a/gone"}
        assert set(stats["expired_served"]) == {"a/m1"}
        assert stats["openrouter_count"] == 2
        assert stats["generated_at"]

    def test_bad_dates_tolerated(self):
        from core.dynamic_pricing_fetcher import compute_staleness_stats
        curr = {"a/bad": self._or("a/bad", exp="garbage")}
        stats = compute_staleness_stats({}, curr)
        assert stats["expired_served"] == []

    def test_first_refresh_no_previous(self):
        from core.dynamic_pricing_fetcher import compute_staleness_stats
        stats = compute_staleness_stats({}, {"a/1": self._or("a/1")})
        assert stats["added"] == ["a/1"]
        assert stats["removed"] == []

    def test_refresh_persists_history(self, tmp_path, monkeypatch):
        import core.dynamic_pricing_fetcher as dpf
        cache_path = tmp_path / "cache.json"
        stats_path = tmp_path / "staleness.json"
        monkeypatch.setattr(dpf, "PRICING_CACHE_PATH", cache_path)
        monkeypatch.setattr(dpf, "STALENESS_STATS_PATH", stats_path)

        fetcher = dpf.DynamicPricingFetcher()
        monkeypatch.setattr(dpf.DynamicPricingFetcher, "_load_cache", lambda self: None)
        fetcher.pricing_cache = {}
        fetcher.last_fetch = None
        fetcher.staleness_history = []

        async def fake_litellm():
            return {}

        async def fake_or():
            return {"a/m1": fetcher._or_entry("a/m1")}

        async def fake_oc():
            return {}

        monkeypatch.setattr(fetcher, "fetch_litellm_pricing", fake_litellm)
        monkeypatch.setattr(fetcher, "fetch_openrouter_pricing", fake_or)
        monkeypatch.setattr(fetcher, "fetch_opencode_pricing", fake_oc)

        import asyncio
        asyncio.run(fetcher.refresh_pricing(force=True))
        first = list(fetcher.staleness_history)
        assert len(first) == 1 and first[0]["added"] == ["a/m1"]

        # Second refresh with one model gone → removed recorded.
        async def fake_or2():
            return {}
        monkeypatch.setattr(fetcher, "fetch_openrouter_pricing", fake_or2)
        asyncio.run(fetcher.refresh_pricing(force=True))
        assert len(fetcher.staleness_history) == 2
        assert fetcher.staleness_history[-1]["removed"] == ["a/m1"]
        assert stats_path.exists()

    def test_summary_shape(self):
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher
        f = DynamicPricingFetcher()
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        f.pricing_cache = {"a/x": {"source": "openrouter", "expiration_date": past}}
        f.staleness_history = [{"generated_at": "t", "added": [], "removed": [],
                                "expired_served": ["a/x"], "openrouter_count": 5}]
        f.bpc_stale_seen = {"a/x": 3}
        summary = f.staleness_summary()
        assert summary["refresh_samples"] == 1
        assert summary["expired_models_currently_cached"] == ["a/x"]
        assert summary["bpc_stale_considerations"] == {"a/x": 3}


# ============================================================================
# 3. BPC measures without changing behavior
# ============================================================================

class TestBpcStaleMeasurement:
    def _fetcher(self):
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher
        fetcher = DynamicPricingFetcher()
        past = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        fetcher.pricing_cache = {
            "alpha/expired-model": {
                "litellm_provider": "openrouter",
                "input_cost_per_token": 1e-6, "output_cost_per_token": 3e-6,
                "max_input_tokens": 200000, "supports_tools": True,
                "expiration_date": past,
            },
        }
        return fetcher

    def test_expired_model_still_ranked_but_counted(self, mock_handler_factory):
        handler, fetcher = mock_handler_factory(self._fetcher())
        from core.llm.byok_handler import QueryComplexity
        ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE, is_managed_service=False)
        # Behavior pin: expiration_date means "may be removed" — routing unchanged.
        assert ("openrouter", "alpha/expired-model") in ranked
        assert fetcher.bpc_stale_seen.get("alpha/expired-model") == 1

    def test_unexpired_not_counted(self, mock_handler_factory):
        fetcher = self._fetcher()
        future = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        fetcher.pricing_cache["alpha/expired-model"]["expiration_date"] = future
        handler, _ = mock_handler_factory(fetcher)
        from core.llm.byok_handler import QueryComplexity
        handler.get_ranked_providers(QueryComplexity.SIMPLE, is_managed_service=False)
        assert fetcher.bpc_stale_seen == {}


# ============================================================================
# 4. Route surface
# ============================================================================

class TestStalenessRoute:
    def test_route_returns_summary(self):
        from types import SimpleNamespace

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.byok_routes import router
        from core.auth import get_current_user as auth_dep
        from core.database import get_db

        app = FastAPI()
        app.include_router(router)

        user = Mock(id="u1")
        user.tenant_id = "t-1"
        app.dependency_overrides[auth_dep] = lambda: user
        app.dependency_overrides[get_db] = lambda: Mock()

        summary = {"refresh_samples": 2, "expired_models_currently_cached": [],
                   "bpc_stale_considerations": {}, "latest": None}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher") as gp:
            gp.return_value.staleness_summary.return_value = summary
            resp = TestClient(app).get("/api/ai/pricing/staleness-stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["refresh_samples"] == 2


# ============================================================================
# Shared fixtures
# ============================================================================

@pytest.fixture
def mock_handler_factory(request):
    """BYOKHandler with stubbed clients/pricing-fetcher (opencode-suite pattern)."""
    from core.llm.byok_handler import BYOKHandler

    finalizers = []
    request.addfinalizer(lambda: [f() for f in finalizers])

    def _make(pricing_fetcher):
        manager = Mock()
        manager.is_configured.return_value = False
        manager.get_api_key.return_value = None
        with patch("core.llm.byok_handler.get_byok_manager", return_value=manager), \
             patch("core.llm.byok_handler.get_db_session", return_value=Mock()):
            handler = BYOKHandler()
        handler.clients = {"openrouter": Mock()}
        patcher = patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                        return_value=pricing_fetcher)
        patcher.start()
        finalizers.append(patcher.stop)
        return handler, pricing_fetcher

    return _make

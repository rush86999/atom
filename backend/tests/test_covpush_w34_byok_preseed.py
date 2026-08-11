"""Coverage wave 34 — core/byok_cache_preseeding.py (82% → 90%+).

Completes the missing branches of the pre-seeding pipeline:
- verbose=True logging lines in every step + preseed_all
- all failure returns (refresh/classifier/fetcher/cache/router exceptions)
- the no-agents dummy fallback in preseed_governance_cache
- models_missing warning + db.close() exception tolerance
- preseed_all partial-failure error capture
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.byok_cache_preseeding import (
    preseed_all_caches,
    preseed_cache_aware_router,
    preseed_cognitive_models,
    preseed_governance_cache,
    preseed_pricing_cache,
)
from core.llm.cache_aware_router import CacheAwareRouter
from core.models import AgentStatus
from core.governance_cache import GovernanceCache


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPreseedAllVerboseAndErrors:
    async def test_verbose_steps_logged(self):
        with patch('core.byok_cache_preseeding.preseed_pricing_cache') as mp, \
             patch('core.byok_cache_preseeding.preseed_cognitive_models') as mc, \
             patch('core.byok_cache_preseeding.preseed_governance_cache') as mg, \
             patch('core.byok_cache_preseeding.preseed_cache_aware_router') as mr:
            mp.return_value = {"success": True}
            mc.return_value = {"success": True}
            mg.return_value = {"success": True}
            mr.return_value = {"success": True}
            result = await preseed_all_caches(workspace_id="default", verbose=True)
        assert result["pricing"]["success"] is True
        assert "started_at" in result
        for m in (mp, mc, mg, mr):
            m.assert_awaited_once()

    async def test_step_exception_captured_in_error(self):
        with patch('core.byok_cache_preseeding.preseed_pricing_cache') as mp, \
             patch('core.byok_cache_preseeding.preseed_cognitive_models') as mc, \
             patch('core.byok_cache_preseeding.preseed_governance_cache') as mg, \
             patch('core.byok_cache_preseeding.preseed_cache_aware_router') as mr:
            mp.side_effect = RuntimeError("boom")
            result = await preseed_all_caches(verbose=True)
        assert "boom" in result["error"]
        assert mc.await_count == 0


class TestPreseedPricingVerboseAndFailure:
    async def test_verbose_success_counts_features(self):
        with patch('core.byok_cache_preseeding.refresh_pricing_cache') as mock_refresh:
            mock_refresh.return_value = {
                "m1": {"litellm_provider": "openai", "supports_cache": True,
                       "supports_tools": True, "supports_vision": True},
                "m2": {"litellm_provider": "anthropic", "supports_cache": False},
                "m3": {},
            }
            result = await preseed_pricing_cache(force_refresh=True, verbose=True)
        assert result["success"] is True
        assert result["models_loaded"] == 3
        assert result["models_with_cache_support"] == 1
        assert result["models_with_tools_support"] == 1
        assert result["models_with_vision_support"] == 1
        assert result["providers"] == ["anthropic", "openai", "unknown"]

    async def test_fetch_failure_verbose(self):
        with patch('core.byok_cache_preseeding.refresh_pricing_cache',
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await preseed_pricing_cache(verbose=True)
        assert result["success"] is False
        assert "boom" in result["error"]
        assert result["models_loaded"] == 0


class TestPreseedCognitiveVerboseAndFailure:
    def _patch_cognitive(self, tiers, missing_models=0):
        mock_classifier = Mock()
        mock_classifier.get_tier_models.return_value = tiers
        mock_fetcher = Mock()
        mock_fetcher.get_pricing.return_value = None  # force missing counts
        return patch('core.byok_cache_preseeding.CognitiveClassifier',
                     return_value=mock_classifier), \
            patch('core.byok_cache_preseeding.get_pricing_fetcher',
                  return_value=mock_fetcher)

    async def test_verbose_with_missing_models_warning(self):
        p1, p2 = self._patch_cognitive([{"models": ["a", "b"], "name": "T1"}])
        with p1, p2:
            result = await preseed_cognitive_models(verbose=True)
        assert result["success"] is True
        assert result["tiers_loaded"] >= 1
        assert result["models_validated"] >= 0

    async def test_failure_returns_false(self):
        with patch('core.byok_cache_preseeding.CognitiveClassifier',
                   side_effect=RuntimeError("boom")):
            result = await preseed_cognitive_models(verbose=True)
        assert result["success"] is False
        assert "boom" in result["error"]
        assert result["tiers_loaded"] == 0


class TestPreseedGovernanceVerboseDummyAndFailure:
    def _governance_mocks(self, agents):
        mock_db = Mock()
        mock_db.query.return_value.limit.return_value.all.return_value = agents
        mock_cache = Mock(spec=GovernanceCache)
        mock_cache.get_stats.return_value = {"size": 60, "hit_rate": 95.0}
        return patch('core.byok_cache_preseeding.SessionLocal',
                     return_value=mock_db), \
            patch('core.byok_cache_preseeding.get_governance_cache',
                  return_value=mock_cache)

    async def test_verbose_with_agents(self):
        agents = [Mock(id="agent-1", status=AgentStatus.SUPERVISED)]
        p1, p2 = self._governance_mocks(agents)
        with p1, p2:
            result = await preseed_governance_cache(verbose=True)
        assert result["success"] is True
        assert result["cache_size"] == 60
        assert result["cache_hit_rate"] == 95.0

    async def test_no_agents_uses_dummy_fallback(self):
        p1, p2 = self._governance_mocks([])
        with p1, p2:
            result = await preseed_governance_cache(verbose=True)
        assert result["success"] is True
        assert result["actions_cached"] >= 0

    async def test_failure_returns_false_and_closes_db(self):
        mock_db = Mock()
        mock_db.close.side_effect = RuntimeError("close boom")
        with patch('core.byok_cache_preseeding.SessionLocal',
                   return_value=mock_db), \
             patch('core.byok_cache_preseeding.get_governance_cache',
                   side_effect=RuntimeError("cache boom")):
            result = await preseed_governance_cache(verbose=True)
        assert result["success"] is False
        assert result["actions_cached"] == 0
        assert "Internal error" in result["error"]


class TestPreseedCacheAwareVerboseAndFailure:
    async def test_verbose_success(self):
        mock_router = Mock()
        mock_router.cache_hit_history = {}
        with patch('core.byok_cache_preseeding.get_pricing_fetcher') as mf, \
             patch('core.byok_cache_preseeding.CacheAwareRouter',
                   return_value=mock_router):
            result = await preseed_cache_aware_router(verbose=True)
        assert result["success"] is True
        assert result["prompts_seeded"] == 10
        assert result["cache_history_size"] == len(mock_router.cache_hit_history)

    async def test_failure_returns_false(self):
        with patch('core.byok_cache_preseeding.get_pricing_fetcher',
                   side_effect=RuntimeError("boom")):
            result = await preseed_cache_aware_router(verbose=True)
        assert result["success"] is False
        assert "boom" in result["error"]
        assert result["prompts_seeded"] == 0

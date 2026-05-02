"""
Unit Tests for BYOK Cache Pre-seeding Service

Tests cache pre-seeding functionality using TDD patterns:
- Pre-seed all caches
- Pre-seed pricing cache
- Pre-seed cognitive models
- Pre-seed governance cache
- Pre-seed cache-aware router
- Startup hook behavior

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+

TDD Pattern:
- RED: Write failing test first
- GREEN: Implement minimal code to pass
- REFACTOR: Improve while tests pass
"""

import pytest
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from core.byok_cache_preseeding import (
    preseed_all_caches,
    preseed_pricing_cache,
    preseed_cognitive_models,
    preseed_governance_cache,
    preseed_cache_aware_router,
    maybe_preseed_on_startup,
    print_preseed_results,
)
from core.dynamic_pricing_fetcher import DynamicPricingFetcher
from core.governance_cache import GovernanceCache
from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.cognitive_tier_system import CognitiveTier
from core.models import AgentRegistry, AgentStatus, User, UserRole
from core.database import SessionLocal


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with cache routes."""
    app = FastAPI()
    from api.admin.cache_routes import router
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_agent(db):
    """Create sample agent for governance pre-seeding."""
    agent = AgentRegistry(
        id="test-agent-123",
        name="Test Agent",
        description="Test agent for cache pre-seeding",
        category="testing",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.75,
        module_path="agents.test",
        class_name="TestAgent",
        configuration={},
        workspace_id="default",
        user_id="test-user-123"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_pricing_fetcher():
    """Mock pricing fetcher with sample data."""
    fetcher = Mock(spec=DynamicPricingFetcher)
    fetcher.pricing_cache = {
        "gpt-4o": {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_tokens": 128000,
            "litellm_provider": "openai",
            "supports_cache": True,
        },
        "claude-3-5-sonnet": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "max_tokens": 200000,
            "litellm_provider": "anthropic",
            "supports_cache": True,
        },
        "deepseek-chat": {
            "input_cost_per_token": 0.0000001,
            "output_cost_per_token": 0.0000001,
            "max_tokens": 128000,
            "litellm_provider": "deepseek",
            "supports_cache": False,
        },
    }
    fetcher.last_fetch = datetime.now()
    return fetcher


# =============================================================================
# Test Class: Preseed All Caches
# =============================================================================

class TestPreseedAllCaches:
    """Tests for preseed_all_caches function."""

    @pytest.mark.asyncio
    async def test_preseeds_all_cache_types(self, db, sample_agent):
        """RED: Test that all cache types are pre-seeded."""
        with patch('core.byok_cache_preseeding.preseed_pricing_cache') as mock_pricing, \
             patch('core.byok_cache_preseeding.preseed_cognitive_models') as mock_cognitive, \
             patch('core.byok_cache_preseeding.preseed_governance_cache') as mock_governance, \
             patch('core.byok_cache_preseeding.preseed_cache_aware_router') as mock_router:

            # Setup mocks
            mock_pricing.return_value = {"success": True, "models_loaded": 1523}
            mock_cognitive.return_value = {"success": True, "tiers_loaded": 5}
            mock_governance.return_value = {"success": True, "actions_cached": 60}
            mock_router.return_value = {"success": True, "prompts_seeded": 10}

            result = await preseed_all_caches(workspace_id="default", verbose=False)

            assert result["pricing"]["success"] is True
            assert result["cognitive"]["success"] is True
            assert result["governance"]["success"] is True
            assert result["cache_aware"]["success"] is True

    @pytest.mark.asyncio
    async def test_tracks_duration(self, db):
        """RED: Test that duration is tracked."""
        with patch('core.byok_cache_preseeding.preseed_pricing_cache') as mock_pricing, \
             patch('core.byok_cache_preseeding.preseed_cognitive_models') as mock_cognitive, \
             patch('core.byok_cache_preseeding.preseed_governance_cache') as mock_governance, \
             patch('core.byok_cache_preseeding.preseed_cache_aware_router') as mock_router:

            mock_pricing.return_value = {"success": True, "duration_seconds": 3.0}
            mock_cognitive.return_value = {"success": True, "duration_seconds": 0.1}
            mock_governance.return_value = {"success": True, "duration_seconds": 0.1}
            mock_router.return_value = {"success": True, "duration_seconds": 0.0}

            result = await preseed_all_caches(workspace_id="default", verbose=False)

            assert "duration_seconds" in result
            assert result["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_handles_partial_failure(self, db):
        """RED: Test that partial failure is handled gracefully."""
        with patch('core.byok_cache_preseeding.preseed_pricing_cache') as mock_pricing, \
             patch('core.byok_cache_preseeding.preseed_cognitive_models') as mock_cognitive, \
             patch('core.byok_cache_preseeding.preseed_governance_cache') as mock_governance, \
             patch('core.byok_cache_preseeding.preseed_cache_aware_router') as mock_router:

            # Pricing fails, others succeed
            mock_pricing.return_value = {"success": False, "error": "Network error"}
            mock_cognitive.return_value = {"success": True, "tiers_loaded": 5}
            mock_governance.return_value = {"success": True, "actions_cached": 60}
            mock_router.return_value = {"success": True, "prompts_seeded": 10}

            result = await preseed_all_caches(workspace_id="default", verbose=False)

            assert result["pricing"]["success"] is False
            assert result["cognitive"]["success"] is True
            assert result["governance"]["success"] is True
            assert result["cache_aware"]["success"] is True


# =============================================================================
# Test Class: Preseed Pricing Cache
# =============================================================================

class TestPreseedPricingCache:
    """Tests for preseed_pricing_cache function."""

    @pytest.mark.asyncio
    async def test_fetches_pricing_from_apis(self):
        """RED: Test that pricing is fetched from external APIs."""
        with patch('core.byok_cache_preseeding.refresh_pricing_cache') as mock_refresh:

            mock_refresh.return_value = {
                "gpt-4o": {"input_cost_per_token": 0.000005},
                "claude-3-5-sonnet": {"input_cost_per_token": 0.000003},
            }

            result = await preseed_pricing_cache(force_refresh=True, verbose=False)

            assert result["success"] is True
            assert result["models_loaded"] == 2
            mock_refresh.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_analyzes_providers(self):
        """RED: Test that providers are identified and counted."""
        with patch('core.byok_cache_preseeding.refresh_pricing_cache') as mock_refresh:

            mock_refresh.return_value = {
                "gpt-4o": {"litellm_provider": "openai", "supports_cache": True},
                "claude-3-5-sonnet": {"litellm_provider": "anthropic", "supports_cache": True},
                "deepseek-chat": {"litellm_provider": "deepseek", "supports_cache": False},
            }

            result = await preseed_pricing_cache(force_refresh=True, verbose=False)

            assert "providers" in result
            assert len(result["providers"]) == 3
            assert "openai" in result["providers"]
            assert "anthropic" in result["providers"]

    @pytest.mark.asyncio
    async def test_counts_cache_capabilities(self):
        """RED: Test that cache support is counted."""
        with patch('core.byok_cache_preseeding.refresh_pricing_cache') as mock_refresh:

            mock_refresh.return_value = {
                "gpt-4o": {"supports_cache": True},
                "claude-3-5-sonnet": {"supports_cache": True},
                "deepseek-chat": {"supports_cache": False},
            }

            result = await preseed_pricing_cache(force_refresh=True, verbose=False)

            assert "models_with_cache_support" in result
            assert result["models_with_cache_support"] == 2

    @pytest.mark.asyncio
    async def test_handles_fetch_failure(self):
        """RED: Test that fetch failures are handled."""
        with patch('core.byok_cache_preseeding.refresh_pricing_cache') as mock_refresh:

            mock_refresh.side_effect = Exception("Network error")

            result = await preseed_pricing_cache(force_refresh=True, verbose=False)

            assert result["success"] is False
            assert "error" in result
            assert "Network error" in result["error"]


# =============================================================================
# Test Class: Preseed Cognitive Models
# =============================================================================

class TestPreseedCognitiveModels:
    """Tests for preseed_cognitive_models function."""

    @pytest.mark.asyncio
    async def test_validates_all_tiers(self):
        """RED: Test that all cognitive tiers are validated."""
        with patch('core.byok_cache_preseeding.CognitiveClassifier') as mock_classifier, \
             patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher:

            # Setup mock classifier
            classifier_instance = Mock()
            classifier_instance.get_tier_models.side_effect = [
                ["gpt-4o-mini", "haiku"],  # MICRO
                ["gemini-flash", "deepseek-chat"],  # STANDARD
                ["gpt-4o", "sonnet"],  # VERSATILE
                ["gpt-4o", "gemini-pro"],  # HEAVY
                ["gpt-5", "o3"],  # COMPLEX
            ]
            mock_classifier.return_value = classifier_instance

            # Mock pricing fetcher
            mock_fetcher = Mock()
            mock_fetcher.get_model_price.return_value = {"input_cost_per_token": 0.000005}
            mock_get_fetcher.return_value = mock_fetcher

            result = await preseed_cognitive_models(verbose=False)

            assert result["success"] is True
            assert result["tiers_loaded"] == 5

    @pytest.mark.asyncio
    async def test_counts_validated_models(self):
        """RED: Test that model validation is counted."""
        with patch('core.byok_cache_preseeding.CognitiveClassifier') as mock_classifier, \
             patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher:

            classifier_instance = Mock()
            classifier_instance.get_tier_models.return_value = ["gpt-4o", "claude-3-5-sonnet"]
            mock_classifier.return_value = classifier_instance

            mock_fetcher = Mock()
            mock_fetcher.get_model_price.return_value = {"input_cost_per_token": 0.000005}
            mock_get_fetcher.return_value = mock_fetcher

            result = await preseed_cognitive_models(verbose=False)

            assert result["models_validated"] == 2

    @pytest.mark.asyncio
    async def test_identifies_missing_models(self):
        """RED: Test that missing models are identified."""
        with patch('core.byok_cache_preseeding.CognitiveClassifier') as mock_classifier, \
             patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher:

            classifier_instance = Mock()
            # Some models not in pricing cache
            classifier_instance.get_tier_models.return_value = [
                "gpt-4o",  # Available
                "missing-model",  # Not available
            ]
            mock_classifier.return_value = classifier_instance

            # Mock get_model_price to return None for missing model
            def get_model_price_side_effect(model):
                if model == "gpt-4o":
                    return {"input_cost_per_token": 0.000005}
                return None

            mock_fetcher = Mock()
            mock_fetcher.get_model_price.side_effect = get_model_price_side_effect
            mock_get_fetcher.return_value = mock_fetcher

            result = await preseed_cognitive_models(verbose=False)

            assert result["models_missing"] == 1


# =============================================================================
# Test Class: Preseed Governance Cache
# =============================================================================

class TestPreseedGovernanceCache:
    """Tests for preseed_governance_cache function."""

    @pytest.mark.asyncio
    async def test_caches_common_actions(self, db, sample_agent):
        """RED: Test that common agent actions are cached."""
        with patch('core.byok_cache_preseeding.get_governance_cache') as mock_get_cache:

            mock_cache = Mock(spec=GovernanceCache)
            mock_cache.get_stats.return_value = {
                "size": 60,
                "hit_rate": 95.0,
            }
            mock_get_cache.return_value = mock_cache

            result = await preseed_governance_cache(
                workspace_id="default",
                verbose=False
            )

            assert result["success"] is True
            assert result["actions_cached"] > 0
            mock_cache.set.assert_called()

    @pytest.mark.asyncio
    async def test_caches_common_directories(self, db, sample_agent):
        """RED: Test that common directories are cached."""
        with patch('core.byok_cache_preseeding.get_governance_cache') as mock_get_cache:

            mock_cache = Mock(spec=GovernanceCache)
            mock_cache.get_stats.return_value = {"size": 30}
            mock_get_cache.return_value = mock_cache

            result = await preseed_governance_cache(
                workspace_id="default",
                verbose=False
            )

            assert result["success"] is True
            assert result["directories_cached"] > 0
            mock_cache.cache_directory.assert_called()

    @pytest.mark.asyncio
    async def test_returns_cache_stats(self, db, sample_agent):
        """RED: Test that cache statistics are returned."""
        with patch('core.byok_cache_preseeding.get_governance_cache') as mock_get_cache:

            mock_cache = Mock(spec=GovernanceCache)
            mock_cache.get_stats.return_value = {
                "size": 90,
                "hit_rate": 94.5,
                "evictions": 5,
            }
            mock_get_cache.return_value = mock_cache

            result = await preseed_governance_cache(
                workspace_id="default",
                verbose=False
            )

            assert result["cache_size"] == 90
            assert result["cache_hit_rate"] == 94.5


# =============================================================================
# Test Class: Preseed Cache-Aware Router
# =============================================================================

class TestPreseedCacheAwareRouter:
    """Tests for preseed_cache_aware_router function."""

    @pytest.mark.asyncio
    async def test_seeds_baseline_probabilities(self, mock_pricing_fetcher):
        """RED: Test that baseline probabilities are seeded."""
        with patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher, \
             patch('core.byok_cache_preseeding.CacheAwareRouter') as mock_router_class:

            mock_get_fetcher.return_value = mock_pricing_fetcher

            mock_router = Mock()
            mock_router.cache_hit_history = {}
            mock_router_class.return_value = mock_router

            result = await preseed_cache_aware_router(
                workspace_id="default",
                verbose=False
            )

            assert result["success"] is True
            assert result["prompts_seeded"] == 10

    @pytest.mark.asyncio
    async def test_establishes_fifty_percent_baseline(self, mock_pricing_fetcher):
        """RED: Test that 50% baseline probability is set."""
        with patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher, \
             patch('core.byok_cache_preseeding.CacheAwareRouter') as mock_router_class:

            mock_get_fetcher.return_value = mock_pricing_fetcher

            mock_router = Mock()
            mock_router.cache_hit_history = {}
            mock_router_class.return_value = mock_router

            result = await preseed_cache_aware_router(
                workspace_id="default",
                verbose=False
            )

            assert result["baseline_probability"] == 0.5

    @pytest.mark.asyncio
    async def test_tracks_history_size(self, mock_pricing_fetcher):
        """RED: Test that history size is tracked."""
        with patch('core.byok_cache_preseeding.get_pricing_fetcher') as mock_get_fetcher, \
             patch('core.byok_cache_preseeding.CacheAwareRouter') as mock_router_class:

            mock_get_fetcher.return_value = mock_pricing_fetcher

            mock_router = Mock()
            mock_router.cache_hit_history = {"key": [5, 10]}
            mock_router_class.return_value = mock_router

            result = await preseed_cache_aware_router(
                workspace_id="default",
                verbose=False
            )

            assert result["cache_history_size"] == 1


# =============================================================================
# Test Class: Startup Hook
# =============================================================================

class TestMaybePreseedOnStartup:
    """Tests for maybe_preseed_on_startup function."""

    @pytest.mark.asyncio
    async def test_preseeds_when_enabled(self):
        """RED: Test that pre-seeding runs when enabled."""
        with patch.dict(os.environ, {"PRESEED_CACHE_ON_STARTUP": "true"}), \
             patch('core.byok_cache_preseeding.preseed_all_caches') as mock_preseed:

            mock_preseed.return_value = {
                "success": True,
                "duration_seconds": 3.5,
            }

            result = await maybe_preseed_on_startup()

            assert result is not None
            assert result["success"] is True
            mock_preseed.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """RED: Test that pre-seeding is skipped when disabled."""
        with patch.dict(os.environ, {"PRESEED_CACHE_ON_STARTUP": "false"}):
            result = await maybe_preseed_on_startup()

            assert result is None

    @pytest.mark.asyncio
    async def test_handles_preseeding_failure_gracefully(self):
        """RED: Test that startup continues on pre-seeding failure."""
        with patch.dict(os.environ, {"PRESEED_CACHE_ON_STARTUP": "true"}), \
             patch('core.byok_cache_preseeding.preseed_all_caches') as mock_preseed:

            mock_preseed.side_effect = Exception("Network error")

            result = await maybe_preseed_on_startup()

            # Should return error but not raise
            assert result is not None
            assert result["success"] is False
            assert "Network error" in result["error"]


# =============================================================================
# Test Class: Print Preseed Results
# =============================================================================

class TestPrintPreseedResults:
    """Tests for print_preseed_results function."""

    def test_prints_success_results(self, capsys):
        """RED: Test that success results are printed."""
        results = {
            "pricing": {"success": True, "models_loaded": 1523, "duration_seconds": 3.0},
            "cognitive": {"success": True, "tiers_loaded": 5, "duration_seconds": 0.1},
            "governance": {"success": True, "actions_cached": 60, "duration_seconds": 0.1},
            "cache_aware": {"success": True, "prompts_seeded": 10, "duration_seconds": 0.0},
            "duration_seconds": 3.2,
        }

        print_preseed_results(results)

        captured = capsys.readouterr()
        assert "COMPLETE" in captured.out
        assert "3.2" in captured.out

    def test_prints_failure_results(self, capsys):
        """RED: Test that failure results are printed."""
        results = {
            "pricing": {"success": False, "error": "Network error"},
            "error": "Pre-seeding failed",
        }

        print_preseed_results(results)

        captured = capsys.readouterr()
        assert "FAILED" in captured.out


# =============================================================================
# Test Class: Admin API Endpoints
# =============================================================================

class TestCacheAPIEndpoints:
    """Tests for cache management API endpoints."""

    def test_preseed_endpoint_accepts_all(self, client, app):
        """RED: Test that preseed endpoint accepts 'all' cache type."""
        with patch('api.admin.cache_routes.preseed_all_caches') as mock_preseed:
            mock_preseed.return_value = {
                "success": True,
                "started_at": "2026-05-02T10:00:00Z",
                "completed_at": "2026-05-02T10:00:15Z",
                "duration_seconds": 15.0,
            }

            response = client.post(
                "/api/v1/admin/cache/preseed",
                json={"cache_type": "all", "workspace_id": "default"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_preseed_endpoint_accepts_pricing(self, client, app):
        """RED: Test that preseed endpoint accepts 'pricing' cache type."""
        with patch('api.admin.cache_routes.preseed_pricing_cache') as mock_pricing:
            mock_pricing.return_value = {
                "success": True,
                "models_loaded": 1523,
            }

            response = client.post(
                "/api/v1/admin/cache/preseed",
                json={"cache_type": "pricing"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["pricing"]["success"] is True

    def test_preseed_endpoint_rejects_invalid_type(self, client, app):
        """RED: Test that invalid cache type returns 400."""
        response = client.post(
            "/api/v1/admin/cache/preseed",
            json={"cache_type": "invalid"}
        )

        assert response.status_code == 400

    def test_stats_endpoint_returns_statistics(self, client, app):
        """RED: Test that stats endpoint returns cache statistics."""
        with patch('api.admin.cache_routes.get_governance_cache') as mock_gov, \
             patch('api.admin.cache_routes.get_pricing_fetcher') as mock_pricing, \
             patch('api.admin.cache_routes.CacheAwareRouter') as mock_router:

            mock_gov_instance = Mock()
            mock_gov_instance.get_stats.return_value = {
                "size": 156,
                "hit_rate": 94.5,
            }
            mock_gov.return_value = mock_gov_instance

            mock_pricing_instance = Mock()
            mock_pricing_instance.pricing_cache = {"gpt-4o": {}}
            mock_pricing_instance.last_fetch = datetime.now()
            mock_pricing.return_value = mock_pricing_instance

            mock_router_instance = Mock()
            mock_router_instance.cache_hit_history = {"key": [5, 10]}
            mock_router.return_value = mock_router_instance

            response = client.get("/api/v1/admin/cache/stats")

            assert response.status_code == 200
            data = response.json()
            assert "governance_cache" in data
            assert "pricing_cache" in data
            assert "cache_aware_router" in data

    def test_health_endpoint_returns_status(self, client, app):
        """RED: Test that health endpoint returns cache health status."""
        with patch('api.admin.cache_routes.get_governance_cache') as mock_gov, \
             patch('api.admin.cache_routes.get_pricing_fetcher') as mock_pricing, \
             patch('api.admin.cache_routes.CacheAwareRouter') as mock_router:

            mock_gov_instance = Mock()
            mock_gov_instance.get_stats.return_value = {"size": 156}
            mock_gov.return_value = mock_gov_instance

            mock_pricing_instance = Mock()
            mock_pricing_instance.pricing_cache = {"gpt-4o": {}}
            mock_pricing_instance.last_fetch = datetime.now()
            mock_pricing.return_value = mock_pricing_instance

            mock_router_instance = Mock()
            mock_router_instance.cache_hit_history = {}
            mock_router.return_value = mock_router_instance

            response = client.get("/api/v1/admin/cache/health")

            assert response.status_code == 200
            data = response.json()
            assert "overall_status" in data
            assert data["overall_status"] == "OK"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

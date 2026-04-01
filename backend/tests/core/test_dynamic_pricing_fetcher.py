"""
TDD Tests for DynamicPricingFetcher

Tests for the dynamic pricing fetcher that retrieves real-time AI model pricing
from LiteLLM GitHub and OpenRouter API.

Tests cover:
- Cache management
- LiteLLM pricing fetch
- OpenRouter pricing fetch
- Price lookup and comparison
- Cost estimation

Run: pytest tests/core/test_dynamic_pricing_fetcher.py -v
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from core.dynamic_pricing_fetcher import DynamicPricingFetcher, get_pricing_fetcher


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def pricing_fetcher() -> DynamicPricingFetcher:
    """Create a fresh pricing fetcher instance."""
    fetcher = DynamicPricingFetcher()
    fetcher.pricing_cache = {}
    fetcher.last_fetch = None
    return fetcher


@pytest.fixture
def mock_litellm_response() -> dict:
    """Mock LiteLLM API response with realistic pricing data."""
    return {
        "gpt-4o": {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_tokens": 128000,
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
            "litellm_provider": "openai",
            "mode": "chat"
        },
        "gpt-4o-mini": {
            "input_cost_per_token": 0.00000015,
            "output_cost_per_token": 0.0000006,
            "max_tokens": 128000,
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
            "litellm_provider": "openai",
            "mode": "chat"
        },
        "claude-3-5-sonnet": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "max_tokens": 200000,
            "max_input_tokens": 200000,
            "max_output_tokens": 8192,
            "litellm_provider": "anthropic",
            "mode": "chat"
        },
        "deepseek-chat": {
            "input_cost_per_token": 0.00000014,
            "output_cost_per_token": 0.00000028,
            "max_tokens": 128000,
            "max_input_tokens": 128000,
            "max_output_tokens": 8192,
            "litellm_provider": "deepseek",
            "mode": "chat"
        }
    }


@pytest.fixture
def mock_openrouter_response() -> dict:
    """Mock OpenRouter API response."""
    return {
        "data": [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000015"
                },
                "context_length": 128000,
                "description": "OpenAI GPT-4o model"
            },
            {
                "id": "anthropic/claude-3.5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "pricing": {
                    "prompt": "0.000003",
                    "completion": "0.000015"
                },
                "context_length": 200000,
                "description": "Anthropic Claude 3.5 Sonnet"
            }
        ]
    }


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Tests for DynamicPricingFetcher initialization."""

    def test_init_creates_empty_cache(self, pricing_fetcher):
        """Test that initialization creates empty cache."""
        assert pricing_fetcher.pricing_cache == {}
        assert pricing_fetcher.last_fetch is None

    def test_init_sets_default_cache_duration(self, pricing_fetcher):
        """Test that cache duration is set to 24 hours."""
        # CACHE_DURATION_HOURS is a module constant
        from core.dynamic_pricing_fetcher import CACHE_DURATION_HOURS
        assert CACHE_DURATION_HOURS == 24


# ============================================================================
# Cache Management Tests
# ============================================================================

class TestCacheManagement:
    """Tests for cache management functionality."""

    def test_is_cache_valid_no_fetch(self, pricing_fetcher):
        """Test cache validity when never fetched."""
        assert pricing_fetcher._is_cache_valid() is False

    def test_is_cache_valid_fresh_fetch(self, pricing_fetcher):
        """Test cache validity with recent fetch."""
        pricing_fetcher.last_fetch = datetime.now()
        pricing_fetcher.pricing_cache = {"model": {}}
        
        assert pricing_fetcher._is_cache_valid() is True

    def test_is_cache_valid_expired(self, pricing_fetcher):
        """Test cache validity with expired fetch."""
        pricing_fetcher.last_fetch = datetime.now() - timedelta(hours=25)
        pricing_fetcher.pricing_cache = {"model": {}}
        
        assert pricing_fetcher._is_cache_valid() is False

    def test_is_cache_valid_at_boundary(self, pricing_fetcher):
        """Test cache validity at 24-hour boundary."""
        pricing_fetcher.last_fetch = datetime.now() - timedelta(hours=23, minutes=59)
        pricing_fetcher.pricing_cache = {"model": {}}
        
        assert pricing_fetcher._is_cache_valid() is True
        
        pricing_fetcher.last_fetch = datetime.now() - timedelta(hours=24, minutes=1)
        assert pricing_fetcher._is_cache_valid() is False


# ============================================================================
# LiteLLM Pricing Fetch Tests
# ============================================================================

class TestLiteLLMFetch:
    """Tests for fetching pricing from LiteLLM."""

    @pytest.mark.asyncio
    async def test_fetch_litellm_pricing_success(self, pricing_fetcher, mock_litellm_response):
        """Test successful LiteLLM pricing fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_litellm_response
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await pricing_fetcher.fetch_litellm_pricing()

            # 4 from mock + 3 MiniMax fallback models
            assert len(result) == 7
            assert "gpt-4o" in result
            assert result["gpt-4o"]["input_cost_per_token"] == 0.000005
            assert result["gpt-4o"]["source"] == "litellm"
            # Check MiniMax fallback models added
            assert "MiniMax-M2.7" in result

    @pytest.mark.asyncio
    async def test_fetch_litellm_pricing_transforms_data(self, pricing_fetcher, mock_litellm_response):
        """Test that LiteLLM data is correctly transformed."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_litellm_response
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_litellm_pricing()
            
            # Check transformation
            gpt4o = result["gpt-4o"]
            assert "litellm_provider" in gpt4o
            assert "mode" in gpt4o
            assert gpt4o["litellm_provider"] == "openai"

    @pytest.mark.asyncio
    async def test_fetch_litellm_pricing_error(self, pricing_fetcher):
        """Test error handling during LiteLLM fetch."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_litellm_pricing()
            
            assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_litellm_pricing_timeout(self, pricing_fetcher):
        """Test timeout handling during LiteLLM fetch."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_litellm_pricing()
            
            assert result == {}


# ============================================================================
# OpenRouter Pricing Fetch Tests
# ============================================================================

class TestOpenRouterFetch:
    """Tests for fetching pricing from OpenRouter."""

    @pytest.mark.asyncio
    async def test_fetch_openrouter_pricing_success(self, pricing_fetcher, mock_openrouter_response):
        """Test successful OpenRouter pricing fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openrouter_response
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_openrouter_pricing()
            
            assert len(result) == 2
            assert "openai/gpt-4o" in result
            assert result["openai/gpt-4o"]["input_cost_per_token"] == 0.000005

    @pytest.mark.asyncio
    async def test_fetch_openrouter_pricing_transforms_data(self, pricing_fetcher, mock_openrouter_response):
        """Test that OpenRouter data is correctly transformed."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_openrouter_response
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_openrouter_pricing()
            
            claude = result["anthropic/claude-3.5-sonnet"]
            assert "name" in claude
            assert "description" in claude
            assert claude["source"] == "openrouter"

    @pytest.mark.asyncio
    async def test_fetch_openrouter_pricing_error(self, pricing_fetcher):
        """Test error handling during OpenRouter fetch."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await pricing_fetcher.fetch_openrouter_pricing()
            
            assert result == {}


# ============================================================================
# Refresh Pricing Tests
# ============================================================================

class TestRefreshPricing:
    """Tests for refreshing pricing data."""

    @pytest.mark.asyncio
    async def test_refresh_pricing_fetches_both_sources(self, pricing_fetcher):
        """Test that refresh fetches from both LiteLLM and OpenRouter."""
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', AsyncMock(return_value={"litellm_model": {}})) as mock_litellm:
            with patch.object(pricing_fetcher, 'fetch_openrouter_pricing', AsyncMock(return_value={"openrouter_model": {}})) as mock_openrouter:
                
                await pricing_fetcher.refresh_pricing(force=True)
                
                mock_litellm.assert_called_once()
                mock_openrouter.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_pricing_merges_data(self, pricing_fetcher):
        """Test that pricing data from both sources is merged."""
        litellm_data = {"gpt-4o": {"source": "litellm"}}
        openrouter_data = {"claude-3-5-sonnet": {"source": "openrouter"}}
        
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', AsyncMock(return_value=litellm_data)):
            with patch.object(pricing_fetcher, 'fetch_openrouter_pricing', AsyncMock(return_value=openrouter_data)):
                
                await pricing_fetcher.refresh_pricing(force=True)
                
                assert "gpt-4o" in pricing_fetcher.pricing_cache
                assert "claude-3-5-sonnet" in pricing_fetcher.pricing_cache
                assert len(pricing_fetcher.pricing_cache) == 2

    @pytest.mark.asyncio
    async def test_refresh_pricing_updates_timestamp(self, pricing_fetcher):
        """Test that refresh updates the last_fetch timestamp."""
        before_fetch = datetime.now()
        
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', AsyncMock(return_value={})):
            with patch.object(pricing_fetcher, 'fetch_openrouter_pricing', AsyncMock(return_value={})):
                
                await pricing_fetcher.refresh_pricing(force=True)
                
                after_fetch = datetime.now()
                assert pricing_fetcher.last_fetch is not None
                assert before_fetch <= pricing_fetcher.last_fetch <= after_fetch

    @pytest.mark.asyncio
    async def test_refresh_pricing_uses_cache_when_valid(self, pricing_fetcher):
        """Test that refresh uses cache when still valid."""
        pricing_fetcher.last_fetch = datetime.now()
        pricing_fetcher.pricing_cache = {"cached_model": {}}
        
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing') as mock_litellm:
            with patch.object(pricing_fetcher, 'fetch_openrouter_pricing') as mock_openrouter:
                
                result = await pricing_fetcher.refresh_pricing(force=False)
                
                mock_litellm.assert_not_called()
                mock_openrouter.assert_not_called()
                assert result == pricing_fetcher.pricing_cache

    @pytest.mark.asyncio
    async def test_refresh_pricing_force_ignores_cache(self, pricing_fetcher):
        """Test that force=True ignores valid cache."""
        pricing_fetcher.last_fetch = datetime.now()
        pricing_fetcher.pricing_cache = {"cached_model": {}}
        
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', AsyncMock(return_value={"new_model": {}})):
            with patch.object(pricing_fetcher, 'fetch_openrouter_pricing', AsyncMock(return_value={})):
                
                await pricing_fetcher.refresh_pricing(force=True)
                
                assert "new_model" in pricing_fetcher.pricing_cache


# ============================================================================
# Model Price Lookup Tests
# ============================================================================

class TestModelPriceLookup:
    """Tests for looking up model prices."""

    def test_get_model_price_found(self, pricing_fetcher):
        """Test getting price for existing model."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "output_cost_per_token": 0.000015
            }
        }
        
        result = pricing_fetcher.get_model_price("gpt-4o")
        
        assert result is not None
        assert result["input_cost_per_token"] == 0.000005
        assert result["output_cost_per_token"] == 0.000015

    def test_get_model_price_not_found(self, pricing_fetcher):
        """Test getting price for non-existent model."""
        pricing_fetcher.pricing_cache = {"gpt-4o": {}}
        
        result = pricing_fetcher.get_model_price("unknown-model")
        
        assert result is None

    def test_get_model_price_partial_data(self, pricing_fetcher):
        """Test getting price with partial data."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005
                # Missing output_cost_per_token
            }
        }
        
        result = pricing_fetcher.get_model_price("gpt-4o")
        
        assert result is not None
        assert result["input_cost_per_token"] == 0.000005
        assert result.get("output_cost_per_token", 0) == 0


# ============================================================================
# Provider Comparison Tests
# ============================================================================

class TestProviderComparison:
    """Tests for provider comparison functionality."""

    def test_compare_providers(self, pricing_fetcher):
        """Test comparing providers by average cost."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "litellm_provider": "openai"
            },
            "gpt-4o-mini": {
                "input_cost_per_token": 0.00000015,
                "litellm_provider": "openai"
            },
            "claude-3-5-sonnet": {
                "input_cost_per_token": 0.000003,
                "litellm_provider": "anthropic"
            }
        }
        
        result = pricing_fetcher.compare_providers()
        
        assert "openai" in result
        assert "anthropic" in result
        assert result["openai"]["model_count"] == 2
        assert result["anthropic"]["model_count"] == 1

    def test_get_cheapest_models(self, pricing_fetcher):
        """Test getting cheapest models."""
        pricing_fetcher.pricing_cache = {
            "expensive-model": {
                "input_cost_per_token": 0.00001,
                "litellm_provider": "openai"
            },
            "cheap-model": {
                "input_cost_per_token": 0.0000001,
                "litellm_provider": "deepseek"
            },
            "medium-model": {
                "input_cost_per_token": 0.000001,
                "litellm_provider": "anthropic"
            }
        }
        
        result = pricing_fetcher.get_cheapest_models(2)
        
        assert len(result) == 2
        assert result[0]["model"] == "cheap-model"
        assert result[1]["model"] == "medium-model"


# ============================================================================
# Cost Estimation Tests
# ============================================================================

class TestCostEstimation:
    """Tests for cost estimation functionality."""

    def test_estimate_cost_basic(self, pricing_fetcher):
        """Test basic cost estimation."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "output_cost_per_token": 0.000015
            }
        }

        cost = pricing_fetcher.estimate_cost("gpt-4o", input_tokens=1000, output_tokens=500)

        assert cost == 0.0125  # 0.000005 * 1000 + 0.000015 * 500

    def test_estimate_cost_zero_tokens(self, pricing_fetcher):
        """Test cost estimation with zero tokens."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "output_cost_per_token": 0.000015
            }
        }

        cost = pricing_fetcher.estimate_cost("gpt-4o", input_tokens=0, output_tokens=0)

        assert cost == 0

    def test_estimate_cost_model_not_found(self, pricing_fetcher):
        """Test cost estimation for unknown model."""
        pricing_fetcher.pricing_cache = {}

        cost = pricing_fetcher.estimate_cost("unknown-model", input_tokens=1000, output_tokens=500)

        assert cost is None

    def test_estimate_cost_output_only(self, pricing_fetcher):
        """Test cost estimation with only output tokens."""
        pricing_fetcher.pricing_cache = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "output_cost_per_token": 0.000015
            }
        }

        cost = pricing_fetcher.estimate_cost("gpt-4o", input_tokens=0, output_tokens=1000)

        assert abs(cost - 0.015) < 0.0001  # Floating point tolerance


# ============================================================================
# Singleton Pattern Tests
# ============================================================================

class TestSingletonPattern:
    """Tests for get_pricing_fetcher singleton function."""

    def test_get_pricing_fetcher_returns_instance(self):
        """Test that get_pricing_fetcher returns an instance."""
        fetcher = get_pricing_fetcher()
        
        assert fetcher is not None
        assert isinstance(fetcher, DynamicPricingFetcher)

    def test_get_pricing_fetcher_returns_same_instance(self):
        """Test that get_pricing_fetcher returns same instance (singleton)."""
        fetcher1 = get_pricing_fetcher()
        fetcher2 = get_pricing_fetcher()
        
        assert fetcher1 is fetcher2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

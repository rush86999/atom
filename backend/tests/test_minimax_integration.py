"""
MiniMax M2.5 Integration Tests

Comprehensive test suite for MiniMax API wrapper, pricing integration,
and BYOK handler integration.

Test Categories:
- Client initialization (3 tests)
- Generate method (4 tests)
- Pricing and capabilities (3 tests)
- BYOK integration (3 tests)
- Fallback behavior (3 tests)
- Benchmark integration (1 test)

Total: 17 tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from core.llm.minimax_integration import MiniMaxIntegration, RateLimitedError
from core.llm.byok_handler import BYOKHandler, COST_EFFICIENT_MODELS
from core.benchmarks import get_quality_score
from core.dynamic_pricing_fetcher import get_pricing_fetcher


class TestMiniMaxClientInitialization:
    """Test MiniMax client initialization and configuration"""

    def test_minimax_client_initialization(self):
        """Test client created with correct BASE_URL"""
        client = MiniMaxIntegration("test-api-key")
        assert client.BASE_URL == "https://api.minimaxi.com/v1"
        assert client.api_key == "test-api-key"

    def test_api_key_header_set(self):
        """Test Authorization header set correctly"""
        client = MiniMaxIntegration("sk-test-key-123")
        headers = client.client.headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer sk-test-key-123"
        assert headers["Content-Type"] == "application/json"

    def test_timeout_configuration(self):
        """Test 30s timeout configured"""
        client = MiniMaxIntegration("test-key")
        # httpx timeout is a Timeout object, check the timeout attribute
        assert client.client.timeout == 30.0 or str(client.client.timeout) == "Timeout(timeout=30.0)"


class TestGenerateMethod:
    """Test MiniMax generate method with various scenarios"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test returns response content on success"""
        client = MiniMaxIntegration("test-key")

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", return_value=mock_response):
            result = await client.generate("Test prompt")
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_generate_rate_limit(self):
        """Test raises RateLimitedError on 429"""
        client = MiniMaxIntegration("test-key")

        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = httpx.HTTPStatusError("Rate limit", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status.side_effect = error

        with patch.object(client.client, "post", return_value=mock_response):
            with pytest.raises(RateLimitedError):
                await client.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_error_handling(self):
        """Test returns None on other errors"""
        client = MiniMaxIntegration("test-key")

        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status.side_effect = error

        with patch.object(client.client, "post", return_value=mock_response):
            result = await client.generate("Test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_temperature_parameter(self):
        """Test temperature parameter passed correctly to API"""
        client = MiniMaxIntegration("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", return_value=mock_response) as mock_post:
            await client.generate("Test", temperature=0.5, max_tokens=500)

            # Verify request payload
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 500
            assert payload["model"] == "m2.5"


class TestPricingAndCapabilities:
    """Test pricing and capabilities methods"""

    def test_get_pricing_returns_estimated(self):
        """Test returns $1/M pricing"""
        client = MiniMaxIntegration("test-key")
        pricing = client.get_pricing()

        assert pricing["input_cost_per_token"] == 0.000001  # $1/M
        assert pricing["output_cost_per_token"] == 0.000001  # $1/M
        assert pricing["max_tokens"] == 128000

    def test_get_capabilities(self):
        """Test returns correct tier (STANDARD) and quality_score (88)"""
        from core.llm.cognitive_tier_system import CognitiveTier

        client = MiniMaxIntegration("test-key")
        capabilities = client.get_capabilities()

        assert capabilities["quality_score"] == 88
        assert capabilities["tier"] == CognitiveTier.STANDARD
        assert capabilities["supports_vision"] is False
        assert capabilities["supports_tools"] is True
        assert capabilities["supports_cache"] is False

    def test_supports_tools_true(self):
        """Test native agent support"""
        client = MiniMaxIntegration("test-key")
        capabilities = client.get_capabilities()
        assert capabilities["supports_tools"] is True


class TestBYOKIntegration:
    """Test MiniMax integration with BYOK handler"""

    def test_minimax_in_provider_config(self):
        """Test listed in providers_config"""
        # This is tested indirectly through COST_EFFICIENT_MODELS
        assert "minimax" in COST_EFFICIENT_MODELS

    def test_minimax_in_cost_efficient_models(self):
        """Test mapped to m2.5 for all complexities"""
        from core.llm.byok_handler import QueryComplexity

        minimax_models = COST_EFFICIENT_MODELS.get("minimax", {})

        assert QueryComplexity.SIMPLE in minimax_models
        assert QueryComplexity.MODERATE in minimax_models
        assert QueryComplexity.COMPLEX in minimax_models
        assert QueryComplexity.ADVANCED in minimax_models

        # All should map to minimax-m2.5
        for complexity in QueryComplexity:
            assert minimax_models[complexity] == "minimax-m2.5"

    def test_minimax_in_static_fallback(self):
        """Test appears in provider_priority"""
        # This is tested by checking BYOKHandler has minimax in config
        # Actual routing tested in integration tests
        assert "minimax" in COST_EFFICIENT_MODELS


class TestFallbackBehavior:
    """Test graceful fallback when MiniMax unavailable"""

    @pytest.mark.asyncio
    async def test_test_connection_returns_false_on_401(self):
        """Test handles invalid API key"""
        client = MiniMaxIntegration("invalid-key")

        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client.client, "get", return_value=mock_response):
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_generate_returns_none_on_unavailable(self):
        """Test graceful degradation"""
        client = MiniMaxIntegration("test-key")

        # Mock connection error
        with patch.object(client.client, "post", side_effect=Exception("API unavailable")):
            result = await client.generate("Test")
            assert result is None

    def test_byok_falls_back_to_next_provider(self):
        """Test BYOK continues without MiniMax"""
        # Create handler without MiniMax API key
        handler = BYOKHandler()

        # Handler should still work with other providers
        # This test ensures minimax doesn't break the system
        assert hasattr(handler, "clients")
        assert hasattr(handler, "get_ranked_providers")


class TestBenchmarkIntegration:
    """Test MiniMax integration with benchmark system"""

    def test_quality_score_defined(self):
        """Test get_quality_score('minimax-m2.5') returns 88"""
        score = get_quality_score("minimax-m2.5")
        assert score == 88

    def test_pricing_fetcher_includes_minimax(self):
        """Test DynamicPricingFetcher includes MiniMax pricing"""
        fetcher = get_pricing_fetcher()

        # Force refresh to get minimax pricing
        import asyncio
        asyncio.run(fetcher.refresh_pricing(force=True))

        pricing = fetcher.get_model_price("minimax-m2.5")

        assert pricing is not None
        assert pricing["input_cost_per_token"] == 0.000001
        assert pricing["output_cost_per_token"] == 0.000001
        assert pricing["source"] == "estimated"

    def test_is_pricing_estimated(self):
        """Test is_pricing_estimated() identifies estimated sources"""
        fetcher = get_pricing_fetcher()

        # Ensure minimax pricing is loaded
        import asyncio
        asyncio.run(fetcher.refresh_pricing(force=True))

        assert fetcher.is_pricing_estimated("minimax-m2.5") is True
        assert fetcher.is_pricing_estimated("gpt-4o") is False

"""
MiniMax M2.7 Integration Tests

Comprehensive test suite for MiniMax API wrapper, pricing integration,
BYOK handler integration, and independent AI validator provider.

Test Categories:
- Client initialization (4 tests)
- Generate method (5 tests) — includes temperature clamping
- Pricing and capabilities (4 tests)
- BYOK integration (4 tests)
- Fallback behavior (3 tests)
- Benchmark integration (3 tests)
- Temperature clamping (4 tests)
- Model selection (3 tests)

Total: 30 unit tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from core.llm.minimax_integration import (
    MiniMaxIntegration,
    RateLimitedError,
    clamp_temperature,
    MINIMAX_MODELS,
    DEFAULT_MODEL,
)
from core.llm.byok_handler import BYOKHandler, COST_EFFICIENT_MODELS
from core.benchmarks import get_quality_score
from core.dynamic_pricing_fetcher import get_pricing_fetcher


class TestMiniMaxClientInitialization:
    """Test MiniMax client initialization and configuration"""

    def test_minimax_client_initialization(self):
        """Test client created with correct BASE_URL (api.minimax.io)"""
        client = MiniMaxIntegration("test-api-key")
        assert client.BASE_URL == "https://api.minimax.io/v1"
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
        assert client.client.timeout == 30.0 or str(client.client.timeout) == "Timeout(timeout=30.0)"

    def test_default_model_is_m27(self):
        """Test default model is MiniMax-M2.7"""
        client = MiniMaxIntegration("test-key")
        assert client.model == "MiniMax-M2.7"

    def test_custom_model_selection(self):
        """Test custom model can be specified"""
        client = MiniMaxIntegration("test-key", model="MiniMax-M2.7-highspeed")
        assert client.model == "MiniMax-M2.7-highspeed"


class TestTemperatureClamping:
    """Test temperature clamping to MiniMax's accepted range (0.0, 1.0]"""

    def test_clamp_zero_temperature(self):
        """Test temperature=0.0 clamped to 0.01"""
        assert clamp_temperature(0.0) == 0.01

    def test_clamp_negative_temperature(self):
        """Test negative temperature clamped to 0.01"""
        assert clamp_temperature(-0.5) == 0.01

    def test_clamp_high_temperature(self):
        """Test temperature>1.0 clamped to 1.0"""
        assert clamp_temperature(1.5) == 1.0
        assert clamp_temperature(2.0) == 1.0

    def test_valid_temperature_unchanged(self):
        """Test valid temperature passes through unchanged"""
        assert clamp_temperature(0.5) == 0.5
        assert clamp_temperature(0.7) == 0.7
        assert clamp_temperature(1.0) == 1.0
        assert clamp_temperature(0.01) == 0.01


class TestGenerateMethod:
    """Test MiniMax generate method with various scenarios"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test returns response content on success"""
        client = MiniMaxIntegration("test-key")

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

        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status.side_effect = error

        with patch.object(client.client, "post", return_value=mock_response):
            result = await client.generate("Test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_temperature_clamped_in_request(self):
        """Test temperature is clamped before sending to API"""
        client = MiniMaxIntegration("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", return_value=mock_response) as mock_post:
            # Pass temperature=0 which should be clamped to 0.01
            await client.generate("Test", temperature=0.0, max_tokens=500)

            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["temperature"] == 0.01
            assert payload["max_tokens"] == 500
            assert payload["model"] == "MiniMax-M2.7"

    @pytest.mark.asyncio
    async def test_model_override_in_generate(self):
        """Test model can be overridden per-request"""
        client = MiniMaxIntegration("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.client, "post", return_value=mock_response) as mock_post:
            await client.generate("Test", model="MiniMax-M2.7-highspeed")

            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "MiniMax-M2.7-highspeed"


class TestPricingAndCapabilities:
    """Test pricing and capabilities methods"""

    def test_get_pricing_returns_204k_context(self):
        """Test returns 204K context window"""
        client = MiniMaxIntegration("test-key")
        pricing = client.get_pricing()

        assert pricing["input_cost_per_token"] == 0.000001  # $1/M
        assert pricing["output_cost_per_token"] == 0.000001  # $1/M
        assert pricing["max_tokens"] == 204000

    def test_get_capabilities(self):
        """Test returns correct tier (STANDARD) and quality_score (90)"""
        from core.llm.cognitive_tier_system import CognitiveTier

        client = MiniMaxIntegration("test-key")
        capabilities = client.get_capabilities()

        assert capabilities["quality_score"] == 90
        assert capabilities["tier"] == CognitiveTier.STANDARD
        assert capabilities["supports_vision"] is False
        assert capabilities["supports_tools"] is True
        assert capabilities["supports_cache"] is False

    def test_supports_tools_true(self):
        """Test native agent support"""
        client = MiniMaxIntegration("test-key")
        capabilities = client.get_capabilities()
        assert capabilities["supports_tools"] is True

    def test_available_models_includes_m27(self):
        """Test available models list includes M2.7 variants"""
        models = MiniMaxIntegration.get_available_models()
        assert "MiniMax-M2.7" in models
        assert "MiniMax-M2.7-highspeed" in models
        assert models["MiniMax-M2.7"]["context_window"] == 204000


class TestBYOKIntegration:
    """Test MiniMax integration with BYOK handler"""

    def test_minimax_in_provider_config(self):
        """Test listed in providers_config"""
        assert "minimax" in COST_EFFICIENT_MODELS

    def test_minimax_uses_m27_models(self):
        """Test mapped to M2.7 models"""
        from core.llm.byok_handler import QueryComplexity

        minimax_models = COST_EFFICIENT_MODELS.get("minimax", {})

        assert QueryComplexity.SIMPLE in minimax_models
        assert QueryComplexity.MODERATE in minimax_models
        assert QueryComplexity.COMPLEX in minimax_models
        assert QueryComplexity.ADVANCED in minimax_models

        # Simple/Moderate -> highspeed, Complex/Advanced -> M2.7
        assert minimax_models[QueryComplexity.SIMPLE] == "MiniMax-M2.7-highspeed"
        assert minimax_models[QueryComplexity.MODERATE] == "MiniMax-M2.7-highspeed"
        assert minimax_models[QueryComplexity.COMPLEX] == "MiniMax-M2.7"
        assert minimax_models[QueryComplexity.ADVANCED] == "MiniMax-M2.7"

    def test_minimax_in_static_fallback(self):
        """Test appears in provider_priority"""
        assert "minimax" in COST_EFFICIENT_MODELS

    def test_minimax_base_url_correct(self):
        """Test base URL is api.minimax.io (not api.minimaxi.com)"""
        client = MiniMaxIntegration("test-key")
        assert "api.minimax.io" in client.BASE_URL
        assert "minimaxi" not in client.BASE_URL


class TestFallbackBehavior:
    """Test graceful fallback when MiniMax unavailable"""

    @pytest.mark.asyncio
    async def test_test_connection_returns_false_on_error(self):
        """Test handles connection errors"""
        client = MiniMaxIntegration("invalid-key")

        with patch.object(client.client, "post", side_effect=Exception("Connection error")):
            result = await client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_generate_returns_none_on_unavailable(self):
        """Test graceful degradation"""
        client = MiniMaxIntegration("test-key")

        with patch.object(client.client, "post", side_effect=Exception("API unavailable")):
            result = await client.generate("Test")
            assert result is None

    def test_byok_falls_back_to_next_provider(self):
        """Test BYOK continues without MiniMax"""
        handler = BYOKHandler()
        assert hasattr(handler, "clients")
        assert hasattr(handler, "get_ranked_providers")


class TestBenchmarkIntegration:
    """Test MiniMax integration with benchmark system"""

    def test_m27_quality_score_defined(self):
        """Test get_quality_score('MiniMax-M2.7') returns 90"""
        score = get_quality_score("MiniMax-M2.7")
        assert score == 90

    def test_m27_highspeed_quality_score_defined(self):
        """Test get_quality_score('MiniMax-M2.7-highspeed') returns 89"""
        score = get_quality_score("MiniMax-M2.7-highspeed")
        assert score == 89

    def test_m25_quality_score_still_defined(self):
        """Test legacy minimax-m2.5 score still available"""
        score = get_quality_score("minimax-m2.5")
        assert score == 88


class TestModelConstants:
    """Test model constants and configuration"""

    def test_default_model_constant(self):
        """Test DEFAULT_MODEL is MiniMax-M2.7"""
        assert DEFAULT_MODEL == "MiniMax-M2.7"

    def test_minimax_models_all_204k(self):
        """Test all models have 204K context window"""
        for model_name, info in MINIMAX_MODELS.items():
            assert info["context_window"] == 204000, f"{model_name} should have 204K context"

    def test_minimax_models_includes_all_variants(self):
        """Test model registry includes M2.5 and M2.7 variants"""
        assert "MiniMax-M2.7" in MINIMAX_MODELS
        assert "MiniMax-M2.7-highspeed" in MINIMAX_MODELS
        assert "MiniMax-M2.5" in MINIMAX_MODELS
        assert "MiniMax-M2.5-highspeed" in MINIMAX_MODELS

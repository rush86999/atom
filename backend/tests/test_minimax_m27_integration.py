"""
MiniMax M2.7 Integration Tests

End-to-end integration tests verifying MiniMax M2.7 provider works
correctly across BYOK handler, validator engine, and pricing systems.

These tests require MINIMAX_API_KEY to be set for live API calls.

Test Categories:
- BYOK routing integration (3 tests)
- Validator provider integration (3 tests)
- Pricing pipeline integration (3 tests)

Total: 9 integration tests
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.llm.minimax_integration import MiniMaxIntegration, clamp_temperature
from core.llm.byok_handler import BYOKHandler, COST_EFFICIENT_MODELS, QueryComplexity
from core.benchmarks import get_quality_score, MODEL_QUALITY_SCORES
from core.dynamic_pricing_fetcher import get_pricing_fetcher
from independent_ai_validator.providers.minimax_provider import MiniMaxProvider
from independent_ai_validator.providers.base_provider import ValidationRequest


class TestBYOKRoutingIntegration:
    """Test MiniMax is correctly routed through BYOK handler"""

    def test_minimax_ranked_in_simple_queries(self):
        """Test MiniMax appears early in provider priority for simple queries"""
        handler = BYOKHandler()
        # MiniMax should be in the cost-efficient models
        assert "minimax" in COST_EFFICIENT_MODELS
        # For simple queries, highspeed model should be selected
        assert COST_EFFICIENT_MODELS["minimax"][QueryComplexity.SIMPLE] == "MiniMax-M2.7-highspeed"

    def test_minimax_ranked_for_complex_queries(self):
        """Test MiniMax uses full M2.7 for complex queries"""
        assert COST_EFFICIENT_MODELS["minimax"][QueryComplexity.COMPLEX] == "MiniMax-M2.7"
        assert COST_EFFICIENT_MODELS["minimax"][QueryComplexity.ADVANCED] == "MiniMax-M2.7"

    def test_minimax_quality_scores_in_benchmarks(self):
        """Test all MiniMax models have quality scores"""
        assert get_quality_score("MiniMax-M2.7") == 90
        assert get_quality_score("MiniMax-M2.7-highspeed") == 89
        assert get_quality_score("minimax-m2.5") == 88


class TestValidatorProviderIntegration:
    """Test MiniMax provider works with validator engine"""

    @pytest.mark.asyncio
    async def test_validate_claim_full_pipeline(self):
        """Test full claim validation pipeline with mocked API"""
        provider = MiniMaxProvider("test-key")
        request = ValidationRequest(
            claim="Our platform reduces workflow time by 50%",
            evidence={
                "benchmark_data": {"before": 120, "after": 60, "unit": "minutes"},
                "user_survey": {"respondents": 100, "satisfaction": 0.92},
            },
            claim_type="performance",
            validation_criteria=["Accuracy", "Evidence Support", "Measurability"],
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": (
                "Assessment: VALIDATED\n"
                "Confidence: 88%\n"
                "Evidence Strength: STRONG\n"
                "Reasoning: The benchmark data shows a clear 50% reduction "
                "from 120 to 60 minutes, and the user survey with 100 respondents "
                "confirms high satisfaction (92%).\n"
                "Recommendations: Include statistical significance testing."
            )}}],
            "usage": {"total_tokens": 800, "prompt_tokens": 500, "completion_tokens": 300},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.validate_claim(request)

        assert result.provider == "MiniMax"
        assert result.confidence == 0.88
        assert result.tokens_used == 800
        assert result.model == "MiniMax-M2.7"
        assert "Reasoning" in (result.reasoning or "")

    @pytest.mark.asyncio
    async def test_evidence_analysis_full_pipeline(self):
        """Test full evidence analysis pipeline"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": (
                "Evidence Strength: MODERATE\n"
                "Confidence Score: 72%\n"
                "Overall Assessment: The evidence partially supports the claim."
            )}}],
            "usage": {"total_tokens": 350},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.analyze_evidence(
                {"metrics": {"latency_ms": 50, "uptime": 0.999}},
                "Our API achieves sub-100ms latency with 99.9% uptime",
            )

        assert result.provider == "MiniMax"
        assert result.tokens_used == 350

    @pytest.mark.asyncio
    async def test_bias_check_full_pipeline(self):
        """Test full bias check pipeline"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": (
                "Bias Detected: POTENTIAL\n"
                "Objectivity Score: 75%\n"
                "Confidence: 82%\n"
                "Recommendations: Consider including negative outcomes."
            )}}],
            "usage": {"total_tokens": 250},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.check_bias("Our product is the best in the market with unmatched performance.")

        assert result.provider == "MiniMax"
        assert result.tokens_used == 250


class TestPricingPipelineIntegration:
    """Test MiniMax pricing flows through the full pipeline"""

    def test_pricing_fetcher_includes_m27(self):
        """Test DynamicPricingFetcher includes M2.7 pricing after refresh"""
        fetcher = get_pricing_fetcher()

        # Mock the HTTP calls to avoid network dependency
        import asyncio

        async def _mock_refresh():
            # Simulate refresh that adds MiniMax fallback pricing
            mock_litellm_data = {}
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_litellm_data
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                await fetcher.refresh_pricing(force=True)

        asyncio.run(_mock_refresh())

        pricing = fetcher.get_model_price("MiniMax-M2.7")
        assert pricing is not None
        assert pricing["max_tokens"] == 204000
        assert pricing["source"] == "estimated"

    def test_pricing_fetcher_includes_m27_highspeed(self):
        """Test DynamicPricingFetcher includes M2.7-highspeed pricing"""
        fetcher = get_pricing_fetcher()

        import asyncio

        async def _mock_refresh():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                await fetcher.refresh_pricing(force=True)

        asyncio.run(_mock_refresh())

        pricing = fetcher.get_model_price("MiniMax-M2.7-highspeed")
        assert pricing is not None
        assert pricing["max_tokens"] == 204000

    def test_m25_pricing_updated_to_204k(self):
        """Test M2.5 pricing reflects 204K context (not 128K)"""
        fetcher = get_pricing_fetcher()

        import asyncio

        async def _mock_refresh():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client
                await fetcher.refresh_pricing(force=True)

        asyncio.run(_mock_refresh())

        pricing = fetcher.get_model_price("minimax-m2.5")
        assert pricing is not None
        assert pricing["max_tokens"] == 204000

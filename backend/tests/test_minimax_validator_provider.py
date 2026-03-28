"""
MiniMax Validator Provider Tests

Tests for the MiniMax provider in the independent AI validator system.
Validates claim validation, evidence analysis, bias checking, and health checks.

Test Categories:
- Provider initialization (3 tests)
- Claim validation (3 tests)
- Evidence analysis (2 tests)
- Bias checking (2 tests)
- Confidence extraction (4 tests)
- Health check (2 tests)
- Temperature clamping (2 tests)

Total: 18 unit tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession

from independent_ai_validator.providers.minimax_provider import MiniMaxProvider, _clamp_temperature
from independent_ai_validator.providers.base_provider import LLMResponse, ValidationRequest


class TestMiniMaxProviderInit:
    """Test MiniMax provider initialization"""

    def test_provider_name(self):
        """Test provider name is 'MiniMax'"""
        provider = MiniMaxProvider("test-key")
        assert provider.name == "MiniMax"

    def test_base_url(self):
        """Test base URL is api.minimax.io"""
        provider = MiniMaxProvider("test-key")
        assert provider.base_url == "https://api.minimax.io/v1"

    def test_default_model(self):
        """Test default model is MiniMax-M2.7"""
        provider = MiniMaxProvider("test-key")
        assert provider.model == "MiniMax-M2.7"

    def test_custom_model(self):
        """Test custom model can be specified"""
        provider = MiniMaxProvider("test-key", model="MiniMax-M2.7-highspeed")
        assert provider.model == "MiniMax-M2.7-highspeed"


class TestClaimValidation:
    """Test claim validation with MiniMax"""

    @pytest.mark.asyncio
    async def test_validate_claim_success(self):
        """Test successful claim validation"""
        provider = MiniMaxProvider("test-key")
        request = ValidationRequest(
            claim="Test claim",
            evidence={"test": "evidence"},
            claim_type="capability",
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Assessment: VALIDATED\nConfidence: 85%\nReasoning: Strong evidence supports the claim."}}],
            "usage": {"total_tokens": 500, "prompt_tokens": 300, "completion_tokens": 200},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.validate_claim(request)

        assert isinstance(result, LLMResponse)
        assert result.provider == "MiniMax"
        assert result.confidence == 0.85
        assert result.tokens_used == 500

    @pytest.mark.asyncio
    async def test_validate_claim_api_error(self):
        """Test claim validation with API error"""
        provider = MiniMaxProvider("test-key")
        request = ValidationRequest(
            claim="Test claim",
            evidence={"test": "evidence"},
            claim_type="capability",
        )

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.validate_claim(request)

        assert result.confidence == 0.0
        assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_validate_claim_exception(self):
        """Test claim validation with exception"""
        provider = MiniMaxProvider("test-key")
        request = ValidationRequest(
            claim="Test claim",
            evidence={"test": "evidence"},
            claim_type="capability",
        )

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", side_effect=Exception("Connection failed")):
            result = await provider.validate_claim(request)

        assert result.confidence == 0.0
        assert result.provider == "MiniMax"


class TestEvidenceAnalysis:
    """Test evidence analysis with MiniMax"""

    @pytest.mark.asyncio
    async def test_analyze_evidence_success(self):
        """Test successful evidence analysis"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Evidence Strength: STRONG\nConfidence Score: 90%"}}],
            "usage": {"total_tokens": 400},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.analyze_evidence({"key": "value"}, "Test claim")

        assert isinstance(result, LLMResponse)
        assert result.provider == "MiniMax"
        assert result.tokens_used == 400

    @pytest.mark.asyncio
    async def test_analyze_evidence_error(self):
        """Test evidence analysis with error"""
        provider = MiniMaxProvider("test-key")

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", side_effect=Exception("API error")):
            result = await provider.analyze_evidence({"key": "value"}, "Test claim")

        assert result.confidence == 0.0


class TestBiasCheck:
    """Test bias checking with MiniMax"""

    @pytest.mark.asyncio
    async def test_check_bias_success(self):
        """Test successful bias check"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Bias Detected: NO\nObjectivity Score: 92%\nConfidence: 88%"}}],
            "usage": {"total_tokens": 300},
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.check_bias("Some text to analyze")

        assert isinstance(result, LLMResponse)
        assert result.provider == "MiniMax"

    @pytest.mark.asyncio
    async def test_check_bias_api_failure(self):
        """Test bias check with API failure"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 503
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.check_bias("Some text")

        assert result.confidence == 0.0


class TestConfidenceExtraction:
    """Test confidence score extraction from responses"""

    def test_extract_confidence_percentage(self):
        """Test extracting confidence from percentage format"""
        provider = MiniMaxProvider("test-key")
        assert provider.extract_confidence("Confidence: 85%") == 0.85

    def test_extract_confidence_objectivity(self):
        """Test extracting objectivity score as confidence"""
        provider = MiniMaxProvider("test-key")
        assert provider.extract_confidence("Objectivity Score: 92%") == 0.92

    def test_extract_confidence_long_content(self):
        """Test default confidence for long content"""
        provider = MiniMaxProvider("test-key")
        long_text = "A" * 600
        assert provider.extract_confidence(long_text) == 0.8

    def test_extract_confidence_short_content(self):
        """Test default confidence for short content"""
        provider = MiniMaxProvider("test-key")
        assert provider.extract_confidence("Short") == 0.4


class TestHealthCheck:
    """Test MiniMax provider health check"""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        provider = MiniMaxProvider("test-key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", return_value=mock_session):
            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with connection error"""
        provider = MiniMaxProvider("test-key")

        with patch("independent_ai_validator.providers.minimax_provider.aiohttp.ClientSession", side_effect=Exception("Connection refused")):
            result = await provider.health_check()
            assert result is False


class TestProviderTemperatureClamping:
    """Test temperature clamping in provider"""

    def test_clamp_zero(self):
        """Test temperature=0 clamped to 0.01"""
        assert _clamp_temperature(0.0) == 0.01

    def test_clamp_valid(self):
        """Test valid temperature passes through"""
        assert _clamp_temperature(0.5) == 0.5
        assert _clamp_temperature(1.0) == 1.0


class TestValidatorEngineIntegration:
    """Test MiniMax is properly wired into the validator engine"""

    def test_minimax_provider_importable(self):
        """Test MiniMaxProvider is importable from providers package"""
        from independent_ai_validator.providers import MiniMaxProvider
        assert MiniMaxProvider is not None

    def test_minimax_in_all_exports(self):
        """Test MiniMaxProvider is in __all__"""
        from independent_ai_validator.providers import __all__
        assert "MiniMaxProvider" in __all__

    def test_minimax_provider_weight_configured(self):
        """Test MiniMax weight is set in validator engine"""
        from independent_ai_validator.core.validator_engine import IndependentAIValidator
        validator = IndependentAIValidator(credential_manager=MagicMock())
        assert "minimax" in validator.provider_weights
        assert validator.provider_weights["minimax"] == 0.8

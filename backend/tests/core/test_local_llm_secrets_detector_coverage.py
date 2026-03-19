"""
Comprehensive tests for Local LLM Secrets Detector

Target: 60%+ coverage for core/local_llm_secrets_detector.py (348 lines)
Focus: LLM-based secrets detection, pattern fallback, Ollama integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from core.local_llm_secrets_detector import (
    LocalLLMProvider,
    LocalLLMSecretsDetector,
    SecretsAnalysis,
    get_local_secrets_detector,
    analyze_for_secrets,
    is_ollama_available,
)


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client."""
    with patch("core.local_llm_secrets_detector.ollama.Client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_secrets_redactor():
    """Mock SecretsRedactor for pattern-based fallback."""
    with patch("core.local_llm_secrets_detector.get_secrets_redactor") as mock:
        redactor = MagicMock()
        mock.return_value = redactor
        yield redactor


@pytest.fixture
def detector_with_ollama():
    """Create detector with Ollama client."""
    detector = LocalLLMSecretsDetector(
        provider=LocalLLMProvider.OLLAMA,
        model="llama3.2:1b",
        fallback_to_pattern=True
    )
    detector._client = MagicMock()
    detector._available_models = ["llama3.2:1b", "phi3:mini"]
    return detector


@pytest.fixture
def detector_without_fallback():
    """Create detector without pattern fallback."""
    detector = LocalLLMSecretsDetector(
        provider=LocalLLMProvider.OLLAMA,
        fallback_to_pattern=False
    )
    return detector


@pytest.fixture
def sample_secrets_text():
    """Sample text containing secrets."""
    return """
    API Key: sk-1234567890abcdef
    Password: mySecretPassword123
    Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
    """


@pytest.fixture
def sample_clean_text():
    """Sample text without secrets."""
    return """
    This is a simple text with no sensitive information.
    It contains regular words and sentences.
    """


# ========================================================================
# Test Class 1: LocalLLMProvider Enum
# ========================================================================


class TestLocalLLMProvider:
    """Test LocalLLMProvider enum values."""

    def test_provider_enum_values(self):
        """Test that provider enum has correct values."""
        assert LocalLLMProvider.OLLAMA == "ollama"
        assert LocalLLMProvider.LLAMACPP == "llamacpp"
        assert LocalLLMProvider.HUGGINGFACE == "huggingface"

    def test_provider_enum_is_string(self):
        """Test that provider enum values are strings."""
        assert isinstance(LocalLLMProvider.OLLAMA, str)
        assert isinstance(LocalLLMProvider.LLAMACPP, str)
        assert isinstance(LocalLLMProvider.HUGGINGFACE, str)


# ========================================================================
# Test Class 2: SecretsAnalysis Dataclass
# ========================================================================


class TestSecretsAnalysis:
    """Test SecretsAnalysis dataclass."""

    def test_secrets_analysis_creation(self):
        """Test creating SecretsAnalysis instance."""
        analysis = SecretsAnalysis(
            text_preview="Sample text...",
            has_secrets=True,
            confidence=0.95,
            detected_secrets=[{"type": "api_key", "snippet": "sk-12345..."}],
            analysis_method="local_llm",
            llm_model="llama3.2:1b",
            processing_time_ms=150.5
        )

        assert analysis.text_preview == "Sample text..."
        assert analysis.has_secrets is True
        assert analysis.confidence == 0.95
        assert len(analysis.detected_secrets) == 1
        assert analysis.analysis_method == "local_llm"
        assert analysis.llm_model == "llama3.2:1b"
        assert analysis.processing_time_ms == 150.5

    def test_secrets_analysis_with_optional_fields(self):
        """Test creating SecretsAnalysis with optional fields."""
        analysis = SecretsAnalysis(
            text_preview="Text...",
            has_secrets=False,
            confidence=0.9,
            detected_secrets=[],
            analysis_method="pattern"
        )

        assert analysis.llm_model is None
        assert analysis.processing_time_ms is None


# ========================================================================
# Test Class 3: LocalLLMSecretsDetector - Initialization
# ========================================================================


class TestDetectorInitialization:
    """Test detector initialization."""

    def test_detector_initialization_with_defaults(self):
        """Test detector initialization with default values."""
        detector = LocalLLMSecretsDetector()

        assert detector.provider == LocalLLMProvider.OLLAMA
        assert detector.model is None
        assert detector.ollama_host == "http://localhost:11434"
        assert detector.timeout_seconds == 30
        assert detector.fallback_to_pattern is True
        assert detector._client is None
        assert len(detector._available_models) == 0

    def test_detector_initialization_with_custom_values(self):
        """Test detector initialization with custom values."""
        detector = LocalLLMSecretsDetector(
            provider=LocalLLMProvider.OLLAMA,
            model="phi3:mini",
            ollama_host="http://localhost:8080",
            timeout_seconds=60,
            fallback_to_pattern=False
        )

        assert detector.model == "phi3:mini"
        assert detector.ollama_host == "http://localhost:8080"
        assert detector.timeout_seconds == 60
        assert detector.fallback_to_pattern is False

    def test_detector_with_pattern_redactor(self, mock_secrets_redactor):
        """Test detector initialization loads pattern redactor."""
        detector = LocalLLMSecretsDetector()

        assert detector.pattern_redactor is not None

    def test_detector_without_pattern_redactor(self):
        """Test detector when pattern redactor import fails."""
        with patch("core.local_llm_secrets_detector.get_secrets_redactor") as mock:
            mock.side_effect = ImportError("No module named 'core.secrets_redactor'")

            detector = LocalLLMSecretsDetector()

            assert detector.pattern_redactor is None


# ========================================================================
# Test Class 4: Ollama Initialization
# ========================================================================


class TestOllamaInitialization:
    """Test Ollama client initialization."""

    @pytest.mark.asyncio
    async def test_initialize_ollama_success(self, mock_ollama_client):
        """Test successful Ollama initialization."""
        mock_ollama_client.list.return_value = {
            "models": [
                {"name": "llama3.2:1b"},
                {"name": "phi3:mini"}
            ]
        }

        detector = LocalLLMSecretsDetector(model="llama3.2:1b")
        result = await detector.initialize()

        assert result is True
        assert detector._client is not None
        assert "llama3.2:1b" in detector._available_models
        assert detector.model == "llama3.2:1b"

    @pytest.mark.asyncio
    async def test_initialize_ollama_auto_select_model(self, mock_ollama_client):
        """Test Ollama initialization with auto model selection."""
        mock_ollama_client.list.return_value = {
            "models": [
                {"name": "llama3.2:1b"},
                {"name": "phi3:mini"}
            ]
        }

        detector = LocalLLMSecretsDetector()  # No model specified
        result = await detector.initialize()

        assert result is True
        # Should auto-select first recommended model
        assert detector.model is not None

    @pytest.mark.asyncio
    async def test_initialize_ollama_no_models(self, mock_ollama_client):
        """Test Ollama initialization when no models available."""
        mock_ollama_client.list.return_value = {"models": []}

        detector = LocalLLMSecretsDetector()
        result = await detector.initialize()

        assert result is False
        assert detector.model is None

    @pytest.mark.asyncio
    async def test_initialize_ollama_import_error(self):
        """Test Ollama initialization when ollama not installed."""
        with patch("core.local_llm_secrets_detector.ollama.Client") as mock:
            mock.side_effect = ImportError("No module named 'ollama'")

            detector = LocalLLMSecretsDetector()
            result = await detector.initialize()

            assert result is False

    @pytest.mark.asyncio
    async def test_initialize_ollama_connection_error(self, mock_ollama_client):
        """Test Ollama initialization with connection error."""
        mock_ollama_client.list.side_effect = Exception("Connection refused")

        detector = LocalLLMSecretsDetector()
        result = await detector.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_unsupported_provider(self):
        """Test initialization with unsupported provider."""
        detector = LocalLLMSecretsDetector(
            provider=LocalLLMProvider.LLAMACPP
        )

        result = await detector.initialize()

        assert result is False


# ========================================================================
# Test Class 5: Model Selection
# ========================================================================


class TestModelSelection:
    """Test model selection logic."""

    def test_select_best_model_from_recommended(self):
        """Test selecting best model from recommended list."""
        detector = LocalLLMSecretsDetector()
        detector._available_models = [
            "llama3.2:1b",
            "phi3:mini",
            "mistral:7b",
            "custom-model:v1"
        ]

        model = detector._select_best_model()

        # Should select first recommended model
        assert "llama3.2" in model

    def test_select_best_model_no_models(self):
        """Test model selection when no models available."""
        detector = LocalLLMSecretsDetector()
        detector._available_models = []

        model = detector._select_best_model()

        assert model is None

    def test_select_best_model_non_recommended(self):
        """Test model selection when only non-recommended models available."""
        detector = LocalLLMSecretsDetector()
        detector._available_models = ["custom-model:v1", "another-model:v2"]

        model = detector._select_best_model()

        # Should fallback to first available
        assert model == "custom-model:v1"

    def test_set_model_success(self):
        """Test setting model successfully."""
        detector = LocalLLMSecretsDetector()
        detector._available_models = ["llama3.2:1b", "phi3:mini"]

        result = detector.set_model("phi3:mini")

        assert result is True
        assert detector.model == "phi3:mini"

    def test_set_model_not_available(self):
        """Test setting model that's not available."""
        detector = LocalLLMSecretsDetector()
        detector._available_models = ["llama3.2:1b"]

        result = detector.set_model("nonexistent:model")

        assert result is False


# ========================================================================
# Test Class 6: LLM-Based Detection
# ========================================================================


class TestLLMBasedDetection:
    """Test LLM-based secrets detection."""

    @pytest.mark.asyncio
    async def test_llm_detect_secrets_success(self, detector_with_ollama):
        """Test successful LLM secrets detection."""
        # Mock LLM response
        mock_response = {
            "message": {
                "content": '''{"has_secrets": true, "confidence": 0.95, "secrets": [
                    {"type": "api_key", "snippet": "sk-123456...", "reason": "Matches API key pattern"}
                ]}'''
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("API key: sk-1234567890")

        assert result.has_secrets is True
        assert result.confidence == 0.95
        assert len(result.detected_secrets) == 1
        assert result.analysis_method == "local_llm"

    @pytest.mark.asyncio
    async def test_llm_detect_no_secrets(self, detector_with_ollama):
        """Test LLM detection finds no secrets."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.95, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("This is clean text")

        assert result.has_secrets is False
        assert result.confidence == 0.95
        assert len(result.detected_secrets) == 0

    @pytest.mark.asyncio
    async def test_llm_detect_with_json_in_markdown(
        self, detector_with_ollama
    ):
        """Test LLM detection when response is wrapped in markdown."""
        mock_response = {
            "message": {
                "content": '''```json
                {"has_secrets": true, "confidence": 0.9, "secrets": []}
                ```'''
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("Test text")

        assert result.has_secrets is True

    @pytest.mark.asyncio
    async def test_llm_detect_json_parse_error(self, detector_with_ollama):
        """Test LLM detection when JSON parsing fails."""
        mock_response = {
            "message": {
                "content": "This is not valid JSON but mentions a password"
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("Test text")

        # Should still detect based on keyword analysis
        assert result.has_secrets is True
        assert result.confidence == 0.3
        assert result.analysis_method == "local_llm_unparsed"

    @pytest.mark.asyncio
    async def test_llm_detect_exception(self, detector_with_ollama):
        """Test LLM detection when exception occurs."""
        detector_with_ollama._client.chat.side_effect = Exception("LLM error")

        result = await detector_with_ollama._llm_detect("Test text")

        # Should raise exception (handled by caller)
        with pytest.raises(Exception):
            await detector_with_ollama._llm_detect("Test text")


# ========================================================================
# Test Class 7: Pattern-Based Detection
# ========================================================================


class TestPatternBasedDetection:
    """Test pattern-based fallback detection."""

    @pytest.mark.asyncio
    async def test_pattern_detect_with_secrets(self, mock_secrets_redactor):
        """Test pattern detection finds secrets."""
        mock_result = MagicMock()
        mock_result.has_secrets = True
        mock_result.redactions = [
            {"type": "api_key", "matched_pattern": "sk-1234567890"}
        ]
        mock_secrets_redactor.redact.return_value = mock_result

        detector = LocalLLMSecretsDetector()
        result = detector._pattern_detect(
            "API key: sk-1234567890",
            "API key:...",
            0
        )

        assert result.has_secrets is True
        assert result.confidence == 0.85
        assert len(result.detected_secrets) == 1
        assert result.analysis_method == "fallback_pattern"

    @pytest.mark.asyncio
    async def test_pattern_detect_no_secrets(self, mock_secrets_redactor):
        """Test pattern detection finds no secrets."""
        mock_result = MagicMock()
        mock_result.has_secrets = False
        mock_result.redactions = []
        mock_secrets_redactor.redact.return_value = mock_result

        detector = LocalLLMSecretsDetector()
        result = detector._pattern_detect(
            "Clean text",
            "Clean text",
            0
        )

        assert result.has_secrets is False
        assert result.confidence == 0.9
        assert len(result.detected_secrets) == 0

    @pytest.mark.asyncio
    async def test_pattern_detect_no_redactor(self):
        """Test pattern detection when redactor unavailable."""
        detector = LocalLLMSecretsDetector()
        detector.pattern_redactor = None

        result = detector._pattern_detect(
            "Text",
            "Text...",
            0
        )

        assert result.has_secrets is False
        assert result.analysis_method == "fallback_unavailable"


# ========================================================================
# Test Class 8: Text Analysis
# ========================================================================


class TestTextAnalysis:
    """Test main analyze_text method."""

    @pytest.mark.asyncio
    async def test_analyze_text_with_llm(self, detector_with_ollama):
        """Test analyze_text using LLM detection."""
        # Mock LLM response
        mock_response = {
            "message": {
                "content": '{"has_secrets": true, "confidence": 0.95, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        text = "API key: sk-1234567890" * 100  # Long text
        result = await detector_with_ollama.analyze_text(text)

        assert result.has_secrets is True
        assert result.analysis_method == "local_llm"
        assert result.processing_time_ms is not None
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_analyze_text_fallback_to_pattern(
        self, detector_with_ollama, mock_secrets_redactor
    ):
        """Test analyze_text falls back to pattern on LLM failure."""
        # Make LLM fail
        detector_with_ollama._client.chat.side_effect = Exception("LLM error")

        # Mock pattern redactor
        mock_result = MagicMock()
        mock_result.has_secrets = True
        mock_result.redactions = []
        mock_secrets_redactor.redact.return_value = mock_result

        result = await detector_with_ollama.analyze_text("API key: sk-1234567890")

        assert result.has_secrets is True
        assert result.analysis_method == "fallback_pattern"

    @pytest.mark.asyncio
    async def test_analyze_text_no_detection_available(
        self, detector_without_fallback
    ):
        """Test analyze_text when no detection method available."""
        detector_without_fallback._client = None
        detector_without_fallback.pattern_redactor = None

        result = await detector_without_fallback.analyze_text("Some text")

        assert result.has_secrets is False
        assert result.analysis_method == "none"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_text_truncates_long_text(self, detector_with_ollama):
        """Test that analyze_text truncates very long text."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.9, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        # Create text longer than max_chars
        long_text = "x" * 5000
        result = await detector_with_ollama.analyze_text(long_text, max_chars=1000)

        assert result.has_secrets is False
        # Verify LLM was called with truncated text
        call_args = detector_with_ollama._client.chat.call_args
        assert len(call_args[1]["messages"][0]["content"]) <= 2000  # Approx

    @pytest.mark.asyncio
    async def test_analyze_text_generates_preview(self, detector_with_ollama):
        """Test that analyze_text generates text preview."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.9, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        long_text = "x" * 200
        result = await detector_with_ollama.analyze_text(long_text)

        assert result.text_preview is not None
        assert "..." in result.text_preview  # Truncated preview


# ========================================================================
# Test Class 9: Global Functions
# ========================================================================


class TestGlobalFunctions:
    """Test global convenience functions."""

    @pytest.mark.asyncio
    async def test_get_local_secrets_detector_singleton(self):
        """Test that get_local_secrets_detector returns singleton."""
        from core.local_llm_secrets_detector import _local_detector

        # Reset global state
        _local_detector = None

        detector1 = await get_local_secrets_detector()
        detector2 = await get_local_secrets_detector()

        assert detector1 is detector2

    @pytest.mark.asyncio
    async def test_analyze_for_secrets_convenience(self):
        """Test analyze_for_secrets convenience function."""
        with patch("core.local_llm_secrets_detector.get_local_secrets_detector") as mock:
            mock_detector = AsyncMock()
            mock_result = SecretsAnalysis(
                text_preview="...",
                has_secrets=False,
                confidence=0.9,
                detected_secrets=[],
                analysis_method="none"
            )
            mock_detector.analyze_text.return_value = mock_result
            mock.return_value = mock_detector

            result = await analyze_for_secrets("Test text")

            assert result.has_secrets is False
            mock_detector.analyze_text.assert_called_once_with("Test text")

    def test_is_ollama_available_true(self):
        """Test is_ollama_available when Ollama is available."""
        with patch("core.local_llm_secrets_detector.ollama.Client") as mock:
            mock_client = MagicMock()
            mock_client.list.return_value = {"models": [{"name": "llama3.2:1b"}]}
            mock.return_value = mock_client

            result = is_ollama_available()

            assert result is True

    def test_is_ollama_available_false_no_models(self):
        """Test is_ollama_available when no models."""
        with patch("core.local_llm_secrets_detector.ollama.Client") as mock:
            mock_client = MagicMock()
            mock_client.list.return_value = {"models": []}
            mock.return_value = mock_client

            result = is_ollama_available()

            assert result is False

    def test_is_ollama_available_false_import_error(self):
        """Test is_ollama_available when ollama not installed."""
        with patch("core.local_llm_secrets_detector.ollama.Client") as mock:
            mock.side_effect = ImportError("No module named 'ollama'")

            result = is_ollama_available()

            assert result is False


# ========================================================================
# Test Class 10: Edge Cases
# ========================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_analyze_empty_text(self, detector_with_ollama):
        """Test analyzing empty text."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.9, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama.analyze_text("")

        assert result.has_secrets is False

    @pytest.mark.asyncio
    async def test_analyze_text_with_special_characters(
        self, detector_with_ollama
    ):
        """Test analyzing text with special characters."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.9, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        text = "Text with émojis 🚨 and spëcial çharacters"
        result = await detector_with_ollama.analyze_text(text)

        assert result.has_secrets is False

    @pytest.mark.asyncio
    async def test_llm_detect_malformed_json(self, detector_with_ollama):
        """Test LLM detection with malformed JSON response."""
        mock_response = {
            "message": {
                "content": '{"has_secrets": true, "confidence": 0.8'  # Missing closing brace
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("Test text")

        # Should handle gracefully
        assert result.analysis_method == "local_llm_unparsed"

    @pytest.mark.asyncio
    async def test_multiple_secrets_detected(self, detector_with_ollama):
        """Test detecting multiple types of secrets."""
        mock_response = {
            "message": {
                "content": '''{"has_secrets": true, "confidence": 0.95, "secrets": [
                    {"type": "api_key", "snippet": "sk-123456...", "reason": "API key pattern"},
                    {"type": "password", "snippet": "pass123...", "reason": "Password field"}
                ]}'''
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        result = await detector_with_ollama._llm_detect("Multiple secrets here")

        assert len(result.detected_secrets) == 2


# ========================================================================
# Test Class 11: Performance
# ========================================================================


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_analyze_text_performance(self, detector_with_ollama):
        """Test that analyze_text completes in reasonable time."""
        import time

        mock_response = {
            "message": {
                "content": '{"has_secrets": false, "confidence": 0.9, "secrets": []}'
            }
        }
        detector_with_ollama._client.chat.return_value = mock_response

        start = time.time()
        await detector_with_ollama.analyze_text("Test text" * 100)
        duration = time.time() - start

        # Should complete quickly (mocked LLM)
        assert duration < 1.0

    @pytest.mark.asyncio
    async def test_pattern_detect_performance(self, mock_secrets_redactor):
        """Test pattern detection performance."""
        import time

        mock_result = MagicMock()
        mock_result.has_secrets = False
        mock_result.redactions = []
        mock_secrets_redactor.redact.return_value = mock_result

        detector = LocalLLMSecretsDetector()

        start = time.time()
        for _ in range(100):
            detector._pattern_detect("Test text", "Preview", 0)
        duration = time.time() - start

        # Should process 100 detections quickly
        assert duration < 1.0


# ========================================================================
# Test Class 12: Configuration
# ========================================================================


class TestConfiguration:
    """Test detector configuration and options."""

    def test_recommended_models_list(self):
        """Test that recommended models list is populated."""
        detector = LocalLLMSecretsDetector()

        assert len(detector.RECOMMENDED_MODELS) > 0
        assert "llama3.2:1b" in detector.RECOMMENDED_MODELS
        assert "phi3:mini" in detector.RECOMMENDED_MODELS

    def test_detection_prompt_template(self):
        """Test that detection prompt template exists."""
        detector = LocalLLMSecretsDetector()

        assert "secrets" in detector.DETECTION_PROMPT.lower()
        assert "api key" in detector.DETECTION_PROMPT.lower()
        assert "password" in detector.DETECTION_PROMPT.lower()

    def test_detector_timeout_configuration(self):
        """Test detector timeout configuration."""
        detector = LocalLLMSecretsDetector(timeout_seconds=120)

        assert detector.timeout_seconds == 120

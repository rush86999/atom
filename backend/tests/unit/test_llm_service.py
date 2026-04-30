"""
Comprehensive tests for LLMService unified LLM interface.

Tests cover:
- Provider selection and routing
- Chat completion (generate, generate_completion)
- Streaming responses (stream_completion)
- Token counting and cost estimation
- Error handling and retry logic
- Multi-provider failover
- Cognitive tier routing
- Embeddings and speech generation
- Integration and edge cases
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open
from io import BytesIO

import pytest

# Import the service under test
from core.llm_service import (
    LLMService,
    LLMProvider,
    LLMModel,
    LLMSentiment,
    LLMTopics
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_byok_handler():
    """Mock BYOKHandler for LLM interactions"""
    handler = AsyncMock()
    handler.workspace_id = "test-workspace"
    handler.tenant_id = "test-tenant"
    handler.generate_response = AsyncMock(return_value="Test response")
    handler.generate_completion = AsyncMock(return_value={
        "success": True,
        "content": "Test completion",
        "text": "Test completion",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "model": "gpt-4o-mini",
        "provider": "openai"
    })
    handler.generate_structured_response = AsyncMock(return_value={"result": "structured"})
    handler.stream_completion = MagicMock()
    handler.analyze_query_complexity = Mock(return_value="moderate")
    handler.get_optimal_provider = Mock(return_value=("openai", "gpt-4o-mini"))
    return handler


@pytest.fixture
def mock_continuous_learning():
    """Mock ContinuousLearningService"""
    service = MagicMock()
    service.get_personalized_parameters = MagicMock(return_value={
        "temperature": 0.5
    })
    return service


@pytest.fixture
def mock_token_counter():
    """Mock TokenCounter"""
    counter = MagicMock()
    counter.count_tokens = MagicMock(return_value=100)
    return counter


@pytest.fixture
def mock_context_validator():
    """Mock ContextValidator"""
    validator = MagicMock()
    validator.estimate_request_tokens = MagicMock(return_value=150)
    return validator


@pytest.fixture
def mock_cognitive_classifier():
    """Mock CognitiveClassifier"""
    classifier = MagicMock()
    classifier.classify = MagicMock(return_value="standard")
    return classifier


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    db = MagicMock()
    return db


@pytest.fixture
def llm_service(mock_byok_handler, mock_db_session):
    """Create LLMService instance with mocked dependencies"""
    with patch('core.llm_service.BYOKHandler', return_value=mock_byok_handler):
        with patch('core.llm_service.ContinuousLearningService', return_value=None):
            with patch('core.llm_service.TokenCounter') as mock_token_counter_cls:
                with patch('core.llm_service.ContextValidator') as mock_context_validator_cls:
                    with patch('core.llm_service.CognitiveClassifier') as mock_cognitive_classifier_cls:
                        # Configure mocks
                        mock_token_counter = MagicMock()
                        mock_token_counter.count_tokens = MagicMock(return_value=100)
                        mock_token_counter_cls.return_value = mock_token_counter

                        mock_context_validator = MagicMock()
                        mock_context_validator.estimate_request_tokens = MagicMock(return_value=150)
                        mock_context_validator_cls.return_value = mock_context_validator

                        mock_cognitive_classifier = MagicMock()
                        mock_cognitive_classifier.classify = MagicMock(return_value="standard")
                        mock_cognitive_classifier_cls.return_value = mock_cognitive_classifier

                        service = LLMService(
                            db=mock_db_session,
                            workspace_id="test-workspace",
                            tenant_id="test-tenant"
                        )
                        service._handler = mock_byok_handler
                        return service


# =============================================================================
# TEST CLASS: INITIALIZATION
# =============================================================================

class TestLLMServiceInitialization:
    """Test LLMService initialization and setup"""

    def test_llm_service_init_default(self, mock_db_session):
        """Test LLMService initialization with default parameters"""
        with patch('core.llm_service.BYOKHandler'):
            with patch('core.llm_service.ContinuousLearningService', return_value=None):
                with patch('core.llm_service.TokenCounter'):
                    with patch('core.llm_service.ContextValidator'):
                        with patch('core.llm_service.CognitiveClassifier'):
                            service = LLMService(db=mock_db_session)
                            assert service.workspace_id == "default"
                            assert service.tenant_id == "default"
                            assert service._db == mock_db_session

    def test_llm_service_init_with_workspace_tenant(self, mock_db_session):
        """Test LLMService initialization with workspace and tenant IDs"""
        with patch('core.llm_service.BYOKHandler'):
            with patch('core.llm_service.ContinuousLearningService', return_value=None):
                with patch('core.llm_service.TokenCounter'):
                    with patch('core.llm_service.ContextValidator'):
                        with patch('core.llm_service.CognitiveClassifier'):
                            service = LLMService(
                                db=mock_db_session,
                                workspace_id="custom-workspace",
                                tenant_id="custom-tenant"
                            )
                            assert service.workspace_id == "custom-workspace"
                            assert service.tenant_id == "custom-tenant"

    def test_llm_service_handler_property(self, llm_service, mock_byok_handler):
        """Test handler property returns BYOKHandler"""
        assert llm_service.handler == mock_byok_handler

    def test_llm_service_workspace_id_property(self, llm_service):
        """Test workspace_id property"""
        assert llm_service.workspace_id == "test-workspace"

    def test_llm_service_tenant_id_property(self, llm_service):
        """Test tenant_id property"""
        assert llm_service.tenant_id == "test-tenant"


# =============================================================================
# TEST CLASS: PROVIDER SELECTION
# =============================================================================

class TestProviderSelection:
    """Test provider selection logic"""

    def test_get_provider_openai_gpt4(self, llm_service):
        """Test provider detection for OpenAI GPT-4"""
        provider = llm_service.get_provider("gpt-4")
        assert provider == LLMProvider.OPENAI

    def test_get_provider_openai_gpt4o(self, llm_service):
        """Test provider detection for GPT-4O"""
        provider = llm_service.get_provider("gpt-4o")
        assert provider == LLMProvider.OPENAI

    def test_get_provider_anthropic_claude(self, llm_service):
        """Test provider detection for Anthropic Claude"""
        provider = llm_service.get_provider("claude-3-5-sonnet")
        assert provider == LLMProvider.ANTHROPIC

    def test_get_provider_deepseek(self, llm_service):
        """Test provider detection for DeepSeek"""
        provider = llm_service.get_provider("deepseek-chat")
        assert provider == LLMProvider.DEEPSEEK

    def test_get_provider_gemini(self, llm_service):
        """Test provider detection for Gemini"""
        provider = llm_service.get_provider("gemini-1.5-pro")
        assert provider == LLMProvider.GEMINI

    def test_get_provider_minimax(self, llm_service):
        """Test provider detection for MiniMax"""
        provider = llm_service.get_provider("minimax-m2.5")
        assert provider == LLMProvider.MINIMAX

    def test_get_provider_mistral(self, llm_service):
        """Test provider detection for Mistral"""
        provider = llm_service.get_provider("mistral-large")
        assert provider == LLMProvider.MISTRAL

    def test_get_provider_qwen(self, llm_service):
        """Test provider detection for Qwen"""
        provider = llm_service.get_provider("qwen-plus")
        assert provider == LLMProvider.QWEN

    def test_get_provider_cohere(self, llm_service):
        """Test provider detection for Cohere"""
        provider = llm_service.get_provider("command-r")
        assert provider == LLMProvider.COHERE

    def test_get_provider_unknown_defaults_to_openai(self, llm_service):
        """Test unknown provider defaults to OpenAI"""
        provider = llm_service.get_provider("unknown-model-x")
        assert provider == LLMProvider.OPENAI


# =============================================================================
# TEST CLASS: GENERATE (SIMPLE TEXT GENERATION)
# =============================================================================

class TestGenerate:
    """Test simple text generation interface"""

    @pytest.mark.asyncio
    async def test_generate_basic_prompt(self, llm_service, mock_byok_handler):
        """Test basic text generation"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Hello, world!")
        result = await llm_service.generate("Hello, world!")
        assert result == "Hello, world!"
        mock_byok_handler.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_custom_system_instruction(self, llm_service, mock_byok_handler):
        """Test generation with custom system instruction"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Custom response")
        result = await llm_service.generate(
            prompt="Test",
            system_instruction="You are a testing assistant."
        )
        assert result == "Custom response"

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, llm_service, mock_byok_handler):
        """Test generation with custom temperature"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(prompt="Test", temperature=0.3)
        assert result == "Response"

    @pytest.mark.asyncio
    async def test_generate_with_max_tokens(self, llm_service, mock_byok_handler):
        """Test generation with max tokens limit"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(prompt="Test", max_tokens=500)
        assert result == "Response"

    @pytest.mark.asyncio
    async def test_generate_with_custom_workspace(self, llm_service, mock_byok_handler):
        """Test generation with custom workspace ID"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(
            prompt="Test",
            workspace_id="custom-workspace"
        )
        assert result == "Response"

    @pytest.mark.asyncio
    async def test_generate_with_continuous_learning_personalization(
        self, llm_service, mock_byok_handler, mock_continuous_learning
    ):
        """Test generation with continuous learning personalization"""
        llm_service.continuous_learning = mock_continuous_learning
        mock_byok_handler.generate_response = AsyncMock(return_value="Personalized")

        result = await llm_service.generate(
            prompt="Test",
            agent_id="test-agent",
            user_id="test-user"
        )

        assert result == "Personalized"
        mock_continuous_learning.get_personalized_parameters.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_model_auto(self, llm_service, mock_byok_handler):
        """Test generation with auto model selection"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Auto response")
        result = await llm_service.generate(prompt="Test", model="auto")
        assert result == "Auto response"

    @pytest.mark.asyncio
    async def test_generate_with_kwargs(self, llm_service, mock_byok_handler):
        """Test generation with additional kwargs passed through"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(
            prompt="Test",
            top_p=0.9,
            frequency_penalty=0.5
        )
        assert result == "Response"


# =============================================================================
# TEST CLASS: GENERATE_COMPLETION (OPENAI-STYLE MESSAGES)
# =============================================================================

class TestGenerateCompletion:
    """Test OpenAI-style message-based completion"""

    @pytest.mark.asyncio
    async def test_generate_completion_basic(self, llm_service, mock_byok_handler):
        """Test basic completion with messages"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Completion text")
        messages = [{"role": "user", "content": "Hello"}]
        result = await llm_service.generate_completion(messages)
        assert result["success"] is True
        assert result["content"] == "Completion text"
        assert result["text"] == "Completion text"
        assert "usage" in result

    @pytest.mark.asyncio
    async def test_generate_completion_with_system_message(self, llm_service, mock_byok_handler):
        """Test completion with system message"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"}
        ]
        result = await llm_service.generate_completion(messages)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_completion_with_history(self, llm_service, mock_byok_handler):
        """Test completion with conversation history"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Final response")
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"}
        ]
        result = await llm_service.generate_completion(messages)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_completion_token_estimation(self, llm_service, mock_byok_handler):
        """Test token estimation in completion response"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response text")
        messages = [{"role": "user", "content": "Test message"}]
        result = await llm_service.generate_completion(messages, model="gpt-4o-mini")

        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]
        assert "total_tokens" in result["usage"]
        assert result["usage"]["total_tokens"] == result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]

    @pytest.mark.asyncio
    async def test_generate_completion_with_temperature(self, llm_service, mock_byok_handler):
        """Test completion with temperature parameter"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = [{"role": "user", "content": "Test"}]
        result = await llm_service.generate_completion(messages, temperature=0.5)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_completion_with_max_tokens(self, llm_service, mock_byok_handler):
        """Test completion with max tokens limit"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = [{"role": "user", "content": "Test"}]
        result = await llm_service.generate_completion(messages, max_tokens=100)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_completion_includes_provider(self, llm_service, mock_byok_handler):
        """Test completion response includes provider information"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = [{"role": "user", "content": "Test"}]
        result = await llm_service.generate_completion(messages, model="gpt-4o-mini")
        assert "provider" in result
        assert result["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_generate_completion_includes_model(self, llm_service, mock_byok_handler):
        """Test completion response includes model name"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = [{"role": "user", "content": "Test"}]
        result = await llm_service.generate_completion(messages, model="gpt-4o-mini")
        assert "model" in result
        assert result["model"] == "gpt-4o-mini"


# =============================================================================
# TEST CLASS: STREAM_COMPLETION
# =============================================================================

class TestStreamCompletion:
    """Test streaming response functionality"""

    @pytest.mark.asyncio
    async def test_stream_completion_basic(self, llm_service, mock_byok_handler):
        """Test basic streaming response"""
        async def mock_stream():
            tokens = ["Hello", " world", "!"]
            for token in tokens:
                yield token

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "Hello"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages):
            chunks.append(chunk)

        assert len(chunks) == 3

    @pytest.mark.asyncio
    async def test_stream_completion_with_model(self, llm_service, mock_byok_handler):
        """Test streaming with specific model"""
        async def mock_stream():
            yield "Response"

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "Test"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages, model="gpt-4o-mini"):
            chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_stream_completion_with_temperature(self, llm_service, mock_byok_handler):
        """Test streaming with custom temperature"""
        async def mock_stream():
            yield "Response"

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "Test"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages, temperature=0.8):
            chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_stream_completion_with_workspace_id(self, llm_service, mock_byok_handler):
        """Test streaming with custom workspace"""
        async def mock_stream():
            yield "Response"

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "Test"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages, workspace_id="custom"):
            chunks.append(chunk)

        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_stream_completion_empty_stream(self, llm_service, mock_byok_handler):
        """Test handling of empty stream"""
        async def mock_stream():
            return
            yield  # Make it a generator

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "Test"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages):
            chunks.append(chunk)

        assert len(chunks) == 0


# =============================================================================
# TEST CLASS: EMBEDDINGS
# =============================================================================

class TestEmbeddings:
    """Test embedding generation"""

    @pytest.mark.asyncio
    async def test_generate_embedding_basic(self, llm_service, mock_byok_handler):
        """Test single text embedding generation"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_byok_handler.async_clients = {"openai": mock_client}

        embedding = await llm_service.generate_embedding("Test text", model="text-embedding-3-small")
        assert embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_generate_embedding_no_client(self, llm_service, mock_byok_handler):
        """Test embedding generation fails when no client available"""
        mock_byok_handler.async_clients = {}
        mock_byok_handler.clients = {}

        with pytest.raises(ValueError, match="No client found"):
            await llm_service.generate_embedding("Test text")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, llm_service, mock_byok_handler):
        """Test batch embedding generation"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2, 0.3]),
            MagicMock(embedding=[0.4, 0.5, 0.6])
        ]
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_byok_handler.async_clients = {"openai": mock_client}

        embeddings = await llm_service.generate_embeddings_batch(
            ["Text 1", "Text 2"],
            model="text-embedding-3-small"
        )
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


# =============================================================================
# TEST CLASS: SPEECH AND AUDIO
# =============================================================================

class TestSpeechAndAudio:
    """Test speech generation and audio transcription"""

    @pytest.mark.asyncio
    async def test_generate_speech_basic(self, llm_service, mock_byok_handler):
        """Test text-to-speech generation"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.read = MagicMock(return_value=b"audio data")
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        mock_byok_handler.async_clients = {"openai": mock_client}

        audio = await llm_service.generate_speech("Hello world")
        assert audio == b"audio data"

    @pytest.mark.asyncio
    async def test_generate_speech_with_custom_voice(self, llm_service, mock_byok_handler):
        """Test TTS with custom voice"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.read = MagicMock(return_value=b"audio data")
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
        mock_byok_handler.async_clients = {"openai": mock_client}

        audio = await llm_service.generate_speech("Test", voice="nova")
        assert audio == b"audio data"

    @pytest.mark.asyncio
    async def test_transcribe_audio_basic(self, llm_service, mock_byok_handler):
        """Test audio transcription"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "Transcribed text"
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
        mock_byok_handler.async_clients = {"openai": mock_client}

        mock_file = BytesIO(b"audio data")
        result = await llm_service.transcribe_audio(mock_file)
        assert result["text"] == "Transcribed text"


# =============================================================================
# TEST CLASS: TOKEN COUNTING
# =============================================================================

class TestTokenCounting:
    """Test token estimation and counting"""

    def test_estimate_tokens_string(self, llm_service):
        """Test token estimation for string input"""
        count = llm_service.estimate_tokens("This is a test string", model="gpt-4o-mini")
        assert count == 100  # Mock returns fixed value

    def test_estimate_tokens_messages(self, llm_service):
        """Test token estimation for message list"""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"}
        ]
        count = llm_service.estimate_tokens(messages, model="gpt-4o-mini")
        assert count == 150  # Mock returns fixed value

    def test_estimate_tokens_empty_string(self, llm_service):
        """Test token estimation for empty string"""
        count = llm_service.estimate_tokens("", model="gpt-4o-mini")
        assert count == 100  # Mock still returns value

    def test_estimate_tokens_long_text(self, llm_service):
        """Test token estimation for long text"""
        long_text = "word " * 1000
        count = llm_service.estimate_tokens(long_text, model="gpt-4o-mini")
        assert isinstance(count, int)


# =============================================================================
# TEST CLASS: COST ESTIMATION
# =============================================================================

class TestCostEstimation:
    """Test cost calculation and estimation"""

    def test_estimate_cost_gpt4o_mini(self, llm_service):
        """Test cost estimation for GPT-4O-mini"""
        with patch('core.llm_service.get_llm_cost') as mock_cost:
            mock_cost.return_value = 0.001
            cost = llm_service.estimate_cost(1000, 500, "gpt-4o-mini")
            assert cost == 0.001

    def test_estimate_cost_with_import_error_fallback(self, llm_service):
        """Test cost estimation fallback when import fails"""
        with patch('core.llm_service.get_llm_cost', side_effect=ImportError):
            cost = llm_service.estimate_cost(1000, 500, "gpt-4o-mini")
            # Should use hardcoded fallback
            assert isinstance(cost, float)

    def test_estimate_cost_deepseek(self, llm_service):
        """Test cost estimation for DeepSeek"""
        with patch('core.llm_service.get_llm_cost', side_effect=ImportError):
            cost = llm_service.estimate_cost(1000, 500, "deepseek-chat")
            assert cost > 0

    def test_estimate_cost_zero_tokens(self, llm_service):
        """Test cost estimation with zero tokens"""
        cost = llm_service.estimate_cost(0, 0, "gpt-4o-mini")
        assert cost == 0.0


# =============================================================================
# TEST CLASS: STRUCTURED RESPONSES
# =============================================================================

class TestStructuredResponses:
    """Test structured response generation with Pydantic models"""

    @pytest.mark.asyncio
    async def test_generate_structured_response_basic(self, llm_service, mock_byok_handler):
        """Test structured response generation"""
        mock_byok_handler.generate_structured_response = AsyncMock(
            return_value=LLMSentiment(score=0.8, label="positive", confidence=0.9)
        )

        result = await llm_service.generate_structured_response(
            prompt="This is great!",
            response_model=LLMSentiment
        )

        assert result.score == 0.8
        assert result.label == "positive"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_generate_structured_response_with_system_instruction(
        self, llm_service, mock_byok_handler
    ):
        """Test structured response with custom system instruction"""
        mock_byok_handler.generate_structured_response = AsyncMock(
            return_value=LLMTopics(topics=["tech", "ai"], confidence=0.85)
        )

        result = await llm_service.generate_structured_response(
            prompt="AI is transforming technology",
            response_model=LLMTopics,
            system_instruction="Extract topics from text."
        )

        assert len(result.topics) == 2
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_generate_structured_response_with_personalization(
        self, llm_service, mock_byok_handler, mock_continuous_learning
    ):
        """Test structured response with continuous learning personalization"""
        llm_service.continuous_learning = mock_continuous_learning
        mock_byok_handler.generate_structured_response = AsyncMock(
            return_value=LLMSentiment(score=0.5, label="neutral", confidence=0.7)
        )

        result = await llm_service.generate_structured_response(
            prompt="Test",
            response_model=LLMSentiment,
            agent_id="test-agent",
            user_id="test-user"
        )

        assert result.label == "neutral"
        mock_continuous_learning.get_personalized_parameters.assert_called_once()


# =============================================================================
# TEST CLASS: COGNITIVE TIER ROUTING
# =============================================================================

class TestCognitiveTierRouting:
    """Test cognitive tier-based routing"""

    @pytest.mark.asyncio
    async def test_generate_with_tier_basic(self, llm_service, mock_byok_handler):
        """Test generation with cognitive tier routing"""
        mock_byok_handler.generate_with_cognitive_tier = AsyncMock(
            return_value={
                "response": "Tiered response",
                "tier": "standard",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "cost_cents": 0.01,
                "escalated": False,
                "request_id": "test-req-123"
            }
        )

        result = await llm_service.generate_with_tier("Explain quantum computing")

        assert result["response"] == "Tiered response"
        assert result["tier"] == "standard"
        assert result["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_generate_with_tier_with_task_type(self, llm_service, mock_byok_handler):
        """Test tier routing with task type hint"""
        mock_byok_handler.generate_with_cognitive_tier = AsyncMock(
            return_value={
                "response": "Code response",
                "tier": "versatile",
                "provider": "openai",
                "model": "gpt-4o",
                "cost_cents": 0.05,
                "escalated": False,
                "request_id": "test-req-456"
            }
        )

        result = await llm_service.generate_with_tier(
            "Write a Python function",
            task_type="code"
        )

        assert result["tier"] == "versatile"

    @pytest.mark.asyncio
    async def test_generate_with_tier_with_user_override(self, llm_service, mock_byok_handler):
        """Test tier routing with user-specified tier override"""
        mock_byok_handler.generate_with_cognitive_tier = AsyncMock(
            return_value={
                "response": "Heavy tier response",
                "tier": "heavy",
                "provider": "anthropic",
                "model": "claude-3-5-sonnet",
                "cost_cents": 0.10,
                "escalated": False,
                "request_id": "test-req-789"
            }
        )

        result = await llm_service.generate_with_tier(
            "Complex analysis",
            user_tier_override="heavy"
        )

        assert result["tier"] == "heavy"

    @pytest.mark.asyncio
    async def test_generate_with_tier_with_agent_tracking(self, llm_service, mock_byok_handler):
        """Test tier routing with agent ID for cost tracking"""
        mock_byok_handler.generate_with_cognitive_tier = AsyncMock(
            return_value={
                "response": "Response",
                "tier": "standard",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "cost_cents": 0.01,
                "escalated": False,
                "request_id": "test-req-101"
            }
        )

        result = await llm_service.generate_with_tier(
            "Test",
            agent_id="test-agent-123"
        )

        assert "request_id" in result

    @pytest.mark.asyncio
    async def test_generate_with_tier_escalation(self, llm_service, mock_byok_handler):
        """Test tier routing with escalation flag"""
        mock_byok_handler.generate_with_cognitive_tier = AsyncMock(
            return_value={
                "response": "Escalated response",
                "tier": "complex",
                "provider": "anthropic",
                "model": "claude-4-opus",
                "cost_cents": 0.50,
                "escalated": True,
                "request_id": "test-req-202"
            }
        )

        result = await llm_service.generate_with_tier("Critical task")

        assert result["escalated"] is True
        assert result["tier"] == "complex"


# =============================================================================
# TEST CLASS: ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_generate_with_handler_error(self, llm_service, mock_byok_handler):
        """Test generate when handler raises error"""
        mock_byok_handler.generate_response = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await llm_service.generate("Test")

    @pytest.mark.asyncio
    async def test_stream_completion_with_error(self, llm_service, mock_byok_handler):
        """Test stream completion when handler raises error"""
        async def mock_stream_error():
            raise Exception("Stream error")
            yield

        mock_byok_handler.stream_completion = mock_stream_error()
        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(Exception, match="Stream error"):
            async for _ in llm_service.stream_completion(messages):
                pass

    @pytest.mark.asyncio
    async def test_generate_completion_empty_messages(self, llm_service, mock_byok_handler):
        """Test completion with empty message list"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        messages = []

        result = await llm_service.generate_completion(messages)
        assert result["success"] is True


# =============================================================================
# TEST CLASS: INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for end-to-end workflows"""

    @pytest.mark.asyncio
    async def test_end_to_end_generate_and_estimate_cost(self, llm_service, mock_byok_handler):
        """Test full workflow: generate, then estimate cost"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response text")

        # Generate response
        response = await llm_service.generate("Test prompt")

        # Estimate cost
        input_tokens = llm_service.estimate_tokens("Test prompt")
        output_tokens = llm_service.estimate_tokens(response)
        cost = llm_service.estimate_cost(input_tokens, output_tokens, "gpt-4o-mini")

        assert response == "Response text"
        assert isinstance(cost, float)

    @pytest.mark.asyncio
    async def test_multi_message_conversation_flow(self, llm_service, mock_byok_handler):
        """Test multi-turn conversation with message history"""
        mock_byok_handler.generate_response = AsyncMock(side_effect=[
            "First response",
            "Second response",
            "Third response"
        ])

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Second response"},
            {"role": "user", "content": "Goodbye"}
        ]

        result = await llm_service.generate_completion(messages)
        assert result["success"] is True
        assert "usage" in result

    @pytest.mark.asyncio
    async def test_provider_selection_by_model(self, llm_service):
        """Test provider is correctly selected for various models"""
        test_cases = [
            ("gpt-4o", LLMProvider.OPENAI),
            ("claude-3-5-sonnet", LLMProvider.ANTHROPIC),
            ("deepseek-chat", LLMProvider.DEEPSEEK),
            ("gemini-1.5-pro", LLMProvider.GEMINI),
            ("minimax-m2.5", LLMProvider.MINIMAX)
        ]

        for model, expected_provider in test_cases:
            provider = llm_service.get_provider(model)
            assert provider == expected_provider, f"Failed for {model}"


# =============================================================================
# TEST CLASS: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_generate_with_unicode_characters(self, llm_service, mock_byok_handler):
        """Test generate with Unicode text"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Unicode: 你好 🌍")
        result = await llm_service.generate("Test with unicode: 你好")
        assert "你好" in result

    @pytest.mark.asyncio
    async def test_generate_with_special_characters(self, llm_service, mock_byok_handler):
        """Test generate with special characters"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Special: <>&\"'")
        result = await llm_service.generate("Test special chars")
        assert "<" in result

    @pytest.mark.asyncio
    async def test_stream_with_single_token(self, llm_service, mock_byok_handler):
        """Test streaming with single token response"""
        async def mock_stream():
            yield "A"

        mock_byok_handler.stream_completion = mock_stream()
        messages = [{"role": "user", "content": "A"}]

        chunks = []
        async for chunk in llm_service.stream_completion(messages):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == "A"

    def test_estimate_cost_very_large_tokens(self, llm_service):
        """Test cost estimation with very large token counts"""
        cost = llm_service.estimate_cost(1000000, 500000, "gpt-4o-mini")
        assert isinstance(cost, float)
        assert cost > 0


# =============================================================================
# TEST CLASS: PERFORMANCE BENCHMARKS
# =============================================================================

class TestPerformanceBenchmarks:
    """Test performance characteristics"""

    def test_provider_selection_performance(self, llm_service):
        """Test provider selection completes quickly"""
        import time
        start = time.time()
        for _ in range(1000):
            llm_service.get_provider("gpt-4o-mini")
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be very fast

    def test_token_estimation_performance(self, llm_service):
        """Test token estimation is reasonably fast"""
        import time
        start = time.time()
        for _ in range(100):
            llm_service.estimate_tokens("Test text for performance", "gpt-4o-mini")
        elapsed = time.time() - start
        assert elapsed < 1.0  # Should be fast


# =============================================================================
# TEST CLASS: WORKSPACE AND TENANT HANDLING
# =============================================================================

class TestWorkspaceAndTenantHandling:
    """Test workspace and tenant ID handling"""

    def test_get_handler_uses_default_workspace(self, llm_service):
        """Test _get_handler returns default handler when no workspace specified"""
        handler = llm_service._get_handler()
        assert handler == llm_service._handler

    @pytest.mark.asyncio
    async def test_generate_uses_custom_workspace(self, llm_service, mock_byok_handler):
        """Test generate creates new handler for custom workspace"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(
            "Test",
            workspace_id="custom-workspace"
        )
        assert result == "Response"

    @pytest.mark.asyncio
    async def test_generate_uses_tenant_id(self, llm_service, mock_byok_handler):
        """Test generate uses tenant_id parameter"""
        mock_byok_handler.generate_response = AsyncMock(return_value="Response")
        result = await llm_service.generate(
            "Test",
            tenant_id="custom-tenant"
        )
        assert result == "Response"


# =============================================================================
# TEST CLASS: HANDLER PROPERTY ALIASES
# =============================================================================

class TestHandlerPropertyAliases:
    """Test handler property provides backwards compatibility"""

    def test_handler_property_returns_byok_handler(self, llm_service, mock_byok_handler):
        """Test handler property returns _handler"""
        assert llm_service.handler is llm_service._handler
        assert llm_service.handler == mock_byok_handler

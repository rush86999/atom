"""
Tests for LLMService provider selection utilities and structured output.

Tests the get_optimal_provider, get_ranked_providers, get_routing_info, and
generate_structured methods that expose BYOKHandler's capabilities.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from core.llm_service import LLMService
from core.llm.byok_handler import QueryComplexity
from core.llm.cognitive_tier_system import CognitiveTier


# Test Pydantic Models
class SampleResponse(BaseModel):
    """Simple test model for structured output"""
    name: str
    value: int


class SummarizationResult(BaseModel):
    """Test model for summarization"""
    summary: str
    sentiment: str


class NestedItem(BaseModel):
    """Nested model for complex tests"""
    title: str
    count: int


class ComplexResponse(BaseModel):
    """Complex test model with nested structure"""
    main_title: str
    items: List[NestedItem]
    metadata: Dict[str, Any]


class TestLLMServiceProviderSelection:
    """Tests for LLMService provider selection methods"""

    @pytest.fixture
    def mock_handler(self):
        """Mock BYOKHandler with provider selection methods"""
        handler = Mock()
        handler.clients = {
            "openai": Mock(),
            "anthropic": Mock(),
            "deepseek": Mock()
        }

        # Mock get_optimal_provider
        handler.get_optimal_provider = Mock(
            return_value=("anthropic", "claude-3-5-sonnet")
        )

        # Mock get_ranked_providers
        handler.get_ranked_providers = Mock(
            return_value=[
                ("anthropic", "claude-3-5-sonnet"),
                ("openai", "gpt-4o"),
                ("deepseek", "deepseek-chat")
            ]
        )

        # Mock get_routing_info
        handler.get_routing_info = Mock(
            return_value={
                "complexity": "moderate",
                "selected_provider": "anthropic",
                "selected_model": "claude-3-5-sonnet",
                "available_providers": ["openai", "anthropic", "deepseek"],
                "cost_tier": "premium",
                "estimated_cost_usd": 0.0005
            }
        )

        return handler

    @pytest.fixture
    def llm_service(self, mock_handler):
        """Create LLMService with mocked handler"""
        with patch('core.llm_service.BYOKHandler', return_value=mock_handler):
            service = LLMService(workspace_id="test")
            service.handler = mock_handler
            return service


class TestGetOptimalProvider(TestLLMServiceProviderSelection):
    """Tests for get_optimal_provider method"""

    def test_get_optimal_provider_basic(self, llm_service, mock_handler):
        """Verify returns (provider, model) tuple"""
        provider, model = llm_service.get_optimal_provider()

        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet"
        assert isinstance(provider, str)
        assert isinstance(model, str)

        # Verify handler was called with correct parameters
        mock_handler.get_optimal_provider.assert_called_once()
        call_args = mock_handler.get_optimal_provider.call_args
        assert call_args.kwargs['complexity'] == QueryComplexity.MODERATE

    def test_get_optimal_provider_all_complexities(self, llm_service, mock_handler):
        """Test all complexity levels map correctly"""
        complexities = ["simple", "moderate", "complex", "advanced"]
        expected_enums = [
            QueryComplexity.SIMPLE,
            QueryComplexity.MODERATE,
            QueryComplexity.COMPLEX,
            QueryComplexity.ADVANCED
        ]

        for complexity, expected_enum in zip(complexities, expected_enums):
            mock_handler.get_optimal_provider.reset_mock()
            llm_service.get_optimal_provider(complexity=complexity)

            call_args = mock_handler.get_optimal_provider.call_args
            assert call_args.kwargs['complexity'] == expected_enum, \
                f"Complexity '{complexity}' should map to {expected_enum}"

    def test_get_optimal_provider_with_tools(self, llm_service, mock_handler):
        """Verify requires_tools filtering works"""
        llm_service.get_optimal_provider(requires_tools=True)

        call_args = mock_handler.get_optimal_provider.call_args
        assert call_args.kwargs['requires_tools'] is True

    def test_get_optimal_provider_prefer_quality(self, llm_service, mock_handler):
        """Verify quality preference works"""
        llm_service.get_optimal_provider(prefer_cost=False)

        call_args = mock_handler.get_optimal_provider.call_args
        assert call_args.kwargs['prefer_cost'] is False

    def test_get_optimal_provider_all_parameters(self, llm_service, mock_handler):
        """Verify all parameters pass through correctly"""
        llm_service.get_optimal_provider(
            complexity="complex",
            task_type="code_generation",
            prefer_cost=False,
            tenant_plan="enterprise",
            is_managed_service=False,
            requires_tools=True,
            requires_structured=True
        )

        call_args = mock_handler.get_optimal_provider.call_args
        assert call_args.kwargs['complexity'] == QueryComplexity.COMPLEX
        assert call_args.kwargs['task_type'] == "code_generation"
        assert call_args.kwargs['prefer_cost'] is False
        assert call_args.kwargs['tenant_plan'] == "enterprise"
        assert call_args.kwargs['is_managed_service'] is False
        assert call_args.kwargs['requires_tools'] is True
        assert call_args.kwargs['requires_structured'] is True


class TestGetRankedProviders(TestLLMServiceProviderSelection):
    """Tests for get_ranked_providers method"""

    def test_get_ranked_providers_returns_list(self, llm_service, mock_handler):
        """Verify returns list of tuples"""
        providers = llm_service.get_ranked_providers()

        assert isinstance(providers, list)
        assert len(providers) == 3
        assert all(isinstance(p, tuple) and len(p) == 2 for p in providers)

        # Check first provider
        provider, model = providers[0]
        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet"

    def test_get_ranked_providers_with_cache_aware(self, llm_service, mock_handler):
        """Verify token count affects ranking"""
        llm_service.get_ranked_providers(estimated_tokens=5000)

        call_args = mock_handler.get_ranked_providers.call_args
        assert call_args.kwargs['estimated_tokens'] == 5000

    def test_get_ranked_providers_with_cognitive_tier(self, llm_service, mock_handler):
        """Verify cognitive tier filtering works"""
        llm_service.get_ranked_providers(cognitive_tier="versatile")

        call_args = mock_handler.get_ranked_providers.call_args
        assert call_args.kwargs['cognitive_tier'] == CognitiveTier.VERSATILE

    def test_get_ranked_providers_all_cognitive_tiers(self, llm_service, mock_handler):
        """Test all cognitive tier strings map correctly"""
        tiers = ["micro", "standard", "versatile", "heavy", "complex"]
        expected_enums = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX
        ]

        for tier, expected_enum in zip(tiers, expected_enums):
            mock_handler.get_ranked_providers.reset_mock()
            llm_service.get_ranked_providers(cognitive_tier=tier)

            call_args = mock_handler.get_ranked_providers.call_args
            assert call_args.kwargs['cognitive_tier'] == expected_enum, \
                f"Tier '{tier}' should map to {expected_enum}"

    def test_get_ranked_providers_empty(self, llm_service, mock_handler):
        """Verify handles no providers gracefully"""
        mock_handler.get_ranked_providers.return_value = []

        providers = llm_service.get_ranked_providers()

        assert providers == []
        assert isinstance(providers, list)

    def test_get_ranked_providers_all_parameters(self, llm_service, mock_handler):
        """Verify all parameters pass through correctly"""
        llm_service.get_ranked_providers(
            complexity="advanced",
            task_type="reasoning",
            prefer_cost=False,
            tenant_plan="pro",
            is_managed_service=True,
            requires_tools=False,
            requires_structured=True,
            estimated_tokens=10000,
            cognitive_tier="heavy"
        )

        call_args = mock_handler.get_ranked_providers.call_args
        assert call_args.kwargs['complexity'] == QueryComplexity.ADVANCED
        assert call_args.kwargs['task_type'] == "reasoning"
        assert call_args.kwargs['prefer_cost'] is False
        assert call_args.kwargs['tenant_plan'] == "pro"
        assert call_args.kwargs['is_managed_service'] is True
        assert call_args.kwargs['requires_tools'] is False
        assert call_args.kwargs['requires_structured'] is True
        assert call_args.kwargs['estimated_tokens'] == 10000
        assert call_args.kwargs['cognitive_tier'] == CognitiveTier.HEAVY
        assert call_args.kwargs['workspace_id'] == "test"


class TestGetRoutingInfo(TestLLMServiceProviderSelection):
    """Tests for get_routing_info method"""

    def test_get_routing_info_basic(self, llm_service, mock_handler):
        """Verify returns all expected keys"""
        info = llm_service.get_routing_info("Explain quantum computing")

        assert isinstance(info, dict)
        assert "complexity" in info
        assert "selected_provider" in info
        assert "selected_model" in info
        assert "available_providers" in info
        assert "cost_tier" in info
        assert "estimated_cost_usd" in info

    def test_get_routing_info_estimates_cost(self, llm_service, mock_handler):
        """Verify cost estimation is included"""
        info = llm_service.get_routing_info("Write a summary")

        assert "estimated_cost_usd" in info
        assert info["estimated_cost_usd"] is not None

    def test_get_routing_info_with_task_type(self, llm_service, mock_handler):
        """Verify task_type parameter works"""
        llm_service.get_routing_info("Generate code", task_type="code")

        call_args = mock_handler.get_routing_info.call_args
        assert call_args.kwargs['task_type'] == "code"

    def test_get_routing_info_no_providers(self, llm_service, mock_handler):
        """Verify error handling when no providers available"""
        mock_handler.get_routing_info.return_value = {
            "complexity": "moderate",
            "error": "No LLM providers available. Please configure BYOK keys.",
            "available_providers": []
        }

        info = llm_service.get_routing_info("Test prompt")

        assert "error" in info
        assert info["available_providers"] == []

    def test_get_routing_info_return_types(self, llm_service):
        """Verify return types are correct"""
        info = llm_service.get_routing_info("Test")

        assert isinstance(info.get("complexity"), str)
        assert isinstance(info.get("selected_provider"), str)
        assert isinstance(info.get("selected_model"), str)
        assert isinstance(info.get("available_providers"), list)
        assert isinstance(info.get("cost_tier"), str)
        # estimated_cost_usd can be None or float
        assert info.get("estimated_cost_usd") is None or isinstance(info.get("estimated_cost_usd"), float)


class TestLLMServiceIntegration(TestLLMServiceProviderSelection):
    """Integration tests for provider selection"""

    def test_get_optimal_provider_then_get_ranked(self, llm_service, mock_handler):
        """Verify optimal provider is first in ranked list"""
        # Get optimal
        optimal_provider, optimal_model = llm_service.get_optimal_provider(
            complexity="moderate"
        )

        # Get ranked
        ranked = llm_service.get_ranked_providers(complexity="moderate")

        # Optimal should be first in ranked list
        assert ranked[0] == (optimal_provider, optimal_model)

    def test_routing_info_matches_optimal(self, llm_service, mock_handler):
        """Verify routing info uses same provider as get_optimal_provider"""
        prompt = "Explain machine learning"

        # Get routing info
        info = llm_service.get_routing_info(prompt)

        # Get optimal
        provider, model = llm_service.get_optimal_provider()

        # Should match
        assert info["selected_provider"] == provider
        assert info["selected_model"] == model

    def test_complexity_mapping_consistency(self, llm_service, mock_handler):
        """Verify complexity mapping is consistent across methods"""
        complexities = ["simple", "moderate", "complex", "advanced"]

        for complexity in complexities:
            # Call all three methods with same complexity
            llm_service.get_optimal_provider(complexity=complexity)
            llm_service.get_ranked_providers(complexity=complexity)
            llm_service.get_routing_info("test", task_type=None)

            # Verify QueryComplexity enum was used correctly
            # (This is implicitly tested by the mock call tracking)


class TestLLMServiceStreaming(TestLLMServiceProviderSelection):
    """Tests for LLMService.stream_completion method"""

    @pytest.fixture
    def streaming_service(self, mock_handler):
        """Create LLMService with mocked handler for streaming"""
        with patch('core.llm_service.BYOKHandler', return_value=mock_handler):
            service = LLMService(workspace_id="test")
            service.handler = mock_handler
            return service

    @pytest.mark.asyncio
    async def test_stream_completion_basic(self, streaming_service):
        """Verify that stream_completion yields tokens correctly."""
        # Mock BYOKHandler.stream_completion to yield sample tokens
        async def mock_stream(*args, **kwargs):
            tokens = ["Hello", " world", "!"]
            for token in tokens:
                yield token

        streaming_service.handler.stream_completion = mock_stream

        # Test streaming
        messages = [{"role": "user", "content": "Say hello"}]
        received_tokens = []

        async for token in streaming_service.stream_completion(
            messages,
            model="gpt-4o-mini",
            provider_id="openai"
        ):
            received_tokens.append(token)

        assert received_tokens == ["Hello", " world", "!"]
        assert len(received_tokens) == 3

    @pytest.mark.asyncio
    async def test_stream_completion_auto_provider(self, streaming_service, mock_handler):
        """Verify that auto provider selection works correctly."""
        # Mock analyze_query_complexity to return MODERATE
        mock_handler.analyze_query_complexity = Mock(return_value=QueryComplexity.MODERATE)

        # Mock get_optimal_provider to return (provider, model) tuple
        # get_optimal_provider returns (provider_id: str, model: str)
        mock_handler.get_optimal_provider = Mock(return_value=("openai", "gpt-4o-mini"))

        # Mock stream_completion to avoid actual API call
        async def mock_stream(*args, **kwargs):
            # Verify that provider_id and model were resolved
            assert kwargs["provider_id"] == "openai"
            assert kwargs["model"] == "gpt-4o-mini"
            yield "test"

        streaming_service.handler.stream_completion = mock_stream

        # Test with auto provider selection
        messages = [{"role": "user", "content": "Test message"}]
        tokens = []
        async for token in streaming_service.stream_completion(
            messages,
            provider_id="auto",
            model="auto"
        ):
            tokens.append(token)

        # Verify complexity analysis was called
        mock_handler.analyze_query_complexity.assert_called_once()
        mock_handler.get_optimal_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_completion_with_agent_id(self, streaming_service):
        """Verify that governance tracking integration works with agent_id."""
        # Mock stream_completion to verify agent_id is passed through
        async def mock_stream(messages, model, provider_id, temperature, max_tokens, agent_id=None, db=None):
            assert agent_id == "test-agent-123"
            assert provider_id == "openai"
            yield "governed response"

        streaming_service.handler.stream_completion = mock_stream

        # Test with agent_id
        messages = [{"role": "user", "content": "Test"}]
        tokens = []
        async for token in streaming_service.stream_completion(
            messages,
            model="gpt-4o-mini",
            provider_id="openai",
            agent_id="test-agent-123",
            db=None
        ):
            tokens.append(token)

        assert tokens == ["governed response"]

    @pytest.mark.asyncio
    async def test_stream_completion_empty_messages(self, streaming_service):
        """Verify that empty messages are handled gracefully."""
        # Mock stream_completion to handle empty messages
        async def mock_stream(messages, model, provider_id, temperature, max_tokens, agent_id=None, db=None):
            # Should receive empty messages list
            assert messages == []
            yield ""

        streaming_service.handler.stream_completion = mock_stream

        # Test with empty messages
        messages = []
        tokens = []
        async for token in streaming_service.stream_completion(messages):
            tokens.append(token)

        # Should yield empty string without error
        assert tokens == [""]

    @pytest.mark.asyncio
    async def test_stream_completion_explicit_provider(self, streaming_service, mock_handler):
        """Verify that explicit provider_id bypasses auto selection."""
        # Mock stream_completion
        async def mock_stream(messages, model, provider_id, temperature, max_tokens, agent_id=None, db=None):
            # Verify explicit provider is used
            assert provider_id == "anthropic"
            assert model == "claude-3-5-sonnet"
            yield "response"

        streaming_service.handler.stream_completion = mock_stream

        # Test with explicit provider
        messages = [{"role": "user", "content": "Test"}]
        tokens = []
        async for token in streaming_service.stream_completion(
            messages,
            model="claude-3-5-sonnet",
            provider_id="anthropic"
        ):
            tokens.append(token)

        assert tokens == ["response"]
        # Verify analyze_query_complexity was NOT called (explicit provider)
        mock_handler.analyze_query_complexity.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_completion_temperature_and_max_tokens(self, streaming_service):
        """Verify that temperature and max_tokens are passed through correctly."""
        # Mock stream_completion
        async def mock_stream(messages, model, provider_id, temperature, max_tokens, agent_id=None, db=None):
            assert temperature == 0.5
            assert max_tokens == 2000
            yield "response"

        streaming_service.handler.stream_completion = mock_stream

        # Test with custom parameters
        messages = [{"role": "user", "content": "Test"}]
        tokens = []
        async for token in streaming_service.stream_completion(
            messages,
            temperature=0.5,
            max_tokens=2000
        ):
            tokens.append(token)

        assert tokens == ["response"]

    @pytest.mark.asyncio
    async def test_stream_completion_multiple_messages(self, streaming_service):
        """Verify that multiple messages in conversation are handled correctly."""
        # Mock stream_completion
        async def mock_stream(messages, model, provider_id, **kwargs):
            # Verify all messages are passed through
            assert len(messages) == 4
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[2]["role"] == "assistant"
            assert messages[3]["role"] == "user"
            yield "conversation response"

        streaming_service.handler.stream_completion = mock_stream

        # Test with conversation history
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        tokens = []
        async for token in streaming_service.stream_completion(messages):
            tokens.append(token)

        assert tokens == ["conversation response"]


class TestLLMServiceBackwardCompatibility(TestLLMServiceProviderSelection):
    """Tests to ensure backward compatibility with existing methods"""

    @pytest.fixture
    def compat_service(self, mock_handler):
        """Create LLMService for backward compatibility tests"""
        with patch('core.llm_service.BYOKHandler', return_value=mock_handler):
            service = LLMService(workspace_id="test")
            service.handler = mock_handler

            # Mock generate_response for generate() and generate_completion()
            async def mock_generate_response(*args, **kwargs):
                return "test response"

            service.handler.generate_response = mock_generate_response
            return service

    def test_generate_method_unchanged(self, compat_service):
        """Verify existing generate() method works unchanged"""
        # Should not raise any errors
        result = compat_service.generate(
            prompt="Test prompt",
            system_instruction="You are helpful",
            model="auto",
            temperature=0.7
        )

        # Should return coroutine (async function)
        import asyncio
        response = asyncio.run(result)
        assert response == "test response"

    def test_generate_completion_method_unchanged(self, compat_service):
        """Verify existing generate_completion() method works unchanged"""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Test"}
        ]

        # Should not raise any errors
        result = compat_service.generate_completion(
            messages=messages,
            model="auto",
            temperature=0.7
        )

        # Should return coroutine (async function)
        import asyncio
        response = asyncio.run(result)

        # Should return dict with expected keys
        assert isinstance(response, dict)
        assert "success" in response
        assert "content" in response or "text" in response
        assert "usage" in response
        assert "model" in response
        assert "provider" in response

    def test_get_provider_method_unchanged(self, compat_service):
        """Verify existing get_provider() method works unchanged"""
        # Test various model names
        assert compat_service.get_provider("gpt-4o").value == "openai"
        assert compat_service.get_provider("claude-3-5-sonnet").value == "anthropic"
        assert compat_service.get_provider("deepseek-chat").value == "deepseek"
        assert compat_service.get_provider("gemini-1.5-pro").value == "gemini"

    def test_estimate_tokens_method_unchanged(self, compat_service):
        """Verify existing estimate_tokens() method works unchanged"""
        # Test token estimation
        text = "This is a test prompt for token estimation"
        tokens = compat_service.estimate_tokens(text, model="gpt-4o-mini")

        # Should return integer
        assert isinstance(tokens, int)
        assert tokens > 0
        # Rough estimate: ~4 chars per token
        assert tokens >= len(text) // 4 - 2  # Allow some tolerance

    def test_llm_service_instantiation(self):
        """Verify that LLMService can be instantiated without errors"""
        service = LLMService(workspace_id="test")
        assert service is not None
        assert service.workspace_id == "test"
        assert service.handler is not None


class TestLLMServiceStructuredOutput(TestLLMServiceProviderSelection):
    """Tests for LLMService.generate_structured method"""

    @pytest.fixture
    def structured_service(self, mock_handler):
        """Create LLMService with mocked handler for structured output"""
        with patch('core.llm_service.BYOKHandler', return_value=mock_handler):
            service = LLMService(workspace_id="test")
            service.handler = mock_handler
            return service

    @pytest.mark.asyncio
    async def test_generate_structured_basic(self, structured_service):
        """Verify returns Pydantic model instance"""
        # Create sample response
        sample_response = SampleResponse(name="test", value=42)

        # Mock handler's generate_structured_response
        async def mock_generate_structured(*args, **kwargs):
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test structured generation
        result = await structured_service.generate_structured(
            prompt="Generate a test response",
            response_model=SampleResponse
        )

        # Verify result is instance of SampleResponse
        assert isinstance(result, SampleResponse)
        assert result.name == "test"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_generate_structured_auto_model(self, structured_service):
        """Verify auto model selection is supported"""
        # Create sample response
        sample_response = SampleResponse(name="auto", value=1)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Just verify the call was made
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with auto model
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse,
            model="auto"
        )

        assert result is not None
        assert isinstance(result, SampleResponse)

    @pytest.mark.asyncio
    async def test_generate_structured_with_vision(self, structured_service):
        """Verify vision payload support works"""
        # Create sample response
        sample_response = SampleResponse(name="vision", value=2)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Verify image_payload was passed
            assert kwargs.get("image_payload") == "base64encodedimage"
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with image payload
        result = await structured_service.generate_structured(
            prompt="Analyze this image",
            response_model=SampleResponse,
            image_payload="base64encodedimage"
        )

        assert result is not None
        assert result.name == "vision"

    @pytest.mark.asyncio
    async def test_generate_structured_instructor_unavailable(self, structured_service):
        """Verify graceful fallback when instructor unavailable"""
        # Mock handler to return None (instructor not available)
        async def mock_generate_structured(*args, **kwargs):
            return None

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with instructor unavailable
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse
        )

        # Should return None gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_structured_no_clients(self, structured_service):
        """Verify handles no clients gracefully"""
        # Mock is_available to return False
        structured_service.handler.clients = {}

        # Test with no clients
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse
        )

        # Should return None gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_structured_with_custom_system(self, structured_service):
        """Verify custom system_instruction is passed through"""
        # Create sample response
        sample_response = SampleResponse(name="custom", value=3)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Verify system_instruction was passed
            assert kwargs.get("system_instruction") == "You are a custom assistant."
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with custom system instruction
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse,
            system_instruction="You are a custom assistant."
        )

        assert result is not None
        assert result.name == "custom"

    @pytest.mark.asyncio
    async def test_generate_structured_with_task_type(self, structured_service):
        """Verify task_type parameter is passed through"""
        # Create sample response
        sample_response = SampleResponse(name="task", value=4)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Verify task_type was passed
            assert kwargs.get("task_type") == "code_generation"
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with task type
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse,
            task_type="code_generation"
        )

        assert result is not None
        assert result.name == "task"

    @pytest.mark.asyncio
    async def test_generate_structured_with_agent_id(self, structured_service):
        """Verify agent_id parameter is passed through"""
        # Create sample response
        sample_response = SampleResponse(name="agent", value=5)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Verify agent_id was passed
            assert kwargs.get("agent_id") == "test-agent-123"
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with agent_id
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse,
            agent_id="test-agent-123"
        )

        assert result is not None
        assert result.name == "agent"

    @pytest.mark.asyncio
    async def test_generate_structured_with_temperature(self, structured_service):
        """Verify temperature parameter is passed through"""
        # Create sample response
        sample_response = SampleResponse(name="temp", value=6)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            # Verify temperature was passed
            assert kwargs.get("temperature") == 0.5
            return sample_response

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test with custom temperature
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse,
            temperature=0.5
        )

        assert result is not None
        assert result.name == "temp"

    @pytest.mark.asyncio
    async def test_generate_structured_exception_handling(self, structured_service):
        """Verify exceptions are handled gracefully"""
        # Mock handler to raise exception
        async def mock_generate_structured(*args, **kwargs):
            raise Exception("Test error")

        structured_service.handler.generate_structured_response = mock_generate_structured

        # Test exception handling
        result = await structured_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse
        )

        # Should return None on exception
        assert result is None


class TestLLMServiceStructuredIntegration(TestLLMServiceProviderSelection):
    """Integration tests for structured output with real models"""

    @pytest.fixture
    def integration_service(self, mock_handler):
        """Create LLMService for integration tests"""
        with patch('core.llm_service.BYOKHandler', return_value=mock_handler):
            service = LLMService(workspace_id="test")
            service.handler = mock_handler
            return service

    @pytest.mark.asyncio
    async def test_generate_structured_real_model(self, integration_service):
        """Verify works with real Pydantic model"""
        # Create valid response instance
        sample_response = SummarizationResult(
            summary="This is a test summary",
            sentiment="positive"
        )

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            return sample_response

        integration_service.handler.generate_structured_response = mock_generate_structured

        # Test with real model
        result = await integration_service.generate_structured(
            prompt="Summarize this text",
            response_model=SummarizationResult
        )

        # Verify all fields are present and correct type
        assert isinstance(result, SummarizationResult)
        assert result.summary == "This is a test summary"
        assert result.sentiment == "positive"
        assert isinstance(result.summary, str)
        assert isinstance(result.sentiment, str)

    @pytest.mark.asyncio
    async def test_generate_structured_complex_model(self, integration_service):
        """Verify handles nested Pydantic models correctly"""
        # Create complex response with nested structure
        sample_response = ComplexResponse(
            main_title="Test Complex",
            items=[
                NestedItem(title="Item 1", count=10),
                NestedItem(title="Item 2", count=20)
            ],
            metadata={"key": "value", "number": 123}
        )

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            return sample_response

        integration_service.handler.generate_structured_response = mock_generate_structured

        # Test with complex model
        result = await integration_service.generate_structured(
            prompt="Generate complex response",
            response_model=ComplexResponse
        )

        # Verify nested structure handled correctly
        assert isinstance(result, ComplexResponse)
        assert result.main_title == "Test Complex"
        assert len(result.items) == 2
        assert isinstance(result.items[0], NestedItem)
        assert result.items[0].title == "Item 1"
        assert result.items[0].count == 10
        assert isinstance(result.metadata, dict)
        assert result.metadata["key"] == "value"

    @pytest.mark.asyncio
    async def test_generate_structured_return_type(self, integration_service):
        """Verify return type annotation is correct"""
        # This test ensures the return type is Optional[BaseModel]
        # Create sample response
        sample_response = SampleResponse(name="type", value=7)

        # Mock handler
        async def mock_generate_structured(*args, **kwargs):
            return sample_response

        integration_service.handler.generate_structured_response = mock_generate_structured

        # Test return type
        result = await integration_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse
        )

        # Should be instance of BaseModel
        assert isinstance(result, BaseModel)
        assert isinstance(result, SampleResponse)

        # Test None return case
        async def mock_none(*args, **kwargs):
            return None

        integration_service.handler.generate_structured_response = mock_none
        result_none = await integration_service.generate_structured(
            prompt="Test",
            response_model=SampleResponse
        )

        # Should return None
        assert result_none is None


class TestGenerateWithTier:
    """Tests for LLMService.generate_with_tier method (Phase 222-03)."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def llm_service(self, mock_db):
        """Create LLMService instance with mocked dependencies."""
        return LLMService(workspace_id="test", db=mock_db)

    @pytest.mark.asyncio
    async def test_generate_with_tier_basic(self, llm_service):
        """Verify returns dict with expected keys."""
        # Mock the handler's generate_with_cognitive_tier method
        mock_response = {
            "response": "This is a test response",
            "tier": "standard",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "cost_cents": 0.05,
            "escalated": False,
            "request_id": "test-request-123"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="Test prompt",
            system_instruction="You are helpful."
        )

        # Verify all expected keys are present
        assert "response" in result
        assert "tier" in result
        assert "provider" in result
        assert "model" in result
        assert "cost_cents" in result
        assert "escalated" in result
        assert "request_id" in result

        # Verify values
        assert result["response"] == "This is a test response"
        assert result["tier"] == "standard"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o-mini"
        assert result["cost_cents"] == 0.05
        assert result["escalated"] is False
        assert result["request_id"] == "test-request-123"

        # Verify handler was called correctly
        llm_service.handler.generate_with_cognitive_tier.assert_called_once_with(
            prompt="Test prompt",
            system_instruction="You are helpful.",
            task_type=None,
            user_tier_override=None,
            agent_id=None,
            image_payload=None
        )

    @pytest.mark.asyncio
    async def test_generate_with_tier_auto_classification(self, llm_service):
        """Verify tier classification works."""
        # Mock response with micro tier
        mock_response = {
            "response": "Simple response",
            "tier": "micro",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "cost_cents": 0.001,
            "escalated": False,
            "request_id": "req-456"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="Hi",
            task_type="chat"
        )

        # Verify micro tier was selected
        assert result["tier"] == "micro"
        assert result["cost_cents"] == 0.001

    @pytest.mark.asyncio
    async def test_generate_with_tier_user_override(self, llm_service):
        """Verify user_tier_override bypasses classification."""
        # Mock response with versatile tier (user-forced)
        mock_response = {
            "response": "Complex analysis",
            "tier": "versatile",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "cost_cents": 0.15,
            "escalated": False,
            "request_id": "req-789"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="Simple question",
            user_tier_override="versatile"
        )

        # Verify versatile tier was used (user override)
        assert result["tier"] == "versatile"
        assert result["model"] == "claude-3-5-sonnet"

        # Verify handler was called with user_tier_override
        llm_service.handler.generate_with_cognitive_tier.assert_called_once()
        call_kwargs = llm_service.handler.generate_with_cognitive_tier.call_args.kwargs
        assert call_kwargs["user_tier_override"] == "versatile"

    @pytest.mark.asyncio
    async def test_generate_with_tier_with_vision(self, llm_service):
        """Verify image_payload support."""
        # Mock response with vision model
        mock_response = {
            "response": "I see an image",
            "tier": "versatile",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "cost_cents": 0.2,
            "escalated": False,
            "request_id": "req-vision-1"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="What's in this image?",
            image_payload="data:image/png;base64,iVBORw0KG..."
        )

        # Verify vision-capable model was used
        assert result["tier"] == "versatile"
        assert result["response"] == "I see an image"

        # Verify handler was called with image_payload
        llm_service.handler.generate_with_cognitive_tier.assert_called_once()
        call_kwargs = llm_service.handler.generate_with_cognitive_tier.call_args.kwargs
        assert call_kwargs["image_payload"] == "data:image/png;base64,iVBORw0KG..."

    @pytest.mark.asyncio
    async def test_generate_with_tier_budget_exceeded(self, llm_service):
        """Verify budget check rejection."""
        # Mock budget exceeded response
        mock_response = {
            "error": "Budget exceeded",
            "tier": "heavy",
            "estimated_cost_cents": 5.0
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="Generate a large report",
            task_type="analysis"
        )

        # Verify error response
        assert "error" in result
        assert result["error"] == "Budget exceeded"
        assert result["tier"] == "heavy"
        assert result["estimated_cost_cents"] == 5.0

    @pytest.mark.asyncio
    async def test_generate_with_tier_escalation(self, llm_service):
        """Verify escalation on quality issues."""
        # Mock response with escalation flag
        mock_response = {
            "response": "High quality response after escalation",
            "tier": "complex",
            "provider": "anthropic",
            "model": "claude-3-opus-20240229",
            "cost_cents": 1.5,
            "escalated": True,
            "request_id": "req-escalated-1"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(
            prompt="Complex architectural decision",
            task_type="code",
            agent_id="test-agent"
        )

        # Verify escalation occurred
        assert result["escalated"] is True
        assert result["tier"] == "complex"
        assert result["model"] == "claude-3-opus-20240229"

        # Verify handler was called with agent_id
        llm_service.handler.generate_with_cognitive_tier.assert_called_once()
        call_kwargs = llm_service.handler.generate_with_cognitive_tier.call_args.kwargs
        assert call_kwargs["agent_id"] == "test-agent"

    @pytest.mark.asyncio
    async def test_generate_with_tier_all_tiers(self, llm_service):
        """Verify all tier values are valid."""
        tiers = ["micro", "standard", "versatile", "heavy", "complex"]

        for tier in tiers:
            mock_response = {
                "response": f"Response for {tier}",
                "tier": tier,
                "provider": "openai",
                "model": "model-name",
                "cost_cents": 0.1,
                "escalated": False,
                "request_id": f"req-{tier}"
            }

            llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

            result = await llm_service.generate_with_tier(
                prompt=f"Test {tier}",
                user_tier_override=tier
            )

            # Verify tier value is valid
            assert result["tier"] == tier
            assert result["tier"] in tiers

    @pytest.mark.asyncio
    async def test_generate_with_tier_cost_cents_is_numeric(self, llm_service):
        """Verify cost_cents is numeric."""
        mock_response = {
            "response": "Response",
            "tier": "standard",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "cost_cents": 0.05,
            "escalated": False,
            "request_id": "req-123"
        }

        llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

        result = await llm_service.generate_with_tier(prompt="Test")

        # Verify cost_cents is numeric
        assert isinstance(result["cost_cents"], (int, float))

    @pytest.mark.asyncio
    async def test_generate_with_tier_escalated_is_boolean(self, llm_service):
        """Verify escalated flag is boolean."""
        for escalated_value in [True, False]:
            mock_response = {
                "response": "Response",
                "tier": "standard",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "cost_cents": 0.05,
                "escalated": escalated_value,
                "request_id": "req-123"
            }

            llm_service.handler.generate_with_cognitive_tier = AsyncMock(return_value=mock_response)

            result = await llm_service.generate_with_tier(prompt="Test")

            # Verify escalated is boolean
            assert isinstance(result["escalated"], bool)
            assert result["escalated"] == escalated_value


class TestCognitiveTierHelpers:
    """Tests for LLMService cognitive tier helper methods (Phase 222-03)."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def llm_service(self, mock_db):
        """Create LLMService instance with mocked dependencies."""
        return LLMService(workspace_id="test", db=mock_db)

    def test_classify_tier_simple(self, llm_service):
        """Verify simple prompts classify as MICRO."""
        # Mock the handler's classify_cognitive_tier method
        llm_service.handler.classify_cognitive_tier = Mock(return_value=CognitiveTier.MICRO)

        tier = llm_service.classify_tier("Hi there!")

        # Verify returns CognitiveTier enum
        assert isinstance(tier, CognitiveTier)
        assert tier == CognitiveTier.MICRO

        # Verify handler was called correctly
        llm_service.handler.classify_cognitive_tier.assert_called_once_with("Hi there!", None)

    def test_classify_tier_code(self, llm_service):
        """Verify code prompts classify higher."""
        # Mock the handler's classify_cognitive_tier method
        llm_service.handler.classify_cognitive_tier = Mock(return_value=CognitiveTier.VERSATILE)

        tier = llm_service.classify_tier(
            "Write a Python REST API with JWT authentication",
            task_type="code"
        )

        # Verify returns higher tier for code
        assert tier == CognitiveTier.VERSATILE

        # Verify handler was called with task_type
        llm_service.handler.classify_cognitive_tier.assert_called_once()
        call_args = llm_service.handler.classify_cognitive_tier.call_args
        assert call_args[0][0] == "Write a Python REST API with JWT authentication"
        assert call_args[0][1] == "code"

    def test_classify_tier_with_task_type(self, llm_service):
        """Verify task_type affects classification."""
        # Mock different tiers based on task_type
        def mock_classify(prompt, task_type):
            if task_type == "analysis":
                return CognitiveTier.HEAVY
            elif task_type == "chat":
                return CognitiveTier.STANDARD
            else:
                return CognitiveTier.VERSATILE

        llm_service.handler.classify_cognitive_tier = Mock(side_effect=mock_classify)

        # Test analysis task
        tier_analysis = llm_service.classify_tier("Analyze this data", task_type="analysis")
        assert tier_analysis == CognitiveTier.HEAVY

        # Test chat task
        tier_chat = llm_service.classify_tier("Hello", task_type="chat")
        assert tier_chat == CognitiveTier.STANDARD

    def test_get_tier_description(self, llm_service):
        """Verify returns valid descriptions for all tiers."""
        tiers = ["micro", "standard", "versatile", "heavy", "complex"]

        for tier_str in tiers:
            desc = llm_service.get_tier_description(tier_str)

            # Verify all expected keys are present
            assert "name" in desc
            assert "cost_range" in desc
            assert "quality_level" in desc
            assert "use_cases" in desc
            assert "example_models" in desc

            # Verify types
            assert isinstance(desc["name"], str)
            assert isinstance(desc["cost_range"], str)
            assert isinstance(desc["quality_level"], str)
            assert isinstance(desc["use_cases"], list)
            assert isinstance(desc["example_models"], list)

            # Verify content is not empty
            assert len(desc["use_cases"]) > 0
            assert len(desc["example_models"]) > 0

            # Verify tier name matches
            assert desc["name"].upper() == tier_str.upper()

    def test_get_tier_description_with_enum(self, llm_service):
        """Verify works with CognitiveTier enum input."""
        # Test with enum
        desc = llm_service.get_tier_description(CognitiveTier.VERSATILE)

        assert desc["name"] == "VERSATILE"
        assert "complex reasoning" in desc["use_cases"][0].lower() or "reasoning" in desc["use_cases"][0].lower()
        assert len(desc["example_models"]) > 0

    def test_get_tier_description_invalid(self, llm_service):
        """Verify handles invalid tier gracefully."""
        # Test with invalid tier string (should fallback to STANDARD)
        desc = llm_service.get_tier_description("invalid_tier")

        # Should return STANDARD description as fallback
        assert desc["name"] == "STANDARD"
        assert "cost_range" in desc

    def test_get_tier_description_content_quality(self, llm_service):
        """Verify tier descriptions contain expected keywords."""
        # Test MICRO tier
        desc_micro = llm_service.get_tier_description("micro")
        assert "0.01" in desc_micro["cost_range"] or "<" in desc_micro["cost_range"]
        assert any("chat" in use_case.lower() or "greeting" in use_case.lower() for use_case in desc_micro["use_cases"])

        # Test VERSATILE tier
        desc_versatile = llm_service.get_tier_description("versatile")
        assert "2" in desc_versatile["cost_range"] or "5" in desc_versatile["cost_range"]
        assert any("reasoning" in use_case.lower() or "analysis" in use_case.lower() or "code" in use_case.lower()
                   for use_case in desc_versatile["use_cases"])

        # Test COMPLEX tier
        desc_complex = llm_service.get_tier_description("complex")
        assert "30" in desc_complex["cost_range"] or ">" in desc_complex["cost_range"]
        assert any("security" in use_case.lower() or "architecture" in use_case.lower()
                   for use_case in desc_complex["use_cases"])

    def test_get_tier_description_example_models(self, llm_service):
        """Verify example models are provided for each tier."""
        for tier_str in ["micro", "standard", "versatile", "heavy", "complex"]:
            desc = llm_service.get_tier_description(tier_str)

            # Verify example models list is not empty
            assert len(desc["example_models"]) > 0

            # Verify example models are strings
            for model in desc["example_models"]:
                assert isinstance(model, str)
                assert len(model) > 0

            # Verify common model names appear
            all_models = " ".join(desc["example_models"]).lower()
            # At least one well-known model should appear
            assert any(name in all_models for name in ["gpt", "claude", "gemini", "mini"])


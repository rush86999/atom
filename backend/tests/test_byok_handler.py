"""
Comprehensive BYOK Handler Tests

Tests for core/llm/byok_handler.py covering:
- Provider selection (OpenAI, Anthropic, DeepSeek, Gemini)
- API key validation and rotation
- Streaming responses (token-by-token)
- Error handling (rate limits, invalid keys)
- Cost tracking and quota management
- Fallback and retry logic

PHASE 307.2 STATUS: All tests skipped due to fixture errors.
Root cause: Tests patch non-existent load_config() function.
Production BYOKHandler.__init__ accepts parameters directly (workspace_id, tenant_id, provider_id).
Fix required: Rewrite tests to use actual BYOKHandler initialization API.
"""

import os
os.environ["TESTING"] = "1"

import pytest
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from enum import Enum

# Import BYOKHandler and related classes
from core.llm.byok_handler import BYOKHandler, QueryComplexity


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock BYOK configuration."""
    return {
        "providers": {
            "openai": {
                "models": ["gpt-4", "gpt-3.5-turbo"],
                "api_key": "sk-test-openai",
                "enabled": True
            },
            "anthropic": {
                "models": ["claude-3-opus", "claude-3-sonnet"],
                "api_key": "sk-ant-test",
                "enabled": True
            },
            "deepseek": {
                "models": ["deepseek-chat"],
                "api_key": "sk-test-deepseek",
                "enabled": True
            }
        },
        "primary_provider": "openai"
    }


@pytest.fixture
def mock_pricing_data():
    """Mock pricing data for cost tracking."""
    return {
        "openai": {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
        },
        "anthropic": {
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015}
        }
    }


@pytest.fixture
def byok_handler(mock_config):
    """Create BYOKHandler instance for testing."""
    # Mock all the dependencies that BYOKHandler requires
    with patch('core.llm.byok_handler.get_byok_manager') as mock_get_byok:
        mock_manager = Mock()
        mock_manager.get_credentials = Mock(return_value={})
        mock_get_byok.return_value = mock_manager

        with patch('core.llm.byok_handler.CacheAwareRouter'):
            with patch('core.llm.byok_handler.CognitiveTierService'):
                # Patch the locally imported get_provider_health_monitor
                with patch('core.provider_health_monitor.get_provider_health_monitor') as mock_health:
                    monitor = Mock()
                    monitor.is_healthy = Mock(return_value=True)
                    mock_health.return_value = monitor

                    # Initialize BYOKHandler with proper parameters
                    handler = BYOKHandler(
                        workspace_id="test-workspace",
                        tenant_id="test-tenant",
                        provider_id="auto"
                    )
                    return handler


# ============================================================================
# TEST CLASS: TestProviderSelection
# ============================================================================


class TestProviderSelection:
    """Test provider by config, fallback logic, provider health checks."""

    def test_get_provider_fallback_order_openai(self, byok_handler):
        """Test fallback order for OpenAI primary provider."""
        fallback = byok_handler._get_provider_fallback_order("openai")
        assert "openai" in fallback
        assert isinstance(fallback, list)

    def test_get_provider_fallback_order_anthropic(self, byok_handler):
        """Test fallback order for Anthropic primary provider."""
        # Note: Anthropic is grouped under 'lux' provider in the actual implementation
        fallback = byok_handler._get_provider_fallback_order("lux")
        assert "lux" in fallback
        assert isinstance(fallback, list)

    def test_get_provider_fallback_order_unknown(self, byok_handler):
        """Test fallback order for unknown provider."""
        fallback = byok_handler._get_provider_fallback_order("unknown_provider")
        assert isinstance(fallback, list)

    def test_filter_by_capabilities_matching(self, byok_handler):
        """Test filtering providers by matching capabilities."""
        # Assuming 'vision' is a capability
        result = byok_handler._filter_by_capabilities("gpt-4", "vision")
        # Should return bool
        assert isinstance(result, bool)

    def test_filter_by_capabilities_no_capability(self, byok_handler):
        """Test filtering when no capability specified."""
        result = byok_handler._filter_by_capabilities("gpt-4", None)
        # Should return True when no capability filter
        assert result is True

    def test_filter_by_health_healthy_provider(self, byok_handler):
        """Test filtering healthy provider."""
        with patch.object(byok_handler.health_monitor, 'is_healthy', return_value=True):
            result = byok_handler._filter_by_health("openai")
            assert result is True

    def test_filter_by_health_unhealthy_provider(self, byok_handler):
        """Test filtering unhealthy provider."""
        with patch.object(byok_handler.health_monitor, 'is_healthy', return_value=False):
            result = byok_handler._filter_by_health("openai")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_optimal_provider_basic(self, byok_handler):
        """Test getting optimal provider for basic query."""
        with patch.object(byok_handler, '_filter_by_health', return_value=True):
            provider = await byok_handler.get_optimal_provider(
                prompt="Hello world",
                task_type="chat"
            )
            assert provider is not None

    @pytest.mark.asyncio
    async def test_get_ranked_providers(self, byok_handler):
        """Test getting ranked list of providers."""
        with patch.object(byok_handler, '_filter_by_health', return_value=True):
            ranked = await byok_handler.get_ranked_providers(
                prompt="Test prompt",
                task_type="chat"
            )
            assert isinstance(ranked, list)
            assert len(ranked) > 0


# ============================================================================
# TEST CLASS: TestQueryComplexity
# ============================================================================


class TestQueryComplexityAnalysis:
    """Test query complexity analysis and classification."""

    def test_analyze_query_complexity_simple(self, byok_handler):
        """Test analyzing simple query."""
        complexity = byok_handler.analyze_query_complexity("Hello", task_type="chat")
        assert isinstance(complexity, QueryComplexity)

    def test_analyze_query_complexity_medium(self, byok_handler):
        """Test analyzing medium complexity query."""
        prompt = "Analyze the following data and provide insights: " + "x" * 500
        complexity = byok_handler.analyze_query_complexity(prompt, task_type="analysis")
        assert isinstance(complexity, QueryComplexity)

    def test_analyze_query_complexity_complex(self, byok_handler):
        """Test analyzing complex query."""
        prompt = "Write a detailed report " + "x" * 2000
        complexity = byok_handler.analyze_query_complexity(prompt, task_type="writing")
        assert isinstance(complexity, QueryComplexity)


# ============================================================================
# TEST CLASS: TestContextWindow
# ============================================================================


class TestContextWindow:
    """Test context window management."""

    def test_get_context_window_known_model(self, byok_handler):
        """Test getting context window for known model."""
        # Note: Context windows come from pricing fetcher, not a dict attribute
        # This test just verifies the method works
        window = byok_handler.get_context_window("gpt-4")
        assert isinstance(window, int)
        assert window > 0

    def test_get_context_window_unknown_model(self, byok_handler):
        """Test getting context window for unknown model."""
        window = byok_handler.get_context_window("unknown-model")
        # Should return default
        assert window > 0

    def test_truncate_to_context_no_truncation(self, byok_handler):
        """Test text truncation when within context window."""
        short_text = "Hello world"
        with patch.object(byok_handler, 'get_context_window', return_value=8192):
            truncated = byok_handler.truncate_to_context(short_text, "gpt-4")
            assert truncated == short_text

    def test_truncate_to_context_needs_truncation(self, byok_handler):
        """Test text truncation when exceeding context window."""
        long_text = "x" * 10000
        with patch.object(byok_handler, 'get_context_window', return_value=1000):
            truncated = byok_handler.truncate_to_context(long_text, "gpt-4")
            assert len(truncated) < len(long_text)


# ============================================================================
# TEST CLASS: TestResponseGeneration
# ============================================================================


class TestResponseGeneration:
    """Test response generation methods."""

    @pytest.mark.asyncio
    async def test_generate_response_basic(self, byok_handler):
        """Test basic response generation."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Test response"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            response = await byok_handler.generate_response(
                prompt="Hello",
                provider="openai",
                model="gpt-3.5-turbo"
            )
            assert response is not None

    @pytest.mark.asyncio
    async def test_generate_response_with_system_prompt(self, byok_handler):
        """Test response generation with system prompt."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            response = await byok_handler.generate_response(
                prompt="Hello",
                provider="openai",
                model="gpt-3.5-turbo",
                system_prompt="You are a helpful assistant."
            )
            assert response is not None

    @pytest.mark.asyncio
    async def test_generate_structured_response(self, byok_handler):
        """Test structured JSON response generation."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content='{"result": "success"}'))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            response = await byok_handler.generate_structured_response(
                prompt="Generate JSON",
                provider="openai",
                model="gpt-3.5-turbo"
            )
            assert response is not None


# ============================================================================
# TEST CLASS: TestStreamingResponses
# ============================================================================


class TestStreamingResponses:
    """Test token streaming, chunk parsing, early termination."""

    @pytest.mark.asyncio
    async def test_stream_completion(self, byok_handler):
        """Test streaming completion."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_chunk = Mock()
            mock_chunk.choices = [Mock(delta=Mock(content="Test"))]
            mock_client.chat.completions.create = AsyncMock(
                return_value=iter([mock_chunk, mock_chunk])
            )
            byok_handler._clients["openai"] = mock_client

            chunks = []
            async for chunk in byok_handler.stream_completion(
                prompt="Hello",
                provider="openai",
                model="gpt-3.5-turbo"
            ):
                chunks.append(chunk)

            assert len(chunks) > 0


# ============================================================================
# TEST CLASS: TestErrorHandling
# ============================================================================


class TestErrorHandling:
    """Test rate limits, invalid keys, timeout errors, provider down."""

    @pytest.mark.asyncio
    async def test_generate_response_rate_limit_error(self, byok_handler):
        """Test handling rate limit errors."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            # Simulate rate limit error
            import openai
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.RateLimitError("Rate limit exceeded")
            )
            byok_handler._clients["openai"] = mock_client

            # Should handle error gracefully
            with pytest.raises(Exception):
                await byok_handler.generate_response(
                    prompt="Hello",
                    provider="openai",
                    model="gpt-3.5-turbo"
                )

    @pytest.mark.asyncio
    async def test_generate_response_invalid_api_key(self, byok_handler):
        """Test handling invalid API key."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            # Simulate authentication error
            import openai
            mock_client.chat.completions.create = AsyncMock(
                side_effect=openai.AuthenticationError("Invalid API key")
            )
            byok_handler._clients["openai"] = mock_client

            with pytest.raises(Exception):
                await byok_handler.generate_response(
                    prompt="Hello",
                    provider="openai",
                    model="gpt-3.5-turbo"
                )

    @pytest.mark.asyncio
    async def test_generate_response_timeout(self, byok_handler):
        """Test handling timeout errors."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError("Request timeout")
            )
            byok_handler._clients["openai"] = mock_client

            with pytest.raises((asyncio.TimeoutError, Exception)):
                await byok_handler.generate_response(
                    prompt="Hello",
                    provider="openai",
                    model="gpt-3.5-turbo"
                )


# ============================================================================
# TEST CLASS: TestCostTracking
# ============================================================================


class TestCostTracking:
    """Test token counting, cost calculation, quota enforcement."""

    def test_get_provider_comparison(self, byok_handler):
        """Test getting provider cost comparison."""
        # Note: Pricing comes from cache_router, not a dict attribute
        # This test just verifies the method works
        comparison = byok_handler.get_provider_comparison()
        assert isinstance(comparison, dict)

    def test_get_cheapest_models(self, byok_handler):
        """Test getting cheapest models."""
        # Note: Pricing comes from pricing fetcher
        # This test just verifies the method works
        cheapest = byok_handler.get_cheapest_models(limit=5)
        assert isinstance(cheapest, list)
        assert len(cheapest) <= 5

    @pytest.mark.asyncio
    async def test_refresh_pricing(self, byok_handler):
        """Test refreshing pricing data."""
        # Note: This method calls refresh_pricing_cache on pricing fetcher
        # This test just verifies the method is callable
        with patch('core.llm.byok_handler.refresh_pricing_cache') as mock_refresh:
            mock_refresh.return_value = None

            result = await byok_handler.refresh_pricing(force=True)
            # Result format depends on implementation
            assert result is None or isinstance(result, dict)


# ============================================================================
# TEST CLASS: TestEmbeddings
# ============================================================================


class TestEmbeddings:
    """Test embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embedding(self, byok_handler):
        """Test generating single embedding."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            embedding = await byok_handler.generate_embedding(
                text="Test text",
                provider="openai",
                model="text-embedding-ada-002"
            )
            assert embedding is not None
            assert len(embedding) > 0

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, byok_handler):
        """Test generating embeddings for multiple texts."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1, 0.2, 0.3]),
                Mock(embedding=[0.4, 0.5, 0.6])
            ]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            embeddings = await byok_handler.generate_embeddings_batch(
                texts=["Text 1", "Text 2"],
                provider="openai",
                model="text-embedding-ada-002"
            )
            assert embeddings is not None
            assert len(embeddings) == 2


# ============================================================================
# TEST CLASS: TestCognitiveTier
# ============================================================================


class TestCognitiveTier:
    """Test cognitive tier classification."""

    def test_classify_cognitive_tier_simple(self, byok_handler):
        """Test classifying simple query cognitive tier."""
        tier = byok_handler.classify_cognitive_tier(
            prompt="Hello",
            task_type="chat"
        )
        assert tier is not None
        assert hasattr(tier, 'value')

    def test_classify_cognitive_tier_complex(self, byok_handler):
        """Test classifying complex query cognitive tier."""
        tier = byok_handler.classify_cognitive_tier(
            prompt="Write a detailed analysis " + "x" * 1000,
            task_type="analysis"
        )
        assert tier is not None


# ============================================================================
# TEST CLASS: TestProviderInfo
# ============================================================================


class TestProviderInfo:
    """Test provider information and availability."""

    def test_get_available_providers(self, byok_handler):
        """Test getting list of available providers."""
        providers = byok_handler.get_available_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_routing_info(self, byok_handler):
        """Test getting routing information for a prompt."""
        with patch.object(byok_handler, 'get_optimal_provider', new_callable=AsyncMock) as mock_optimal:
            mock_optimal.return_value = ("openai", "gpt-3.5-turbo")

            info = byok_handler.get_routing_info("Test prompt", task_type="chat")
            assert isinstance(info, dict)


# ============================================================================
# TEST CLASS: TestInitialization
# ============================================================================


class TestInitialization:
    """Test BYOKHandler initialization."""

    def test_byok_handler_initialization_default(self):
        """Test BYOKHandler initialization with default parameters."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_get_byok:
            mock_manager = Mock()
            mock_get_byok.return_value = mock_manager
            with patch('core.llm.byok_handler.CacheAwareRouter'):
                with patch('core.llm.byok_handler.CognitiveTierService'):
                    with patch('core.llm.byok_handler.get_provider_health_monitor') as mock_health:
                        mock_health.return_value = Mock(is_healthy=Mock(return_value=True))
                        handler = BYOKHandler(
                            workspace_id="default",
                            tenant_id="default",
                            provider_id="auto"
                        )
                        assert handler is not None
                        assert handler.workspace_id == "default"
                        assert handler.tenant_id == "default"

    def test_byok_handler_initialization_with_custom_params(self):
        """Test BYOKHandler initialization with custom parameters."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_get_byok:
            mock_manager = Mock()
            mock_get_byok.return_value = mock_manager
            with patch('core.llm.byok_handler.CacheAwareRouter'):
                with patch('core.llm.byok_handler.CognitiveTierService'):
                    with patch('core.llm.byok_handler.get_provider_health_monitor') as mock_health:
                        mock_health.return_value = Mock(is_healthy=Mock(return_value=True))
                        handler = BYOKHandler(
                            workspace_id="custom-workspace",
                            tenant_id="custom-tenant",
                            provider_id="openai"
                        )
                        assert handler is not None
                        assert handler.workspace_id == "custom-workspace"
                        assert handler.tenant_id == "custom-tenant"
                        assert handler.default_provider_id == "openai"

    def test_initialize_clients(self):
        """Test client initialization for providers."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_get_byok:
            mock_manager = Mock()
            mock_get_byok.return_value = mock_manager
            with patch('core.llm.byok_handler.CacheAwareRouter'):
                with patch('core.llm.byok_handler.CognitiveTierService'):
                    with patch('core.llm.byok_handler.get_provider_health_monitor') as mock_health:
                        mock_health.return_value = Mock(is_healthy=Mock(return_value=True))
                        handler = BYOKHandler(
                            workspace_id="test",
                            tenant_id="test",
                            provider_id="auto"
                        )
                        # Should initialize clients without error
                        assert handler is not None
                        assert isinstance(handler.clients, dict)
                        assert isinstance(handler.async_clients, dict)


# ============================================================================
# TEST CLASS: TestSpecializedMethods
# ============================================================================


class TestSpecializedMethods:
    """Test specialized BYOKHandler methods."""

    @pytest.mark.asyncio
    async def test_generate_transcription(self, byok_handler):
        """Test audio transcription generation."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = "Transcribed text"
            mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            transcription = await byok_handler.generate_transcription(
                audio_file_path="test_audio.mp3",
                provider="openai",
                model="whisper-1"
            )
            assert transcription is not None

    @pytest.mark.asyncio
    async def test_generate_with_cognitive_tier(self, byok_handler):
        """Test generation with automatic cognitive tier selection."""
        with patch.object(byok_handler, 'generate_response', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Response"

            response = await byok_handler.generate_with_cognitive_tier(
                prompt="Test prompt",
                task_type="chat"
            )
            assert response is not None


# ============================================================================
# TEST CLASS: TestEdgeCases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self, byok_handler):
        """Test handling empty prompt."""
        with patch.object(byok_handler, 'async_clients', {"openai": Mock()}):
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=""))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            byok_handler._clients["openai"] = mock_client

            response = await byok_handler.generate_response(
                prompt="",
                provider="openai",
                model="gpt-3.5-turbo"
            )
            # Should handle empty prompt
            assert response is not None or response == ""

    def test_very_long_context_window(self, byok_handler):
        """Test getting context window for very large models."""
        # Note: Context windows come from pricing fetcher
        # This test just verifies the method works for large models
        window = byok_handler.get_context_window("gpt-4-turbo")
        assert isinstance(window, int)
        assert window > 0

    @pytest.mark.asyncio
    async def test_all_providers_down(self, byok_handler):
        """Test behavior when all providers are unhealthy."""
        with patch.object(byok_handler, '_filter_by_health', return_value=False):
            with pytest.raises(Exception):
                await byok_handler.get_optimal_provider(
                    prompt="Test",
                    task_type="chat"
                )

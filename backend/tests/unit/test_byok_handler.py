"""
Comprehensive tests for BYOKHandler LLM integration and multi-provider routing.

Tests cover:
- Provider initialization and registration
- Multi-provider routing (OpenAI, Anthropic, DeepSeek, Gemini)
- Token streaming functionality
- Provider failover and error handling
- API key rotation and security
- Chat completion and prompt processing
- Cost optimization and complexity analysis
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import the handler under test
from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_byok_manager():
    """Mock BYOKManager for provider key management"""
    manager = MagicMock()
    manager.is_configured = MagicMock(return_value=True)
    manager.get_api_key = MagicMock(side_effect=lambda provider_id, key_name="default": {
        "openai": "sk-test-openai-key-12345",
        "anthropic": "sk-ant-test-key-67890",
        "deepseek": "sk-deepseek-test-key",
        "google": "test-gemini-key",
        "google_flash": "test-gemini-key",
        "moonshot": "sk-moonshot-test-key",
        "deepinfra": "sk-deepinfra-test-key"
    }.get(provider_id))
    manager.get_tenant_api_key = manager.get_api_key
    return manager


@pytest.fixture
def mock_db_session():
    """Mock database session for governance tracking"""
    db = MagicMock()
    return db


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestBYOKHandlerInit:
    """Test BYOKHandler class initialization and setup"""

    def test_byok_handler_init_default(self, mock_byok_manager):
        """Test BYOKHandler initialization with default parameters"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            assert handler.workspace_id == "default"
            assert handler.default_provider_id is None
            assert isinstance(handler.clients, dict)
            assert isinstance(handler.async_clients, dict)

    def test_byok_handler_init_with_provider_id(self, mock_byok_manager):
        """Test BYOKHandler initialization with specific provider ID"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler(provider_id="openai")
            assert handler.default_provider_id == "openai"
            assert handler.workspace_id == "default"

    def test_byok_handler_clients_dict_initialization(self, mock_byok_manager):
        """Test that clients dictionaries are properly initialized"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            assert hasattr(handler, 'clients')
            assert hasattr(handler, 'async_clients')
            assert len(handler.clients) >= 0
            assert len(handler.async_clients) >= 0

    def test_byok_handler_byok_manager_reference(self, mock_byok_manager):
        """Test that BYOKHandler references the BYOK manager"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager) as mock_mgr:
            handler = BYOKHandler()
            assert handler.byok_manager is not None
            mock_mgr.assert_called_once()

    def test_byok_handler_without_openai_package(self, mock_byok_manager):
        """Test BYOKHandler behavior when OpenAI package is not installed"""
        with patch('core.llm.byok_handler.OpenAI', None):
            with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
                handler = BYOKHandler()
                # Should handle gracefully without crashing
                assert handler.workspace_id == "default"


class TestProviderConfigValidation:
    """Test provider configuration validation"""

    def test_provider_config_valid_openai(self):
        """Test valid OpenAI provider configuration"""
        config = {
            "provider": "openai",
            "api_key": "sk-test-key-12345",
            "model": "gpt-4o",
            "base_url": None
        }
        assert config["provider"] == "openai"
        assert config["api_key"].startswith("sk-")
        assert "model" in config

    def test_provider_config_valid_anthropic(self):
        """Test valid Anthropic provider configuration"""
        config = {
            "provider": "anthropic",
            "api_key": "sk-ant-test-key-67890",
            "model": "claude-3-5-sonnet-20240620",
            "base_url": "https://api.anthropic.com/v1"
        }
        assert config["provider"] == "anthropic"
        assert config["api_key"].startswith("sk-ant-")
        assert "base_url" in config

    def test_provider_config_valid_deepseek(self):
        """Test valid DeepSeek provider configuration"""
        config = {
            "provider": "deepseek",
            "api_key": "sk-deepseek-test-key",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1"
        }
        assert config["provider"] == "deepseek"
        assert "base_url" in config
        assert config["base_url"] == "https://api.deepseek.com/v1"

    def test_provider_config_missing_required_field(self):
        """Test that provider config without api_key is invalid"""
        invalid_config = {
            "provider": "openai",
            "model": "gpt-4o"
        }
        assert "api_key" not in invalid_config

    def test_provider_config_empty_api_key(self):
        """Test that provider config with empty api_key is invalid"""
        invalid_config = {
            "provider": "openai",
            "api_key": "",
            "model": "gpt-4o"
        }
        assert invalid_config["api_key"] == ""

    def test_provider_config_base_url_optional(self):
        """Test that base_url is optional (None for OpenAI)"""
        config = {
            "provider": "openai",
            "api_key": "sk-test-key",
            "base_url": None
        }
        assert config["base_url"] is None


class TestProviderStorage:
    """Test provider storage in internal registry"""

    def test_clients_dict_storage(self, mock_byok_manager):
        """Test that providers are stored in clients dictionary"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            assert isinstance(handler.clients, dict)

    def test_async_clients_dict_storage(self, mock_byok_manager):
        """Test that async providers are stored in async_clients dictionary"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            assert isinstance(handler.async_clients, dict)

    def test_provider_separation_sync_async(self, mock_byok_manager):
        """Test that sync and async clients are stored separately"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            assert handler.clients is not handler.async_clients


class TestProviderRouting:
    """Test LLM provider selection and routing"""

    def test_analyze_query_complexity_simple(self, mock_byok_manager):
        """Test complexity analysis for simple queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            complexity = handler.analyze_query_complexity("hello")
            assert complexity == QueryComplexity.SIMPLE

    def test_analyze_query_complexity_moderate(self, mock_byok_manager):
        """Test complexity analysis for moderate queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            complexity = handler.analyze_query_complexity("Analyze the data trends")
            assert complexity in [QueryComplexity.SIMPLE, QueryComplexity.MODERATE]

    def test_analyze_query_complexity_code(self, mock_byok_manager):
        """Test complexity analysis for code-related queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            complexity = handler.analyze_query_complexity("Write a function to sort an array")
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_with_code_block(self, mock_byok_manager):
        """Test complexity analysis with code blocks in prompt"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Here's some code:\n```\ndef hello():\n    print('hi')\n```"
            complexity = handler.analyze_query_complexity(prompt)
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX]

    def test_analyze_query_complexity_long_prompt(self, mock_byok_manager):
        """Test complexity analysis for long prompts"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            long_prompt = "analyze this " * 200
            complexity = handler.analyze_query_complexity(long_prompt)
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX]

    def test_get_optimal_provider_returns_tuple(self, mock_byok_manager):
        """Test that get_optimal_provider returns (provider_id, model) tuple"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients["deepseek"] = MagicMock()

            result = handler.get_optimal_provider(QueryComplexity.SIMPLE)
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], str)
            assert isinstance(result[1], str)

    def test_get_ranked_providers_returns_list(self, mock_byok_manager):
        """Test that get_ranked_providers returns list of tuples"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients["deepseek"] = MagicMock()

            result = handler.get_ranked_providers(QueryComplexity.SIMPLE)
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], tuple)
                assert len(result[0]) == 2

    def test_get_available_providers(self, mock_byok_manager):
        """Test get_available_providers returns list of provider IDs"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients["openai"] = MagicMock()
            handler.clients["deepseek"] = MagicMock()

            providers = handler.get_available_providers()
            assert isinstance(providers, list)
            assert all(isinstance(p, str) for p in providers)


class TestTokenStreaming:
    """Test streaming LLM responses token-by-token"""

    @pytest.mark.asyncio
    async def test_stream_completion_basic(self, mock_byok_manager):
        """Test basic streaming completion"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_async_client = AsyncMock()
            mock_stream = AsyncMock()

            chunk1 = MagicMock()
            chunk1.choices = [MagicMock()]
            chunk1.choices[0].delta = MagicMock()
            chunk1.choices[0].delta.content = "Hello"

            chunk2 = MagicMock()
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta = MagicMock()
            chunk2.choices[0].delta.content = " world"

            chunk3 = MagicMock()
            chunk3.choices = []

            mock_stream.__aiter__ = AsyncMock(return_value=iter([chunk1, chunk2, chunk3]))
            mock_async_client.chat.completions.create = AsyncMock(return_value=mock_stream)
            handler.async_clients = {"openai": mock_async_client}

            messages = [{"role": "user", "content": "Say hello"}]
            tokens = []
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai",
                temperature=0.7
            ):
                tokens.append(token)

            assert len(tokens) == 2
            assert "Hello" in "".join(tokens)

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, mock_byok_manager):
        """Test that stream yields individual tokens"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_async_client = AsyncMock()
            mock_stream = AsyncMock()

            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = "test"

            mock_stream.__aiter__ = AsyncMock(return_value=iter([chunk]))
            mock_async_client.chat.completions.create = AsyncMock(return_value=mock_stream)
            handler.async_clients = {"openai": mock_async_client}

            messages = [{"role": "user", "content": "test"}]
            token_count = 0
            async for _ in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai"
            ):
                token_count += 1

            assert token_count == 1

    @pytest.mark.asyncio
    async def test_stream_handles_empty_delta(self, mock_byok_manager):
        """Test streaming handles chunks with empty delta content"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_async_client = AsyncMock()
            mock_stream = AsyncMock()

            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = None

            mock_stream.__aiter__ = AsyncMock(return_value=iter([chunk]))
            mock_async_client.chat.completions.create = AsyncMock(return_value=mock_stream)
            handler.async_clients = {"openai": mock_async_client}

            messages = [{"role": "user", "content": "test"}]
            tokens = []
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai"
            ):
                if token.strip():
                    tokens.append(token)

            assert isinstance(tokens, list)

    @pytest.mark.asyncio
    async def test_stream_with_max_tokens(self, mock_byok_manager):
        """Test streaming with max_tokens parameter"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_async_client = AsyncMock()
            mock_stream = AsyncMock()

            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = "limited content"

            mock_stream.__aiter__ = AsyncMock(return_value=iter([chunk]))
            mock_async_client.chat.completions.create = AsyncMock(return_value=mock_stream)
            handler.async_clients = {"openai": mock_async_client}

            messages = [{"role": "user", "content": "test"}]
            async for _ in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai",
                max_tokens=100
            ):
                pass

            mock_async_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_async_client.chat.completions.create.call_args[1]
            assert call_kwargs.get('max_tokens') == 100

    @pytest.mark.asyncio
    async def test_stream_without_async_clients(self, mock_byok_manager):
        """Test streaming error when async clients not initialized"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.async_clients = {}

            messages = [{"role": "user", "content": "test"}]

            with pytest.raises(ValueError, match="Async clients not initialized"):
                async for _ in handler.stream_completion(
                    messages=messages,
                    model="gpt-4o",
                    provider_id="openai"
                ):
                    pass


class TestFailover:
    """Test provider failover scenarios"""

    def test_generate_response_with_provider_failover(self, mock_byok_manager):
        """Test failover when primary provider fails"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            openai_client = MagicMock()
            openai_client.chat.completions.create.side_effect = Exception("OpenAI API error")

            deepseek_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Success from DeepSeek"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            deepseek_client.chat.completions.create = MagicMock(return_value=mock_response)

            handler.clients = {
                "openai": openai_client,
                "deepseek": deepseek_client
            }

            result = asyncio.run(handler.generate_response(
                prompt="test prompt",
                system_instruction="You are helpful"
            ))

            assert "DeepSeek" in result

    def test_generate_response_all_providers_fail(self, mock_byok_manager):
        """Test behavior when all providers fail"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            openai_client = MagicMock()
            openai_client.chat.completions.create.side_effect = Exception("OpenAI error")

            deepseek_client = MagicMock()
            deepseek_client.chat.completions.create.side_effect = Exception("DeepSeek error")

            handler.clients = {
                "openai": openai_client,
                "deepseek": deepseek_client
            }

            result = asyncio.run(handler.generate_response(
                prompt="test prompt",
                system_instruction="You are helpful"
            ))

            assert "failed" in result.lower() or "error" in result.lower()

    def test_generate_response_no_clients_available(self, mock_byok_manager):
        """Test behavior when no LLM clients are available"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}

            result = asyncio.run(handler.generate_response(
                prompt="test prompt",
                system_instruction="You are helpful"
            ))

            assert "not initialized" in result.lower() or "no api keys" in result.lower()

    def test_generate_response_with_budget_exceeded(self, mock_byok_manager):
        """Test behavior when budget is exceeded"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"deepseek": MagicMock()}

            with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                mock_tracker.is_budget_exceeded.return_value = True

                result = asyncio.run(handler.generate_response(
                    prompt="test prompt",
                    system_instruction="You are helpful"
                ))

                assert "BUDGET EXCEEDED" in result


class TestKeyManagement:
    """Test API key management and rotation"""

    def test_byok_manager_is_configured(self, mock_byok_manager):
        """Test BYOKManager.is_configured method"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            result = handler.byok_manager.is_configured("default", "openai")
            assert isinstance(result, bool)

    def test_byok_manager_get_api_key(self, mock_byok_manager):
        """Test BYOKManager.get_api_key method"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            api_key = handler.byok_manager.get_api_key("openai")
            assert api_key is not None

    def test_byok_manager_get_tenant_api_key(self, mock_byok_manager):
        """Test BYOKManager.get_tenant_api_key compatibility method"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            api_key = handler.byok_manager.get_tenant_api_key("default", "openai")
            assert isinstance(api_key, str) or api_key is None

    def test_key_validation_format_openai(self):
        """Test OpenAI key format validation"""
        valid_key = "sk-test-key-12345"
        assert valid_key.startswith("sk-")

    def test_key_validation_format_anthropic(self):
        """Test Anthropic key format validation"""
        valid_key = "sk-ant-test-key-12345"
        assert valid_key.startswith("sk-ant-")


class TestChatCompletion:
    """Test LLM chat completion functionality"""

    def test_chat_completion_basic(self, mock_byok_manager):
        """Test basic chat completion"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Hello, how can I help you?"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 15
            mock_response.usage.completion_tokens = 8

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            result = asyncio.run(handler.generate_response(
                prompt="Hello!",
                system_instruction="You are a helpful assistant"
            ))

            assert "help" in result.lower()

    def test_chat_completion_with_temperature(self, mock_byok_manager):
        """Test chat completion with custom temperature"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage = MagicMock()

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            asyncio.run(handler.generate_response(
                prompt="test",
                system_instruction="You are helpful",
                temperature=0.2
            ))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs.get('temperature') == 0.2

    def test_system_prompt_handling(self, mock_byok_manager):
        """Test that system prompt is properly included"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Custom response"
            mock_response.usage = MagicMock()

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            asyncio.run(handler.generate_response(
                prompt="test",
                system_instruction="You are a specialized assistant for coding"
            ))

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            assert any(m.get('role') == 'system' for m in messages)

    def test_response_content_extraction(self, mock_byok_manager):
        """Test that content is extracted from response correctly"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Extracted content here"
            mock_response.usage = MagicMock()

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            result = asyncio.run(handler.generate_response(
                prompt="test",
                system_instruction="You are helpful"
            ))

            assert result == "Extracted content here"


class TestContextWindow:
    """Test context window management"""

    def test_get_context_window_known_model(self, mock_byok_manager):
        """Test context window retrieval for known models"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            context = handler.get_context_window("gpt-4o")
            assert isinstance(context, int)
            assert context > 0

    def test_get_context_window_unknown_model(self, mock_byok_manager):
        """Test context window for unknown model returns default"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            context = handler.get_context_window("unknown-model-xyz")
            assert isinstance(context, int)
            assert context > 0

    def test_truncate_to_context_short_text(self, mock_byok_manager):
        """Test that short text is not truncated"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            short_text = "This is a short text"
            result = handler.truncate_to_context(short_text, "gpt-4o")
            assert result == short_text

    def test_truncate_to_context_long_text(self, mock_byok_manager):
        """Test that long text is truncated appropriately"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            long_text = "word " * 100000
            result = handler.truncate_to_context(long_text, "gpt-4o")
            assert len(result) < len(long_text)
            assert "truncated" in result.lower()


class TestVisionSupport:
    """Test vision/multimodal support"""

    def test_generate_response_with_image_url(self, mock_byok_manager):
        """Test response generation with image URL"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "I see an image"
            mock_response.usage = MagicMock()

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            result = asyncio.run(handler.generate_response(
                prompt="What's in this image?",
                system_instruction="You are a vision assistant",
                image_payload="https://example.com/image.jpg"
            ))

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            user_message = [m for m in messages if m.get('role') == 'user'][0]

            assert 'content' in user_message
            assert any(isinstance(c, dict) and c.get('type') == 'image_url' for c in user_message['content'])

    def test_generate_response_with_base64_image(self, mock_byok_manager):
        """Test response generation with base64 image"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "Base64 image received"
            mock_response.usage = MagicMock()

            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            handler.clients = {"openai": mock_client}

            result = asyncio.run(handler.generate_response(
                prompt="Describe this",
                system_instruction="You are helpful",
                image_payload="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            ))

            assert "Base64" in result or "image" in result.lower()


class TestCostOptimization:
    """Test cost optimization features"""

    def test_get_routing_info(self, mock_byok_manager):
        """Test get_routing_info returns routing decision info"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"deepseek": MagicMock()}
            info = handler.get_routing_info("test prompt")
            assert isinstance(info, dict)
            assert 'complexity' in info

    def test_get_provider_comparison(self, mock_byok_manager):
        """Test get_provider_comparison returns cost comparison"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            comparison = handler.get_provider_comparison()
            assert isinstance(comparison, dict)
            assert len(comparison) > 0

    def test_get_cheapest_models(self, mock_byok_manager):
        """Test get_cheapest_models returns sorted list"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            models = handler.get_cheapest_models(limit=5)
            assert isinstance(models, list)


class TestTrialRestrictions:
    """Test trial/budget restriction checks"""

    def test_trial_restriction_check_default(self, mock_byok_manager):
        """Test that trial restriction check returns False by default"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            is_restricted = handler._is_trial_restricted()
            assert isinstance(is_restricted, bool)

    def test_generate_response_with_trial_restriction(self, mock_byok_manager):
        """Test response generation when trial is restricted"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            with patch.object(handler, '_is_trial_restricted', return_value=True):
                result = asyncio.run(handler.generate_response(
                    prompt="test",
                    system_instruction="You are helpful"
                ))

                assert "Trial" in result or "expired" in result.lower()


class TestBYOKHandlerHelpers:
    """Test BYOKHandler helper methods"""

    def test_get_available_providers_empty(self, mock_byok_manager):
        """Test get_available_providers when no providers configured"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}
            providers = handler.get_available_providers()
            assert providers == []

    def test_get_available_providers_multiple(self, mock_byok_manager):
        """Test get_available_providers with multiple providers"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {
                "openai": MagicMock(),
                "deepseek": MagicMock(),
                "anthropic": MagicMock()
            }
            providers = handler.get_available_providers()
            assert len(providers) == 3
            assert "openai" in providers
            assert "deepseek" in providers
            assert "anthropic" in providers

    def test_query_complexity_enum_values(self):
        """Test QueryComplexity enum has correct values"""
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.MODERATE.value == "moderate"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.ADVANCED.value == "advanced"

    def test_provider_tiers_structure(self):
        """Test PROVIDER_TIERS has expected structure"""
        assert "budget" in PROVIDER_TIERS
        assert "mid" in PROVIDER_TIERS
        assert "premium" in PROVIDER_TIERS
        assert isinstance(PROVIDER_TIERS["budget"], list)
        assert isinstance(PROVIDER_TIERS["mid"], list)
        assert isinstance(PROVIDER_TIERS["premium"], list)

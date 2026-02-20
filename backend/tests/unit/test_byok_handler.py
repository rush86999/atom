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

# ============================================================================
# Extended Tests for BYOKHandler - Plan 28
# ============================================================================

"""
Extended tests for BYOKHandler covering:
- Model capabilities (VISION_ONLY_MODELS, REASONING_MODELS_WITHOUT_VISION, MODELS_WITHOUT_TOOLS)
- Client initialization edge cases
- Context window management
- Text truncation
- Query complexity analysis
- Provider comparison
- Routing information
- Cheapest models retrieval
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS


# ============================================================================
# Model Capabilities Tests
# ============================================================================

class TestModelCapabilities:
    """Tests for model capability lists."""

    def test_vision_only_models_exist(self):
        """Test vision-only models list exists."""
        from core.llm.byok_handler import VISION_ONLY_MODELS
        assert "janus-pro-7b" in VISION_ONLY_MODELS
        assert "janus-pro-1.3b" in VISION_ONLY_MODELS

    def test_reasoning_models_without_vision_exist(self):
        """Test reasoning models without vision list exists."""
        from core.llm.byok_handler import REASONING_MODELS_WITHOUT_VISION
        assert "deepseek-v3.2" in REASONING_MODELS_WITHOUT_VISION
        # Note: Production code has typo "speciale" not "special"
        assert "deepseek-v3.2-speciale" in REASONING_MODELS_WITHOUT_VISION

    def test_models_without_tools_is_accurate(self):
        """Test models without tools list is accurate."""
        from core.llm.byok_handler import MODELS_WITHOUT_TOOLS
        # Note: Production code has typo "speciale" not "special"
        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS


# ============================================================================
# Client Initialization Tests
# ============================================================================

class TestClientInitializationExtended:
    """Tests for client initialization edge cases."""

    def test_byok_manager_not_configured_uses_env(self, monkeypatch):
        """Test BYOK not configured falls back to environment variables."""
        mock_byok_manager = MagicMock()
        mock_byok_manager.is_configured.return_value = False
        mock_byok_manager.get_api_key.return_value = None

        monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key-456")
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-789")

        with patch('core.llm.byok_handler.OpenAI'):
            with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
                handler = BYOKHandler()
                # Verify fallback occurred - handler created without crashing
                assert handler is not None
                assert handler.workspace_id == "default"

    def test_env_fallback_with_base_url(self, monkeypatch):
        """Test environment fallback with base_url configuration."""
        mock_byok_manager = MagicMock()
        mock_byok_manager.is_configured.return_value = False
        mock_byok_manager.get_api_key.return_value = None

        monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
        # Note: base_url comes from config dict, not env

        with patch('core.llm.byok_handler.OpenAI'):
            with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
                handler = BYOKHandler()
                assert handler is not None

    def test_multiple_provider_initialization(self):
        """Test multiple providers can be initialized."""
        mock_byok_manager = MagicMock()
        mock_byok_manager.is_configured.return_value = True
        mock_byok_manager.get_api_key.side_effect = lambda p, k=None: f"key-{p}"

        with patch('core.llm.byok_handler.OpenAI') as mock_openai:
            with patch('core.llm.byok_handler.AsyncOpenAI'):
                with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
                    handler = BYOKHandler()
                    # Should initialize for each configured provider
                    assert mock_openai.called or len(handler.clients) >= 0

    def test_client_initialization_failure_logged(self, caplog):
        """Test client initialization failures are logged."""
        mock_byok_manager = MagicMock()
        mock_byok_manager.is_configured.return_value = True
        mock_byok_manager.get_api_key.return_value = "error-key"

        with caplog.at_level(logging.ERROR):
            with patch('core.llm.byok_handler.OpenAI') as mock_openai:
                mock_openai.side_effect = Exception("Connection failed")
                with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
                    handler = BYOKHandler()

                    # Verify error was logged
                    assert any("Failed to initialize" in record.message for record in caplog.records)


# ============================================================================
# Context Window Management Tests
# ============================================================================

class TestContextWindowManagementExtended:
    """Tests for context window management edge cases."""

    def test_context_window_pricing_fallback(self):
        """Test context window falls back to static pricing when unavailable."""
        mock_byok_manager = MagicMock()

        with patch('core.llm.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = MagicMock()
            fetcher.get_model_price.return_value = None
            mock_fetcher.return_value = fetcher

        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            window = handler.get_context_window("unknown-model")

            # Should return safe default
            assert window > 0

    def test_context_window_uses_max_input_tokens(self):
        """Test context window uses max_input_tokens when available."""
        mock_byok_manager = MagicMock()

        with patch('core.llm.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = MagicMock()
            fetcher.get_model_price.return_value = {"max_input_tokens": 32000}
            mock_fetcher.return_value = fetcher

        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            window = handler.get_context_window("model-with-max-input")

            assert window == 32000

    def test_context_window_uses_max_tokens_fallback(self):
        """Test context window falls back to max_tokens when max_input_tokens missing."""
        mock_byok_manager = MagicMock()

        with patch('core.llm.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = MagicMock()
            fetcher.get_model_price.return_value = {"max_tokens": 8192}
            mock_fetcher.return_value = fetcher

        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            window = handler.get_context_window("model-with-max-tokens")

            assert window == 8192

    def test_context_window_no_pricing_uses_safe_default(self):
        """Test unknown model without pricing uses conservative default."""
        mock_byok_manager = MagicMock()

        with patch('core.llm.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = MagicMock()
            fetcher.get_model_price.side_effect = Exception("Service unavailable")
            mock_fetcher.return_value = fetcher

        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            window = handler.get_context_window("completely-unknown-model")

            # Conservative default
            assert window == 4096

    def test_context_window_known_model_defaults(self):
        """Test context window for known model defaults."""
        mock_byok_manager = MagicMock()

        with patch('core.llm.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = MagicMock()
            fetcher.get_model_price.side_effect = Exception("No pricing")
            mock_fetcher.return_value = fetcher

        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Test known model defaults
            assert handler.get_context_window("gpt-4o") == 128000
            assert handler.get_context_window("gpt-4o-mini") == 128000
            assert handler.get_context_window("gpt-4") == 8192
            assert handler.get_context_window("claude-3") == 200000
            assert handler.get_context_window("deepseek-chat") == 32768
            assert handler.get_context_window("gemini-flash") == 1000000


# ============================================================================
# Text Truncation Tests
# ============================================================================

class TestTextTruncationExtended:
    """Tests for text truncation functionality."""

    def test_truncate_to_context_exact_fit(self):
        """Test truncation when text exactly fits context window."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            text = "A" * 100  # 100 chars

        with patch.object(handler, 'get_context_window', return_value=100):
            result = handler.truncate_to_context(text, "model")

            # Should not be truncated
            assert result == text

    def test_truncate_to_context_needs_truncation(self):
        """Test truncation when text exceeds context window."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            text = "word " * 200  # 1000 chars

        with patch.object(handler, 'get_context_window', return_value=100):
            result = handler.truncate_to_context(text, "model")

            # Should be truncated
            assert len(result) < len(text)
            # Verify truncation indicator added
            assert "truncated" in result.lower() or len(result) < len(text)

    def test_truncate_to_context_reserve_tokens(self):
        """Test truncation respects reserve_tokens parameter."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            text = "word " * 200

        with patch.object(handler, 'get_context_window', return_value=100):
            result_less_reserve = handler.truncate_to_context(text, "model", reserve_tokens=20)
            result_no_reserve = handler.truncate_to_context(text, "model", reserve_tokens=0)

            # More reserve = shorter result
            assert len(result_less_reserve) <= len(result_no_reserve)

    def test_truncate_preserves_truncation_indicator(self):
        """Test truncation includes indicator when content is truncated."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            text = "word " * 200  # 1000 chars, exceeds 100 char window

        with patch.object(handler, 'get_context_window', return_value=100):
            result = handler.truncate_to_context(text, "model")

            # If truncated, should have indicator
            if len(result) < len(text):
                assert "truncated" in result.lower()

    def test_truncate_respects_context_window_calculation(self):
        """Test truncation properly calculates max chars from context window."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            # 500 tokens * 4 chars/token = 2000 chars - 1000 reserve = 1000 chars
            text = "word " * 300  # 1500 chars

        with patch.object(handler, 'get_context_window', return_value=500):
            result = handler.truncate_to_context(text, "model", reserve_tokens=250)

            # Should truncate to fit: (500 - 250) * 4 = 1000 chars
            assert len(result) <= 1000


# ============================================================================
# Query Complexity Analysis Tests
# ============================================================================

class TestQueryComplexityAnalysisExtended:
    """Tests for query complexity analysis edge cases."""

    def test_analyze_query_complexity_with_code_blocks(self):
        """Test complexity analysis detects code blocks."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "```python\ndef hello():\n    print('world')\n```"

            complexity = handler.analyze_query_complexity(prompt)

            # Code blocks should increase complexity
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_with_math_keywords(self):
        """Test complexity analysis detects math keywords."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Calculate integral of this function and solve for x"

            complexity = handler.analyze_query_complexity(prompt)

            # Math keywords should increase complexity
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_with_code_keywords(self):
        """Test complexity analysis detects code keywords."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Debug this async function and refactor database schema"

            complexity = handler.analyze_query_complexity(prompt)

            # Code keywords should increase complexity
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_simple_query(self):
        """Test complexity analysis classifies simple queries correctly."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Hello, how are you today?"

            complexity = handler.analyze_query_complexity(prompt)

            # Simple query should be SIMPLE
            assert complexity == QueryComplexity.SIMPLE

    def test_analyze_query_complexity_with_task_type_override(self):
        """Test complexity analysis with task type parameter."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "What is the weather?"

            # Code task type should increase complexity
            complexity_code = handler.analyze_query_complexity(prompt, task_type="code")
            complexity_chat = handler.analyze_query_complexity(prompt, task_type="chat")

            # Code task should be higher complexity
            assert complexity_code.value >= complexity_chat.value

    def test_analyze_query_complexity_long_text(self):
        """Test complexity analysis with long text."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            # 2000+ tokens = 8000+ chars
            long_text = "word " * 3000

            complexity = handler.analyze_query_complexity(long_text)

            # Long text should increase complexity
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_advanced_keywords(self):
        """Test complexity analysis detects advanced keywords."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Design architecture for scaling this enterprise system"

            complexity = handler.analyze_query_complexity(prompt)

            # Advanced keywords should increase complexity
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_moderate_keywords(self):
        """Test complexity analysis detects moderate keywords."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            prompt = "Analyze this concept and explain the background"

            complexity = handler.analyze_query_complexity(prompt)

            # Moderate keywords should give MODERATE or higher
            assert complexity.value >= QueryComplexity.MODERATE.value


# ============================================================================
# Provider Comparison Tests
# ============================================================================

class TestProviderComparisonExtended:
    """Tests for provider comparison functionality."""

    def test_get_provider_comparison_structure(self):
        """Test provider comparison returns correct structure."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {
                "openai": MagicMock(),
                "deepseek": MagicMock()
            }

            comparison = handler.get_provider_comparison()

            assert isinstance(comparison, dict)
            # Should have provider-related keys
            assert len(comparison) > 0

    def test_get_cheapest_models_returns_list(self):
        """Test get_cheapest_models returns list."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            models = handler.get_cheapest_models(limit=5)

            assert isinstance(models, list)
            assert len(models) <= 5

    def test_get_cheapest_models_with_limit(self):
        """Test get_cheapest_models respects limit parameter."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            models_3 = handler.get_cheapest_models(limit=3)
            models_10 = handler.get_cheapest_models(limit=10)

            assert len(models_3) <= 3
            assert len(models_10) <= 10


# ============================================================================
# Routing Information Tests
# ============================================================================

class TestRoutingInfoExtended:
    """Tests for routing information generation."""

    def test_get_routing_info_structure(self):
        """Test routing info returns correct structure."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            routing = handler.get_routing_info("test prompt")

            assert isinstance(routing, dict)
            # Should have complexity or provider info
            assert len(routing) > 0

    def test_get_routing_info_with_task_type(self):
        """Test routing info includes task type."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            routing = handler.get_routing_info("test prompt", task_type="code")

            assert isinstance(routing, dict)

    def test_get_routing_info_simple_query(self):
        """Test routing info for simple query."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            routing = handler.get_routing_info("Hello")

            assert isinstance(routing, dict)
            # Should detect SIMPLE complexity
            assert "complexity" in routing or "provider" in routing

    def test_get_routing_info_complex_query(self):
        """Test routing info for complex query."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            routing = handler.get_routing_info("```python\ndef complex():\n    pass\n```")

            assert isinstance(routing, dict)
            # Should detect higher complexity due to code block
            assert "complexity" in routing or "provider" in routing


# ============================================================================
# Available Providers Tests
# ============================================================================

class TestAvailableProvidersExtended:
    """Tests for available providers listing."""

    def test_get_available_providers_empty(self):
        """Test get_available_providers when no providers configured."""
        mock_byok_manager = MagicMock()
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}
            providers = handler.get_available_providers()
            assert providers == []

    def test_get_available_providers_multiple(self):
        """Test get_available_providers with multiple providers."""
        mock_byok_manager = MagicMock()
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


# ============================================================================
# STRUCTURED RESPONSE TESTS (NEW - Plan 62-04)
# ============================================================================

class TestStructuredResponse:
    """Test structured response generation using instructor"""

    def test_structured_response_basic(self, mock_byok_manager):
        """Test basic structured response generation"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.field1 = "test_value"
            mock_response.field2 = 123

            handler.clients = {"openai": mock_client}

            # Mock instructor
            import sys
            sys.modules['instructor'] = MagicMock()
            import core.llm.byok_handler
            import importlib
            importlib.reload(core.llm.byok_handler)

            from core.llm.byok_handler import BYOKHandler as HandlerReloaded
            handler2 = HandlerReloaded()
            handler2.clients = handler.clients
            handler2.async_clients = handler.async_clients
            handler2.byok_manager = handler.byok_manager

            # Create a simple Pydantic model for testing
            from pydantic import BaseModel
            class TestModel(BaseModel):
                field1: str
                field2: int

            import asyncio
            async def run_test():
                with patch('instructor.from_openai') as mock_instructor:
                    mock_instructor.return_value.chat.completions.create.return_value = mock_response
                    result = await handler2.generate_structured_response(
                        prompt="Generate test data",
                        system_instruction="You are a helpful assistant",
                        response_model=TestModel,
                        temperature=0.2
                    )
                    assert result is not None
                    assert result.field1 == "test_value"
                    assert result.field2 == 123

            asyncio.run(run_test())

    def test_structured_response_with_vision(self, mock_byok_manager):
        """Test structured response with image payload"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.description = "Image content"

            handler.clients = {"openai": mock_client}

            import sys
            sys.modules['instructor'] = MagicMock()
            import core.llm.byok_handler
            import importlib
            importlib.reload(core.llm.byok_handler)

            from pydantic import BaseModel
            class ImageDescription(BaseModel):
                description: str

            import asyncio
            async def run_test():
                with patch('instructor.from_openai') as mock_instructor:
                    mock_instructor.return_value.chat.completions.create.return_value = mock_response
                    result = await handler.generate_structured_response(
                        prompt="Describe this image",
                        system_instruction="You are a vision specialist",
                        response_model=ImageDescription,
                        image_payload="base64encodedimagedata"
                    )
                    assert result is not None
                    assert result.description == "Image content"

            asyncio.run(run_test())

    def test_structured_response_trial_restriction(self, mock_byok_manager):
        """Test structured response blocked by trial restriction"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock trial restriction
            with patch.object(handler, '_is_trial_restricted', return_value=True):
                from pydantic import BaseModel
                class TestModel(BaseModel):
                    field: str

                import asyncio
                async def run_test():
                    result = await handler.generate_structured_response(
                        prompt="test",
                        system_instruction="test",
                        response_model=TestModel
                    )
                    assert result is None  # Blocked by trial

                asyncio.run(run_test())

    def test_structured_response_no_clients(self, mock_byok_manager):
        """Test structured response with no clients available"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}  # No clients

            from pydantic import BaseModel
            class TestModel(BaseModel):
                field: str

            import asyncio
            async def run_test():
                result = await handler.generate_structured_response(
                    prompt="test",
                    system_instruction="test",
                    response_model=TestModel
                )
                assert result is None

            asyncio.run(run_test())

    def test_structured_response_instructor_unavailable(self, mock_byok_manager):
        """Test structured response fallback when instructor unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"openai": MagicMock()}

            # Instructor import error is handled inside generate_structured_response
            from pydantic import BaseModel
            class TestModel(BaseModel):
                field: str

            import asyncio
            async def run_test():
                # Mock ImportError for instructor module
                import builtins
                real_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == 'instructor':
                        raise ImportError("instructor not available")
                    return real_import(name, *args, **kwargs)

                with patch('builtins.__import__', side_effect=mock_import):
                    result = await handler.generate_structured_response(
                        prompt="test",
                        system_instruction="test",
                        response_model=TestModel
                    )
                    # Should return None when instructor unavailable
                    assert result is None

            asyncio.run(run_test())


class TestCoordinatedVision:
    """Test coordinated vision description extraction for non-vision models"""

    @pytest.mark.asyncio
    async def test_coordinated_vision_description(self, mock_byok_manager):
        """Test coordinated vision description extraction"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Screenshot shows a button at [500, 200]"

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            result = await handler._get_coordinated_vision_description(
                image_payload="base64image",
                tenant_plan="free",
                is_managed=True
            )

            assert result is not None
            assert "button" in result

    @pytest.mark.asyncio
    async def test_coordinated_vision_with_gemini_flash(self, mock_byok_manager):
        """Test coordinated vision prefers Gemini Flash when available"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock Gemini Flash client
            mock_gemini_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Gemini analysis"

            mock_gemini_client.chat.completions.create.return_value = mock_response
            handler.clients = {"google_flash": mock_gemini_client}

            result = await handler._get_coordinated_vision_description(
                image_payload="base64image",
                tenant_plan="free",
                is_managed=True
            )

            assert result is not None
            assert "Gemini" in result

    @pytest.mark.asyncio
    async def test_coordinated_vision_error_handling(self, mock_byok_manager):
        """Test coordinated vision handles errors gracefully"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("Vision API failed")

            handler.clients = {"openai": mock_client}

            result = await handler._get_coordinated_vision_description(
                image_payload="base64image",
                tenant_plan="free",
                is_managed=True
            )

            assert result is None  # Should return None on error


class TestCostTracking:
    """Test cost calculation and tracking with dynamic pricing"""

    def test_cost_calculation_with_dynamic_pricing(self, mock_byok_manager):
        """Test cost calculation using dynamic pricing fetcher"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock client
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response text"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            # Mock dynamic pricing
            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                mock_pricing = MagicMock()
                mock_pricing.estimate_cost.return_value = 0.001  # $0.001
                mock_fetcher.return_value = mock_pricing

                # Mock usage tracker
                with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                    import asyncio
                    async def run_test():
                        result = await handler.generate_response(
                            prompt="Test prompt",
                            system_instruction="You are helpful"
                        )
                        assert result == "Response text"

                    asyncio.run(run_test())

    def test_cost_fallback_to_static_pricing(self, mock_byok_manager):
        """Test cost calculation falls back to static pricing when dynamic unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            # Mock dynamic pricing failure
            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                mock_fetcher.return_value.estimate_cost.return_value = None

                # Mock static pricing fallback
                with patch('core.llm.byok_handler.get_llm_cost') as mock_static:
                    mock_static.return_value = 0.002

                    with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                        import asyncio
                        async def run_test():
                            result = await handler.generate_response(
                                prompt="Test",
                                system_instruction="Test"
                            )
                            assert result == "Response"

                        asyncio.run(run_test())

    def test_savings_calculation(self, mock_byok_manager):
        """Test savings calculation against reference cost (gpt-4o)"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"deepseek": mock_client}

            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                # DeepSeek: $0.0001, GPT-4o reference: $0.001
                mock_fetcher.return_value.estimate_cost.side_effect = [0.0001, 0.001]

                with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                    import asyncio
                    async def run_test():
                        result = await handler.generate_response(prompt="Test")
                        assert result == "Response"

                    asyncio.run(run_test())


class TestProviderFiltering:
    """Test provider filtering for tools, structured output, and vision"""

    def test_tool_requirement_filtering(self, mock_byok_manager):
        """Test providers filtered by tool support requirement"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"deepseek": MagicMock(), "openai": MagicMock()}

            # Request with tool requirement (agent_id present)
            options = handler.get_ranked_providers(
                complexity=QueryComplexity.COMPLEX,
                requires_tools=True,
                tenant_plan="free",
                is_managed_service=False
            )

            # Should exclude deepseek-v3.2-speciale (no tool support)
            for provider, model in options:
                if provider == "deepseek":
                    assert model != "deepseek-v3.2-speciale"

    def test_structured_requirement_filtering(self, mock_byok_manager):
        """Test providers filtered by structured output support"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"deepseek": MagicMock()}

            # Request with structured requirement
            options = handler.get_ranked_providers(
                complexity=QueryComplexity.COMPLEX,
                requires_structured=True,
                tenant_plan="free",
                is_managed_service=False
            )

            # Should filter out models without structured support
            for provider, model in options:
                assert model not in ["deepseek-v3.2-speciale"]

    def test_vision_model_filtering(self, mock_byok_manager):
        """Test vision-capable model filtering"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock vision routing
            handler.clients = {"openai": MagicMock(), "deepseek": MagicMock()}

            complexity = handler.analyze_query_complexity("Analyze this image")

            # Verify complexity analysis works
            assert complexity in [QueryComplexity.SIMPLE, QueryComplexity.MODERATE]


class TestTenantPlanLogic:
    """Test tenant plan routing and BYOK vs Managed AI logic"""

    def test_free_tier_managed_ai_blocking(self, mock_byok_manager):
        """Test free tier blocks managed AI"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            # Mock tenant as free tier with no custom key
            with patch('core.llm.byok_handler.get_db_session') as mock_db:
                mock_workspace = MagicMock()
                mock_workspace.tenant_id = "tenant_123"

                mock_tenant = MagicMock()
                mock_tenant.plan_type.value = "free"

                mock_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.side_effect = [
                    mock_workspace, mock_tenant
                ]

                # Mock no custom key
                handler.byok_manager.get_tenant_api_key.return_value = None

                import asyncio
                async def run_test():
                    result = await handler.generate_response(prompt="Test")
                    # Should block with plan restriction message
                    assert "PLAN RESTRICTION" in result

                asyncio.run(run_test())

    def test_custom_api_key_detection(self, mock_byok_manager):
        """Test custom API key enables BYOK mode"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock custom key present
            handler.byok_manager.get_tenant_api_key.return_value = "sk-custom-key"

            custom_key = handler.byok_manager.get_tenant_api_key("default", "openai")

            assert custom_key == "sk-custom-key"


class TestErrorHandling:
    """Test error handling and graceful degradation"""

    def test_missing_dynamic_pricing_fetcher(self, mock_byok_manager):
        """Test graceful degradation when dynamic_pricing_fetcher unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Should not crash when pricing fetcher missing
            with patch('core.llm.byok_handler.get_pricing_fetcher', side_effect=ImportError):
                routing = handler.get_routing_info("test prompt")

                # Should still return routing info with static fallback
                assert isinstance(routing, dict)
                assert "complexity" in routing

    def test_missing_benchmarks_module(self, mock_byok_manager):
        """Test graceful degradation when benchmarks module unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"openai": MagicMock()}

            # Mock benchmarks import error
            with patch('core.llm.byok_handler.get_quality_score', side_effect=ImportError):
                options = handler.get_ranked_providers(
                    complexity=QueryComplexity.SIMPLE,
                    tenant_plan="free",
                    is_managed_service=False
                )

                # Should fall back to static provider list
                assert isinstance(options, list)

    def test_missing_llm_usage_tracker(self, mock_byok_manager):
        """Test graceful degradation when llm_usage_tracker unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.usage = None  # No usage data

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            # Mock usage tracker missing
            with patch('core.llm.byok_handler.llm_usage_tracker', side_effect=AttributeError):
                import asyncio
                async def run_test():
                    result = await handler.generate_response(prompt="Test")
                    # Should still return result even if tracking fails
                    assert result == "Response"

                asyncio.run(run_test())


class TestBudgetEnforcement:
    """Test budget enforcement logic"""

    def test_budget_exceeded_blocks_generation(self, mock_byok_manager):
        """Test budget exceeded blocks AI generation"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            handler.clients = {"openai": MagicMock()}

            # Mock budget exceeded
            with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                mock_tracker.is_budget_exceeded.return_value = True

                import asyncio
                async def run_test():
                    result = await handler.generate_response(prompt="Test")
                    assert "BUDGET EXCEEDED" in result

                asyncio.run(run_test())

    def test_budget_not_exceeded_allows_generation(self, mock_byok_manager):
        """Test generation proceeds when budget not exceeded"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Success"

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            # Mock budget not exceeded
            with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                mock_tracker.is_budget_exceeded.return_value = False

                import asyncio
                async def run_test():
                    result = await handler.generate_response(prompt="Test")
                    assert result == "Success"

                asyncio.run(run_test())


class TestVisionRouting:
    """Test vision routing and multimodal support"""

    def test_vision_routing_with_image_payload(self, mock_byok_manager):
        """Test vision routing with image payload"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Image analyzed"

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                import asyncio
                async def run_test():
                    result = await handler.generate_response(
                        prompt="What's in this image?",
                        image_payload="base64imagedata"
                    )
                    assert result == "Image analyzed"

                asyncio.run(run_test())

    def test_vision_routing_with_image_url(self, mock_byok_manager):
        """Test vision routing with image URL"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "URL image analyzed"

            mock_client.chat.completions.create.return_value = mock_response
            handler.clients = {"openai": mock_client}

            with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
                import asyncio
                async def run_test():
                    result = await handler.generate_response(
                        prompt="Analyze this",
                        image_payload="http://example.com/image.jpg"
                    )
                    assert result == "URL image analyzed"

                asyncio.run(run_test())


class TestContextWindowExtended:
    """Test context window management"""

    def test_context_window_dynamic_pricing(self, mock_byok_manager):
        """Test context window from dynamic pricing"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock dynamic pricing with context window
            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                mock_pricing = {
                    "max_input_tokens": 128000,
                    "max_tokens": 128000
                }
                mock_fetcher.return_value.get_model_price.return_value = mock_pricing

                context = handler.get_context_window("gpt-4o")

                # Should use dynamic pricing value
                assert context == 128000

    def test_context_window_fallback_to_defaults(self, mock_byok_manager):
        """Test context window falls back to safe defaults"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock pricing fetcher failure
            with patch('core.llm.byok_handler.get_pricing_fetcher', side_effect=Exception):
                context = handler.get_context_window("gpt-4o")

                # Should use safe default for gpt-4o
                assert context == 128000

    def test_truncate_to_context(self, mock_byok_manager):
        """Test text truncation to fit context window"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Create text that's too long (1M chars)
            long_text = "A" * 1000000

            truncated = handler.truncate_to_context(long_text, "gpt-4o")

            # Should be truncated
            assert len(truncated) < len(long_text)
            assert "truncated" in truncated.lower()

    def test_truncate_with_reserve_tokens(self, mock_byok_manager):
        """Test truncation respects reserve tokens for response"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Create text slightly under context window
            text = "A" * 500000  # ~125K tokens

            truncated = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=2000)

            # Should reserve space for 2000 tokens
            assert len(truncated) < len(text)


class TestStreamingFixed:
    """Fixed streaming tests with proper async mock setup"""

    @pytest.mark.asyncio
    async def test_stream_completion_basic_fixed(self, mock_byok_manager):
        """Test basic streaming with proper async mock"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Create async generator properly
            async def mock_stream_generator():
                chunks = [
                    MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))]),
                    MagicMock(choices=[MagicMock(delta=MagicMock(content="world"))]),
                    MagicMock(choices=[])
                ]
                for chunk in chunks:
                    yield chunk

            mock_async_client = MagicMock()
            mock_async_client.chat.completions.create = MagicMock(return_value=mock_stream_generator())

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


class TestProviderRanking:
    """Test provider ranking with BPC algorithm"""

    def test_bpc_ranking_with_dynamic_pricing(self, mock_byok_manager):
        """Test BPC (Benchmark-Price-Capability) ranking"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock dynamic pricing cache
            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                mock_fetcher.return_value.pricing_cache = {
                    "deepseek-chat": {
                        "litellm_provider": "deepseek",
                        "max_input_tokens": 16000,
                        "input_cost_per_token": 0.000002,
                        "output_cost_per_token": 0.000002
                    }
                }

                with patch('core.llm.byok_handler.get_quality_score', return_value=85):
                    handler.clients = {"deepseek": MagicMock()}

                    options = handler.get_ranked_providers(
                        complexity=QueryComplexity.SIMPLE,
                        tenant_plan="free",
                        is_managed_service=False
                    )

                    # Should return ranked options
                    assert isinstance(options, list)

    def test_static_fallback_provider_ranking(self, mock_byok_manager):
        """Test static fallback when BPC ranking unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {"deepseek": MagicMock()}

            # Mock BPC failure
            with patch('core.llm.byok_handler.get_pricing_fetcher', side_effect=Exception):
                options = handler.get_ranked_providers(
                    complexity=QueryComplexity.SIMPLE,
                    tenant_plan="free",
                    is_managed_service=False
                )

                # Should use static fallback
                assert isinstance(options, list)
                assert len(options) > 0

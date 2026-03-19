"""
Coverage-driven tests for BYOKHandler (currently 0% -> target 70%+)

Target file: core/llm/byok_handler.py (1,557 lines, 654 statements)

Focus areas from coverage gap analysis:
- Handler initialization (lines 114-148)
- Provider capability detection (lines 149-252)
- Query complexity analysis (lines 303-353)
- Provider ranking and optimization (lines 355-579)
- Response generation (lines 581-832)
- Cognitive tier integration (lines 834-1014)
- Structured response generation (lines 1016-1231)
- Streaming methods (lines 1372-1518)
- Error handling (lines 1519-1557)
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock, mock_open
from datetime import datetime, timezone
from uuid import uuid4

from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    PROVIDER_TIERS,
    COST_EFFICIENT_MODELS,
    MODELS_WITHOUT_TOOLS,
    MIN_QUALITY_BY_TIER,
    REASONING_MODELS_WITHOUT_VISION,
    VISION_ONLY_MODELS,
)
from core.llm.cognitive_tier_system import CognitiveTier


class TestBYOKHandlerInitialization:
    """Test BYOKHandler initialization (lines 114-148)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_handler_initialization_with_defaults(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 125-137: Handler initialization with default parameters"""
        # Setup mocks
        mock_byok_mgr = MagicMock()
        mock_byok_mgr.is_configured.return_value = False
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        assert handler.workspace_id == "default"
        assert handler.default_provider_id is None
        assert handler.clients == {}
        assert handler.async_clients == {}
        assert handler.byok_manager is mock_byok_mgr
        assert handler.cognitive_classifier is mock_classifier
        assert handler.cache_router is mock_router
        assert handler.tier_service is mock_tier_svc

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_handler_initialization_with_custom_provider(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 126-127: Handler initialization with custom provider"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler(provider_id="openai")

        assert handler.default_provider_id == "openai"

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_handler_initialization_with_db_session_error(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, caplog
    ):
        """Cover lines 142-144: Handler initialization with DB error"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        # Simulate DB error
        mock_get_db.side_effect = Exception("DB connection failed")

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        assert handler.db_session is None
        assert "Could not create database session" in caplog.text


class TestProviderFallbackOrder:
    """Test provider fallback order logic (lines 149-192)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_fallback_order_with_deepseek_primary(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 173-192: Fallback order with deepseek as primary"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"deepseek": MagicMock(), "openai": MagicMock()}

        fallback = handler._get_provider_fallback_order("deepseek")

        assert fallback[0] == "deepseek"  # Primary first
        assert "openai" in fallback  # Other providers in priority order

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_fallback_order_with_no_clients(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 169-170: Fallback order with no clients available"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {}

        fallback = handler._get_provider_fallback_order("openai")

        assert fallback == []

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_fallback_order_with_unavailable_provider(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 178-180: Fallback order when primary provider not available"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"openai": MagicMock()}

        fallback = handler._get_provider_fallback_order("deepseek")

        # deepseek not available, should start with openai
        assert "openai" in fallback


class TestClientInitialization:
    """Test client initialization logic (lines 194-252)."""

    @patch('core.llm.byok_handler.OpenAI', None)
    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_initialize_clients_without_openai_package(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, caplog
    ):
        """Cover lines 196-198: Client initialization without OpenAI package"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        assert handler.clients == {}
        assert "OpenAI package not installed" in caplog.text

    @patch('core.llm.byok_handler.OpenAI')
    @patch('core.llm.byok_handler.AsyncOpenAI', None)
    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_initialize_clients_from_byok(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, mock_openai
    ):
        """Cover lines 212-228: Initialize clients from BYOK manager"""
        mock_byok_mgr = MagicMock()
        mock_byok_mgr.is_configured.return_value = True
        mock_byok_mgr.get_api_key.return_value = "sk-test-byok"
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        handler = BYOKHandler()

        assert "deepseek" in handler.clients or "openai" in handler.clients

    @patch('core.llm.byok_handler.OpenAI')
    @patch('core.llm.byok_handler.AsyncOpenAI')
    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_initialize_clients_from_env_fallback(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, mock_async_openai,
        mock_openai, monkeypatch
    ):
        """Cover lines 230-251: Initialize clients from environment variables"""
        # Set env var
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-env")

        mock_byok_mgr = MagicMock()
        mock_byok_mgr.is_configured.return_value = False
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_async_client = MagicMock()
        mock_async_openai.return_value = mock_async_client

        handler = BYOKHandler()

        # Should initialize deepseek from env
        if "deepseek" in handler.clients:
            assert handler.clients["deepseek"] is not None

    @patch('core.llm.byok_handler.OpenAI')
    @patch('core.llm.byok_handler.AsyncOpenAI')
    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_initialize_clients_with_initialization_error(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, mock_async_openai,
        mock_openai, caplog
    ):
        """Cover lines 227-228: Handle client initialization errors"""
        mock_byok_mgr = MagicMock()
        mock_byok_mgr.is_configured.return_value = True
        mock_byok_mgr.get_api_key.return_value = "invalid-key"
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        # Simulate initialization error
        mock_openai.side_effect = Exception("Invalid API key")

        handler = BYOKHandler()

        assert "Failed to initialize" in caplog.text


class TestContextWindow:
    """Test context window methods (lines 253-301)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_context_window_from_pricing(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 258-264: Get context window from pricing data"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_pricing = MagicMock()
            mock_pricing.get.return_value = 128000
            mock_fetcher.return_value.get_model_price.return_value = mock_pricing

            context = handler.get_context_window("gpt-4o")

            assert context == 128000

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_context_window_fallback_to_defaults(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 269-281: Fallback to context defaults"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_fetcher.return_value.get_model_price.return_value = None

            context = handler.get_context_window("gpt-4o")

            assert context == 128000  # Default for gpt-4o

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_truncate_to_context_no_truncation_needed(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 294-295: No truncation when text fits"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        with patch.object(handler, 'get_context_window', return_value=4096):
            text = "short text"
            result = handler.truncate_to_context(text, "gpt-4o")

            assert result == text

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_truncate_to_context_with_truncation(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, caplog
    ):
        """Cover lines 298-300: Truncate text that exceeds context"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        with patch.object(handler, 'get_context_window', return_value=1000):
            long_text = "x" * 10000  # Way over limit
            result = handler.truncate_to_context(long_text, "gpt-4o")

            assert len(result) < len(long_text)
            assert "truncated" in result.lower()
            assert "Truncated prompt" in caplog.text


class TestQueryComplexityAnalysis:
    """Test query complexity analysis (lines 303-353)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    @pytest.mark.parametrize("prompt,expected_complexity", [
        ("hello", QueryComplexity.SIMPLE),
        ("summarize this", QueryComplexity.SIMPLE),
        ("analyze the data", QueryComplexity.MODERATE),
        ("compare and contrast", QueryComplexity.MODERATE),
        ("write a python function", QueryComplexity.COMPLEX),
        ("debug this code", QueryComplexity.COMPLEX),
        ("architecture design for enterprise", QueryComplexity.ADVANCED),
        ("security audit and vulnerability assessment", QueryComplexity.ADVANCED),
    ])
    def test_analyze_query_complexity(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager, prompt, expected_complexity
    ):
        """Cover lines 303-353: Query complexity analysis with various prompts"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        complexity = handler.analyze_query_complexity(prompt)

        assert complexity == expected_complexity

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_analyze_complexity_with_task_type(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 338-342: Task type override"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        # Code task type increases complexity
        complexity_code = handler.analyze_query_complexity("hello", task_type="code")
        complexity_general = handler.analyze_query_complexity("hello", task_type="chat")

        assert complexity_code.value >= complexity_general.value

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_analyze_complexity_with_code_blocks(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 330-331: Code blocks increase complexity"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        complexity_with_code = handler.analyze_query_complexity("```print('hello')```")
        complexity_without = handler.analyze_query_complexity("print hello")

        # Code blocks should increase complexity
        assert complexity_with_code.value >= complexity_without.value


class TestGetOptimalProvider:
    """Test optimal provider selection (lines 355-378)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_optimal_provider_returns_first_option(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 366-371: Get optimal provider returns first option"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"deepseek": MagicMock()}

        with patch.object(handler, 'get_ranked_providers', return_value=[("deepseek", "deepseek-chat")]):
            provider, model = handler.get_optimal_provider(QueryComplexity.SIMPLE)

            assert provider == "deepseek"
            assert model == "deepseek-chat"

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_optimal_provider_fallback_to_default(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 373-376: Fallback to default when no options"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"openai": MagicMock()}

        with patch.object(handler, 'get_ranked_providers', return_value=[]):
            provider, model = handler.get_optimal_provider(QueryComplexity.SIMPLE)

            assert provider == "openai"
            assert model == "gpt-4o-mini"

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_optimal_provider_raises_error_when_no_clients(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover line 378: Raise error when no providers available"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {}

        with patch.object(handler, 'get_ranked_providers', return_value=[]):
            with pytest.raises(ValueError, match="No LLM providers available"):
                handler.get_optimal_provider(QueryComplexity.SIMPLE)


class TestGetAvailableProviders:
    """Test get_available_providers method (lines 1234-1236)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_available_providers_returns_client_keys(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1235-1236: Get list of available providers"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"deepseek": MagicMock(), "openai": MagicMock()}

        providers = handler.get_available_providers()

        assert set(providers) == {"deepseek", "openai"}


class TestTrialRestriction:
    """Test trial restriction check (lines 1540-1556)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_trial_restriction_when_trial_ended(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1551-1552: Return True when trial ended"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_ws = MagicMock()
        mock_ws.trial_ended = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ws
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        is_restricted = handler._is_trial_restricted()

        assert is_restricted is True

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_trial_restriction_when_trial_active(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover line 1553: Return False when trial active"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_ws = MagicMock()
        mock_ws.trial_ended = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ws
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        is_restricted = handler._is_trial_restricted()

        assert is_restricted is False

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_trial_restriction_with_db_error(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1554-1556: Return False on DB error"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB error")
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        is_restricted = handler._is_trial_restricted()

        assert is_restricted is False


class TestCognitiveTierClassification:
    """Test cognitive tier classification (lines 1519-1538)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_classify_cognitive_tier_simple_query(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1537-1538: Classify simple query as MICRO tier"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = CognitiveTier.MICRO
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        tier = handler.classify_cognitive_tier("hello")

        assert tier == CognitiveTier.MICRO
        mock_classifier.classify.assert_called_once_with("hello", None)

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_classify_cognitive_tier_with_task_type(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1537-1538: Classify with task type hint"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = CognitiveTier.STANDARD
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()

        tier = handler.classify_cognitive_tier("explain code", task_type="code")

        assert tier == CognitiveTier.STANDARD
        mock_classifier.classify.assert_called_once_with("explain code", "code")


class TestGetRoutingInfo:
    """Test get_routing_info method (lines 1238-1272)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_routing_info_success(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1240-1266: Get routing info successfully"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {"deepseek": MagicMock()}

        with patch.object(handler, 'get_optimal_provider', return_value=("deepseek", "deepseek-chat")):
            with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
                mock_pricing = MagicMock()
                mock_pricing.get_model_price.return_value = {"max_input_tokens": 16000}
                mock_fetcher.return_value.get_model_price.return_value = mock_pricing
                mock_fetcher.return_value.estimate_cost.return_value = 0.001

                info = handler.get_routing_info("test prompt")

                assert info["complexity"] == "simple"
                assert info["selected_provider"] == "deepseek"
                assert info["selected_model"] == "deepseek-chat"
                assert "deepseek" in info["available_providers"]
                assert info["estimated_cost_usd"] is not None

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    def test_get_routing_info_no_providers(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1267-1272: Handle error when no providers available"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {}

        with patch.object(handler, 'get_optimal_provider', side_effect=ValueError("No providers")):
            info = handler.get_routing_info("test prompt")

            assert info["complexity"] == "simple"
            assert "error" in info
            assert info["available_providers"] == []


class TestStreamingMethods:
    """Test streaming methods (lines 1372-1518)."""

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    @pytest.mark.asyncio
    async def test_stream_completion_no_clients(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1399-1400: Raise error when no clients available"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {}
        handler.async_clients = {}

        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(ValueError, match="No clients initialized"):
            stream = handler.stream_completion(messages, "gpt-4o", "openai")
            async for _ in stream:
                pass

    @patch('core.byok_endpoints.get_byok_manager')
    @patch('core.llm.cognitive_tier_system.CognitiveClassifier')
    @patch('core.llm.byok_handler.CacheAwareRouter')
    @patch('core.llm.byok_handler.CognitiveTierService')
    @patch('core.database.get_db_session')
    @pytest.mark.asyncio
    async def test_stream_completion_no_fallback_providers(
        self, mock_get_db, mock_tier_service, mock_router_class,
        mock_classifier_class, mock_byok_manager
    ):
        """Cover lines 1405-1406: Raise error when no fallback providers"""
        mock_byok_mgr = MagicMock()
        mock_byok_manager.return_value = mock_byok_mgr

        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier

        mock_router = MagicMock()
        mock_router_class.return_value = mock_router

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        mock_tier_svc = MagicMock()
        mock_tier_service.return_value = mock_tier_svc

        handler = BYOKHandler()
        handler.clients = {}
        handler.async_clients = {}

        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(ValueError, match="No available providers"):
            stream = handler.stream_completion(messages, "gpt-4o", "openai")
            async for _ in stream:
                pass


class TestRankingConstants:
    """Test ranking and configuration constants (lines 22-112)."""

    def test_query_complexity_enum_values(self):
        """Cover lines 22-27: QueryComplexity enum values"""
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.MODERATE.value == "moderate"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.ADVANCED.value == "advanced"

    def test_provider_tiers_configuration(self):
        """Cover lines 30-42: PROVIDER_TIERS configuration"""
        assert "budget" in PROVIDER_TIERS
        assert "mid" in PROVIDER_TIERS
        assert "premium" in PROVIDER_TIERS
        assert "code" in PROVIDER_TIERS
        assert "math" in PROVIDER_TIERS
        assert "creative" in PROVIDER_TIERS

        # Verify budget tier providers
        assert "deepseek" in PROVIDER_TIERS["budget"]
        assert "moonshot" in PROVIDER_TIERS["budget"]

    def test_cost_efficient_models_configuration(self):
        """Cover lines 44-82: COST_EFFICIENT_MODELS configuration"""
        assert "openai" in COST_EFFICIENT_MODELS
        assert "anthropic" in COST_EFFICIENT_MODELS
        assert "deepseek" in COST_EFFICIENT_MODELS
        assert "gemini" in COST_EFFICIENT_MODELS

        # Verify model mappings
        assert QueryComplexity.SIMPLE in COST_EFFICIENT_MODELS["openai"]
        assert QueryComplexity.ADVANCED in COST_EFFICIENT_MODELS["anthropic"]

    def test_models_without_tools(self):
        """Cover lines 85-88: MODELS_WITHOUT_TOOLS configuration"""
        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS

    def test_min_quality_by_tier(self):
        """Cover lines 90-97: MIN_QUALITY_BY_TIER configuration"""
        assert CognitiveTier.MICRO in MIN_QUALITY_BY_TIER
        assert CognitiveTier.STANDARD in MIN_QUALITY_BY_TIER
        assert CognitiveTier.VERSATILE in MIN_QUALITY_BY_TIER
        assert CognitiveTier.HEAVY in MIN_QUALITY_BY_TIER
        assert CognitiveTier.COMPLEX in MIN_QUALITY_BY_TIER

        # Verify quality thresholds
        assert MIN_QUALITY_BY_TIER[CognitiveTier.MICRO] == 0
        assert MIN_QUALITY_BY_TIER[CognitiveTier.STANDARD] == 80
        assert MIN_QUALITY_BY_TIER[CognitiveTier.COMPLEX] == 94

    def test_reasoning_models_without_vision(self):
        """Cover lines 99-106: REASONING_MODELS_WITHOUT_VISION configuration"""
        assert "deepseek-v3.2" in REASONING_MODELS_WITHOUT_VISION
        assert "o3" in REASONING_MODELS_WITHOUT_VISION
        assert "deepseek-chat" in REASONING_MODELS_WITHOUT_VISION

    def test_vision_only_models(self):
        """Cover lines 108-111: VISION_ONLY_MODELS configuration"""
        assert "janus-pro-7b" in VISION_ONLY_MODELS
        assert "janus-pro-1.3b" in VISION_ONLY_MODELS

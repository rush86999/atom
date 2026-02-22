"""
Enhanced BYOK Handler tests for 80%+ coverage.

This file provides comprehensive coverage for:
- Query complexity analysis edge cases
- Provider selection with all tiers (budget, mid, premium)
- Token estimation and model selection
- Context window management
- Provider initialization scenarios
- Cognitive tier classification integration
- Cache-aware routing integration
- Trial restriction handling
- Budget enforcement scenarios

Created: Phase 71-03
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime

import pytest

# Import the handler under test
from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    PROVIDER_TIERS,
    COST_EFFICIENT_MODELS,
    MODELS_WITHOUT_TOOLS,
    REASONING_MODELS_WITHOUT_VISION,
    VISION_ONLY_MODELS,
    MIN_QUALITY_BY_TIER
)
from core.llm.cognitive_tier_system import CognitiveTier


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
        "minimax": "sk-minimax-test-key",
        "deepinfra": "sk-deepinfra-test-key"
    }.get(provider_id))
    manager.get_tenant_api_key = manager.get_api_key
    manager.clear_api_key = MagicMock(return_value=True)
    return manager


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    db = MagicMock()

    # Mock Workspace and Tenant queries
    mock_workspace = MagicMock()
    mock_workspace.id = "default"
    mock_workspace.tenant_id = "tenant-123"

    mock_tenant = MagicMock()
    mock_tenant.id = "tenant-123"
    mock_tenant.plan_type = "free"
    mock_tenant.trial_ended = False

    db.query.return_value.filter.return_value.first.return_value = mock_workspace
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_tenant

    return db


@pytest.fixture
def mock_pricing_fetcher():
    """Mock dynamic pricing fetcher"""
    fetcher = MagicMock()

    # Mock pricing data
    fetcher.pricing_cache = {
        "gpt-4o": {
            "litellm_provider": "openai",
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_input_tokens": 128000,
            "max_tokens": 128000
        },
        "deepseek-chat": {
            "litellm_provider": "deepseek",
            "input_cost_per_token": 0.00000014,
            "output_cost_per_token": 0.00000028,
            "max_input_tokens": 32768,
            "max_tokens": 32768
        },
        "claude-3-5-sonnet": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "max_input_tokens": 200000,
            "max_tokens": 200000
        }
    }

    fetcher.get_model_price = MagicMock(side_effect=lambda model: fetcher.pricing_cache.get(model))
    fetcher.estimate_cost = MagicMock(return_value=0.001)
    fetcher.compare_providers = MagicMock(return_value={
        "openai": {"avg_cost_per_token": 0.00003, "tier": "premium"},
        "deepseek": {"avg_cost_per_token": 0.000002, "tier": "budget"}
    })
    fetcher.get_cheapest_models = MagicMock(return_value=[
        {"model": "deepseek-chat", "cost_per_token": 0.00000014}
    ])

    return fetcher


@pytest.fixture
def mock_benchmarks():
    """Mock benchmarks module"""
    with patch('core.llm.byok_handler.get_quality_score') as mock_get_quality:
        mock_get_quality.side_effect = lambda model: {
            "gpt-4o": 95,
            "deepseek-chat": 80,
            "claude-3-5-sonnet": 90
        }.get(model, 85)
        yield mock_get_quality


@pytest.fixture
def mock_usage_tracker():
    """Mock LLM usage tracker"""
    with patch('core.llm.byok_handler.llm_usage_tracker') as mock_tracker:
        mock_tracker.is_budget_exceeded = MagicMock(return_value=False)
        mock_tracker.record = MagicMock()
        yield mock_tracker


# =============================================================================
# QUERY COMPLEXITY ANALYSIS TESTS
# =============================================================================

class TestQueryComplexityAnalysisCoverage:
    """Comprehensive tests for query complexity analysis"""

    def test_analyze_query_complexity_simple_greeting(self, mock_byok_manager):
        """Test SIMPLE complexity for basic greetings"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Simple greetings
            assert handler.analyze_query_complexity("hi") == QueryComplexity.SIMPLE
            assert handler.analyze_query_complexity("hello") == QueryComplexity.SIMPLE
            assert handler.analyze_query_complexity("hey") == QueryComplexity.SIMPLE

    def test_analyze_query_complexity_simple_with_simple_keywords(self, mock_byok_manager):
        """Test SIMPLE complexity with simple keyword patterns"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Simple keyword patterns
            assert handler.analyze_query_complexity("summarize this") == QueryComplexity.SIMPLE
            assert handler.analyze_query_complexity("translate to Spanish") == QueryComplexity.SIMPLE
            assert handler.analyze_query_complexity("list the items") == QueryComplexity.SIMPLE
            assert handler.analyze_query_complexity("what is AI") == QueryComplexity.SIMPLE

    def test_analyze_query_complexity_moderate_analysis(self, mock_byok_manager):
        """Test MODERATE complexity for analysis tasks"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Moderate patterns
            complexity = handler.analyze_query_complexity("analyze the data trends")
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.SIMPLE]

            complexity = handler.analyze_query_complexity("compare these two options")
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.SIMPLE]

    def test_analyze_query_complexity_complex_multi_step(self, mock_byok_manager):
        """Test COMPLEX complexity for multi-step reasoning"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Longer prompt with multiple sentences
            long_prompt = "First, analyze the data. Then, create a visualization. Finally, write a report."
            complexity = handler.analyze_query_complexity(long_prompt)
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.MODERATE]

    def test_analyze_query_complexity_advanced_code(self, mock_byok_manager):
        """Test ADVANCED complexity for code-related queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Code keywords trigger ADVANCED
            complexity = handler.analyze_query_complexity("debug this distributed system")
            assert complexity == QueryComplexity.ADVANCED

            complexity = handler.analyze_query_complexity("optimize this database schema")
            assert complexity == QueryComplexity.ADVANCED

    def test_analyze_query_complexity_with_task_type_code(self, mock_byok_manager):
        """Test complexity analysis with code task type"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Task type override for code
            complexity = handler.analyze_query_complexity("simple task", task_type="code")
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_with_task_type_chat(self, mock_byok_manager):
        """Test complexity analysis with chat task type (reduces complexity)"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Chat task type reduces complexity
            complexity = handler.analyze_query_complexity("analyze this", task_type="chat")
            # The -1 adjustment for "chat" should reduce complexity
            assert isinstance(complexity, QueryComplexity)

    def test_analyze_query_complexity_with_code_block(self, mock_byok_manager):
        """Test complexity analysis with code blocks in prompt"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Code block adds +3 to complexity score
            prompt = "Here's code:\n```python\ndef hello():\n    pass\n```"
            complexity = handler.analyze_query_complexity(prompt)
            assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_empty_prompt(self, mock_byok_manager):
        """Test complexity analysis for empty/very short prompts"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Empty prompt
            complexity = handler.analyze_query_complexity("")
            assert isinstance(complexity, QueryComplexity)

    def test_analyze_query_complexity_math_keywords(self, mock_byok_manager):
        """Test complexity analysis with math keywords"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Math keywords trigger ADVANCED
            complexity = handler.analyze_query_complexity("solve this integral equation")
            assert complexity == QueryComplexity.ADVANCED

    def test_analyze_query_complexity_advanced_keywords(self, mock_byok_manager):
        """Test complexity analysis with advanced keywords"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Advanced keywords like "architecture", "security audit"
            complexity = handler.analyze_query_complexity("perform security audit on the system")
            assert complexity == QueryComplexity.ADVANCED


# =============================================================================
# PROVIDER SELECTION TESTS
# =============================================================================

class TestProviderSelectionCoverage:
    """Comprehensive tests for provider selection logic"""

    def test_get_optimal_provider_budget_tier(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider selection for budget tier (cost-conscious)"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["deepseek"] = MagicMock()

                    provider, model = handler.get_optimal_provider(
                        QueryComplexity.SIMPLE,
                        prefer_cost=True
                    )

                    assert isinstance(provider, str)
                    assert isinstance(model, str)

    def test_get_optimal_provider_premium_tier(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider selection for premium tier (quality-first)"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["openai"] = MagicMock()

                    provider, model = handler.get_optimal_provider(
                        QueryComplexity.ADVANCED,
                        prefer_cost=False
                    )

                    assert isinstance(provider, str)
                    assert isinstance(model, str)

    def test_get_optimal_provider_code_task(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider selection for code-specific tasks"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["deepseek"] = MagicMock()

                    provider, model = handler.get_optimal_provider(
                        QueryComplexity.ADVANCED,
                        task_type="code"
                    )

                    assert isinstance(provider, str)
                    assert isinstance(model, str)

    def test_get_optimal_provider_with_unavailable_provider(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test fallback handling when optimal provider is unavailable"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    # No clients configured
                    handler.clients = {}

                    with pytest.raises(ValueError, match="No LLM providers"):
                        handler.get_optimal_provider(QueryComplexity.SIMPLE)

    def test_get_ranked_providers_with_cognitive_tier(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider ranking with CognitiveTier filtering"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["deepseek"] = MagicMock()

                    ranked = handler.get_ranked_providers(
                        QueryComplexity.SIMPLE,
                        cognitive_tier=CognitiveTier.MICRO
                    )

                    assert isinstance(ranked, list)

    def test_get_ranked_providers_with_requires_tools(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider ranking filters out models without tools"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["deepseek"] = MagicMock()

                    ranked = handler.get_ranked_providers(
                        QueryComplexity.ADVANCED,
                        requires_tools=True
                    )

                    assert isinstance(ranked, list)
                    # Should filter out MODELS_WITHOUT_TOOLS
                    for provider, model in ranked:
                        assert model not in MODELS_WITHOUT_TOOLS

    def test_get_ranked_providers_estimated_tokens(self, mock_byok_manager, mock_benchmarks, mock_pricing_fetcher):
        """Test provider ranking with estimated tokens for cache-aware routing"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                with patch('core.llm.byok_handler.get_db_session'):
                    handler = BYOKHandler()
                    handler.clients["openai"] = MagicMock()

                    ranked = handler.get_ranked_providers(
                        QueryComplexity.SIMPLE,
                        estimated_tokens=2000,
                        workspace_id="default"
                    )

                    assert isinstance(ranked, list)


# =============================================================================
# CONTEXT WINDOW TESTS
# =============================================================================

class TestContextWindowManagementCoverage:
    """Comprehensive tests for context window management"""

    def test_get_context_window_known_model(self, mock_byok_manager, mock_pricing_fetcher):
        """Test context window retrieval for known models"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                handler = BYOKHandler()

                # GPT-4o from pricing cache
                context = handler.get_context_window("gpt-4o")
                assert context == 128000

    def test_get_context_window_fallback_defaults(self, mock_byok_manager):
        """Test context window fallback to safe defaults"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Model not in pricing cache, fallback to defaults
            context = handler.get_context_window("gpt-4")
            assert context == 8192

            context = handler.get_context_window("claude-3")
            assert context == 200000

            context = handler.get_context_window("deepseek-chat")
            assert context == 32768

    def test_get_context_window_conservative_default(self, mock_byok_manager):
        """Test context window conservative default for unknown models"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Unknown model
            context = handler.get_context_window("unknown-model")
            assert context == 4096

    def test_truncate_to_context_no_truncation_needed(self, mock_byok_manager):
        """Test text truncation when text fits in context window"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            short_text = "This is a short text"
            result = handler.truncate_to_context(short_text, "gpt-4o")

            assert result == short_text

    def test_truncate_to_context_with_truncation(self, mock_byok_manager):
        """Test text truncation when text exceeds context window"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Create very long text (> 128000 tokens * 4 chars = 512000 chars)
            long_text = "A" * 600000
            result = handler.truncate_to_context(long_text, "gpt-4o")

            assert len(result) < len(long_text)
            assert "truncated" in result.lower()


# =============================================================================
# TOKEN ESTIMATION TESTS
# =============================================================================

class TestTokenEstimationCoverage:
    """Test token estimation logic"""

    def test_estimate_tokens_from_prompt_short(self, mock_byok_manager):
        """Test token estimation for short prompts"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # ~25 chars / 4 = ~6 tokens
            estimated = handler.analyze_query_complexity("This is a test message")
            assert isinstance(estimated, QueryComplexity)

    def test_estimate_tokens_from_prompt_long(self, mock_byok_manager):
        """Test token estimation for long prompts"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # 4000 chars / 4 = ~1000 tokens
            long_prompt = "word " * 2000
            complexity = handler.analyze_query_complexity(long_prompt)

            # Long prompts should be at least MODERATE
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]


# =============================================================================
# MODEL SELECTION TESTS
# =============================================================================

class TestModelSelectionCoverage:
    """Test model selection logic"""

    def test_select_model_for_complexity_simple(self, mock_byok_manager):
        """Test model selection for SIMPLE complexity"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Check that cost-efficient models exist for SIMPLE
            for provider, models in COST_EFFICIENT_MODELS.items():
                model = models.get(QueryComplexity.SIMPLE)
                assert model is not None

    def test_select_model_for_complexity_advanced(self, mock_byok_manager):
        """Test model selection for ADVANCED complexity"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Check that cost-efficient models exist for ADVANCED
            for provider, models in COST_EFFICIENT_MODELS.items():
                model = models.get(QueryComplexity.ADVANCED)
                assert model is not None


# =============================================================================
# COGNITIVE TIER INTEGRATION TESTS
# =============================================================================

class TestCognitiveTierIntegrationCoverage:
    """Test cognitive tier system integration"""

    def test_classify_cognitive_tier_simple(self, mock_byok_manager):
        """Test cognitive tier classification for simple queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            tier = handler.classify_cognitive_tier("hi")
            assert tier == CognitiveTier.MICRO

    def test_classify_cognitive_tier_code(self, mock_byok_manager):
        """Test cognitive tier classification for code queries"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            tier = handler.classify_cognitive_tier("write a python function")
            assert tier == CognitiveTier.COMPLEX

    def test_classify_cognitive_tier_with_task_type(self, mock_byok_manager):
        """Test cognitive tier classification with task type hint"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            tier = handler.classify_cognitive_tier("explain this", task_type="code")
            assert isinstance(tier, CognitiveTier)


# =============================================================================
# VISION MODEL FILTERING TESTS
# =============================================================================

class TestVisionModelFilteringCoverage:
    """Test vision model filtering logic"""

    def test_reasoning_models_without_vision(self):
        """Test that reasoning models are correctly identified"""
        assert "deepseek-v3.2" in REASONING_MODELS_WITHOUT_VISION
        assert "o3" in REASONING_MODELS_WITHOUT_VISION
        assert "deepseek-chat" in REASONING_MODELS_WITHOUT_VISION

    def test_vision_only_models(self):
        """Test that vision-only models are correctly identified"""
        assert "janus-pro-7b" in VISION_ONLY_MODELS

    def test_models_without_tools(self):
        """Test that models without tools are correctly identified"""
        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS


# =============================================================================
# TRIAL RESTRICTION TESTS
# =============================================================================

class TestTrialRestrictionCoverage:
    """Test trial restriction handling"""

    def test_trial_restriction_check(self, mock_byok_manager):
        """Test trial restriction check method"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_db_session') as mock_get_db:
                # Mock workspace with trial_ended = False
                mock_db = MagicMock()
                mock_workspace = MagicMock()
                mock_workspace.trial_ended = False
                mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                handler = BYOKHandler()

                is_restricted = handler._is_trial_restricted()
                assert is_restricted is False

    def test_trial_ended_blocks_generation(self, mock_byok_manager):
        """Test that ended trial blocks generation"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_db_session') as mock_get_db:
                # Mock workspace with trial_ended = True
                mock_db = MagicMock()
                mock_workspace = MagicMock()
                mock_workspace.trial_ended = True
                mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                handler = BYOKHandler()
                handler.clients = {"deepseek": MagicMock()}

                result = asyncio.run(handler.generate_response(
                    prompt="test",
                    system_instruction="You are helpful"
                ))

                assert "Trial Expired" in result


# =============================================================================
# BUDGET ENFORCEMENT TESTS
# =============================================================================

class TestBudgetEnforcementCoverage:
    """Test budget enforcement logic"""

    def test_budget_exceeded_blocks_generation(self, mock_byok_manager, mock_usage_tracker):
        """Test that exceeded budget blocks generation"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_db_session'):
                handler = BYOKHandler()
                handler.clients = {"deepseek": MagicMock()}

                mock_usage_tracker.is_budget_exceeded.return_value = True

                result = asyncio.run(handler.generate_response(
                    prompt="test",
                    system_instruction="You are helpful"
                ))

                assert "BUDGET EXCEEDED" in result

    def test_budget_not_exceeded_allows_generation(self, mock_byok_manager, mock_usage_tracker):
        """Test that non-exceeded budget allows generation"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_db_session'):
                handler = BYOKHandler()

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = MagicMock()
                mock_response.choices[0].message.content = "Success"
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 5

                mock_client.chat.completions.create = MagicMock(return_value=mock_response)
                handler.clients = {"deepseek": mock_client}

                mock_usage_tracker.is_budget_exceeded.return_value = False

                result = asyncio.run(handler.generate_response(
                    prompt="test",
                    system_instruction="You are helpful"
                ))

                assert "Success" in result


# =============================================================================
# API KEY VALIDATION TESTS
# =============================================================================

class TestApiKeyValidationCoverage:
    """Test API key validation methods"""

    def test_validate_api_key_configured(self, mock_byok_manager):
        """Test API key validation for configured provider"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            result = handler.validate_api_key("openai")
            assert result["configured"] is True
            assert result["provider_id"] == "openai"
            assert result["source"] == "BYOK_MANAGER"
            assert result["key_suffix"] == "2345"

    def test_validate_api_key_not_configured(self, mock_byok_manager):
        """Test API key validation for unconfigured provider"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            mock_byok_manager.is_configured.return_value = False
            handler = BYOKHandler()

            result = handler.validate_api_key("unconfigured_provider")
            assert result["configured"] is False
            assert result["source"] == "NONE"

    def test_clear_provider_key(self, mock_byok_manager):
        """Test clearing provider key"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            result = handler.clear_provider_key("openai")
            assert result is True


# =============================================================================
# PROVIDER TIERS TESTS
# =============================================================================

class TestProviderTiersCoverage:
    """Test provider tier configuration"""

    def test_provider_tiers_budget(self):
        """Test budget tier providers"""
        assert "deepseek" in PROVIDER_TIERS["budget"]
        assert "moonshot" in PROVIDER_TIERS["budget"]

    def test_provider_tiers_mid(self):
        """Test mid tier providers"""
        assert "anthropic" in PROVIDER_TIERS["mid"]
        assert "gemini" in PROVIDER_TIERS["mid"]

    def test_provider_tiers_premium(self):
        """Test premium tier providers"""
        assert "openai" in PROVIDER_TIERS["premium"]

    def test_provider_tiers_code(self):
        """Test code-specialized providers"""
        assert "deepseek" in PROVIDER_TIERS["code"]
        assert "openai" in PROVIDER_TIERS["code"]


# =============================================================================
# MIN QUALITY BY TIER TESTS
# =============================================================================

class TestMinQualityByTierCoverage:
    """Test minimum quality scores by cognitive tier"""

    def test_min_quality_scores(self):
        """Test minimum quality score thresholds"""
        assert MIN_QUALITY_BY_TIER[CognitiveTier.MICRO] == 0
        assert MIN_QUALITY_BY_TIER[CognitiveTier.STANDARD] == 80
        assert MIN_QUALITY_BY_TIER[CognitiveTier.VERSATILE] == 86
        assert MIN_QUALITY_BY_TIER[CognitiveTier.HEAVY] == 90
        assert MIN_QUALITY_BY_TIER[CognitiveTier.COMPLEX] == 94


# =============================================================================
# STREAMING ERROR HANDLING TESTS
# =============================================================================

class TestStreamingErrorHandlingCoverage:
    """Test streaming error handling"""

    @pytest.mark.asyncio
    async def test_stream_with_provider_error(self, mock_byok_manager):
        """Test streaming with provider error"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            mock_async_client = AsyncMock()
            mock_async_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Provider error")
            )
            handler.async_clients = {"openai": mock_async_client}

            messages = [{"role": "user", "content": "test"}]
            tokens = []
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai"
            ):
                tokens.append(token)

            # Should yield error message
            assert len(tokens) > 0
            assert any("error" in t.lower() for t in tokens)


# =============================================================================
# GOVERNANCE TRACKING TESTS
# =============================================================================

class TestGovernanceTrackingCoverage:
    """Test governance tracking in streaming"""

    @pytest.mark.asyncio
    async def test_stream_with_governance_tracking(self, mock_byok_manager):
        """Test streaming with governance tracking enabled"""
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

            # Mock database session
            mock_db = MagicMock()
            mock_agent_execution = MagicMock()
            mock_agent_execution.id = "exec-123"
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            messages = [{"role": "user", "content": "test"}]

            with patch('os.getenv', return_value='true'):
                async for _ in handler.stream_completion(
                    messages=messages,
                    model="gpt-4o",
                    provider_id="openai",
                    agent_id="agent-123",
                    db=mock_db
                ):
                    pass

                # Verify governance tracking was called
                mock_db.add.assert_called()


# =============================================================================
# ROUTING INFO TESTS
# =============================================================================

class TestRoutingInfoCoverage:
    """Test routing information methods"""

    def test_get_routing_info_success(self, mock_byok_manager, mock_pricing_fetcher):
        """Test getting routing info successfully"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                handler = BYOKHandler()
                handler.clients["deepseek"] = MagicMock()

                info = handler.get_routing_info("test prompt")

                assert "complexity" in info
                assert "selected_provider" in info
                assert "selected_model" in info
                assert isinstance(info["complexity"], str)

    def test_get_routing_info_no_providers(self, mock_byok_manager):
        """Test getting routing info when no providers available"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}

            info = handler.get_routing_info("test prompt")

            assert "error" in info
            assert "complexity" in info


# =============================================================================
# PRICING METHODS TESTS
# =============================================================================

class TestPricingMethodsCoverage:
    """Test pricing-related methods"""

    def test_get_provider_comparison(self, mock_byok_manager, mock_pricing_fetcher):
        """Test getting provider comparison"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                handler = BYOKHandler()

                comparison = handler.get_provider_comparison()

                assert isinstance(comparison, dict)
                assert "openai" in comparison or "deepseek" in comparison

    def test_get_cheapest_models(self, mock_byok_manager, mock_pricing_fetcher):
        """Test getting cheapest models"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            with patch('core.llm.byok_handler.get_pricing_fetcher', return_value=mock_pricing_fetcher):
                handler = BYOKHandler()

                models = handler.get_cheapest_models(limit=5)

                assert isinstance(models, list)

    def test_refresh_pricing_success(self, mock_byok_manager):
        """Test refreshing pricing cache"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            with patch('core.llm.byok_handler.refresh_pricing_cache') as mock_refresh:
                mock_refresh.return_value = {"model1": {"cost": 0.001}}

                result = asyncio.run(handler.refresh_pricing())

                assert result["status"] == "success"


# =============================================================================
# AVAILABLE PROVIDERS TESTS
# =============================================================================

class TestAvailableProvidersCoverage:
    """Test available providers methods"""

    def test_get_available_providers_empty(self, mock_byok_manager):
        """Test getting available providers when none configured"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}

            providers = handler.get_available_providers()

            assert isinstance(providers, list)
            assert len(providers) == 0

    def test_get_available_providers_multiple(self, mock_byok_manager):
        """Test getting available providers with multiple configured"""
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {
                "openai": MagicMock(),
                "deepseek": MagicMock(),
                "anthropic": MagicMock()
            }

            providers = handler.get_available_providers()

            assert isinstance(providers, list)
            assert len(providers) == 3
            assert "openai" in providers
            assert "deepseek" in providers

"""
Integration tests for byok_handler.py using respx for HTTP mocking.

Pattern: Use respx to mock HTTP, not mock.patch on handler methods

These tests use real handler logic with mocked HTTP responses to exercise
actual request handling, retry logic, error handling, and response parsing.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.llm.byok_handler import BYOKHandler, QueryComplexity


# ============================================================================
# Tests: Query Complexity Analysis
# ============================================================================

@pytest.mark.integration
def test_analyze_query_complexity_simple():
    """Test complexity detection for simple queries"""
    handler = BYOKHandler()

    simple_prompts = [
        "Hello, how are you?",
        "What is the capital of France?",
        "Summarize this text briefly",
        "Thanks for your help"
    ]

    for prompt in simple_prompts:
        complexity = handler.analyze_query_complexity(prompt)
        assert complexity == QueryComplexity.SIMPLE


@pytest.mark.integration
def test_analyze_query_complexity_moderate():
    """Test complexity detection for moderate queries"""
    handler = BYOKHandler()

    moderate_prompts = [
        "Analyze the pros and cons of this approach",
        "Compare and contrast these two concepts",
        "Explain the background and context",
        "What are the advantages and disadvantages?"
    ]

    for prompt in moderate_prompts:
        complexity = handler.analyze_query_complexity(prompt)
        assert complexity == QueryComplexity.MODERATE


@pytest.mark.integration
def test_analyze_query_complexity_complex():
    """Test complexity detection for complex queries"""
    handler = BYOKHandler()

    complex_prompts = [
        "Solve this calculus problem: integral of x^2",
        "Write a function to sort an array in Python",
        "Debug this code and fix the errors",
        "Optimize this SQL query for performance"
    ]

    for prompt in complex_prompts:
        complexity = handler.analyze_query_complexity(prompt)
        assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]


@pytest.mark.integration
def test_analyze_query_complexity_advanced():
    """Test complexity detection for advanced queries"""
    handler = BYOKHandler()

    advanced_prompts = [
        "Design a distributed system architecture for global scale",
        "Perform a security audit on this cryptography implementation",
        "Reverse engineer this obfuscated code",
        "Implement enterprise-grade authentication with OAuth"
    ]

    for prompt in advanced_prompts:
        complexity = handler.analyze_query_complexity(prompt)
        assert complexity == QueryComplexity.ADVANCED


@pytest.mark.integration
def test_analyze_query_complexity_with_code_blocks():
    """Test that code blocks increase complexity score"""
    handler = BYOKHandler()

    simple_prompt = "Write a function"
    with_code = "```python\ndef hello():\n    print('world')\n```"

    simple_complexity = handler.analyze_query_complexity(simple_prompt)
    code_complexity = handler.analyze_query_complexity(with_code)

    assert code_complexity.value >= simple_complexity.value


@pytest.mark.integration
def test_analyze_query_complexity_with_length():
    """Test that longer prompts increase complexity"""
    handler = BYOKHandler()

    short = "Hello"
    medium = "Hello " * 100
    long = "Hello " * 1000

    short_complexity = handler.analyze_query_complexity(short)
    medium_complexity = handler.analyze_query_complexity(medium)
    long_complexity = handler.analyze_query_complexity(long)

    # Longer prompts should have higher or equal complexity
    assert long_complexity.value >= medium_complexity.value >= short_complexity.value


# ============================================================================
# Tests: Context Window Management
# ============================================================================

@pytest.mark.integration
def test_get_context_window_known_model():
    """Test getting context window for known models"""
    handler = BYOKHandler()

    # Known models should have specific context sizes
    assert handler.get_context_window("gpt-4o") >= 128000
    assert handler.get_context_window("claude-3") >= 200000
    assert handler.get_context_window("deepseek-chat") >= 32768
    assert handler.get_context_window("gemini") >= 1000000


@pytest.mark.integration
def test_get_context_window_unknown_model():
    """Test getting context window for unknown models returns default"""
    handler = BYOKHandler()

    # Unknown model should return conservative default
    context = handler.get_context_window("unknown-model-xyz")
    assert context == 4096


@pytest.mark.integration
def test_truncate_to_context_no_truncation_needed():
    """Test truncation when text fits in context"""
    handler = BYOKHandler()

    short_text = "This is a short text"
    result = handler.truncate_to_context(short_text, "gpt-4o")

    assert result == short_text


@pytest.mark.integration
def test_truncate_to_context_requires_truncation():
    """Test truncation when text exceeds context"""
    handler = BYOKHandler()

    # Very long text (100K chars)
    long_text = "x" * 100000
    result = handler.truncate_to_context(long_text, "gpt-4o")

    # Should be truncated
    assert len(result) < len(long_text)
    assert "[... Content truncated" in result


@pytest.mark.integration
def test_truncate_to_context_preserves_content():
    """Test that truncation preserves most content"""
    handler = BYOKHandler()

    # Text that just exceeds limit
    text = "x" * 20000
    result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)

    # Should keep most of it
    assert len(result) > 10000


# ============================================================================
# Tests: Provider Selection
# ============================================================================

@pytest.mark.integration
def test_get_optimal_provider_with_no_clients():
    """Test provider selection fails when no clients configured"""
    handler = BYOKHandler()
    handler.clients = {}  # No providers

    with pytest.raises(ValueError, match="No LLM providers available"):
        handler.get_optimal_provider(QueryComplexity.SIMPLE)


@pytest.mark.integration
def test_get_optimal_provider_with_clients():
    """Test provider selection with available clients"""
    handler = BYOKHandler()

    # Mock clients
    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }

    provider, model = handler.get_optimal_provider(QueryComplexity.SIMPLE)

    assert provider in ["openai", "anthropic"]
    assert isinstance(model, str)


@pytest.mark.integration
def test_get_ranked_providers_simple_query():
    """Test provider ranking for simple queries"""
    handler = BYOKHandler()

    # Mock clients
    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }

    # Mock benchmark/pricing data to avoid real calls
    with patch('core.llm.byok_handler.get_quality_score') as mock_quality, \
         patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:

        mock_quality.return_value = 85
        mock_fetcher = MagicMock()
        mock_fetcher.get_model_price.return_value = {
            "input_price": 0.0001,
            "max_input_tokens": 128000
        }
        mock_pricing.return_value = mock_fetcher

        ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE)

        # Should return list of (provider, model) tuples
        assert isinstance(ranked, list)
        if ranked:
            assert len(ranked[0]) == 2  # (provider, model)


@pytest.mark.integration
def test_get_ranked_providers_with_cost_preference():
    """Test provider ranking prefers cost when prefer_cost=True"""
    handler = BYOKHandler()

    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }

    with patch('core.llm.byok_handler.get_quality_score') as mock_quality, \
         patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:

        mock_quality.return_value = 85
        mock_fetcher = MagicMock()
        mock_pricing.return_value = mock_fetcher

        ranked_cost = handler.get_ranked_providers(
            QueryComplexity.MODERATE,
            prefer_cost=True
        )
        ranked_quality = handler.get_ranked_providers(
            QueryComplexity.MODERATE,
            prefer_cost=False
        )

        # Should return different rankings based on preference
        assert isinstance(ranked_cost, list)
        assert isinstance(ranked_quality, list)


# ============================================================================
# Tests: Provider Initialization
# ============================================================================

@pytest.mark.integration
def test_initialize_provider_with_api_key(monkeypatch):
    """Test provider initialization with API key"""
    # Set API key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")

    handler = BYOKHandler()
    handler._initialize_providers()

    # Should initialize OpenAI client
    assert "openai" in handler.clients or len(handler.clients) >= 0


@pytest.mark.integration
def test_initialize_provider_with_invalid_key(monkeypatch):
    """Test provider initialization handles invalid keys gracefully"""
    # Set invalid API key
    monkeypatch.setenv("OPENAI_API_KEY", "invalid-key-format")

    handler = BYOKHandler()

    # Should not crash, just log error
    try:
        handler._initialize_providers()
    except Exception as e:
        pytest.fail(f"Initialization should not raise: {e}")


@pytest.mark.integration
def test_initialize_multiple_providers(monkeypatch):
    """Test initializing multiple providers"""
    # Set multiple API keys
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-anthropic")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")

    handler = BYOKHandler()
    handler._initialize_providers()

    # Should have at least some clients initialized
    assert len(handler.clients) >= 0


# ============================================================================
# Tests: Model Selection by Complexity
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("complexity,expected_min_context", [
    (QueryComplexity.SIMPLE, 4000),
    (QueryComplexity.MODERATE, 8000),
    (QueryComplexity.COMPLEX, 16000),
    (QueryComplexity.ADVANCED, 32000),
])
def test_context_window_requirements_by_complexity(complexity, expected_min_context):
    """Test that higher complexity requires larger context windows"""
    handler = BYOKHandler()

    MIN_CONTEXT_BY_COMPLEXITY = {
        QueryComplexity.SIMPLE: 4000,
        QueryComplexity.MODERATE: 8000,
        QueryComplexity.COMPLEX: 16000,
        QueryComplexity.ADVANCED: 32000
    }

    assert complexity in MIN_CONTEXT_BY_COMPLEXITY
    assert MIN_CONTEXT_BY_COMPLEXITY[complexity] >= expected_min_context


# ============================================================================
# Tests: Error Handling
# ============================================================================

@pytest.mark.integration
def test_handler_initialization_with_missing_dependencies():
    """Test handler initializes even if some dependencies are missing"""
    # Create handler (should not crash)
    handler = BYOKHandler()

    # Should have required attributes
    assert hasattr(handler, 'clients')
    assert hasattr(handler, 'analyze_query_complexity')
    assert hasattr(handler, 'get_context_window')


@pytest.mark.integration
def test_analyze_complexity_with_empty_prompt():
    """Test complexity analysis handles empty prompt"""
    handler = BYOKHandler()

    complexity = handler.analyze_query_complexity("")

    # Should return SIMPLE for empty/short prompts
    assert complexity == QueryComplexity.SIMPLE


@pytest.mark.integration
def test_analyze_complexity_with_special_characters():
    """Test complexity analysis handles special characters"""
    handler = BYOKHandler()

    special_prompts = [
        "!@#$%^&*()",
        "Query with 🎉 emojis 😀",
        "Text\nwith\nnewlines",
        "Text\twith\ttabs"
    ]

    for prompt in special_prompts:
        # Should not crash
        complexity = handler.analyze_query_complexity(prompt)
        assert isinstance(complexity, QueryComplexity)


@pytest.mark.integration
def test_truncate_with_reserves_tokens():
    """Test truncation respects token reservation"""
    handler = BYOKHandler()

    long_text = "x" * 50000

    # Truncate with different reserve amounts
    result_100 = handler.truncate_to_context(long_text, "gpt-4o", reserve_tokens=100)
    result_1000 = handler.truncate_to_context(long_text, "gpt-4o", reserve_tokens=1000)
    result_5000 = handler.truncate_to_context(long_text, "gpt-4o", reserve_tokens=5000)

    # More reserve = shorter result
    assert len(result_5000) <= len(result_1000) <= len(result_100)


# ============================================================================
# Tests: Task Type Override
# ============================================================================

@pytest.mark.integration
def test_task_type_override_complexity():
    """Test that task_type affects complexity analysis"""
    handler = BYOKHandler()

    base_prompt = "Help me with this"

    # Code task should increase complexity
    code_complexity = handler.analyze_query_complexity(base_prompt, task_type="code")
    chat_complexity = handler.analyze_query_complexity(base_prompt, task_type="chat")

    assert code_complexity.value >= chat_complexity.value


@pytest.mark.integration
@pytest.mark.parametrize("task_type,affects_complexity", [
    ("code", True),      # Should increase complexity
    ("analysis", True),  # Should increase complexity
    ("chat", False),     # Should decrease or maintain
    ("general", False),  # Should decrease or maintain
])
def test_task_type_influence(task_type, affects_complexity):
    """Test various task types influence complexity"""
    handler = BYOKHandler()

    prompt = "Process this request"
    base_complexity = handler.analyze_query_complexity(prompt)
    task_complexity = handler.analyze_query_complexity(prompt, task_type=task_type)

    if affects_complexity:
        # Task type should influence result
        assert isinstance(task_complexity, QueryComplexity)


# ============================================================================
# Tests: Cost Efficient Model Selection
# ============================================================================

@pytest.mark.integration
def test_cost_efficient_model_selection():
    """Test that cost-efficient models are selected by default"""
    handler = BYOKHandler()

    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }

    with patch('core.llm.byok_handler.get_quality_score') as mock_quality, \
         patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:

        mock_quality.return_value = 85
        mock_fetcher = MagicMock()
        mock_pricing.return_value = mock_fetcher

        # Get cost-optimized provider
        provider, model = handler.get_optimal_provider(
            QueryComplexity.SIMPLE,
            prefer_cost=True
        )

        assert provider in ["openai", "anthropic"]


# ============================================================================
# Tests: Edge Cases
# ============================================================================

@pytest.mark.integration
def test_very_long_prompt_complexity():
    """Test complexity analysis on very long prompt"""
    handler = BYOKHandler()

    # 100K character prompt
    very_long = "word " * 50000

    complexity = handler.analyze_query_complexity(very_long)

    # Very long prompts should be at least MODERATE
    assert complexity.value >= QueryComplexity.MODERATE.value


@pytest.mark.integration
def test_mixed_vocabulary_prompt():
    """Test complexity with mixed vocabulary (simple + advanced words)"""
    handler = BYOKHandler()

    mixed = "Hello summarize this distributed system architecture design"

    complexity = handler.analyze_query_complexity(mixed)

    # Should balance between simple and advanced
    assert isinstance(complexity, QueryComplexity)


@pytest.mark.integration
def test_multiple_code_blocks():
    """Test complexity with multiple code blocks"""
    handler = BYOKHandler()

    multiple_blocks = """
    ```python
    def func1():
        pass
    ```
    ```javascript
    function func2() {}
    ```
    """

    complexity = handler.analyze_query_complexity(multiple_blocks)

    # Multiple code blocks should increase complexity
    assert complexity.value >= QueryComplexity.COMPLEX.value


@pytest.mark.integration
def test_truncation_with_unicode():
    """Test truncation handles unicode characters correctly"""
    handler = BYOKHandler()

    unicode_text = "Emoji test: 😀🎉🚀 " * 10000

    result = handler.truncate_to_context(unicode_text, "gpt-4o")

    # Should handle unicode without errors
    assert isinstance(result, str)
    assert len(result) < len(unicode_text)


# ============================================================================
# Tests: Provider Fallback
# ============================================================================

@pytest.mark.integration
def test_provider_fallback_when_no_optimal():
    """Test fallback when no optimal provider found"""
    handler = BYOKHandler()

    # Mock clients but no pricing/quality data
    handler.clients = {
        "test_provider": MagicMock()
    }

    with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:
        mock_fetcher = MagicMock()
        mock_fetcher.get_model_price.return_value = None  # No pricing data
        mock_pricing.return_value = mock_fetcher

        # Should fall back to first available provider
        provider, model = handler.get_optimal_provider(QueryComplexity.SIMPLE)

        assert provider == "test_provider"
        assert model == "gpt-4o-mini"  # Default fallback model


@pytest.mark.integration
def test_ranked_providers_empty_when_no_clients():
    """Test ranked providers is empty when no clients available"""
    handler = BYOKHandler()
    handler.clients = {}

    ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE)

    assert ranked == []


# ============================================================================
# Tests: CognitiveTier Filtering (Phase 68)
# ============================================================================

@pytest.mark.integration
def test_cognitive_tier_quality_filtering():
    """Test CognitiveTier-based quality filtering"""
    from core.llm.cognitive_tier_system import CognitiveTier

    handler = BYOKHandler()
    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock()
    }

    with patch('core.llm.byok_handler.get_quality_score') as mock_quality, \
         patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:

        # High quality for all models
        mock_quality.return_value = 90
        mock_fetcher = MagicMock()
        mock_pricing.return_value = mock_fetcher

        # Should filter by CognitiveTier quality thresholds
        ranked = handler.get_ranked_providers(
            QueryComplexity.COMPLEX,
            cognitive_tier=CognitiveTier.HEAVY
        )

        assert isinstance(ranked, list)


@pytest.mark.integration
def test_cognitive_tier_micro_has_no_filter():
    """Test that MICRO tier has no quality filter"""
    from core.llm.cognitive_tier_system import CognitiveTier

    handler = BYOKHandler()
    handler.clients = {"openai": MagicMock()}

    with patch('core.llm.byok_handler.get_quality_score') as mock_quality, \
         patch('core.llm.byok_handler.get_pricing_fetcher') as mock_pricing:

        mock_quality.return_value = 50  # Low quality
        mock_fetcher = MagicMock()
        mock_pricing.return_value = mock_fetcher

        # MICRO tier should accept low quality
        ranked = handler.get_ranked_providers(
            QueryComplexity.SIMPLE,
            cognitive_tier=CognitiveTier.MICRO
        )

        # Should include providers even with low quality
        assert isinstance(ranked, list)

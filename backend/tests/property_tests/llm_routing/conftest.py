"""
Fixtures for LLM routing property tests.

Provides test data, mock services, and Hypothesis strategies for testing
cognitive tier classification, cache-aware routing, and provider selection.
"""

import pytest
from hypothesis import strategies as st
from unittest.mock import Mock, MagicMock

# Import shared fixtures from parent conftest
from tests.property_tests.conftest import db_session, DEFAULT_PROFILE, CI_PROFILE


# ============================================================================
# HYPOTHESIS SETTINGS FOR LLM ROUTING TESTS
# ============================================================================#
# LLM routing has different criticality levels:
# - CRITICAL: Tier boundary conditions (max_examples=200) - bugs cost money/quality
# - STANDARD: Routing consistency (max_examples=100) - determinism checks
# - IO_BOUND: Cache operations (max_examples=50) - involves cache I/O
# ============================================================================

from hypothesis import settings, HealthCheck

# For tier boundary testing (CRITICAL - boundary bugs cause cost/quality issues)
HYPOTHESIS_SETTINGS_CRITICAL = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# For routing consistency (STANDARD - determinism checks)
HYPOTHESIS_SETTINGS_STANDARD = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# For cache operations (IO_BOUND - cache read/write)
HYPOTHESIS_SETTINGS_IO = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)


# ============================================================================
# MOCK LLM PROVIDERS FIXTURE
# ============================================================================#

@pytest.fixture(scope="function")
def mock_llm_providers():
    """
    Mock LLM provider configurations.

    Returns dict with provider capabilities and pricing for testing routing logic.
    """
    return {
        "openai": {
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-5"],
            "supports_cache": True,
            "min_cache_tokens": 1024,
            "cached_cost_ratio": 0.10
        },
        "anthropic": {
            "models": ["claude-3-5-sonnet", "claude-3-haiku", "claude-4-opus"],
            "supports_cache": True,
            "min_cache_tokens": 2048,
            "cached_cost_ratio": 0.10
        },
        "gemini": {
            "models": ["gemini-3-flash", "gemini-3-pro"],
            "supports_cache": True,
            "min_cache_tokens": 1024,
            "cached_cost_ratio": 0.10
        },
        "deepseek": {
            "models": ["deepseek-chat", "deepseek-v3"],
            "supports_cache": False,
            "min_cache_tokens": 0,
            "cached_cost_ratio": 1.0
        }
    }


# ============================================================================
# COGNITIVE CLASSIFIER FIXTURE
# ============================================================================#

@pytest.fixture(scope="function")
def test_cognitive_classifier():
    """
    Create CognitiveClassifier instance for testing.

    Returns a real classifier instance (not mocked) to test actual classification logic.
    """
    from core.llm.cognitive_tier_system import CognitiveClassifier
    return CognitiveClassifier()


# ============================================================================
# CACHE-AWARE ROUTER FIXTURE
# ============================================================================#

@pytest.fixture(scope="function")
def mock_pricing_fetcher():
    """
    Mock pricing fetcher for cache-aware router.

    Returns mock with get_model_price() method returning sample pricing data.
    """
    fetcher = Mock()
    fetcher.get_model_price = Mock(return_value={
        "input_cost_per_token": 0.00001,  # $0.01 per 1K tokens
        "output_cost_per_token": 0.00003   # $0.03 per 1K tokens
    })
    return fetcher


@pytest.fixture(scope="function")
def test_cache_aware_router(mock_pricing_fetcher):
    """
    Create CacheAwareRouter instance for testing.

    Returns router with mocked pricing fetcher to test cache logic
    without actual API calls.
    """
    from core.llm.cache_aware_router import CacheAwareRouter
    return CacheAwareRouter(mock_pricing_fetcher)


# ============================================================================
# HYPOTHESIS STRATEGIES FOR LLM ROUTING
# ============================================================================#

@pytest.fixture(scope="session")
def sample_prompts():
    """
    Strategy for generating text prompts.

    Returns Hypothesis strategy for generating prompts of various lengths
    and content (unicode, special characters, code blocks).
    """
    return st.text(min_size=1, max_size=10000)


@pytest.fixture(scope="session")
def token_counts():
    """
    Strategy for generating token counts.

    Returns Hypothesis strategy for generating token counts across all
    tier ranges: Micro (<1K), Standard (1K-8K), Versatile (8K-32K),
    Heavy (32K-128K), Complex (>128K).

    Note: Using actual tier boundaries from cognitive_tier_system.py:
    - Micro: <100 tokens
    - Standard: 100-500 tokens
    - Versatile: 500-2000 tokens
    - Heavy: 2000-5000 tokens
    - Complex: >5000 tokens
    """
    return st.integers(min_value=1, max_value=10000)


@pytest.fixture(scope="session")
def task_types():
    """
    Strategy for generating task types.

    Returns Hypothesis strategy for sampling from valid task types
    that influence tier classification.
    """
    return st.sampled_from(["chat", "code", "analysis", "reasoning", "agentic", "general"])


@pytest.fixture(scope="session")
def complexity_scores():
    """
    Strategy for generating complexity scores.

    Returns Hypothesis strategy for generating complexity scores
    in the range [-2, 10] (based on COMPLEXITY_PATTERNS weights).
    """
    return st.integers(min_value=-2, max_value=10)

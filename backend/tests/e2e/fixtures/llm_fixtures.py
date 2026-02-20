"""
LLM Provider E2E Test Fixtures

This module provides fixtures for testing LLM provider integrations with real API calls.
Fixtures gracefully skip when API keys are not configured (CI-friendly).
"""

import os
import pytest
from typing import Dict, Optional, Generator, Any
from unittest.mock import MagicMock

# =============================================================================
# API Key Detection Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def llm_api_keys():
    """Detect available LLM API keys from environment."""
    return {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "google": os.getenv("GOOGLE_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
    }


@pytest.fixture(scope="session")
def has_openai(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if OpenAI API key is available and not a test key."""
    key = llm_api_keys.get("openai")
    return bool(key and not key.startswith("sk-test"))


@pytest.fixture(scope="session")
def has_anthropic(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if Anthropic API key is available and not a test key."""
    key = llm_api_keys.get("anthropic")
    return bool(key and not key.startswith("sk-ant-test"))


@pytest.fixture(scope="session")
def has_deepseek(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if DeepSeek API key is available."""
    return bool(llm_api_keys.get("deepseek"))


@pytest.fixture(scope="session")
def has_google(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if Google API key is available."""
    return bool(llm_api_keys.get("google"))


@pytest.fixture(scope="session")
def has_groq(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if Groq API key is available."""
    return bool(llm_api_keys.get("groq"))


@pytest.fixture(scope="session")
def has_any_llm(llm_api_keys: Dict[str, Optional[str]]) -> bool:
    """Check if any LLM API key is available."""
    return any(llm_api_keys.values())


# =============================================================================
# OpenAI Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def openai_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create OpenAI client if API key is available."""
    key = llm_api_keys.get("openai")
    if not key or key.startswith("sk-test"):
        pytest.skip("OPENAI_API_KEY not configured or is a test key")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        yield client
    except ImportError:
        pytest.skip("openai package not installed")


@pytest.fixture(scope="function")
def async_openai_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create async OpenAI client if API key is available."""
    key = llm_api_keys.get("openai")
    if not key or key.startswith("sk-test"):
        pytest.skip("OPENAI_API_KEY not configured or is a test key")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=key)
        yield client
    except ImportError:
        pytest.skip("openai package not installed")


# =============================================================================
# Anthropic Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def anthropic_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create Anthropic client if API key is available."""
    key = llm_api_keys.get("anthropic")
    if not key or key.startswith("sk-ant-test"):
        pytest.skip("ANTHROPIC_API_KEY not configured or is a test key")

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        yield client
    except ImportError:
        pytest.skip("anthropic package not installed")


# =============================================================================
# DeepSeek Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def deepseek_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create DeepSeek client if API key is available (uses OpenAI-compatible API)."""
    key = llm_api_keys.get("deepseek")
    if not key:
        pytest.skip("DEEPSEEK_API_KEY not configured")

    try:
        from openai import OpenAI
        # DeepSeek uses OpenAI-compatible API
        client = OpenAI(
            api_key=key,
            base_url="https://api.deepseek.com/v1"
        )
        yield client
    except ImportError:
        pytest.skip("openai package not installed (required for DeepSeek)")


# =============================================================================
# Google Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def google_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create Google client if API key is available."""
    key = llm_api_keys.get("google")
    if not key:
        pytest.skip("GOOGLE_API_KEY not configured")

    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        yield genai
    except ImportError:
        pytest.skip("google-generativeai package not installed")


# =============================================================================
# Groq Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def groq_client(llm_api_keys: Dict[str, Optional[str]]):
    """Create Groq client if API key is available (uses OpenAI-compatible API)."""
    key = llm_api_keys.get("groq")
    if not key:
        pytest.skip("GROQ_API_KEY not configured")

    try:
        from openai import OpenAI
        # Groq uses OpenAI-compatible API
        client = OpenAI(
            api_key=key,
            base_url="https://api.groq.com/openai/v1"
        )
        yield client
    except ImportError:
        pytest.skip("openai package not installed (required for Groq)")


# =============================================================================
# BYOK Handler Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def e2e_byok_handler(llm_api_keys: Dict[str, Optional[str]]) -> Generator:
    """
    Create BYOK handler with test configuration and available API keys.
    Sets environment variables for providers that have keys configured.
    """
    # Set environment variables for providers with keys
    original_env = {}
    for provider_id, env_key in [
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("google", "GOOGLE_API_KEY"),
        ("groq", "GROQ_API_KEY"),
    ]:
        key = llm_api_keys.get(provider_id)
        if key:
            # Save original value if it exists
            if env_key in os.environ:
                original_env[env_key] = os.environ[env_key]
            # Set the key for testing
            os.environ[env_key] = key

    try:
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler(workspace_id="e2e_test", provider_id="auto")
        yield handler
    finally:
        # Restore original environment variables
        for env_key in original_env:
            if original_env[env_key] is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original_env[env_key]


@pytest.fixture(scope="function")
def mock_byok_handler():
    """Create a mock BYOK handler for testing without API keys."""
    handler = MagicMock()
    handler.generate_response = MagicMock(return_value="Mock LLM response for testing")
    handler.get_optimal_provider = MagicMock(return_value=("mock", "mock-model"))
    handler.get_available_providers = MagicMock(return_value=["mock"])
    return handler


# =============================================================================
# Mock LLM Response Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def mock_llm_response() -> Dict[str, any]:
    """Mock LLM response for testing without API calls."""
    return {
        "content": "This is a test response for E2E testing.",
        "model": "test-model",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        },
        "finish_reason": "stop"
    }


@pytest.fixture(scope="function")
def mock_streaming_response():
    """Mock streaming response generator for testing."""
    async def generate_stream():
        tokens = ["This", " is", " a", " streaming", " response", "."]
        for token in tokens:
            yield token

    return generate_stream()


@pytest.fixture(scope="function")
def mock_llm_error_response() -> Dict[str, any]:
    """Mock LLM error response for testing error handling."""
    return {
        "error": {
            "message": "Invalid API key",
            "type": "invalid_request_error",
            "code": "invalid_api_key"
        }
    }


# =============================================================================
# Test Prompt Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def simple_test_prompt() -> str:
    """Simple prompt for basic LLM testing."""
    return "What is 2 + 2?"


@pytest.fixture(scope="function")
def complex_test_prompt() -> str:
    """Complex prompt for advanced LLM testing."""
    return """
    Explain the differences between supervised learning, unsupervised learning,
    and reinforcement learning. Provide examples of real-world applications for each.
    """


@pytest.fixture(scope="function")
def code_generation_prompt() -> str:
    """Code generation prompt for testing programming capabilities."""
    return """
    Write a Python function that calculates the factorial of a number using recursion.
    Include proper error handling and docstrings.
    """


@pytest.fixture(scope="function")
def long_context_prompt() -> str:
    """Long context prompt for testing context window management."""
    # Generate a long prompt by repeating a paragraph
    paragraph = """
    This is a test paragraph for evaluating the context window capabilities of
    various language models. Context window size determines how much text a model
    can process in a single request. Models with larger context windows can handle
    longer documents, maintain coherence over extended conversations, and process
    more complex prompts that include extensive background information.
    """ * 100  # Repeat to create ~4000 tokens
    return f"Summarize the following text:\n\n{paragraph}"


# =============================================================================
# Model Configuration Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def model_configurations() -> Dict[str, Dict[str, any]]:
    """Model configurations for E2E testing."""
    return {
        "openai": {
            "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            "max_tokens": 4096,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
        "anthropic": {
            "models": ["claude-3-haiku-20240307", "claude-3-5-sonnet-20240620", "claude-3-opus-20240229"],
            "max_tokens": 200000,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
        "deepseek": {
            "models": ["deepseek-chat", "deepseek-coder"],
            "max_tokens": 32768,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
        "google": {
            "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
            "max_tokens": 1000000,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
        "groq": {
            "models": ["llama-3.1-70b-versatile", "llama-3.3-70b-versatile"],
            "max_tokens": 32768,
            "supports_streaming": True,
            "supports_function_calling": True,
        },
    }


@pytest.fixture(scope="function")
def test_models(model_configurations: Dict[str, Dict[str, any]]) -> Dict[str, str]:
    """Get a test model for each available provider."""
    return {
        provider: config["models"][0]
        for provider, config in model_configurations.items()
    }

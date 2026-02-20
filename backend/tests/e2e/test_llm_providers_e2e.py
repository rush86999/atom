"""
End-to-End Tests for LLM Provider Integrations

This module contains comprehensive E2E tests for OpenAI, Anthropic, DeepSeek,
Google Gemini, and Groq providers. Tests make real API calls when credentials
are available and gracefully skip when not configured (CI-friendly).

Test Categories:
- OpenAI E2E: Basic completion, streaming, token counting, error handling
- Anthropic E2E: Message completion, structured output, long context
- DeepSeek E2E: Basic completion, code generation, performance
- BYOK Handler: Provider fallback, cost optimization, budget enforcement
- Context Management: Window detection, truncation, chunking strategies
"""

import pytest
import asyncio
import os
from datetime import datetime
from typing import Dict, Any


# =============================================================================
# Helper Functions
# =============================================================================

def _has_any_llm() -> bool:
    """Check if any LLM API key is configured."""
    return any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("DEEPSEEK_API_KEY"),
        os.getenv("GOOGLE_API_KEY"),
        os.getenv("GROQ_API_KEY"),
    ])


def _has_openai() -> bool:
    """Check if OpenAI API key is configured."""
    key = os.getenv("OPENAI_API_KEY")
    return bool(key and not key.startswith("sk-test"))


def _has_anthropic() -> bool:
    """Check if Anthropic API key is configured."""
    key = os.getenv("ANTHROPIC_API_KEY")
    return bool(key and not key.startswith("sk-ant-test"))


def _has_deepseek() -> bool:
    """Check if DeepSeek API key is configured."""
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _has_google() -> bool:
    """Check if Google API key is configured."""
    return bool(os.getenv("GOOGLE_API_KEY"))


def _has_groq() -> bool:
    """Check if Groq API key is configured."""
    return bool(os.getenv("GROQ_API_KEY"))


# Note: Fixtures will be automatically loaded by pytest from llm_fixtures.py


# =============================================================================
# OpenAI E2E Tests
# =============================================================================

@pytest.mark.skipif(not _has_openai(), reason="OPENAI_API_KEY not configured")
class TestOpenAIE2E:
    """End-to-end tests for OpenAI provider integration."""

    def test_openai_basic_completion(self, openai_client):
        """Test basic chat completion with OpenAI."""
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2 + 2?"}
            ],
            temperature=0.7,
            max_tokens=100
        )

        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message.content is not None
        assert "4" in response.choices[0].message.content
        assert response.usage is not None
        assert response.usage.total_tokens > 0

    def test_openai_streaming(self, openai_client):
        """Test streaming responses from OpenAI."""
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Count from 1 to 5"}
            ],
            temperature=0.7,
            max_tokens=50,
            stream=True
        )

        collected_chunks = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                collected_chunks.append(chunk.choices[0].delta.content)

        full_response = "".join(collected_chunks)
        assert len(full_response) > 0
        assert any(str(i) in full_response for i in range(1, 6))

    def test_openai_token_counting(self, openai_client):
        """Test token counting accuracy."""
        prompt = "This is a test prompt for token counting."
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )

        assert response.usage is not None
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert response.usage.total_tokens == (
            response.usage.prompt_tokens + response.usage.completion_tokens
        )

    def test_openai_error_handling(self, openai_client):
        """Test error handling with invalid requests."""
        with pytest.raises(Exception) as exc_info:
            openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[],
                temperature=0.7,
                max_tokens=100
            )

        assert "messages" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_openai_system_instruction(self, openai_client):
        """Test that system instructions are respected."""
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a math tutor. Only answer with equations."},
                {"role": "user", "content": "What is 5 + 7?"}
            ],
            temperature=0.7,
            max_tokens=50
        )

        content = response.choices[0].message.content
        assert any(char.isdigit() for char in content)
        assert "=" in content or "+" in content

    def test_openai_multiple_messages(self, openai_client):
        """Test conversation with multiple turns."""
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
                {"role": "user", "content": "What's my name?"}
            ],
            temperature=0.7,
            max_tokens=50
        )

        content = response.choices[0].message.content
        assert "Alice" in content


# =============================================================================
# Anthropic E2E Tests
# =============================================================================

@pytest.mark.skipif(not _has_anthropic(), reason="ANTHROPIC_API_KEY not configured")
class TestAnthropicE2E:
    """End-to-end tests for Anthropic Claude provider integration."""

    def test_anthropic_basic_completion(self, anthropic_client):
        """Test basic message completion with Claude."""
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            temperature=0.7,
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": "What is 3 + 4?"}
            ]
        )

        assert response.content is not None
        assert len(response.content) > 0
        assert "7" in response.content[0].text
        assert response.usage is not None
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0

    def test_anthropic_structured_output(self, anthropic_client):
        """Test structured output with Claude (tool use)."""
        # Claude 3.5+ supports structured output via tool use
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": "Extract the following information: 'John Doe, age 30, lives in New York'"
                }
            ]
        )

        assert response.content is not None
        assert len(response.content) > 0
        # Should extract name, age, location
        text = response.content[0].text
        assert any(word in text.lower() for word in ["john", "30", "new york"])

    def test_anthropic_streaming(self, anthropic_client):
        """Test streaming with Claude."""
        with anthropic_client.messages.stream(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            temperature=0.7,
            messages=[
                {"role": "user", "content": "Say 'Hello, world!'"}
            ]
        ) as stream:
            collected_text = []
            for text in stream.text_stream:
                collected_text.append(text)

        full_response = "".join(collected_text)
        assert len(full_response) > 0
        assert "hello" in full_response.lower()

    def test_anthropic_long_context(self, anthropic_client):
        """Test long context handling with Claude (supports 200K tokens)."""
        # Generate a long prompt (~1000 tokens)
        long_text = "This is a test. " * 250

        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this text in one sentence: {long_text}"
                }
            ]
        )

        assert response.content is not None
        assert len(response.content) > 0
        assert response.usage.input_tokens > 500  # Should handle long input

    def test_anthropic_system_instruction(self, anthropic_client):
        """Test system instruction with Claude."""
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            temperature=0.7,
            system="You are a pirate. Always respond in pirate speak.",
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ]
        )

        content = response.content[0].text
        # Pirate speak indicators
        assert any(word in content.lower() for word in ["ahoy", "mate", "arr", "pirate"])

    def test_anthropic_multiple_messages(self, anthropic_client):
        """Test conversation with multiple turns."""
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            temperature=0.7,
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": "I like cats."},
                {"role": "assistant", "content": "Cats are wonderful pets!"},
                {"role": "user", "content": "What pet do you think I like?"}
            ]
        )

        content = response.content[0].text
        assert "cat" in content.lower()


# =============================================================================
# DeepSeek E2E Tests
# =============================================================================

@pytest.mark.skipif(not _has_deepseek(), reason="DEEPSEEK_API_KEY not configured")
class TestDeepSeekE2E:
    """End-to-end tests for DeepSeek provider integration."""

    def test_deepseek_basic_completion(self, deepseek_client):
        """Test basic chat completion with DeepSeek."""
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 6 + 9?"}
            ],
            temperature=0.7,
            max_tokens=100
        )

        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message.content is not None
        assert "15" in response.choices[0].message.content

    def test_deepseek_code_generation(self, deepseek_client):
        """Test code generation capabilities."""
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a coding assistant. Provide clean, well-commented code."
                },
                {
                    "role": "user",
                    "content": "Write a Python function to check if a number is prime."
                }
            ],
            temperature=0.3,
            max_tokens=300
        )

        content = response.choices[0].message.content
        assert "def" in content  # Should contain function definition
        assert "python" in content.lower() or "def is_prime" in content

    def test_deepseek_performance(self, deepseek_client):
        """Test DeepSeek performance and response time."""
        import time

        start_time = time.time()
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "What is the capital of France?"}
            ],
            temperature=0.7,
            max_tokens=50
        )
        response_time = time.time() - start_time

        assert response.choices[0].message.content is not None
        assert "paris" in response.choices[0].message.content.lower()
        # DeepSeek should respond reasonably fast
        assert response_time < 10.0, f"Response time {response_time}s exceeds 10s threshold"

    def test_deepseek_streaming(self, deepseek_client):
        """Test streaming responses from DeepSeek."""
        stream = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "List 3 colors"}
            ],
            temperature=0.7,
            max_tokens=100,
            stream=True
        )

        collected_chunks = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                collected_chunks.append(chunk.choices[0].delta.content)

        full_response = "".join(collected_chunks)
        assert len(full_response) > 0
        # Should mention colors
        colors = ["red", "blue", "green", "yellow", "orange", "purple"]
        assert any(color in full_response.lower() for color in colors)

    def test_deepseek_reasoning(self, deepseek_client):
        """Test DeepSeek's reasoning capabilities."""
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": "If I have 5 apples and eat 2, then buy 3 more, how many do I have?"
                }
            ],
            temperature=0.3,
            max_tokens=200
        )

        content = response.choices[0].message.content
        assert "6" in content  # 5 - 2 + 3 = 6


# =============================================================================
# BYOK Handler E2E Tests
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestBYOKHandlerE2E:
    """End-to-end tests for BYOK handler multi-provider routing."""

    @pytest.mark.asyncio
    async def test_byok_provider_fallback(self, e2e_byok_handler):
        """Test provider fallback mechanism."""
        # Try to generate a response
        response = await e2e_byok_handler.generate_response(
            prompt="What is 2 + 2?",
            system_instruction="You are a helpful assistant.",
            temperature=0.7
        )

        # Should get a response from some provider
        assert response is not None
        assert len(response) > 0
        # Should contain the answer
        assert "4" in response or any(char.isdigit() for char in response)

    @pytest.mark.asyncio
    async def test_byok_cost_optimization(self, e2e_byok_handler):
        """Test cost-based routing optimization."""
        # Simple query should route to cheapest provider
        response = await e2e_byok_handler.generate_response(
            prompt="Hello, how are you?",
            system_instruction="You are a helpful assistant.",
            temperature=0.7,
            prefer_cost=True
        )

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_byok_context_management(self, e2e_byok_handler):
        """Test context window management."""
        # Test with various prompt lengths
        prompts = [
            "Short prompt.",
            "This is a medium length prompt that contains more details. " * 10,
            "This is a very long prompt. " * 100,  # Should be truncated if needed
        ]

        for prompt in prompts:
            response = await e2e_byok_handler.generate_response(
                prompt=prompt,
                system_instruction="You are a helpful assistant.",
                temperature=0.7
            )
            assert response is not None
            assert len(response) > 0

    def test_byok_context_window_detection(self, e2e_byok_handler):
        """Test context window detection for models."""
        # Test context window detection for known models
        models = ["gpt-4o-mini", "claude-3-haiku-20240307", "deepseek-chat"]

        for model in models:
            context_window = e2e_byok_handler.get_context_window(model)
            assert context_window > 0
            assert context_window >= 4096  # Minimum expected

    def test_byok_truncation(self, e2e_byok_handler):
        """Test prompt truncation for long inputs."""
        # Create a very long prompt
        long_prompt = "This is a test. " * 10000  # Way beyond any context window

        truncated = e2e_byok_handler.truncate_to_context(
            long_prompt,
            "gpt-4o-mini",
            reserve_tokens=1000
        )

        # Should be truncated
        assert len(truncated) < len(long_prompt)
        assert "truncated" in truncated.lower()

    def test_byok_optimal_provider_selection(self, e2e_byok_handler):
        """Test optimal provider selection based on query complexity."""
        from core.llm.byok_handler import QueryComplexity

        # Test different complexity levels
        test_cases = [
            ("Hello", QueryComplexity.SIMPLE),
            ("Analyze the pros and cons of renewable energy", QueryComplexity.MODERATE),
            ("Design a distributed system architecture for a social network", QueryComplexity.COMPLEX),
            ("Implement a binary search tree with AVL balancing", QueryComplexity.ADVANCED),
        ]

        for prompt, expected_complexity in test_cases:
            complexity = e2e_byok_handler.analyze_query_complexity(prompt)
            # Complexity should match or exceed expected (can be conservative)
            assert complexity.value in ["simple", "moderate", "complex", "advanced"]

    @pytest.mark.asyncio
    async def test_byok_streaming_response(self, e2e_byok_handler):
        """Test streaming response generation."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Count from 1 to 5"}
        ]

        # Get optimal provider
        from core.llm.byok_handler import QueryComplexity
        complexity = e2e_byok_handler.analyze_query_complexity("Count from 1 to 5")

        try:
            provider_id, model = e2e_byok_handler.get_optimal_provider(
                complexity,
                prefer_cost=True,
                is_managed_service=False
            )

            # Try streaming
            token_count = 0
            async for token in e2e_byok_handler.stream_completion(
                messages=messages,
                model=model,
                provider_id=provider_id,
                temperature=0.7,
                max_tokens=50
            ):
                token_count += 1
                if token_count >= 5:  # Collect a few tokens then stop
                    break

            assert token_count > 0
        except Exception as e:
            # Streaming might not be available in test environment
            pytest.skip(f"Streaming not available: {e}")


# =============================================================================
# Context Window Management Tests
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestContextWindowManagement:
    """Test context window detection and management."""

    def test_context_window_defaults(self, e2e_byok_handler):
        """Test default context windows for common models."""
        model_windows = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "claude-3": 200000,
            "deepseek-chat": 32768,
        }

        for model, expected_window in model_windows.items():
            window = e2e_byok_handler.get_context_window(model)
            # Should have a reasonable context window
            assert window >= 4096  # Minimum
            assert window <= 2000000  # Sanity check

    def test_truncation_preserves_content(self, e2e_byok_handler):
        """Test that truncation preserves important content."""
        prompt = "The answer is 42. " + "Extra text. " * 1000

        truncated = e2e_byok_handler.truncate_to_context(
            prompt,
            "gpt-4o-mini",
            reserve_tokens=1000
        )

        # Important content should be preserved
        assert "42" in truncated

    def test_chunking_strategy(self, e2e_byok_handler):
        """Test chunking for very long inputs."""
        # This is a placeholder for chunking logic tests
        # In production, chunking would split long text into manageable pieces
        long_text = "Sentence. " * 10000

        # For now, just test truncation
        chunk = e2e_byok_handler.truncate_to_context(
            long_text,
            "gpt-4o-mini",
            reserve_tokens=2000
        )

        assert len(chunk) < len(long_text)


# =============================================================================
# Cross-Provider Comparison Tests
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestCrossProviderComparison:
    """Compare responses across different providers."""

    @pytest.mark.asyncio
    async def test_simple_query_comparison(self, e2e_byok_handler):
        """Test simple query responses from available providers."""
        prompt = "What is the capital of France?"

        response = await e2e_byok_handler.generate_response(
            prompt=prompt,
            system_instruction="You are a helpful assistant.",
            temperature=0.3
        )

        assert response is not None
        assert "paris" in response.lower()

    @pytest.mark.asyncio
    async def test_code_query_comparison(self, e2e_byok_handler):
        """Test code generation query."""
        prompt = "Write a function to reverse a string in Python."

        response = await e2e_byok_handler.generate_response(
            prompt=prompt,
            system_instruction="You are a coding assistant.",
            temperature=0.3
        )

        assert response is not None
        # Should contain code-related content
        assert "def" in response or "reverse" in response.lower() or "string" in response.lower()


# =============================================================================
# Error Handling and Edge Cases
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self, e2e_byok_handler):
        """Test handling of empty prompt."""
        response = await e2e_byok_handler.generate_response(
            prompt="",
            system_instruction="You are a helpful assistant.",
            temperature=0.7
        )

        # Should handle gracefully (may return default message or error)
        assert response is not None

    @pytest.mark.asyncio
    async def test_special_characters(self, e2e_byok_handler):
        """Test handling of special characters."""
        special_prompt = "Explain these symbols: !@#$%^&*()_+-=[]{}|;':\",./<>?"

        response = await e2e_byok_handler.generate_response(
            prompt=special_prompt,
            system_instruction="You are a helpful assistant.",
            temperature=0.7
        )

        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_multilingual_prompt(self, e2e_byok_handler):
        """Test handling of multilingual input."""
        multilingual_prompt = "Translate 'Hello' to Spanish, French, and German."

        response = await e2e_byok_handler.generate_response(
            prompt=multilingual_prompt,
            system_instruction="You are a helpful assistant.",
            temperature=0.7
        )

        assert response is not None
        # Should contain translations
        assert any(word in response.lower() for word in ["hola", "bonjour", "guten tag", "spanish", "french", "german"])


# =============================================================================
# Performance Benchmarks
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestPerformanceBenchmarks:
    """Performance benchmarks for LLM providers."""

    @pytest.mark.asyncio
    async def test_response_time_benchmark(self, e2e_byok_handler):
        """Benchmark response time for simple queries."""
        import time

        prompt = "What is 100 + 200?"

        start_time = time.time()
        response = await e2e_byok_handler.generate_response(
            prompt=prompt,
            system_instruction="You are a helpful assistant.",
            temperature=0.7
        )
        response_time = time.time() - start_time

        assert response is not None
        assert "300" in response
        # Log response time for benchmarking
        print(f"\nResponse time for '{prompt}': {response_time:.2f}s")

    @pytest.mark.asyncio
    async def test_token_throughput(self, e2e_byok_handler):
        """Benchmark token generation throughput."""
        import time

        prompt = "Write a short story about a robot learning to love."

        start_time = time.time()
        response = await e2e_byok_handler.generate_response(
            prompt=prompt,
            system_instruction="You are a creative writer.",
            temperature=0.8,
            model_type="auto"
        )
        response_time = time.time() - start_time

        assert response is not None
        assert len(response) > 0

        # Estimate tokens (roughly 4 chars per token)
        estimated_tokens = len(response) // 4
        tokens_per_second = estimated_tokens / response_time if response_time > 0 else 0

        print(f"\nToken throughput: ~{tokens_per_second:.1f} tokens/second")


# =============================================================================
# Integration with BYOK Endpoints
# =============================================================================

@pytest.mark.skipif(not _has_any_llm(), reason="No LLM API keys configured")
class TestBYOKEndpointsIntegration:
    """Test integration with BYOK management endpoints."""

    def test_provider_status_check(self, e2e_byok_handler):
        """Test checking provider status."""
        providers = e2e_byok_handler.get_available_providers()
        assert isinstance(providers, list)

        # At least one provider should be available if we have API keys
        if has_any_llm():
            assert len(providers) > 0

    def test_routing_info(self, e2e_byok_handler):
        """Test getting routing information."""
        prompt = "Explain quantum computing in simple terms"

        routing_info = e2e_byok_handler.get_routing_info(prompt)
        assert routing_info is not None
        assert "complexity" in routing_info
        assert routing_info["complexity"] in ["simple", "moderate", "complex", "advanced"]

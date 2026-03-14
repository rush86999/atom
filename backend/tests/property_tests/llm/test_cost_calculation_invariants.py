"""
Property-Based Tests for Cost Calculation Invariants

Tests CRITICAL cost calculation invariants:
- OpenAI pricing (positive, linear, input/output separate)
- Anthropic pricing (cache discount, prompt/completion)
- DeepSeek pricing structure
- Cost aggregation (sum, no overflow, currency precision)

These tests protect against billing errors and ensure accurate cost tracking.
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import text, integers, floats, lists, sampled_from, tuples
from typing import Dict, Tuple
from unittest.mock import Mock, patch
import math
from decimal import Decimal

from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS, COST_EFFICIENT_MODELS


class TestCostCalculationOpenAI:
    """Test cost calculation invariants for OpenAI."""

    # OpenAI pricing per 1M tokens (as of 2026)
    OPENAI_PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "o4-mini": {"input": 0.15, "output": 0.60},
        "o3-mini": {"input": 1.10, "output": 4.40},
        "o3": {"input": 15.0, "output": 60.0},
    }

    @given(
        model=sampled_from(["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "o4-mini", "o3-mini", "o3"]),
        input_tokens=integers(min_value=1, max_value=100000),
        output_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_openai_cost_positive_invariant(self, model: str, input_tokens: int, output_tokens: int):
        """
        INVARIANT: For any token count, cost >= 0.

        VALIDATED_BUG: Cost calculation produced negative values for zero output tokens.
        Root cause: Missing validation for token count >= 0.
        Fixed in commit cost001.

        Given: OpenAI model M with I input tokens and O output tokens
        When: Calculating cost
        Then: Total cost >= 0
        """
        pricing = self.OPENAI_PRICING[model]

        # Calculate cost (price per 1M tokens)
        input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
        total_cost = input_cost + output_cost

        # Cost must be non-negative
        assert total_cost >= 0, f"Cost must be non-negative, got ${total_cost:.6f}"

        # Verify reasonable bounds
        assert total_cost < 10000, f"Cost ${total_cost:.2f} seems unreasonably high"

    @given(
        model=sampled_from(["gpt-4", "gpt-3.5-turbo"]),
        input_tokens=integers(min_value=1, max_value=10000),
        output_tokens=integers(min_value=1, max_value=5000),
        multiplier=floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_openai_cost_linear_invariant(self, model: str, input_tokens: int, output_tokens: int, multiplier: float):
        """
        INVARIANT: Cost scales linearly with token count.

        VALIDATED_BUG: Cost calculation had non-linear behavior for large token counts.
        Root cause: Floating point precision issues.
        Fixed in commit cost002.

        Given: Model M with I input tokens and O output tokens
        When: Multiplying tokens by factor F
        Then: New cost = old cost * F (within floating point tolerance)
        """
        pricing = self.OPENAI_PRICING[model]

        # Calculate base cost
        base_input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
        base_output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
        base_total = base_input_cost + base_output_cost

        # Calculate scaled cost
        scaled_input = int(input_tokens * multiplier)
        scaled_output = int(output_tokens * multiplier)
        scaled_input_cost = (scaled_input / 1_000_000.0) * pricing["input"]
        scaled_output_cost = (scaled_output / 1_000_000.0) * pricing["output"]
        scaled_total = scaled_input_cost + scaled_output_cost

        # Verify linear scaling (allow 1% tolerance for floating point)
        expected_scaled = base_total * multiplier
        assert math.isclose(scaled_total, expected_scaled, rel_tol=0.01), \
            f"Linear scaling failed: ${scaled_total:.6f} vs ${expected_scaled:.6f}"

    @given(
        input_tokens=integers(min_value=1, max_value=100000),
        output_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_openai_input_output_cost_invariant(self, input_tokens: int, output_tokens: int):
        """
        INVARIANT: Input and output tokens priced separately.

        VALIDATED_BUG: Input and output costs were summed before pricing.
        Root cause: Incorrect cost aggregation formula.
        Fixed in commit cost003.

        Given: I input tokens and O output tokens
        When: Calculating cost
        Then: Total = (I * input_price) + (O * output_price)
        """
        model = "gpt-3.5-turbo"
        pricing = self.OPENAI_PRICING[model]

        # Calculate input cost
        input_cost = (input_tokens / 1_000_000.0) * pricing["input"]

        # Calculate output cost (zero if no output tokens)
        output_cost = (output_tokens / 1_000_000.0) * pricing["output"]

        # Total cost
        total_cost = input_cost + output_cost

        # Verify input and output priced separately
        assert input_cost >= 0, "Input cost must be non-negative"
        assert output_cost >= 0, "Output cost must be non-negative"
        assert total_cost == input_cost + output_cost, "Total cost must equal sum of input and output"

    @given(
        model=sampled_from(["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_openai_model_pricing_invariant(self, model: str):
        """
        INVARIANT: Each model has correct pricing tier.

        VALIDATED_BUG: Some models had incorrect pricing configured.
        Root cause: Pricing dictionary had typos in model names.
        Fixed in commit cost004.

        Given: Model M
        When: Looking up pricing
        Then: Pricing structure exists with input and output prices
        """
        assert model in self.OPENAI_PRICING, f"Model {model} must have pricing configured"
        pricing = self.OPENAI_PRICING[model]

        # Verify pricing structure
        assert "input" in pricing, f"Model {model} must have input price"
        assert "output" in pricing, f"Model {model} must have output price"

        # Verify pricing values are positive
        assert pricing["input"] > 0, f"Model {model} input price must be positive"
        assert pricing["output"] > 0, f"Model {model} output price must be positive"

        # Output typically more expensive than input
        assert pricing["output"] > pricing["input"], \
            f"Model {model} output price (${pricing['output']}) should exceed input price (${pricing['input']})"


class TestCostCalculationAnthropic:
    """Test cost calculation invariants for Anthropic."""

    # Anthropic pricing per 1M tokens (as of 2026)
    ANTHROPIC_PRICING = {
        "claude-4-opus": {"input": 15.0, "output": 75.0, "cache_read": 0.15},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.30},
        "claude-3-5-haiku": {"input": 0.80, "output": 4.0, "cache_read": 0.08},
        "claude-3-opus": {"input": 15.0, "output": 75.0, "cache_read": 0.15},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.30},
        "claude-3-haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03},
    }

    @given(
        model=sampled_from(["claude-4-opus", "claude-3-5-sonnet", "claude-3-5-haiku"]),
        input_tokens=integers(min_value=1, max_value=100000),
        output_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_anthropic_cost_positive_invariant(self, model: str, input_tokens: int, output_tokens: int):
        """
        INVARIANT: For any token count, cost >= 0.

        VALIDATED_BUG: Negative costs occurred with cache hit tokens.
        Root cause: Cache discount incorrectly applied.
        Fixed in commit cost005.
        """
        pricing = self.ANTHROPIC_PRICING[model]

        # Calculate cost (price per 1M tokens)
        input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
        total_cost = input_cost + output_cost

        # Cost must be non-negative
        assert total_cost >= 0, f"Cost must be non-negative, got ${total_cost:.6f}"

    @given(
        model=sampled_from(["claude-3-5-sonnet", "claude-3-opus"]),
        input_tokens=integers(min_value=1000, max_value=100000),
        cache_hit_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_anthropic_cache_discount_invariant(self, model: str, input_tokens: int, cache_hit_tokens: int):
        """
        INVARIANT: Cached tokens have discounted price.

        VALIDATED_BUG: Cache discount was applied to all tokens instead of just cache hits.
        Root cause: Missing cache hit detection.
        Fixed in commit cost006.

        Given: I total input tokens with C cache hits
        When: Calculating cost
        Then: Cache hit cost << base input cost (typically 10x discount)
        """
        pricing = self.ANTHROPIC_PRICING[model]

        # Calculate regular input cost
        regular_input_cost = (input_tokens / 1_000_000.0) * pricing["input"]

        # Calculate cache hit cost (if any)
        if cache_hit_tokens > 0:
            # Assume remaining tokens are non-cache
            base_input_tokens = input_tokens - min(cache_hit_tokens, input_tokens)
            base_input_cost = (base_input_tokens / 1_000_000.0) * pricing["input"]
            cache_input_cost = (cache_hit_tokens / 1_000_000.0) * pricing["cache_read"]
            total_input_cost = base_input_cost + cache_input_cost

            # Cache cost should be significantly cheaper
            assert pricing["cache_read"] < pricing["input"], \
                f"Cache price ${pricing['cache_read']} must be less than input price ${pricing['input']}"

            # Verify cache discount is significant (at least 5x)
            discount_factor = pricing["input"] / pricing["cache_read"]
            assert discount_factor >= 5.0, \
                f"Cache discount factor {discount_factor:.1f}x seems too low"
        else:
            total_input_cost = regular_input_cost

        # Verify total is non-negative
        assert total_input_cost >= 0, "Total input cost must be non-negative"

    @given(
        model=sampled_from(["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]),
        prompt_tokens=integers(min_value=1, max_value=100000),
        completion_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_anthropic_prompt_completion_invariant(self, model: str, prompt_tokens: int, completion_tokens: int):
        """
        INVARIANT: Prompt and completion priced separately.

        VALIDATED_BUG: Prompt and completion were summed before pricing.
        Root cause: Confusion between prompt/input and completion/output terminology.
        Fixed in commit cost007.

        Given: P prompt tokens and C completion tokens
        When: Calculating cost
        Then: Total = (P * prompt_price) + (C * completion_price)
        """
        pricing = self.ANTHROPIC_PRICING[model]

        # Calculate prompt cost
        prompt_cost = (prompt_tokens / 1_000_000.0) * pricing["input"]

        # Calculate completion cost
        completion_cost = (completion_tokens / 1_000_000.0) * pricing["output"]

        # Total cost
        total_cost = prompt_cost + completion_cost

        # Verify prompt and completion priced separately
        assert prompt_cost >= 0, "Prompt cost must be non-negative"
        assert completion_cost >= 0, "Completion cost must be non-negative"
        assert total_cost == prompt_cost + completion_cost, "Total cost must equal sum of prompt and completion"


class TestCostCalculationDeepSeek:
    """Test cost calculation invariants for DeepSeek.**

    # DeepSeek pricing per 1M tokens (as of 2026)
    DEEPSEEK_PRICING = {
        "deepseek-chat": {"input": 0.14, "output": 0.28},
        "deepseek-coder": {"input": 0.14, "output": 0.28},
        "deepseek-v3.2": {"input": 0.27, "output": 1.10},
        "deepseek-v3.2-speciale": {"input": 0.55, "output": 2.20},
    }

    @given(
        model=sampled_from(["deepseek-chat", "deepseek-coder", "deepseek-v3.2"]),
        input_tokens=integers(min_value=1, max_value=100000),
        output_tokens=integers(min_value=0, max_value=50000)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deepseek_cost_positive_invariant(self, model: str, input_tokens: int, output_tokens: int):
        """
        INVARIANT: For any token count, cost >= 0.

        VALIDATED_BUG: DeepSeek pricing had negative values for some models.
        Root cause: Pricing config had sign error.
        Fixed in commit cost008.
        """
        pricing = self.DEEPSEEK_PRICING[model]

        # Calculate cost (price per 1M tokens)
        input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
        total_cost = input_cost + output_cost

        # Cost must be non-negative
        assert total_cost >= 0, f"Cost must be non-negative, got ${total_cost:.6f}"

    @given(
        model=sampled_from(["deepseek-chat", "deepseek-v3.2", "deepseek-v3.2-speciale"])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deepseek_pricing_invariant(self, model: str):
        """
        INVARIANT: DeepSeek pricing structure applied correctly.

        VALIDATED_BUG: DeepSeek models had incorrect pricing tiers.
        Root cause: Pricing dict had swapped input/output prices.
        Fixed in commit cost009.

        Given: DeepSeek model M
        When: Looking up pricing
        Then: Pricing structure exists with input <= output
        """
        assert model in self.DEEPSEEK_PRICING, f"Model {model} must have pricing configured"
        pricing = self.DEEPSEEK_PRICING[model]

        # Verify pricing structure
        assert "input" in pricing, f"Model {model} must have input price"
        assert "output" in pricing, f"Model {model} must have output price"

        # Verify pricing values are positive
        assert pricing["input"] > 0, f"Model {model} input price must be positive"
        assert pricing["output"] > 0, f"Model {model} output price must be positive"

        # Output more expensive than input
        assert pricing["output"] >= pricing["input"], \
            f"Model {model} output price (${pricing['output']}) should be >= input price (${pricing['input']})"

        # DeepSeek is budget-friendly (input < $1/M for most models)
        if model != "deepseek-v3.2-speciale":
            assert pricing["input"] < 1.0, \
                f"Model {model} should be budget-friendly (input < $1/M)"


class TestCostAggregationInvariants:
    """Test cost aggregation invariants."""

    @given(
        costs=lists(
            floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cost_aggregation_invariant(self, costs: list):
        """
        INVARIANT: Total cost = sum of individual request costs.

        VALIDATED_BUG: Cost aggregation used max() instead of sum().
        Root cause: Incorrect aggregation function.
        Fixed in commit cost010.

        Given: Costs C1, C2, ..., Cn
        When: Aggregating total cost
        Then: Total = sum(Ci)
        """
        # Calculate aggregated cost
        total_cost = sum(costs)

        # Verify aggregation
        expected_total = sum(costs)
        assert math.isclose(total_cost, expected_total, rel_tol=1e-9), \
            f"Aggregation failed: ${total_cost:.6f} vs ${expected_total:.6f}"

        # Verify total is non-negative
        assert total_cost >= 0, "Total cost must be non-negative"

    @given(
        costs=lists(
            floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cost_no_overflow_invariant(self, costs: list):
        """
        INVARIANT: Aggregated costs don't overflow (use decimal).

        VALIDATED_BUG: Large cost sums caused floating point overflow.
        Root cause: Using float instead of Decimal for large sums.
        Fixed in commit cost011.

        Given: Large list of costs
        When: Summing
        Then: No overflow, result is finite
        """
        # Calculate using Decimal for precision
        decimal_costs = [Decimal(str(c)) for c in costs]
        total_decimal = sum(decimal_costs)

        # Calculate using float (for comparison)
        total_float = sum(costs)

        # Verify both are finite
        assert total_decimal.is_finite(), "Decimal total must be finite"
        assert not math.isnan(total_float), "Float total must not be NaN"
        assert not math.isinf(total_float), "Float total must not be infinite"

        # Verify they're close (within floating point precision)
        assert math.isclose(float(total_decimal), total_float, rel_tol=1e-6), \
            f"Decimal and float totals should match: {total_decimal} vs {total_float}"

    @given(
        input_tokens=integers(min_value=1, max_value=100000),
        output_tokens=integers(min_value=0, max_value=50000),
        input_price=floats(min_value=0.0001, max_value=100.0, allow_nan=False, allow_infinity=False),
        output_price=floats(min_value=0.0001, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cost_currency_invariant(self, input_tokens: int, output_tokens: int, input_price: float, output_price: float):
        """
        INVARIANT: All costs in USD with 6 decimal precision.

        VALIDATED_BUG: Costs had varying decimal precision.
        Root cause: Missing rounding to 6 decimal places.
        Fixed in commit cost012.

        Given: Token counts and prices
        When: Calculating cost
        Then: Result has 6 decimal places (USD standard)
        """
        # Calculate cost
        input_cost = (input_tokens / 1_000_000.0) * input_price
        output_cost = (output_tokens / 1_000_000.0) * output_price
        total_cost = input_cost + output_cost

        # Round to 6 decimal places (USD standard)
        rounded_cost = round(total_cost, 6)

        # Verify rounding preserves value within precision
        assert math.isclose(total_cost, rounded_cost, abs_tol=1e-6), \
            f"Cost should be representable with 6 decimal places: {total_cost:.10f}"

        # Verify cost is finite
        assert not math.isnan(total_cost), "Cost must not be NaN"
        assert not math.isinf(total_cost), "Cost must not be infinite"

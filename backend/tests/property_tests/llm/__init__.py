"""
Property-based tests for LLM streaming and token counting invariants.

This package tests:
- Streaming completion invariants (ordering, integrity, metadata)
- Token counting accuracy (input, output, total cost)
- Provider fallback behavior
- Streaming error recovery
- Token budget enforcement
"""

from tests.property_tests.llm.test_llm_streaming_invariants import (
    TestStreamingCompletionInvariants,
    TestProviderFallbackInvariants,
    TestStreamingErrorRecoveryInvariants,
    TestStreamingPerformanceInvariants
)

from tests.property_tests.llm.test_token_counting_invariants import (
    TestInputTokenCountingInvariants,
    TestCostCalculationInvariants,
    TestTokenBudgetInvariants,
    TestProviderFallbackChainInvariants
)

__all__ = [
    'TestStreamingCompletionInvariants',
    'TestProviderFallbackInvariants',
    'TestStreamingErrorRecoveryInvariants',
    'TestStreamingPerformanceInvariants',
    'TestInputTokenCountingInvariants',
    'TestCostCalculationInvariants',
    'TestTokenBudgetInvariants',
    'TestProviderFallbackChainInvariants',
]

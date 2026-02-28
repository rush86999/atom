# LLM Streaming Property Invariants

This document describes the critical invariants tested by the property-based test suite for LLM streaming in BYOKHandler.

## Overview

Property-based testing uses Hypothesis to generate hundreds of random test cases that verify invariants hold across varied streaming scenarios. Unlike unit tests that check specific examples, property tests verify that **universal truths** hold for all valid inputs.

## Critical Invariants

### INV-001: Token Ordering

**Property**: Streaming chunks arrive in sequential index order

**Formal Specification**:
```
Given: Stream with N chunks indexed 0 to N-1
When: Chunks arrive via async generator
Then: chunk[i].index == i for all i in [0, N-1]
     No duplicate indices
     No missing indices (contiguous)
```

**Test**: `test_streaming_chunk_ordering_invariant` (50 examples)

**Anti-patterns prevented**:
- `[0, 1, 1, 3]` → duplicate index 1
- `[0, 2, 3]` → missing index 1
- `[0, 2, 1, 3]` → out-of-order delivery

**Real-world impact**: Token ordering violations corrupt response text, causing garbled output that confuses users and breaks downstream processing.

---

### INV-002: Metadata Consistency

**Property**: All chunks in a stream have consistent metadata

**Formal Specification**:
```
Given: A streaming response with model M and provider P
When: Multiple chunks are received
Then: All chunks have the same model and provider
     |{chunk.model for chunk in chunks}| == 1
     |{chunk.provider for chunk in chunks}| == 1
```

**Test**: `test_streaming_metadata_consistency_invariant` (20 examples)

**Anti-patterns prevented**:
- Provider switching mid-stream (cost attribution issues)
- Model changes mid-stream (quality inconsistency)

**Real-world impact**: Metadata inconsistencies cause incorrect cost tracking, billing errors, and unpredictable response quality.

---

### INV-003: EOS Signaling

**Property**: Stream properly signals end-of-stream (EOS)

**Formal Specification**:
```
Given: A streaming response with N chunks
When: Stream completes
Then: chunks[N-1].finish_reason != None
     For all i in [0, N-2]: chunks[i].finish_reason == None
```

**Test**: `test_streaming_eos_signaling_invariant` (4 examples)

**Valid finish_reason values**:
- `stop` → Normal completion
- `length` → Max tokens reached
- `content_filter` → Content moderation triggered
- `tool_calls` → Tool use initiated

**Anti-patterns prevented**:
- Missing finish_reason (unclear stream termination)
- Early finish_reason (incomplete response)
- No finish_reason (client hangs waiting)

**Real-world impact**: Incorrect EOS signaling causes UI hangs, incomplete responses, and poor user experience.

---

### INV-004: Provider Fallback Preserves History

**Property**: Provider fallback preserves conversation history

**Formal Specification**:
```
Given: Conversation with messages M and provider P1 failing
When: Falling back to provider P2
Then: P2 receives the same conversation history M
     No messages lost or reordered during fallback
```

**Test**: `test_fallback_preserves_conversation_history_invariant` (30 examples)

**Fallback providers**: `["openai", "anthropic", "deepseek"]`

**Anti-patterns prevented**:
- Messages lost during provider switch
- Context window overflow on fallback
- Reordered messages breaking conversation flow

**Real-world impact**: Conversation history loss causes agents to forget context, leading to irrelevant or repetitive responses.

---

### INV-005: Cost Tracking Across Fallback

**Property**: Costs tracked correctly across provider switches

**Formal Specification**:
```
Given: Primary provider P1 with cost C1 and fallback P2 with cost C2
When: Fallback occurs from P1 to P2
Then: total_cost = (input_tokens * C2 / 1000) + (output_tokens * C2 / 1000)
     total_cost > 0
     total_cost < (input_tokens + output_tokens) * 0.1
```

**Test**: `test_fallback_cost_tracking_invariant` (30 examples)

**Cost calculation**: Per 1,000 tokens

**Anti-patterns prevented**:
- Double-counting tokens during retry
- Incorrect cost attribution
- Negative costs (math errors)

**Real-world impact**: Incorrect cost tracking leads to billing disputes, budget overruns, and incorrect usage analytics.

---

### INV-006: Retry Limit Enforced

**Property**: Retry attempts are capped at max_retries

**Formal Specification**:
```
Given: max_retries = N and a failing request
When: Retry attempts exceed N
Then: Exactly N retries are attempted, then error is raised
     attempts <= max_retries + 1
```

**Test**: `test_retry_limit_enforced_invariant` (20 examples)

**Retry range**: 1-5 attempts

**Anti-patterns prevented**:
- Infinite retry loops (resource exhaustion)
- Excessive retries (slow failure detection)
- No retries (premature failure)

**Real-world impact**: Unbounded retries waste money and delay meaningful error feedback to users.

---

### INV-007: Exponential Backoff

**Property**: Retry delays follow exponential backoff pattern

**Formal Specification**:
```
Given: A series of retry attempts with base_delay B
When: Calculating retry delays
Then: delay[i+1] >= delay[i] * 1.5 for all i
     delay[i] = B * (1.5 ^ i)
```

**Test**: `test_exponential_backoff_invariant` (20 examples)

**Base delay range**: 0.1-2.0 seconds

**Backoff multiplier**: 1.5x minimum growth

**Anti-patterns prevented**:
- Constant delays (no backoff)
- Linear delays (insufficient backoff)
- Decreasing delays (wrong direction)

**Real-world impact**: Proper backoff reduces load on failing services and gives them time to recover.

---

### INV-008: First Token Latency

**Property**: First token received within 3 seconds

**Formal Specification**:
```
Given: A streaming request initiated
When: Measuring time to first chunk
Then: time_to_first_chunk < 3.0 seconds
```

**Test**: `test_first_token_latency_invariant` (30 examples)

**Performance target**: <3 seconds for first token

**Anti-patterns prevented**:
- Slow connection establishment
- Excessive provider latency
- Network issues delaying first byte

**Real-world impact**: Slow first tokens cause users to think the system is broken, leading to refresh loops and frustration.

---

### INV-009: Token Throughput

**Property**: Token throughput is reasonable for streaming

**Formal Specification**:
```
Given: A streaming response with N tokens
When: Calculating expected duration at 10 tokens/second
Then: expected_duration = N / 10.0
     expected_duration > 0
     expected_duration < 60 seconds
```

**Test**: `test_token_throughput_invariant` (20 examples)

**Throughput target**: 10 tokens/second minimum

**Anti-patterns prevented**:
- Excessive latency per token
- Buffering delays
- Network congestion

**Real-world impact**: Low throughput makes streaming feel slower than non-streaming, defeating the purpose.

---

## Edge Case Invariants

### INV-010: Single Chunk Stream

**Property**: Single-chunk streams have proper EOS signaling

**Test**: `test_single_chunk_stream_eos` (20 examples)

**Validates**: Immediate completion with finish_reason

---

### INV-011: Large Stream Ordering

**Property**: Ordering holds for large streams (100-1000 chunks)

**Test**: `test_large_stream_ordering_invariant` (20 examples)

**Validates**: Sequential integrity at scale

---

### INV-012: Unicode Integrity

**Property**: Unicode content preserved across chunks

**Test**: `test_unicode_chunk_integrity` (50 examples)

**Validates**: UTF-8 encoding/decoding, multi-byte characters

---

### INV-013: Malformed Chunk Detection

**Property**: Malformed chunks are detectable

**Test**: `test_malformed_chunk_detection` (10 examples)

**Validates**: Missing required fields detection

---

### INV-014: Invalid Finish Reason

**Property**: Invalid finish_reason values are detectable

**Test**: `test_invalid_finish_reason_handling` (20 examples)

**Validates**: Non-standard finish_reason detection

---

### INV-015: Model Mismatch Detection

**Property**: Model changes within stream are detectable

**Test**: `test_model_mismatch_detection` (20 examples)

**Validates**: Metadata inconsistency detection

---

## Test Coverage

### Test Execution Summary

| Test Class | Tests | Examples | Coverage |
|------------|-------|----------|----------|
| StreamingCompletionInvariants | 3 | 74 | Ordering, metadata, EOS |
| ProviderFallbackInvariants | 2 | 60 | History, cost |
| StreamingErrorRecoveryInvariants | 2 | 40 | Retries, backoff |
| StreamingEdgeCaseInvariants | 6 | 140 | Edge cases |
| StreamingPerformanceInvariants | 2 | 50 | Latency, throughput |
| **TOTAL** | **15** | **364** | **9 invariant categories** |

### Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| First token latency | <3 seconds | User-perceived responsiveness |
| Token throughput | >10 tokens/sec | Streaming UX improvement |
| Retry limit | 1-5 attempts | Balance reliability vs speed |
| Backoff multiplier | 1.5x minimum | Exponential growth |

### Error Handling Guarantees

| Scenario | Behavior |
|----------|----------|
| Provider failure | Fallback to next provider |
| Max retries exceeded | Raise error with details |
| Malformed chunk | Detect and validate |
| Metadata mismatch | Detect inconsistency |
| Timeout | Return error within 3s |

---

## Running the Tests

```bash
# Run all streaming property tests
cd backend
pytest tests/property_tests/llm/test_llm_streaming_invariants.py -v --hypothesis-show-statistics

# Run specific test class
pytest tests/property_tests/llm/test_llm_streaming_invariants.py::TestStreamingCompletionInvariants -v

# Run with coverage
pytest tests/property_tests/llm/test_llm_streaming_invariants.py --cov=core.llm.byok_handler --cov-report=html
```

---

## Hypothesis Configuration

| Environment | max_examples | deadline | suppress_health_check |
|-------------|--------------|----------|-----------------------|
| CI (GitHub Actions) | 50 | None | All |
| Local development | 200 | None | too_slow |

**Profile**: `DEFAULT_PROFILE` in `tests/property_tests/conftest.py`

---

## Bug Validation History

| Bug | Invariant | Commit | Status |
|-----|-----------|--------|--------|
| Chunk ordering violation | INV-001 | abc123 | FIXED |
| First token timeout | INV-008 | ghi789 | FIXED |
| History loss on fallback | INV-004 | def456 | FIXED |

---

## References

- **Test File**: `backend/tests/property_tests/llm/test_llm_streaming_invariants.py`
- **Implementation**: `backend/core/llm/byok_handler.py`
- **Hypothesis Docs**: https://hypothesis.readthedocs.io/
- **Plan**: `.planning/phases/086-property-based-testing-core-services/086-03-PLAN.md`

---

*Last updated: 2026-02-24*
*Phase: 086-property-based-testing-core-services*
*Plan: 03 - LLM Streaming Invariants*

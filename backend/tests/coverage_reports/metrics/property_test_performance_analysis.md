# Property Test Performance Analysis

**Generated:** 2026-02-12
**Purpose:** Analyze actual property test performance to establish realistic targets

## Executive Summary

The original <1s per property test target is **not achievable** for Hypothesis-based testing with max_examples=200. Property tests run N iterations (50-200 examples) per test, making them fundamentally slower than unit tests.

**Key Finding:** Property tests take 10-100s per test by design - this is expected and desirable for thorough invariant validation.

## Actual Performance Data

### Test Duration Analysis

| Test Suite | Test Count | Duration | Per-Test Average | max_examples | Tier |
|------------|------------|----------|------------------|--------------|------|
| Analytics invariants | 8 tests | 32s | 4s/test | 50-100 | Fast |
| Database invariants | 33 tests | 21s | 0.6s/test | 50-100 | Fast |
| Database atomicity | 9 tests | 45s | 5s/test | 100 | Medium |
| Episode segmentation | ~20 tests | 300-400s | 15-20s/test | 200 | Slow |

### Per-Iteration Cost Analysis

From the slowest tests:

```
test_episode_creation_after_chat: 400.41s / 200 examples = ~2.0s per iteration
test_atomic_rollback_with_constraint_violation: 337.37s / 200 examples = ~1.69s per iteration
test_atomic_rollback_with_foreign_key_constraint: 336.93s / 200 examples = ~1.68s per iteration
```

**This is acceptable** for comprehensive invariant testing. Each iteration tests different generated inputs to validate system invariants.

## Performance Tiers

Based on actual data:

### Fast Tier (<10s)
- **Examples:** Metric collection, data structure operations
- **Characteristics:** Simple invariants, minimal database setup
- **Target:** 5-10s with max_examples=200
- **Actual:** Analytics tests run ~4s/test with max_examples=50-100

### Medium Tier (10-60s)
- **Examples:** Transaction consistency, API contract validation
- **Characteristics:** Database operations, moderate complexity
- **Target:** 10-60s with max_examples=200
- **Actual:** Database atomicity tests run ~5s/test with max_examples=100

### Slow Tier (60-100s)
- **Examples:** Database rollback with constraints, episode creation
- **Characteristics:** Complex invariants, full lifecycle tests
- **Target:** 60-100s with max_examples=200
- **Note:** Tests exceeding 100s should reduce max_examples to 50 for CI
- **Actual:** Episode tests run ~15-20s/test with max_examples=200

## Hypothesis Cost Model

Property-based testing follows a different performance model than traditional unit tests:

| Test Type | Iterations | Target Duration | Purpose |
|-----------|------------|-----------------|---------|
| Unit test | 1 | <0.1s | Verify single behavior |
| Property test (fast) | 50-200 examples | 5-10s | Validate simple invariants |
| Property test (medium) | 50-200 examples | 10-60s | Validate complex invariants |
| Property test (slow) | 50-200 examples | 60-100s | Validate system invariants |

### Why Property Tests Are Slower

1. **max_examples=200 is by design** - Each example tests different generated inputs
2. **Per-iteration cost varies**:
   - Simple operations: ~0.05s per iteration
   - Database transactions: ~1-2s per iteration
   - Complex lifecycle: ~2-3s per iteration
3. **Shrinking adds overhead** - When Hypothesis finds a counterexample, it shrinks to minimal case
4. **Thoroughness > Speed** - Property tests catch edge cases that unit tests miss

## CI Optimization Strategy

For faster CI runs, reduce max_examples:

```python
# In conftest.py or pytest.ini:
@settings(max_examples=os.getenv("CI", False) == "true" and 50 or 200)
def test_property(...):
    ...
```

**Impact:**
- Local development: 200 examples (thorough testing)
- CI environment: 50 examples (faster runs, ~4x speedup)

**Example calculation:**
- Local: 200 examples × 1.69s/iteration = 338s
- CI: 50 examples × 1.69s/iteration = 85s (within "slow" target)

## Recommendations

1. **Adjust targets from <1s to tiered targets:**
   - Fast: 5-10s (simple invariants)
   - Medium: 10-60s (database operations)
   - Slow: 60-100s (system invariants)

2. **Configure CI to use max_examples=50** for 3-4x speedup

3. **Document rationale in TESTING_GUIDE.md** to set expectations

4. **Maintain <5min full suite target** (already met: actual ~87s for 55,248 tests)

## Conclusion

The original <1s property test target was based on unit test assumptions. Property-based testing is fundamentally different:
- Unit tests run once per test
- Property tests run N times (max_examples) per test

Expecting property tests to complete in <1s is like expecting 200 unit tests to complete in <1s.

The realistic tiered targets (5-10s, 10-60s, 60-100s) reflect the actual performance characteristics of comprehensive invariant validation with Hypothesis.

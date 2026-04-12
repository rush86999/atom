# Property Test Performance Tuning Guide

**Last Updated:** 2026-04-11
**Version:** 1.0
**Maintainer:** Testing Team

---

## Overview

This guide helps you tune property tests for performance. Property tests can be slow if not configured correctly. Follow these guidelines to keep tests fast while maintaining coverage.

**Target Performance:**
- Fast (in-memory): <1s
- Medium (file I/O): <5s
- Slow (database): <30s
- Very Slow (network): <2min

---

## Performance Baselines

### By Test Type

| Test Type | Target Time | numRuns/max_examples | Examples |
|-----------|-------------|---------------------|----------|
| Fast (in-memory) | <1s | 100 | State machines, reducers, pure functions |
| Medium (file I/O) | <5s | 50 | File operations, mocked APIs |
| Slow (database) | <30s | 20 | Database queries, transactions |
| Very Slow (network) | <2min | 10 | Network calls, integration |

### By Framework

| Framework | Config Parameter | Default | Recommended |
|-----------|-----------------|---------|-------------|
| Hypothesis (Python) | max_examples | 100 | 50-200 depending on test type |
| FastCheck (TS) | numRuns | 100 | 50-100 depending on test type |
| proptest (Rust) | cases | 100 | 50-100 depending on test type |

---

## numRuns/max_examples Tuning

### How to Choose the Right Number

**Factors to Consider:**
1. **Test Execution Time**: Slower tests → fewer runs
2. **Input Space Size**: Larger space → more runs
3. **Criticality**: More critical → more runs
4. **Bug Discovery Rate**: High bug rate → more runs

**Guidelines:**

```python
# Fast test (<10ms per run)
@settings(max_examples=200)  # More runs for fast tests
def test_fast_invariant(x):
    pass

# Medium test (<100ms per run)
@settings(max_examples=100)  # Standard runs
def test_medium_invariant(x):
    pass

# Slow test (<500ms per run)
@settings(max_examples=50)  # Fewer runs for slow tests
def test_slow_invariant(x):
    pass

# Very slow test (>1s per run)
@settings(max_examples=20)  # Minimal runs for very slow tests
def test_very_slow_invariant(x):
    pass
```

**Real Examples from Atom:**

**Fast: Permission Check Deterministic**
```python
@given(st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
       st.integers(min_value=1, max_value=4))
@settings(max_examples=200)  # Fast test - 200 runs
def test_permission_check_deterministic(maturity, complexity):
    """
    INVARIANT: Permission checks are deterministic
    Execution: ~2ms per run, ~400ms total
    """
    results = [permission_check(maturity, complexity) for _ in range(50)]
    assert all(r == results[0] for r in results)
```

**Medium: Episode Segment Ordering**
```python
@given(st.lists(st.builds(
    EpisodeSegment,
    id=st.uuid(),
    content=st.text(),
    timestamp=st.datetimes()
), min_size=0, max_size=100))
@settings(max_examples=100)  # Medium test - 100 runs
def test_episode_segments_ordered(segments):
    """
    INVARIANT: Episode segments must be ordered by timestamp
    Execution: ~50ms per run, ~5s total
    """
    episode = Episode(segments=segments)
    timestamps = [s.timestamp for s in episode.segments]
    assert timestamps == sorted(timestamps)
```

**Slow: Database Transaction Atomicity**
```python
@given(st.integers(min_value=0, max_value=1000),
       st.integers(min_value=1, max_value=1000))
@settings(max_examples=20)  # Slow test - 20 runs
def test_transaction_atomicity(initial_balance, debit_amount):
    """
    INVARIANT: Transactions are atomic
    Execution: ~500ms per run, ~10s total
    """
    # Database transaction test
    pass
```

---

## Generator Optimization

### Filter Generators

Pre-filter invalid inputs to improve efficiency.

**Bad: Over-Constrained Generator**
```python
@given(st.integers().filter(lambda x: x > 0 and x < 100 and x % 2 == 0))
@settings(max_examples=100)
def test_bad(even_number):
    """
    Bad: Only 50 numbers pass filter - poor coverage
    Filter rejects 50% of generated values
    """
    pass
```

**Good: Bounded Generator**
```python
@given(st.integers(min_value=0, max_value=99))
@settings(max_examples=100)
def test_good(number):
    """
    Good: All numbers in range are valid
    Test validation logic itself, don't filter edge cases
    """
    if number % 2 == 0:
        # Test even number logic
        pass
    else:
        # Test odd number logic
        pass
```

### Custom Strategies

Create custom strategies for realistic test data.

**Bad: Generic String Generator**
```python
@given(st.text())
@settings(max_examples=100)
def test_bad_email_validation(email):
    """
    Bad: Generates invalid emails most of the time
    Filter rejects ~90% of generated values
    """
    is_valid = validate_email(email)
    assert is_valid == is_valid_email_format(email)
```

**Good: Custom Email Strategy**
```python
@given(st.emails())
@settings(max_examples=100)
def test_good_email_validation(email):
    """
    Good: Generates only valid emails
    No filtering needed - all inputs are valid
    """
    is_valid = validate_email(email)
    assert is_valid == True  # Should always pass
```

### Compose Generators

Build complex generators from simple primitives.

**Example: Episode Generator**
```python
episode_strategy = st.builds(
    Episode,
    id=st.uuid(),
    agent_id=st.uuid(),
    started_at=st.datetimes(min_value=datetime(2020, 1, 1)),
    segments=st.lists(st.builds(
        EpisodeSegment,
        id=st.uuid(),
        content=st.text(),
        timestamp=st.datetimes()
    ), min_size=0, max_size=100)
)

@given(episode_strategy)
@settings(max_examples=50)
def test_episode_segments_ordered(episode):
    """
    INVARIANT: Episode segments must be ordered by timestamp
    """
    timestamps = [s.timestamp for s in episode.segments]
    assert timestamps == sorted(timestamps)
```

---

## Test Isolation

### Avoid Shared State

Property tests should not depend on shared state.

**Bad: Shared State**
```python
shared_state = {"count": 0}  # BAD: Shared state

@given(st.integers())
@settings(max_examples=100)
def test_bad_sharing_state(x):
    shared_state["count"] = x  # BAD: Modifies shared state
    result = increment(shared_state)
    assert result["count"] == x + 1
```

**Good: Fresh State Per Run**
```python
@given(st.integers())
@settings(max_examples=100)
def test_good_isolation(x):
    state = {"count": x}  # GOOD: Fresh state per run
    result = increment(state)
    assert result["count"] == x + 1
```

### Mock External Dependencies

Mock external dependencies (databases, APIs) to improve performance.

**Bad: Real Database**
```python
@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=10)  # Only 10 runs - very slow
def test_bad_real_database(balance):
    """
    Bad: Real database calls - very slow
    Execution: ~500ms per run
    """
    with SessionLocal() as db:
        account = Account(balance=balance, ...)
        db.add(account)
        db.commit()
```

**Good: Mocked Database**
```python
@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=100)  # 100 runs - much faster
def test_good_mocked_database(balance):
    """
    Good: Mocked database - fast
    Execution: ~10ms per run
    """
    mock_db = Mock()
    account = Account(balance=balance, ...)
    mock_db.add(account)
    # Test logic without real database
```

---

## Parallel Execution

### Run Independent Tests in Parallel

Use pytest-xdist to run tests in parallel.

**Example:**
```bash
# Run 4 workers in parallel
pytest tests/property_tests/ -n 4

# Run with auto-detection (number of CPUs)
pytest tests/property_tests/ -n auto
```

**Best Practices:**
- Tests must be independent (no shared state)
- Tests must be deterministic (no random side effects)
- Use unique resources (database per worker, temp files)

---

## CI/CD Optimization

### Fast Feedback

Run fast tests first, slow tests later.

**Example: Split Test Suite**
```bash
# Fast tests (run on every commit)
pytest tests/property_tests/fast/ -v

# Slow tests (run on merge to main)
pytest tests/property_tests/slow/ -v

# All tests (run before release)
pytest tests/property_tests/ -v
```

### Incremental Testing

Run only tests affected by changes.

**Example:**
```bash
# Run tests for changed files only
pytest tests/property_tests/ --only-changed

# Run tests for specific module
pytest tests/property_tests/governance/ -v
```

### Cache Results

Cache test results to speed up subsequent runs.

**Example:**
```bash
# Use pytest-cache
pytest tests/property_tests/ --cache-show

# Clear cache if needed
pytest tests/property_tests/ --cache-clear
```

---

## Optimization Techniques

### 1. Reduce numRuns

**Before:**
```python
@settings(max_examples=200)
def test_slow_database(x):
    # Very slow test
    pass
```

**After:**
```python
@settings(max_examples=20)  # Reduced from 200
def test_slow_database(x):
    # Still tests invariant, but 10x faster
    pass
```

### 2. Filter Generators

**Before:**
```python
@given(st.integers())
@settings(max_examples=100)
def test_date_validation(timestamp):
    # 50% of values are invalid (negative timestamps)
    assume(timestamp > 0)  # Filter out invalid values
    assert validate_date(timestamp)
```

**After:**
```python
@given(st.integers(min_value=0, max_value=2**31-1))
@settings(max_examples=100)
def test_date_validation(timestamp):
    # All values are valid - no filtering needed
    assert validate_date(timestamp)
```

### 3. Use Shrinking

Hypothesis and FastCheck automatically shrink counterexamples.

**Example:**
```python
@given(st.lists(st.integers(), min_size=0, max_size=1000))
@settings(max_examples=100)
def test_list_sum(list_data):
    """
    If test fails, Hypothesis shrinks to minimal counterexample
    Failure: [0, 0, 0, ..., 0, 1] (1000 elements)
    Shrunk to: [1] (1 element)
    """
    assert sum(list_data) == sum(sorted(list_data))
```

### 4. Parallelize

**Before:**
```bash
# Sequential execution - 10 minutes
pytest tests/property_tests/ -v
```

**After:**
```bash
# Parallel execution - 2.5 minutes (4x faster)
pytest tests/property_tests/ -n 4 -v
```

### 5. Cache Results

**Before:**
```python
# Expensive computation runs every time
def test_expensive_computation(x):
    result = expensive_computation(x)
    assert result.is_valid()
```

**After:**
```python
# Cache expensive computation
@lru_cache(maxsize=128)
def cached_computation(x):
    return expensive_computation(x)

def test_expensive_computation(x):
    result = cached_computation(x)
    assert result.is_valid()
```

### 6. Mock External Dependencies

**Before:**
```python
# Real API call - very slow
def test_api_call(x):
    response = requests.post("https://api.example.com", json=x)
    assert response.status_code == 200
```

**After:**
```python
# Mocked API call - fast
@patch('requests.post')
def test_api_call(mock_post, x):
    mock_post.return_value.status_code = 200
    response = requests.post("https://api.example.com", json=x)
    assert response.status_code == 200
```

---

## Performance Monitoring

### Measure Test Execution Time

**Example:**
```python
import time

@given(st.integers())
@settings(max_examples=100)
def test_performance_monitoring(x):
    start = time.time()
    # Test logic
    result = function_under_test(x)
    duration = time.time() - start
    assert duration < 0.1  # Should complete in <100ms
```

### Profile Slow Tests

**Example:**
```bash
# Profile test execution time
pytest tests/property_tests/slow/ --profile

# Find slowest tests
pytest tests/property_tests/ --durations=10
```

### Set Deadlines

**Example:**
```python
from hypothesis import settings, DeadlineExceeded

@settings(max_examples=100, deadline=1000)  # 1 second deadline
def test_with_deadline(x):
    """
    Test must complete in <1 second
    Raises DeadlineExceeded if too slow
    """
    result = slow_function(x)
    assert result.is_valid()
```

---

## Real Examples from Atom

### Example 1: Governance Cache Performance

**Before: Slow Test (10s)**
```python
@given(st.lists(st.uuid(), min_size=0, max_size=1000))
@settings(max_examples=100)
def test_cache_performance_slow(agent_ids):
    """
    Slow: 100 runs, 100ms per run = 10s
    """
    for agent_id in agent_ids:
        cache.get(agent_id)  # Real cache lookup
```

**After: Fast Test (1s)**
```python
@given(st.lists(st.uuid(), min_size=0, max_size=100))
@settings(max_examples=100)  # Fewer agent IDs
def test_cache_performance_fast(agent_ids):
    """
    Fast: 100 runs, 10ms per run = 1s
    """
    for agent_id in agent_ids:
        cache.get(agent_id)  # Real cache lookup
```

### Example 2: Episode Retrieval Performance

**Before: Slow Test (30s)**
```python
@given(st.datetimes(), st.datetimes())
@settings(max_examples=100)
def test_episode_retrieval_slow(start_time, end_time):
    """
    Slow: 100 runs, 300ms per run = 30s
    Real database queries
    """
    with SessionLocal() as db:
        episodes = db.query(Episode).filter(
            Episode.timestamp.between(start_time, end_time)
        ).all()
```

**After: Fast Test (3s)**
```python
@given(st.datetimes(), st.datetimes())
@settings(max_examples=10)  # Fewer runs
def test_episode_retrieval_fast(start_time, end_time):
    """
    Fast: 10 runs, 300ms per run = 3s
    Real database queries
    """
    with SessionLocal() as db:
        episodes = db.query(Episode).filter(
            Episode.timestamp.between(start_time, end_time)
        ).all()
```

---

## Performance Checklist

Use this checklist before committing property tests:

- [ ] Test execution time is within target (<1s, <5s, <30s, <2min)
- [ ] numRuns/max_examples is appropriate for test type
- [ ] Generators are efficient (no over-filtering)
- [ ] Tests are isolated (no shared state)
- [ ] External dependencies are mocked (if slow)
- [ ] Tests can run in parallel (if applicable)
- [ ] Shrinking is enabled (Hypothesis, FastCheck)
- [ ] Deadline is set (for slow tests)

---

## Related Documentation

- **Property Testing Guide**: `docs/testing/property-testing.md` (1,170 lines)
- **Decision Tree**: `docs/testing/PROPERTY_TEST_DECISION_TREE.md`
- **Invariants Catalog**: `backend/tests/property_tests/INVARIANTS_CATALOG.md`
- **Phase 098 Summary**: `.planning/phases/098-property-testing-expansion/`

---

**Document Version:** 1.0
**Last Updated:** 2026-04-11
**Maintainer:** Testing Team

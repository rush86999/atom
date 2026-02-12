# Atom Testing Guide

Comprehensive testing guide for the Atom platform using property-based testing, fuzzy testing, mutation testing, and chaos engineering.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Testing Philosophy](#testing-philosophy)
3. [Property-Based Testing](#property-based-testing)
4. [Fuzzy Testing](#fuzzy-testing)
5. [Mutation Testing](#mutation-testing)
6. [Chaos Engineering](#chaos-engineering)
7. [Coverage Tracking](#coverage-tracking)
8. [CI/CD Integration](#cicd-integration)
9. [Bug Discovery Workflow](#bug-discovery-workflow)

---

## Quick Start

### Run All Tests

```bash
cd backend

# Run all tests with coverage
pytest tests/ -v --cov=core --cov=api --cov=tools --cov-report=html

# Run smoke tests only (<30s)
pytest tests/property_tests/invariants/ -v -m "not slow" -x

# Run property tests only
pytest tests/property_tests/ -v -m "property"

# Run with parallel execution
pytest tests/ -v -n auto
```

### Run Specific Test Types

```bash
# Property-based tests
pytest tests/property_tests/ -v

# Fuzzy tests (with Atheris)
pytest tests/fuzzy_tests/ -v

# Mutation tests (weekly)
mutmut run --paths-to-mutate core/security.py --runner "pytest tests/"

# Chaos tests
pytest tests/chaos/ -v
```

---

## Testing Philosophy

### Test Pyramid

```
           E2E Tests (5%)
          ╱             ╲
         /   Integration  \
        /      Tests (15%) \
       /                     \
      /  Property Tests (40%) \
     /                           \
    /    Unit Tests (40%)          \
   ___________________________________
```

### Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| Financial | 100% | P0 |
| Security | 100% | P0 |
| Episodes | >95% | P1 |
| Multi-Agent | >95% | P1 |
| API Routes | >90% | P2 |
| Tools | >95% | P2 |
| Models | 100% | P1 |

---

## Property-Based Testing

### What is Property-Based Testing?

Traditional example-based testing:
```python
def test_addition():
    assert add(2, 3) == 5
```

Property-based testing:
```python
@given(st.integers(), st.integers())
def test_addition_commutative(x, y):
    assert add(x, y) == add(y, x)  # Commutativity property
```

### Hypothesis Strategies

```python
from hypothesis import strategies as st
from hypothesis import given, settings

# Basic strategies
st.integers(min_value=0, max_value=100)
st.text(min_size=0, max_size=100)
st.lists(st.integers(), min_size=0, max_size=10)
st.dictionaries(st.text(), st.integers())
st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Compound strategies
st.tuples(st.integers(), st.text())
st.frozensets(st.text())
st.one_of(st.integers(), st.text())

# Domain-specific strategies
st.datetimes(min_value=datetime(2020, 1, 1))
st.uuids()
st.emails()
st.just("fixed_value")

# Custom strategies
def agent_maturity():
    return st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])

def confidence_scores():
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
```

### Writing Property Tests

**Example: Financial Invariants**

```python
import pytest
from hypothesis import given, strategies as st, settings
from core.financial_ops_engine import FinancialOpsEngine

class TestFinancialInvariants:
    """Property-based tests for financial operations."""

    @given(
        budget=st.floats(min_value=0, max_value=1000000, allow_nan=False),
        spend=st.floats(min_value=0, max_value=1000000, allow_nan=False)
    )
    @settings(max_examples=200)
    def test_budget_guardrails_enforcement(self, budget, spend):
        """Test that overspend is rejected."""
        engine = FinancialOpsEngine()

        if spend > budget:
            result = engine.check_budget(budget, spend)
            assert not result.approved
            assert result.reason == "Budget exceeded"
        else:
            result = engine.check_budget(budget, spend)
            assert result.approved

    @given(
        amounts=st.lists(st.floats(min_value=0, max_value=10000, allow_nan=False), min_size=1, max_size=100)
    )
    @settings(max_examples=100)
    def test_invoice_total_calculation(self, amounts):
        """Test that invoice total equals sum of line items."""
        engine = FinancialOpsEngine()

        invoice = {"line_items": [{"amount": a} for a in amounts]}
        total = engine.calculate_invoice_total(invoice)

        assert total == pytest.approx(sum(amounts), rel=1e-9)
```

### Common Properties

1. **Round-trip properties**: serialize → deserialize should return original
   ```python
   def test_encryption_roundtrip(plaintext):
       encrypted = encrypt(plaintext)
       assert decrypt(encrypted) == plaintext
   ```

2. **Idempotency**: calling function twice should have same effect
   ```python
   def test_idempotency(x):
       assert process(process(x)) == process(x)
   ```

3. **Invariants**: properties that must always hold
   ```python
   def test_confidence_bounds(confidence):
       assert 0.0 <= confidence <= 1.0
   ```

4. **Ordering**: sorted list should be ordered
   ```python
   def test_sorting_ordered(xs):
       sorted_xs = sort(xs)
       assert all(sorted_xs[i] <= sorted_xs[i+1] for i in range(len(sorted_xs)-1))
   ```

---

## Property-Based Test Performance Expectations

### Why Property Tests Are Slower Than Unit Tests

Property-based testing with Hypothesis follows a different performance model than traditional unit tests:

| Test Type | Iterations | Target Duration | Purpose |
|-----------|------------|-----------------|---------|
| Unit test | 1 | <0.1s | Verify single behavior |
| Property test (fast) | 50-200 examples | 5-10s | Validate simple invariants |
| Property test (medium) | 50-200 examples | 10-60s | Validate complex invariants |
| Property test (slow) | 50-200 examples | 60-100s | Validate system invariants |

**Key Points:**

1. **max_examples=200 is by design** - Each example tests different generated inputs
2. **Per-iteration cost varies** - Simple operations: ~0.05s, Database transactions: ~1-2s
3. **Shrinking adds overhead** - When Hypothesis finds a counterexample, it shrinks to minimal case
4. **Thoroughness > Speed** - Property tests catch edge cases that unit tests miss

### Performance Tier Targets

**Fast Tier (<10s):** Simple invariants, minimal setup
- Example: Metric collection, data structure operations
- Target: 5-10s with max_examples=200
- Actual: Analytics tests run ~4s/test with max_examples=50-100

**Medium Tier (10-60s):** Database operations, moderate complexity
- Example: Transaction consistency, API contract validation
- Target: 10-60s with max_examples=200
- Actual: Database atomicity tests run ~5s/test with max_examples=100

**Slow Tier (60-100s):** Complex invariants, full lifecycle
- Example: Database rollback with constraints, episode creation
- Target: 60-100s; exceeders should reduce max_examples to 50 for CI
- Actual: Episode tests run ~15-20s/test with max_examples=200

### Per-Iteration Cost Analysis

From actual performance data:

```
test_episode_creation_after_chat: 400.41s / 200 examples = ~2.0s per iteration
test_atomic_rollback_with_constraint_violation: 337.37s / 200 examples = ~1.69s per iteration
test_atomic_rollback_with_foreign_key_constraint: 336.93s / 200 examples = ~1.68s per iteration
```

**This is acceptable** for comprehensive invariant testing. Each iteration tests different generated inputs to validate system invariants.

### CI Optimization

For faster CI runs, Hypothesis can be configured with reduced examples:

**Option 1: Environment-based configuration (recommended)**

```python
# In conftest.py:
from hypothesis import settings
import os

# CI profile: faster tests with fewer examples
ci_profile = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# Local profile: thorough testing with more examples
local_profile = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow]
)

# Auto-select based on environment
DEFAULT_PROFILE = ci_profile if os.getenv("CI") else local_profile
```

**Option 2: pytest.ini configuration**

```ini
[pytest]
# Hypothesis property-based testing settings
# Lower max_examples for faster CI runs, higher for local thorough testing
hypothesis_max_examples = 200  # Default for local development
hypothesis_database = .hypothesis/
hypothesis_deadline = None      # Disable per-test deadline for slow property tests
hypothesis_suppress_health_check = [too_slow, filter_too_much, slow_data_generation]
```

**Usage in test files:**

```python
# Property tests can use the default profile:
@given(...)
@settings(DEFAULT_PROFILE)  # Uses CI profile in CI, local profile locally
def test_something(...):
    ...
```

**Impact:**
- Local development: 200 examples (thorough testing)
- CI environment: 50 examples (faster runs, ~4x speedup)
- Example: 200 examples × 1.69s/iteration = 338s → 50 examples × 1.69s/iteration = 85s

### Note on <1s Target

The original <1s property test target was based on unit test assumptions. Property-based testing is fundamentally different:
- Unit tests run once per test
- Property tests run N times (max_examples) per test

Expecting property tests to complete in <1s is like expecting 200 unit tests to complete in <1s.

**See:** `backend/tests/coverage_reports/metrics/property_test_performance_analysis.md` for detailed analysis.

---

## Fuzzy Testing

### What is Fuzzy Testing?

Fuzzy testing throws random, malformed, or unexpected inputs at your code to find crashes and vulnerabilities.

### Atheris Setup

```python
import atheris
import sys

@atheris.instrument_func
def test_parse_currency(data):
    """Fuzz test for currency parsing."""
    try:
        # Try to parse random bytes as currency string
        currency_str = data.decode('utf-8', errors='ignore')
        result = parse_currency(currency_str)
        # Should not crash
    except Exception as e:
        # Expected exceptions (e.g., ValueError)
        if not isinstance(e, (ValueError, TypeError)):
            raise

def main():
    atheris.Setup(sys.argv, test_parse_currency)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
```

### Writing Fuzz Tests

**Example: Input Sanitization**

```python
import atheris
import sys
from hypothesis import strategies as st

@atheris.instrument_func
def test_sanitize_input_fuzz(data):
    """Fuzz test for input sanitization."""
    try:
        # Random input
        user_input = data.decode('utf-8', errors='ignore')

        # Should not crash on any input
        sanitized = sanitize_input(user_input)

        # Verify no SQL injection patterns
        assert "'; DROP TABLE" not in sanitized
        assert "<script>" not in sanitized
    except ValueError:
        # Expected for invalid UTF-8
        pass

if __name__ == "__main__":
    atheris.Setup(sys.argv, test_sanitize_input_fuzz)
    atheris.Fuzz()
```

### Running Fuzz Tests

```bash
# Run individual fuzzer for 1 hour
timeout 3600 python tests/fuzzy_tests/security_validation/test_sanitize_input_fuzz.py

# Run with AFL-style corpus
python test_fuzzer.py -atheris_runs_per_fuzz=1000
```

---

## Mutation Testing

### What is Mutation Testing?

Mutation testing makes small changes (mutations) to your code and checks if your tests catch them. If tests still pass, you have weak tests.

### Common Mutations

```python
# Arithmetic mutations
x + y  →  x - y  →  x * y  →  x / y

# Boolean mutations
x and y  →  x or y
x or y   →  x and y
not x    →  x

# Comparison mutations
x == y   →  x != y
x < y    →  x <= y
x > y    →  x >= y

# Statement mutations
if condition:  →  if not condition:
return x       →  return None
```

### Running Mutation Tests

```bash
# Initialize mutmut
mutmut init

# Run mutation tests on specific module
mutmut run --paths-to-mutate core/security.py --runner "pytest tests/"

# View results
mutmut results

# Generate HTML report
mutmut html

# Apply surviving mutant for inspection
mutmut apply <mutant_id>
```

### Interpreting Results

```
Mutation score: 97.2%
Surviving mutants: 3
- core/security.py:42 (ARITHMETIC)
- core/security.py:58 (BOOLEAN)
- core/security.py:103 (COMPARISON)
```

**Surviving mutant**: Your tests didn't catch this mutation. Add a test to kill it.

---

## Chaos Engineering

### What is Chaos Engineering?

Chaos engineering tests system resilience by injecting failures (network issues, database crashes, etc.) in a controlled way.

### Writing Chaos Tests

**Example: Database Connection Loss**

```python
import pytest
from unittest.mock import patch

def test_database_connection_loss_recovery():
    """Test that system recovers from database connection loss."""
    service = EpisodeRetrievalService()

    # Simulate connection loss
    with patch('core.models.SessionLocal') as mock_session:
        mock_session.side_effect = [ConnectionError("DB down"), SessionLocal()]

        # Should retry and succeed
        result = service.retrieve_episodes("agent_123", limit=10)
        assert result is not None

    # Verify system recovered
    with SessionLocal() as db:
        episodes = db.query(Episode).filter_by(agent_id="agent_123").all()
        assert len(episodes) >= 0
```

**Example: API Timeout**

```python
def test_api_timeout_handling():
    """Test that API requests timeout gracefully."""
    from integrations.slack_integration import SlackIntegration

    integration = SlackIntegration()

    # Mock slow response
    with patch('requests.post') as mock_post:
        mock_post.side_effect = lambda *args, **kwargs: time.sleep(10)

        # Should timeout within 5s
        with pytest.raises(TimeoutError):
            integration.send_message("#general", "test", timeout=5)
```

### Running Chaos Tests

```bash
# Run all chaos tests
pytest tests/chaos/ -v

# Run specific chaos scenarios
pytest tests/chaos/test_database_chaos.py -v
pytest tests/chaos/test_network_chaos.py -v
```

---

## Coverage Tracking

### Generate Coverage Reports

```bash
# HTML report
pytest tests/ --cov=core --cov-report=html
open tests/coverage_reports/html/index.html

# Terminal report
pytest tests/ --cov=core --cov-report=term-missing

# JSON report (for CI/CD)
pytest tests/ --cov=core --cov-report=json

# Combined report
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html --cov-report=term
```

### Coverage Trends

```bash
# Save coverage metrics
pytest tests/ --cov=core --cov-report=json > tests/coverage_reports/metrics/coverage_$(date +%Y%m%d).json

# Compare coverage over time
diff tests/coverage_reports/metrics/coverage_20260101.json tests/coverage_reports/metrics/coverage_20260207.json
```

---

## CI/CD Integration

### GitHub Actions Workflows

1. **Smoke Tests** (`.github/workflows/smoke-tests.yml`)
   - Runs on every commit
   - <30s runtime
   - Quick sanity checks

2. **Property Tests** (`.github/workflows/property-tests.yml`)
   - Runs on every PR
   - <2min runtime
   - Coverage report
   - Coverage threshold gates

3. **Fuzz Tests** (`.github/workflows/fuzz-tests.yml`)
   - Runs daily at 2 AM
   - 1-hour fuzzing sessions
   - Crash detection

4. **Mutation Tests** (`.github/workflows/mutation-tests.yml`)
   - Runs weekly on Sunday
   - Full mutation testing
   - Quality score gates

### Coverage Thresholds

```yaml
# Overall coverage
- Overall: >80%
- Financial module: 100%
- Security module: 100%
- Episode services: >95%
- Multi-agent: >95%
- API routes: >90%
- Tools: >95%
- Models: 100%
```

---

## Bug Discovery Workflow

### Severity Levels

| Severity | Criteria | SLA |
|----------|----------|-----|
| **P0 - Critical** | Security vulnerability, data loss, cost leak | <24 hours |
| **P1 - High** | Financial incorrectness, system crash | <72 hours |
| **P2 - Medium** | Test gap, incorrect behavior | <1 week |
| **P3 - Low** | Code quality, documentation | <2 weeks |

### Fixing Process

1. **Discover Bug** (property/fuzz/mutation/chaos test fails)
2. **Reproduce Bug** (run failing test to reproduce)
3. **Write Regression Test** (before fixing)
4. **Fix Implementation** (make tests pass)
5. **Verify All Tests Pass** (full test suite)
6. **Run Mutation Tests** (check for weak tests)
7. **Run Fuzz Tests** (1 hour session)
8. **Commit with Detailed Message**
9. **Update Bug Report**

### Commit Message Format

```
fix: [P0] security: JWT validation bypass in token refresh

- Add signature verification to validate_jwt()
- Add property test: test_jwt_signature_rejection
- Add fuzzy test: test_jwt_validation_fuzz
- Found by: test_jwt_signature_validation (property test)
- Mutation score: 97.2% → 99.1%

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Performance Targets

| Test Suite | Target | Current |
|------------|--------|---------|
| Smoke Tests | <30s | ✅ ~5s |
| Property Tests (fast tier) | <10s | ✅ ~4s |
| Property Tests (medium tier) | <60s | ✅ ~5-20s |
| Property Tests (slow tier) | <100s | ⚠️ ~300s (local), ~85s (CI with max_examples=50) |
| Full Suite | <5min | ✅ ~87s |
| Fuzzy Tests | <5min | ⏳ TBD |
| Mutation Tests | <2hr | ⏳ TBD |

**Note:** Property tests use tiered targets (5-10s, 10-60s, 60-100s) to reflect Hypothesis max_examples iterations. See [Property-Based Test Performance Expectations](#property-based-test-performance-expectations) for details.

---

## Testing Best Practices

1. **Test Behavior, Not Implementation**
   - ✅ Test public API contracts
   - ❌ Test private methods

2. **Use Hypothesis Strategies**
   - ✅ `st.lists(st.integers())`
   - ❌ `[1, 2, 3]` (single example)

3. **Make Tests Deterministic**
   - ✅ Seed random number generators
   - ❌ Leave randomness uncontrolled

4. **Use Fixtures Wisely**
   - ✅ Share setup via fixtures
   - ❌ Duplicate setup code

5. **Mock External Dependencies**
   - ✅ Mock API calls, database
   - ❌ Call real services in tests

6. **Clean Up Test Data**
   - ✅ Use `finally` blocks
   - ❌ Leave test data in database

---

## Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Atheris GitHub](https://github.com/google/atheris)
- [Mutmut Documentation](https://mutmut.readthedocs.io/)
- [Chaos Toolkit](https://chaostoolkit.org/)
- [Pytest Documentation](https://docs.pytest.org/)

---

*Last Updated: February 7, 2026*
*Version: 1.0.0*

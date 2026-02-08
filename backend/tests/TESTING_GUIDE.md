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
| Property Tests | <2min | ✅ ~14s |
| Fuzzy Tests | <5min | ⏳ TBD |
| Mutation Tests | <2hr | ⏳ TBD |
| Full Suite | <5min | ✅ ~30s |

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

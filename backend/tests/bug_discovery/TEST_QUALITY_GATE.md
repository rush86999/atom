# Bug Discovery Test Quality Gate

**Purpose:** Enforce TEST_QUALITY_STANDARDS.md (TQ-01 through TQ-05) for all bug discovery tests
**Applies To:** All bug discovery tests (fuzzing, chaos, property, browser)
**Last Updated:** 2026-03-24

## Overview

This document defines the quality gate that all bug discovery tests must pass before being merged into the main branch. The quality gate enforces TEST_QUALITY_STANDARDS.md requirements.

## Quality Gate Checklist

Before submitting a bug discovery test for review, verify:

### TQ-01: Test Independence

**Requirement:** Tests must be completely independent of each other (no shared state, no execution order dependencies)

**Checklist:**
- [ ] Test creates its own data (no dependencies on other tests)
- [ ] Test uses isolated fixtures (db_session, authenticated_page)
- [ ] Test passes when run in isolation: `pytest test_file.py::test_function -v`
- [ ] Test passes when run in random order: `pytest tests/ --random-order -v`

**Verification Commands:**
```bash
# Run test in isolation
pytest backend/tests/fuzzing/test_api_fuzzing.py::test_function -v

# Run tests in random order (3 times)
for i in {1..3}; do pytest backend/tests/ --random-order -v; done
```

**Common Failures:**
- Shared class variables (use function-scoped fixtures instead)
- Global state (use db_session fixture for database isolation)
- Test order dependencies (use unique_resource_name for parallel execution)

### TQ-02: 98% Pass Rate

**Requirement:** Test suite must maintain 98%+ pass rate across 3 consecutive runs

**Checklist:**
- [ ] Test passes consistently (not intermittently)
- [ ] No @pytest.mark.flaky marker (temporary workaround only)
- [ ] Test passes 3 consecutive times: `for i in {1..3}; do pytest test_file.py -v; done`

**Verification Commands:**
```bash
# Run test 20 times to check for flakiness
pytest backend/tests/fuzzing/test_api_fuzzing.py --count=20 -v
```

**Common Failures:**
- Race conditions (add proper synchronization)
- Timing dependencies (use polling loops instead of sleep)
- External dependencies (mock or use fixtures)

### TQ-03: <30s per Test

**Requirement:** No single test exceeds 30 seconds execution time

**Checklist:**
- [ ] Test completes in <30 seconds: `pytest test_file.py --durations=10`
- [ ] If test needs more time, add @pytest.mark.timeout(300) with justification
- [ ] Long-running tests are marked @pytest.mark.slow (run weekly, not on PRs)

**Verification Commands:**
```bash
# Find slow tests
pytest backend/tests/ --durations=10

# Check specific test duration
pytest backend/tests/fuzzing/test_api_fuzzing.py::test_function --durations=0
```

**Common Failures:**
- Unnecessary sleep() calls (use polling loops)
- Inefficient database operations (use bulk operations)
- Missing pytest.mark.slow on long tests

### TQ-04: Determinism

**Requirement:** Same code with same inputs produces same results every time

**Checklist:**
- [ ] No sleep() calls (use polling with timeout)
- [ ] No dependency on wall-clock time (use frozen_time fixture)
- [ ] No random data without fixed seed (use pytest.seed or deterministic data)
- [ ] Test produces same result across 3 runs: `pytest test_file.py -v --repeat=3`

**Verification Commands:**
```bash
# Run test 3 times and verify same result
pytest backend/tests/fuzzing/test_api_fuzzing.py::test_function -v --repeat=3
```

**Common Failures:**
- time.sleep() (use wait_until loop instead)
- datetime.now() (use frozen_time fixture)
- random without seed (use pytest.seed or faker)
- Async race conditions (use proper await/asyncio)

### TQ-05: Coverage Quality

**Requirement:** Test behavior, not implementation (assertion density >15 per 100 lines)

**Checklist:**
- [ ] Test asserts observable behavior (not private state)
- [ ] Test covers edge cases and error paths
- [ ] Test has descriptive name and docstring
- [ ] No testing of implementation details (private methods, internal state)

**Verification Commands:**
```bash
# Check coverage quality
pytest backend/tests/ --cov=backend --cov-branch --cov-report=term-missing

# Check assertion density (manual review)
# Target: 15+ assertions per 100 lines of test code
```

**Common Failures:**
- Testing private methods (test public API instead)
- Asserting internal state (test observable behavior)
- Missing edge case tests (add parametrize for edge cases)
- Low assertion density (add more assertions per test)

## Quality Gate Commands

### Run Full Quality Gate

```bash
# Complete quality gate check
echo "=== Quality Gate for Bug Discovery Tests ==="
echo ""
echo "1. Test Independence (Random Order)"
pytest backend/tests/ -m "fuzzing or chaos or browser" --random-order -v
echo ""
echo "2. Pass Rate (3 consecutive runs)"
for i in {1..3}; do
  echo "Run $i:"
  pytest backend/tests/ -m "fuzzing or chaos or browser" -q --tb=no
done
echo ""
echo "3. Performance (<30s per test)"
pytest backend/tests/ -m "fuzzing or chaos or browser" --durations=10
echo ""
echo "4. Determinism (3 runs, same results)"
pytest backend/tests/fuzzing/test_api_fuzzing.py::test_function -v --repeat=3
echo ""
echo "5. Coverage Quality"
pytest backend/tests/ --cov=backend --cov-branch --cov-report=term-missing
```

### Quick Quality Gate (Before Commit)

```bash
# Quick checks before committing
pytest backend/tests/ -m "fuzzing or chaos or browser" \
  --random-order \
  --durations=5 \
  -q
```

## Quality Gate Enforcement

### Pre-Merge Hook (Optional)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit quality gate for bug discovery tests

echo "Running quality gate for bug discovery tests..."

# Quick checks
pytest backend/tests/ -m "fuzzing or chaos or browser" \
  --random-order \
  --durations=5 \
  -q

# Exit on failure
if [ $? -ne 0 ]; then
  echo "Quality gate failed. Fix issues before committing."
  exit 1
fi

echo "Quality gate passed!"
```

### CI/CD Quality Gate

Add to `.github/workflows/pr-tests.yml`:

```yaml
- name: Enforce test quality standards
  run: |
    pytest backend/tests/ -m "fast or property" \
      --random-order \
      --durations=10 \
      --maxfail=5 \
      --tb=short
    if [ $? -ne 0 ]; then
      echo "Quality gate failed: Tests do not meet TQ standards"
      exit 1
    fi
```

## Waiver Process

If a bug discovery test legitimately cannot meet a quality standard:

1. **Document Rationale:** Add comment explaining why standard cannot be met
2. **Request Waiver:** Create issue requesting waiver with justification
3. **Team Review:** Team approves waiver with explicit expiration
4. **Track Waiver:** Add @pytest.mark.waiver(marker_name, issue="URL") with waiver issue URL

**Example Waiver:**
```python
@pytest.mark.fuzzing
@pytest.mark.waiver(
    "long-running-fuzz",
    issue="https://github.com/atom/atom/issues/123",
    expires="2026-04-30"
)
@pytest.mark.timeout(300)  # 5 minutes for comprehensive fuzzing
def test_comprehensive_fuzzing():
    """
    Comprehensive fuzzing test (waived from TQ-03 <30s requirement).

    Rationale: Fuzzing requires 1000+ iterations for coverage.
    Waiver expires: 2026-04-30
    Issue: https://github.com/atom/atom/issues/123
    """
    # Test implementation
    pass
```

## Quality Metrics

Track these metrics to ensure quality gate effectiveness:

| Metric | Target | Current | Trend |
|--------|--------|---------|-------|
| Test independence rate | 100% | _ | _ |
| Pass rate | >98% | _ | _ |
| Avg test duration | <10s | _ | _ |
| Flaky test rate | <2% | _ | _ |
| Coverage quality score | >80% | _ | _ |

## See Also

- `backend/docs/TEST_QUALITY_STANDARDS.md` - Full TQ-01 through TQ-05 requirements
- `backend/tests/bug_discovery/INFRASTRUCTURE_VERIFICATION.md` - Infrastructure verification
- `backend/tests/bug_discovery/TEMPLATES/` - Test templates with TQ compliance

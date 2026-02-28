# Quality Gates Documentation

## Overview

Quality gates prevent technical debt accumulation and ensure code quality standards are met before merging. All gates are automated in CI/CD and run on every pull request.

**Purpose**: Automated quality enforcement, consistent validation, immediate feedback on quality issues.

**Gate Types**:
- **Coverage Gate**: 80% line coverage, 70% branch coverage minimum
- **Pass Rate Gate**: 98% minimum test pass rate
- **Regression Gate**: No more than 5% coverage drop from baseline
- **Flaky Test Gate**: Warn if >5% flaky, fail if >10% flaky

---

## Gate Descriptions

### 1. Coverage Gate

**What it checks**:
- Line coverage: Percentage of code lines executed by tests (minimum 80%)
- Branch coverage: Percentage of if/else branches executed (minimum 70%)

**Why these thresholds exist**:
- 80% line coverage ensures critical paths are tested
- 70% branch coverage catches edge cases in conditional logic
- Higher thresholds catch more bugs but increase maintenance burden
- Industry research shows diminishing returns above 80%

**Failure consequences**:
- CI job fails, blocking PR merge
- Comment posted to PR with remediation steps
- Coverage report shows uncovered lines

**Metrics**:
- Reads from: `backend/tests/coverage_reports/metrics/coverage.json`
- Baseline: 74.55% (Phase 090-01)

---

### 2. Pass Rate Gate

**What it checks**:
- Percentage of tests that pass (minimum 98%)
- Total tests: 342 (as of Phase 090-02)

**Why 98% threshold exists**:
- Allows 2% tolerance for legitimate test failures
- Catches regressions early while allowing some flexibility
- High threshold ensures broken tests are fixed or removed promptly

**Failure consequences**:
- CI job fails, blocking PR merge
- Comment posted to PR with failing test count
- Developer must fix or remove failing tests

**Metrics**:
- Reads from: `backend/tests/coverage_reports/metrics/test_health.json`
- History: Tracks pass rate over time

---

### 3. Regression Gate

**What it checks**:
- Coverage hasn't dropped more than 5% from baseline
- Compares current coverage to Phase 090-01 baseline (74.55%)

**Why 5% threshold exists**:
- Allows small fluctuations (test refactoring, mocking changes)
- Catches significant coverage drops from new untested code
- Prevents gradual erosion of test coverage

**Failure consequences**:
- CI job fails, blocking PR merge
- Shows exact regression amount (e.g., "↓3.2% from baseline")
- Developer must add coverage for new functionality

**Metrics**:
- Reads from: `backend/tests/coverage_reports/metrics/trending.json`
- Baselines: v1.0 (5.13%), v3.2 (15.23%), 090-baseline (74.55%)

---

### 4. Flaky Test Gate

**What it checks**:
- Percentage of tests that fail intermittently (warn at 5%, fail at 10%)
- Tests marked as flaky in `test_health.json`

**Why thresholds exist**:
- Flaky tests undermine confidence in test suite
- 5% warning identifies early flaky test issues
- 10% failure forces investigation before merge

**Failure consequences**:
- **Warning (5-10%)**: Gate passes, but warning logged
- **Failure (>10%)**: CI job fails, blocking PR merge
- Comment posted to PR with flaky test count

**Metrics**:
- Reads from: `backend/tests/coverage_reports/metrics/test_health.json`
- Tracked: List of flaky test names

---

## Remediation Steps

### Coverage Below 80%

**Diagnose**:
```bash
cd backend
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing
```

**Fix**:
1. Review uncovered lines in the coverage report
2. Prioritize high-value modules (governance, LLM, episodic memory)
3. Add unit tests for uncovered code paths
4. Add integration tests for complex workflows
5. Re-run tests to verify improvement

**Common causes**:
- New code added without tests
- Edge cases not covered (error handling, empty inputs)
- Configuration or environment-specific code

**Example**:
```python
# Before: Coverage gap
def calculate_tax(amount, rate):
    if amount > 0:
        return amount * rate  # Missing: amount <= 0 case

# After: Test added
def test_calculate_tax_zero_amount():
    assert calculate_tax(0, 0.1) == 0
```

---

### Pass Rate Below 98%

**Diagnose**:
```bash
cd backend
pytest tests/ -v --tb=short
```

**Fix**:
1. Fix failing tests (check assertions, mocks, data setup)
2. Remove broken tests that cannot be fixed (comment why in PR)
3. Investigate flaky tests (timing issues, external dependencies)
4. Run tests multiple times to verify stability: `pytest --reruns 2`

**Common causes**:
- Broken assertions (expected values changed)
- Missing mocks (external services, databases)
- Flaky tests (race conditions, shared state)

**Example**:
```python
# Before: Failing test
def test_agent_governance():
    agent = create_agent()
    assert agent.maturity == "AUTONOMOUS"  # FAIL: Default is STUDENT

# After: Fixed assertion
def test_agent_governance():
    agent = create_agent()
    agent.promote("AUTONOMOUS")
    assert agent.maturity == "AUTONOMOUS"  # PASS
```

---

### Coverage Regression Detected

**Diagnose**:
```bash
cd backend
python tests/scripts/generate_coverage_trend.py
cat tests/coverage_reports/metrics/trending.json
```

**Fix**:
1. Review new code for test gaps
2. Add coverage for changed functionality
3. Ensure no test files were accidentally removed
4. Check if coverage exclusion patterns changed (`.coveragerc`)

**Common causes**:
- New feature added without tests
- Test file deleted or moved
- Coverage exclusion pattern changed
- Refactoring removed test coverage

**Example**:
```bash
# Check what changed
git diff main --stat

# Add tests for new code
cat > tests/test_new_feature.py << EOF
def test_new_feature_coverage():
    # Test all branches of new code
    assert new_feature() == expected
EOF
```

---

### Flaky Tests Detected

**Diagnose**:
```bash
cd backend
cat tests/coverage_reports/metrics/test_health.json | grep flaky_tests
```

**Fix**:
1. Identify flaky tests from `test_health.json`
2. Fix timing issues (add proper async coordination)
3. Add mocks for external dependencies (network, databases)
4. Use `unique_resource_name` fixture for parallel test isolation
5. Remove non-determinism (random data, timestamps)

**Common causes**:
- Race conditions in parallel execution
- Improper async/await handling
- External service dependencies (network, databases)
- Time-based assertions without proper mocking
- Shared state between tests
- Non-deterministic test data

**Example**:
```python
# Before: Flaky test (timing issue)
def test_async_operation():
    result = async_operation()
    assert result is not None  # FAIL: Race condition

# After: Fixed with proper await
async def test_async_operation():
    result = await async_operation()
    assert result is not None  # PASS
```

---

## Local Validation

### Run All Gates Locally

Before pushing, run all quality gates locally:

```bash
cd backend

# Run tests with coverage
pytest tests/ -v \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json \
  --cov-report=html \
  --json-report --json-report-file=pytest_report.json

# Update health metrics
python tests/scripts/check_pass_rate.py \
  --json-file pytest_report.json \
  --update-health \
  --phase 090 --plan 05

# Run all gates
python3 tests/scripts/ci_quality_gate.py
```

### Run Individual Gates

**Coverage gate only**:
```bash
python3 tests/scripts/ci_quality_gate.py --coverage-min 80 --branch-min 70
```

**Pass rate gate only**:
```bash
python3 tests/scripts/check_pass_rate.py --json-file pytest_report.json --minimum 98
```

**Strict mode (higher thresholds)**:
```bash
python3 tests/scripts/ci_quality_gate.py --strict
```

### Pre-Commit Hook (Optional)

Install pre-commit hook to run gates automatically:

```bash
cd backend
./tests/scripts/install_hooks.sh
```

This runs coverage enforcement on staged files before commit (from Plan 090-01).

---

## CI Integration

### Workflows Enforcing Gates

1. **`.github/workflows/ci.yml`**:
   - `quality-gates` job runs after `backend-test-full`
   - Downloads coverage artifacts
   - Runs `ci_quality_gate.py` with all gates
   - Posts PR comment on failure

2. **`.github/workflows/test-coverage.yml`**:
   - Runs on every push to main/develop
   - Enforces coverage gates with detailed PR comments
   - Uploads coverage metrics as artifacts

### How Gates Appear in CI Logs

```
================================================================================
QUALITY GATES ENFORCEMENT
================================================================================

COVERAGE GATE: ✓
  PASS - Line: 81.2% (>= 80%), Branch: 72.5% (>= 70%)

PASS RATE GATE: ✓
  PASS - 99.1% (>= 98%), 339/342 tests passed

REGRESSION GATE: ✓
  PASS - 81.2% (↑+6.7% from baseline 74.55%)

FLAKY TEST GATE: ✓
  PASS - 0/342 tests flaky (0.0% < 5%)

================================================================================
OVERALL: PASS ✓
================================================================================
```

### PR Comment Format (on Failure)

```markdown
## ❌ Quality Gates Failed

One or more quality gates failed. Please review the details below and take corrective action.

### Failed Gates
- COVERAGE GATE: Line coverage 74.5% < 80%

### Remediation Steps
1. **Coverage below 80%**: Run tests locally with `pytest --cov=core --cov=api --cov=tools --cov-report=term-missing`
2. **Pass rate below 98%**: Fix failing tests, remove broken tests
3. **Coverage regression**: Review new code for test gaps
4. **Flaky tests**: Fix timing issues, add proper mocks

See CODEOWNERS_QUALITY.md for detailed remediation steps.
```

---

## Troubleshooting

### Common Failure Causes

**1. Coverage below 80%**

**Cause**: New code added without tests

**Quick Fix**:
```bash
# Identify uncovered modules
pytest --cov=core --cov=api --cov=tools --cov-report=term-missing | grep "MISS"

# Add tests for top uncovered files
```

**2. Pass rate below 98%**

**Cause**: Test failure due to environment or data changes

**Quick Fix**:
```bash
# Run failing test in isolation
pytest tests/test_module.py::test_function -v

# Update expected values or add proper mocks
```

**3. Coverage regression**

**Cause**: Test file deleted or coverage exclusion changed

**Quick Fix**:
```bash
# Check for deleted test files
git diff main --name-only | grep test

# Restore or rewrite deleted tests
```

**4. Flaky tests**

**Cause**: Race condition or external dependency

**Quick Fix**:
```bash
# Identify flaky test
pytest tests/test_module.py::test_function --reruns 5

# Add proper mocks or fix timing
```

### When to Ask for Help

- Gate failure persists after remediation steps
- Unclear which code needs coverage
- Test failures are intermittent and difficult to reproduce
- Coverage regression but no obvious missing tests

**Where to ask**:
- Open GitHub issue with CI logs attached
- Tag `@rushiparikh` for review
- Include: gate type, error message, reproduction steps

### False Positives

**If gate fails incorrectly**:

1. **Coverage gate false positive**:
   - Check coverage exclusion patterns in `pytest.ini`
   - Ensure generated code is excluded (e.g., protobuf, migrations)

2. **Pass rate false positive**:
   - Check if test was marked as `xfail` or skipped
   - Verify test environment (database, Redis) is running

3. **Regression false positive**:
   - Check if baseline changed (should be 74.55% for 090-baseline)
   - Verify trending.json hasn't been corrupted

4. **Flaky test false positive**:
   - Ensure test isn't genuinely flaky (run 10 times)
   - Check for external dependencies (network, databases)

**To override gate (not recommended)**:
- Edit thresholds in `.github/workflows/ci.yml` (temporary)
- File issue explaining why gate is incorrect
- Update CODEOWNERS_QUALITY.md with exception rationale

---

## Continuous Improvement

### Monitoring Gate Health

Track these metrics over time:

- **Coverage trend**: Should increase gradually
- **Pass rate**: Should stay at 98-100%
- **Flaky test count**: Should decrease to 0%
- **Gate failures**: Should be rare (<5% of PRs)

### Updating Thresholds

Before changing thresholds:

1. Justify with data (e.g., "Coverage at 85%, propose raising to 82%")
2. Document decision in STATE.md
3. Update all CI workflows consistently
4. Update this documentation

### Related Documentation

- `TESTING.md`: Test writing guidelines
- `pytest.ini`: Test configuration
- `.github/workflows/ci.yml`: CI pipeline definition
- `.github/workflows/test-coverage.yml`: Coverage workflow
- `backend/tests/scripts/ci_quality_gate.py`: Gate enforcement script

---

**Last Updated**: Phase 090-05 (2026-02-25)
**Maintained By**: @rushiparikh
**Status**: Active - All gates enforced in CI

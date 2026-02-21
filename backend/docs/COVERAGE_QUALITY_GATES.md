# Coverage Quality Gates Documentation

**Purpose:** Document test quality standards (TQ-01 through TQ-05) and coverage enforcement mechanisms for the Atom backend.

**Last Updated:** 2026-02-21

---

## Table of Contents

1. [Overview](#overview)
2. [Quality Standards TQ-01 through TQ-05](#quality-standards-tq-01-through-tq-05)
3. [CI/CD Coverage Enforcement](#cicd-coverage-enforcement)
4. [Pre-Commit Hooks](#pre-commit-hooks)
5. [Coverage Reports](#coverage-reports)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Overview

Atom backend enforces code quality through multiple layers:

1. **CI/CD Pipeline:** GitHub Actions workflow enforces 55% coverage threshold
2. **Pre-Commit Hooks:** Local development checks before commits
3. **Quality Gates:** TQ-01 through TQ-05 test quality standards
4. **Coverage Reports:** HTML, XML, and terminal reports for analysis

**Current Coverage Target:** 55% (enforced in CI/CD)
**Planned Coverage Target:** 80% (Phase 62 goal)

---

## Quality Standards TQ-01 through TQ-05

### TQ-01: Test Independence

**Definition:** Tests can run in any order without shared state dependencies.

**Rationale:** Shared state between tests causes flaky failures and makes debugging difficult. Independent tests are reliable and maintainable.

**Implementation:**
- Use `pytest-xdist` for parallel test execution
- Each test should create and destroy its own data
- No global mutable state in test modules
- Use fixtures for setup/teardown

**Validation:**
```bash
# Run tests in random order
pytest --random-order -v

# Run tests in parallel
pytest -n auto -v
```

**Success Criteria:** Tests pass consistently regardless of execution order.

---

### TQ-02: Pass Rate

**Definition:** 98%+ pass rate across 3 consecutive runs.

**Rationale:** Flaky tests erode trust in the test suite. A 98% pass rate ensures stability while accounting for occasional environmental issues.

**Implementation:**
- Deterministic test data (no random values without seeded RNG)
- Proper async cleanup (no lingering tasks)
- Wait for async operations with timeouts
- Stable environment configuration

**Validation:**
```bash
# Run tests 3 times and verify pass rate
for i in {1..3}; do
  pytest -q --tb=no
done
```

**Success Criteria:** ≥98% of tests pass across all 3 runs.

**Current Status:** Quality gate tests validated for stability (see `tests/test_quality_gates.py`).

---

### TQ-03: Performance

**Definition:** Full test suite completes in <60 minutes.

**Rationale:** Slow test suites reduce development velocity and discourage running tests frequently. Fast tests enable continuous feedback.

**Implementation:**
- Use mocks for external services (LLM providers, databases)
- Avoid unnecessary sleeps (use polling loops)
- Parallel test execution with `pytest-xdist`
- Efficient test data setup (factories over fixtures)

**Benchmarks:**

| Test Category | Target | Current |
|--------------|--------|---------|
| Unit tests | <5 min | ✅ Pass |
| Integration tests | <15 min | ✅ Pass |
| E2E tests | <30 min | ✅ Pass |
| Full suite | <60 min | ✅ Pass |

**Validation:**
```bash
# Time the full suite
time pytest -q --tb=no
```

**Success Criteria:** Full suite completes in <3600 seconds (60 minutes).

---

### TQ-04: Determinism

**Definition:** Same test results across 3 consecutive runs.

**Rationale:** Non-deterministic tests indicate timing issues, race conditions, or environment dependencies. Deterministic tests are predictable and debuggable.

**Implementation:**
- No hardcoded sleeps (use polling loops)
- Stable identifiers (UUID v4, not auto-increment)
- Isolated test databases
- Consistent environment variables
- Deterministic mock responses

**Validation:**
```bash
# Run tests 3 times and compare output
pytest -q --tb=no > run1.txt
pytest -q --tb=no > run2.txt
pytest -q --tb=no > run3.txt
diff run1.txt run2.txt
diff run2.txt run3.txt
```

**Success Criteria:** All 3 runs produce identical output (same test counts, same results).

**Current Status:** Quality gate tests validated for determinism (see `tests/test_quality_gates.py`).

---

### TQ-05: Coverage Quality

**Definition:** Branch coverage enabled with behavior-based tests.

**Rationale:** Line coverage alone is insufficient. Branch coverage ensures all code paths are tested, including conditional logic. Behavior-based tests verify actual functionality, not implementation details.

**Implementation:**
- Enable `--cov-branch` flag in pytest
- Test both branches of conditionals
- Test error paths and edge cases
- Use property-based testing (Hypothesis) for stateful logic
- Focus on behavior over implementation

**Validation:**
```bash
# Run coverage with branch reporting
pytest --cov=core --cov=api --cov=tools --cov=integrations \
  --cov-branch \
  --cov-report=html \
  --cov-report=term-missing
```

**Success Criteria:**
- Branch coverage enabled (not just line coverage)
- Coverage report includes "Branch" column
- Behavior-based tests for critical paths

**Current Status:** ✅ Branch coverage enabled in CI/CD and pre-commit hooks.

---

## CI/CD Coverage Enforcement

### GitHub Actions Workflow

**File:** `.github/workflows/test.yml`

**Trigger Conditions:**
- Push to `main` branch
- Pull requests to `main` branch

**Coverage Enforcement:**
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=core --cov=api --cov=tools --cov=integrations \
      --cov-branch \
      --cov-report=xml \
      --cov-report=html \
      --cov-report=term-missing \
      --cov-fail-under=55 \
      -v
```

**Key Settings:**
- `--cov-fail-under=55`: Fail if coverage drops below 55%
- `--cov-branch`: Enable branch coverage (not just line coverage)
- `--cov-report=xml`: Generate XML report for PR comments
- `--cov-report=html`: Generate HTML report for detailed analysis
- `--cov-report=term-missing`: Show missing lines in terminal output

**Artifacts:**
- `coverage.xml`: Machine-readable coverage data
- `htmlcov/`: Interactive HTML coverage report

**PR Comments:**
Coverage is automatically posted as a comment on pull requests using `romeovs/lcov-reporter-action`.

### Updating Coverage Threshold

To increase the coverage threshold:

1. Update `.github/workflows/test.yml`:
   ```yaml
   --cov-fail-under=60  # Increase from 55% to 60%
   ```

2. Update `.pre-commit-config.yaml`:
   ```yaml
   entry: pytest --cov=core --cov=api --cov=tools --cov-fail-under=60 -q
   ```

3. Commit and push changes:
   ```bash
   git add .github/workflows/test.yml .pre-commit-config.yaml
   git commit -m "feat: increase coverage threshold to 60%"
   git push
   ```

---

## Pre-Commit Hooks

### Installation

```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks in your repository
cd backend
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

### Configuration

**File:** `.pre-commit-config.yaml`

**Hooks:**

| Hook | Purpose | Fixable |
|------|---------|---------|
| check-ast | Syntax errors | No |
| check-docstring-first | Docstring placement | Yes |
| check-merge-conflict | Merge conflict markers | No |
| trailing-whitespace | Trailing whitespace | Yes |
| end-of-file-fixer | Newline at EOF | Yes |
| black | Code formatting | Yes |
| flake8 | Linting | Partial |
| isort | Import sorting | Yes |
| mypy | Type checking | No |
| bandit | Security checks | No |
| pytest-with-coverage | Coverage validation | No |

### Coverage Hook

```yaml
- repo: local
  hooks:
    - id: pytest-with-coverage
      name: Run pytest with coverage check (55% minimum)
      entry: pytest --cov=core --cov=api --cov=tools --cov-fail-under=55 -q
      language: system
      pass_filenames: false
      always_run: true
```

**Behavior:**
- Runs on every commit attempt
- Fails the commit if coverage <55%
- Always runs (even if no Python files changed)
- Reports missing lines in terminal output

### Skipping Hooks

To skip hooks for a specific commit (not recommended):

```bash
git commit --no-verify -m "WIP: work in progress"
```

---

## Coverage Reports

### Terminal Report

```bash
pytest --cov=core --cov=api --cov-branch --cov-report=term-missing
```

**Output:**
```
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
core/agent_governance_service.py     50      5    90%   23-27
api/agent_routes.py                  40     10    75%   45-50
---------------------------------------------------------------
TOTAL                               500     200    60%
```

### HTML Report

```bash
pytest --cov=core --cov=api --cov-branch --cov-report=html
open htmlcov/index.html
```

**Features:**
- Interactive drill-down into files
- Line-by-line coverage highlighting
- Branch coverage visualization
- Missing coverage highlighted in red

### XML Report

```bash
pytest --cov=core --cov=api --cov-branch --cov-report=xml
```

**Usage:**
- CI/CD integration (GitHub Actions, GitLab CI)
- Coverage trending tools (Codecov, Coveralls)
- PR comments (via `romeovs/lcov-reporter-action`)

### JSON Report

```bash
pytest --cov=core --cov=api --cov-branch --cov-report=json
```

**Usage:**
- Programmatic analysis
- Coverage metrics extraction
- Custom reporting tools

---

## Troubleshooting

### Issue: Coverage Not Calculated

**Symptoms:** Coverage report shows 0% or "No data to report".

**Solutions:**
1. Verify pytest-cov is installed:
   ```bash
   pip install pytest-cov
   ```

2. Check that `--cov` argument specifies correct modules:
   ```bash
   pytest --cov=core --cov=api
   ```

3. Ensure tests import the modules under test:
   ```python
   from core.agent_governance_service import AgentGovernanceService
   ```

### Issue: Branch Coverage Not Showing

**Symptoms:** Coverage report shows "Stmt" but not "Branch".

**Solutions:**
1. Add `--cov-branch` flag:
   ```bash
   pytest --cov=core --cov-branch
   ```

2. Verify coverage.py version ≥5.0:
   ```bash
   pip show pytest-cov
   ```

3. Check `.coveragerc` configuration:
   ```ini
   [run]
   branch = True
   ```

### Issue: CI/CD Fails with "Coverage Below Threshold"

**Symptoms:** GitHub Actions workflow fails with `CoverageFailureException`.

**Solutions:**
1. Check actual coverage in workflow logs
2. Review `htmlcov/` report artifact to identify gaps
3. Add tests for missing lines/branches
4. If threshold is too aggressive, incrementally increase (55% → 57% → 60%)

### Issue: Pre-Commit Hook Fails

**Symptoms:** `git commit` fails with coverage error.

**Solutions:**
1. Run tests manually to see details:
   ```bash
   pytest --cov=core --cov=api --cov-report=term-missing
   ```

2. Fix failing tests or add missing coverage
3. Skip hook for temporary workaround (not recommended):
   ```bash
   git commit --no-verify
   ```

### Issue: Quality Gate Tests Hang

**Symptoms:** `pytest tests/test_quality_gates.py` never completes.

**Solutions:**
1. Check for infinite recursion in subprocess calls
2. Add timeout to subprocess.run():
   ```python
   subprocess.run(["pytest", ...], timeout=30)
   ```
3. Verify no circular test dependencies

---

## Best Practices

### Writing High-Coverage Tests

1. **Test Both Success and Failure Paths:**
   ```python
   def test_agent_creation():
       # Success path
       agent = create_agent("test-agent")
       assert agent.id == "test-agent"

       # Failure path
       with pytest.raises(ValidationError):
           create_agent("")  # Invalid name
   ```

2. **Test All Branches:**
   ```python
   def test_agent_governance():
       # Branch 1: Student agent
       result = govern_agent("test-agent", "STUDENT")
       assert result.allowed == False

       # Branch 2: Autonomous agent
       result = govern_agent("test-agent", "AUTONOMOUS")
       assert result.allowed == True
   ```

3. **Use Property-Based Testing:**
   ```python
   from hypothesis import given, strategies as st

   @given(st.text(min_size=1))
   def test_agent_name_validation(name):
       agent = create_agent(name)
       assert agent.name == name
   ```

### Increasing Coverage Efficiently

1. **Focus on High-Impact Files:**
   - Large files with low coverage (impact score = lines × (1 - coverage))
   - Critical business logic
   - Security-sensitive code

2. **Add Missing Tests Before Refactoring:**
   - Ensure existing behavior is tested
   - Refactor with confidence
   - Maintain coverage during changes

3. **Use Coverage-Guided Development:**
   - Write test → Run coverage → Identify gaps → Add more tests
   - Iterate until coverage target met

4. **Prioritize Behavior Over Implementation:**
   - Test what the code does, not how it does it
   - Avoid testing private methods directly
   - Focus on public APIs and user-facing behavior

### Maintaining Coverage Quality

1. **Review Coverage Reports Regularly:**
   - Check HTML report after major changes
   - Identify coverage regression trends
   - Address coverage gaps early

2. **Set Incremental Targets:**
   - 55% → 60% → 65% → 70% → 75% → 80%
   - Celebrate milestones
   - Adjust thresholds as coverage improves

3. **Balance Coverage with Test Quality:**
   - Don't write tests just to hit coverage targets
   - Focus on meaningful assertions
   - Use property-based testing for stateful logic

4. **Document Coverage Decisions:**
   - Note why certain code is excluded from coverage
   - Use `.coveragerc` for legitimate exclusions (e.g., `pragma: no cover`)
   - Review exclusions periodically

---

## Appendix: Configuration Files

### .coveragerc

```ini
[run]
source = core, api, tools, integrations
branch = True
omit =
    */tests/*
    */test_*.py
    */__init__.py
    */migrations/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstract
```

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=core
    --cov=api
    --cov=tools
    --cov=integrations
    --cov-branch
    --cov-report=term-missing
    --cov-report=html
    --strict-markers
    --tb=short
markers =
    quality: Quality gate tests (TQ-01 through TQ-05)
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, external deps)
    e2e: End-to-end tests (slowest, full stack)
```

---

**Questions?** See `tests/test_quality_gates.py` for working examples of quality gate validation.

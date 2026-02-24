# Phase 74: Quality Gates & Property Testing - Research

**Researched:** 2026-02-22
**Domain:** CI/CD Quality Gates, Property-Based Testing, Coverage Enforcement
**Confidence:** HIGH

## Summary

Phase 74 focuses on enforcing 80% coverage thresholds in CI/CD and implementing property-based tests for critical system invariants using Hypothesis. This phase builds upon Atom's existing testing infrastructure (96.9% coverage, 168 property test files, pytest-xdist parallel execution) to add production-quality enforcement mechanisms.

**Key Findings:**
- **80% is the industry-standard threshold** for CI/CD coverage gates, widely adopted by enterprises and financial institutions
- **Hypothesis framework with strategic max_examples (50-200)** balances test thoroughness with execution time
- **pytest-cov with --cov-fail-under=80** provides the enforcement mechanism
- **Pre-commit hooks** can enforce local standards before commits reach CI
- **Property-based tests** should focus on critical invariants: governance, LLM routing, database transactions, API contracts
- **VALIDATED_BUG docstrings** document bug-finding evidence from property tests

**Primary Recommendation:** Implement 80% coverage gates using pytest-cov in CI/CD, enhance pre-commit hooks from 55% to 80%, and create property-based tests for the four critical invariant categories using Hypothesis with max_examples=50-200.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest-cov** | >=4.1.0,<5.0.0 | Coverage reporting and threshold enforcement | Industry standard for pytest coverage, supports --cov-fail-under flag for blocking gates |
| **Hypothesis** | >=6.92.0,<7.0.0 | Property-based testing framework | De facto standard for PBT in Python, integrates seamlessly with pytest |
| **pytest-xdist** | >=3.6.0,<4.0.0 | Parallel test execution | Already configured (7.2x speedup achieved), essential for keeping CI times manageable |
| **coverage.py** | (included with pytest-cov) | Coverage measurement engine | Underlying engine for pytest-cov, supports branch coverage and HTML reports |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pre-commit** | (existing) | Local git hooks enforcement | For GATES-04: enforce local testing before commits |
| **pytest-json-report** | (existing) | JSON test output parsing | For coverage trend tracking in CI/CD |
| **pytest-random-order** | (existing) | Test independence validation (TQ-01) | For verifying tests don't depend on execution order |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-cov | coverage.py (standalone) | pytest-cov integrates better with pytest test discovery, provides --cov-fail-under flag |
| Hypothesis | QuickCheck (hypothesis-python predecessor) | Hypothesis is actively maintained, has better Python integration |
| 80% threshold | 90% or 95% | 80% is industry standard; higher thresholds risk false negatives and slower development |
| Single threshold | Tiered thresholds (critical vs utility modules) | Tiered is more flexible but adds complexity; start with single threshold, evolve to tiered |

**Installation:**
```bash
# All dependencies already installed in Atom backend
pip install -r requirements.txt        # pytest-cov, hypothesis
pip install -r requirements-testing.txt  # pytest-xdist, pytest-json-report, pytest-random-order

# For pre-commit hooks (Phase 74 requirement)
pip install pre-commit
pre-commit install
```

## Architecture Patterns

### Recommended CI/CD Pipeline Structure

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions Workflow (.github/workflows/quality-gates.yml) │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Job 1: Pre-commit Checks (fast feedback)            │   │
│  │ - Run pre-commit hooks locally before push          │   │
│  │ - Enforce: formatting, linting, type checking       │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Job 2: Test Suite (parallel execution)              │   │
│  │ - pytest -n auto (xdist)                            │   │
│  │ - All unit + integration tests                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Job 3: Coverage Gate (GATES-01, GATES-05)           │   │
│  │ - pytest --cov --cov-fail-under=80                  │   │
│  │ - Block deployment if coverage < 80%                │   │
│  │ - Generate HTML + JSON reports                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Job 4: Property Tests (PROP-01 through PROP-05)     │   │
│  │ - Run in separate job (timeout protection)          │   │
│  │ - Critical invariants only                          │   │
│  │ - max_examples=50-200 per test                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Job 5: Quality Gate Summary                         │   │
│  │ - All gates must pass for merge                     │   │
│  │ - Report: coverage %, test count, property tests    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Pattern 1: Coverage Gate Enforcement (GATES-01, GATES-05)

**What:** CI pipeline blocks deployment if coverage drops below 80%

**When to use:** All merge requests to main/develop branches

**Example:**
```yaml
# Source: .github/workflows/quality-gates.yml
- name: Coverage Gate (GATES-01, GATES-05)
  working-directory: ./backend
  run: |
    pytest tests/ \
      --cov=core \
      --cov=api \
      --cov=tools \
      --cov-branch \
      --cov-report=html:tests/coverage_reports/html \
      --cov-report=json:tests/coverage_reports/metrics/coverage.json \
      --cov-report=term-missing:skip-covered \
      --cov-fail-under=80  # 🔴 BLOCKS deployment if < 80%
```

**Why this pattern:**
- `--cov-fail-under=80` makes the gate **blocking** (not advisory)
- `--cov-branch` enables branch coverage (stricter than line coverage)
- HTML reports enable developer investigation of coverage gaps
- JSON reports enable trend tracking and dashboards

### Pattern 2: Pre-Commit Coverage Hook (GATES-04)

**What:** Local development check before commits

**When to use:** All local commits (runs on `git commit`)

**Example:**
```yaml
# Source: .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-with-coverage
        name: Run pytest with coverage check (80% minimum)
        entry: pytest tests/ --cov=core --cov=api --cov=tools --cov-fail-under=80 -q
        language: system
        pass_filenames: false
        always_run: true
```

**Why this pattern:**
- **Shift-left quality**: Catch coverage issues before pushing to remote
- **Faster feedback**: No need to wait for CI queue
- **Developer-friendly**: Can be bypassed with `git commit --no-verify` if needed

### Pattern 3: Property-Based Test Structure (PROP-01 through PROP-05)

**What:** Hypothesis tests for critical system invariants

**When to use:** Testing properties that must hold for ALL inputs, not just examples

**Example:**
```python
# Source: tests/property_tests/governance/test_governance_invariants.py

from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import floats, lists

# Common settings for property tests
HYPOTHESIS_SETTINGS = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200  # 50-200 based on test complexity
}

class TestConfidenceScoreInvariants:
    @given(
        initial_confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False),
        boost_amount=floats(min_value=-0.5, max_value=0.5, allow_nan=False)
    )
    @example(initial_confidence=0.3, boost_amount=0.8)  # Edge case: would exceed 1.0
    @settings(**HYPOTHESIS_SETTINGS)
    def test_confidence_bounds_invariant(
        self, db_session, initial_confidence: float, boost_amount: float
    ):
        """
        INVARIANT: Confidence scores MUST stay within [0.0, 1.0] bounds.

        VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts.
        Root cause: Missing min(1.0, ...) clamp in confidence update logic.
        Fixed in commit abc123 by adding bounds checking.

        Scenario: Agent at 0.8 receives +0.3 boost -> should clamp to 1.0, not 1.1
        """
        # Create agent with initial confidence
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            confidence_score=initial_confidence
        )
        db_session.add(agent)
        db_session.commit()

        # Simulate confidence update (clamped to [0.0, 1.0])
        new_confidence = max(0.0, min(1.0, initial_confidence + boost_amount))
        agent.confidence_score = new_confidence
        db_session.commit()

        # Assert: Confidence must be in valid range
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence {agent.confidence_score} outside [0.0, 1.0] bounds"
```

**Why this pattern:**
- `@given` decorator generates hundreds of random test cases
- `@example` adds specific edge cases (boundary conditions)
- `max_examples=200` balances thoroughness with execution time
- `VALIDATED_BUG` docstrings document real bugs found by property tests
- `suppress_health_check` needed for pytest fixtures that support multiple test cases

### Anti-Patterns to Avoid

- **Advisory-only gates**: Setting coverage thresholds but not blocking deployment. Use `--cov-fail-under` instead of just checking coverage in CI output.
- **Property tests for simple functions**: Using Hypothesis for trivial getters/setters. Reserve PBT for complex invariants (governance, database transactions, API contracts).
- **max_examples=1000 in CI**: Too many examples makes CI too slow. Use 50-200 for property tests, reserve 1000+ for local development or nightly builds.
- **Coverage exclusions abuse**: Overusing `# pragma: no cover` to artificially inflate coverage. Only exclude truly untestable code (e.g., OS-specific modules).
- **No VALIDATED_BUG documentation**: Property tests finding bugs but not documenting the evidence. Always add docstrings explaining what bug was found and how it was fixed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom Python script parsing AST | coverage.py (via pytest-cov) | Handles branches, partial lines, exclusion patterns, concurrency |
| Property testing framework | Custom random input generators | Hypothesis | Shrinking (minimizes failing examples), strategy combinators, pytest integration |
| Coverage trend tracking | Custom GitHub Action parsing JSON | Codecov or CodeClimate | Professional dashboards, PR comments, trend analysis |
| Pre-commit framework | Custom git hooks script | pre-commit framework | Cross-platform, dependency caching, hook management |

**Key insight:** Building coverage measurement or property testing from scratch requires handling edge cases (concurrent file access, partial line coverage, test case minimization) that established libraries have solved over decades of development.

## Common Pitfalls

### Pitfall 1: CI False Negatives from Stochastic Tests

**What goes wrong:** Property tests or flaky tests fail intermittently in CI, blocking merges for non-code-related reasons (random seed issues, timing issues).

**Why it happens:** Hypothesis generates random inputs; without proper settings, tests can timeout or produce non-deterministic failures.

**How to avoid:**
- Use `@settings(max_examples=50-200, deadline=None)` for property tests
- Set `suppress_health_check=[HealthCheck.too_slow]` for slower operations
- Use `@pytest.mark.flaky` as temporary workaround (fix root cause later)
- Fix underlying issues: proper async coordination, mocks vs real services

**Warning signs:** CI failures that pass on re-run with no code changes.

### Pitfall 2: Coverage Regression Without Blocking Gates

**What goes wrong:** Coverage drops from 85% to 78% in a PR, but merge is allowed because gate only warns (doesn't block).

**Why it happens:** Using coverage reporting (`--cov-report`) without enforcement (`--cov-fail-under`).

**How to avoid:**
- Always use `--cov-fail-under=80` for blocking behavior
- Set threshold slightly above current coverage (e.g., if at 85%, set gate to 83%) to prevent regression
- Monitor coverage trends and incrementally raise threshold toward 80%

**Warning signs:** Merge requests that decrease overall coverage metric.

### Pitfall 3: Property Tests Running Too Long in CI

**What goes wrong:** Property tests with `max_examples=1000` cause CI job to timeout (>30 minutes).

**Why it happens:** Hypothesis default is 100 examples; developers increase to 1000 for thoroughness without considering CI time impact.

**How to avoid:**
- Use `max_examples=50-200` for CI (balances thoroughness vs speed)
- Reserve `max_examples=1000+` for local development or nightly builds
- Use `@settings(deadline=None)` for legitimate slow operations
- Run property tests in separate job with longer timeout

**Warning signs:** CI jobs exceeding 20-30 minutes due to test execution.

### Pitfall 4: Pre-Commit Hooks Blocking All Commits

**What goes wrong:** Developers disable pre-commit hooks because they're too slow (running full test suite on every commit).

**Why it happens:** Hook configured to run entire test suite with 80% coverage check on every commit.

**How to avoid:**
- Pre-commit hooks: Fast checks only (linting, formatting, type checking)
- CI/CD pipeline: Full test suite with coverage gate
- Developers can run full suite manually before push
- Allow bypass with `git commit --no-verify` for emergency fixes

**Warning signs:** Developers commenting out pre-commit hooks in `.git/config`.

### Pitfall 5: Property Tests Without Invariants

**What goes wrong:** Property tests validate implementation details rather than invariants, making tests brittle and requiring updates when implementation changes.

**Why it happens:** Confusing "property" (implementation behavior) with "invariant" (always-true property).

**How to avoid:**
- Test invariants: "confidence scores always stay in [0.0, 1.0]"
- Test invariants: "database transactions are atomic (all-or-nothing)"
- Test invariants: "LLM provider fallback always returns valid provider"
- Avoid: "confidence update function uses specific algorithm"

**Warning signs:** Property tests failing when refactoring non-buggy code.

## Code Examples

Verified patterns from official sources:

### Coverage Gate Enforcement

```python
# Source: pytest-cov documentation (https://pytest-cov.readthedocs.io/)
# Command-line usage
pytest --cov=src --cov-fail-under=80

# With branch coverage and multiple reports
pytest --cov=core --cov=api --cov=tools \
  --cov-branch \
  --cov-report=html:htmlcov \
  --cov-report=json:coverage.json \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=80
```

### Hypothesis Property Test with Settings

```python
# Source: Hypothesis documentation (https://hypothesis.readthedocs.io/)
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import integers

# Settings for CI (faster)
@settings(max_examples=50, deadline=None)
@given(x=integers(), y=integers())
def test_commutative_property(x, y):
    assert x + y == y + x

# Settings for local development (thorough)
@settings(max_examples=1000)
@given(x=integers(), y=integers())
def test_commutative_property_thorough(x, y):
    assert x + y == y + x

# Settings for database tests (slow fixtures)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(amount=integers(min_value=0, max_value=1000000))
def test_account_balance_invariant(db_session, amount):
    # Test invariant: balance never negative
    assert account.balance >= 0
```

### Pre-Commit Coverage Hook

```yaml
# Source: pre-commit documentation (https://pre-commit.com/)
repos:
  - repo: local
    hooks:
      - id: coverage-check
        name: Coverage Check (80% minimum)
        entry: pytest tests/ --cov=core --cov=api --cov=tools --cov-fail-under=80 -q
        language: system
        pass_filenames: false
        always_run: true
```

### VALIDATED_BUG Docstring Pattern

```python
# Source: Atom property test standards (tests/property_tests/)
def test_confidence_bounds_invariant(self, initial_confidence, boost_amount):
    """
    INVARIANT: Confidence scores MUST stay within [0.0, 1.0] bounds.

    VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts.
    Root cause: Missing min(1.0, ...) clamp in confidence update logic.
    Fixed in commit abc123 by adding bounds checking.

    Scenario: Agent at 0.8 receives +0.3 boost -> should clamp to 1.0, not 1.1
    """
    # Test implementation...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Advisory coverage warnings | Blocking coverage gates (--cov-fail-under) | 2019-2020 (pytest-cov 2.0+) | Coverage gates now enforce standards, not just report them |
| Example-based testing only | Property-based testing (Hypothesis) | 2015-2020 (Hypothesis 1.0-6.0) | PBT finds edge cases human testers miss |
| Sequential test execution | Parallel execution (pytest-xdist) | 2020-2023 (pytest-xdist 3.0+) | 7.2x speedup achieved in Atom |
| Single coverage threshold | Tiered thresholds (critical vs utility modules) | 2021-2024 (enterprise adoption) | Financial institutions use 95%+ for payment logic, 70% for utilities |

**Deprecated/outdated:**
- **coverage.py standalone (without pytest-cov)**: Still works but pytest-cov integration is superior for test discovery
- **Hypothesis @given without @settings**: Default max_examples=100 is too low for CI; always specify settings
- **Pre-commit hooks running full test suite**: Too slow; use hooks for fast checks only (linting, formatting)
- **Coverage without --cov-branch**: Line coverage is insufficient; branch coverage catches more bugs

## Open Questions

1. **Incremental vs. Overall Coverage Gates**
   - What we know: 80% overall coverage is the Phase 74 requirement
   - What's unclear: Whether to enforce incremental coverage (new code only) or overall coverage
   - Recommendation: Start with **overall coverage gate** (simpler). Consider incremental gates if legacy code blocks progress. Incremental gates require tooling support (Codecov, SonarQube) and add complexity.

2. **Tiered Coverage Thresholds**
   - What we know: Phase 74 specifies 80% threshold across all modules
   - What's unclear: Whether different modules should have different thresholds (e.g., 95% for financial, 70% for utilities)
   - Recommendation: Start with **single 80% threshold** (simpler implementation). Evolve to tiered thresholds in future phase if business needs justify complexity.

3. **Property Test Execution Time**
   - What we know: Hypothesis tests with max_examples=200 can be slow
   - What's unclear: Whether to run property tests in every CI run or only nightly/weekly
   - Recommendation: Run **all property tests in every CI** but with `max_examples=50-200` (not 1000+). Separate job with timeout protection (10 minutes). If timeout exceeded, investigate and optimize tests.

4. **Coverage Exclusions Strategy**
   - What we know: Some code is truly untestable (OS-specific, external dependencies)
   - What's unclear: How much `# pragma: no cover` is acceptable before coverage metric becomes meaningless
   - Recommendation: Audit existing exclusions, document rationale for each. Target <5% excluded lines. Re-evaluate exclusions quarterly.

## Sources

### Primary (HIGH confidence)

- **pytest-cov documentation** - Coverage enforcement, `--cov-fail-under` flag, branch coverage
- **Hypothesis documentation** - Property testing patterns, `max_examples` settings, health checks
- **pytest-xdist documentation** - Parallel test execution, worker distribution
- **pre-commit documentation** - Local git hooks, hook configuration

### Secondary (MEDIUM confidence)

- [CI/CD中的测试覆盖率门禁：低于80%？拒绝合并](https://m.toutiao.com/a7598103419856880154/) - Industry standard 80% threshold in CI/CD
- [如何建立完美的 Python 项目](https://m.163.com/dy/article/GC7BCVEC0531PCHX.html) - Coverage best practices, pytest-cov usage
- [Python持续集成高级教程](https://m.php.cn/faq/1918745.html) - CI/CD coverage gate implementation strategies
- [pre-commit终极指南](https://m.blog.csdn.net/gitblog_00828/article/details/154965580) - Pre-commit coverage check configuration
- [Hypothesis属性测试库终极使用指南](https://m.blog.csdn.net/gitblog_00820/article/details/155730023) - Hypothesis max_examples best practices (50-200 for CI, 1000+ for local)

### Tertiary (LOW confidence)

- [Mopidy单元测试覆盖率报告](https://m.blog.csdn.net/gitblog_01022/article/details/151646320) - Example project's coverage configuration (single source, needs verification)
- [Test Documentation for Anomalib](https://gitee.com/atari/anomalib/tree/master/tests) - Another project's test setup (for comparison only)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - All libraries are industry standards with extensive documentation. Already installed in Atom backend.
- Architecture: **HIGH** - CI/CD patterns verified from official docs (pytest-cov, Hypothesis, pre-commit). 80% threshold confirmed by multiple sources as industry standard.
- Pitfalls: **HIGH** - Pitfalls identified from common CI/CD anti-patterns documented in industry best practices. Specific to Atom's existing infrastructure (96.9% coverage, 168 property test files).

**Research date:** 2026-02-22
**Valid until:** 2026-03-24 (30 days - stable domain, testing best practices evolve slowly)

**Atom-specific context:**
- Current coverage: 96.9% (well above 80% threshold)
- Property tests: 168 files already exist in `tests/property_tests/`
- CI/CD: GitHub Actions workflows already configured (ci.yml, property-tests.yml, deploy.yml)
- Pre-commit: Already configured but threshold set to 55% (needs update to 80%)
- pytest-xdist: Already configured with 7.2x speedup achieved
- Hypothesis: Already installed (>=6.92.0,<7.0.0)

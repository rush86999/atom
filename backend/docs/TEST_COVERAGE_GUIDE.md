# Test Coverage Guide

**Purpose**: Comprehensive guide for understanding, measuring, and improving test coverage in Atom OS backend.

**Last Updated**: 2026-02-25

---

## Table of Contents

1. [Overview](#overview)
2. [Coverage Targets](#coverage-targets)
3. [How to Measure Coverage](#how-to-measure-coverage)
4. [Improving Coverage](#improving-coverage)
5. [Coverage Maintenance](#coverage-maintenance)
6. [Tools and Scripts](#tools-and-scripts)

---

## Overview

### Why Coverage Matters

Test coverage is a critical metric for:

- **Bug Prevention**: Catch issues before they reach production
- **Refactoring Confidence**: Make changes with assurance that existing functionality isn't broken
- **Code Quality**: High coverage correlates with fewer defects and better maintainability
- **Team Velocity**: Reduce time spent debugging and fixing regressions
- **Documentation**: Tests serve as executable documentation of expected behavior

### Current Coverage Status

**Overall Coverage**: 74.55% (as of Phase 090)
**Goal**: 80% overall coverage
**Total Tests**: 342 tests (100% pass rate)

**Coverage by Module**:
- Governance: 74.55% (core/agent_governance_service.py)
- Database Models: 82%+ (core/models.py)
- API Routes: 70-85% (varies by endpoint)
- Tools: 65-80% (browser, canvas, device)
- LLM Integration: 68% (core/llm/)

**Trends**: Coverage has improved from 15.87% (Milestone v1.0) to 74.55% (Milestone v3.2) - a 370% improvement.

---

## Coverage Targets

Coverage targets are tiered by module criticality and risk profile.

### Critical Modules: >90% Coverage

**Definition**: Modules handling security, governance, financial transactions, or data integrity.

**Examples**:
- `core/agent_governance_service.py` - Agent permissions and maturity
- `core/models.py` - Database schema and integrity
- `core/security/*.py` - Security validation, JWT, auth
- `core/financial/*.py` - Payment processing, accounting
- `api/auth_routes.py` - Authentication endpoints

**Rationale**: Security and financial bugs are expensive and damage trust. These modules warrant the highest coverage.

### Core Services: >85% Coverage

**Definition**: Core business logic and agent orchestration.

**Examples**:
- `core/agent_context_resolver.py` - Agent resolution
- `core/episode_*.py` - Episodic memory services
- `core/llm/byok_handler.py` - LLM routing and streaming
- `core/governance_cache.py` - Performance-critical caching
- `tools/canvas_tool.py` - Canvas presentations

**Rationale**: Core services handle complex business logic. High coverage ensures reliability and reduces debugging time.

### Standard Modules: >80% Coverage

**Definition**: API endpoints, tools, and standard integrations.

**Examples**:
- `api/*.py` - REST API routes
- `tools/browser_tool.py` - Browser automation
- `tools/device_tool.py` - Device capabilities
- `core/skill_adapter.py` - Community skills integration
- `core/package_governance_service.py` - Package governance

**Rationale**: Standard modules interact with external systems. Coverage ensures graceful error handling and contract compliance.

### Support Modules: >70% Coverage

**Definition**: Utilities, fixtures, helpers, and non-critical code.

**Examples**:
- `core/utils/*.py` - Utility functions
- `tests/conftest.py` - Test fixtures
- `tests/fixtures/*.py` - Test data factories
- `cli/*.py` - CLI commands (low risk)
- `docs/*.py` - Documentation generators

**Rationale**: Support modules have lower business impact. Lower coverage targets allow faster iteration while maintaining quality.

---

## How to Measure Coverage

### Run Coverage with pytest

**Basic coverage report**:
```bash
cd backend
pytest tests/ --cov=core --cov-report=term-missing
```

**HTML report with drill-down**:
```bash
pytest tests/ --cov=core --cov-report=html
open htmlcov/index.html  # macOS
# On Linux: xdg-open htmlcov/index.html
```

**Multiple modules**:
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
```

**Coverage for specific test file**:
```bash
pytest tests/test_governance.py --cov=core.agent_governance_service --cov-report=term
```

### Parse Coverage JSON for CI Integration

Use `parse_coverage_json.py` to extract metrics programmatically:

```bash
# JSON output (default)
python tests/scripts/parse_coverage_json.py

# Text summary
python tests/scripts/parse_coverage_json.py --format text

# CSV for spreadsheet analysis
python tests/scripts/parse_coverage_json.py --format csv

# Query specific module
python tests/scripts/parse_coverage_json.py --module core.agent_governance_service

# Filter by coverage threshold
python tests/scripts/parse_coverage_json.py --below-threshold 80
```

**Example JSON output**:
```json
{
  "overall_coverage": 74.55,
  "total_lines": 15234,
  "covered_lines": 11361,
  "modules": [
    {
      "name": "core.agent_governance_service",
      "line_coverage": 74.55,
      "branch_coverage": 68.2,
      "missing_lines": 42
    }
  ]
}
```

### Pre-commit Coverage Enforcement

Use `enforce_coverage.py` to check coverage before pushing:

```bash
# Check all files (default 80% minimum)
python tests/scripts/enforce_coverage.py

# Check only changed files
python tests/scripts/enforce_coverage.py --files-only

# Set custom threshold
python tests/scripts/enforce_coverage.py --minimum 85

# Verbose output with details
python tests/scripts/enforce_coverage.py --verbose
```

**Exit codes**:
- `0`: All checks passed
- `1`: Coverage below threshold
- `2`: Coverage regression detected

---

## Improving Coverage

### Step 1: Identify Low-Coverage Modules

**Use trending data**:
```bash
python tests/scripts/generate_coverage_trend.py
cat tests/coverage_reports/metrics/trending.json
```

**Use gap analysis**:
```bash
python tests/scripts/analyze_coverage_gaps.py
```

**View HTML report**:
```bash
pytest tests/ --cov=core --cov-report=html
open htmlcov/index.html
# Sort by coverage percentage to find lowest files
```

### Step 2: Prioritize Critical Paths

**Priority order**:
1. **User-facing features** - API endpoints, agent execution
2. **Data modification** - Database writes, state changes
3. **Error handling** - Exception paths, edge cases
4. **Security/governance** - Permission checks, validation

**Focus on high-risk areas**:
- Financial calculations (use `decimal.Decimal`, property tests)
- Security checks (authentication, authorization)
- External integrations (API calls, webhooks)
- State management (database transactions, caching)

### Step 3: Add Tests Incrementally

**Start with happy path**:
```python
def test_agent_permission_granted():
    """Test that agents with sufficient permissions can execute actions."""
    agent = create_agent(maturity="AUTONOMOUS")
    result = agent_governance_service.check_permission(agent, action="execute")
    assert result.granted is True
```

**Add error cases**:
```python
def test_agent_permission_denied_for_student():
    """Test that STUDENT agents cannot execute high-complexity actions."""
    agent = create_agent(maturity="STUDENT")
    result = agent_governance_service.check_permission(agent, action="execute", complexity=4)
    assert result.granted is False
    assert result.reason == "Insufficient maturity"
```

**Use property tests for edge cases**:
```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=0, max_value=100))
def test_confidence_threshold_boundary(confidence):
    """Test that confidence threshold validation works at boundaries."""
    agent = create_agent(confidence=confidence / 100)
    result = agent_governance_service.can_automate_trigger(agent)
    # STUDENT agents blocked regardless of confidence
    if agent.maturity == "STUDENT":
        assert result is False
```

**Cover all branches**:
```python
def test_governance_cache_miss():
    """Test cache miss scenario."""
    cache = GovernanceCache()
    # Clear cache to force miss
    cache.clear()
    result = cache.get("agent_123")
    assert result is None

def test_governance_cache_hit():
    """Test cache hit scenario."""
    cache = GovernanceCache()
    cache.set("agent_123", {"maturity": "AUTONOMOUS"})
    result = cache.get("agent_123")
    assert result["maturity"] == "AUTONOMOUS"
```

### Step 4: Verify Coverage Improvement

**Before and after comparison**:
```bash
# Before: Run coverage
pytest tests/ --cov=core.agent_governance_service --cov-report=term-missing

# Add tests...

# After: Run coverage again
pytest tests/ --cov=core.agent_governance_service --cov-report=term-missing

# Compare: Look for increased percentage
```

**Use coverage diff**:
```bash
# Generate baseline
pytest tests/ --cov=core --cov-context=test --cov-report=xml > before.xml

# Make changes...

# Generate new report
pytest tests/ --cov=core --cov-context=test --cov-report=xml > after.xml

# Diff coverage (requires coveragepy)
python -m coverage diff before.xml after.xml
```

---

## Coverage Maintenance

### Pre-commit Hook Enforcement

**Install pre-commit hook**:
```bash
# .git/hooks/pre-commit
#!/bin/bash
cd backend
python tests/scripts/enforce_coverage.py --files-only --minimum 80
if [ $? -ne 0 ]; then
    echo "Coverage check failed. Run tests to improve coverage before pushing."
    exit 1
fi
```

**Make executable**:
```bash
chmod +x .git/hooks/pre-commit
```

### CI Gate Enforcement

**GitHub Actions workflow** (`.github/workflows/test-coverage.yml`):
```yaml
- name: Enforce coverage gate
  run: |
    python tests/scripts/ci_quality_gate.py
```

**Gate thresholds**:
- **Minimum coverage**: 80% overall
- **Minimum pass rate**: 98% (check_pass_rate.py)
- **Regression threshold**: 5% drop from baseline
- **Flaky test tolerance**: 10% (detect_flaky_tests.py)

**PR comments**: CI workflow automatically posts coverage comments on PRs:
```markdown
## Coverage Report

Overall: 74.55% (+2.3%)

Top modules below 80% threshold:
- core/agent_governance_service.py: 74.55% (-42 lines)
- tools/browser_tool.py: 68.2% (-15 lines)

See detailed report: [HTML Coverage](link-to-report)
```

### Regression Detection

**Track coverage over time**:
```bash
python tests/scripts/update_coverage_trending.py
cat tests/coverage_reports/metrics/trending.json
```

**Regression alert**: If coverage drops by >5% from baseline, CI gate fails.

**Recovery plan**:
1. Identify dropped coverage (compare HTML reports)
2. Determine if regression is acceptable (e.g., removed code)
3. Update baseline or add tests to recover coverage

### Regular Coverage Audits

**Monthly coverage review**:
1. Generate coverage report: `pytest tests/ --cov=core --cov-report=html`
2. Identify modules below threshold
3. Create tickets for coverage improvement
4. Track progress in next review

**Quarterly quality assessment**:
1. Review coverage targets (adjust if needed)
2. Evaluate test quality (pass rate, flakiness, execution time)
3. Assess testing tools and infrastructure
4. Update documentation and best practices

---

## Tools and Scripts

### Coverage Tools

| Script | Purpose | Usage |
|--------|---------|-------|
| `enforce_coverage.py` | Pre-commit coverage enforcement | `python enforce_coverage.py --minimum 80` |
| `check_pass_rate.py` | Test suite health monitoring | `python check_pass_rate.py --threshold 98` |
| `detect_flaky_tests.py` | Flaky test identification | `python detect_flaky_tests.py --runs 3` |
| `generate_coverage_trend.py` | Trend analysis over time | `python generate_coverage_trend.py` |
| `coverage_report_generator.py` | Actionable insights generation | `python coverage_report_generator.py --output report.md` |
| `parse_coverage_json.py` | CI integration and metrics extraction | `python parse_coverage_json.py --format json` |
| `analyze_coverage_gaps.py` | Gap identification and prioritization | `python analyze_coverage_gaps.py --below 80` |
| `ci_quality_gate.py` | Unified CI gate enforcement | `python ci_quality_gate.py --verbose` |

### pytest Configuration

**pytest.ini**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage
addopts =
    --cov=core
    --cov=api
    --cov=tools
    --cov-report=html
    --cov-report=term-missing
    --cov-context=test

# Markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, external deps)
    property: Property-based tests (Hypothesis)
    slow: Slow tests (>1s)
```

### Coverage Badges

**README badges**:
```markdown
![Coverage](https://img.shields.io/badge/coverage-74.55%25-yellow)
![Tests](https://img.shields.io/badge/tests-342-brightgreen)
![Pass Rate](https://img.shields.io/badge/pass_rate-100%25-brightgreen)
```

**Generate badges dynamically**:
```bash
# Use coverage JSON to generate badges
python tests/scripts/generate_badges.py
```

---

## Best Practices

### DO:
- Write tests alongside code (test-driven development when possible)
- Aim for high coverage on critical paths (>90%)
- Use property tests for complex logic (Hypothesis)
- Mock external dependencies (APIs, databases)
- Keep tests independent and deterministic
- Review coverage reports regularly

### DON'T:
- Chase 100% coverage at the expense of quality
- Test implementation details (test behavior, not code)
- Write brittle tests that break on refactoring
- Mock what you don't own (test integrations with real libraries)
- Share state between tests (use fixtures)
- Ignore coverage warnings

---

## Related Documentation

- [QUALITY_STANDARDS.md](QUALITY_STANDARDS.md) - Testing patterns and conventions
- [QUALITY_RUNBOOK.md](QUALITY_RUNBOOK.md) - Troubleshooting and debugging
- [backend/README.md](../README.md) - Project overview and quick start

---

*Last Updated: 2026-02-25*
*Phase: 090 (Quality Gates & CI/CD)*
*Plan: 06 (Documentation & Maintenance)*

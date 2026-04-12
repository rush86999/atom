# Coverage Report Guide

**Last Updated:** 2026-04-12
**Status:** Production Ready

---

## Overview

This guide explains how to measure, interpret, and improve code coverage for the Atom backend. Coverage is a key quality metric that tracks how much of the codebase is exercised by tests.

---

## What is Code Coverage?

**Definition:** Code coverage measures the percentage of code lines executed during test runs.

**Why It Matters:**
1. **Quality Signal:** Higher coverage correlates with fewer bugs
2. **Refactoring Safety:** Tests provide safety net for changes
3. **Documentation:** Tests show how code should work
4. **Regression Prevention:** Catch bugs early

**Important:** Coverage is a *tool*, not a *goal*. 100% coverage doesn't guarantee bug-free code, but low coverage indicates insufficient testing.

---

## Coverage Targets

### Progressive Thresholds

| Phase | Target | Timeline | Status |
|-------|--------|----------|--------|
| Baseline | Measured | Phase 251 | ✅ Complete (4.60%) |
| Threshold 1 | 70% | Phase 252+ | 🚧 In Progress |
| Threshold 2 | 75% | Phase 253+ | ⏳ Planned |
| Final Target | 80% | Phase 253+ | ⏳ Planned |

### Component Breakdown

| Component | Current | Target | Priority |
|-----------|---------|--------|----------|
| `core/` | 4.60% | 80% | High |
| `api/` | TBD | 80% | High |
| `tools/` | TBD | 80% | Medium |

---

## How to Measure Coverage

### Quick Coverage Check

```bash
# Backend coverage summary
cd backend
python3 -m pytest --cov=core --cov=api --cov=tools --cov-report=term-missing -q

# Expected output:
# Name                 Stmts   Miss  Cover   Missing
# --------------------------------------------------
# core/agent_governance_service.py    100      5    95%   23-27
# core/llm/byok_handler.py            200     50    75%   45-67, 89-102
# ...
# TOTAL                            5000    2500    50%
```

### Full Coverage Report

```bash
# Generate detailed coverage report
python3 -m pytest \
  --cov=core \
  --cov=api \
  --cov=tools \
  --cov-report=html \
  --cov-report=json:tests/coverage_reports/metrics/coverage_latest.json \
  --cov-report=term-missing \
  --cov-branch \
  -q

# View HTML report
open htmlcov/index.html
```

### Coverage for Specific Module

```bash
# Coverage for single module
python3 -m pytest --cov=core.agent_governance_service --cov-report=term-missing -q

# Coverage for single test file
python3 -m pytest tests/test_governance_services.py --cov=core.agent_governance_service --cov-report=term-missing -q
```

### Branch Coverage

```bash
# Measure branch coverage (if/else statements)
python3 -m pytest --cov=core --cov-branch --cov-report=term-missing -q

# Output includes:
# Name                 Stmts   Miss Branch BrPart  Cover   Missing
# ----------------------------------------------------------------------
# core/governance.py      50      5     10      2    90%   23-27
#                                                    85%   2/10
```

---

## Interpreting Coverage Reports

### Reading Terminal Output

```
Name                                      Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------
core/agent_governance_service.py            100     20    80%   23-27, 45-49
core/llm/byok_handler.py                    200     50    75%   12-15, 89-102
core/episode_segmentation_service.py        150     30    80%   67-89
----------------------------------------------------------------------------
TOTAL                                       450    100    78%
```

**Columns:**
- **Stmts:** Total statements in file
- **Miss:** Statements not executed by tests
- **Cover:** Percentage coverage (Stmts - Miss) / Stmts
- **Missing:** Line numbers not covered

**Example:** `core/agent_governance_service.py` has 100 statements, 20 missed (80% coverage). Missing lines 23-27, 45-49.

### Reading HTML Report

**HTML Report Features:**
- **File Overview:** Coverage percentage per file
- **Line Highlights:** Red = uncovered, green = covered, yellow = partially covered
- **Branch Indicators:** Show which if/else branches not taken
- **Navigation:** Click files to see detailed line-by-line coverage

**Access:**
```bash
# Generate HTML report
python3 -m pytest --cov=core --cov-report=html -q

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Reading JSON Report

**JSON Structure:**
```json
{
  "totals": {
    "percent_covered": 78.5,
    "covered_lines": 353,
    "num_statements": 450,
    "num_branches": 50,
    "covered_branches": 40
  },
  "files": {
    "core/agent_governance_service.py": {
      "summary": {
        "percent_covered": 80.0,
        "covered_lines": 80,
        "num_statements": 100
      },
      "missing_lines": [23, 24, 25, 26, 27, 45, 46, 47, 48, 49]
    }
  }
}
```

**Use Cases:**
- Automated metrics collection
- Trend analysis
- CI/CD integration
- Dashboard data feed

---

## Improving Coverage

### Strategy 1: Cover High-Impact Files First

**Identify High-Impact Files:**
```bash
# Find files with >200 lines and low coverage
python3 -c "
import json
with open('tests/coverage_reports/metrics/coverage_latest.json') as f:
    data = json.load(f)

for file, metrics in data['files'].items():
    stmts = metrics['summary']['num_statements']
    cover = metrics['summary']['percent_covered']
    if stmts > 200 and cover < 50:
        print(f'{file}: {stmts} stmts, {cover:.1f}% cover')
"
```

**Prioritize:**
1. Core business logic (`core/`)
2. API endpoints (`api/`)
3. Integration points (`tools/`)

### Strategy 2: Add Tests for Missing Lines

**Example:** Missing lines 23-27 in `agent_governance_service.py`

```python
# Read the uncovered code
# Lines 23-27:
def check_permission(self, agent, action, complexity=1):
    if agent.maturity == AgentMaturity.STUDENT and complexity > 1:
        return PermissionResult(granted=False, reason="Blocked")

# Write test to cover this path
def test_student_blocked_from_high_complexity():
    student = AgentRegistry(id="test", maturity=AgentMaturity.STUDENT)
    result = service.check_permission(student, "action", complexity=3)
    assert result.granted == False  # Covers lines 23-27
```

### Strategy 3: Cover Edge Cases

**Common Uncovered Paths:**
- Error handling (`except` blocks)
- Edge cases (empty, None, zero)
- Boundary conditions (min/max values)
- Rare branches (specific error codes)

**Example:**
```python
# Original code (lines 89-102 uncovered)
def process_agent(self, agent_id):
    try:
        agent = self.get_agent(agent_id)
        return agent
    except AgentNotFound:
        logger.error(f"Agent not found: {agent_id}")
        return None  # Line 102 uncovered

# Test to cover error path
def test_process_agent_not_found_returns_none():
    result = service.process_agent("nonexistent")
    assert result is None  # Covers line 102
```

### Strategy 4: Use Coverage-Driven Development

**Workflow:**
1. Write code
2. Check coverage
3. Identify uncovered lines
4. Write tests for uncovered lines
5. Repeat until coverage target met

**Example:**
```bash
# Initial coverage: 60%
pytest --cov=core --cov-report=term-missing -q

# Add tests for missing lines
# Check again: 75%

# Add more tests
# Check again: 80% (target met)
```

---

## Coverage Anti-Patterns

### Anti-Pattern 1: Useless Coverage

**Bad:**
```python
def test_add():
    assert add(1, 1) == 2  # Trivial, adds no value
```

**Better:**
```python
def test_add_with_negative_numbers():
    assert add(-1, -1) == -2  # Edge case
```

### Anti-Pattern 2: Coverage Inflation

**Bad:**
```python
def test_coverage_inflation():
    # Call every function without assertions
    agent_service.get_agent("test")
    agent_service.create_agent("test")
    agent_service.delete_agent("test")
    # High coverage, low value
```

**Better:**
```python
def test_agent_lifecycle():
    agent = agent_service.create_agent("test")
    assert agent.id == "test"
    retrieved = agent_service.get_agent("test")
    assert retrieved.id == "test"
    # Meaningful assertions
```

### Anti-Pattern 3: Testing Implementation

**Bad:**
```python
def test_internal_variable():
    service._internal_var = 5  # Tests implementation detail
    assert service.calculate() == 10
```

**Better:**
```python
def test_public_api():
    result = service.process(input_data=5)  # Tests public interface
    assert result == expected
```

---

## Coverage in CI/CD

### Quality Gates

**Configuration:** `.github/workflows/quality-gate.yml`

```yaml
# Enforce 70% coverage threshold
- name: Check coverage threshold
  run: |
    python3 -c "
    coverage = data['totals']['percent_covered']
    if coverage < 70.0:
        print(f'❌ Coverage {coverage:.2f}% below 70%')
        exit(1)
    "
```

### PR Comments

**Automatic Feedback:**
```markdown
## 📊 Coverage Report

| Component | Coverage | Threshold | Status |
|-----------|----------|-----------|--------|
| Backend | 75.5% | 70% | ✅ |
| Frontend | 68.2% | 70% | ❌ |

⚠️ **Action Required**: Frontend coverage below threshold.
```

---

## Coverage Trends

### Track Progress Over Time

**Historical Data:** `tests/coverage_reports/metrics/quality_metrics.json`

**View Trends:**
```bash
# Plot coverage over time
python3 .github/scripts/plot-coverage-trends.py
```

**Expected Progression:**
```
Phase 251: 4.60% (baseline)
Phase 252: 15.20% (+10.60%)
Phase 253b: 18.50% (+3.30%)
Phase 253: 25.00% (+6.50%)
Target: 80.00% (+55.00% from baseline)
```

---

## Troubleshooting

### Issue: Coverage Decreased

**Diagnosis:**
```bash
# Find what caused decrease
git diff HEAD~1 coverage_report.json
```

**Solution:**
- Add tests for new code
- Restore accidentally deleted tests
- Check test exclusions

### Issue: Coverage Not Increasing

**Diagnosis:**
```bash
# Check if tests actually execute code
python3 -m pytest --cov=core --cov-report=annotate -q
# View annotated files: cat core_agent_governance_service.py_cover
```

**Solution:**
- Verify tests actually call production code
- Check for mocked code (doesn't count as coverage)
- Add integration tests

### Issue: Slow Coverage Measurement

**Diagnosis:**
```bash
# Profile coverage run
python3 -m pytest --cov=core --cov-report=term-missing --profile -q
```

**Solution:**
- Use `--parallel` to run tests in parallel
- Exclude slow tests from coverage
- Split coverage runs by module

---

## Best Practices

1. **Aim for Meaningful Coverage**
   - Test critical paths
   - Cover edge cases
   - Don't chase 100% blindly

2. **Review Missing Lines**
   - Understand why not covered
   - Decide if needs test
   - Document exceptions

3. **Use Branch Coverage**
   - More accurate than line coverage
   - Shows missing if/else paths
   - Better quality signal

4. **Combine with Other Metrics**
   - Code complexity
   - Test pass rate
   - Bug frequency

5. **Automate Coverage Checks**
   - CI/CD quality gates
   - PR comments
   - Trend monitoring

---

## Related Documentation

- **Testing Guide:** `TESTING.md`
- **Quality Dashboard:** `docs/QUALITY_DASHBOARD.md`
- **Quality Gates:** `.github/workflows/quality-gate.yml`
- **Bug Fix Process:** `docs/BUG_FIX_PROCESS.md`

---

**Coverage Report Guide Version:** 1.0
**Last Updated:** 2026-04-12
**Maintained By:** Development Team

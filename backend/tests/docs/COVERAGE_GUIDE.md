# Coverage Report Interpretation Guide

**Purpose**: Comprehensive guide for interpreting coverage reports and improving test coverage.

**Last Updated**: 2026-02-11

---

## Overview

Code coverage measures how much of your codebase is executed by tests. Coverage reports help identify untested code, track testing progress, and enforce quality standards.

**Key Concepts**:
- **Line Coverage**: Percentage of executable lines executed by tests
- **Branch Coverage**: Percentage of code branches (if/else, try/except) executed by tests
- **Coverage Paradox**: High coverage numbers don't guarantee high quality

**Project Coverage Targets**:
- Overall backend: 80%
- Governance domain: 80%
- Security domain: 80%
- Episodes domain: 80%

---

## Coverage Metrics Explained

### Line Coverage vs Branch Coverage

**Line Coverage** measures which lines of code were executed:
```
def check_permission(user, action):
    if user.is_admin:           # Line 1
        return True              # Line 2
    return False                 # Line 3
```

If tests only call `check_permission(admin_user, "read")`:
- Line coverage: 67% (lines 1-2 executed, line 3 not executed)
- Branch coverage: 50% (only "if" branch tested, "else" branch not tested)

**Branch Coverage** is more accurate because it measures all possible execution paths:
- If statements: 2 branches (true, false)
- Try/except: 2 branches (success, exception)
- Short-circuit operators: 2 branches (or, and)

**Why Branch Coverage Matters**:
```python
# Line coverage: 100%, Branch coverage: 50%
def divide(a, b):
    if b != 0 and a / b > 10:   # Both lines executed
        return "large"
    return "small"

# Test: divide(20, 2) → lines 1-3 executed
# Missing: divide(10, 0) → exception path not tested
```

**Recommendation**: Always enable branch coverage with `--cov-branch` flag (already in pytest.ini).

---

### Coverage Percentage Interpretation

| Coverage Range | Interpretation | Action |
|----------------|----------------|--------|
| 0-20% | Untested codebase | Start with critical paths |
| 20-50% | Early testing | Focus on core functionality |
| 50-80% | Good coverage | Target for most projects |
| 80-90% | Excellent coverage | Diminishing returns above 80% |
| 90-100% | Near-perfect | Risk of over-testing |

**Diminishing Returns Above 90%**:
- Last 10% costs 50% of testing effort
- Focus on critical paths first
- 100% coverage is rarely practical

**When 80% is Sufficient**:
- Error handling is tested
- Critical paths covered
- Property tests validate invariants
- Integration tests cover workflows

---

### Coverage Paradox

**High Coverage, Low Quality**: Tests cover lines but not scenarios.

**Example**:
```python
# Line coverage: 100%, Branch coverage: 100%
# Quality: LOW (no assertions verify correctness)

def calculate_discount(price, user):
    if user.is_vip:
        return price * 0.9
    return price

def test_calculate_discount():
    calculate_discount(100, vip_user)    # Line covered
    calculate_discount(100, regular_user) # Line covered
    # No assertions! Bugs would pass silently.
```

**Detection Strategies**:
1. **Property-based tests**: Validate invariants across all inputs (Hypothesis)
2. **Mutation testing**: Detect weak tests (mutmut)
3. **Assertion density**: Track assertions per line (conftest.py)

**See**: `property_tests/INVARIANTS.md` for property test patterns.

---

### Missing Coverage

**0% Coverage Means**:
- No tests execute this code
- Untested bugs may exist
- Refactoring is risky

**Common Causes**:
1. **Dead code**: Unused functions (consider removing)
2. **Error paths**: Exception handlers not tested
3. **Edge cases**: Boundary conditions not covered
4. **New code**: Written without tests

**Priority for Improving Coverage**:
1. **Critical paths**: Authentication, authorization, payments
2. **Security**: Input validation, encryption, access control
3. **Data integrity**: Database operations, transactions
4. **User-facing**: API endpoints, business logic

---

## Reading Coverage Reports

### HTML Report Navigation

**Location**: `backend/tests/coverage_reports/html/index.html`

**Usage**:
```bash
# Generate HTML report
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html

# Open in browser
open tests/coverage_reports/html/index.html
```

**Interpretation**:
- **Green**: >80% coverage (good)
- **Yellow**: 50-80% coverage (needs improvement)
- **Red**: <50% coverage (critical gaps)

**HTML Report Features**:
- Click directory to see files
- Click file to see line-by-line coverage
- Red lines = not executed
- Yellow lines = partially executed (branch coverage)

---

### JSON Report Structure

**Location**: `backend/tests/coverage_reports/metrics/coverage.json`

**Format**:
```json
{
  "meta": {
    "timestamp": "2026-02-11T10:30:00",
    "branch_coverage": true,
    "show_contexts": true
  },
  "totals": {
    "covered_lines": 2340,
    "num_statements": 15000,
    "percent_covered": 15.6,
    "covered_branches": 1200,
    "num_branches": 3000,
    "percent_covered_branch": 40.0
  },
  "files": {
    "core/agent_governance_service.py": {
      "summary": {
        "percent_covered": 45.2,
        "percent_covered_branch": 30.0
      },
      "executed_lines": [10, 11, 15, 20],
      "missing_lines": [25, 30, 35],
      "excluded_lines": [1, 2, 3]
    }
  }
}
```

**Key Fields**:
- `percent_covered`: Line coverage percentage
- `percent_covered_branch`: Branch coverage percentage
- `missing_lines`: Line numbers not executed
- `executed_lines`: Line numbers executed

**Usage in CI/CD**:
```bash
# Extract coverage percentage
COVERAGE=$(jq '.totals.percent_covered' tests/coverage_reports/metrics/coverage.json)

# Fail if below threshold
if (( $(echo "$COVERAGE < 80" | bc -l) )); then
    echo "Coverage $COVERAGE% below 80% threshold"
    exit 1
fi
```

---

### Terminal Report Interpretation

**Generate Terminal Report**:
```bash
pytest tests/ --cov-report=term-missing
```

**Output Format**:
```
Name                                         Stmts   Miss  Cover   Missing
------------------------------------------------------------------------
core/agent_governance_service.py               150     75    50%   23-45, 89-102
core/models.py                                 300    120    60%   156-189, 234-267
api/auth_routes.py                              50     40    20%   12-35, 67-89
------------------------------------------------------------------------
TOTAL                                          500    235    53%
```

**Columns**:
- `Stmts`: Total executable statements
- `Miss`: Statements not executed
- `Cover`: Coverage percentage
- `Missing`: Line ranges not covered

**Color Coding**:
- Green: >80%
- Yellow: 50-80%
- Red: <50%

---

## Coverage by Domain

### Governance Domain

**Target**: 80%
**Current**: 13.37% (as of 2026-02-11)

**Files**:
- `agent_governance_service.py` - Agent lifecycle and permissions
- `agent_context_resolver.py` - Agent resolution
- `governance_cache.py` - High-performance caching
- `trigger_interceptor.py` - Maturity-based trigger routing

**Priority Tests**:
1. Maturity threshold enforcement (STUDENT agents block high-complexity actions)
2. Confidence-based routing (low confidence → supervised)
3. Permission checks (all 4x4 maturity/complexity combinations)

**Impact**: Governance failures cause unauthorized actions or security violations.

---

### Security Domain

**Target**: 80%
**Current**: 22.40% (as of 2026-02-11)

**Files**:
- `auth_routes.py` - Authentication endpoints
- `encryption.py` - Data encryption/decryption
- `validation.py` - Input validation

**Priority Tests**:
1. JWT token validation (expired, invalid, malformed)
2. Password hashing (bcrypt, salt rounds)
3. Input validation (OWASP Top 10 payloads)
4. SQL injection prevention (parameterized queries)

**Impact**: Security failures cause unauthorized access or data breaches.

---

### Episodes Domain

**Target**: 80%
**Current**: 15.52% (as of 2026-02-11)

**Files**:
- `episode_segmentation_service.py` - Episode creation
- `episode_retrieval_service.py` - Episode retrieval
- `episode_lifecycle_service.py` - Episode lifecycle
- `agent_graduation_service.py` - Graduation validation

**Priority Tests**:
1. Time gap detection (boundaries, thresholds)
2. Semantic retrieval (similarity, ranking)
3. Graduation criteria (episode count, intervention rate)
4. Constitutional compliance (intervention tracking)

**Impact**: Episode failures cause incorrect agent learning or premature promotion.

---

### Backend Overall

**Target**: 80%
**Current**: 15.57% (as of 2026-02-11)

**Files Tracked**: 401 files

**Breakdown**:
- Governance: 13.37%
- Security: 22.40%
- Episodes: 15.52%
- Other domains: Variable

**Focus Areas**:
1. Critical paths: Auth, governance, payments
2. Error handling: Exception paths, edge cases
3. Integration points: API endpoints, database operations

---

## Coverage Trending

### Tracking Coverage Over Time

**Purpose**: Detect coverage regressions and measure progress.

**Location**: `backend/tests/coverage_reports/trends/coverage_trend.json`

**Format**:
```json
{
  "coverage_history": [
    {
      "date": "2026-02-11",
      "commit": "abc123",
      "overall_percent": 15.57,
      "governance_percent": 13.37,
      "security_percent": 22.40,
      "episodes_percent": 15.52
    }
  ],
  "targets": {
    "overall": 80,
    "governance": 80,
    "security": 80,
    "episodes": 80
  }
}
```

**Usage**:
```bash
# View trend
jq '.coverage_history[] | .date + ": " + (.overall_percent | tostring) + "%"' \
  tests/coverage_reports/trends/coverage_trend.json

# Detect regression
LATEST=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
PREVIOUS=$(jq '.coverage_history[1].overall_percent' coverage_trend.json)

if (( $(echo "$LATEST < $PREVIOUS" | bc -l) )); then
    echo "Coverage regression detected: $PREVIOUS% → $LATEST%"
fi
```

---

### Detecting Coverage Regressions

**Regression**: Coverage decreases between commits.

**CI/CD Check**:
```yaml
# .github/workflows/coverage-report.yml
- name: Check coverage regression
  run: |
    LATEST=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
    PREVIOUS=$(jq '.coverage_history[1].overall_percent' coverage_trend.json)
    THRESHOLD=1.0  # 1% tolerance

    if (( $(echo "$PREVIOUS - $LATEST > $THRESHOLD" | bc -l) )); then
      echo "Coverage regression: $PREVIOUS% → $LATEST%"
      exit 1
    fi
```

**Common Causes**:
1. Deleted tests without replacement
2. Refactored code without updating tests
3. New code written without tests

---

### Coverage Thresholds and Quality Gates

**Quality Gate**: Minimum coverage requirement for PR approval.

**Configuration** (pytest.ini):
```ini
[pytest]
cov_fail_under = 80
```

**CI/CD Enforcement**:
```yaml
- name: Run tests with coverage
  run: pytest tests/ --cov=core --cov=api --cov=tools --cov-fail-under=80
```

**Per-Domain Thresholds**:
```python
# conftest.py
def pytest_terminal_summary(terminalreporter):
    coverage_data = json.load(open("coverage.json"))

    governance_cov = coverage_data['files']['core/agent_governance_service.py']['summary']['percent_covered']
    if governance_cov < 80:
        terminalreporter.write_line(f"ERROR: Governance coverage {governance_cov}% below 80%", red=True)
```

**Recommendation**: Start with 60% threshold, increase to 80% as coverage improves.

---

## Improving Coverage

### Identifying Uncovered Lines

**Step 1: Generate HTML Report**
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
open tests/coverage_reports/html/index.html
```

**Step 2: Find Red Files**
- Click through directories
- Look for files with <80% coverage
- Click file to see line-by-line breakdown

**Step 3: Analyze Missing Lines**
- Red lines = not executed
- Yellow lines = partially executed (branch coverage)
- Right-click line → "show context" to see why it's not covered

---

### Prioritizing Coverage Gaps

**Priority Matrix**:

| Impact | High Coverage | Low Coverage | Action |
|--------|---------------|--------------|--------|
| **Critical** | Error in test | **IMMEDIATE** | Fix tests |
| **High** | Monitor | **HIGH** | Add tests |
| **Medium** | Defer | **MEDIUM** | Add tests |
| **Low** | Accept | **LOW** | Document |

**Critical Paths** (test first):
1. Authentication: Login, logout, token refresh
2. Authorization: Permission checks, maturity enforcement
3. Data integrity: Database transactions, validation
4. Security: Encryption, input validation, access control

**Example Priority**:
```python
# CRITICAL: Auth bypass
if user.is_admin:  # Branch coverage: 50% → Fix immediately
    return sensitive_data

# HIGH: Business logic
if discount > 0.9:  # Branch coverage: 75% → Add test
    apply_discount()

# MEDIUM: Edge case
if user.preferences.color == "blue":  # Branch coverage: 0% → Defer
    set_theme("blue")
```

---

### Writing Tests for Uncovered Code

**Step 1: Understand What's Missing**
```python
# Original code (lines 25-30 not covered)
def delete_agent(agent_id, user):
    if not user.is_admin:          # Line 25
        raise PermissionError()     # Line 26
    agent = db.get(agent_id)        # Line 27
    if agent.status == "ACTIVE":    # Line 28
        raise ValueError()          # Line 29
    db.delete(agent)                # Line 30
```

**Step 2: Write Test for Missing Path**
```python
def test_delete_agent_requires_admin(unique_resource_name):
    """Test non-admin cannot delete agents (line 25-26)."""
    user = UserFactory.create(role="member")  # Not admin
    agent = AgentFactory.create(id=unique_resource_name)

    with pytest.raises(PermissionError):
        delete_agent(agent.id, user)

def test_delete_active_agent_fails(unique_resource_name):
    """Test deleting active agent raises error (line 28-29)."""
    admin = UserFactory.create(role="admin")
    agent = AgentFactory.create(id=unique_resource_name, status="ACTIVE")

    with pytest.raises(ValueError):
        delete_agent(agent.id, admin)

def test_delete_inactive_agent_succeeds(unique_resource_name):
    """Test deleting inactive agent works (line 30)."""
    admin = UserFactory.create(role="admin")
    agent = AgentFactory.create(id=unique_resource_name, status="INACTIVE")

    delete_agent(agent.id, admin)
    assert db.get(agent.id) is None
```

**Step 3: Run Tests**
```bash
pytest tests/test_agent_service.py -v --cov=core/agent_service --cov-report=term-missing
```

**Step 4: Verify Coverage Improved**
- Check HTML report
- Lines 25-30 should now be green

---

### When NOT to Chase 100% Coverage

**Exclusions from Coverage Targets**:

1. **Generated Code**:
   - Protobuf-generated files
   - OpenAPI-generated models
   - Database migration scripts

2. **Configuration**:
   - Constants, enums
   - Environment variable loading
   - Logging configuration

3. **Third-Party Wrappers**:
   - Thin wrappers around libraries
   - Adapter classes (1-2 lines)

4. **Impossible Paths**:
   - OS-specific code (Windows tests on Mac)
   - Hardware-dependent code
   - GUI code in CI/CD

**Example .coveragerc**:
```ini
[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

**Guideline**: 80% coverage is practical. 100% coverage is rarely worth the cost.

---

## Coverage Tools Reference

### pytest-cov Command Reference

**Basic Usage**:
```bash
# Run tests with coverage
pytest tests/ --cov=core

# Multiple modules
pytest tests/ --cov=core --cov=api --cov=tools

# Generate reports
pytest tests/ --cov=core --cov-report=html --cov-report=json --cov-report=term
```

**Report Formats**:
- `--cov-report=html`: HTML report (coverage_reports/html/index.html)
- `--cov-report=json`: JSON report (coverage.json)
- `--cov-report=term`: Terminal output
- `--cov-report=term-missing`: Terminal with missing lines

**Branch Coverage**:
```bash
pytest tests/ --cov=core --cov-branch
```

**Coverage Fail Threshold**:
```bash
pytest tests/ --cov=core --cov-fail-under=80
```

**Source Configuration**:
```bash
pytest tests/ --cov=core --cov-context=test
```

---

### Coverage.py CLI Reference

**Combine Coverage Data**:
```bash
# Run tests in parallel
pytest tests/ -n auto --cov=core --cov-parallel

# Combine .coverage files
coverage combine
```

**Generate Report After Tests**:
```bash
pytest tests/ --cov=core
coverage html    # Generate HTML
coverage report  # Generate terminal
coverage json    # Generate JSON
```

**Debug Coverage**:
```bash
coverage debug sys
coverage debug config
```

**Erase Coverage Data**:
```bash
coverage erase  # Delete .coverage file
```

---

### Codecov/Coveralls Integration

**Codecov Upload** (via GitHub Actions):
```yaml
- name: Upload to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./tests/coverage_reports/metrics/coverage.json
    flags: backend
    name: backend-coverage
    fail_ci_if_error: false  # Don't fail CI if Codecov is down
```

**Coveralls Upload** (alternative):
```yaml
- name: Upload to Coveralls
  uses: coverallsapp/github-action@v2
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    path-to-lcov: ./coverage.lcov
```

**Benefits**:
- Historical trending dashboard
- PR comments with coverage diff
- File-by-file coverage breakdown
- Coverage badges for README

**Alternative**: Git-tracked JSON (no external service needed)

---

## Related Documentation

- **[TEST_ISOLATION_PATTERNS.md](./TEST_ISOLATION_PATTERNS.md)** - Test isolation patterns and examples
- **[FLAKY_TEST_GUIDE.md](./FLAKY_TEST_GUIDE.md)** - Flaky test prevention and fixing
- **[../property_tests/INVARIANTS.md](../property_tests/INVARIANTS.md)** - Property test invariants
- **[../factories/README.md](../factories/README.md)** - Test data factory usage
- **[../TESTING_GUIDE.md](../TESTING_GUIDE.md)** - Comprehensive testing guide

---

## Summary

**Key Takeaways**:
1. **Branch coverage > Line coverage**: Always use `--cov-branch`
2. **80% is practical**: Diminishing returns above 90%
3. **Coverage paradox**: High coverage ≠ high quality (use property tests)
4. **Trending matters**: Track coverage over time to detect regressions
5. **Prioritize critical paths**: Auth, governance, security first

**Quick Reference**:
```bash
# Generate all reports
pytest tests/ --cov=core --cov=api --cov=tools \
  --cov-branch \
  --cov-report=html \
  --cov-report=json \
  --cov-report=term-missing

# Check coverage trend
jq '.coverage_history[0]' tests/coverage_reports/trends/coverage_trend.json

# View HTML report
open tests/coverage_reports/html/index.html
```

**Next Steps**:
1. Generate coverage report for your domain
2. Identify files <80% coverage
3. Write tests for critical paths first
4. Track coverage in CI/CD
5. Review coverage trends weekly

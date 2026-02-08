# Mutation Testing Guide

**Last Updated:** February 7, 2026
**Version:** 1.0.0

---

## Table of Contents

1. [What is Mutation Testing?](#what-is-mutation-testing)
2. [Why Mutation Testing?](#why-mutation-testing)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Running Mutation Tests](#running-mutation-tests)
6. [Interpreting Results](#interpreting-results)
7. [Quality Gates](#quality-gates)
8. [Best Practices](#best-practices)

---

## What is Mutation Testing?

Mutation testing is a technique for evaluating the quality of your test suite. It makes small changes (mutations) to your code and checks if your tests can detect them.

### How It Works

1. **Generate Mutants**: Mutmut introduces small bugs (mutations) into your code
   ```python
   # Original code
   if user.is_admin:
       grant_access()

   # Mutated code (conditional boundary mutation)
   if not user.is_admin:  # Changed: if → if not
       grant_access()
   ```

2. **Run Tests**: Mutmut runs your test suite against each mutant

3. **Classify Results**:
   - **Killed**: Tests detected the mutation (tests failed)
   - **Survived**: Tests didn't detect the mutation (tests still passed)
   - **Timeout**: Tests hung (potential performance issue)

4. **Calculate Score**:
   ```
   Mutation Score = (Killed Mutants / Total Mutants) × 100
   ```

### Common Mutation Types

| Type | Example | Description |
|------|---------|-------------|
| Arithmetic | `x + y` → `x - y` | Change operator |
| Boolean | `a and b` → `a or b` | Change logic |
| Comparison | `x < y` → `x <= y` | Change comparison |
| Conditional | `if condition:` → `if not condition:` | Negate condition |
| Statement | `return x` → `return None` | Remove statement |

---

## Why Mutation Testing?

### Problems with Traditional Coverage Metrics

**Code Coverage:**
```python
def is_admin(user):
    return True  # Bug: always returns True

# Test:
assert is_admin(user)  # 100% coverage, but bug not detected!
```

**Mutation Testing:**
- Changes `return True` to `return False`
- Test still passes → **Surviving mutant detected** → **Test gap found**

### Benefits

1. **Find Test Gaps**: Surviving mutants indicate missing tests
2. **Improve Test Quality**: Forces you to write better assertions
3. **Validate Edge Cases**: Mutations often test boundary conditions
4. **Measure Test Effectiveness**: More accurate than code coverage

### When to Use

- **Critical Code**: Financial operations, security, data validation
- **High Risk**: Authentication, authorization, payment processing
- **Complex Logic**: Algorithms, state machines, workflows
- **Refactoring**: Before refactoring, ensure tests are solid

---

## Quick Start

### Installation

```bash
# Install mutmut
pip install mutmut>=2.4.0

# Verify installation
mutmut --version
```

### Basic Usage

```bash
# Run mutation tests for a single module
mutmut run --paths-to-mutate core/security.py --runner "pytest tests/"

# Generate HTML report
mutmut html

# View results
mutmut results
```

### Using the Run Scripts

```bash
# Run specific target
python tests/mutation_tests/scripts/run_mutation_tests.py --target priority_p0_financial

# Run all targets
python tests/mutation_tests/scripts/run_mutation_tests.py --all

# Quick smoke test (fewer mutations)
python tests/mutation_tests/scripts/run_mutation_tests.py --all --quick

# Generate report
python tests/mutation_tests/scripts/generate_mutation_report.py
```

---

## Configuration

### Target Configuration (`TARGETS.ini`)

```ini
[priority_p0_financial]
modules = [
    "core/financial_ops_engine.py",
    "core/financial_forensics.py"
]
mutation_score_threshold = 95.0
description = "Financial operations"
risk_level = "CRITICAL"
```

**Parameters:**
- `modules`: List of Python files to mutate
- `mutation_score_threshold`: Minimum required score (0-100)
- `description`: Human-readable description
- `risk_level`: CRITICAL, HIGH, MEDIUM, or LOW

### Mutmut Configuration (`mutmut.ini`)

Already created in `backend/tests/mutation_tests/config/mutmut.ini` with:
- Test runner command
- Paths to mutate/exclude
- Mutation types
- Worker settings

---

## Running Mutation Tests

### Phase 5 Workflow

#### 1. Initial Run

```bash
# Run mutation tests for P0 (Financial & Security)
python tests/mutation_tests/scripts/run_mutation_tests.py --target priority_p0_financial
```

**Expected Output:**
```
============================================================
Running mutation tests for: priority_p0_financial
Modules: core/financial_ops_engine.py, core/financial_forensics.py
Score threshold: 95.0%
============================================================

- Mutation testing started ...
- 127 mutants generated
- 121 mutants killed
- 6 mutants survived
- 0 mutants timed out

Mutation Score: 95.28%
Threshold: 95.0%

============================================================
✅ PASSED: Score 95.28% >= 95.0%
============================================================
```

#### 2. Analyze Surviving Mutants

If score is below threshold:
```bash
# View surviving mutants
mutmut results | grep SURVIVED

# Apply surviving mutant for inspection
mutmut apply <mutant_id>

# View mutated code
cat core/financial_ops_engine.py | grep -A 10 -B 10 "MUTATION"

# Write test to kill mutant
# Add property test, re-run
```

#### 3. Generate Report

```bash
# Generate HTML report
python tests/mutation_tests/scripts/generate_mutation_report.py

# View report
open tests/mutation_tests/reports/mutation_report.html
```

#### 4. CI/CD Integration

**Weekly Workflow (`.github/workflows/mutation-tests.yml`)**:
- Runs every Sunday at 3 AM UTC
- Tests all priority targets
- Fails if any target below threshold
- Generates report artifact

---

## Interpreting Results

### Mutation Score Categories

| Score | Quality | Action |
|-------|---------|--------|
| 95-100% | Excellent | ✅ No action needed |
| 90-94% | Good | ⚠️ Review surviving mutants |
| 80-89% | Fair | ⚠️ Add tests to kill survivors |
| <80% | Poor | ❌ Significant test gaps |

### Surviving Mutant Analysis

**Example:**
```
⚠️  SURVIVED: core/security.py:42 (ARITHMETIC)
---
Original:
    if attempts >= 3:
        block_user()

Mutated:
    if attempts > 3:  # Changed: >= to >
        block_user()
```

**Why Survived?**
- Tests only check `attempts == 3` or `attempts > 3`
- No test for `attempts == 4` (boundary condition)

**Fix:**
```python
# Add property test
@given(attempts=st.integers(min_value=0, max_value=10))
def test_block_after_3_attempts(attempts):
    if attempts >= 3:
        assert user.is_blocked
```

### Common Test Gaps

1. **Boundary Conditions**: `x > 3` vs `x >= 3`
2. **Null/None Handling**: Missing null checks
3. **Empty Collections**: Empty list/dict handling
4. **Off-by-One**: Loop boundaries, array indices
5. **Logic Inversions**: `and` vs `or`, `not` missing

---

## Quality Gates

### Score Thresholds by Priority

| Priority | Target | Rationale |
|----------|--------|-----------|
| P0: Financial & Security | >95% | Highest risk (cost, security) |
| P1: Core Business Logic | >90% | High risk (data integrity) |
| P2: API & Tools | >85% | Medium risk (UX, functionality) |
| P3: Other | >80% | Lower risk (nice-to-have) |

### CI/CD Gates

**Weekly Mutation Test** (`.github/workflows/mutation-tests.yml`):
```yaml
name: Mutation Tests
on:
  schedule:
    - cron: '0 3 * * 0'  # Sunday 3 AM UTC

jobs:
  mutation-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run mutation tests
        run: |
          python tests/mutation_tests/scripts/run_mutation_tests.py --all

      - name: Upload mutation report
        uses: actions/upload-artifact@v4
        with:
          name: mutation-report
          path: html/
```

### Failing the Build

If mutation score below threshold:
```yaml
- name: Check mutation score
  run: |
    SCORE=$(mutmut results | grep "Mutation score" | awk '{print $3}' | sed 's/%//')

    if (( $(echo "$SCORE < 95" | bc -l) )); then
      echo "❌ Mutation score $SCORE% below threshold 95%"
      exit 1
    fi
```

---

## Best Practices

### 1. Start Small

Don't try to mutate everything at once. Start with:
- Critical paths (authentication, payments)
- High-risk code (security, financial)
- Recently changed code (regression testing)

### 2. Use Property-Based Tests

Property-based tests (Hypothesis) are great for killing mutants:
- Generate many random inputs
- Test edge cases automatically
- Find boundary conditions

```python
@given(x=st.integers(min_value=0, max_value=100))
def test_boundary(x):
    # Will test 0, 1, 2, ..., 100
    # Likely to catch off-by-one mutations
    assert is_valid(x)
```

### 3. Fix Surviving Mutants Immediately

When you find a surviving mutant:
1. ✅ Write a regression test **before** fixing code
2. ✅ Verify test fails on mutant
3. ✅ Fix test (if test bug) or code (if code bug)
4. ✅ Verify test now kills mutant
5. ✅ Commit with detailed message

### 4. Review Test Assertions

Surviving mutants often indicate weak assertions:
```python
# Weak assertion (won't catch mutations)
def test_add():
    result = add(2, 3)
    assert result is not None  # ❌ Too weak

# Strong assertion (will catch mutations)
def test_add():
    result = add(2, 3)
    assert result == 5  # ✅ Specific assertion
```

### 5. Balance Mutation Types

Not all mutations are equally useful:
- **High Value**: Arithmetic, boolean, comparison (business logic)
- **Medium Value**: Conditional, statement (control flow)
- **Low Value**: String literals, comments (cosmetic)

Focus on high-value mutations first.

### 6. Consider Performance

Mutation testing can be slow:
- **1000 mutants** × **10 min test suite** = **10,000 min** ≈ **7 days**

**Optimizations:**
- Use parallel workers (`mutmut run --workers=auto`)
- Reduce Hypothesis examples (`hypothesis_max_examples = 50`)
- Test only critical paths (P0, P1)
- Use incremental mutation testing (only new code)

### 7. Set Realistic Targets

100% mutation score is rarely practical:
- **90-95%**: Good for critical code
- **80-85%**: Acceptable for most code
- **<80%**: Needs improvement

Focus on critical code quality over perfect scores.

---

## Troubleshooting

### Issue: "ImportError: No module named 'mutmut'"

**Solution:**
```bash
pip install mutmut>=2.4.0
```

### Issue: "Mutations too slow"

**Solution:**
```bash
# Use quick mode (fewer mutations)
python run_mutation_tests.py --quick

# Limit number of mutants
mutmut run --max-mutations 100

# Use parallel workers
mutmut run --workers 4
```

### Issue: "Too many surviving mutants"

**Solution:**
1. Run with verbose output: `mutmut run --verbose`
2. Identify patterns in surviving mutants
3. Add property-based tests for those patterns
4. Re-run mutation testing

### Issue: "Mutant causes test to hang"

**Solution:**
```bash
# Kill process
pkill -9 mutmut

# Use timeout
mutmut run --timeout=30  # 30 second timeout per mutant
```

---

## Resources

- [Mutmut Documentation](https://mutmut.readthedocs.io/)
- [Mutation Testing on Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing)
- [Property-Based Testing with Hypothesis](https://hypothesis.readthedocs.io/)
- [Testing Guide](../TESTING_GUIDE.md)

---

**Last Updated:** February 7, 2026
**Version:** 1.0.0

# Backend Coverage Guide

## CRITICAL: Use Actual Line Coverage, Not Estimates

**READ THIS FIRST:** This guide explains how to measure **actual line coverage** using coverage.py execution data. Do NOT use service-level estimates (aggregated boolean coverage per service), which create false confidence.

**The Pitfall:** In Phases 160-162, service-level estimates showed 74.6% coverage for episode services, but actual line coverage was 8.50% — a 66.1 percentage point gap that masked thousands of untested lines.

**The Fix:** Always use `coverage.py` JSON output with actual line execution counts:
- **CORRECT:** `line_covered / num_statements` from coverage.json
- **WRONG:** Aggregated service-level percentages

See `backend/docs/METHODOLOGY.md` for detailed explanation of the pitfall and correct methodology.

---

## Quick Start

### Generate Coverage Report

```bash
# From backend directory
pytest --cov=backend --cov-branch --cov-report=json --cov-report=term-missing --cov-report=html
```

**Or use the baseline script:**
```bash
cd backend
python tests/scripts/generate_baseline_coverage_report.py
```

**Output files:**
- `coverage.json` - Machine-readable coverage data (for parsing)
- `htmlcov/index.html` - Human-readable HTML report (for inspection)
- Terminal output - Quick summary with missing lines

### Parse Coverage Metrics

```python
import json

with open('coverage.json') as f:
    cov = json.load(f)

# Actual line coverage (NOT service-level estimates)
totals = cov['totals']
line_covered = totals['line_covered']  # or totals['covered_lines']
num_statements = totals['num_statements']
line_coverage_pct = (line_covered / num_statements) * 100

# Branch coverage (if --cov-branch enabled)
branch_covered = totals['branch_covered']  # or totals['covered_branches']
num_branches = totals['num_branches']
branch_coverage_pct = (branch_covered / num_branches) * 100 if num_branches > 0 else 0

print(f"Line Coverage: {line_coverage_pct:.2f}% ({line_covered}/{num_statements})")
print(f"Branch Coverage: {branch_coverage_pct:.2f}% ({branch_covered}/{num_branches})")
```

### Quality Gate Enforcement

```bash
# Check if coverage meets threshold (default: 70%)
python tests/scripts/backend_coverage_gate.py

# With baseline comparison
python tests/scripts/backend_coverage_gate.py --baseline tests/coverage_reports/backend_163_baseline.json

# Override threshold (emergency)
COVERAGE_THRESHOLD_OVERRIDE=70 python tests/scripts/backend_coverage_gate.py

# Emergency bypass with justification
BYPASS_REASON="Security fix: Critical auth vulnerability" python tests/scripts/backend_coverage_gate.py
```

---

## Coverage.py Configuration

### pytest.ini Setup

`backend/pytest.ini` is already configured for coverage:

```ini
[coverage:run]
source = backend
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */migrations/*
branch = true

[coverage:report]
precision = 2
show_missing = True
fail_under = 80
fail_under_branch = 70
```

**Key settings:**
- `source = backend` - Measure coverage for backend module
- `branch = true` - Enable branch coverage
- `fail_under = 80` - Target 80% line coverage
- `fail_under_branch = 70` - Target 70% branch coverage

### Coverage Flags

| Flag | Purpose |
|------|---------|
| `--cov=backend` | Measure coverage for backend module |
| `--cov-branch` | Enable branch coverage measurement |
| `--cov-report=json` | Generate coverage.json for parsing |
| `--cov-report=term-missing` | Show missing lines in terminal |
| `--cov-report=html` | Generate HTML report at htmlcov/index.html |

---

## Coverage.json Structure

### Valid Format

```json
{
  "meta": {
    "format": 3,
    "version": "7.13.4",
    "timestamp": "2026-03-11T12:00:00.000000",
    "branch_coverage": true
  },
  "files": {
    "core/agent_governance_service.py": {
      "summary": {
        "covered": 125,
        "num_statements": 450,
        "covered_lines": 125,
        "num_branches": 50,
        "covered_branches": 30
      },
      "executed_lines": [1, 2, 3, 5, 10, 15, 20, ...],
      "missing_lines": [4, 6, 7, 8, ...]
    }
  },
  "totals": {
    "covered": 6179,
    "num_statements": 72727,
    "covered_lines": 6179,
    "num_branches": 12500,
    "covered_branches": 8500,
    "percent_covered": 8.5
  }
}
```

### Critical Validation Checks

**Before trusting coverage metrics, verify:**

1. **`files` array exists:**
   ```python
   assert 'files' in cov, "coverage.json missing 'files' array - service-level aggregation detected"
   ```

2. **Each file has `summary`:**
   ```python
   for file_path, file_data in cov['files'].items():
       assert 'summary' in file_data, f"{file_path} missing summary"
       assert 'num_statements' in file_data['summary'], f"{file_path} missing num_statements"
   ```

3. **`totals` has actual metrics:**
   ```python
   assert 'num_statements' in cov['totals'], "totals missing num_statements"
   assert 'line_covered' in cov['totals'] or 'covered_lines' in cov['totals'], "totals missing line coverage"
   ```

**If any check fails:** Re-run pytest with `--cov=backend` (not `--cov=backend/core`)

---

## Coverage Measurement Workflow

### 1. Baseline Generation (Phase 163)

**Purpose:** Establish initial baseline using actual line coverage

```bash
cd backend
python tests/scripts/generate_baseline_coverage_report.py
```

**Output:**
- `tests/coverage_reports/backend_163_baseline.json` - Baseline coverage data
- `tests/coverage_reports/backend_163_baseline.md` - Human-readable baseline report

**Validation:**
- Script validates coverage.json has `files` array (not just totals)
- Handles multiple coverage.py versions (different field names)
- Prevents service-level aggregation errors

### 2. Daily Coverage Checks

**Quick check:**
```bash
pytest --cov=backend --cov-branch --cov-report=term-missing
```

**Detailed inspection:**
```bash
pytest --cov=backend --cov-branch --cov-report=html
open htmlcov/index.html
```

### 3. CI/CD Quality Gate

**Enforce threshold in PRs:**
```yaml
# .github/workflows/ci.yml
- name: Coverage Gate
  run: |
    cd backend
    python tests/scripts/backend_coverage_gate.py --phase phase_1
```

**Exit codes:**
- `0`: Pass (coverage >= threshold)
- `1`: Fail (coverage < threshold)
- `2`: Error (invalid configuration)

### 4. Emergency Bypass

**For critical security fixes:**
```bash
export BYPASS_REASON="Security fix: Critical auth vulnerability in production"
python tests/scripts/backend_coverage_gate.py --bypass-justification "$BYPASS_REASON"
```

**Requirements:**
- Justification >= 20 characters
- Logged to audit trail: `tests/coverage_reports/metrics/bypass_log.json`
- Frequency-monitored (>3 bypasses in 30 days triggers alert)

---

## Progressive Threshold Strategy

Phase 163 implements a **progressive rollout** to reach 80% coverage:

### Phase 1: Minimum Enforcement (70%)
- **Target:** 70% line coverage
- **Duration:** Until gap closure
- **Enforcement:** CI/CD gate blocks PRs below 70%
- **Use case:** Initial enforcement, prevent regression

### Phase 2: Interim Target (75%)
- **Target:** 75% line coverage
- **Duration:** Until gap closure
- **Enforcement:** CI/CD gate blocks PRs below 75%
- **Use case:** Accelerate improvement

### Phase 3: Final Target (80%)
- **Target:** 80% line coverage
- **Duration:** Ongoing (maintenance)
- **Enforcement:** CI/CD gate blocks PRs below 80%
- **Use case:** Production-ready coverage

### New Code Requirement
- **All new code:** 80% coverage regardless of phase
- **Rationale:** Prevent technical debt accumulation

### Setting Phase

```bash
# Environment variable
export COVERAGE_PHASE=phase_1  # or phase_2, phase_3

# CLI argument
python tests/scripts/backend_coverage_gate.py --phase phase_2
```

---

## Troubleshooting

### Why Coverage Seems Higher Than It Is

**Symptom:** Coverage report shows 70%+ but test suite feels incomplete

**Cause:** Service-level aggregation (estimating coverage per service instead of measuring actual lines)

**Diagnosis:**
```bash
# Check if coverage.json has files array
python -c "import json; cov = json.load(open('coverage.json')); print('Has files:', 'files' in cov)"
```

**If "Has files: False":**
- You're using service-level aggregation
- Re-run pytest with `--cov=backend` (not `--cov=backend/core`)
- Ensure coverage target is the entire backend module

**If "Has files: True" but coverage still seems high:**
- Check for `# pragma: no cover` exclusions
- Review HTML report: `htmlcov/index.html`
- Identify files with 100% coverage but few tests

### Coverage.json Missing or Empty

**Symptom:** `coverage.json` doesn't exist or is 0 bytes

**Diagnosis:**
```bash
# Check pytest coverage flags
pytest --cov=backend --cov-report=json

# Check coverage.json location
ls -la coverage.json tests/coverage_reports/metrics/coverage.json
```

**Solutions:**
1. Add `--cov-report=json` to pytest command
2. Ensure pytest-cov is installed: `pip install pytest pytest-cov`
3. Check pytest.ini `[coverage:run]` configuration
4. Run from backend directory (not project root)

### Branch Coverage Missing

**Symptom:** coverage.json has no `branch_covered` or `num_branches`

**Diagnosis:**
```bash
# Check if --cov-branch flag is set
grep -E "cov-branch" pytest.ini .github/workflows/ci.yml
```

**Solutions:**
1. Add `--cov-branch` to pytest command
2. Add `branch = true` to pytest.ini `[coverage:run]` section (already done)
3. Verify pytest-cov version >= 5.0

### Quality Gate Fails Unexpectedly

**Symptom:** Coverage gate fails despite coverage.json existing

**Diagnosis:**
```bash
# Check coverage.json structure
python -c "import json; cov = json.load(open('coverage.json')); print('Keys:', list(cov.keys()))"
```

**Common issues:**
- Missing `totals` section (incomplete coverage.py run)
- Missing `num_statements` in totals (service-level aggregation)
- Wrong coverage target (e.g., `--cov=core` instead of `--cov=backend`)

**Solution:**
```bash
# Re-run with correct flags
cd backend
pytest --cov=backend --cov-branch --cov-report=json
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  pull_request:
    branches: [main, develop]

jobs:
  backend-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        working-directory: ./backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests with coverage
        working-directory: ./backend
        run: |
          pytest --cov=backend --cov-branch --cov-report=json --cov-report=term-missing

      - name: Coverage gate
        working-directory: ./backend
        env:
          COVERAGE_PHASE: phase_1
        run: |
          python tests/scripts/backend_coverage_gate.py

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: backend/htmlcov/
```

### Emergency Bypass in CI/CD

```yaml
# Allow bypass for critical fixes
- name: Coverage gate (with bypass)
  working-directory: ./backend
  env:
    BYPASS_REASON: ${{ github.event.pull_request.body }}
  run: |
    # Extract bypass reason from PR body if labeled "emergency-bypass"
    if [[ "${{ contains(github.event.pull_request.labels.*.name, 'emergency-bypass') }}" == "true" ]]; then
      python tests/scripts/backend_coverage_gate.py --bypass-justification "$BYPASS_REASON"
    else
      python tests/scripts/backend_coverage_gate.py
    fi
```

---

## Best Practices

### 1. Always Use Actual Line Coverage
- **NEVER** use service-level estimates
- **ALWAYS** parse coverage.json for `line_covered / num_statements`
- **ALWAYS** validate `files` array exists (not just totals)

### 2. Enable Branch Coverage
- **ALWAYS** use `--cov-branch` flag
- **TARGET:** 70% branch coverage (lower than line coverage)
- **REASON:** Branch coverage catches conditionals that line coverage misses

### 3. Generate Multiple Reports
- **JSON:** For automated parsing (coverage.json)
- **Terminal:** For quick checks (`--cov-report=term-missing`)
- **HTML:** For detailed inspection (`htmlcov/index.html`)

### 4. Use Progressive Thresholds
- **Phase 1 (70%):** Minimum enforcement
- **Phase 2 (75%):** Interim target
- **Phase 3 (80%):** Final target
- **New code:** 80% regardless of phase

### 5. Emergency Bypass as Last Resort
- **ONLY** for security fixes, critical hotfixes
- **MUST** include justification (>= 20 characters)
- **ALWAYS** logged to audit trail
- **REVIEWED** monthly for abuse prevention

### 6. Baseline Before Improving
- **ALWAYS** establish baseline before adding tests
- **USE** Phase 161 baseline (8.50% coverage)
- **COMPARE** each phase's progress against baseline
- **TRACK** percentage point improvements

---

## References

**Scripts:**
- `backend/tests/scripts/generate_baseline_coverage_report.py` - Baseline generation (463 lines)
- `backend/tests/scripts/backend_coverage_gate.py` - Quality gate enforcement (456 lines)
- `backend/tests/scripts/emergency_coverage_bypass.py` - Emergency bypass tracking
- `backend/tests/scripts/progressive_coverage_gate.py` - Progressive rollout orchestration

**Documentation:**
- `backend/docs/METHODOLOGY.md` - Detailed methodology explanation (pitfall, correct approach)
- `backend/tests/coverage_reports/backend_163_baseline.md` - Phase 163 baseline report
- `.planning/phases/163-coverage-baseline-infrastructure/163-VERIFICATION.md` - Phase 163 verification

**Configuration:**
- `backend/pytest.ini` - Pytest and coverage configuration
- `.github/workflows/ci.yml` - CI/CD pipeline integration

**Tools:**
- [coverage.py](https://coverage.readthedocs.io/) - Coverage measurement tool
- [pytest-cov](https://pytest-cov.readthedocs.io/) - Pytest plugin for coverage.py

---

**Document Version:** 2.0
**Last Updated:** 2026-03-11
**Author:** Phase 163 Coverage Baseline Infrastructure
**Status:** PRODUCTION - Updated with correct actual line coverage methodology

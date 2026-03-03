# Backend Test Coverage Measurement Methodology

**Purpose:** Ensure consistent, reproducible coverage measurements across all phases of the Atom test coverage initiative.

**Last Updated:** 2026-03-03 (Phase 127-07)

---

## Standard Coverage Measurement Command

```bash
cd backend
pytest tests/ \
  --cov=core \
  --cov=api \
  --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json \
  --cov-report=html:tests/coverage_reports/html \
  --cov-report=term-missing:skip-covered
```

**Explanation:**
- `--cov=core --cov=api --cov=tools`: Measure only production code (exclude tests/)
- `--cov-report=json`: Machine-readable output for trend analysis
- `--cov-report=html`: Human-readable HTML report for detailed investigation
- `--cov-report=term-missing:skip-covered`: Show only missing lines in terminal

**Alternative (single source directory):**
```bash
pytest tests/ --cov=backend --cov-report=json:tests/coverage_reports/metrics/coverage.json
```

---

## Scope Definition

### Include (Production Code)
- `core/` - Core services (governance, LLM, episodic memory, etc.)
- `api/` - API routes (FastAPI routers)
- `tools/` - Agent tools (canvas, browser, device, etc.)

### Exclude (Non-Production Code)
- `tests/` - Test files themselves
- `__pycache__/` - Python bytecode cache
- `migrations/` - Database migrations (Alembic)
- `venv/`, `virtualenv/`, `.venv/` - Virtual environments
- `env/` - Environment directories

**Rationale:** Test coverage should measure production code quality, not test code itself. Including test files in coverage measurements inflates percentages without providing meaningful quality signals.

---

## Baseline Tracking

### Phase Baseline Protocol

Each phase **must** create a baseline measurement before adding new tests:

```bash
# Before adding any new tests for the phase
pytest tests/ \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/phase_{NN}_baseline.json

# After completing all phase tests
pytest tests/ \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/phase_{NN}_final_coverage.json
```

**Example (Phase 127):**
- Baseline: `phase_127_baseline.json` (26.15% - starting point)
- Final: `phase_127_final_coverage.json` (measured after all tests added)

### Baseline vs. Final

- **Baseline**: Coverage at the START of a phase (before new tests)
- **Final**: Coverage at the END of a phase (after new tests added)
- **Improvement** = Final - Baseline (percentage points gained)

---

## Gap Calculation

### Formulas

```python
# Gap to target
gap = target_percentage - baseline_percentage

# Example: Phase 127
baseline = 26.15
target = 80.0
gap = 80.0 - 26.15  # 53.85 percentage points

# Improvement achieved
improvement = final_percentage - baseline_percentage

# Remaining work
remaining = target_percentage - final_percentage
```

### Example Calculation

```
Phase 127 Gap Closure:
  Baseline: 26.15%
  Target: 80.0%
  Gap: 53.85 percentage points
  Final: TBD (after adding tests)
  Improvement: final - 26.15
  Remaining: 80.0 - final
```

---

## Reporting Format

### JSON Metadata

Each coverage report should include metadata for tracking:

```json
{
  "phase": "127",
  "baseline_percentage": 26.15,
  "final_percentage": 26.15,
  "target_percentage": 80.0,
  "gap_percentage_points": 53.85,
  "improvement_percentage_points": 0.0,
  "measurement_scope": "core/, api/, tools/",
  "files_measured": 528,
  "timestamp": "2026-03-03T08:00:44.803413Z",
  "command": "pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json:..."
}
```

### Phase Summary Template

```markdown
## Phase {NN}: {Phase Name} Coverage Results

**Measurement Scope:** core/, api/, tools/ (production code only)

**Baseline:** {XX.XX}%
**Final:** {YY.YY}%
**Target:** 80.0%
**Gap:** {ZZ.ZZ} percentage points

**Improvement:** +{AA.AA} percentage points
**Remaining:** {BB.BB} percentage points to target

**Files Measured:** {N} production files
**Tests Added:** {M} tests
```

---

## pytest.ini Configuration

The `pytest.ini` file defines coverage measurement defaults:

```ini
[coverage:run]
source = backend
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */migrations/*
    */venv/*
    */virtualenv/*
    .venv/*
    env/*
branch = true

[coverage:report]
precision = 2
show_missing = True
skip_covered = false
fail_under = 80
```

**Key Settings:**
- `source = backend`: Default source directory (can override with `--cov`)
- `omit`: Files to exclude from measurement
- `branch = true`: Enable branch coverage (more rigorous than line coverage)
- `fail_under = 80`: CI fails if coverage drops below 80%

---

## Common Mistakes

### Mistake 1: Including Test Files

**Wrong:**
```bash
pytest tests/ --cov=backend --cov=tests  # Includes test code
```

**Correct:**
```bash
pytest tests/ --cov=core --cov=api --cov=tools  # Production code only
```

### Mistake 2: Single-File Measurements

**Wrong:**
```bash
pytest tests/test_agent_governance.py --cov=core/agent_governance_service.py
# This gives 74.55% for ONE FILE, not overall backend
```

**Correct:**
```bash
pytest tests/ --cov=core --cov=api --cov=tools
# This gives 26.15% for ALL production files (528 files)
```

**Lesson:** Phase 127-07 investigation revealed that 74.55% was for `agent_governance_service.py` only, not the entire backend. Always measure the full production codebase.

### Mistake 3: Not Creating Baselines

**Wrong:**
```bash
# Add tests immediately, then measure
pytest tests/ --cov=core --cov=api --cov=tools
# Can't tell how much improvement was achieved
```

**Correct:**
```bash
# Measure baseline first
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json:phase_NN_baseline.json

# Add tests

# Measure final
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json:phase_NN_final.json

# Compare: final - baseline = improvement
```

---

## Verification

### After Each Phase

1. **Baseline exists**: `phase_{NN}_baseline.json`
2. **Final exists**: `phase_{NN}_final_coverage.json`
3. **Improvement calculated**: `final - baseline > 0`
4. **Scope consistent**: Same 528 files (core/, api/, tools/)

### Quick Verification Command

```bash
python3 -c "
import json
baseline = json.load(open('tests/coverage_reports/metrics/phase_127_baseline.json'))
final = json.load(open('tests/coverage_reports/metrics/phase_127_final_coverage.json'))
print(f\"Baseline: {baseline['totals']['percent_covered']:.2f}%\")
print(f\"Final: {final['totals']['percent_covered']:.2f}%\")
print(f\"Improvement: {final['totals']['percent_covered'] - baseline['totals']['percent_covered']:.2f} pp\")
print(f\"Files: {len(final['files'])}\")
"
```

---

## References

- **pytest-cov Documentation:** https://pytest-cov.readthedocs.io/
- **coverage.py Documentation:** https://coverage.readthedocs.io/
- **Phase 127-07 Investigation:** `backend/tests/coverage_reports/metrics/phase_127_measurement_investigation.json`

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
| 2026-03-03 | 127-07 | Initial methodology document created. Clarified scope (core/, api/, tools/) after investigation revealed 74.55% was single-file measurement. |

---
phase: "292"
plan: "01"
subsystem: "coverage-infrastructure"
tags: ["baseline", "coverage", "measurement", "validation"]
requires: []
provides: ["backend-coverage-baseline", "frontend-coverage-baseline", "baseline-validation-methodology"]
affects: ["backend-tests", "frontend-tests"]
key-files:
  created:
    - "backend/tests/coverage_reports/metrics/phase_292_backend_baseline.json"
    - "backend/tests/coverage_reports/metrics/BASELINE_VALIDATION.md"
    - "backend/tests/scripts/validate_coverage_structure.py"
    - "backend/tests/coverage_reports/trends/2026-04-24_coverage_trend.json"
    - "frontend-nextjs/coverage/phase_292_frontend_baseline.json"
    - "frontend-nextjs/coverage/phase_292_frontend_summary.json"
  modified:
    - "backend/tests/coverage_reports/metrics/coverage.json"
    - "backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json"
    - "backend/tests/conftest.py"
    - "backend/core/active_intervention_service.py"
tech-stack:
  added: []
  patterns:
    - "Structural validation script for coverage JSON files"
    - "Systematic ignore strategy for collection-error test files"
metrics:
  duration_minutes: ~55
  tasks_total: 3
  tasks_completed: 3
  commit_count: 3
  files_created: 6
  files_modified: 4
coverage:
  backend_overall: "36.72%"
  backend_files: 693
  backend_api: "27.72%"
  backend_core: "38.47%"
  backend_tools: "44.06%"
  frontend_lines: "15.14%"
  frontend_statements: "15.55%"
  frontend_functions: "10.56%"
  frontend_branches: "8.6%"
  frontend_files: 707
key-decisions:
  - "17 collection-error test files excluded via --ignore (Rule 3: missing dependencies)"
  - "Soak and chaos tests excluded via -m marker (15-30 min tests impractical for baseline)"
  - "Frontend phase_292 baseline files force-added despite .gitignore (coverage/ pattern)"
  - "Backend coverage-trend-v5.0 updated to 36.72% from 21.67% previous baseline"
  - "Combined xdist worker .coverage files for backend completeness"
---

# Phase 292 Plan 01: Coverage Baseline Measurement Summary

**One-liner:** Measured authoritative backend (36.72%) and frontend (15.14%) coverage baselines for Phase 292 with structural validation, trend recording, and deviation-documented methodology.

## Context

This plan established the zero-point coverage baselines for Phase 292's coverage improvement work. Both backend (Python/pytest-cov) and frontend (Jest/Istanbul) were measured with 1,503 failing frontend tests and 17 excluded backend test files. The fresh backend measurement of 36.72% significantly exceeds the historical v5.0 reference of 21.67% due to substantial test additions in intervening phases.

## Tasks Executed

### Task 1: Backend Coverage Baseline (36.72%)

**Command:** `pytest tests/ -n auto --dist loadscope -m "not soak and not chaos" --cov core --cov api --cov tools`

**Results:**
- Overall: **36.72%** (33,332 / 90,770 lines)
- Module breakdown: api: 27.72%, core: 38.47%, tools: 44.06%
- 693 production files measured

**Key actions:**
- Ignored 17 test files with collection errors (import failures, missing modules)
- Excluded soak/chaos tests (15-30 min duration)
- Excluded root-level sub-project test directories (consolidated, integrations, accounting, etc.)
- Combined xdist worker .coverage files into final report
- Saved baseline as `phase_292_backend_baseline.json`
- Created `validate_coverage_structure.py` structural validator
- Recorded in coverage trend tracker (v5.0): 36.72%

**Deviation 1:** Fixed `tests/conftest.py:1703` -- `pytest_exception_interact` hook crashed on collection-error nodes (accessing `node.obj` on nodes without the attribute). Wrapped in try/except. Without this, pytest aborted at first collection error instead of continuing.

**Deviation 2:** Fixed `core/active_intervention_service.py:7` -- nested try block had wrong indentation (inner `try:` at same level as outer), making the file unparseable by coverage.py. Coverage JSON generation failed until this was fixed.

### Task 2: Frontend Coverage Baseline (15.14%)

**Command:** `COVERAGE_PHASE=phase_1 npx jest --coverage`

**Results:**
- Line coverage: **15.14%**
- Statement coverage: 15.55%
- Function coverage: 10.56%
- Branch coverage: 8.60%
- 707 production files measured
- 5,197 total tests: 3,680 passed, 1,502 failed, 15 todo (70.8% pass rate)

**Key actions:**
- Saved baseline as `phase_292_frontend_baseline.json` (coverage-final.json copy)
- Saved summary as `phase_292_frontend_summary.json` (coverage-summary.json copy)
- Files force-added despite `coverage/` in .gitignore

### Task 3: Baseline Methodology Validation Document

Created `BASELINE_VALIDATION.md` covering:
1. Exact measurement commands for reproducibility
2. Coverage percentages with reference deltas
3. Full catalog of 17 ignored test files and their import errors
4. All deviations (conftest crash fix, indentation syntax fix, soak/chaos exclusion)
5. Validation script output (both backend and frontend)
6. Source-of-truth statement identifying the authoritative baseline files

## Verification

### Backend Validation

```python
python backend/tests/scripts/validate_coverage_structure.py \
  backend/tests/coverage_reports/metrics/phase_292_backend_baseline.json
# => VALIDATION PASSED
# => Overall coverage: 36.72%
# => Files measured: 693
```

### Frontend Validation

```python
# coverage-final.json: VALIDATION PASSED (707 files, all fields present)
# coverage-summary.json: VALIDATION PASSED (total.lines/statements/functions/branches all present)
```

### Trend Tracker

```bash
# coverage_trend_v5.0.json updated with Phase 292 snapshot
# Daily snapshot saved to trends/2026-04-24_coverage_trend.json
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] conftest pytest_exception_interact crash**
- **Found during:** Task 1
- **Issue:** The `pytest_exception_interact` hook in `tests/conftest.py:1703` accessed `node.obj` on Collector nodes (collection errors), which don't have an `obj` attribute. This caused cascading INTERNALERROR that aborted test collection.
- **Fix:** Wrapped `node.obj` access in try/except to skip bug filing for collection-error nodes.
- **Files modified:** `backend/tests/conftest.py`
- **Commit:** `7c44022d4`

**2. [Rule 1 - Bug] active_intervention_service.py try-block indentation error**
- **Found during:** Task 1 (coverage JSON generation step)
- **Issue:** Nested `try:` block at line 7 had wrong indentation (inner `try` at same level as outer `try`), causing `coverage json` to fail parsing the file as Python source.
- **Fix:** Indented the inner try block and its body correctly.
- **Files modified:** `backend/core/active_intervention_service.py`
- **Commit:** `7c44022d4`

**3. [Rule 3 - Blocking] 17 test files with collection errors**
- **Found during:** Task 1
- **Issue:** Multiple test files had missing dependencies (flask, core.llm.llm_service, etc.) or import failures, preventing pytest collection.
- **Fix:** Added `--ignore` flags for all failing files plus root-level sub-project directories.
- **Commit:** `7c44022d4`

### Excluded Tests

| Exclusion                | Reason                                   |
|--------------------------|------------------------------------------|
| 17 files (collection err)| Missing dependencies, broken imports     |
| Soak tests (2 files)     | 15-30 minute duration                    |
| Chaos experiments        | Destructive/slow tests                   |
| Root sub-project dirs    | Not part of core/api/tools test suite    |

### Scope Boundary

Pre-existing warnings (91+ SyntaxWarnings for escape sequences, apscheduler logging errors) were logged to `deferred-items.md` but not fixed.

## Known Stubs

None. All baseline files contain real measured data.

## Threat Flags

No new security-relevant surface introduced. The conftest fix reduces crash surface but does not change authentication, authorization, or data access patterns.

## Plans Referenced

- Phase 292, Plan 01: This plan (baseline measurement)
- Phase 292, Plan 02+: Will be created from this baseline

## Self-Check: PASSED

All 7 created files verified to exist on disk.
All 3 commits verified in git log (`7c44022d4`, `c25474f62`, `2acf8ec8f`).
Backend coverage structural validation passes (36.72%, 693 files).

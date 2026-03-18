---
phase: 205-coverage-quality-push
plan: 03
subsystem: pytest-collection-configuration
tags: [pytest, collection-errors, test-configuration, coverage-quality]

# Dependency graph
requires:
  - phase: 205-coverage-quality-push
    plan: 02
    provides: Research findings on collection errors
provides:
  - Zero collection errors (5 → 0)
  - pytest_plugins moved to root conftest (pytest 7.4+ compliant)
  - 53 documented ignore patterns in pytest.ini
  - Clean collection baseline for accurate coverage measurement
affects: [pytest-configuration, test-collection, coverage-measurement]

# Tech tracking
tech-stack:
  added: [root-conftest.py, pytest-7.4-compliance]
  patterns:
    - "pytest_plugins in top-level conftest only (pytest 7.4+ requirement)"
    - "Duplicate test file detection and ignore patterns"
    - "Documented ignore patterns with inline comments"

key-files:
  created:
    - conftest.py (root conftest with pytest_plugins)
  modified:
    - backend/conftest.py (pytest_plugins commented out)
    - backend/pytest.ini (6 new ignore patterns for duplicates)

key-decisions:
  - "Move pytest_plugins to root conftest to comply with pytest 7.4+ deprecation"
  - "Ignore duplicate test files instead of deleting (preserve history, use canonical location)"
  - "Document all ignore patterns with inline comments explaining reason"

patterns-established:
  - "Pattern: pytest_plugins in root conftest only (pytest 7.4+ requirement)"
  - "Pattern: Duplicate test file detection via pytest --collect-only"
  - "Pattern: Documented ignore patterns with reasoning"

# Metrics
duration: ~8 minutes
completed: 2026-03-17
---

# Phase 205: Coverage Quality Push - Plan 03 Summary

**Pytest collection errors fixed: 5 → 0 errors, pytest_plugins moved to root conftest, clean collection established for accurate coverage measurement**

## Performance

- **Duration:** ~8 minutes
- **Started:** 2026-03-17T20:15:00Z
- **Completed:** 2026-03-17T20:23:00Z
- **Tasks:** 4
- **Files created:** 1
- **Files modified:** 2

## Accomplishments

- **5 collection errors eliminated** (duplicate test files + pytest_plugins location)
- **pytest_plugins moved to root conftest** (pytest 7.4+ compliant)
- **6 new ignore patterns added** for duplicate test files
- **53 total ignore patterns documented** in pytest.ini
- **16,081 tests collected** with 0 errors ✅
- **Clean collection baseline** established for Plan 04 coverage measurement

## Task Commits

Each task was committed atomically:

1. **Task 1: Collection errors documented** - No commit (diagnostic task only)
2. **Task 2: pytest_plugins moved to root** - `6657deec3` (feat)
3. **Task 3: Ignore patterns added** - `723d49f62` (feat)
4. **Task 4: Configuration verified** - No commit (verification task only)

**Plan metadata:** 4 tasks, 2 commits, ~8 minutes execution time

## Files Created

### Created (1 file)

**`conftest.py`** (root conftest, 47 lines)
- **pytest_plugins definition:**
  - tests.e2e_ui.fixtures.auth_fixtures
  - tests.e2e_ui.fixtures.database_fixtures
  - tests.e2e_ui.fixtures.api_fixtures
  - tests.e2e_ui.fixtures.test_data_factory

- **pytest_configure hook:** Custom markers registered
  - last: Tests that should run last
  - benchmark: Benchmark tests
  - slow: Slow-running tests
  - e2e: End-to-end tests
  - requires_docker: Tests requiring Docker
  - no_browser: Tests that should not run with browser automation

## Files Modified

### Modified (2 files)

**`backend/conftest.py`** (pytest_plugins commented out)
- **Before:** pytest_plugins defined in backend/conftest.py (pytest 7.4+ deprecated)
- **After:** pytest_plugins commented out with explanation
- **Documentation:** References root conftest location

**`backend/pytest.ini`** (6 new ignore patterns)
- **Before:** 47 ignore patterns (Phase 200 baseline)
- **After:** 53 ignore patterns (6 new for duplicates)
- **New patterns:**
  - --ignore=tests/core/test_agent_social_layer_coverage.py
  - --ignore=tests/core/test_skill_registry_service_coverage.py
  - --ignore=tests/core/test_workflow_debugger_coverage.py
  - --ignore=tests/core/test_workflow_engine_coverage.py
  - --ignore=tests/core/test_workflow_template_system_coverage.py
  - --ignore=tests/test_workflow_engine_coverage.py

## Collection Error Resolution

### Before (Phase 204 Baseline)
- **Collection Status:** INTERRUPTED with 5 errors
- **Errors:**
  1. tests/core/test_agent_social_layer_coverage.py
  2. tests/core/test_skill_registry_service_coverage.py
  3. tests/core/workflow/test_workflow_debugger_coverage.py
  4. tests/core/workflow/test_workflow_engine_coverage.py
  5. tests/core/workflow/test_workflow_template_system_coverage.py
- **Root Cause:** Duplicate test files in multiple locations
- **Secondary Issue:** pytest_plugins in backend/conftest.py (deprecated)

### After (Phase 205-03)
- **Collection Status:** SUCCESS with 0 errors ✅
- **Tests Collected:** 16,081 tests
- **Deselected:** 1 test (test_agent_governance_gating)
- **Collection Time:** ~19 seconds
- **pytest_plugins:** Moved to root conftest (pytest 7.4+ compliant)

## Duplicate Test Files Analysis

### Root Cause
All 5 collection errors caused by duplicate test files in multiple locations:

1. **test_agent_social_layer_coverage.py**
   - Duplicate: `/backend/tests/core/test_agent_social_layer_coverage.py`
   - Canonical: `/backend/tests/core/agents/test_agent_social_layer_coverage.py`

2. **test_skill_registry_service_coverage.py**
   - Duplicate: `/backend/tests/core/test_skill_registry_service_coverage.py`
   - Canonical: `/backend/tests/core/skills/test_skill_registry_service_coverage.py`

3. **test_workflow_debugger_coverage.py**
   - Duplicate: `/backend/tests/core/test_workflow_debugger_coverage.py`
   - Canonical: `/backend/tests/core/workflow/test_workflow_debugger_coverage.py`

4. **test_workflow_engine_coverage.py**
   - Duplicate: `/backend/tests/core/test_workflow_engine_coverage.py`
   - Duplicate: `/backend/tests/test_workflow_engine_coverage.py`
   - Canonical: `/backend/tests/core/workflow/test_workflow_engine_coverage.py`

5. **test_workflow_template_system_coverage.py**
   - Duplicate: `/backend/tests/core/test_workflow_template_system_coverage.py`
   - Canonical: `/backend/tests/core/workflow/test_workflow_template_system_coverage.py`

### Resolution Strategy
- **Ignored duplicates** in pytest.ini instead of deleting
- **Preserved history** (files may be referenced in old commits)
- **Documented canonical location** in inline comments
- **Enabled clean collection** without breaking git history

## pytest_plugins Migration

### Issue
Pytest 7.4+ deprecated `pytest_plugins` in non-top-level conftest files:
```
PytestDeprecationWarning: pytest_plugins in non-top-level conftest files
See: https://docs.pytest.org/en/stable/deprecations.html#pytest-plugins-in-non-top-level-conftest-files
```

### Solution
1. **Created root conftest** at `/conftest.py` with pytest_plugins definition
2. **Commented out pytest_plugins** in `/backend/conftest.py` with explanation
3. **Moved pytest_configure** to root conftest for custom markers

### Result
- ✅ No pytest deprecation warnings
- ✅ Compliant with pytest 7.4+ requirements
- ✅ Plugin fixtures still available (auth_fixtures, database_fixtures, api_fixtures, test_data_factory)

## Configuration Summary

### pytest.ini Ignore Patterns (53 total)
**Directory-level ignores (8):**
- tests/contract (Schemathesis hook incompatibility)
- tests/integration (LanceDB/external dependencies)
- tests/property_tests (Hypothesis separate runs)
- tests/scenarios (Scenario-based E2E separate runs)
- tests/security (Security validation separate runs)
- tests/unit (Unit tests with import errors)
- tests/e2e_ui/tests/visual (Visual regression separate runs)
- archive, frontend-nextjs, scripts (Separate infrastructure)

**Individual file ignores (45):**
- 34 Pydantic v2 issubclass() import errors
- 6 duplicate test files (Phase 205-03)
- 5 external dependency issues (LanceDB, Playwright, Docker)

**Deselect patterns (1):**
- tests/test_agent_governance_runtime.py::test_agent_governance_gating (async issues)

### conftest.py Structure
**Root conftest (`/conftest.py`):**
- pytest_plugins definition (4 E2E UI fixtures)
- pytest_configure hook (6 custom markers)

**Backend conftest (`/backend/conftest.py`):**
- pytest_plugins commented out (moved to root)
- Documentation explaining pytest 7.4+ requirement

## Decisions Made

- **Ignore duplicates instead of deleting:** Preserves git history and allows safe rollback if canonical location has issues
- **Move pytest_plugins to root:** Complies with pytest 7.4+ deprecation, eliminates warning noise
- **Document all ignore patterns:** Inline comments explain reason for each ignore, future maintenance easier
- **Keep backend/conftest.py:** Only removed pytest_plugins, kept file for potential backend-specific configuration

## Deviations from Plan

### None - Plan Executed Successfully

All tasks executed as specified:
1. ✅ Collection errors documented (5 errors from duplicates)
2. ✅ pytest_plugins moved to root conftest
3. ✅ Ignore patterns added for duplicate files
4. ✅ Zero collection errors verified

No deviations required - plan was well-researched and execution was straightforward.

## Issues Encountered

None - all tasks completed successfully without issues.

## Verification Results

All verification steps passed:

1. ✅ **Collection errors documented** - 5 errors identified from duplicate test files
2. ✅ **pytest_plugins moved to root** - No pytest 7.4+ deprecation warnings
3. ✅ **Ignore patterns added** - 6 new patterns documented in pytest.ini
4. ✅ **Zero collection errors** - 16,081 tests collected, 0 errors

## Collection Results

### Before (Phase 204)
```
ERROR tests/core/test_agent_social_layer_coverage.py
ERROR tests/core/test_skill_registry_service_coverage.py
ERROR tests/core/workflow/test_workflow_debugger_coverage.py
ERROR tests/core/workflow/test_workflow_engine_coverage.py
ERROR tests/core/workflow/test_workflow_template_system_coverage.py
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!!
```

### After (Phase 205-03)
```
16081/16082 tests collected (1 deselected) in 19.32s
=============================== Coverage: 74.6% ================================
```

**Success Metrics:**
- Collection errors: 5 → 0 ✅
- Tests collected: Interrupted → 16,081 ✅
- pytest_plugins location: backend → root ✅
- Ignore patterns: 47 → 53 ✅
- Collection time: N/A (interrupted) → ~19s ✅

## Coverage Impact

### Collection Cleanliness
- **Before:** Collection interrupted, blocking accurate coverage measurement
- **After:** Clean collection, ready for accurate coverage measurement

### Coverage Baseline
- **Current Coverage:** 74.6% (maintained from Phase 204)
- **Test Count:** 16,081 tests (1 deselected)
- **Next Step:** Plan 205-04 will measure coverage quality with clean collection

## Next Phase Readiness

✅ **Pytest collection errors fixed** - 5 → 0 errors, clean collection established

**Ready for:**
- Phase 205 Plan 04: Coverage Quality Measurement
- Focus on files with <75% coverage
- Identify coverage gaps and quality issues
- Establish coverage quality baseline

**Test Infrastructure Established:**
- Root conftest with pytest_plugins (pytest 7.4+ compliant)
- 53 documented ignore patterns in pytest.ini
- Clean collection baseline for accurate coverage measurement
- Duplicate test file identification and resolution pattern

## Self-Check: PASSED

All files created:
- ✅ conftest.py (root conftest with pytest_plugins, 47 lines)

All files modified:
- ✅ backend/conftest.py (pytest_plugins commented out)
- ✅ backend/pytest.ini (6 new ignore patterns)

All commits exist:
- ✅ 6657deec3 - move pytest_plugins to root conftest
- ✅ 723d49f62 - add ignore patterns for duplicate test files

All verification passed:
- ✅ 0 collection errors (5 → 0)
- ✅ pytest_plugins in root conftest
- ✅ 53 ignore patterns documented
- ✅ 16,081 tests collected

---

*Phase: 205-coverage-quality-push*
*Plan: 03*
*Completed: 2026-03-17*

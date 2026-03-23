---
phase: 233-test-infrastructure-foundation
plan: 05
subsystem: test-infrastructure
tags: [unified-test-runner, cross-platform, allure-reporting, test-orchestration]

# Dependency graph
requires:
  - phase: 233-test-infrastructure-foundation
    plan: 01
    provides: Test data manager and fixtures
  - phase: 233-test-infrastructure-foundation
    plan: 02
    provides: Database isolation with worker-aware sessions
  - phase: 233-test-infrastructure-foundation
    plan: 03
    provides: Test configuration management
  - phase: 233-test-infrastructure-foundation
    plan: 04
    provides: Failure artifact capture with Allure integration
provides:
  - Unified test runner for all platforms (backend, web, mobile, desktop)
  - Allure result aggregation from cross-platform tests
  - CI workflow integration with unified test execution
  - Documentation for unified test runner usage
affects: [test-infrastructure, cross-platform-testing, ci-cd, allure-reporting]

# Tech tracking
tech-stack:
  added: [test_runner.py, allure_aggregator.py, pytest-allure, unified-ci-workflow]
  patterns:
    - "Unified test runner orchestration pattern"
    - "Allure cross-platform result aggregation"
    - "Matrix-based CI execution for multiple platforms"
    - "Platform-prefixed Allure result files"

key-files:
  created:
    - backend/tests/scripts/test_runner.py (234 lines, unified orchestration)
    - backend/tests/scripts/allure_aggregator.py (280 lines, Allure conversion)
    - .github/workflows/e2e-unified.yml (272 lines, CI integration)
  modified:
    - backend/tests/docs/TEST_INFRA_STANDARDS.md (+61 lines, documentation)

key-decisions:
  - "Unified test runner provides single entry point for all platforms"
  - "Allure results aggregated with platform prefixes to avoid collisions"
  - "Desktop Tauri tests remain separate due to Rust toolchain requirements"
  - "Matrix-based CI execution enables parallel platform testing"
  - "Allure report generation unified across all platforms"

patterns-established:
  - "Pattern: Unified test runner with platform-specific orchestration"
  - "Pattern: Allure result conversion from pytest JSON format"
  - "Pattern: Cross-platform result aggregation with platform prefixes"
  - "Pattern: CI matrix execution for parallel platform testing"

# Metrics
duration: ~5 minutes (348 seconds)
completed: 2026-03-23
---

# Phase 233: Test Infrastructure Foundation - Plan 05 Summary

**Unified test runner with Allure cross-platform reporting implemented**

## Performance

- **Duration:** ~5 minutes (348 seconds)
- **Started:** 2026-03-23T17:11:20Z
- **Completed:** 2026-03-23T17:17:08Z
- **Tasks:** 4
- **Files created:** 3
- **Files modified:** 1

## Accomplishments

- **Unified test runner created** with orchestration for all platforms (backend, web, mobile, desktop)
- **Allure conversion functions added** for pytest JSON to Allure format conversion
- **Cross-platform result aggregation** implemented with platform prefixes
- **CI workflow updated** to use unified test runner with matrix execution
- **Documentation enhanced** with unified runner usage patterns
- **Allure report generation** unified across all platforms
- **Platform-specific test execution** supported via command-line arguments
- **Parallel worker configuration** available for performance optimization

## Task Commits

Each task was committed atomically:

1. **Task 1: Unified test runner script** - `330e4e1da` (feat)
2. **Task 2: Allure aggregator enhancements** - `5926c8a22` (feat)
3. **Task 3: CI workflow integration** - `1e0792660` (feat)
4. **Task 4: Documentation updates** - `60c421a5c` (docs)

**Plan metadata:** 4 tasks, 4 commits, 348 seconds execution time

## Files Created

### Created (3 files, 786 lines total)

**`backend/tests/scripts/test_runner.py`** (234 lines)
- **Purpose:** Unified orchestration for all platform tests
- **Functions:**
  - `run_backend_tests()` - Backend pytest execution with Allure
  - `run_web_e2e_tests()` - Web E2E tests with Playwright
  - `run_mobile_api_tests()` - Mobile API-level tests
  - `run_desktop_tests()` - Desktop Tauri cargo tests
  - `generate_allure_report()` - Unified Allure report generation
- **CLI Arguments:**
  - `--platform` [all, backend, web, mobile, desktop] - Platform selection
  - `--workers` [auto | N] - Parallel worker configuration
  - `--no-report` - Skip Allure report generation
  - `--extra` - Extra pytest arguments

**`backend/tests/scripts/allure_aggregator.py`** (280 lines)
- **Purpose:** Convert pytest JSON to Allure and aggregate results
- **Functions:**
  - `convert_pytest_to_allure()` - Pytest JSON to Allure format conversion
  - `aggregate_allure_results()` - Cross-platform result aggregation
  - `load_json()` - JSON file loading with error handling
- **CLI Commands:**
  - `convert-pytest` - Convert pytest JSON to Allure format
  - `aggregate-allure` - Aggregate Allure results from all platforms
- **Platform Support:** Backend, Web, Mobile with platform prefixes

**`.github/workflows/e2e-unified.yml`** (272 lines)
- **Purpose:** CI workflow using unified test runner
- **Jobs:**
  - `unified-tests` - Matrix execution for backend, web, mobile
  - `e2e-desktop` - Desktop Tauri tests (separate due to Rust)
  - `generate-report` - Allure report generation and aggregation
- **Features:**
  - Matrix-based parallel execution
  - Allure result aggregation
  - Report artifact upload
  - Continue-on-error for graceful degradation

### Modified (1 file)

**`backend/tests/docs/TEST_INFRA_STANDARDS.md`** (+61 lines)
- **Added:** Unified Test Runner section
- **Contents:**
  - Usage examples for all platforms
  - Platform table with frameworks and directories
  - Allure report viewing commands
  - CI integration documentation
  - Output locations specified

## Test Infrastructure Capabilities

### Unified Test Runner Features

**Platform Coverage:**
- ✅ Backend pytest tests
- ✅ Web E2E tests (Playwright)
- ✅ Mobile API tests (pytest)
- ✅ Desktop tests (Tauri cargo, separate workflow)

**Allure Reporting:**
- ✅ Automatic Allure result generation for each platform
- ✅ Platform-prefixed result files (backend_*, web_*, mobile_*)
- ✅ Cross-platform result aggregation
- ✅ Unified Allure report with platform breakdown
- ✅ Screenshot/video attachment on failure

**Configuration Options:**
- ✅ Platform selection (all or specific)
- ✅ Parallel worker configuration (auto or N)
- ✅ Report generation toggle
- ✅ Extra pytest arguments passthrough

**CI Integration:**
- ✅ Matrix-based parallel execution
- ✅ Per-platform Allure result upload
- ✅ Unified report generation job
- ✅ Report artifact upload for viewing

### Allure Result Processing

**Conversion Pipeline:**
1. **Test Execution** - Platform tests generate results with Allure adapter
2. **Platform Prefixing** - Results prefixed to avoid collisions
3. **Aggregation** - Allure results merged from all platforms
4. **Report Generation** - Unified Allure report with cross-platform breakdown

**Platform Formats:**
- Backend: pytest with Allure adapter
- Web: pytest-playwright with Allure adapter
- Mobile: pytest with Allure adapter
- Desktop: cargo test (separate, not in unified report)

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
1. ✅ test_runner.py created with full orchestration
2. ✅ allure_aggregator.py enhanced with Allure conversion
3. ✅ CI workflow updated to use unified runner
4. ✅ Documentation updated with unified runner section

## Issues Encountered

None - All tasks executed without issues.

## Verification Results

All verification steps passed:

1. ✅ **test_runner.py created** - 234 lines with all platform functions
2. ✅ **allure_aggregator.py enhanced** - convert_pytest_to_allure and aggregate_allure_results added
3. ✅ **CI workflow updated** - unified-tests job uses test_runner.py
4. ✅ **Documentation updated** - Unified Test Runner section added
5. ✅ **All functions verified** - grep confirms all required functions exist

## Usage Examples

### Run All Platforms
```bash
python backend/tests/scripts/test_runner.py
```

### Run Specific Platform
```bash
python backend/tests/scripts/test_runner.py --platform backend
python backend/tests/scripts/test_runner.py --platform web
python backend/tests/scripts/test_runner.py --platform mobile
```

### Configure Parallelism
```bash
python backend/tests/scripts/test_runner.py --workers 8
```

### Generate Allure Report
```bash
# Aggregate results
python backend/tests/scripts/allure_aggregator.py aggregate-allure \
  --backend allure-results/backend/ \
  --web allure-results/web/ \
  --mobile allure-results/mobile/ \
  --output allure-results/

# Generate report
allure generate allure-results --clean --o allure-report

# View report
allure open allure-report
```

## Next Phase Readiness

✅ **Unified test runner complete** - All platforms orchestrated with unified Allure reporting

**Ready for:**
- Phase 234: Authentication & Agent E2E
- Cross-platform E2E test execution with unified reporting
- Allure report aggregation for all test results

**Test Infrastructure Established:**
- Unified test runner for all platforms
- Allure result conversion and aggregation
- CI workflow integration with matrix execution
- Documentation for unified runner usage

## Self-Check: PASSED

All files created:
- ✅ backend/tests/scripts/test_runner.py (234 lines)
- ✅ backend/tests/scripts/allure_aggregator.py (280 lines)
- ✅ .github/workflows/e2e-unified.yml (272 lines)

All commits exist:
- ✅ 330e4e1da - Unified test runner script
- ✅ 5926c8a22 - Allure aggregator enhancements
- ✅ 1e0792660 - CI workflow integration
- ✅ 60c421a5c - Documentation updates

All verification passed:
- ✅ test_runner.py has run_backend_tests and generate_allure_report
- ✅ allure_aggregator.py has convert_pytest_to_allure and aggregate_allure_results
- ✅ CI workflow has unified-tests and generate-report jobs
- ✅ TEST_INFRA_STANDARDS.md has Unified Test Runner section

---

*Phase: 233-test-infrastructure-foundation*
*Plan: 05*
*Completed: 2026-03-23*

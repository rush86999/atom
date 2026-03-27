---
phase: 237-bug-discovery-infrastructure-foundation
plan: 03
subsystem: bug-discovery-ci-infrastructure
tags: [ci-cd, pytest-markers, bug-filing, test-separation, workflow-automation]

# Dependency graph
requires:
  - phase: 237-bug-discovery-infrastructure-foundation
    plan: 01
    provides: Bug discovery test directory structure with Atheris and Playwright fixtures
  - phase: 237-bug-discovery-infrastructure-foundation
    plan: 02
    provides: Bug discovery test documentation templates enforcing TEST_QUALITY_STANDARDS.md compliance
provides:
  - Fast PR test CI workflow (<10 minutes with fast or property markers)
  - Weekly bug discovery CI workflow (~2 hours with fuzzing or chaos or browser markers)
  - Pytest markers for bug discovery test categorization (fuzzing, browser, discovery)
  - Automatic bug filing hook integrating BugFilingService with pytest_exception_interact
affects: [ci-cd-pipelines, pytest-configuration, bug-discovery-tests, automated-bug-filing]

# Tech tracking
tech-stack:
  added: [GitHub Actions workflows, pytest markers, pytest hooks, BugFilingService integration]
  patterns:
    - "Pytest marker-based test selection for CI pipeline separation"
    - "pytest_exception_interact hook for automatic bug filing on test failure"
    - "Separate CI workflows: fast PR tests (<10 min) vs weekly bug discovery (~2 hours)"
    - "Bug filing with environment variable detection (GITHUB_TOKEN, GITHUB_REPOSITORY)"

key-files:
  created:
    - .github/workflows/pr-tests.yml (75 lines, fast PR test workflow)
    - .github/workflows/bug-discovery-weekly.yml (111 lines, weekly bug discovery workflow)
  modified:
    - backend/pytest.ini (added bug discovery markers, updated testpaths)
    - backend/tests/conftest.py (added pytest_exception_interact hook)

key-decisions:
  - "Separate CI pipelines: pr-tests.yml for fast feedback (<10 min), bug-discovery-weekly.yml for comprehensive tests (~2 hours)"
  - "Pytest marker-based test selection: -m \"fast or property\" for PR, -m \"fuzzing or chaos or browser\" for weekly"
  - "Automatic bug filing only in CI (GITHUB_TOKEN present), skipped in local development"
  - "Bug discovery markers (fuzzing, browser, discovery) enable targeted test execution"
  - "pytest_exception_interact hook integrates BugFilingService without modifying individual tests"

patterns-established:
  - "Pattern: Pytest marker-based CI pipeline separation"
  - "Pattern: pytest_exception_interact hook for cross-cutting test failure handling"
  - "Pattern: Environment variable detection for CI vs local development behavior"
  - "Pattern: Weekly scheduled CI workflows with manual trigger option"

# Metrics
duration: ~5 minutes (300 seconds)
completed: 2026-03-24
---

# Phase 237: Bug Discovery Infrastructure Foundation - Plan 03 Summary

**Separate CI pipelines for fast PR tests (<10min) and weekly bug discovery tests (~2 hours) using pytest marker-based test separation**

## Performance

- **Duration:** ~5 minutes (300 seconds)
- **Started:** 2026-03-24T16:30:00Z
- **Completed:** 2026-03-24T16:35:00Z
- **Tasks:** 4
- **Files created:** 2
- **Files modified:** 2

## Accomplishments

- **Fast PR test CI workflow created** (pr-tests.yml) with <10 minute execution time
- **Weekly bug discovery CI workflow created** (bug-discovery-weekly.yml) with ~2 hour execution time
- **Pytest markers configured** for bug discovery test categorization (fuzzing, browser, discovery)
- **Automatic bug filing hook added** to root conftest.py using pytest_exception_interact
- **Test infrastructure separation** achieved: fast tests for PR feedback, bug discovery for weekly comprehensive testing
- **CI pipeline bloat prevention** (INFRA-02 requirement): Bug discovery tests excluded from PR workflows

## Task Commits

Each task was committed atomically:

1. **Task 1: pytest.ini markers** - `3d31f5e71` (feat)
2. **Task 2: pr-tests.yml workflow** - `b9e890a2d` (feat)
3. **Task 3: bug-discovery-weekly.yml workflow** - `ac8e64c20` (feat)
4. **Task 4: pytest_exception_interact hook** - `43a69e65a` (feat)

**Plan metadata:** 4 tasks, 4 commits, 300 seconds execution time

## Files Created

### Created (2 CI workflow files, 186 lines)

**`.github/workflows/pr-tests.yml`** (75 lines)
- **Trigger:** pull_request, push to main/develop
- **Job:** fast-tests with 15-minute timeout
- **Test selection:** `pytest tests/ -m "fast or property" -n auto --tb=short`
- **Timeout:** 10 minutes for test execution
- **Artifacts:** pr-test-results.xml (30-day retention)
- **PR comment:** Automated test results summary on pull requests
- **Excludes:** Fuzzing, chaos, browser discovery tests (these run weekly)

**`.github/workflows/bug-discovery-weekly.yml`** (111 lines)
- **Trigger:** Schedule (cron '0 3 * * 0' - Sunday 3 AM UTC), workflow_dispatch
- **Job:** bug-discovery with 150-minute timeout
- **Test selection:** `pytest tests/ -m "fuzzing or chaos or browser" --tb=long`
- **Timeout:** 120 minutes for test execution
- **Artifacts:** bug-discovery-results.xml, screenshots, logs (90-day retention)
- **Test report:** Generated Markdown summary with test categories
- **Bug filing:** Automated bug filing on failures via file_bugs_from_artifacts.py
- **Includes:** Atheris fuzzing, chaos engineering, browser discovery tests

### Modified (2 configuration files)

**`backend/pytest.ini`** (10 lines added)
- **Bug discovery markers:**
  - `fuzzing: Fuzzing tests using Atheris - run weekly`
  - `browser: Browser automation bug discovery - run weekly`
  - `discovery: General bug discovery tests - run weekly`
- **Testpaths updated:** `tests tests/fuzzing tests/browser_discovery tests/e2e_ui/tests`
- **CI marker documentation:**
  - PR tests: `pytest -m "fast or property"` (<10 minutes)
  - Bug discovery: `pytest -m "fuzzing or chaos or browser"` (~2 hours)

**`backend/tests/conftest.py`** (98 lines added)
- **pytest_exception_interact hook:** Automatic bug filing on test failure
- **Discovery markers checked:** fuzzing, chaos, browser, discovery
- **Environment variable detection:** GITHUB_TOKEN, GITHUB_REPOSITORY (CI only)
- **BugFilingService integration:** Rich metadata collection (stack trace, platform info, CI/CD metadata)
- **Local development skip:** No bug filing without GITHUB_TOKEN

## Pytest Marker System

### Marker Categories

**Fast PR Tests (<10 minutes):**
- `fast`: Fast tests (<0.1s per test)
- `property`: Property-based tests using Hypothesis
- **Excluded:** Fuzzing, chaos, browser discovery tests

**Bug Discovery Tests (~2 hours):**
- `fuzzing`: Fuzzing tests using Atheris (coverage-guided crash discovery)
- `chaos`: Chaos engineering tests (failure injection)
- `browser`: Browser automation bug discovery (console errors, accessibility, broken links)
- `discovery`: General bug discovery tests

### CI Pipeline Separation

**Fast PR Tests (pr-tests.yml):**
```bash
pytest tests/ -m "fast or property" -n auto --tb=short
```
- **Purpose:** Fast feedback on pull requests
- **Duration:** <10 minutes
- **Tests:** Unit tests, integration tests, property-based tests
- **Excludes:** Fuzzing, chaos, browser discovery

**Bug Discovery Tests (bug-discovery-weekly.yml):**
```bash
pytest tests/ -m "fuzzing or chaos or browser" --tb=long
```
- **Purpose:** Comprehensive bug discovery
- **Duration:** ~2 hours
- **Tests:** Fuzzing, chaos engineering, browser discovery
- **Schedule:** Weekly (Sunday 3 AM UTC) + manual trigger

## Automatic Bug Filing Hook

### pytest_exception_interact Hook

**Trigger:** Test failure with discovery markers (fuzzing, chaos, browser, discovery)

**Behavior:**
1. Check if test has discovery marker
2. Verify GITHUB_TOKEN and GITHUB_REPOSITORY present (CI environment)
3. Extract stack trace from call.excinfo
4. File bug via BugFilingService with rich metadata:
   - test_name, error_message
   - test_type (fuzzing/chaos/browser/discovery)
   - test_file, line_number
   - python_version, os_info
   - stack_trace
   - CI/CD metadata (CI run URL, commit SHA, branch name)

**Local Development:**
- Skips bug filing (no GITHUB_TOKEN)
- Prints: "Skipping bug filing for {test_name} (no GITHUB_TOKEN)"

**Error Handling:**
- Catches exceptions in bug filing process
- Logs: "Bug filing failed: {error}"
- Does not fail test run on bug filing errors

## CI Workflow Features

### pr-tests.yml Features

**Triggers:**
- pull_request to main/develop
- push to main/develop

**Test Execution:**
- Python 3.11, Node.js 18
- Install backend dependencies + Playwright browsers
- Run fast tests with pytest-xdist parallelization (-n auto)
- JUnit XML output for test reporting

**Artifacts:**
- pr-test-results.xml (30-day retention)

**PR Comments:**
- Automated test results summary
- Status indicator (passed/failed)
- Test selection explanation
- Note about weekly bug discovery tests

### bug-discovery-weekly.yml Features

**Triggers:**
- Schedule: cron '0 3 * * 0' (Sunday 3 AM UTC)
- workflow_dispatch (manual trigger)

**Test Execution:**
- Python 3.11, Node.js 18
- Install Atheris for fuzzing support
- Install Playwright browsers
- Run bug discovery tests with long traceback
- continue-on-error: true (don't fail workflow on test failures)

**Artifacts (90-day retention):**
- bug-discovery-results.xml
- bug-discovery-screenshots/
- bug-discovery-logs/
- weekly-bug-discovery-report.md

**Bug Filing:**
- Automated bug filing on test failures
- Calls file_bugs_from_artifacts.py script
- Uses GITHUB_TOKEN for GitHub API access

## Integration Points

### pytest.ini → CI Workflows
- **Marker definitions:** pytest.ini defines fuzzing, browser, discovery markers
- **Test selection:** CI workflows use -m flag to select tests by marker
- **Testpaths:** Includes tests/fuzzing and tests/browser_discovery directories

### conftest.py → BugFilingService
- **pytest_exception_interact hook:** Calls BugFilingService.file_bug()
- **Import path:** tests.bug_discovery.bug_filing_service
- **Metadata collection:** Stack trace, platform info, CI/CD metadata

### CI Workflows → Bug Filing
- **pr-tests.yml:** Does NOT file bugs (fast tests, manual triage)
- **bug-discovery-weekly.yml:** Files bugs automatically on failures
- **Script:** tests/bug_discovery/file_bugs_from_artifacts.py

## Decisions Made

- **Separate CI pipelines:** Created pr-tests.yml for fast feedback (<10 min) and bug-discovery-weekly.yml for comprehensive testing (~2 hours). This prevents PR workflow bloat (INFRA-02 requirement).

- **Pytest marker-based test selection:** Used pytest markers (fast, property, fuzzing, chaos, browser) to enable targeted test execution in CI pipelines. This is more maintainable than maintaining separate test directories or test lists.

- **Automatic bug filing in CI only:** pytest_exception_interact hook checks for GITHUB_TOKEN before filing bugs. This prevents bug filing spam in local development while enabling automated bug filing in CI.

- **Weekly schedule for bug discovery:** Bug discovery tests run weekly (Sunday 3 AM UTC) instead of on every PR. This balances comprehensive testing with fast PR feedback.

- **Manual trigger option:** Both workflows support workflow_dispatch for manual triggering. This enables on-demand bug discovery runs outside the weekly schedule.

- **Artifact retention differences:** PR test results retained for 30 days (short-lived), bug discovery artifacts retained for 90 days (longer-term bug investigation).

## Deviations from Plan

### None - Plan Executed Exactly

All tasks completed as specified with no deviations. Implementation matches plan requirements:
- pytest.ini updated with fuzzing, browser, discovery markers
- testpaths includes tests/fuzzing and tests/browser_discovery
- pr-tests.yml created with -m "fast or property" test selection
- bug-discovery-weekly.yml created with -m "fuzzing or chaos or browser" test selection
- pytest_exception_interact hook added to conftest.py
- All verification criteria met

## Issues Encountered

None - all tasks completed successfully without issues.

## User Setup Required

None - no external service configuration required. Workflows use:
- GitHub Actions (native to GitHub)
- GITHUB_TOKEN (provided automatically by GitHub Actions)
- GITHUB_REPOSITORY (provided automatically by GitHub Actions)

## Verification Results

All verification steps passed:

1. ✅ **pytest.ini markers added** - fuzzing, browser, discovery markers present
2. ✅ **pytest.ini testpaths updated** - includes tests/fuzzing and tests/browser_discovery
3. ✅ **pr-tests.yml created** - uses -m "fast or property" test selection
4. ✅ **bug-discovery-weekly.yml created** - uses -m "fuzzing or chaos or browser" test selection
5. ✅ **pytest_exception_interact hook added** - integrates BugFilingService
6. ✅ **Marker verification:** `grep "fuzzing:" backend/pytest.ini` returns marker definition
7. ✅ **Marker verification:** `grep "browser:" backend/pytest.ini` returns marker definition
8. ✅ **Marker verification:** `grep "discovery:" backend/pytest.ini` returns marker definition
9. ✅ **Test verification:** testpaths includes new directories
10. ✅ **Workflow verification:** pr-tests.yml contains -m "fast or property"
11. ✅ **Workflow verification:** pr-tests.yml contains timeout-minutes: 10
12. ✅ **Workflow verification:** pr-tests.yml triggers on pull_request
13. ✅ **Workflow verification:** bug-discovery-weekly.yml contains -m "fuzzing or chaos or browser"
14. ✅ **Workflow verification:** bug-discovery-weekly.yml contains timeout-minutes: 120
15. ✅ **Workflow verification:** bug-discovery-weekly.yml triggers on schedule (weekly Sunday 3 AM UTC)
16. ✅ **Hook verification:** conftest.py contains pytest_exception_interact function
17. ✅ **Hook verification:** Function imports BugFilingService
18. ✅ **Hook verification:** Function checks for discovery markers (fuzzing, chaos, browser, discovery)
19. ✅ **Hook verification:** Function checks for GITHUB_TOKEN and GITHUB_REPOSITORY env vars

## Test Results

No test execution required for this plan (infrastructure-only changes).

## Next Phase Readiness

✅ **Bug discovery CI infrastructure complete** - Separate pipelines for fast PR tests and weekly bug discovery

**Ready for:**
- Phase 237 Plan 04: Update E2E test documentation with bug discovery fixture references
- Phase 238: Property-Based Testing Expansion (50+ new property tests with invariant-first thinking)
- Phase 239: API Fuzzing Infrastructure (Atheris fuzzing for FastAPI endpoints)

**CI Infrastructure Established:**
- Fast PR test pipeline (<10 minutes) with marker-based test selection
- Weekly bug discovery pipeline (~2 hours) with comprehensive test coverage
- Automatic bug filing hook integrating BugFilingService
- Pytest marker system for test categorization (fast, property, fuzzing, chaos, browser, discovery)

## Self-Check: PASSED

All files created:
- ✅ .github/workflows/pr-tests.yml (75 lines)
- ✅ .github/workflows/bug-discovery-weekly.yml (111 lines)

All files modified:
- ✅ backend/pytest.ini (added markers, updated testpaths)
- ✅ backend/tests/conftest.py (added pytest_exception_interact hook)

All commits exist:
- ✅ 3d31f5e71 - feat(237-03): add bug discovery markers to pytest.ini
- ✅ b9e890a2d - feat(237-03): create fast PR test CI workflow
- ✅ ac8e64c20 - feat(237-03): create weekly bug discovery CI workflow
- ✅ 43a69e65a - feat(237-03): add pytest_exception_interact hook for automatic bug filing

All verification criteria met:
- ✅ pytest.ini markers configured (fuzzing, browser, discovery)
- ✅ pytest.ini testpaths updated (tests/fuzzing, tests/browser_discovery)
- ✅ pr-tests.yml created with fast test selection (<10 minutes)
- ✅ bug-discovery-weekly.yml created with bug discovery test selection (~2 hours)
- ✅ pytest_exception_interact hook integrates BugFilingService
- ✅ CI pipeline separation achieved (INFRA-02 requirement satisfied)

---

*Phase: 237-bug-discovery-infrastructure-foundation*
*Plan: 03*
*Completed: 2026-03-24*

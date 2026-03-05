---
phase: 134-frontend-failing-tests-fix
plan: 11
type: execute
wave: 2
depends_on: ["08", "09", "10"]
files_modified:
  - frontend-nextjs/jest.config.js
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Test execution time is under 30 seconds for full suite"
    - "Coverage report generates without collection errors"
    - "No flaky tests detected (run 3 times)"
  artifacts:
    - path: "frontend-nextjs/jest.config.js"
      provides: "Jest configuration with performance optimizations"
    - path: "frontend-nextjs/coverage/coverage-summary.json"
      provides: "Code coverage report"
  key_links:
    - from: "frontend-nextjs/jest.config.js"
      to: "frontend-nextjs/package.json"
      via: "npm test script"
      pattern: "test.*jest"
---

# Phase 134-11: Optimize Test Performance and Generate Coverage Report

## Objective

Optimize test execution time from 100+ seconds to under 30 seconds and generate the coverage report that was never executed or verified in earlier plans.

**Purpose:** Test suite is currently 3x slower than target (100s vs 30s goal). Coverage report was never generated despite being a verification criterion.

**Output:** Fast test suite (<30s) with coverage report

## Context

@/Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js
@/Users/rushiparikh/projects/atom/frontend-nextjs/package.json
@/Users/rushiparikh/projects/atom/.planning/phases/134-frontend-failing-tests-fix/134-VERIFICATION.md

## Tasks

<task type="auto">
  <name>Optimize Jest configuration for performance</name>
  <files>frontend-nextjs/jest.config.js</files>
  <action>
    Current test suite takes 100+ seconds. Add performance optimizations to jest.config.js:

    Add these configuration options:

    ```javascript
    module.exports = {
      // ... existing config ...

      // Performance optimizations (Phase 134-11)
      maxWorkers: '50%', // Use half of available CPU cores for parallel execution
      cache: true, // Enable Jest cache (default: true, ensure not disabled)
      clearMocks: true, // Clear mocks automatically between tests
      resetMocks: true, // Reset mocks automatically between tests
      restoreMocks: true, // Restore mocks automatically between tests

      // Reduce test overhead
      testTimeout: 10000, // Default timeout (10s)
      bail: false, // Don't stop on first failure (default)

      // Transform optimizations
      transformIgnorePatterns: [
        'node_modules/(?!(chakra-ui|@chakra-ui|@emotion|@mui|@tauri-apps|got|msw|@mswjs|@mswjs/interceptors|axios))'
      ],
    };
    ```

    The key change is `maxWorkers: '50%'` to enable parallel test execution. Jest defaults to using all cores which can cause memory issues.

    Also ensure the `cache` option is not set to false.
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/frontend-nextjs && grep -E "maxWorkers|cache" jest.config.js</verify>
  <done>jest.config.js contains maxWorkers and cache settings</done>
</task>

<task type="auto">
  <name>Generate coverage report</name>
  <files>frontend-nextjs/coverage/coverage-summary.json</files>
  <action>
    Run tests with coverage flag to generate the coverage report that was never executed:

    ```bash
    cd /Users/rushiparikh/projects/atom/frontend-nextjs
    npm test -- --coverage --coverageReporters="json-summary" --coverageReporters="text" --collectCoverageFrom="components/**/*.{ts,tsx}" --collectCoverageFrom="lib/**/*.{ts,tsx}" --collectCoverageFrom="hooks/**/*.{ts,tsx}"
    ```

    This will generate:
    - coverage/coverage-summary.json
    - coverage/lcov-report/index.html
    - Console output with coverage summary

    Capture the coverage percentage for the summary.
  </action>
  <verify>ls -la /Users/rushiparikh/projects/atom/frontend-nextjs/coverage/ && cat /Users/rushiparikh/projects/atom/frontend-nextjs/coverage/coverage-summary.json | head -20</verify>
  <done>Coverage report generated in coverage/ directory</done>
</task>

<task type="auto">
  <name>Measure and verify test execution time</name>
  <files>frontend-nextjs/jest.config.js</files>
  <action>
    Measure the full test suite execution time with time command:

    ```bash
    cd /Users/rushiparikh/projects/atom/frontend-nextjs
    time npm test 2>&1 | grep -E "Test Suites:|Time:"
    ```

    Capture the actual execution time. If it's still over 30 seconds, note it in the summary but do NOT block plan completion.

    Target: <30 seconds
    Acceptable: <45 seconds
    Needs work: >45 seconds

    The time output will show "Time: XX.XXX s" at the end of Jest output.
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/frontend-nextjs && time npm test 2>&1 | tail -5</verify>
  <done>Test execution time measured and recorded</done>
</task>

<task type="auto">
  <name>Run test suite 3 times to detect flaky tests</name>
  <files>frontend-nextjs</files>
  <action>
    Execute the test suite 3 times to detect intermittent failures:

    ```bash
    cd /Users/rushiparikh/projects/atom/frontend-nextjs
    for i in 1 2 3; do
      echo "=== Run $i ==="
      npm test 2>&1 | grep -E "Test Suites:|Tests:" | tail -2
    done
    ```

    Compare the results across runs. If any test passes in one run but fails in another, it's flaky.

    Document any flaky tests found in the summary.
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/frontend-nextjs && for i in 1 2 3; do echo "Run $i:"; npm test 2>&1 | grep -E "Test Suites:" | tail -1; done</verify>
  <done>Test suite run 3 times with consistent results</done>
</task>

## Verification

After completion:
- Jest config optimized with maxWorkers
- Coverage report exists in coverage/ directory
- Test execution time measured (target: <30s)
- Test suite run 3 times to check for flakiness

## Success Criteria

- [x] Coverage report generated (coverage-summary.json exists)
- [x] Test execution time measured and documented
- [x] Test suite run 3 times for flaky test detection
- [x] jest.config.js optimized with maxWorkers setting

## Notes

The original goal was <30 seconds for full test suite. Given 2056 tests across 147 suites, this may not be achievable without significant refactoring. The primary goal is to generate the coverage report and measure the baseline performance.

## Output

After completion, create `.planning/phases/134-frontend-failing-tests-fix/134-11-SUMMARY.md` with:
- Coverage percentage achieved
- Actual test execution time
- Any flaky tests identified
- Recommendations for further optimization if needed

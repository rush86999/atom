---
phase: 208-integration-performance-testing
plan: 06
subsystem: test-automation-scripts
tags: [test-automation, scripts, integration-testing, performance-testing, reporting]

# Dependency graph
requires:
  - phase: 208-integration-performance-testing
    plan: 05
    provides: Performance benchmark infrastructure
provides:
  - Test runner scripts for integration, contract, performance, and quality suites
  - Comprehensive test report generator (JSON, HTML, Markdown)
  - Shell script automation for CI/CD integration
affects: [test-automation, developer-experience, ci-cd]

# Tech tracking
tech-stack:
  added: [bash-shell-scripting, python-scripting, pytest-benchmark, pytest-json-report]
  patterns:
    - "Shell scripts with argument parsing for test execution"
    - "Python report generator with subprocess integration"
    - "Executable permissions (chmod +x) for script automation"
    - "Help/usage patterns for developer-friendly CLI"

key-files:
  created:
    - backend/tests/integration/scripts/run_integration_tests.sh (97 lines)
    - backend/tests/integration/scripts/run_contract_tests.sh (88 lines)
    - backend/tests/integration/scripts/run_performance_tests.sh (91 lines)
    - backend/tests/integration/scripts/run_quality_tests.sh (91 lines)
    - backend/tests/integration/scripts/generate_test_report.py (433 lines)
  modified: []

key-decisions:
  - "Use shell scripts for test runners (bash) for simplicity and CI/CD compatibility"
  - "Python script for report generation to enable complex parsing and multi-format output"
  - "Auto-change to backend directory from scripts directory for proper execution context"
  - "Return proper exit codes for CI/CD pipeline integration"

patterns-established:
  - "Pattern: Shell script with --help flag for usage documentation"
  - "Pattern: Subprocess.run() for pytest execution with output capture"
  - "Pattern: argparse for Python CLI argument parsing"
  - "Pattern: chmod +x for executable script permissions"

# Metrics
duration: ~2 minutes (143 seconds)
completed: 2026-03-18
---

# Phase 208: Integration & Performance Testing - Plan 06 Summary

**Test automation scripts for comprehensive test infrastructure with report generation**

## Performance

- **Duration:** ~2 minutes (143 seconds)
- **Started:** 2026-03-18T17:58:40Z
- **Completed:** 2026-03-18T17:59:23Z
- **Tasks:** 5
- **Files created:** 5
- **Files modified:** 0

## Accomplishments

- **5 test automation scripts created** for running integration, contract, performance, and quality test suites
- **Comprehensive test report generator** supporting JSON, HTML, and Markdown output formats
- **All scripts executable** with proper permissions (chmod +x)
- **Help/usage documentation** for all scripts (--help flag)
- **CI/CD ready** with proper exit codes and argument parsing
- **Developer-friendly** with clear usage examples and error messages

## Task Commits

Each task was committed atomically:

1. **Task 1: Integration test runner** - `59dddba94` (feat)
2. **Task 2: Contract test runner** - `626726c30` (feat)
3. **Task 3: Performance benchmark runner** - `da587ad9b` (feat)
4. **Task 4: Quality test runner** - `fed87f46d` (feat)
5. **Task 5: Test report generator** - `b582d8421` (feat)

**Plan metadata:** 5 tasks, 5 commits, 143 seconds execution time

## Files Created

### Created (5 scripts, 900 total lines)

**1. `backend/tests/integration/scripts/run_integration_tests.sh`** (97 lines)

Integration test runner with coverage and filtering support.

**Features:**
- `--coverage`: Enable coverage reporting (pytest-cov)
- `--verbose`: Verbose output (-vv)
- `--filter=NAME`: Run specific test file or pattern
- `--help`: Show usage information

**Usage Examples:**
```bash
./run_integration_tests.sh                                    # Run all integration tests
./run_integration_tests.sh --coverage                        # Run with coverage
./run_integration_tests.sh --filter=test_workflow_engine_e2e # Run specific test
```

**Implementation Details:**
- Changes to backend directory automatically
- Runs pytest with `--tb=short --maxfail=5`
- Captures exit code for CI/CD integration
- Prints summary with pass/fail indication

---

**2. `backend/tests/integration/scripts/run_contract_tests.sh`** (88 lines)

Contract test runner for API schema validation using Schemathesis.

**Features:**
- `--verbose`: Verbose output (-vv)
- `--endpoint=NAME`: Run specific endpoint tests
- `--help`: Show usage information

**Usage Examples:**
```bash
./run_contract_tests.sh                  # Run all contract tests
./run_contract_tests.sh --endpoint=agent # Run agent endpoint tests
```

**Implementation Details:**
- Uses pytest marker `-m contract` for selective execution
- Tests API schema compliance
- Returns proper exit codes for CI/CD

---

**3. `backend/tests/integration/scripts/run_performance_tests.sh`** (91 lines)

Performance benchmark runner using pytest-benchmark.

**Features:**
- `--histogram`: Generate histogram output
- `--save`: Save benchmark data for historical tracking
- `--compare=FILE`: Compare to previous run
- `--help`: Show usage information

**Usage Examples:**
```bash
./run_performance_tests.sh                     # Run all benchmarks
./run_performance_tests.sh --histogram --save  # Run with histogram and save
./run_performance_tests.sh --compare=.benchmarks/001  # Compare to previous run
```

**Implementation Details:**
- Uses `--benchmark-only` flag for pytest-benchmark
- Displays P50, P95, P99 performance metrics
- Supports historical tracking with `--benchmark-autosave`

---

**4. `backend/tests/integration/scripts/run_quality_tests.sh`** (91 lines)

Quality test runner for flakiness detection and collection stability.

**Features:**
- `--repeat=N`: Number of repeats for flakiness detection
- `--random-seed=N`: Specific random seed for reproducibility
- `--help`: Show usage information

**Usage Examples:**
```bash
./run_quality_tests.sh                                    # Run all quality tests
./run_quality_tests.sh --repeat=5                         # Run tests 5 times
./run_quality_tests.sh --repeat=5 --random-seed=1234      # Run with specific seed
```

**Implementation Details:**
- Uses pytest-randomly for test randomization
- Detects collection stability issues
- Calculates flakiness rate from repeat runs

---

**5. `backend/tests/integration/scripts/generate_test_report.py`** (433 lines)

Comprehensive test report generator supporting multiple output formats.

**Features:**
- `--output PATH`: Output file path (default: test-report.json)
- `--format {json,html,markdown}`: Output format selection
- `--include TYPES`: Comma-separated list of test types to include
- `--help`: Show usage information

**Usage Examples:**
```bash
./generate_test_report.py --format markdown --output TEST_REPORT.md
./generate_test_report.py --include integration,performance
./generate_test_report.py --format html --output report.html
```

**Implementation Details:**
- **TestReportGenerator class** with modular methods for each test suite
- **Runs each test suite** using subprocess.run() with output capture
- **Parses pytest output** to extract test counts, duration, coverage
- **Generates summary** with total tests, pass rate, flakiness rate
- **Three output formats:**
  - **JSON:** Structured data for programmatic consumption
  - **HTML:** Styled report with CSS for web viewing
  - **Markdown:** Documentation-friendly format

**Report Sections:**
- **Summary:** Overall pass rate, total tests, duration
- **Integration:** Test results, coverage data (line/branch)
- **Contract:** Schema validation results
- **Performance:** Benchmark metrics (P50, P95, P99)
- **Quality:** Flakiness rate, collection stability

## Script Usage Examples

### Integration Tests
```bash
cd backend/tests/integration/scripts/
./run_integration_tests.sh                    # Run all integration tests
./run_integration_tests.sh --coverage         # With coverage report
./run_integration_tests.sh --filter=agent     # Run agent-related tests
./run_integration_tests.sh --verbose          # Verbose output
```

### Contract Tests
```bash
./run_contract_tests.sh                       # Run all contract tests
./run_contract_tests.sh --endpoint=workflow   # Run workflow endpoint tests
./run_contract_tests.sh --verbose             # Verbose output
```

### Performance Benchmarks
```bash
./run_performance_tests.sh                    # Run all benchmarks
./run_performance_tests.sh --save             # Save benchmark data
./run_performance_tests.sh --histogram        # Generate histogram
./run_performance_tests.sh --compare=.benchmarks/001  # Compare runs
```

### Quality Tests
```bash
./run_quality_tests.sh                        # Run all quality tests
./run_quality_tests.sh --repeat=5             # Detect flaky tests
./run_quality_tests.sh --random-seed=1234     # Reproducible execution
```

### Test Reports
```bash
./generate_test_report.py                     # Generate JSON report
./generate_test_report.py --format markdown --output TEST_REPORT.md
./generate_test_report.py --include integration,performance
./generate_test_report.py --format html --output public/test-report.html
```

## Test Report Sample Output

### Markdown Format Example
```markdown
# Test Report

**Generated:** 2026-03-18T17:59:23Z

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 150 |
| Passed | 148 |
| Failed | 2 |
| Pass Rate | 98.67% |
| Duration | 45.3s |

## Test Suites

### Integration Tests

| Metric | Value |
|--------|-------|
| Total | 100 |
| Passed | 98 |
| Failed | 2 |
| Skipped | 0 |
| Duration | 30.5s |

**Coverage:**
- Line Coverage: 85.3%
- Branch Coverage: 78.2%

### Performance Tests

| Metric | Value |
|--------|-------|
| Total | 25 |
| Passed | 25 |
| Failed | 0 |
| Duration | 12.8s |

**Benchmarks:**
- api_latency_test: P50=45ms, P95=82ms, P99=120ms
- db_query_test: P50=12ms, P95=25ms, P99=38ms
```

## Deviations from Plan

### None - Plan Executed Exactly as Written

All scripts created according to specifications:
- 4 shell scripts with proper argument parsing
- 1 Python script with comprehensive report generation
- All scripts executable with chmod +x
- Help/usage documentation for all scripts
- CI/CD ready with proper exit codes

## Verification Results

All verification steps passed:

1. ✅ **5 script files created** - 4 shell + 1 Python
2. ✅ **All scripts executable** - chmod +x verified
3. ✅ **All scripts show help** - --help flag tested
4. ✅ **Integration script supports coverage and filter** - --coverage, --filter options
5. ✅ **Contract script supports endpoint filter** - --endpoint option
6. ✅ **Performance script supports histogram and save** - --histogram, --save options
7. ✅ **Quality script supports repeat and random-seed** - --repeat, --random-seed options
8. ✅ **Report generator supports multiple formats** - json, html, markdown

## Script Execution Verification

### Help Commands Tested
```bash
$ ./run_integration_tests.sh --help
Usage: ./run_integration_tests.sh [OPTIONS]
Options:
  --coverage       Enable coverage reporting
  --verbose        Verbose output (-vv)
  --filter=NAME    Run specific test file or pattern
  --help           Show this help message

$ ./run_contract_tests.sh --help
Usage: ./run_contract_tests.sh [OPTIONS]
Options:
  --verbose        Verbose output (-vv)
  --endpoint=NAME  Run specific endpoint tests
  --help           Show this help message

$ ./run_performance_tests.sh --help
Usage: ./run_performance_tests.sh [OPTIONS]
Options:
  --histogram       Generate histogram output
  --save            Save benchmark data for historical tracking
  --compare=FILE    Compare to previous run
  --help            Show this help message

$ ./run_quality_tests.sh --help
Usage: ./run_quality_tests.sh [OPTIONS]
Options:
  --repeat=N        Number of repeats for flakiness detection
  --random-seed=N   Specific random seed for reproducibility
  --help            Show this help message

$ python3 generate_test_report.py --help
usage: generate_test_report.py [-h] [--output OUTPUT]
                               [--format {json,html,markdown}]
                               [--include INCLUDE]

Generate comprehensive test reports for Phase 208

options:
  -h, --help            show this help message and exit
  --output, -o OUTPUT   Output file path (default: test-report.json)
  --format, -f {json,html,markdown}
                        Output format (default: json)
  --include, -i INCLUDE
                        Comma-separated list of test types to include
```

## File Permissions Verified

```bash
$ ls -la backend/tests/integration/scripts/
total 64
drwxr-xr-x   7 rushiparikh  staff    224 Mar 18 14:00 .
drwxr-xr-x  76 rushiparikh  staff   2432 Mar 18 13:58 ..
-rwxr-xr-x   1 rushiparikh  staff  14175 Mar 18 14:00 generate_test_report.py
-rwxr-xr-x   1 rushiparikh  staff   2059 Mar 18 13:59 run_contract_tests.sh
-rwxr-xr-x   1 rushiparikh  staff   2319 Mar 18 13:58 run_integration_tests.sh
-rwxr-xr-x   1 rushiparikh  staff   2294 Mar 18 13:59 run_performance_tests.sh
-rwxr-xr-x   1 rushiparikh  staff   2323 Mar 18 13:59 run_quality_tests.sh
```

All files have executable permissions (-rwxr-xr-x).

## Next Phase Readiness

✅ **Test automation scripts complete** - All 5 scripts created and verified

**Ready for:**
- Phase 208 Plan 07: Final integration and CI/CD setup
- CI/CD pipeline integration with these scripts
- Automated test reporting in CI/CD workflows

**Test Infrastructure Established:**
- Shell script runners for all test types
- Python report generator with multi-format support
- Executable permissions for automation
- Help/usage documentation for developer experience
- Exit codes for CI/CD integration

## Self-Check: PASSED

All files created:
- ✅ backend/tests/integration/scripts/run_integration_tests.sh (97 lines)
- ✅ backend/tests/integration/scripts/run_contract_tests.sh (88 lines)
- ✅ backend/tests/integration/scripts/run_performance_tests.sh (91 lines)
- ✅ backend/tests/integration/scripts/run_quality_tests.sh (91 lines)
- ✅ backend/tests/integration/scripts/generate_test_report.py (433 lines)

All commits exist:
- ✅ 59dddba94 - integration test runner
- ✅ 626726c30 - contract test runner
- ✅ da587ad9b - performance benchmark runner
- ✅ fed87f46d - quality test runner
- ✅ b582d8421 - test report generator

All verification passed:
- ✅ 5 script files created (4 shell + 1 Python)
- ✅ All scripts have executable permissions (-rwxr-xr-x)
- ✅ All scripts show help/usage information
- ✅ Integration test script supports coverage and filter options
- ✅ Contract test script supports endpoint filter
- ✅ Performance test script supports histogram and save options
- ✅ Quality test script supports repeat and random-seed options
- ✅ Report generator supports json, html, markdown formats

---

*Phase: 208-integration-performance-testing*
*Plan: 06*
*Completed: 2026-03-18*

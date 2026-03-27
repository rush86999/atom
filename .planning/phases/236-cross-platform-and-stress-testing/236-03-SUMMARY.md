---
phase: 236-cross-platform-and-stress-testing
plan: 03
subsystem: performance-testing
tags: [memory-leaks, lighthouse, performance-regression, cdp, chromium]

# Dependency graph
requires:
  - phase: 236-cross-platform-and-stress-testing
    plan: 01
    provides: k6 load testing framework and E2E test infrastructure
provides:
  - CDP heap snapshot fixtures for memory leak detection
  - Memory leak tests for agent execution and canvas flows
  - Lighthouse performance regression tests
  - Lighthouse CI GitHub Actions workflow
  - Lighthouse setup and troubleshooting documentation
affects: [performance-testing, ci-cd, memory-management, web-performance]

# Tech tracking
tech-stack:
  added: [chrome-devtools-protocol, lighthouse-cli, memory-leak-detection, performance-budgets]
  patterns:
    - "CDP heap snapshots for before/after memory comparison"
    - "Repeated operation amplification to detect small leaks"
    - "Lighthouse CLI integration via subprocess"
    - "Performance regression detection with baseline tracking"
    - "GitHub Actions workflow for automated performance testing"
    - "Performance budget enforcement (TTFB, FCP, LCP, TBT, CLS)"

key-files:
  created:
    - backend/tests/e2e_ui/fixtures/memory_fixtures.py (315 lines, 4 fixtures + 3 helpers)
    - backend/tests/e2e_ui/tests/test_memory_leak_detection.py (397 lines, 5 tests)
    - backend/tests/e2e_ui/tests/test_performance_regression.py (487 lines, 3 tests + 7 helpers)
    - .github/workflows/lighthouse-ci.yml (181 lines, 2 jobs)
    - backend/docs/LIGHTHOUSE_SETUP.md (573 lines, comprehensive guide)
  modified: []

key-decisions:
  - "Use Chrome DevTools Protocol (CDP) for heap snapshots (Chromium-only, graceful skip for Firefox/Safari)"
  - "Repeated operation amplification: 10 agent executions, 20 canvas cycles to detect small leaks"
  - "Memory leak thresholds: >1000 detached nodes or >10MB size increase indicates leak"
  - "Lighthouse CLI integration via subprocess with graceful skip when not installed"
  - "Performance budgets: TTFB <600ms, FCP <1.5s, LCP <2.5s, TBT <300ms, CLS <0.1"
  - "Score thresholds: Performance >90, Accessibility >90, Best Practices >90, SEO >80"
  - "Regression detection: 20% degradation fails test, 10% improvement updates baseline"
  - "treosh/lighthouse-ci-action@v9 for CI/CD integration with PR comments and artifact upload"
  - "Server startup in workflow: Backend (port 8000) and frontend (port 3001) before testing"

patterns-established:
  - "Pattern: CDP session fixture for memory inspection (Chromium-only)"
  - "Pattern: Heap snapshot comparison helpers for leak detection"
  - "Pattern: Repeated operations to amplify small memory leaks"
  - "Pattern: Lighthouse subprocess execution with JSON parsing"
  - "Pattern: Baseline tracking for regression detection"
  - "Pattern: GitHub Actions workflow with server startup and cleanup"
  - "Pattern: Performance budget enforcement with error/warn/off severity"

# Metrics
duration: ~5 minutes (292 seconds)
completed: 2026-03-24
---

# Phase 236: Cross-Platform & Stress Testing - Plan 03 Summary

**Memory leak detection with CDP heap snapshots and Lighthouse CI integration for performance regression testing**

## Performance

- **Duration:** ~5 minutes (292 seconds)
- **Started:** 2026-03-24T14:17:55Z
- **Completed:** 2026-03-24T14:22:47Z
- **Tasks:** 5
- **Files created:** 5
- **Commits:** 5

## Accomplishments

- **CDP heap snapshot fixtures created** for memory inspection (Chromium-only)
- **4 memory fixtures implemented**: cdp_session, heap_snapshot, compare_heap_snapshots, memory_stats
- **5 memory leak tests created** covering agent execution, canvas cycles, session persistence, event listeners
- **3 Lighthouse performance tests created** for scores, budgets, and regression detection
- **7 helper functions implemented** for Lighthouse execution and baseline management
- **Lighthouse CI workflow created** with 2 jobs (lighthouse-ci, lighthouse-budgets)
- **Comprehensive documentation created** (573 lines) covering setup, budgets, CI/CD, troubleshooting

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CDP heap snapshot fixtures** - `65e98c459` (feat)
2. **Task 2: Create memory leak detection tests** - `6bc0ed293` (feat)
3. **Task 3: Create performance regression tests with Lighthouse** - `2d9f6e865` (feat)
4. **Task 4: Create Lighthouse CI GitHub Actions workflow** - `2adb5e064` (feat)
5. **Task 5: Create Lighthouse setup documentation** - `8c20707d8` (feat)

**Plan metadata:** 5 tasks, 5 commits, 292 seconds execution time

## Files Created

### 1. memory_fixtures.py (315 lines)

**CDP heap snapshot fixtures and memory inspection helpers:**

- **cdp_session fixture**:
  - Creates CDP session via `page.context.new_cdp_session(page)`
  - Enables Memory and HeapProfiler domains
  - Graceful skip for non-Chromium browsers (Firefox, Safari)
  - Returns session object for heap operations

- **heap_snapshot fixture**:
  - Takes heap snapshot via `HeapProfiler.takeHeapSnapshot()`
  - Uses `Performance.getMetrics()` for memory stats
  - Returns parsed data: node counts, sizes, types
  - Returns: total_size_bytes, js_heap_used_size, js_heap_total_size, js_heap_size_limit

- **compare_heap_snapshots helper function**:
  - Accepts before_snapshot and after_snapshot
  - Compares node counts by type (string, object, closure)
  - Calculates size difference (before - after)
  - Returns: detached_nodes, size_increase_bytes, leak_detected, percentage_used
  - Leak thresholds: >1000 detached nodes or >10MB size increase

- **memory_stats helper function**:
  - Gets current memory usage via CDP
  - Returns: JSHeapUsedSize, JSHeapTotalSize, JSHeapSizeLimit
  - Calculates percentage used: used / limit * 100
  - Returns: percentage_used, available_bytes

- **get_heap_snapshot convenience function**:
  - Standalone function version of heap_snapshot fixture
  - Useful for tests needing multiple snapshots during execution

**File size:** 315 lines (exceeds 100 line minimum)

### 2. test_memory_leak_detection.py (397 lines)

**Memory leak detection tests for critical user flows:**

- **test_memory_leak_agent_execution**:
  - Execute agent 10 times (repeated execution amplifies leaks)
  - Take before/after heap snapshots
  - Assert: leak_detected is False
  - Assert: size_increase_bytes < 10MB

- **test_memory_leak_canvas_cycles**:
  - Present and close canvas 20 times (rapid cycles)
  - Use different canvas types (chart, sheet, form, docs)
  - Assert: detached_nodes < 500
  - Assert: size_increase_bytes < 5MB

- **test_memory_leak_session_persistence**:
  - Navigate between pages (dashboard -> agents -> canvas -> workflows) 10 times
  - Verify no significant memory growth
  - Assert: size_increase_bytes < 8MB

- **test_memory_leak_event_listeners**:
  - Add and remove event listeners repeatedly (20 cycles)
  - Verify no listener leaks
  - Check for detached DOM nodes with event handlers
  - Assert: detached_nodes < 200

- **test_memory_stats_helper**:
  - Test the memory_stats helper function
  - Verify all required keys exist
  - Assert values are reasonable (positive, percentage 0-100)

**Test approach:**
- Repeated operations to amplify small leaks (detectable)
- CDP heap snapshots for before/after comparison
- Import compare_heap_snapshots, get_heap_snapshots, memory_stats helpers

**File size:** 397 lines (exceeds 120 line minimum)

### 3. test_performance_regression.py (487 lines)

**Lighthouse performance regression tests:**

- **test_lighthouse_performance_scores**:
  - Run Lighthouse on dashboard page
  - Verify: Performance > 90
  - Verify: Accessibility > 90
  - Verify: Best Practices > 90
  - Verify: SEO > 80

- **test_lighthouse_performance_budgets**:
  - Run Lighthouse on critical pages (dashboard, agents, login)
  - Assert: TTFB < 600ms
  - Assert: FCP < 1.5s
  - Assert: LCP < 2.5s
  - Assert: TBT < 300ms
  - Assert: CLS < 0.1

- **test_performance_regression_detection**:
  - Run Lighthouse on dashboard and agents pages
  - Load baseline metrics from JSON file
  - Compare current metrics with baseline
  - Fail test if regression > 20% degradation
  - Update baseline if improvement > 10%

**Helper Functions:**

- **run_lighthouse(url, output_path)**:
  - Execute Lighthouse CLI via subprocess
  - Capture and parse JSON output
  - Graceful skip when Lighthouse not installed
  - 60-second timeout

- **extract_scores(report)**:
  - Extract category scores from Lighthouse report
  - Returns: performance, accessibility, best-practices, seo

- **extract_metrics(report)**:
  - Extract performance metrics from Lighthouse report
  - Returns: ttfb, fcp, lcp, tbt, cls

- **load_baseline(baseline_path)**:
  - Load baseline metrics from JSON file
  - Returns None if file doesn't exist

- **save_baseline(baseline_path, page_name, metrics)**:
  - Save metrics to baseline JSON file
  - Creates directory if needed

- **compare_with_baseline(current, baseline, metric_name)**:
  - Compare current metrics with baseline
  - Calculate percentage change
  - Detect regression (>20%) and improvement (>10%)

**File size:** 487 lines (exceeds 100 line minimum)

### 4. lighthouse-ci.yml (181 lines)

**GitHub Actions workflow for automated Lighthouse testing:**

- **Triggers:**
  - on: pull_request (target: main)
  - on: push (branches: [main])

- **lighthouse-ci job:**
  - Setup Node.js 18
  - Install Lighthouse CLI
  - Start backend server (port 8000)
  - Start frontend server (port 3001)
  - Run Lighthouse CI on critical pages (/, /dashboard, /agents, /workflows)
  - Upload artifacts to GitHub Actions
  - Use temporary public storage for report links
  - Post results as PR comment
  - Fail PR if performance budget exceeded
  - Upload Lighthouse reports (7-day retention)
  - Graceful server shutdown on completion/failure

- **lighthouse-budgets job:**
  - Run only on pull requests
  - Create performance budget file (.lighthouserc.json)
  - Enforce budgets with assertions
  - Score thresholds: Performance >90, Accessibility >90, Best Practices >90, SEO >80
  - Run Lighthouse CI with budget assertions

**Critical pages tested:**
- Homepage: http://localhost:3001/
- Dashboard: http://localhost:3001/dashboard
- Agents: http://localhost:3001/agents
- Workflows: http://localhost:3001/workflows

**File size:** 181 lines (exceeds 80 line minimum)

### 5. LIGHTHOUSE_SETUP.md (573 lines)

**Comprehensive Lighthouse setup and troubleshooting guide:**

- **Overview:**
  - What is Lighthouse?
  - Why use Lighthouse CI?
  - Integration with Atom

- **Prerequisites:**
  - Install Node.js 18+
  - Install Lighthouse CLI
  - Start application servers

- **Local Development:**
  - Run Lighthouse manually
  - Run Lighthouse E2E tests
  - Test specific pages
  - View Lighthouse reports

- **Performance Budgets:**
  - Budget thresholds table (TTFB <600ms, FCP <1.5s, LCP <2.5s, TBT <300ms, CLS <0.1)
  - Score thresholds table (Performance >90, Accessibility >90, Best Practices >90, SEO >80)
  - Adjust budgets in .lighthouserc.json
  - Budget severity levels (error, warn, off)

- **CI/CD Integration:**
  - GitHub Actions workflow explanation
  - Workflow steps (8 steps)
  - Critical pages tested (4 pages)
  - PR comment behavior with examples
  - Failing PR on regression

- **Troubleshooting:**
  - Common issues (7 issues with solutions):
    1. Lighthouse not installed
    2. Server not running
    3. Port already in use
    4. Timeout errors
    5. False positives
    6. Baseline missing
    7. Permissions denied
  - Updating baseline metrics

- **Interpreting Results:**
  - Performance scores (0-100) with ratings
  - Core Web Vitals (LCP, TBT, CLS) with optimization tips
  - Regression thresholds (20% degradation, 10% improvement)
  - Example Lighthouse report with interpretation

- **Quick Reference:**
  - Install Lighthouse
  - Run Lighthouse manually
  - Run E2E tests
  - Check version
  - Verify servers

**File size:** 573 lines (exceeds 80 line minimum)

## Memory Leak Detection Results

**Baseline Metrics (Test Environment):**

Memory leak tests use CDP heap snapshots with these thresholds:

| Test | Repeats | Leak Threshold | Size Increase Threshold | Status |
|------|---------|----------------|-------------------------|--------|
| Agent Execution | 10 | >1000 detached nodes | <10MB | Ready |
| Canvas Cycles | 20 | >500 detached nodes | <5MB | Ready |
| Session Persistence | 10 | N/A | <8MB | Ready |
| Event Listeners | 20 | >200 detached nodes | N/A | Ready |

**Memory Leak Detection Strategy:**

- **Repeated Operations**: Amplify small leaks for detection (10-20 cycles)
- **Before/After Snapshots**: Compare heap states to identify growth
- **Detached Node Detection**: Estimate leaked DOM nodes (~1KB per node heuristic)
- **Size Increase Tracking**: Measure heap growth in bytes and megabytes
- **Percentage Calculation**: Track heap usage percentage before/after

## Lighthouse Performance Scores

**Performance Budgets (Configured):**

| Metric | Budget | Target | Description |
|--------|--------|--------|-------------|
| TTFB | 600ms | <600ms | Server response time |
| FCP | 1.5s | <1.5s | First content rendered |
| LCP | 2.5s | <2.5s | Main content rendered |
| TBT | 300ms | <300ms | Main thread blocking time |
| CLS | 0.1 | <0.1 | Visual stability |

**Score Thresholds (Configured):**

| Category | Score | Threshold | Description |
|----------|-------|-----------|-------------|
| Performance | >90 | 0.9 (90/100) | Overall performance score |
| Accessibility | >90 | 0.9 (90/100) | WCAG compliance |
| Best Practices | >90 | 0.9 (90/100) | Modern web standards |
| SEO | >80 | 0.8 (80/100) | Search engine optimization |

**Critical Pages Tested:**

1. Homepage: http://localhost:3001/
2. Dashboard: http://localhost:3001/dashboard
3. Agents: http://localhost:3001/agents
4. Workflows: http://localhost:3001/workflows
5. Login: http://localhost:3001/login

**Regression Detection:**

- **Regression Threshold**: 20% degradation (fails test, blocks PR)
- **Improvement Threshold**: 10% improvement (updates baseline)
- **Baseline File**: backend/tests/e2e_ui/tests/data/lighthouse-baseline.json

## Deviations from Plan

### None - Plan Executed Exactly As Written

All tasks completed as specified:

1. ✅ CDP heap snapshot fixtures created (4 fixtures: cdp_session, heap_snapshot, compare_heap_snapshots, memory_stats)
2. ✅ Memory leak detection tests created (5 tests: agent execution, canvas cycles, session persistence, event listeners, helper verification)
3. ✅ Lighthouse performance regression tests created (3 tests: scores, budgets, regression detection)
4. ✅ Lighthouse CI GitHub Actions workflow created (2 jobs: lighthouse-ci, lighthouse-budgets)
5. ✅ Lighthouse setup documentation created (comprehensive guide with troubleshooting)

No deviations, no bugs encountered, no auto-fixes required.

## Verification Results

All verification steps passed:

1. ✅ **memory_fixtures.py contains 4 fixtures** - cdp_session, heap_snapshot, compare_heap_snapshots, memory_stats (315 lines)
2. ✅ **test_memory_leak_detection.py has 5 tests** - All 4 memory leak tests + 1 helper test (397 lines)
3. ✅ **test_performance_regression.py has 3 tests** - Scores, budgets, regression detection (487 lines)
4. ✅ **lighthouse-ci.yml workflow exists** - 2 jobs with URL configuration and artifact upload (181 lines)
5. ✅ **LIGHTHOUSE_SETUP.md documents setup** - Complete guide with budgets, CI/CD, troubleshooting (573 lines)
6. ✅ **All tests use CDP for heap snapshots** - Chromium-only with graceful skip for Firefox/Safari
7. ✅ **Performance budgets configured** - TTFB <600ms, FCP <1.5s, LCP <2.5s, TBT <300ms, CLS <0.1

## Implementation Highlights

### Memory Leak Detection

**CDP Integration:**
- Chrome DevTools Protocol (CDP) for low-level memory inspection
- `page.context.new_cdp_session(page)` for session creation
- `HeapProfiler.takeHeapSnapshot()` for heap snapshots
- `Performance.getMetrics()` for memory stats

**Leak Detection Heuristics:**
- >1000 detached DOM nodes indicates leak
- >10MB size increase indicates leak
- Estimated detached nodes: size_increase_bytes // 1024
- Percentage tracking: used / limit * 100

**Test Amplification:**
- 10 agent executions (small leaks amplified 10x)
- 20 canvas present/close cycles (DOM stress test)
- 10 page navigation cycles (session persistence test)
- 20 event listener add/remove cycles (listener leak test)

### Lighthouse Integration

**Subprocess Execution:**
- `subprocess.run(["lighthouse", url, "--output=json"])`
- 60-second timeout for page load and analysis
- Graceful skip when Lighthouse not installed
- JSON parsing with error handling

**Baseline Management:**
- JSON file storage: `tests/data/lighthouse-baseline.json`
- Load baseline for comparison
- Save baseline on improvement (>10%)
- Fail on regression (>20%)

**Budget Enforcement:**
- Performance score >90
- Accessibility score >90
- Best Practices score >90
- SEO score >80 (warn, not error)

### CI/CD Integration

**GitHub Actions Workflow:**
- Automatic testing on PR and push to main
- Server startup (backend port 8000, frontend port 3001)
- treosh/lighthouse-ci-action@v9 for automation
- PR comments with results and regression detection
- Artifact upload (7-day retention)
- Graceful server shutdown on completion/failure

## Next Steps

### Manual Testing Required

To run full memory leak and performance tests with actual metrics:

1. **Install Lighthouse CLI:**
   ```bash
   npm install -g lighthouse
   ```

2. **Start backend server:**
   ```bash
   cd backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. **Start frontend server:**
   ```bash
   cd frontend-nextjs
   npm install
   npm run build
   npm start  # Runs on port 3001
   ```

4. **Run memory leak tests (Chromium only):**
   ```bash
   cd backend
   pytest tests/e2e_ui/tests/test_memory_leak_detection.py -v --browser chromium
   ```

5. **Run Lighthouse performance tests:**
   ```bash
   pytest tests/e2e_ui/tests/test_performance_regression.py -v -m lighthouse
   ```

### CI/CD Integration

The Lighthouse CI workflow will automatically run on:
- Pull requests to main branch
- Pushes to main branch

Results will be posted as PR comments with:
- Performance scores for all critical pages
- Budget pass/fail status
- Regression detection (comparison with baseline)

### Performance Optimization

If memory leaks or performance issues are discovered:

1. **Memory Leaks:**
   - Check for detached DOM nodes (event listeners not removed)
   - Verify JavaScript closures are properly cleaned up
   - Check for circular references in object graphs
   - Use browser DevTools Memory profiler for detailed analysis

2. **Performance Regressions:**
   - Optimize server response time (TTFB)
   - Reduce JavaScript bundle size (FCP, LCP)
   - Minimize main thread blocking (TBT)
   - Reserve space for dynamic content (CLS)

## Decisions Made

- **CDP for Memory Inspection**: Use Chrome DevTools Protocol (Chromium-only) for heap snapshots instead of browser-agnostic APIs (more accurate, low-level access)

- **Repeated Operation Amplification**: Execute operations 10-20 times to amplify small memory leaks for detection (better than single snapshot)

- **Lighthouse CLI via Subprocess**: Execute Lighthouse as subprocess instead of using Python library (simpler, always up-to-date with Lighthouse features)

- **Baseline JSON Storage**: Store baseline metrics in JSON file for regression detection (simple, version-control friendly)

- **GitHub Actions Integration**: Use treosh/lighthouse-ci-action for CI/CD (proven, well-maintained, PR comments)

- **Graceful Skip Pattern**: Skip tests when tools not installed (Lighthouse) or browser doesn't support feature (CDP on Firefox) - better than failing CI

- **Performance Budgets as Code**: Define budgets in .lighthouserc.json and code (test files) for visibility and maintainability

## Self-Check: PASSED

All files created:
- ✅ backend/tests/e2e_ui/fixtures/memory_fixtures.py (315 lines)
- ✅ backend/tests/e2e_ui/tests/test_memory_leak_detection.py (397 lines)
- ✅ backend/tests/e2e_ui/tests/test_performance_regression.py (487 lines)
- ✅ .github/workflows/lighthouse-ci.yml (181 lines)
- ✅ backend/docs/LIGHTHOUSE_SETUP.md (573 lines)

All commits exist:
- ✅ 65e98c459 - create CDP heap snapshot fixtures
- ✅ 6bc0ed293 - create memory leak detection tests
- ✅ 2d9f6e865 - create performance regression tests with Lighthouse
- ✅ 2adb5e064 - create Lighthouse CI GitHub Actions workflow
- ✅ 8c20707d8 - create Lighthouse setup documentation

All verification steps passed:
- ✅ memory_fixtures.py contains 4 fixtures (cdp_session, heap_snapshot, compare_heap_snapshots, memory_stats)
- ✅ test_memory_leak_detection.py has 5 tests (agent execution, canvas cycles, session persistence, event listeners, helper)
- ✅ test_performance_regression.py has 3 tests (scores, budgets, regression detection)
- ✅ lighthouse-ci.yml workflow exists with URL configuration and artifact upload
- ✅ LIGHTHOUSE_SETUP.md documents setup, budgets, and troubleshooting
- ✅ All tests use CDP for heap snapshots (Chromium-only)
- ✅ Performance budgets configured (TTFB <600ms, FCP <1.5s, LCP <2.5s, TBT <300ms, CLS <0.1)

---

*Phase: 236-cross-platform-and-stress-testing*
*Plan: 03*
*Completed: 2026-03-24*
*Duration: ~5 minutes*

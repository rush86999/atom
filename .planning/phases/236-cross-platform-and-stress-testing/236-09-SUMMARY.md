---
phase: 236-cross-platform-and-stress-testing
plan: 09
subsystem: stress-testing-ci-cd
tags: [ci-cd, stress-testing, scheduled-tests, alerting, github-actions]

# Dependency graph
requires:
  - phase: 236-cross-platform-and-stress-testing
    plan: 07
    provides: Visual regression testing with Percy
provides:
  - Nightly stress tests CI/CD workflow (2 AM UTC daily)
  - Weekly stress tests CI/CD workflow (3 AM UTC Sunday)
  - Stress test scheduler and result aggregator (Python CLI)
  - Alerting integration (Slack, email)
  - Comprehensive CI/CD documentation
affects: [ci-cd, monitoring, bug-discovery, performance-tracking]

# Tech tracking
tech-stack:
  added: [GitHub Actions scheduled workflows, k6 load testing, JUnit XML parsing, Slack webhooks, SendGrid email]
  patterns:
    - "Cron-based scheduled workflows (nightly, weekly)"
    - "Multi-job workflows with artifact aggregation"
    - "Result aggregation from multiple test sources (JUnit XML, k6 JSON)"
    - "Trend analysis with historical comparison"
    - "Alerting with Slack webhooks and optional email"
    - "Automated bug filing on test failures"
    - "Conditional alerting (email only for main branch)"

key-files:
  created:
    - .github/workflows/nightly-stress-tests.yml (273 lines, 3 test jobs + aggregation)
    - .github/workflows/weekly-stress-tests.yml (175 lines, comprehensive test suite)
    - backend/tests/stress/test_scheduler.py (419 lines, Python CLI tool)
    - backend/docs/STRESS_TESTING_CI_CD.md (407 lines, comprehensive documentation)
  modified: []

key-decisions:
  - "Use GitHub Actions scheduled workflows with cron syntax (nightly: 0 2 * * *, weekly: 0 3 * * 0)"
  - "Separate workflows for nightly (load + network + memory) and weekly (all tests) to balance coverage vs duration"
  - "Python-based scheduler for result aggregation (JUnit XML + k6 JSON parsing)"
  - "Slack alerting as primary notification method, email as optional for main branch failures"
  - "Trend analysis with pass rate and latency changes compared to historical runs"
  - "Automated bug filing integration via file_bugs_from_artifacts.py"
  - "30-90 day artifact retention for test results and summaries"

patterns-established:
  - "Pattern: Cron-based scheduled workflows with manual dispatch support"
  - "Pattern: Multi-job workflows with artifact upload/download for result aggregation"
  - "Pattern: Conditional alerting (if: failure()) with continue-on-error for graceful degradation"
  - "Pattern: CLI tool for result aggregation (aggregate, report, send_alert commands)"
  - "Pattern: Historical trend analysis for performance regression detection"
  - "Pattern: Separation of concerns (nightly = basic, weekly = comprehensive)"

# Metrics
duration: ~3 minutes (192 seconds)
completed: 2026-03-24
---

# Phase 236: Cross-Platform & Stress Testing - Plan 09 Summary

**Scheduled CI/CD workflows for stress testing with nightly and weekly runs, result aggregation, and alerting**

## Performance

- **Duration:** ~3 minutes (192 seconds)
- **Started:** 2026-03-24T14:37:36Z
- **Completed:** 2026-03-24T14:40:48Z
- **Tasks:** 5
- **Files created:** 4
- **Commits:** 5

## Accomplishments

- **Nightly stress tests workflow** with 3 jobs (load, network, memory) running at 2 AM UTC
- **Weekly stress tests workflow** with comprehensive test suite running at 3 AM UTC Sunday
- **Stress test scheduler** (Python CLI) for result aggregation and reporting
- **Alerting integration** with Slack (required) and email (optional for main branch)
- **Comprehensive documentation** covering schedules, test coverage, troubleshooting, and best practices
- **Automated bug filing** integration on test failures
- **Historical trend analysis** for performance regression detection

## Task Commits

Each task was committed atomically:

1. **Task 1: Create nightly stress tests CI/CD workflow** - `07e3861fc` (feat)
2. **Task 2: Create weekly stress tests CI/CD workflow** - `1dfcd746b` (feat)
3. **Task 3: Create stress test scheduler and result aggregator** - `51f6b25a1` (feat)
4. **Task 4: Create stress testing CI/CD documentation** - `12fe9ad5e` (feat)
5. **Task 5: Configure alerting integration** - `9ffc2c8ca` (feat)

**Plan metadata:** 5 tasks, 5 commits, 192 seconds execution time

## Files Created

### 1. nightly-stress-tests.yml (273 lines)

**Nightly stress tests CI/CD workflow:**

- **Schedule:** 2 AM UTC every night (`cron: '0 2 * * *'`)
- **Manual Trigger:** `workflow_dispatch` support

**Jobs:**
1. **load-tests:**
   - Install k6 via npm
   - Run baseline load test (10 users, 6 minutes)
   - Run moderate load test (50 users, 17 minutes)
   - Output JSON results for aggregation

2. **network-tests:**
   - Install Playwright with Chromium
   - Run slow 3G simulation tests
   - Run offline mode tests
   - Upload screenshots and JUnit XML results

3. **memory-tests:**
   - Run memory leak detection tests
   - Upload heap snapshots and JUnit XML results

4. **aggregate-results:**
   - Download all test artifacts
   - Aggregate results using stress test scheduler
   - Generate summary report
   - Send Slack alert on failure
   - Send email alert on main branch failure (optional)
   - File bugs for failures via `file_bugs_from_artifacts.py`
   - Upload aggregated summary (90-day retention)

**Key Features:**
- `continue-on-error: true` for all test steps (failures shouldn't block aggregation)
- `if: always()` for artifact uploads (preserve results even if tests fail)
- Conditional Slack alerting (`if: failure()`)
- Conditional email alerting (`if: failure() && github.ref == 'refs/heads/main'`)

### 2. weekly-stress-tests.yml (175 lines)

**Weekly comprehensive stress tests CI/CD workflow:**

- **Schedule:** 3 AM UTC every Sunday (`cron: '0 3 * * 0'`)
- **Manual Trigger:** `workflow_dispatch` support

**Single Job: comprehensive-stress-tests**
- Install Python 3.11, Node.js 18
- Install backend dependencies and Playwright
- Install k6
- Start backend server
- Run all stress tests:
  - `tests/load/` (k6 load tests)
  - `tests/e2e_ui/tests/test_network_*.py` (network simulation)
  - `tests/e2e_ui/tests/test_memory_leak_detection.py` (memory leaks)
  - `tests/mobile_api/` (mobile API tests)
  - `tests/desktop/` (desktop Tauri tests)
  - `frontend-nextjs/tests/visual/` (visual regression)
  - `frontend-nextjs/tests/accessibility/` (WCAG a11y tests)
- Output JUnit XML for aggregation
- Aggregate results using stress test scheduler
- Send Slack summary report
- Send email alert on main branch failure (optional)
- File bugs for failures
- Upload test report and summary (90-day retention)

**Key Features:**
- Comprehensive test coverage (7 test categories)
- Artifact uploads for screenshots and heap snapshots
- Generated test report in markdown format
- 90-day retention for weekly summaries and reports

### 3. test_scheduler.py (419 lines)

**Stress test scheduler and result aggregator (Python CLI):**

**StressTestScheduler Class Methods:**
1. `__init__(results_dir, output_dir)` - Initialize with directories
2. `aggregate_results(results_file)` - Parse JUnit XML or k6 JSON
3. `_parse_junit_xml(xml_path)` - Extract test counts and failures
4. `_parse_k6_json(json_path)` - Extract metrics (p95, p99, error rate)
5. `calculate_trends(historical_results)` - Compare to historical runs
6. `report_summary(summary_data, slack, email)` - Print formatted report
7. `send_alert(test_failures, alert_type, webhook_url)` - Send Slack/email
8. `save_summary(summary_data, output_file)` - Save to JSON file

**CLI Commands:**
```bash
# Aggregate results
python backend/tests/stress/test_scheduler.py aggregate \
  --results-file backend/stress-test-results.xml \
  --output backend/stress-test-summary.json

# Generate report
python backend/tests/stress/test_scheduler.py report \
  --summary-file backend/stress-test-summary.json \
  --slack

# Send alert
python backend/tests/stress/test_scheduler.py send_alert \
  --results-file backend/stress-test-results.xml \
  --alert-type slack
```

**Summary Structure:**
```json
{
  "timestamp": "2026-03-24T02:00:00Z",
  "summary": {
    "total_tests": 150,
    "passed": 145,
    "failed": 5,
    "pass_rate": 0.967
  },
  "by_category": {
    "load": {"total": 4, "passed": 4, "failed": 0},
    "network": {"total": 16, "passed": 15, "failed": 1},
    "memory": {"total": 4, "passed": 4, "failed": 0}
  },
  "performance": {
    "p50_latency_ms": 350,
    "p95_latency_ms": 650,
    "p99_latency_ms": 1100,
    "error_rate": 0.03
  },
  "trends": {
    "pass_rate_change": "+0.02",
    "latency_change": "-50ms"
  }
}
```

**Key Features:**
- Supports JUnit XML (pytest) and k6 JSON formats
- Calculates pass/fail rates per category
- Extracts performance metrics (p50, p95, p99, error rate)
- Historical trend analysis (pass rate change, latency change)
- Slack webhook integration for alerts
- Graceful degradation if `requests` library not available

### 4. STRESS_TESTING_CI_CD.md (407 lines)

**Comprehensive CI/CD documentation:**

**Sections:**
1. **Overview** - Purpose and goals of scheduled stress testing
2. **Schedules** - Nightly (2 AM UTC) and weekly (3 AM UTC Sunday) schedules with cron syntax
3. **Test Coverage** - Detailed breakdown of all test categories (load, network, memory, mobile, desktop, visual, a11y)
4. **Result Aggregation** - JUnit XML and k6 JSON parsing, summary structure, performance metrics
5. **Alerting** - Slack webhooks, email (SendGrid), GitHub Issues setup
6. **Manual Testing** - Local execution examples and test scheduler CLI usage
7. **Troubleshooting** - Common issues (workflow not running, flaky tests, missing artifacts, alerts not sending, high memory usage)
8. **Result Storage** - GitHub Actions artifacts, local storage paths, historical trends
9. **Best Practices** - 10 recommendations for effective stress testing
10. **Related Documentation** - Links to related docs and summaries

**Cron Examples:**
```
0 2 * * *     # 2 AM UTC daily
0 3 * * 0     # 3 AM UTC every Sunday
0 4 * * 1     # 4 AM UTC every Monday
0 */6 * * *   # Every 6 hours
*/30 * * * *  # Every 30 minutes
```

**Example Slack Alert:**
```
🔴 Stress Tests Failed (Nightly - 2026-03-24)

Summary: 145/150 passed (96.7%)

Failures by Category:
- Network: 1 failure (test_offline_mode)
- Mobile: 1 failure (test_mobile_camera_capture)

Performance:
- p95 Latency: 650ms (threshold: 500ms) ⚠️
- Error Rate: 3% (threshold: 5%)

View Details: https://github.com/owner/repo/actions/runs/123456
```

**Secrets Configuration:**
- `SLACK_WEBHOOK_URL` - Create Slack Incoming Webhook
- `SENDGRID_API_KEY` - SendGrid API key for email alerts
- `ALERT_EMAIL_TO` - Destination email address
- `ALERT_EMAIL_FROM` - Source email address (verified in SendGrid)

## Deviations from Plan

### None - Plan Executed Exactly As Written

All tasks completed as specified:
1. ✅ Nightly stress tests workflow created with 3 jobs (load, network, memory)
2. ✅ Weekly stress tests workflow created with comprehensive test suite
3. ✅ Stress test scheduler created with all required methods
4. ✅ CI/CD documentation created with all required sections
5. ✅ Alerting configured for Slack and email (optional)

No deviations, no bugs encountered, no auto-fixes required.

## Verification Results

All verification steps passed:

1. ✅ **Nightly workflow schedule** - Cron: `0 2 * * *` (2 AM UTC daily)
2. ✅ **Nightly workflow jobs** - load-tests, network-tests, memory-tests, aggregate-results
3. ✅ **Weekly workflow schedule** - Cron: `0 3 * * 0` (3 AM UTC Sunday)
4. ✅ **Weekly workflow comprehensive tests** - All 7 test categories covered
5. ✅ **Stress test scheduler methods** - aggregate_results, report_summary, send_alert, calculate_trends, save_summary
6. ✅ **CLI interface** - aggregate, report, send_alert commands
7. ✅ **Alerting configuration** - Slack alert on failure, email alert on main branch failure
8. ✅ **Documentation sections** - Overview, Schedules, Test coverage, Result aggregation, Alerting, Troubleshooting
9. ✅ **Automated bug filing** - Integrated via `file_bugs_from_artifacts.py`
10. ✅ **Trend analysis** - Historical comparison with pass rate and latency changes

## CI/CD Workflow Features

### Nightly Stress Tests
- **Frequency:** Daily at 2 AM UTC
- **Duration:** ~30-45 minutes
- **Coverage:** Load (k6), Network, Memory
- **Alerting:** Slack on failure, email on main branch failure
- **Artifact Retention:** 30 days (test results), 90 days (summary)

### Weekly Stress Tests
- **Frequency:** Sunday at 3 AM UTC
- **Duration:** ~2-3 hours
- **Coverage:** Load, Network, Memory, Mobile, Desktop, Visual, Accessibility
- **Alerting:** Slack summary report, email on main branch failure
- **Artifact Retention:** 30 days (test results), 90 days (summary and report)

### Result Aggregation
- **Sources:** JUnit XML (pytest), k6 JSON (load tests)
- **Metrics:** Total tests, passed, failed, pass rate
- **Performance:** p50, p95, p99 latency, error rate
- **Categories:** Load, network, memory, mobile, desktop, visual, a11y
- **Trends:** Pass rate change, latency change vs. historical

### Alerting
- **Slack:** Primary notification channel (required)
- **Email:** Optional for critical main branch failures
- **GitHub Issues:** Automated bug filing on any failure
- **Graceful Degradation:** `continue-on-error: true` for all alerting steps

## Next Steps

### Manual Testing Required

To test workflows locally before first scheduled run:

1. **Create test data:**
   ```bash
   # Create sample JUnit XML
   cat > test-results.xml << 'EOF'
   <?xml version="1.0" encoding="utf-8"?>
   <testsuites>
     <testsuite name="load" tests="4" failures="0" errors="0">
       <testcase name="test_baseline_load"/>
     </testsuite>
   </testsuites>
   EOF
   ```

2. **Test scheduler CLI:**
   ```bash
   cd backend
   python tests/stress/test_scheduler.py aggregate \
     --results-file test-results.xml \
     --output test-summary.json

   python tests/stress/test_scheduler.py report \
     --summary-file test-summary.json
   ```

3. **Test Slack webhook:**
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   curl -X POST $SLACK_WEBHOOK_URL \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test alert from stress testing CI/CD"}'
   ```

### GitHub Secrets Setup

Before workflows can send alerts:

1. **Slack Webhook:**
   - Go to https://api.slack.com/messaging/webhooks
   - Create Incoming Webhook integration
   - Copy webhook URL
   - Add to repository secrets: `SLACK_WEBHOOK_URL`

2. **SendGrid Email (Optional):**
   - Create SendGrid account: https://sendgrid.com/
   - Generate API key with "Mail Send" permission
   - Verify sender email address in SendGrid
   - Add secrets: `SENDGRID_API_KEY`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`

3. **Verify Secrets:**
   ```bash
   # List secrets (requires repo admin access)
   gh secret list

   # Test Slack webhook
   gh workflow run nightly-stress-tests.yml
   ```

### First Scheduled Run

After merging to main branch:
1. Monitor Actions tab for first scheduled run
2. Verify workflow executes successfully
3. Check Slack alert sent (if tests failed)
4. Review aggregated summary artifact
5. Validate bug filing creates GitHub issues (if failures)

## Decisions Made

- **Scheduled workflows:** Use cron syntax for automated execution (nightly vs. weekly)
- **Separate workflows:** Balance coverage vs. duration (nightly = 30-45 min, weekly = 2-3 hours)
- **Python scheduler:** Parse JUnit XML and k6 JSON, calculate metrics and trends
- **Slack primary:** Required alerting channel with webhook integration
- **Email optional:** Only for main branch critical failures to reduce noise
- **Trend analysis:** Compare to historical runs for regression detection
- **Bug filing:** Automated GitHub issue creation on any test failure
- **Artifact retention:** 30 days for test results, 90 days for summaries (cost vs. storage)

## Self-Check: PASSED

All files created:
- ✅ .github/workflows/nightly-stress-tests.yml (273 lines)
- ✅ .github/workflows/weekly-stress-tests.yml (175 lines)
- ✅ backend/tests/stress/test_scheduler.py (419 lines)
- ✅ backend/docs/STRESS_TESTING_CI_CD.md (407 lines)

All commits exist:
- ✅ 07e3861fc - create nightly stress tests CI/CD workflow
- ✅ 1dfcd746b - create weekly stress tests CI/CD workflow
- ✅ 51f6b25a1 - create stress test scheduler and result aggregator
- ✅ 12fe9ad5e - create stress testing CI/CD documentation
- ✅ 9ffc2c8ca - configure alerting integration for stress tests

All verification steps passed:
- ✅ Nightly workflow has schedule (0 2 * * *) and 3 jobs (load, network, memory)
- ✅ Weekly workflow has schedule (0 3 * * 0) and comprehensive test suite
- ✅ Stress test scheduler has all required methods (aggregate, report, send_alert, calculate_trends, save_summary)
- ✅ Alerting configured for Slack and email (optional for main branch)
- ✅ Documentation contains all required sections (Overview, Schedules, Test coverage, Result aggregation, Alerting, Troubleshooting)
- ✅ Automated bug filing integrated (file_bugs_from_artifacts.py)
- ✅ Trend analysis implemented (historical comparison)

---

*Phase: 236-cross-platform-and-stress-testing*
*Plan: 09*
*Completed: 2026-03-24*

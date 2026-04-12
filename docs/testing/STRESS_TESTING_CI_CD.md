# Stress Testing CI/CD

## Overview

Scheduled stress testing runs automated load, network, and memory tests on a recurring schedule to catch performance regressions and bugs early. Tests run nightly (basic stress tests) and weekly (comprehensive test suite) with automated result aggregation, reporting, and alerting.

**Purpose:**
- Detect performance regressions before they reach production
- Validate system behavior under stress (high load, slow networks, memory pressure)
- Automated bug filing for test failures
- Track performance trends over time
- Ensure cross-platform reliability (web, mobile, desktop)

## Schedules

### Nightly Stress Tests
- **Schedule:** 2 AM UTC every night (9 PM EST / 6 PM PST)
- **Cron:** `0 2 * * *`
- **Duration:** ~30-45 minutes
- **Scope:** Load tests (k6), network simulation, memory leak detection
- **Workflow:** `.github/workflows/nightly-stress-tests.yml`

### Weekly Stress Tests
- **Schedule:** 3 AM UTC every Sunday (10 PM EST / 7 PM PST Saturday)
- **Cron:** `0 3 * * 0`
- **Duration:** ~2-3 hours
- **Scope:** All stress tests (load, network, memory, mobile, desktop, visual, accessibility)
- **Workflow:** `.github/workflows/weekly-stress-tests.yml`

### Manual Trigger
Both workflows support manual triggering via GitHub Actions UI:
1. Go to Actions tab in GitHub repository
2. Select "Nightly Stress Tests" or "Weekly Stress Tests"
3. Click "Run workflow" button
4. Select branch (default: main)
5. Click "Run workflow"

Or via GitHub CLI:
```bash
gh workflow run nightly-stress-tests.yml
gh workflow run weekly-stress-tests.yml
```

## Test Coverage

### Load Testing (k6)
- **Baseline:** 10 concurrent users, 6 minutes (ramp-up 2m, sustained 3m, ramp-down 1m)
- **Moderate:** 50 concurrent users, 17 minutes (ramp-up 5m, sustained 10m, ramp-down 2m)
- **High:** 100 concurrent users, 28 minutes (ramp-up 10m, sustained 15m, ramp-down 3m)
- **Web UI:** 20 concurrent users, 9 minutes (realistic 9-step user flow)
- **Metrics:** p95/p99 latency, error rate, check pass rate, requests per second
- **Files:** `backend/tests/load/test_api_load_*.js`

**Test Scenarios:**
- Authentication (login, logout)
- Agent execution (list, execute)
- Canvas operations (present, close)
- Workflow execution (trigger, wait)

### Network Simulation
- **Slow 3G:** 750ms RTT, 750 Kbps download, 250 Kbps upload
- **Offline Mode:** Browser offline, error handling validation
- **API Timeout:** 30s timeout, retry logic verification
- **Database Drop:** Connection loss, graceful degradation
- **Tests:** `backend/tests/e2e_ui/tests/test_network_*.py`

### Memory Leak Detection
- **Agent Execution:** 10 rapid executions, heap snapshot comparison
- **Canvas Cycles:** 20 present/close cycles, DOM node count verification
- **Session Persistence:** 10 login/logout cycles, session cleanup validation
- **Event Listeners:** 20 cycles, listener leak detection (<1000 threshold)
- **Tests:** `backend/tests/e2e_ui/tests/test_memory_leak_detection.py`

### Mobile API Tests
- **Authentication:** Mobile auth flows, JWT validation
- **Agents:** Agent execution via mobile API
- **Workflows:** Skill installation, DAG validation
- **Device Features:** Camera, screen recording, location (API-level)
- **Tests:** `backend/tests/mobile_api/`

### Desktop Tests (Tauri)
- **Window Management:** Create, resize, maximize, minimize, close
- **Native Features:** File system access, notifications, system tray
- **Cross-Platform:** Windows, macOS, Linux behavior validation
- **Tests:** `backend/tests/desktop/`

### Visual Regression Tests
- **Percy Screenshots:** 24+ pages across 5 page groups
- **Viewports:** Mobile (375px), Tablet (768px), Desktop (1280px)
- **Pages:** Login, dashboard, agents, canvas, workflows
- **Tests:** `frontend-nextjs/tests/visual/`

### Accessibility Tests
- **WCAG 2.1 AA Compliance:** Color contrast, keyboard navigation
- **jest-axe:** Automated accessibility checks for React components
- **Screen Reader:** ARIA labels, roles, landmarks
- **Tests:** `frontend-nextjs/tests/accessibility/`

## Result Aggregation

### JUnit XML Parsing
Stress test scheduler parses JUnit XML output from pytest:
```xml
<testsuite name="network" tests="16" failures="1" errors="0" skipped="0">
  <testcase name="test_offline_mode" classname="test_network_offline"/>
</testsuite>
```

### k6 JSON Parsing
Load test results from k6 in JSON format:
```json
{
  "metrics": {
    "http_reqs": {"values": {"count": 1234}},
    "http_req_duration": {"values": {"p(95)": 420, "p(99)": 780}},
    "http_req_failed": {"values": {"rate": 3.65}}
  }
}
```

### Summary Report Structure
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
    "memory": {"total": 4, "passed": 4, "failed": 0},
    "mobile": {"total": 20, "passed": 19, "failed": 1},
    "desktop": {"total": 16, "passed": 16, "failed": 0},
    "visual": {"total": 24, "passed": 24, "failed": 0},
    "a11y": {"total": 17, "passed": 17, "failed": 0}
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

### Performance Metrics
- **p50 Latency:** Median response time (50th percentile)
- **p95 Latency:** 95th percentile response time (SLA target)
- **p99 Latency:** Tail latency (99th percentile)
- **Error Rate:** Percentage of failed requests (target: <5%)
- **Pass Rate:** Percentage of passed tests (target: >95%)

## Alerting

### Slack Alerts
**Trigger:** Test failures in nightly or weekly runs

**Setup:**
1. Create Slack Incoming Webhook: https://api.slack.com/messaging/webhooks
2. Add webhook URL to GitHub Secrets: `SLACK_WEBHOOK_URL`
3. Workflow sends alert automatically on failure

**Example Alert:**
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

### Email Alerts (Optional)
**Trigger:** Critical failures on main branch

**Setup:**
1. Set up SendGrid account: https://sendgrid.com/
2. Add API key to GitHub Secrets: `SENDGRID_API_KEY`
3. Add email addresses: `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`
4. Only sends for main branch failures

### GitHub Issues (Automated Bug Filing)
**Trigger:** Any test failure

**Setup:**
- Workflow calls `backend/tests/bug_discovery/file_bugs_from_artifacts.py`
- Creates GitHub issues with failure details
- Labels: `bug`, `stress-test`, `auto-filed`
- Assignee: None (triage needed)

**Example Issue:**
```
Title: [Stress Test] test_offline_mode failed

**Test:** test_offline_mode
**Category:** Network
**Run:** Nightly Stress Tests - 2026-03-24 02:00 UTC
**Commit:** abc123def

**Failure Details:**
AssertionError: Expected offline mode to show error message
Got: "No internet connection" timeout

**Artifacts:**
- Screenshots: https://github.com/owner/repo/actions/runs/123456
- Logs: Attached

**Priority:** High (user-facing regression)
```

## Manual Testing

### Local Stress Testing
Run stress tests locally without CI/CD:

```bash
# 1. Start backend server
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &

# 2. Run load tests (k6)
cd backend/tests/load
k6 run test_api_load_baseline.js --duration 2m --vus 10
k6 run test_api_load_moderate.js --duration 5m --vus 50

# 3. Run network tests
cd backend
pytest tests/e2e_ui/tests/test_network_slow_3g.py -v

# 4. Run memory leak tests
pytest tests/e2e_ui/tests/test_memory_leak_detection.py -v

# 5. Run all stress tests
pytest tests/load/ tests/e2e_ui/tests/test_network_*.py \
       tests/e2e_ui/tests/test_memory_leak_detection.py \
       -v --junitxml=stress-test-results.xml

# 6. Aggregate results
python tests/stress/test_scheduler.py aggregate \
  --results-file stress-test-results.xml \
  --output stress-test-summary.json

# 7. View summary
python tests/stress/test_scheduler.py report \
  --summary-file stress-test-summary.json
```

### Test Scheduler CLI
```bash
# Aggregate results
python backend/tests/stress/test_scheduler.py aggregate \
  --results-file backend/stress-test-results.xml \
  --output backend/stress-test-summary.json

# Generate report
python backend/tests/stress/test_scheduler.py report \
  --summary-file backend/stress-test-summary.json \
  --slack  # Format for Slack

# Send alert manually
python backend/tests/stress/test_scheduler.py send_alert \
  --results-file backend/stress-test-results.xml \
  --alert-type slack
```

## Troubleshooting

### Workflow Not Running
**Symptom:** Scheduled workflow doesn't trigger at expected time

**Solutions:**
1. Check cron syntax: `0 2 * * *` = 2 AM UTC (not local time)
2. Verify workflow file is in `.github/workflows/` directory
3. Check GitHub Actions tab for recent runs
4. Ensure repository is active (pushed to within 60 days)
5. Check timezone: GitHub Actions uses UTC

**Cron Examples:**
```
0 2 * * *     # 2 AM UTC daily
0 3 * * 0     # 3 AM UTC every Sunday
0 4 * * 1     # 4 AM UTC every Monday
0 */6 * * *   # Every 6 hours
*/30 * * * *  # Every 30 minutes
```

### Tests Failing Intermittently
**Symptom:** Flaky tests, sometimes pass, sometimes fail

**Possible Causes:**
1. **Resource contention:** CI server overload, reduce concurrent users
2. **Network issues:** External API timeouts, add retries
3. **Race conditions:** Timing-dependent tests, add waits
4. **Test data pollution:** Shared state between tests, use fixtures

**Solutions:**
1. Increase timeouts in test fixtures
2. Add explicit waits (page.waitForLoadState)
3. Use test data factories with isolated sessions
4. Run tests serially to identify flaky ones: `pytest -v --serial`
5. Add retry logic for external calls

### Missing Artifacts
**Symptom:** Test artifacts not uploaded or missing after workflow run

**Solutions:**
1. Check artifact upload step uses `if: always()` condition
2. Verify artifact path is correct (relative to repository root)
3. Check artifact retention period (30-90 days default)
4. Ensure test artifacts directory exists before upload
5. Check GitHub Actions storage quota (10GB limit per repo)

### Alerts Not Sending
**Symptom:** Slack or email alerts not received after test failures

**Solutions:**
1. **Slack:**
   - Verify `SLACK_WEBHOOK_URL` secret is set in repository settings
   - Test webhook URL: `curl -X POST $WEBHOOK_URL -d '{"text":"test"}'`
   - Check Slack app permissions (Incoming Webhooks scope)
   - Verify workflow has `if: failure()` condition

2. **Email:**
   - Verify `SENDGRID_API_KEY`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM` secrets
   - Check SendGrid API key is valid and has sender verification
   - Ensure email addresses are verified in SendGrid
   - Check spam folder for test emails

### High Memory Usage
**Symptom:** CI workflow exceeds GitHub Actions memory limits (7GB)

**Solutions:**
1. Reduce concurrent user count in load tests
2. Run test categories sequentially instead of parallel
3. Use `ubuntu-large` runner (more resources, costs more)
4. Add memory cleanup steps between test runs
5. Limit heap snapshot retention (delete old snapshots)

## Result Storage

### GitHub Actions Artifacts
- **Retention:** 30 days for test results, 90 days for summaries
- **Location:** Actions tab → Workflow run → Artifacts section
- **Download:** Click artifact name or use `gh run download`

### Local Storage
- **Summaries:** `backend/tests/artifacts/summaries/`
- **Trends:** `backend/tests/artifacts/trends/`
- **Screenshots:** `backend/tests/e2e_ui/screenshots/`
- **Heap Snapshots:** `backend/tests/e2e_ui/heap-snapshots/`

### Historical Trends
Trend analysis compares current run to previous runs:
- **Pass Rate Change:** Current pass rate - Previous pass rate
- **Latency Change:** Current p95 - Previous p95 (in milliseconds)
- **Sample Size:** Number of historical runs available

**Trend Thresholds:**
- Pass rate decrease >5%: Flag as regression
- Latency increase >100ms: Flag as regression
- Pass rate increase >5%: Flag as improvement
- Latency decrease >50ms: Flag as improvement

## Best Practices

1. **Warm up the cache:** Run tests for 1-2 minutes before collecting metrics
2. **Start small:** Begin with 50 users, scale up gradually
3. **Monitor resources:** Watch CPU, memory, database connections during tests
4. **Use realistic data:** Test with production-like data volumes
5. **Run multiple times:** Performance can vary due to system load
6. **Compare to baseline:** Track performance over time to detect regressions
7. **Test in staging:** Never run load tests in production without limits
8. **Review trends:** Look for gradual performance degradation over weeks
9. **Investigate failures:** Don't ignore intermittent failures
10. **Update baselines:** When performance improves, update baseline targets

## Related Documentation

- **Load Testing:** `backend/tests/load/README_K6.md`
- **Network Testing:** Phase 236-02 summary
- **Memory Testing:** Phase 236-03 summary
- **Mobile Testing:** Phase 236-04 summary
- **Desktop Testing:** Phase 236-05 summary
- **Visual Testing:** Phase 236-06 summary
- **Bug Filing:** `backend/tests/bug_discovery/README.md`

## Support

For issues or questions about stress testing CI/CD:
1. Check workflow logs in GitHub Actions tab
2. Review test artifacts (screenshots, logs, heap snapshots)
3. Consult troubleshooting section above
4. Open issue with label `stress-test` and `ci-cd`

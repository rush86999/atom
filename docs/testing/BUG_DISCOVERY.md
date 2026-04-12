# Automated Bug Discovery

**Automated bug filing service that creates GitHub Issues for test failures with complete metadata including screenshots, logs, traces, and reproducible test cases.**

## Overview

The Automated Bug Discovery system automatically files GitHub Issues when tests fail, reducing manual triage and accelerating bug fixes. It captures rich metadata from test failures including:

- Screenshots (for visual/E2E tests)
- Test logs (stdout/stderr)
- Stack traces
- Performance metrics (for load tests)
- Platform information (OS, browser, Python version)
- CI/CD context (commit SHA, branch, run URL)

This enables developers to quickly understand, reproduce, and fix bugs without manually triaging test failures.

## How It Works

### 1. Test Failure Detection

When a test fails, the test framework (pytest) captures:

- **Test name and file path**
- **Error message and stack trace**
- **Screenshot** (automatically captured via `screenshot_on_failure` fixture)
- **Test logs** (automatically captured via `log_on_failure` fixture)
- **Performance metrics** (for load/performance tests)

### 2. Bug Metadata Collection

The `BugFilingService` collects comprehensive metadata:

```python
metadata = {
    "test_name": "test_api_load_baseline",
    "error_message": "p(95) > 500ms",
    "test_file": "backend/tests/load/test_api_load_baseline.py",
    "stack_trace": "...",
    "screenshot_path": "/path/to/screenshot.png",
    "log_path": "/path/to/test.log",
    "performance_metrics": {
        "p95_latency_ms": 650,
        "error_rate": 8.5
    },
    "test_type": "load",
    "platform": "web",
    "os_info": "Linux-5.15.0-x86_64",
    "python_version": "3.11.2"
}
```

### 3. GitHub Issue Creation

The service creates a GitHub Issue with:

- **Title:** `[Bug] {Error Type}: {Test Name}`
- **Body:** Markdown-formatted with complete metadata
- **Labels:** `bug`, `automated`, `test-type:{type}`, `severity:{level}`, `platform:{platform}`

Example issue:

```markdown
## Bug Description

p(95) > 500ms: Actual p(95) = 650ms

## Test Context

- **Test:** `test_api_load_baseline`
- **File:** `backend/tests/load/test_api_load_baseline.py`
- **Platform:** Linux-5.15.0-x86_64
- **Python:** 3.11.2

## Stack Trace

```
Error: Threshold exceeded
  at test_api_load_baseline (test_api_load_baseline.py:42)
```

## Performance Metrics

- **p95_latency_ms:** 650
- **error_rate:** 8.5

## Metadata

- **Test run:** [link to CI run]
- **Commit:** `abc123def456`
- **Branch:** `main`
```

### 4. Idempotency

The service checks for existing issues with the same title before creating new ones, preventing duplicate bugs for the same failure.

## Supported Test Types

| Test Type | Description | Metadata Fields |
|-----------|-------------|-----------------|
| **load** | Load testing failures (k6 threshold violations) | `p95_latency_ms`, `error_rate`, `throughput_rps` |
| **network** | Network simulation failures (offline mode, slow 3G) | `network_condition` (offline/slow3g) |
| **memory** | Memory leak detection failures | `memory_increase_mb`, `iterations` |
| **mobile** | Mobile API test failures | `endpoint`, `status_code`, `device` |
| **desktop** | Desktop (Tauri) test failures | `action` (minimize/maximize/close) |
| **visual** | Visual regression failures (Percy) | `percy_diff_url`, `pixel_diff_count` |
| **a11y** | Accessibility failures (WCAG violations) | `violation_type`, `violation_count`, `wcag_level` |

## Severity Levels

The bug filing service automatically assigns severity levels based on test type and metadata:

| Severity | Criteria |
|----------|----------|
| **critical** | Load test failures with error rate > 10% |
| **high** | Memory leaks, network failures, accessibility violations |
| **medium** | Visual regressions, mobile API failures, desktop failures |
| **low** | Other issues |

## Labels

All bugs filed automatically include:

- `bug` - Bug label
- `automated` - Automatically filed
- `test-type:{type}` - One of: load, network, memory, mobile, desktop, visual, a11y
- `severity:{level}` - One of: critical, high, medium, low
- `platform:{platform}` - One of: web, mobile, desktop

## CI/CD Integration

### Automated Bug Filing Workflow

The `.github/workflows/automated-bug-filing.yml` workflow automatically files bugs when test workflows fail:

```yaml
on:
  workflow_run:
    workflows: ["Load Testing", "E2E Testing", ...]
    types: [completed]
    branches: [main, develop]

jobs:
  file-bugs:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    steps:
      - uses: actions/checkout@v3
      - uses: actions/download-artifact@v3
      - name: File bugs
        run: python backend/tests/bug_discovery/file_bugs_from_artifacts.py
```

### PR Comments

When bugs are filed from a PR test run, the workflow automatically comments on the PR with links to the filed bugs:

```markdown
## Automated Bug Filing

The following bugs were automatically filed for test failures:

- [1234] https://github.com/owner/repo/issues/1234
- [1235] https://github.com/owner/repo/issues/1235
```

## Manual Bug Filing

### File Bug from Test Failure Report

If you have a test failure report JSON file:

```bash
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=owner/repo
python backend/tests/bug_discovery/file_bugs_from_artifacts.py
```

### File Bug Programmatically

```python
from backend.tests.bug_discovery.bug_filing_service import file_bug_from_test_failure

result = file_bug_from_test_failure(
    test_name="test_example",
    error_message="Assertion failed: Expected 200, got 500",
    stack_trace="...",
    test_type="load"
)

print(f"Bug filed: {result['issue_url']}")
```

## Architecture

### BugFilingService Class

**Location:** `backend/tests/bug_discovery/bug_filing_service.py`

**Key Methods:**

- `file_bug(test_name, error_message, metadata)` - Main method to file a bug
- `_check_duplicate_bug(title)` - Check for existing issues (idempotency)
- `_create_github_issue(title, body, labels)` - Create GitHub issue via REST API
- `_generate_bug_title(test_name, error_type)` - Generate standardized title
- `_generate_bug_body(metadata)` - Generate markdown-formatted body
- `_attach_screenshot(issue_number, screenshot_path)` - Attach screenshot to issue
- `_attach_logs(issue_number, log_path)` - Attach logs to issue
- `_generate_labels(metadata)` - Generate labels based on test type
- `_determine_severity(test_type, metadata)` - Determine severity level

### Fixtures

**Location:** `backend/tests/bug_discovery/fixtures/bug_filing_fixtures.py`

**Fixtures:**

- `mock_github_api` - Mock GitHub API calls for testing
- `bug_filing_service` - Create BugFilingService instance
- `test_metadata` - Sample metadata for load tests
- `test_metadata_network` - Sample metadata for network tests
- `test_metadata_memory` - Sample metadata for memory tests
- `test_metadata_mobile` - Sample metadata for mobile tests
- `test_metadata_desktop` - Sample metadata for desktop tests
- `test_metadata_visual` - Sample metadata for visual tests
- `test_metadata_a11y` - Sample metadata for accessibility tests
- `artifacts_dir` - Temporary artifacts directory
- `sample_screenshot_file` - Sample screenshot file for testing
- `sample_log_file` - Sample log file for testing

### Tests

**Location:** `backend/tests/bug_discovery/test_automated_bug_filing.py`

**30 Tests covering:**

- Load test failures (3 tests)
- Network test failures (3 tests)
- Memory leak failures (3 tests)
- Mobile API failures (3 tests)
- Desktop failures (2 tests)
- Visual regression failures (3 tests)
- Accessibility failures (3 tests)
- Idempotency (3 tests)
- Convenience function (3 tests)
- Attachments (4 tests)

**Run tests:**

```bash
pytest backend/tests/bug_discovery/test_automated_bug_filing.py -v
```

## Example Bug Reports

### Load Test Failure

**Title:** `[Bug] Load Test Failure: Test Api Load Baseline`

**Labels:** `bug`, `automated`, `test-type:load`, `severity:high`, `platform:web`

**Key Metadata:**
- p(95) latency: 650ms (threshold: 500ms)
- Error rate: 8.5%
- Throughput: 45 RPS

### Visual Regression Failure

**Title:** `[Bug] Visual Regression Detected: Test Visual Dashboard`

**Labels:** `bug`, `automated`, `test-type:visual`, `severity:medium`, `platform:web`

**Key Metadata:**
- Percy diff URL: https://percy.io/...
- Pixel differences: 3
- Screenshot attached

### Accessibility Failure

**Title:** `[Bug] WCAG Violation Detected: Test Wcag Compliance Dashboard`

**Labels:** `bug`, `automated`, `test-type:a11y`, `severity:high`, `platform:web`

**Key Metadata:**
- Violation type: color-contrast
- Violation count: 5
- WCAG level: AA

## Troubleshooting

### GitHub Token Not Found

**Error:** `ValueError: GITHUB_TOKEN environment variable not set`

**Solution:**
- In CI/CD: `GITHUB_TOKEN` is automatically provided by GitHub Actions
- Local testing: Create a Personal Access Token (PAT) with `repo` scope
  ```bash
  export GITHUB_TOKEN=ghp_xxx
  ```

### Duplicate Issues

**Issue:** Same bug filed multiple times

**Solution:**
- Check `_check_duplicate_bug()` logic in `BugFilingService`
- Ensure issue titles are consistent
- Verify GitHub API is returning existing issues correctly

### Missing Screenshots/Logs

**Issue:** Bug reports don't include screenshots or logs

**Solution:**
- Ensure `screenshot_on_failure` and `log_on_failure` fixtures are enabled
- Check that artifact upload is working in CI/CD
- Verify file paths in metadata are correct

### Bug Filing Script Fails

**Error:** `No failure reports found`

**Solution:**
- Ensure tests are generating failure report JSON files
- Check that artifacts are being uploaded/downloaded correctly
- Verify `artifacts_dir` path in `file_bugs_from_artifacts.py`

### Tests Failing Locally

**Issue:** Bug filing tests fail when running locally

**Solution:**
- Disable pytest-randomly plugin: `pytest -p no:randomly`
- Ensure fixtures are discovered: Check `conftest.py` exists
- Verify mock imports: `from unittest.mock import MagicMock`

## Best Practices

1. **Enable Automatic Screenshot/Log Capture:**
   - Use `screenshot_on_failure` and `log_on_failure` fixtures in all E2E tests
   - Configure artifact upload in CI/CD workflows

2. **Customize Metadata:**
   - Add test-specific metadata fields (e.g., `percy_diff_url` for visual tests)
   - Enrich metadata with CI/CD context (commit SHA, branch, run URL)

3. **Monitor Bug Volume:**
   - Set up alerts for high bug filing rates
   - Review and close duplicate bugs regularly
   - Prioritize critical and high-severity bugs first

4. **Integrate with Sprint Planning:**
   - Review auto-filed bugs during sprint planning
   - Triage bugs by severity and test type
   - Assign bugs to appropriate team members

## Future Enhancements

- **Bug clustering:** Group similar bugs automatically
- **Triage suggestions:** Suggest assignees based on code ownership
- **Bug deduplication:** Use ML to detect duplicate bugs across different test runs
- **Auto-resolution:** Close bugs automatically when tests pass
- **Metrics dashboard:** Track bug filing trends and resolution times

## See Also

- **Bug Filing Service:** `backend/tests/bug_discovery/bug_filing_service.py`
- **Bug Filing Tests:** `backend/tests/bug_discovery/test_automated_bug_filing.py`
- **CI/CD Workflow:** `.github/workflows/automated-bug-filing.yml`
- **Bug Filing Script:** `backend/tests/bug_discovery/file_bugs_from_artifacts.py`
- **Test Fixtures:** `backend/tests/bug_discovery/fixtures/bug_filing_fixtures.py`

---

*Last Updated: 2026-03-24*

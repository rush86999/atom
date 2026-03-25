# Test Infrastructure Standards

**Purpose**: Comprehensive guide for test infrastructure standards and patterns in Atom.

**Last Updated**: 2026-03-23

---

## Overview

This document outlines the test infrastructure standards for the Atom project, covering:
- Test fixtures and patterns
- Database isolation and test data management
- Failure artifact capture (screenshots, videos)
- Test reporting (Allure, HTML, JSON)
- Parallel execution patterns
- Test cleanup and teardown

**Target Audience**: Test engineers, developers writing tests, CI/CD engineers

---

## Test Fixtures Standards

### Fixture Scope

**Session-scoped fixtures** (expensive, shared):
```python
@pytest.fixture(scope="session")
def browser():
    """Shared browser instance for all tests."""
    # Use for: Browser launch, server startup
```

**Function-scoped fixtures** (default, isolated):
```python
@pytest.fixture(scope="function")
def page(browser):
    """New page for each test."""
    # Use for: Page objects, test data
```

**Autouse fixtures** (automatic):
```python
@pytest.fixture(autouse=True)
def track_page_for_screenshots(request, page):
    """Track page for automatic screenshot capture."""
    # Runs for every test automatically
```

### Fixture Naming Conventions

- Descriptive names: `screenshot_page`, not `sp`
- Return type hints in docstrings
- Yield for cleanup, return for values

---

## Database Isolation Patterns

### Worker-Specific Database Isolation

All tests automatically get worker-specific database isolation via `db_session` fixture:

```python
@pytest.fixture(scope="function")
def db_session():
    """
    Worker-specific database session with automatic rollback.

    Each pytest-xdist worker gets its own database file to prevent
    test data collisions during parallel execution.
    """
    # Worker ID: gw0, gw1, gw2, etc.
    # Database: atom_test_<worker_id>.db
    # Automatic rollback after each test
```

**Key Benefits**:
- No test data collisions between workers
- No cleanup code needed in tests
- Full parallel execution support

**Usage**:
```python
def test_create_agent(db_session):
    agent = AgentRegistry(id="test-agent", name="Test")
    db_session.add(agent)
    db_session.commit()

    # Auto-rollback after test
```

---

## Failure Artifacts (INFRA-04)

### Automatic Capture

Failed E2E tests automatically capture:
- **Screenshot**: Full-page screenshot saved to `artifacts/screenshots/`
- **Video**: Browser recording saved to `artifacts/videos/` (CI only)
- **Allure Report**: Artifacts attached to test result for easy viewing

### Screenshot Format

- Filename: `{timestamp}_{test_name}.png`
- Full page capture (includes scrolled content)
- Available in: `artifacts/screenshots/`

**Example**:
```
20260323_170120_test_login_success.png
```

### Video Recording

- Enabled in CI only (GITHUB_ACTIONS=true)
- Format: WEBM
- Available in: `artifacts/videos/`
- Accessed via: `page.video.path()`

**Example**:
```
20260323_170120_test_login_success.webm
```

### Allure Integration

```python
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach screenshots/videos to Allure on failure."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # Capture and attach artifacts
        allure.attach.file(screenshot_path, ...)
        allure.attach.file(video_path, ...)
```

**Benefits**:
- Artifacts embedded in test report
- One-click viewing in Allure UI
- No manual file searching

### Viewing Artifacts

```bash
# Local: Check artifacts directory
ls artifacts/screenshots/
ls artifacts/videos/

# CI: Download from workflow run artifacts
# Allure: Open report and click failed test
allure open allure-report
```

### Manual Screenshot Capture

```python
def test_manual_screenshot(page):
    page.screenshot(path="custom-screenshot.png")

    # Attach to Allure
    allure.attach.file(
        "custom-screenshot.png",
        name="Custom Screenshot",
        attachment_type=allure.attachment_type.PNG
    )
```

---

## Test Cleanup Patterns

### Automatic Cleanup

Use fixtures with yield for cleanup:

```python
@pytest.fixture(scope="function")
def temp_file():
    """Create temp file and clean up after test."""
    path = "/tmp/test-file.txt"
    with open(path, "w") as f:
        f.write("test data")

    yield path

    # Cleanup
    os.remove(path)
```

### Database Cleanup

Use transaction rollback (automatic):

```python
def test_create_agent(db_session):
    agent = AgentRegistry(id="test", name="Test")
    db_session.add(agent)
    db_session.commit()
    # Auto-rollback after test
```

### Resource Cleanup

```python
@pytest.fixture(scope="function")
def server():
    """Start server and stop after test."""
    srv = start_server(port=8000)
    yield srv
    srv.stop()  # Cleanup
```

---

## Test Reporting Standards

### Allure Reporting

**Generate Report**:
```bash
pytest tests/ --alluredir=allure-results
allure generate allure-results --clean -o allure-report
allure open allure-report
```

**Benefits**:
- Rich test report with screenshots/videos
- Test history and trends
- Suites, categories, and tags

### HTML Reporting

**Generate Report**:
```bash
pytest tests/ --html=report.html --self-contained-html
```

**Features**:
- Embedded screenshots in failed tests
- Test execution summary
- Test duration and logs

### JSON Reporting

**Generate Report**:
```bash
pytest tests/ --json-report --json-report-file=report.json
```

**Use Case**: CI/CD pass rate parsing

---

## Parallel Execution Standards

### pytest-xdist Configuration

**Run tests in parallel**:
```bash
pytest -n auto  # Auto-detect CPU count
pytest -n 4     # Use 4 workers
```

**Worker Isolation**:
- Each worker gets own database file
- Unique resource names via fixtures
- No shared state between workers

### Test Independence

**Requirements**:
- No hardcoded IDs (use fixtures)
- No shared files (use temp files)
- No hardcoded ports (use random ports)

**Bad Example**:
```python
def test_create_agent():
    agent = AgentRegistry(id="test-agent", ...)  # Collision!
```

**Good Example**:
```python
def test_create_agent(unique_name):
    agent = AgentRegistry(id=unique_name(), ...)  # Safe
```

---

## CI/CD Integration

### CI-Specific Behavior

**Video Recording**: Enabled in CI only
```python
if is_ci_environment():
    context_args["record_video_dir"] = video_dir
```

**Test Retries**: Enabled in CI only
```python
if is_ci_environment():
    sys.argv.extend(["--reruns", "2"])
```

**Artifact Upload**: Screenshots and videos uploaded as workflow artifacts

### GitHub Actions Example

```yaml
- name: Run E2E tests
  run: pytest tests/e2e_ui/ -n auto

- name: Upload screenshots
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: screenshots
    path: backend/tests/e2e_ui/artifacts/screenshots/
```

---

## Best Practices

### DO ✅

- Use fixtures for setup/teardown
- Write isolated tests (no dependencies)
- Use unique resource names
- Leverage automatic rollback
- Attach screenshots to Allure on failure

### DON'T ❌

- Hardcode IDs or ports
- Share state between tests
- Manually cleanup database
- Skip fixture cleanup
- Ignore flaky tests (fix them)

---

## Troubleshooting

### Screenshots Not Capturing

**Check**:
1. Is `page` fixture available?
2. Is `allure-pytest` installed?
3. Is `allure-results` directory writable?

**Fix**:
```bash
pip install allure-pytest
mkdir -p allure-results
```

### Videos Not Recording

**Check**:
1. Is running in CI (GITHUB_ACTIONS=true)?
2. Is video dir created?
3. Is browser context configured for video?

**Fix**:
```python
if is_ci_environment():
    os.makedirs(video_dir, exist_ok=True)
    context_args["record_video_dir"] = video_dir
```

### Tests Failing in Parallel but Passing Sequentially

**Check**:
1. Are resources uniquely named?
2. Is database isolation enabled?
3. Are ports hardcoded?

**Fix**:
```python
# Use unique_name fixture
agent = AgentRegistry(id=unique_name(), ...)

# Use db_session fixture (auto-isolation)
def test_something(db_session):
    ...
```

---

## Additional Resources

- **Test Isolation Patterns**: `TEST_ISOLATION_PATTERNS.md`
- **Flaky Test Guide**: `FLAKY_TEST_GUIDE.md`
- **Parallel Execution Guide**: `PARALLEL_EXECUTION_GUIDE.md`
- **Coverage Guide**: `COVERAGE_GUIDE.md`

## Unified Test Runner (INFRA-08, INFRA-09, INFRA-10)

### Overview
Single entry point for running all platform tests with unified Allure reporting.

### Usage
```bash
# Run all platforms
python backend/tests/scripts/test_runner.py

# Run specific platform
python backend/tests/scripts/test_runner.py --platform backend
python backend/tests/scripts/test_runner.py --platform web
python backend/tests/scripts/test_runner.py --platform mobile

# Configure parallelism
python backend/tests/scripts/test_runner.py --workers 8

# Skip Allure report (faster iteration)
python backend/tests/scripts/test_runner.py --no-report

# Extra pytest arguments
python backend/tests/scripts/test_runner.py --extra "-k test_agent"
```

### Platforms
| Platform | Test Framework | Allure Directory |
|----------|---------------|------------------|
| Backend | pytest | allure-results/backend/ |
| Web E2E | pytest-playwright | allure-results/web/ |
| Mobile API | pytest | allure-results/mobile/ |
| Desktop | cargo test | (separate workflow) |

### Allure Report
```bash
# Generate report manually
python backend/tests/scripts/allure_aggregator.py aggregate-allure \
  --backend allure-results/backend/ \
  --web allure-results/web/ \
  --mobile allure-results/mobile/ \
  --output allure-results/

# View report (auto-refreshes)
allure open allure-report

# Serve report on port 8080
allure serve allure-results
```

### CI Integration
- GitHub Actions runs unified-tests job per platform
- generate-report job aggregates results
- Report uploaded as artifact for viewing

### Output
- Allure results: `allure-results/`
- Allure report: `allure-report/index.html`
- Screenshots: `artifacts/screenshots/` (on failure)
- Videos: `artifacts/videos/` (on failure, CI only)

---

*Last Updated: 2026-03-23*
*Phase: 233 - Test Infrastructure Foundation*
*Plan: 05 - Unified Test Runner with Allure Cross-Platform Reporting*

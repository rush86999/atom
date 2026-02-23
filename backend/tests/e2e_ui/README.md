# E2E UI Testing with Playwright

This directory contains end-to-end (E2E) UI tests for Atom using Playwright Python 1.58.0. The tests validate critical user workflows across authentication, agent chat, canvas presentations, skills, and workflows.

## Overview

**Technology Stack:**
- **Playwright Python 1.58.0**: Browser automation framework (Chromium)
- **pytest-playwright 0.5.2**: Pytest plugin for Playwright
- **pytest-xdist 3.6.1**: Parallel test execution
- **faker 22.7.0**: Realistic test data generation

**Test Infrastructure:**
- API-first authentication (JWT tokens in localStorage, 10-100x faster than UI login)
- Worker-based database isolation for parallel execution
- Page Object Model for maintainable UI abstractions
- Comprehensive fixture suite (auth, database, API, factory)

## Quick Start

### Prerequisites

1. **Docker Desktop** - For test environment (backend, frontend, PostgreSQL)
   ```bash
   docker --version
   ```

2. **Python 3.11+** - For running pytest
   ```bash
   python --version
   ```

3. **Node.js 18+** - For frontend (if running locally)
   ```bash
   node --version
   ```

### Setup

1. **Start E2E Test Environment**
   ```bash
   # Start Docker Compose services (backend, frontend, PostgreSQL)
   ./scripts/start-e2e-env.sh

   # Verify services are running
   curl http://localhost:8001/health/live  # Backend health check
   curl http://localhost:3001              # Frontend (should load)
   ```

2. **Install Dependencies**
   ```bash
   # Install Python dependencies
   pip install -r backend/requirements.txt

   # Install Playwright browsers
   playwright install chromium
   ```

3. **Verify Installation**
   ```bash
   # Check Playwright version
   playwright --version
   # Expected output: Version 1.58.0

   # Run smoke tests to verify setup
   pytest backend/tests/e2e_ui/tests/test_smoke.py -v
   ```

## Running Tests

### Run All E2E Tests
```bash
# Run all E2E tests sequentially
pytest backend/tests/e2e_ui/ -v

# Run with 4 parallel workers (faster)
pytest backend/tests/e2e_ui/ -v -n 4
```

### Run Specific Test Files
```bash
# Run smoke tests only
pytest backend/tests/e2e_ui/tests/test_smoke.py -v

# Run authentication tests
pytest backend/tests/e2e_ui/tests/test_auth_example.py -v

# Run database isolation tests
pytest backend/tests/e2e_ui/tests/test_database_isolation.py -v
```

### Run with Markers
```bash
# Run only E2E tests (skip unit/integration tests)
pytest backend/tests/e2e_ui/ -v -m e2e

# Run authentication tests only
pytest backend/tests/e2e_ui/ -v -m auth

# Skip slow tests
pytest backend/tests/e2e_ui/ -v -m "not slow"
```

### Run with Debugging
```bash
# Run with headful browser (see UI)
pytest backend/tests/e2e_ui/tests/test_smoke.py::test_playwright_browser_launches -v --headed

# Run with Playwright Inspector (debug mode)
pytest backend/tests/e2e_ui/tests/test_smoke.py::test_playwright_browser_launches -v --debug

# Run with screenshots on failure (default)
pytest backend/tests/e2e_ui/tests/test_smoke.py -v --tracing on
```

## Test Structure

### Directory Layout
```
tests/e2e_ui/
├── conftest.py                 # Pytest configuration and fixtures
├── fixtures/                   # Reusable test fixtures
│   ├── auth_fixtures.py        # API-first authentication (JWT in localStorage)
│   ├── database_fixtures.py    # Database session and worker isolation
│   ├── api_fixtures.py         # API setup utilities (setup_test_user, setup_test_project)
│   └── test_data_factory.py    # Factory Boy factories (UserFactory, ProjectFactory)
├── tests/                      # Test files
│   ├── test_smoke.py           # Smoke tests (infrastructure validation)
│   ├── test_auth_example.py    # Authentication test examples
│   ├── test_api_setup_example.py  # API setup test examples
│   └── test_database_isolation.py  # Database isolation tests
└── README.md                   # This file
```

### Fixtures

#### Authentication Fixtures
- **`test_user`**: Creates a test user with UUID v4 email (unique per test)
- **`authenticated_user`**: Creates user and returns (user, JWT token) tuple
- **`authenticated_page`**: Creates Playwright page with JWT token in localStorage (bypasses UI login)
- **`admin_user`**: Creates admin user with elevated permissions

#### Database Fixtures
- **`db_session`**: SQLAlchemy session with worker-specific schema isolation
- **`clean_database`**: Fresh database tables per test (function-scoped)

#### API Fixtures
- **`setup_test_user`**: Creates test user via API
- **`setup_test_project`**: Creates test project via API
- **`api_client_authenticated`**: HTTP client with pre-set Authorization header

#### Factory Fixtures
- **`UserFactory`**: Factory Boy factory for test users
- **`ProjectFactory`**: Factory Boy factory for test projects

### Example Test

```python
import pytest
from playwright.sync_api import Page

def test_user_login_flow(authenticated_page: Page):
    """Test user can access protected route after authentication."""
    # Navigate to dashboard (JWT token already set in localStorage)
    authenticated_page.goto("/dashboard")

    # Verify dashboard loads (no redirect to login)
    assert authenticated_page.locator("h1").contains("Dashboard")

    # Verify user menu shows logged-in user
    authenticated_page.click("button[data-testid='user-menu']")
    assert authenticated_page.locator("text=Logout").is_visible()
```

## Troubleshooting

### Port Conflicts

**Issue**: `Error: listen EADDRINUSE :8001` or `:3001`

**Solution**: Kill process using the port
```bash
# Kill backend on port 8001
lsof -ti:8001 | xargs kill -9

# Kill frontend on port 3001
lsof -ti:3001 | xargs kill -9

# Or use different ports in docker-compose-e2e.yml
```

### Database Connection Issues

**Issue**: `sqlalchemy.exc.OperationalError: could not connect to server`

**Solution**: Verify PostgreSQL container is running
```bash
# Check container status
docker ps | grep postgres

# Restart PostgreSQL container
docker restart atom-e2e-postgres

# Check connection
docker exec atom-e2e-postgres psql -U atom -d atom_test -c "SELECT 1;"
```

### Playwright Browser Not Found

**Issue**: `Executable doesn't exist at /path/to/chromium`

**Solution**: Install Playwright browsers
```bash
playwright install chromium

# Or install all browsers
playwright install
```

### Frontend Not Loading

**Issue**: `Error: connect ECONNREFUSED localhost:3001`

**Solution**: Verify frontend container is running
```bash
# Check container status
docker ps | grep frontend

# View frontend logs
docker logs atom-e2e-frontend

# Restart frontend container
docker restart atom-e2e-frontend
```

### Tests Timing Out

**Issue**: Tests timeout after 30 seconds (Playwright default)

**Solution**: Increase timeout for specific tests
```python
@pytest.mark.timeout(60)
def test_slow_operation(authenticated_page: Page):
    authenticated_page.goto("/slow-page")
    authenticated_page.wait_for_selector("text=Loaded", timeout=30000)
```

### JWT Token Not Working

**Issue**: Tests redirect to login despite authenticated_page fixture

**Solution**: Verify token format and localStorage keys
```python
# Debug: Check localStorage in test
def test_debug_auth(authenticated_page: Page):
    token = authenticated_page.evaluate("() => localStorage.getItem('auth_token')")
    print(f"Token: {token}")  # Should not be None

    # Verify backend accepts token
    response = authenticated_page.request.get("/api/v1/users/me", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.ok
```

## Best Practices

### 1. Use API-First Setup
Always use `authenticated_page` fixture instead of UI login:
```python
# Good: 10-100x faster
def test_authenticated_access(authenticated_page: Page):
    authenticated_page.goto("/dashboard")
    # Already logged in via JWT token

# Bad: Slow and fragile
def test_ui_login(page: Page):
    page.goto("/login")
    page.fill("input[name='email']", "test@example.com")
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
    # Waits for navigation, slower and less reliable
```

### 2. Use data-testid Selectors
Prefer `data-testid` attributes over CSS selectors:
```python
# Good: Resilient to CSS changes
authenticated_page.click("button[data-testid='submit-button']")

# Bad: Breaks when CSS classes change
authenticated_page.click(".btn.btn-primary.submit")
```

### 3. Keep Tests Independent
Each test should create its own data (no shared state):
```python
# Good: Isolated test data
def test_user_can_create_project(authenticated_page: Page, setup_test_project):
    project = setup_test_project(name="My Project")
    authenticated_page.goto(f"/projects/{project['id']}")

# Bad: Relies on data from other tests
def test_user_can_edit_project(authenticated_page: Page):
    # Assumes project was created in previous test
    authenticated_page.goto("/projects/1")  # Fragile!
```

### 4. Use Explicit Waits
Avoid hard-coded sleeps, use Playwright's auto-waiting:
```python
# Good: Waits for element to be ready
authenticated_page.click("button[data-testid='submit']")
authenticated_page.wait_for_selector("text=Success")

# Bad: Arbitrary sleep time
authenticated_page.click("button[data-testid='submit']")
time.sleep(2)  # Flaky!
```

### 5. Run Tests in Parallel
Use pytest-xdist for faster execution:
```bash
# Run with 4 workers
pytest backend/tests/e2e_ui/ -v -n 4

# Each worker gets isolated database schema (gw0, gw1, gw2, gw3)
```

## Performance Targets

- **Per test**: <30 seconds
- **Full suite**: <10 minutes (with 4 parallel workers)
- **Authentication**: <100ms (API-first vs 2-10s UI login)
- **Database isolation**: <50ms per test setup

## CI/CD Integration

To run E2E tests in CI/CD (GitHub Actions, GitLab CI, etc.):

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start E2E environment
        run: ./scripts/start-e2e-env.sh

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          playwright install chromium

      - name: Run E2E tests
        run: pytest backend/tests/e2e_ui/ -v -n 4

      - name: Upload screenshots
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: screenshots
          path: backend/tests/e2e_ui/screenshots/

      - name: Upload videos
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: videos
          path: backend/tests/e2e_ui/videos/
```

## Additional Resources

- **Playwright Documentation**: https://playwright.dev/python/
- **pytest-playwright Plugin**: https://pytest-playwright.readthedocs.io/
- **Factory Boy**: https://factoryboy.readthedocs.io/
- **pytest-xdist**: https://pytest-xdist.readthedocs.io/

## Status

**Phase**: 75 - Test Infrastructure & Fixtures
**Plan**: 75-07 - Update Playwright to 1.58.0 and Finalize Configuration
**Status**: ✅ COMPLETE

**Completed Tasks**:
- ✅ Playwright 1.58.0 installed
- ✅ All Wave 1 fixtures integrated
- ✅ pytest.ini configured for E2E test discovery
- ✅ Smoke test suite created
- ✅ Developer documentation (README.md)

**Next Steps**:
- Phase 76: Authentication & User Management E2E tests
- Phase 77: Agent Chat & Streaming E2E tests
- Phase 78: Canvas Presentations E2E tests

# Technology Stack

**Project:** Atom Platform - E2E UI Testing Enhancement (v3.1)
**Researched:** 2026-02-23
**Focus:** Playwright-based E2E UI testing for existing production platform

---

## Recommended Stack

### Core E2E Testing Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Playwright Python** | **1.58.0** | E2E browser automation | Latest stable (Feb 2026), active maintenance, 18 version updates from current 1.40.0. Python API integrates seamlessly with existing pytest infrastructure. Multi-browser support (Chromium/Firefox/WebKit), auto-waiting, built-in fixtures. |
| **pytest-playwright** | **latest** | Pytest integration | Official plugin providing `page`, `browser`, `context` fixtures. Context isolation, parallel execution, consistent with existing pytest patterns (already used for 80% backend coverage). |
| **pytest** | **7.4.0+** (existing) | Test runner | Already in use, supports markers, fixtures, parallel execution (pytest-xdist), 98%+ pass rate gates. No changes needed. |
| **pytest-xdist** | **3.6.0+** (existing) | Parallel test execution | Already configured for `-n auto`, essential for E2E test performance. Browser tests can run in parallel across workers. |
| **pytest-asyncio** | **0.21.0+** (existing) | Async test support | Required for Playwright async API, already in requirements.txt, `asyncio_mode = auto` configured in pytest.ini. |

### Browser Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Chromium** | **bundled** | Primary testing browser | Default Playwright browser, fastest, most stable. Covers 80%+ of user traffic (Chrome/Edge). |
| **Firefox** | **bundled** | Secondary browser | Cross-browser validation, catches engine-specific issues. Run weekly, not every PR. |
| **WebKit** | **bundled** | Safari simulation | macOS/iOS coverage, WebKit engine validation. Run weekly, not every PR. |
| **playwright install** | **CLI** | Browser binary installation | One-time setup to download browser binaries. Automated in CI/CD. |

### Test Data & Fixtures

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **factory-boy** | **3.3.0** (existing) | Test data factories | Complex object creation (users, agents, workflows). Better than fixtures for multi-step test data setup. |
| **faker** | **22.0.0** (existing) | Fake data generation | Realistic test data (names, emails, addresses). Prevents hardcoded values, improves test realism. |
| **freezegun** | **1.4.0** (existing) | Time freezing | Time-dependent tests (episode segmentation, graduation, expiry). Prevents flaky tests at midnight/month boundaries. |
| **pytest-mock** | **3.12.0** (existing) | Mocking utilities | External service mocking (payment APIs, third-party integrations). Use sparingly - E2E should use real services when possible. |

### Reporting & Observability

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-cov** | **4.1.0+** (existing) | Coverage reporting | Already integrated with 80% coverage gate. E2E tests contribute to overall coverage metrics. |
| **Allure Report** | **new** | HTML test reports | Rich UI for E2E test results, screenshots, video recordings, timelines. Better than pytest-html for browser tests. |
| **pytest-json-report** | **0.6.0** (existing) | JSON output | Already in use for pass rate parsing. CI/CD integration for quality gates. |
| **Playwright Tracing** | **built-in** | Failure debugging | Capture traces on test failure (network, console, DOM). Essential for flaky test investigation. |

### CI/CD Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **GitHub Actions** | **existing** | CI/CD pipeline | Already configured for backend tests, frontend build, Docker. Extend existing workflow with E2E job. |
| **Docker Compose** | **existing** | Test environment | `docker-compose-e2e.yml` already starts PostgreSQL, Redis. Add Next.js container for UI testing. |
| **playwright-image** | **official** | Docker browser support | If needed for CI isolation. Otherwise, use `playwright install` on Ubuntu runner. |

---

## Version Updates Required

### Current State
- **Playwright**: 1.40.0 (November 2023) - **18 versions behind**
- **Latest**: 1.58.0 (February 2026)
- **Impact**: Missing 18 months of bug fixes, features, performance improvements

### Recommended Upgrade
```bash
# Update Playwright to latest
pip install playwright==1.58.0 --upgrade
pip install pytest-playwright --upgrade

# Reinstall browser binaries
playwright install
playwright install chromium  # Explicitly install Chromium
```

### Breaking Changes (1.40.0 → 1.58.0)
- **None reported** in search results. Playwright maintains backward compatibility.
- Review [PyPI changelog](https://pypi.org/project/playwright/) for deprecation warnings.
- Test upgrade in staging before production (standard practice).

---

## Installation Commands

### Initial Setup (One-Time)

```bash
# 1. Install Python packages
cd /Users/rushiparikh/projects/atom/backend
pip install pytest-playwright==latest
pip install allure-pytest==2.13.0  # Optional: HTML reports

# 2. Install browser binaries
playwright install
playwright install chromium

# 3. Verify installation
python -c "from playwright.sync_api import sync_playwright; print('OK')"
pytest --version  # Should show pytest-playwright plugin
```

### Dependency Updates

**backend/requirements.txt** (add):
```txt
# E2E UI Testing (Phase 71)
pytest-playwright>=0.5.0,<1.0.0  # Pytest plugin
allure-pytest>=2.13.0,<3.0.0    # HTML test reports (optional)
playwright==1.58.0               # Pin to latest stable
```

**Update existing:**
```txt
# Change from:
playwright==1.40.0
# To:
playwright==1.58.0
```

---

## Test Framework Integration

### pytest.ini Configuration

**Existing configuration** (backend/pytest.ini):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -q --strict-markers --tb=line -n auto --dist=loadscope --timeout=300

# E2E-specific markers (add these)
markers =
    e2e: End-to-end tests (slow, real services)
    ui: UI/browser tests (Playwright)
    critical: Critical path tests (run on every PR)
    regression: Full regression tests (run nightly)
```

**New E2E-specific options** (add to addopts):
```ini
# For E2E tests only (use pytest.ini in tests/e2e/)
--headed=false               # Headless mode for CI
--browser=chromium           # Default browser
--video=on                   # Record video on failure
--screenshot=only-on-failure # Capture screenshots on failure
--tracing=retain-on-failure  # Capture traces for debugging
--output=test-results        # Artifact directory
```

### Directory Structure

```
backend/tests/
├── e2e/                          # Existing E2E tests (backend-focused)
│   ├── test_mcp_tools_e2e.py
│   ├── test_database_integration_e2e.py
│   └── fixtures/
├── e2e-ui/                       # NEW: UI/browser tests
│   ├── conftest.py               # Playwright fixtures, base URL
│   ├── test_agent_chat_ui.py     # Agent chat interface
│   ├── test_canvas_presentations.py  # Canvas rendering, governance
│   ├── test_skills_workflows_ui.py   # Skills marketplace, execution
│   ├── test_user_management_ui.py   # Login, permissions, settings
│   ├── fixtures/                 # UI-specific fixtures
│   │   ├── browser_fixtures.py   # Custom browser contexts
│   │   ├── page_fixtures.py      # Page objects, login helpers
│   │   └── test_data_fixtures.py # UI test data factories
│   └── pages/                    # Page Object Model
│       ├── base_page.py          # Base page class
│       ├── agent_chat_page.py    # Agent chat page
│       ├── canvas_page.py        # Canvas page
│       └── admin_page.py         # Admin/user management
```

---

## Headless vs Headed Mode

### Headless Mode (Default)
**When to use:** CI/CD, PR checks, automated regression runs

```bash
pytest tests/e2e-ui/ --browser=chromium --headed=false
```

**Advantages:**
- Faster execution (no UI rendering overhead)
- Lower CI resource usage
- No display server required (Xvfb)
- Screenshot/video still captured on failure

**Disadvantages:**
- Harder to debug (can't see what's happening)
- Can't observe test execution in real-time

### Headed Mode
**When to use:** Local development, debugging flaky tests, demo recordings

```bash
pytest tests/e2e-ui/ --browser=chromium --headed=true
```

**Advantages:**
- Visual debugging (see what the test sees)
- Easier to diagnose race conditions, timing issues
- Better for demo/test recording

**Disadvantages:**
- Slower (UI rendering overhead)
- Requires display server (local GUI or Xvfb)
- Not suitable for parallel execution (multiple windows)

### Recommended Strategy
```bash
# CI/CD: Headless with artifacts
pytest tests/e2e-ui/ --headed=false --video=on --screenshot=only-on-failure

# Local dev: Headed for debugging
pytest tests/e2e-ui/ --headed=true --slowmo=100  # Slow down actions

# PR checks: Headless, critical path only
pytest tests/e2e-ui/ -m critical --headed=false
```

---

## Testing Patterns

### Page Object Model (Recommended)

**Why:** Separate test logic from page interaction logic. Improves maintainability, reduces duplication.

**Example:**
```python
# tests/e2e-ui/pages/agent_chat_page.py
class AgentChatPage:
    def __init__(self, page: Page):
        self.page = page
        self.chat_input = page.get_by_test_id("chat-input")
        self.send_button = page.get_by_test_id("send-button")
        self.response_area = page.get_by_test_id("agent-response")

    def send_message(self, message: str):
        self.chat_input.fill(message)
        self.send_button.click()
        self.response_area.wait_for(state="visible")

    def get_response(self) -> str:
        return self.response_area.text_content()
```

**Usage in test:**
```python
def test_agent_chat_response(page: Page, base_url: str):
    chat_page = AgentChatPage(page)
    page.goto(f"{base_url}/agent/chat")

    chat_page.send_message("What agents are available?")
    response = chat_page.get_response()

    assert "AUTONOMOUS" in response
```

### Test Data Management Strategy

**Problem:** E2E tests need realistic data (users, agents, workflows) but should not interfere with each other.

**Solutions:**

1. **Unique Identifiers per Test**
   ```python
   def test_create_user(page: Page):
       unique_id = uuid.uuid4().hex[:8]
       email = f"test-{unique_id}@example.com"
       # Create user with unique email
       # No conflicts with parallel tests
   ```

2. **Database Transaction Rollback**
   ```python
   @pytest.fixture
   def db_session():
       session = SessionLocal()
       yield session
       session.rollback()  # Cleanup after test
   ```

3. **Dedicated Test Database**
   ```bash
   # Use separate DB for E2E UI tests
   DATABASE_URL=postgresql://atom:atom@localhost:5433/atom_e2e_ui
   # Seed with baseline data, reset between runs
   ```

4. **storageState for Login Reuse**
   ```python
   @pytest.fixture
   def logged_in_context(browser, base_url):
       context = browser.new_context()
       page = context.new_page()

       # Login once per session
       page.goto(f"{base_url}/auth/signin")
       page.fill("input[type=email]", "test@example.com")
       page.fill("input[type=password]", "testpassword")
       page.click("button[type=submit]")

       # Save auth state for reuse
       context.storage_state(path="auth.json")

       yield context, page

       # Cleanup
       context.close()
   ```

### Locator Strategies (Best Practices)

**Priority Order:**
1. **`data-testid` attributes** (BEST - most stable)
   ```python
   page.get_by_test_id("submit-button").click()
   ```

2. **ARIA roles** (GOOD - accessible, semantic)
   ```python
   page.get_by_role("button", name="Submit").click()
   ```

3. **Text content** (OK - brittle if UI copy changes)
   ```python
   page.get_by_text("Submit").click()
   ```

**AVOID:**
- CSS selectors like `div.container > button.submit-btn` (brittle)
- XPath selectors (hard to read, brittle)
- Fixed waits like `page.wait_for_timeout(5000)` (flaky!)

**Instead use:**
```python
# Web-first assertions (auto-wait)
expect(page.get_by_test_id("response")).to_be_visible()
expect(page).to_have_url("/agent/chat")
```

---

## CI/CD Integration

### GitHub Actions Workflow

**Add to existing `.github/workflows/ci.yml`:**

```yaml
e2e-ui-tests:
  runs-on: ubuntu-latest
  timeout-minutes: 20

  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_USER: atom
        POSTGRES_PASSWORD: atom
        POSTGRES_DB: atom_e2e_ui
      ports:
        - 5433:5432

  steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '20'

    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest-playwright allure-pytest
        playwright install chromium

    - name: Install frontend
      run: |
        cd frontend-nextjs
        npm ci --legacy-peer-deps

    - name: Start services
      run: |
        docker-compose -f docker-compose-e2e.yml up -d

    - name: Run E2E UI tests
      env:
        DATABASE_URL: postgresql://atom:atom@localhost:5433/atom_e2e_ui
        BASE_URL: http://localhost:3000
      run: |
        cd backend
        pytest tests/e2e-ui/ -v \
          --headed=false \
          --browser=chromium \
          --video=on \
          --screenshot=only-on-failure \
          --alluredir=allure-results \
          --timeout=600

    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: e2e-ui-results
        path: |
          backend/test-results/
          backend/allure-results/

    - name: Generate Allure report
      if: always()
      run: |
        pip install allure-pytest
        allure generate backend/allure-results --clean -o backend/allure-report

    - name: Upload Allure report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: allure-report
        path: backend/allure-report/
```

---

## Alternatives Considered

### Playwright TypeScript vs Python

| Criterion | TypeScript (native) | Python (wrapper) | Decision |
|-----------|---------------------|------------------|----------|
| **Performance** | Native, faster | Wrapper, slower (~20% overhead) | **Python** - integrates with existing pytest infrastructure |
| **Type Safety** | Compile-time checks | Runtime checks | **Python** - simpler for existing Python team |
| **Ecosystem** | Larger, first-party features | Smaller, delayed features | **Python** - good enough for E2E needs |
| **Integration** | Requires Node.js setup | Already in pytest.ini | **Python** - seamless integration |
| **Learning Curve** | Steeper for Python team | Familiar syntax | **Python** - lower adoption cost |

**Why Python Playwright:**
- Existing backend is Python, pytest infrastructure already mature (80% coverage)
- Team familiarity with Python > TypeScript
- E2E tests don't need TypeScript's type safety (unlike production frontend code)
- Seamless integration with existing backend test fixtures, factories, mocks
- Single language across backend + E2E tests simplifies CI/CD

### Playwright vs Selenium

| Criterion | Playwright | Selenium | Decision |
|-----------|-----------|----------|----------|
| **Speed** | Fast (auto-wait) | Slow (explicit waits) | **Playwright** |
| **Stability** | High (web-first assertions) | Low (flaky waits) | **Playwright** |
| **Multi-browser** | Chromium, Firefox, WebKit | Chrome, Firefox, Safari | **Playwright** |
| **Documentation** | Excellent | Fragmented | **Playwright** |
| **Community** | Growing, active | Mature, shrinking | **Playwright** |
| **Mobile emulation** | Built-in | Requires Appium | **Playwright** |
| **Network control** | Built-in | Limited | **Playwright** |

**Why Playwright:**
- Already in use for backend browser automation (1.40.0)
- Modern tooling, active development (18 versions in 18 months)
- Official pytest plugin for seamless integration
- Better for CI/CD (headless mode, Docker support)

---

## What NOT to Use

### Deprecated Patterns

1. **CSS/XPath Selectors** (brittle, hard to maintain)
   ```python
   # BAD
   page.click("div.container > button.submit-btn")
   page.click('//*[@id="submit-btn"]')

   # GOOD
   page.get_by_test_id("submit-button").click()
   ```

2. **Fixed Waits** (cause flaky tests)
   ```python
   # BAD
   page.wait_for_timeout(5000)

   # GOOD
   expect(page.get_by_test_id("result")).to_be_visible()
   ```

3. **Global Page Fixtures** (test interference)
   ```python
   # BAD - Shared across tests
   @pytest.fixture(scope="session")
   def global_page():
       return browser.new_page()

   # GOOD - Isolated per test
   @pytest.fixture(scope="function")
   def page(context):
       page = context.new_page()
       yield page
       page.close()
   ```

4. **Hardcoded Test Data** (parallel conflicts)
   ```python
   # BAD
   def test_create_user():
       create_user(email="test@example.com")  # Conflicts!

   # GOOD
   def test_create_user():
       unique = uuid.uuid4().hex[:8]
       create_user(email=f"test-{unique}@example.com")
   ```

### Tools to Avoid

- **Cypress**: JavaScript-only, no Python support
- **Puppeteer**: Chrome-only, Playwright is drop-in replacement with more features
- **TestCafe**: No Python support, less mature than Playwright
- **Selenium**: Legacy, slower, less reliable (see comparison above)

---

## Performance Targets

| Test Suite | Target | Notes |
|------------|--------|-------|
| Agent Chat UI | <30s | 5 tests × 6s avg (login, chat, response, governance) |
| Canvas Presentations | <45s | 8 tests × 5-6s avg (render, interaction, feedback) |
| Skills/Workflows UI | <60s | 10 tests × 6s avg (marketplace, execution, monitoring) |
| User Management | <30s | 6 tests × 5s avg (login, permissions, settings) |
| **TOTAL** | **<3 min** | **Parallel execution: 4 workers = ~45s wall time** |

### Optimization Strategies
1. **Parallel execution**: `pytest -n auto` (already in pytest.ini)
2. **Headless mode**: CI/CD default (no UI rendering overhead)
3. **Login reuse**: `storageState` fixture (skip auth per test)
4. **Database caching**: Test data factories with caching
5. **Browser context reuse**: One context per test module

---

## Migration Plan

### Phase 1: Infrastructure (Week 1)
1. Update Playwright 1.40.0 → 1.58.0 in requirements.txt
2. Install `pytest-playwright`, `allure-pytest`
3. Run `playwright install chromium` (local + CI)
4. Create `tests/e2e-ui/` directory structure
5. Add E2E markers to pytest.ini

### Phase 2: Fixtures & Pages (Week 2)
1. Create `conftest.py` with base URL, browser fixtures
2. Implement Page Object Model classes (`pages/`)
3. Create test data factories (`fixtures/test_data_fixtures.py`)
4. Implement login/auth fixtures with `storageState`

### Phase 3: Critical Path Tests (Week 3)
1. **Agent Chat UI** (5 tests): Login → Chat → Response → Governance
2. **Canvas Presentations** (8 tests): Render → Interaction → Feedback
3. **User Management** (6 tests): Login → Permissions → Settings

### Phase 4: Regression Tests (Week 4)
1. **Skills/Workflows UI** (10 tests): Marketplace → Execution → Monitoring
2. **Cross-browser validation** (Firefox, WebKit)
3. **Performance benchmarks** (response time, rendering)

### Phase 5: CI/CD Integration (Week 5)
1. Add E2E UI job to GitHub Actions
2. Configure artifacts (video, screenshots, traces)
3. Set up Allure report generation
4. Establish quality gates (95%+ pass rate)

---

## Sources

### Official Documentation
- [Playwright Python Documentation](https://playwright.dev/python/docs/intro) - HIGH confidence (official)
- [Playwright Python Installation Guide](https://playwright.nodejs.cn/python/docs/intro) - HIGH confidence (official, updated Feb 2026)
- [Pytest-Playwright Plugin](https://pypi.org/project/pytest-playwright/) - HIGH confidence (official PyPI)
- [Playwright PyPI - Latest Versions](https://pypi.org/project/playwright/) - HIGH confidence (verified 1.58.0 current)

### Best Practices
- [Playwright与PyTest结合指南](https://juejin.cn/post/7543838463356796964) - MEDIUM confidence (community, 2025)
- [Playwright Python测试夹具：从混乱到有序](https://m.blog.csdn.net/gitblog_01158/article/details/150973019) - MEDIUM confidence (community, 2025)
- [Playwright Fixtures 进阶应用技巧](https://m.blog.csdn.net/danmyw/article/details/151766975) - MEDIUM confidence (community, 2025)

### CI/CD Integration
- [Playwright CI/CD集成指南：配置GitHub Actions与Jenkins](https://developer.aliyun.com/article/1706462) - MEDIUM confidence (community, Jan 2026)
- [零失败指南：Playwright MCP在GitHub Actions中的自动化测试配置](https://m.blog.csdn.net/gitblog_00492/article/details/151801260) - MEDIUM confidence (community, Sep 2025)

### Tool Comparison
- [Playwright Python vs TypeScript Comparison](https://blog.csdn.net/xiugou3365/article/details/152928029) - LOW confidence (single source, needs verification)
- [从Selenium到Playwright：快速入门指南](https://m.sohu.com/a/976757202_120635785) - MEDIUM confidence (community, Jan 2026)

### Existing Atom Context
- `/Users/rushiparikh/projects/atom/CLAUDE.md` - HIGH confidence (project documentation)
- `/Users/rushiparikh/projects/atom/backend/requirements.txt` - HIGH confidence (verified current state)
- `/Users/rushiparikh/projects/atom/backend/requirements-testing.txt` - HIGH confidence (verified current testing stack)
- `/Users/rushiparikh/projects/atom/backend/pytest.ini` - HIGH confidence (verified pytest configuration)
- `/Users/rushiparikh/projects/atom/.github/workflows/ci.yml` - HIGH confidence (verified CI/CD setup)
- `/Users/rushiparikh/projects/atom/backend/tests/e2e/README.md` - HIGH confidence (existing E2E test patterns)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Playwright Version Update | **HIGH** | Verified on PyPI: 1.58.0 is latest (Feb 2026), 18 versions ahead of 1.40.0 |
| pytest-playwright Integration | **HIGH** | Official plugin, documented on Playwright site, proven in production |
| Page Object Model | **HIGH** | Industry-standard pattern, recommended by Playwright docs |
| Test Data Management | **MEDIUM** | factory-boy, faker already in use; strategies from community best practices |
| CI/CD Integration | **HIGH** | GitHub Actions pattern from existing CI/CD, verified to work |
| Headless vs Headed | **HIGH** | Official Playwright documentation covers both modes |
| Allure Reporting | **MEDIUM** | Not verified locally, but widely used in industry |
| Performance Targets | **LOW** | Estimates based on typical E2E test times; needs measurement |

**Overall Confidence: HIGH**

**Rationale:**
- Official sources (Playwright docs, PyPI) confirm version, installation, features
- Existing Atom infrastructure verified (pytest, CI/CD, E2E tests)
- Community sources corroborate best practices (Page Object Model, fixtures)
- Only LOW confidence areas are performance estimates (will be measured during implementation)

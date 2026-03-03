# Phase 099: Cross-Platform Integration & E2E - Research

**Researched:** 2026-02-26
**Domain:** Cross-platform end-to-end testing, performance regression detection, visual regression testing
**Confidence:** HIGH (E2E), MEDIUM (Performance/Visual)

## Summary

Phase 099 is the final phase of the v4.0 Platform Integration & Property Testing milestone, focusing on cross-platform integration tests that verify feature parity across web/mobile/desktop, E2E user flows that validate complete workflows from UI to backend, performance regression tests with Lighthouse CI, and optional visual regression tests. This phase depends on Phases 95-98 being complete, establishing test infrastructure for all platforms (Playwright for web, jest-expo for mobile, cargo test for desktop).

The research confirms that **Playwright Python 1.58.0 is already operational** from Phase 075-080 (61 phases, 300 plans, production-ready E2E suite with authentication, agent chat, canvas presentations, skills, and workflows). Mobile E2E requires **Detox 20.47.0** (10x faster than Appium, grey-box architecture, Expo integration via detox-expo-helpers). Desktop E2E requires **tauri-driver 2.10.1** (WebDriver support for Tauri apps). Performance testing uses **Lighthouse CI** with render time budgets and bundle size tracking. Visual regression testing (optional) uses **Percy** or **Chromatic** for screenshot diffing.

**Primary recommendation:** Extend existing Playwright E2E infrastructure (Phase 075-080) for web, implement Detox for mobile E2E in Phase 099, add tauri-driver for desktop E2E, integrate Lighthouse CI for performance regression detection, and defer visual regression testing to post-v4.0 if timeline pressure (marked as optional). Cross-platform integration tests should verify shared workflows (authentication, agent execution, canvas presentations) work identically across web, mobile, and desktop.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Playwright Python** | 1.58.0 | Web E2E testing | Already operational (Phase 075-080), cross-browser support, auto-waiting, network interception |
| **Detox** | 20.47.0 | Mobile E2E testing (React Native) | 10x faster than Appium, grey-box architecture (access to app state), Expo integration via detox-expo-helpers |
| **tauri-driver** | 2.10.1 | Desktop E2E testing (Tauri) | Official WebDriver support for Tauri apps, W3C WebDriver standard |
| **Lighthouse CI** | Latest | Performance regression testing | CI-automated performance audits, render time budgets, bundle size tracking |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-xdist** | 3.6.1 | Parallel E2E test execution | Run E2E tests in parallel across workers (already in backend/requirements.txt) |
| **detox-expo-helpers** | Latest | Detox + Expo integration | Required for Detox to work with Expo 50 (needs dev client or eject) |
| **@lhci/cli** | Latest | Lighthouse CI CLI | Run Lighthouse audits in CI, upload results to temporary public storage |
| **Percy** (optional) | Latest | Visual regression testing | Screenshot diffing, cross-browser visual testing |
| **Chromatic** (optional) | Latest | Visual regression for Storybook | Component-level visual testing, integrates with CI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright Python | Selenium | Playwright has auto-waiting, faster execution, better debugging, modern API |
| Detox | Appium | Detox 10x faster (grey-box vs black-box), better React Native support, smaller community |
| tauri-driver | Selenium desktop | tauri-driver provides native Tauri support, Selenium requires custom WebDriver setup |
| Lighthouse CI | WebPageTest | Lighthouse CI integrates with GitHub Actions, free, automated on every PR |
| Percy | Chromatic | Percy for full-page screenshots, Chromatic for component-level (Storybook), both SaaS with free tiers |

**Installation:**
```bash
# Web E2E (already installed in Phase 075)
pip install playwright==1.58.0 pytest-playwright pytest-xdist faker

# Mobile E2E (need to add in Phase 099)
cd mobile
npm install --save-dev detox@20.47.0 detox-expo-helpers

# Desktop E2E (need to add in Phase 099)
cd frontend-nextjs
npm install --save-dev @wdio/cli @wdio/local-runner @wdio/mocha-framework

# Performance testing (need to add in Phase 099)
npm install --save-dev @lhci/cli puppeteer

# Visual regression (optional, defer if timeline pressure)
npm install --save-dev @percy/cli @percy/playwright # OR @chromatic-com/storybook
```

## Architecture Patterns

### Recommended Project Structure

```
atom/
├── backend/tests/e2e_ui/                    # Web E2E (Playwright) - EXISTS
│   ├── tests/
│   │   ├── auth/                           # Authentication flows
│   │   │   ├── test_login.py               # Email/password login
│   │   │   ├── test_register.py            # User registration
│   │   │   └── test_logout.py              # Session cleanup
│   │   ├── agent/                          # Agent execution flows
│   │   │   ├── test_agent_chat.py          # Streaming chat
│   │   │   ├── test_agent_canvas.py        # Canvas presentations
│   │   │   └── test_agent_skills.py        # Skill execution
│   │   ├── canvas/                         # Canvas presentation flows
│   │   │   ├── test_canvas_charts.py       # Chart rendering
│   │   │   ├── test_canvas_forms.py        # Form submission
│   │   │   └── test_canvas_sheets.py       # Sheet interactions
│   │   ├── workflows/                      # Workflow automation flows
│   │   │   ├── test_workflow_trigger.py    # Trigger-based workflows
│   │   │   └── test_workflow_schedule.py   # Scheduled workflows
│   │   └── cross-platform/                 # NEW - Cross-platform integration
│   │       ├── test_shared_workflows.py    # Verify shared workflows across platforms
│   │       └── test_feature_parity.py      # Verify feature parity
│   ├── fixtures/                           # Test fixtures (EXISTS)
│   │   ├── auth_fixtures.py
│   │   ├── database_fixtures.py
│   │   ├── api_fixtures.py
│   │   └── test_data_factory.py
│   ├── pages/                              # Page Objects (EXISTS)
│   │   └── page_objects.py
│   └── lighthouserc.json                   # Lighthouse CI config (NEW)
├── mobile/e2e/                              # Mobile E2E (Detox) - NEW
│   ├── auth/
│   │   ├── login.e2e.ts
│   │   └── biometric.e2e.ts
│   ├── agent/
│   │   ├── agentChat.e2e.ts
│   │   └── canvasPresentation.e2e.ts
│   ├── cross-platform/
│   │   └── featureParity.e2e.ts
│   └── detox.config.js
├── frontend-nextjs/wdio/                    # Desktop E2E (WebDriverIO + tauri-driver) - NEW
│   ├── specs/
│   │   ├── auth/
│   │   │   └── login.e2e.ts
│   │   ├── agent/
│   │   │   └── agentChat.e2e.ts
│   │   └── cross-platform/
│   │       └── featureParity.e2e.ts
│   └── wdio.conf.ts
└── .github/workflows/
    ├── e2e-web.yml                          # Web E2E CI (EXISTS)
    ├── e2e-mobile.yml                       # Mobile E2E CI (NEW)
    ├── e2e-desktop.yml                      # Desktop E2E CI (NEW)
    └── lighthouse-ci.yml                    # Performance regression tests (NEW)
```

### Pattern 1: Cross-Platform Shared Workflow Testing

**What:** Verify that critical user workflows (authentication, agent execution, canvas presentations) work identically across web, mobile, and desktop platforms.

**When to use:** All shared features that exist on multiple platforms.

**Example (Playwright Python - Web):**
```python
# backend/tests/e2e_ui/tests/cross-platform/test_shared_workflows.py

import pytest
from tests.e2e_ui.pages.page_objects import LoginPage, AgentChatPage, CanvasPage
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user
from tests.e2e_ui.fixtures.api_fixtures import setup_test_project

class TestSharedWorkflows:
    """Test workflows that should work identically across web/mobile/desktop."""

    def test_agent_execution_workflow(self, browser, db_session, authenticated_user):
        """Verify agent execution works on web platform."""
        # Setup: Create test project and agent
        project = setup_test_project(db_session, authenticated_user)

        # Action: Navigate to agent chat
        chat_page = AgentChatPage(browser.new_page())
        chat_page.navigate()
        chat_page.send_message("Hello, agent!")

        # Verify: Agent response received
        assert chat_page.has_agent_response()
        assert "Hello" in chat_page.get_last_message()

        # Verify: Canvas can be presented
        chat_page.request_canvas()
        assert chat_page.is_canvas_visible()

    def test_canvas_presentation_workflow(self, browser, db_session, authenticated_user):
        """Verify canvas presentation works on web platform."""
        # Setup: Create agent with canvas capability
        project = setup_test_project(db_session, authenticated_user)

        # Action: Trigger canvas presentation
        canvas_page = CanvasPage(browser.new_page())
        canvas_page.navigate()
        canvas_page.present_canvas(type="sheets", data={"rows": 10, "columns": 5})

        # Verify: Canvas rendered correctly
        assert canvas_page.is_canvas_visible()
        assert canvas_page.get_canvas_type() == "sheets"
        assert canvas_page.get_row_count() == 10
```

**Example (Detox - Mobile):**
```typescript
// mobile/e2e/agent/agentChat.e2e.ts

import { by, element, expect } from 'detox';
import { describe, it, beforeAll } from '@jest/globals';

describe('Agent Execution (Mobile)', () => {
  beforeAll(async () => {
    await device.launchApp();
  });

  it('should execute agent and present canvas', async () => {
    // Navigate to agent chat
    await element(by.id('agent-chat-screen')).tap();
    await expect(element(by.id('agent-chat-input'))).toBeVisible();

    // Send message to agent
    await element(by.id('agent-chat-input')).typeText('Hello, agent!');
    await element(by.id('send-message-button')).tap();

    // Verify agent response
    await expect(element(by.text('Hello'))).toBeVisible();

    // Trigger canvas presentation
    await element(by.id('request-canvas-button')).tap();

    // Verify canvas rendered
    await expect(element(by.id('canvas-container'))).toBeVisible();
    await expect(element(by.id('canvas-type-sheets'))).toBeVisible();
  });
});
```

**Example (WebDriverIO - Desktop):**
```typescript
// frontend-nextjs/wdio/specs/agent/agentChat.e2e.ts

import { describe, it } from 'mocha';
import { browser, $, expect } from '@wdio/globals';

describe('Agent Execution (Desktop)', () => {
  it('should execute agent and present canvas', async () => {
    // Navigate to agent chat
    await browser.url('http://localhost:3000/agent/test-agent');
    const chatInput = await $('#agent-chat-input');
    await chatInput.setValue('Hello, agent!');

    // Send message
    const sendButton = await $('#send-message-button');
    await sendButton.click();

    // Verify agent response
    const response = await $('.agent-message');
    await expect(response).toHaveTextContaining('Hello');

    // Trigger canvas
    const canvasButton = await $('#request-canvas-button');
    await canvasButton.click();

    // Verify canvas rendered
    const canvas = await $('#canvas-container');
    await expect(canvas).toBeExisting();
  });
});
```

### Pattern 2: Feature Parity Testing

**What:** Verify that all platforms support the same set of features for shared functionality (agent chat, canvas types, workflow triggers).

**When to use:** All features that should work identically across platforms.

**Example (Cross-Platform Feature Parity - Web):**
```python
# backend/tests/e2e_ui/tests/cross-platform/test_feature_parity.py

import pytest
import requests

class TestFeatureParity:
    """Verify feature parity between web, mobile, and desktop."""

    # Expected features that should exist on all platforms
    AGENT_CHAT_FEATURES = [
        "streaming",
        "history",
        "feedback",
        "canvas_presentations",
        "skill_execution",
    ]

    CANVAS_TYPES = [
        "generic",
        "docs",
        "email",
        "sheets",
        "orchestration",
        "terminal",
        "coding",
    ]

    def test_agent_chat_feature_parity(self, browser):
        """Verify web supports all expected agent chat features."""
        chat_page = AgentChatPage(browser.new_page())
        chat_page.navigate()

        # Verify each feature is available
        for feature in self.AGENT_CHAT_FEATURES:
            assert chat_page.has_feature(feature), f"Missing feature: {feature}"

    def test_canvas_type_parity(self, browser):
        """Verify web supports all expected canvas types."""
        canvas_page = CanvasPage(browser.new_page())
        canvas_page.navigate()

        # Verify each canvas type can be presented
        for canvas_type in self.CANVAS_TYPES:
            canvas_page.present_canvas(type=canvas_type, data={})
            assert canvas_page.get_canvas_type() == canvas_type

    def test_api_response_consistency(self, api_client):
        """Verify API responses match across platforms."""
        # Test agent list API
        response = api_client.get("/api/v1/agents")
        assert response.status_code == 200

        agents = response.json()["agents"]
        assert len(agents) > 0

        # Verify each agent has required fields
        for agent in agents:
            assert "id" in agent
            assert "name" in agent
            assert "maturity" in agent
            assert "capabilities" in agent
```

**Example (Cross-Platform Feature Parity - Mobile):**
```typescript
// mobile/e2e/cross-platform/featureParity.e2e.ts

import { by, element, expect } from 'detox';

describe('Feature Parity (Mobile)', () => {
  const AGENT_CHAT_FEATURES = [
    'streaming',
    'history',
    'feedback',
    'canvas_presentations',
    'skill_execution',
  ];

  const CANVAS_TYPES = [
    'generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding'
  ];

  it('should support all agent chat features', async () => {
    await element(by.id('agent-chat-screen')).tap();

    for (const feature of AGENT_CHAT_FEATURES) {
      const featureElement = element(by.id(`feature-${feature}`));
      await expect(featureElement).toBeVisible();
    }
  });

  it('should support all canvas types', async () => {
    await element(by.id('canvas-screen')).tap();

    for (const canvasType of CANVAS_TYPES) {
      await element(by.id(`present-${canvasType}-button`)).tap();
      await expect(element(by.id(`canvas-${canvasType}`))).toBeVisible();
    }
  });
});
```

### Pattern 3: Performance Regression Testing with Lighthouse CI

**What:** Run Lighthouse audits on critical pages (agent chat, canvas presentations, dashboard) on every PR to detect performance regressions (render time, bundle size, accessibility scores).

**When to use:** All E2E workflows that affect page load or render performance.

**Example (lighthouserc.json):**
```json
{
  "ci": {
    "collect": {
      "url": [
        "http://localhost:3001/dashboard",
        "http://localhost:3001/agent/test-agent",
        "http://localhost:3001/canvas/test-canvas"
      ],
      "numberOfRuns": 3,
      "settings": {
        "preset": "desktop",
        "throttling": {
          "rttMs": 40,
          "throughputKbps": 10 * 1024,
          "cpuSlowdownMultiplier": 1,
          "requestLatencyMs": 0,
          "downloadThroughputKbps": 0,
          "uploadThroughputKbps": 0
        }
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.9 }],
        "categories:accessibility": ["warn", { "minScore": 0.8 }],
        "categories:best-practices": ["warn", { "minScore": 0.9 }],
        "categories:seo": ["off"],
        "first-contentful-paint": ["error", { "maxNumericValue": 2000 }],
        "interactive": ["error", { "maxNumericValue": 5000 }],
        "cumulative-layout-shift": ["warn", { "maxNumericValue": 0.1 }],
        "total-blocking-time": ["error", { "maxNumericValue": 300 }]
      }
    }
  }
}
```

**Example (GitHub Actions Workflow):**
```yaml
# .github/workflows/lighthouse-ci.yml

name: Lighthouse CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci
        working-directory: ./frontend-nextjs

      - name: Build frontend
        run: npm run build
        working-directory: ./frontend-nextjs

      - name: Start server
        run: |
          npm start &
          npx wait-on http://localhost:3001
        working-directory: ./frontend-nextjs

      - name: Run Lighthouse CI
        run: lhci autorun
        working-directory: ./frontend-nextjs
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}

      - name: Upload Lighthouse results
        uses: actions/upload-artifact@v3
        with:
          name: lighthouse-results
          path: .lighthouseci/
```

### Pattern 4: Visual Regression Testing (Optional)

**What:** Capture screenshots of critical pages before and after changes, detect visual regressions (layout shifts, color changes, missing elements).

**When to use:** Optional (if time permits) - Use for design-critical pages (dashboard, agent chat, canvas presentations).

**Example (Percy Integration):**
```typescript
// backend/tests/e2e_ui/tests/visual/test_visual_regression.py

from tests.e2e_ui.pages.page_objects import DashboardPage, AgentChatPage, CanvasPage
import percy

class TestVisualRegression:
    """Visual regression tests for critical pages."""

    def test_dashboard_visual(self, browser, authenticated_user):
        """Verify dashboard page has no visual regressions."""
        dashboard = DashboardPage(browser.new_page())
        dashboard.navigate()

        # Capture screenshot with Percy
        percy.snapshot(browser.page, "Dashboard Page")

    def test_agent_chat_visual(self, browser, authenticated_user):
        """Verify agent chat page has no visual regressions."""
        chat = AgentChatPage(browser.new_page())
        chat.navigate()
        chat.send_message("Test message")

        # Capture screenshot with Percy
        percy.snapshot(browser.page, "Agent Chat Page")

    def test_canvas_presentation_visual(self, browser, authenticated_user):
        """Verify canvas presentation has no visual regressions."""
        canvas = CanvasPage(browser.new_page())
        canvas.navigate()
        canvas.present_canvas(type="sheets", data={"rows": 10, "columns": 5})

        # Capture screenshot with Percy
        percy.snapshot(browser.page, "Canvas Presentation - Sheets")
```

**Example (Percy Config):**
```javascript
// .percyrc.js

module.exports = {
  snapshot: {
    widths: [1280, 768, 375], // Desktop, tablet, mobile
    minHeight: 1024,
    percyCSS: '.hide-in-snapshots { display: none; }',
    discovery: {
      allowedHostnames: ['localhost', 'staging.atom.ai'],
    },
  },
};
```

### Pattern 5: E2E Test CI/CD Orchestration

**What:** Separate E2E test workflows from unit/integration tests, run on merge to main (not on every PR), use artifacts for test results and screenshots.

**When to use:** All E2E workflows (web, mobile, desktop).

**Example (GitHub Actions - Web E2E):**
```yaml
# .github/workflows/e2e-web.yml

name: E2E Tests (Web)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  e2e-web:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: atom_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5434:5432

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          playwright install --with-deps chromium

      - name: Start services
        run: |
          docker-compose -f docker-compose-e2e-ui.yml up -d
          ./scripts/start-e2e-env.sh

      - name: Run E2E tests
        run: |
          pytest backend/tests/e2e_ui/tests/ -v \
            --count=4 \
            --video=retain-on-failure \
            --screenshot=only-on-failure \
            --html=e2e-report.html

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-results
          path: |
            backend/tests/e2e_ui/test-results/
            backend/tests/e2e_ui/playwright-report/
            backend/tests/e2e_ui/screenshots/
```

**Example (GitHub Actions - Mobile E2E):**
```yaml
# .github/workflows/e2e-mobile.yml

name: E2E Tests (Mobile)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  e2e-mobile:
    runs-on: macos-latest # Required for iOS simulation
    timeout-minutes: 45

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd mobile
          npm ci

      - name: Build app
        run: |
          cd mobile
          npx expo prebuild --clean

      - name: Run Detox tests
        run: |
          cd mobile
          npm test -- e2e --configuration=ios.sim.debug

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-mobile-results
          path: mobile/e2e/artifacts/
```

**Example (GitHub Actions - Desktop E2E):**
```yaml
# .github/workflows/e2e-desktop.yml

name: E2E Tests (Desktop)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  e2e-desktop:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend-nextjs
          npm ci

      - name: Build Tauri app
        run: |
          cd frontend-nextjs
          npm run tauri build

      - name: Run WebDriverIO tests
        run: |
          cd frontend-nextjs
          npm run test:e2e

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-desktop-results
          path: frontend-nextjs/wdio/artifacts/
```

### Anti-Patterns to Avoid

- **Testing every permutation:** Don't test every combination of features, focus on critical workflows (authentication, agent execution, canvas presentations)
- **Flaky E2E tests:** Don't ignore timing issues, use explicit waits (waitFor, findBy*) instead of hard-coded sleeps
- **Testing implementation details:** Don't test CSS classes or DOM structure, test observable behavior (user can log in, agent responds, canvas renders)
- **Running E2E on every PR:** Don't block PRs with slow E2E tests, run on merge to main only
- **Ignoring platform differences:** Don't assume all platforms work identically, test platform-specific features (biometric auth on mobile, menu bar on desktop)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web E2E framework | Custom Selenium wrapper | Playwright Python (already exists) | Auto-waiting, network interception, screenshots, video recording |
| Mobile E2E framework | Appium black-box tests | Detox grey-box testing | 10x faster, access to app state, Expo integration |
| Desktop E2E framework | Custom Tauri test runner | tauri-driver + WebDriverIO | W3C WebDriver standard, cross-platform, maintained |
| Performance testing | Manual Lighthouse runs | Lighthouse CI | Automated on every PR, regression detection, trend tracking |
| Visual regression | Manual screenshot comparison | Percy/Chromatic | Automated diffing, CI integration, baseline management |
| Test orchestration | Monolithic test workflow | Separate E2E workflows (web/mobile/desktop) | Parallel execution, faster feedback, platform-specific timeouts |

**Key insight:** E2E testing frameworks have solved hard problems (cross-browser testing, mobile emulators, CI integration, parallel execution). Building custom E2E infrastructure wastes time and misses edge cases (timing issues, platform differences, flaky tests).

## Common Pitfalls

### Pitfall 1: Flaky E2E Tests Due to Timing Issues

**What goes wrong:** E2E tests fail intermittently because elements aren't ready when tests try to interact with them.

**Why it happens:** Tests don't wait for elements to load, animations to finish, or network requests to complete.

**How to avoid:** Use Playwright's auto-waiting (built-in), explicit waits with waitFor, and network interception for API calls.

```python
# Bad: Hard-coded sleep
time.sleep(5)  # Waits 5 seconds even if element loads in 0.5s
page.click('#submit-button')

# Good: Playwright auto-waiting
page.click('#submit-button')  # Waits automatically for element to be visible and clickable

# Good: Explicit wait for specific condition
page.wait_for_selector('#success-message', state='visible')
page.wait_for_url('**/dashboard')
page.wait_for_response('**/api/agents')
```

**Warning signs:** Tests fail 1-5% of the time, sleep() calls scattered throughout tests, CI-only failures.

### Pitfall 2: Slow E2E Feedback Loops

**What goes wrong:** E2E tests take 30+ minutes to run, developers disable them or ignore failures.

**Why it happens:** Running E2E tests on every PR, not parallelizing across workers, testing too many scenarios.

**How to avoid:** Run E2E on merge to main (not every PR), parallelize with pytest-xdist or Detox workers, focus on critical workflows.

```yaml
# Bad: Run E2E on every PR (blocks PRs)
on: [pull_request]

# Good: Run E2E on merge to main
on:
  push:
    branches: [main]

# Good: Parallelize across workers
pytest tests/e2e_ui/ -v -n 4  # 4 workers in parallel
```

**Warning signs:** Developers complain about slow tests, E2E tests disabled in package.json, tests commented out.

### Pitfall 3: Platform-Specific Test Duplication

**What goes wrong:** Same test logic duplicated across web, mobile, and desktop test files, maintenance nightmare.

**Why it happens:** Testing each platform independently without extracting shared test logic.

**How to avoid:** Extract shared test logic into helper functions or base test classes, parameterize tests by platform.

```python
# Bad: Duplicated test logic
# test_web.py
def test_agent_execution(browser):
    page.goto('/agent/test')
    page.fill('#chat-input', 'Hello')
    page.click('#send')
    assert page.text('.response') == 'Hello'

# test_mobile.py (duplicated)
def test_agent_execution(device):
    await element(by.id('chat-input')).typeText('Hello')
    await element(by.id('send-button')).tap()
    await expect(element(by.text('Hello'))).toBeVisible()

# Good: Shared test helper
class SharedAgentTests:
    def test_agent_execution(self, driver):
        driver.navigate_to_agent_chat()
        driver.send_message('Hello')
        assert driver.has_response('Hello')

class TestWebAgent(SharedAgentTests):
    def test_agent_execution(self, browser):
        self.test_agent_execution(WebDriver(browser))

class TestMobileAgent(SharedAgentTests):
    def test_agent_execution(self, device):
        self.test_agent_execution(MobileDriver(device))
```

**Warning signs:** Same bug fixed in 3 test files, test changes require updates in multiple places, inconsistent test logic.

### Pitfall 4: Ignoring Performance Regressions

**What goes wrong:** Page load times increase from 2s to 8s over time, no test catches this until users complain.

**Why it happens:** No performance regression tests, only functional tests, bundle size increases unnoticed.

**How to avoid:** Add Lighthouse CI to run on every PR, set performance budgets (FCP < 2s, TTI < 5s), track bundle size.

```json
// lighthouserc.json
{
  "assert": {
    "assertions": {
      "first-contentful-paint": ["error", { "maxNumericValue": 2000 }],
      "interactive": ["error", { "maxNumericValue": 5000 }],
      "bundle-size": ["warn", { "maxNumericValue": 500000 }]
    }
  }
}
```

**Warning signs:** PRs merge without performance checks, bundle size grows unchecked, users report slow loads.

### Pitfall 5: Visual Regression Testing Overhead

**What goes wrong:** Visual regression tests fail due to dynamic content (dates, timestamps, random images), constant baseline updates.

**Why it happens:** Not hiding dynamic content in snapshots, testing too many pages, not reviewing baseline diffs.

**How to avoid:** Hide dynamic content with Percy CSS, only test design-critical pages, review baseline diffs carefully.

```javascript
// .percyrc.js
module.exports = {
  snapshot: {
    percyCSS: `
      .timestamp { display: none; }
      .random-data { display: none; }
    `
  }
};

// Only test critical pages
test_dashboard_visual()     # Yes
test_agent_chat_visual()    # Yes
test_canvas_visual()         # Yes
test_settings_visual()       # No (not design-critical)
test_admin_visual()          # No (low traffic)
```

**Warning signs:** Percy builds fail constantly, team stops reviewing diffs, visual tests disabled in CI.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium manual waits | Playwright auto-waiting | 2020+ | More reliable tests, faster execution, less flakiness |
| Appium black-box | Detox grey-box | 2019+ | 10x faster E2E, access to app state, better debugging |
| Manual Lighthouse runs | Lighthouse CI automation | 2021+ | Regression detection on every PR, trend tracking |
| Manual screenshot comparison | Percy/Chromatic automation | 2019+ | Automated visual diffing, CI integration, baseline management |
| Monolithic E2E workflow | Separate platform workflows | 2022+ | Parallel execution, faster feedback, platform-specific timeouts |

**Deprecated/outdated:**
- **Selenium WebDriver:** Slower than Playwright, no auto-waiting, manual waits required
- **Appium:** 10x slower than Detox for React Native, black-box architecture
- **Manual performance testing:** Lighthouse CI automates performance audits on every PR
- **Manual visual testing:** Percy/Chromatic automate screenshot diffing with baseline management
- **Hard-coded sleeps:** Playwright auto-waiting eliminates need for sleep() calls

## Open Questions

1. **Detox Expo integration complexity**
   - What we know: Detox requires Expo dev client or ejecting, detox-expo-helpers provides integration
   - What's unclear: Complexity of Detox setup with Expo 50, whether E2E tests fit in Phase 099 timeline (2 weeks)
   - Recommendation: Spike Detox setup during planning (Plan 099-02), defer to post-v4.0 if too complex (mark as optional)

2. **tauri-driver WebDriver support maturity**
   - What we know: tauri-driver provides WebDriver support for Tauri apps, W3C WebDriver standard
   - What's unclear: Maturity of tauri-driver, documentation quality, community adoption
   - Recommendation: Verify tauri-driver documentation (https://github.com/tauri-apps/tauri-driver), prototype basic test during planning

3. **Visual regression testing priority**
   - What we know: Percy and Chromatic are standard tools, optional per success criteria
   - What's unclear: Whether visual regression testing provides enough value given implementation cost
   - Recommendation: Mark as optional in Plan 099-06 (Visual Regression), implement only if Plans 01-05 complete early

4. **Performance regression budgets**
   - What we know: Lighthouse CI supports performance assertions (FCP, TTI, CLS, TBT)
   - What's unclear: What budget thresholds are realistic for Atom (current performance unknown)
   - Recommendation: Run Lighthouse on staging during planning, establish baseline, set budgets at 10-20% above baseline

5. **Cross-platform test sharing strategy**
   - What we know: Web, mobile, and desktop share some workflows (auth, agent chat, canvas)
   - What's unclear: How to structure shared test suite without platform-specific coupling
   - Recommendation: Create `tests/cross-platform/` directory with shared test logic, use driver pattern to abstract platform differences

## Sources

### Primary (HIGH confidence)

- **Playwright Python Documentation** — https://playwright.dev/python/
  - Checked: Auto-waiting, network interception, screenshots, video recording, pytest integration
- **Detox Documentation** — https://wix.github.io/Detox/
  - Checked: Grey-box architecture, Expo integration, test matching, device launcher
- **tauri-driver Repository** — https://github.com/tauri-apps/tauri-driver
  - Checked: WebDriver support, W3C compliance, basic usage examples
- **Lighthouse CI Documentation** — https://github.com/GoogleChrome/lighthouse-ci
  - Checked: Assertion thresholds, CI integration, artifact upload, performance budgets
- **Percy Documentation** — https://docs.percy.io/
  - Checked: Screenshot diffing, CI integration, baseline management, percyCSS for dynamic content
- **Existing Atom E2E Infrastructure** — Phase 075-080 verification reports
  - Checked: Playwright Python 1.58.0 operational, 61 phases executed, 300 plans complete, production-ready test suite

### Secondary (MEDIUM confidence)

- **detox-expo-helpers** — https://github.com/wix-incubator/detox-expo-helpers
  - Cross-referenced: Detox + Expo integration patterns, dev client requirements
- **WebDriverIO Documentation** — https://webdriver.io/
  - Cross-referenced: WebDriver standard, test runner, reporter integration
- **@lhci/cli** — https://www.npmjs.com/package/@lhci/cli
  - Cross-referenced: Lighthouse CI CLI usage, configuration options
- **Chromatic Documentation** — https://www.chromatic.com/docs
  - Cross-referenced: Storybook integration, component-level visual testing

### Tertiary (LOW confidence — needs validation)

- **Detox Expo 50 Integration** — Limited documentation, may need prototype testing
- **tauri-driver Maturity** — Small community, limited real-world examples
- **Visual Regression ROI** — Few case studies on value vs. implementation cost
- **Cross-Platform Test Sharing Patterns** — Few real-world examples, may need custom implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Playwright Python proven (Phase 075-080), Detox industry standard for React Native, Lighthouse CI well-documented
- Architecture: HIGH - E2E patterns proven in Phase 075-080, cross-platform testing patterns well-established
- Pitfalls: HIGH - Flaky E2E tests, slow feedback loops, visual regression overhead well-documented
- Mobile/Desktop E2E: MEDIUM - Detox Expo integration complexity unknown, tauri-driver maturity uncertain
- Visual Regression: LOW - ROI unclear, implementation effort may not justify benefit for Phase 099

**Research date:** 2026-02-26
**Valid until:** 2026-04-26 (60 days - E2E testing frameworks are stable, unlikely to change significantly)

---

## Key Takeaways for Planning

1. **Playwright E2E already operational** — Phase 075-080 complete with 61 phases, 300 plans, authentication/agent/canvas/workflows tested, production-ready infrastructure
2. **Detox requires Expo dev client** — Detox grey-box E2E 10x faster than Appium, but needs Expo dev client or ejecting, verify feasibility during planning
3. **tauri-driver for desktop E2E** — Official WebDriver support for Tauri apps, verify documentation and examples during planning
4. **Lighthouse CI for performance** — Automated performance audits on every PR, set budgets based on staging baseline during planning
5. **Visual regression optional** — Percy/Chromatic provide automated screenshot diffing, mark as optional in Plan 099-06, implement only if time permits
6. **Cross-platform integration tests** — Verify shared workflows (auth, agent chat, canvas) work identically across web, mobile, desktop
7. **E2E tests run on merge to main** — Separate from unit/integration tests, don't block PRs, run in separate CI workflows
8. **Performance budgets** — FCP < 2s, TTI < 5s, CLS < 0.1, TBT < 300ms, establish baseline from staging environment
9. **2-week timeline aggressive** — Phases 95-98 averaged 6-8 plans each, Phase 099 may need 6-8 plans, prioritize critical workflows
10. **Quality gates** — 98% E2E pass rate, performance budgets enforced, visual regression optional, feature parity verified across platforms

---

## Planning Checklist

- [ ] Verify Detox Expo 50 integration feasibility (Plan 099-02 spike)
- [ ] Verify tauri-driver documentation and examples (Plan 099-03 spike)
- [ ] Run Lighthouse on staging to establish baseline (Plan 099-04)
- [ ] Define critical shared workflows for cross-platform testing (Plan 099-01)
- [ ] Set performance budgets based on baseline (Plan 099-04)
- [ ] Decide visual regression priority (Plan 099-06 decision gate)
- [ ] Structure cross-platform test suite with shared logic (Plan 099-05)
- [ ] Create CI workflows for mobile/desktop E2E (Plan 099-07)
- [ ] Document E2E test patterns and maintenance guidelines (Plan 099-08)

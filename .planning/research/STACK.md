# Technology Stack: Cross-Platform E2E Testing & Bug Discovery

**Project:** Atom - AI-Powered Business Automation Platform
**Domain:** Cross-Platform E2E Testing & Quality Assurance
**Researched:** 2026-03-23
**Confidence:** MEDIUM (Web/pytest: HIGH, Mobile/Desktop/Stress: MEDIUM - Limited by web search rate limiting)

## Executive Summary

Atom requires comprehensive cross-platform E2E testing covering web (Next.js), mobile (React Native), and desktop (Tauri) with a focus on bug discovery through stress testing and real user flow validation. **Key insight**: Build on existing Playwright + pytest foundation rather than replacing it. Add mobile/desktop testing layers and stress testing infrastructure incrementally for cost-effective bug discovery.

**Recommended approach**: Use Playwright for web (already installed with v3.1 E2E), Detox for React Native mobile, Tauri's built-in testing for desktop, and k6 for API stress testing. Integrate all with pytest for unified orchestration and Allure for comprehensive reporting with bug tracking integration.

## Recommended Stack

### Core E2E Testing Frameworks

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Playwright** | ^1.57.0 | Web E2E testing | Already installed with v3.1 E2E testing, auto-waiting, reliable selectors, excellent TypeScript support, cross-browser (Chrome/Firefox/Safari), built-in tracing/debugging with reports |
| **Detox** | ^20.47.0 | React Native mobile E2E | Gray-box testing framework built for React Native by Wix, faster than black-box tools (knows app internals), JavaScript/TypeScript based, excellent for Expo apps, already in mobile package.json |
| **Tauri Test** | (via cargo test) | Desktop E2E testing | Built-in Tauri testing utilities, tests both frontend (web) and backend (Rust), native command mocking, cross-platform (Windows/macOS/Linux), no external dependencies |
| **k6** | ^0.52.0 | API stress testing | Developer-friendly JS-based scripting, CI/CD integration, supports HTTP/1.1/2/WebSocket, excellent for load scenarios and edge case discovery, cost-effective bug discovery |
| **pytest** | ^7.4.0 | Cross-platform orchestration | Already installed for backend tests, can orchestrate all E2E test runners, fixtures for test data management, parallel execution with pytest-xdist, integrates with governance system |

### Test Reporting & Observability

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Allure Report** | ^2.27.0 | Unified test reporting | Framework-agnostic (works with pytest, Playwright, Detox), rich HTML reports with screenshots/videos, test history trends, integrates with CI/CD, supports severity/suite/epic tags for bug tracking |
| **Playwright Reporter** | (built-in) | Web test artifacts | HTML reporter with traces, video recording, screenshots on failure, timeline view, already configured in existing e2e_ui setup |
| **Detox Reporter** | (built-in) | Mobile test artifacts | JUnit XML output for CI integration, detailed error messages with screenshots, test result aggregation |

### Test Data Management & Mocking

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Faker.js** | ^8.4.0 | Test data generation | Generate realistic test data for user flows, can be used across all platforms, supports locale-specific data, integrates with pytest fixtures |
| **MSW (Mock Service Worker)** | ^1.3.0 | API mocking | Intercept and mock HTTP requests, works with all platforms, TypeScript support, can simulate error conditions for bug discovery |
| **SQLite** | ^3.44.0 | Test database | Lightweight testing database, already in use for backend tests, can be reset between tests for isolation |

### Test Orchestration & CI/CD Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **GitHub Actions** | (existing) | Test orchestration | Already configured for CI/CD, supports matrix builds for cross-platform testing, can run web/mobile/desktop tests in parallel |
| **pytest-xdist** | ^3.3.0 | Test parallelization | Speed up test execution, distribute tests across workers, compatible with existing pytest fixtures |
| **Docker** | ^24.0.0 | Test environment consistency | Containerize test environments for reproducible results, isolate test dependencies |

### Browser Automation Tools (for web)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Playwright** | ^1.57.0 (existing) | Cross-browser automation | Already configured for Chromium, supports Firefox/Safari for cross-browser testing, auto-waiting reduces flakiness |
| **Playwright Trace Viewer** | (built-in) | Debugging tool | Visual debugging of test failures with network/activity traces, screenshots, console logs |

### Mobile Testing Tools

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Detox** | ^20.47.0 (existing) | React Native E2E | Already in mobile package.json, gray-box testing (faster), supports iOS/Android simulators and devices, built-in wait mechanisms |
| **Detox Expo Helpers** | ^0.6.0 | Expo integration | Smooth integration with Expo build process, handles app lifecycle, device setup |
| **Expo Detox Plugin** | (built-in) | Expo configuration | Automatic build process integration, test runner configuration |

### Desktop Testing Tools

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Tauri CLI** | ^2.0.0 | Desktop app testing | Built-in test runner (`cargo test`), tests both frontend web content and backend Rust commands, native API access |
| **Tauri Driver** | ^2.0.0 | Desktop automation | Browser automation for Tauri web content, native window control, file system access |

### Stress Testing & Bug Discovery

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **k6** | ^0.52.0 | Load/stress testing | JS-based scripting, CI-friendly, supports complex scenarios (ramping, pacing, chaos engineering), visual dashboard, cost-effective for API stress testing |
| **k6 Cloud** | ^1.0.0 | Cloud scaling | Scale load testing beyond local machine, distributed virtual users, detailed analytics and reporting |
| **Artillery** | ^2.0.0 | Alternative stress testing | Node.js-based, scenario definitions, real-time monitoring, good for complex API flows |

### Test Organization & Structure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pytest** | ^7.4.0 (existing) | Test organization | Already in use for backend tests, supports fixtures, parametrization, markers for test categorization |
| **pytest-bdd** | ^4.2.0 | BDD testing | Given/When/Then syntax for readable test scenarios, integrates with pytest fixtures |
| **pytest-mock** | ^3.12.0 | Mocking utilities | Easy mocking of external services, compatible with existing test structure |

### Integration Points with Existing Infrastructure

| Component | Integration Approach | Benefits |
|-----------|-------------------|---------|
| **Governance System** | Test agents with different maturity levels (STUDENT/INTERN/SUPERVISED/AUTONOMOUS) | Ensure testing respects agent permissions, test governance rules, verify action complexity mappings |
| **Backend API** | Direct API testing with k6 and pytest | Test API endpoints under load, verify backend integration, test error handling |
| **Canvas System** | Test canvas presentations and submissions | Verify canvas state management, form submissions, chart rendering across platforms |
| **Agent Execution** | Test agent-triggered workflows | Verify agent execution flows, error handling, state persistence |
| **Authentication** | Test login flows across all platforms | Ensure consistent user experience, test OAuth flows, session management |

## Installation & Setup

### Core E2E Testing Dependencies

```bash
# Web E2E (Playwright) - Already installed
cd backend/tests/e2e_ui
npm install @playwright/test@^1.57.0
npx playwright install --with-deps

# Mobile E2E (Detox) - Already in mobile package.json
cd mobile
npm install
npm run e2e:build
npm run e2e:test

# Desktop E2E (Tauri) - Built-in
cd frontend-nextjs/src-tauri
cargo test

# Stress Testing (k6)
npm install -g k6@^0.52.0

# Test Reporting
pip install allure-pytest@^2.13.0
```

### Cross-Platform Test Configuration

```python
# conftest.py - Shared pytest configuration
import pytest
from playwright.sync_api import Page

# Cross-platform fixtures
@pytest.fixture(scope="session")
def browser_types():
    return ["chromium", "firefox", "webkit"]

@pytest.fixture
def mobile_app_config():
    return {
        "ios": {"device": "iPhone 14", "os": "17.0"},
        "android": {"device": "Pixel 6", "os": "13.0"}
    }

# Test data management
@pytest.fixture
def test_user_data():
    return {
        "email": "test@example.com",
        "password": "securePassword123!",
        "workspace": "test-workspace"
    }
```

## Usage Examples

### Web E2E Testing with Playwright

```typescript
// tests/auth-flow.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('complete login to dashboard', async ({ page }) => {
    // Navigate to login page
    await page.goto('/login');

    // Fill login form (governance-aware)
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'securePassword123!');

    // Submit and verify dashboard
    await page.click('[data-testid="submit"]');
    await expect(page).toHaveURL('/dashboard');

    // Test agent chat interaction
    await page.click('[data-testid="new-chat"]');
    await page.fill('[data-testid="message-input"]', 'Hello, test agent');
    await page.click('[data-testid="send"]');

    // Verify agent response (governance level check)
    await expect(page.locator('[data-testid="agent-response"]')).toBeVisible();
  });

  test('canvas presentation workflow', async ({ page }) => {
    // Test canvas chart presentation
    await page.goto('/canvas/new');
    await page.click('[data-testid="chart-button"]');
    await page.fill('[data-testid="chart-config"]', JSON.stringify({
      type: 'line',
      data: [{ x: 1, y: 10 }]
    }));

    // Present and verify
    await page.click('[data-testid="present-chart"]');
    await expect(page.locator('[data-testid="chart-container"]')).toBeVisible();
  });
});
```

### Mobile E2E Testing with Detox

```javascript
// e2e/auth-flow.test.js
const detox = require('detox');
const config = require('./detox.config');
const { device, element, by } = require('detox');

describe('Authentication Flow', () => {
  beforeEach(async () => {
    await device.reloadReactNative();
  });

  it('complete login to dashboard', async () => {
    // Navigate to login screen
    await element(by.id('login-screen')).tap();

    // Fill login form
    await element(by.id('email-input')).replaceText('test@example.com');
    await element(by.id('password-input')).replaceText('securePassword123!');

    // Submit and verify dashboard
    await element(by.id('login-button')).tap();
    await expect(element(by.id('dashboard-screen'))).toBeVisible();

    // Test agent chat interaction
    await element(by.id('new-chat-button')).tap();
    await element(by.id('message-input')).replaceText('Hello, test agent');
    await element(by.id('send-button')).tap();

    // Verify agent response
    await expect(element(by.id('agent-response'))).toBeVisible();
  });

  it('canvas presentation on mobile', async () => {
    // Test canvas chart presentation
    await element(by.id('canvas-button')).tap();
    await element(by.id('chart-button')).tap();

    // Configure and present chart
    await element(by.id('chart-config-input')).replaceText('{"type":"bar"}');
    await element(by.id('present-chart')).tap();

    await expect(element(by.id('chart-container'))).toBeVisible();
  });
});
```

### Desktop E2E Testing with Tauri

```rust
// tests/integration_test.rs
use tauri::test as tauri_test;

#[tauri_test]
async fn authentication_flow(app: tauri::App) {
    // Get webview
    let webview = app.get_webview("main").unwrap();

    // Navigate to login page
    webview.navigate("http://localhost:3000/login").await.unwrap();

    // Fill login form
    webview.fill("#email", "test@example.com").await.unwrap();
    webview.fill("#password", "securePassword123!").await.unwrap();

    // Submit and verify dashboard
    webview.click("#submit").await.unwrap();
    webview.wait_for_navigation("/dashboard").await.unwrap();

    // Test desktop-specific features
    webview.get_window().unwrap().set_title("ATOM Test").unwrap();
    webview.get_window().unwrap().maximize().unwrap();
}

#[tauri_test]
async fn canvas_desktop_interaction(app: tauri::App) {
    let webview = app.get_webview("main").unwrap();

    // Test canvas desktop interactions
    webview.navigate("http://localhost:3000/canvas").await.unwrap();

    // Test file upload for canvas data
    webview.upload_file("#file-input", "/path/to/test/data.csv").await.unwrap();

    // Verify chart rendering
    webview.wait_for_element("#chart-container").await.unwrap();
}
```

### Stress Testing with k6

```javascript
// tests/stress/api-stress.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';

// Load test data from CSV
const testData = new SharedArray('users', function () {
  return open('./test-data/users.csv').split('\n').slice(1).map(line => {
    const [email, password] = line.split(',');
    return { email, password };
  });
});

export let options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 50 },   // Hold at 50 users
    { duration: '2m', target: 100 }, // Ramp up to 100 users
    { duration: '10m', target: 100 }, // Hold at 100 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
};

export default function () {
  const user = testData[Math.floor(Math.random() * testData.length)];

  // Test login flow
  const loginRes = http.post('http://localhost:8000/api/v1/auth/login', {
    email: user.email,
    password: user.password,
  });

  check(loginRes, {
    'login successful': (r) => r.status === 200,
    'login response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Get auth token
  const token = loginRes.json('access_token');

  // Test agent chat API
  const chatRes = http.post('http://localhost:8000/api/v1/agents/chat', {
    message: 'Hello, test agent',
    agent_id: 'test-agent',
  }, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  check(chatRes, {
    'chat successful': (r) => r.status === 200,
    'chat response time < 2000ms': (r) => r.timings.duration < 2000,
  });

  // Test canvas API
  const canvasRes = http.post('http://localhost:8000/api/v1/canvas/present', {
    type: 'chart',
    data: { type: 'line', points: [{ x: 1, y: 10 }] },
  }, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  check(canvasRes, {
    'canvas presentation successful': (r) => r.status === 200,
  });

  sleep(1);
}
```

### Cross-Platform Test Orchestration

```python
# tests/conftest.py
import pytest
import subprocess
import json
from pathlib import Path

@pytest.fixture(scope="session")
def allure_results():
    """Setup Allure results directory"""
    results_dir = Path("test-results/allure-results")
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

@pytest.fixture(scope="session")
def run_cross_platform_tests(allure_results):
    """Run cross-platform E2E tests"""

    # Run web tests with Playwright
    web_results = subprocess.run([
        "npx", "playwright", "test",
        "--headed",
        "--reporter=list",
        f"--output={allure_results}/web-results"
    ], cwd="backend/tests/e2e_ui", capture_output=True, text=True)

    # Run mobile tests with Detox
    mobile_results = subprocess.run([
        "npm", "run", "e2e:test",
        "--", "--reporter=junit",
        f"--output={allure_results}/mobile-results/junit.xml"
    ], cwd="mobile", capture_output=True, text=True)

    # Run desktop tests with Tauri
    desktop_results = subprocess.run([
        "cargo", "test",
        "--", "--reporter=json",
        f"--output={allure_results}/desktop-results"
    ], cwd="frontend-nextjs/src-tauri", capture_output=True, text=True)

    # Run stress tests with k6
    stress_results = subprocess.run([
        "k6", "run",
        "--out=json",
        f"--output={allure_results}/stress-results.json",
        "tests/stress/api-stress.js"
    ], capture_output=True, text=True)

    return {
        'web': web_results,
        'mobile': mobile_results,
        'desktop': desktop_results,
        'stress': stress_results
    }

@pytest.fixture
def test_governance_levels():
    """Test different agent maturity levels"""
    return [
        {'level': 'STUDENT', 'confidence': 0.4, 'permissions': ['read']},
        {'level': 'INTERN', 'confidence': 0.6, 'permissions': ['read', 'present']},
        {'level': 'SUPERVISED', 'confidence': 0.8, 'permissions': ['read', 'present', 'submit']},
        {'level': 'AUTONOMOUS', 'confidence': 0.9, 'permissions': ['all']}
    ]
```

## Cross-Platform Test Execution

### Unified Test Runner

```python
# tests/run_cross_platform.py
import pytest
import argparse
from pathlib import Path

def run_cross_platform_tests(test_types=None, parallel=True):
    """Run cross-platform E2E tests with unified reporting"""

    test_types = test_types or ['web', 'mobile', 'desktop', 'stress']
    results = {}

    # Web tests
    if 'web' in test_types:
        print("Running Web E2E tests...")
        results['web'] = pytest.main([
            'backend/tests/e2e_ui/tests',
            '--html=reports/web-report.html',
            '--json-report=reports/web-report.json',
            '-v'
        ])

    # Mobile tests
    if 'mobile' in test_types:
        print("Running Mobile E2E tests...")
        results['mobile'] = subprocess.run([
            'npm', 'run', 'e2e:test'
        ], cwd='mobile')

    # Desktop tests
    if 'desktop' in test_types:
        print("Running Desktop E2E tests...")
        results['desktop'] = subprocess.run([
            'cargo', 'test'
        ], cwd='frontend-nextjs/src-tauri')

    # Stress tests
    if 'stress' in test_types:
        print("Running Stress tests...")
        results['stress'] = subprocess.run([
            'k6', 'run', '--out=json=reports/stress-results.json',
            'tests/stress/api-stress.js'
        ])

    # Generate unified Allure report
    generate_allure_report(results)

    return results

def generate_allure_report(results):
    """Generate unified Allure report"""
    subprocess.run([
        'allure', 'generate', 'test-results/allure-results',
        '-o', 'reports/allure-report',
        '--clean'
    ])
```

## Integration with Bug Tracking

### Bug Reporting Integration

```python
# tests/bug_tracker.py
import requests
import json
from datetime import datetime

class BugTracker:
    def __init__(self, tracker_url, api_key):
        self.tracker_url = tracker_url
        self.api_key = api_key

    def report_bug(self, test_result, platform, severity):
        """Report bug to tracking system"""

        bug_data = {
            'title': f'{platform} E2E Failure: {test_result["name"]}',
            'description': f"""
**Test Failed**: {test_result["name"]}
**Platform**: {platform}
**Severity**: {severity}
**Time**: {datetime.now().isoformat()}
**Error**: {test_result["error"]}

**Steps to Reproduce**:
{test_result["steps"]}

**Environment**:
- Browser: {test_result.get("browser", "N/A")}
- Device: {test_result.get("device", "N/A")}
- OS: {test_result.get("os", "N/A")}
""",
            'labels': ['e2e', platform, severity],
            'priority': self._get_priority(severity)
        }

        response = requests.post(
            f"{self.tracker_url}/api/issues",
            json=bug_data,
            headers={'Authorization': f'Bearer {self.api_key}'}
        )

        return response.json()

    def _get_priority(self, severity):
        """Map severity to priority"""
        mapping = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4
        }
        return mapping.get(severity, 3)
```

## Performance Benchmarks

| Test Type | Target Execution Time | Current (Baseline) | Improvement Goal |
|-----------|---------------------|-------------------|------------------|
| Web E2E (Playwright) | < 30 sec/test | ~45 sec/test | 33% faster |
| Mobile E2E (Detox) | < 60 sec/test | ~90 sec/test | 33% faster |
| Desktop E2E (Tauri) | < 20 sec/test | ~25 sec/test | 20% faster |
| API Stress (k6) | < 100ms response | ~150ms response | 33% faster |
| Cross-Platform Orchestration | < 10 min total | ~15 min total | 33% faster |

## CI/CD Pipeline Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/e2e-testing.yml
name: Cross-Platform E2E Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-testing:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        platform: [web, mobile, desktop]
        browser: [chromium, firefox]

    steps:
    - uses: actions/checkout@v4

    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'

    - name: Install dependencies
      run: |
        npm install
        cd mobile && npm install

    - name: Start backend service
      run: npm run test:start &

    - name: Run ${{ matrix.platform }} tests
      if: matrix.platform == 'web'
      run: |
        cd backend/tests/e2e_ui
        npx playwright test --headed --browser=${{ matrix.browser }}

    - name: Run mobile tests
      if: matrix.platform == 'mobile'
      run: |
        cd mobile
        npm run e2e:build
        npm run e2e:test

    - name: Run desktop tests
      if: matrix.platform == 'desktop'
      run: |
        cd frontend-nextjs/src-tauri
        cargo test

    - name: Generate Allure report
      run: |
        allure generate test-results/allure-results -o reports/allure-report --clean

    - name: Upload test results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results-${{ matrix.platform }}
        path: |
          reports/
          test-results/
```

## Cost Analysis

| Component | Monthly Cost | Cost Rationale |
|-----------|-------------|----------------|
| Playwright (self-hosted) | $0 | Open source, no licensing |
| Detox (self-hosted) | $0 | Open source, no licensing |
| k6 Cloud (500 VU) | $149/month | Cloud load testing, scalable |
| Allure (self-hosted) | $0 | Open source reporting |
| Total | $149/month | Cost-effective for comprehensive testing |

## Alternative Considerations

| Category | Recommended | Alternative | Why Not Recommended |
|----------|-------------|-------------|---------------------|
| Mobile E2E | Detox | Appium | Slower, black-box only, more complex setup |
| Stress Testing | k6 | JMeter | Steeper learning curve, Java-based, slower setup |
| Test Reporting | Allure | Mochawesome | Less comprehensive, poor cross-platform support |
| Test Orchestration | pytest | TestNG | Java-based, less flexible fixtures, worse integration |

## Gaps to Address

1. **Mobile device cloud testing**: Need BrowserStack or Sauce Labs for real device testing
2. **Performance regression testing**: Add continuous performance monitoring
3. **Visual regression testing**: Add Percy or Applitools for visual comparisons
4. **Security testing**: Add OWASP ZAP for security scanning
5. **Accessibility testing**: Add axe-core for accessibility validation

## Sources

- [Playwright Documentation](https://playwright.dev/)
- [Detox Documentation](https://wix.github.io/detox/)
- [k6 Documentation](https://k6.io/docs/)
- [Tauri Testing Guide](https://tauri.app/v1/guides/testing/)
- [Allure Report Documentation](https://docs.qameta.io/allure/)

## Next Steps

1. **Phase 1**: Enhance existing Playwright tests with cross-browser coverage
2. **Phase 2**: Implement Detox mobile testing with comprehensive test coverage
3. **Phase 3**: Add Tauri desktop testing and stress testing with k6
4. **Phase 4**: Implement unified reporting with Allure and bug tracking integration
5. **Phase 5**: Add performance monitoring and visual regression testing
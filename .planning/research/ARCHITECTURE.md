# Architecture Research

**Domain:** Cross-Platform E2E Testing & Bug Discovery
**Researched:** March 23, 2026
**Confidence:** HIGH

## Executive Summary

Atom's existing architecture (Python backend, Next.js frontend, React Native mobile, Tauri desktop) provides a solid foundation for comprehensive E2E testing across web, mobile, and desktop platforms. The platform already has Playwright configured for web E2E (v3.1 shipped with 61 phases), pytest backend tests, and Detox available for mobile. This research outlines the integration architecture for expanding E2E testing to 600+ tests with cross-platform orchestration, stress testing infrastructure, and automated bug discovery.

**Key Findings:**
- **Existing infrastructure**: Playwright (web), pytest (backend), Detox (mobile available), Tauri (desktop with Playwright compatibility)
- **Integration points**: FastAPI backend (auth, agents, workflows), SQLite/PostgreSQL (test data), GitHub Actions (CI/CD)
- **Critical components needed**: Test orchestration layer, shared test data management, stress testing infrastructure, bug discovery tools
- **Build order**: Foundation → Platform-specific expansion → Cross-platform orchestration → Stress testing → Bug discovery
- **Performance targets**: <30min total E2E suite execution, parallel testing across platforms, <5s test data setup/teardown

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD Layer (GitHub Actions)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Web E2E Job │  │Mobile E2E Job│  │Desktop E2E Job│  │Stress Test Job│   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │                  │
┌─────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                       Test Orchestration Layer                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Unified Test Runner (Playwright + Detox + Tauri Driver)            │    │
│  │  - Test scheduling & sharding                                       │    │
│  │  - Parallel execution coordination                                  │    │
│  │  - Result aggregation & reporting                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                       Test Data Management Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Fixtures    │  │ Factories   │  │ Seed Data   │  │ Cleanup     │       │
│  │ (pytest)    │  │(factory-boy)│  │ (JSON/SQL)  │  │ (auto)      │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │                  │
┌─────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                         Platform Test Layers                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐ │
│  │  Web E2E (Playwright)│  │Mobile E2E (Detox)    │  │Desktop (Tauri E2E) │ │
│  │  - Chromium          │  │  - iOS Simulator     │  │  - WebView testing │ │
│  │  - Firefox           │  │  - Android Emulator  │  │  - Native features │ │
│  │  - WebKit            │  │  - Device interactions│  │  - Window management││
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘ │
└─────────────┼──────────────────────────┼──────────────────────────┼───────────┘
              │                          │                          │
┌─────────────┴──────────────────────────┴──────────────────────────┴───────────┐
│                        Application Under Test                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Next.js Web  │  │React Native  │  │  Tauri       │  │FastAPI       │     │
│  │ (localhost:  │  │ Mobile App   │  │  Desktop     │  │ Backend      │     │
│  │  3000/3001)  │  │ (Expo)       │  │  App         │  │ (localhost:  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │                  │
┌─────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                       Stress Testing & Bug Discovery                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Load Gen     │  │ Network Sim  │  │ Failure      │  │ Bug          │     │
│  │ (k6/locust)  │  │ (Chaos net)  │  │ Injection    │  │ Reporting    │     │
│  │              │  │              │  │ (Gremlin)    │  │ (GitHub)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Unified Test Runner** | Orchestrates test execution across platforms, manages parallelization, aggregates results | Custom Node.js CLI or Python orchestrator calling platform-specific test runners |
| **Test Data Manager** | Creates, seeds, and cleans test data; manages fixtures and factories | pytest fixtures + factory-boy + custom seed data management |
| **Web E2E Runner** | Executes browser-based tests using Playwright with multi-browser support | `@playwright/test` with config for Chromium/Firefox/WebKit |
| **Mobile E2E Runner** | Executes React Native tests using Detox with iOS/Android simulators | Detox framework with Expo integration |
| **Desktop E2E Runner** | Executes Tauri desktop tests using Playwright WebDriver protocol | Playwright with Tauri driver or CDP connection |
| **Stress Test Runner** | Generates load, simulates concurrent users, injects failures | k6 or Locust for load generation, Chaos tools for failure injection |
| **Bug Discovery Engine** | Analyzes test failures, generates reproducible test cases, documents bugs | Custom analysis + GitHub Issues integration |
| **CI/CD Coordinator** | Triggers E2E tests in GitHub Actions, manages test matrix, reports results | GitHub Actions workflows with matrix strategy |

## Recommended Project Structure

```
atom/
├── backend/
│   ├── tests/
│   │   ├── e2e/                          # Existing backend E2E tests
│   │   ├── fixtures/                     # Shared test fixtures
│   │   │   ├── conftest.py              # Root fixtures (50+ existing)
│   │   │   ├── factories.py             # factory-boy factories
│   │   │   └── seed_data/               # JSON seed data
│   │   └── stress/                       # Stress testing scripts
│   │       ├── load_test_k6.js          # k6 load test scripts
│   │       └── chaos_test.py            # Chaos engineering tests
│   └── core/
│       └── test_data_manager.py         # Test data CRUD orchestration
├── frontend-nextjs/
│   ├── tests/
│   │   ├── e2e/                         # Web E2E tests (Playwright)
│   │   │   ├── auth/                    # Authentication flows
│   │   │   ├── agents/                  # Agent interaction flows
│   │   │   ├── workflows/               # Workflow execution flows
│   │   │   └── canvas/                  # Canvas presentation flows
│   │   ├── fixtures/                    # Test fixtures (MSW, data)
│   │   │   ├── msw-handlers.ts          # API mocks
│   │   │   └── test-data.ts             # Shared test data
│   │   └── utils/                       # Test utilities
│   │       ├── test-helpers.ts          # Custom test helpers
│   │       └── selectors.ts             # Reusable selectors
│   └── playwright.config.ts             # Playwright configuration
├── mobile/
│   ├── e2e/                             # Mobile E2E tests (Detox)
│   │   ├── auth/
│   │   ├── agents/
│   │   ├── workflows/
│   │   └── device-features/             # Camera, location, notifications
│   ├── configs/
│   │   └── detox.config.js              # Detox configuration
│   └── tests/
│       └── fixtures/                    # Mobile-specific fixtures
├── desktop-e2e/                         # NEW: Desktop E2E tests
│   ├── tests/
│   │   ├── window-management/           # Window controls, resizing
│   │   ├── native-features/             # File system, system tray
│   │   └── cross-platform/              # Platform-specific tests (Win/Mac/Linux)
│   ├── fixtures/                        # Desktop test fixtures
│   └── playwright-tauri.config.ts       # Tauri-specific Playwright config
├── test-orchestrator/                   # NEW: Unified test orchestration
│   ├── src/
│   │   ├── orchestrator.ts              # Main orchestration logic
│   │   ├── runners/
│   │   │   ├── web-runner.ts            # Playwright runner wrapper
│   │   │   ├── mobile-runner.ts         # Detox runner wrapper
│   │   │   └── desktop-runner.ts        # Tauri runner wrapper
│   │   ├── data-manager.ts              # Cross-platform test data management
│   │   ├── reporters/
│   │   │   ├── unified-reporter.ts      # Aggregate test results
│   │   │   └── bug-reporter.ts          # GitHub Issues integration
│   │   └── stress-tester.ts             # Stress test orchestration
│   └── package.json
└── .github/
    └── workflows/
        ├── e2e-web.yml                  # Web E2E workflow
        ├── e2e-mobile.yml               # Mobile E2E workflow
        ├── e2e-desktop.yml              # Desktop E2E workflow
        ├── e2e-all.yml                  # Full cross-platform E2E
        └── stress-test.yml              # Stress testing workflow
```

### Structure Rationale

- **`backend/tests/`**: Extends existing pytest infrastructure with E2E, fixtures, stress tests
- **`frontend-nextjs/tests/e2e/`**: Web E2E tests using existing Playwright setup (port 3000/3001)
- **`mobile/e2e/`**: Mobile E2E tests using Detox (already in package.json)
- **`desktop-e2e/`**: NEW - Desktop-specific tests for Tauri (window management, native features)
- **`test-orchestrator/`**: NEW - Unified test runner for cross-platform coordination
- **`.github/workflows/`**: CI/CD workflows for each platform + full cross-platform runs

## Architectural Patterns

### Pattern 1: Test Orchestration with Unified Runner

**What:** Central orchestration service that coordinates test execution across web, mobile, and desktop platforms, managing parallelization, test data setup, and result aggregation.

**When to use:**
- Running E2E tests across multiple platforms
- Coordinating test data setup/teardown across platforms
- Aggregating test results from multiple test runners

**Trade-offs:**
- **Pros**: Single entry point, centralized configuration, shared test data, unified reporting
- **Cons**: Additional complexity, orchestration layer to maintain, single point of failure

**Example:**
```typescript
// test-orchestrator/src/orchestrator.ts
import { WebRunner } from './runners/web-runner';
import { MobileRunner } from './runners/mobile-runner';
import { DesktopRunner } from './runners/desktop-runner';
import { TestDataManager } from './data-manager';

interface TestSuite {
  platform: 'web' | 'mobile' | 'desktop';
  tests: string[];
  parallel?: boolean;
}

export class TestOrchestrator {
  private webRunner = new WebRunner();
  private mobileRunner = new MobileRunner();
  private desktopRunner = new DesktopRunner();
  private dataManager = new TestDataManager();

  async runE2ESuites(suites: TestSuite[]) {
    // Setup shared test data
    await this.dataManager.setup();

    const results = await Promise.allSettled(
      suites.map(suite => this.runSuite(suite))
    );

    // Cleanup test data
    await this.dataManager.cleanup();

    return this.aggregateResults(results);
  }

  private async runSuite(suite: TestSuite) {
    const runner = this.getRunner(suite.platform);
    return runner.run(suite.tests, { parallel: suite.parallel });
  }

  private getRunner(platform: string) {
    switch (platform) {
      case 'web': return this.webRunner;
      case 'mobile': return this.mobileRunner;
      case 'desktop': return this.desktopRunner;
      default: throw new Error(`Unknown platform: ${platform}`);
    }
  }

  private aggregateResults(results: PromiseSettledResult<void>[]) {
    // Aggregate results from all platforms
    const passed = results.filter(r => r.status === 'fulfilled').length;
    const failed = results.filter(r => r.status === 'rejected').length;
    return { total: results.length, passed, failed };
  }
}
```

---

### Pattern 2: Shared Test Data Management

**What:** Centralized test data management using fixtures, factories, and seed data that can be used across all E2E test platforms.

**When to use:**
- Multiple test platforms need consistent test data
- Complex test data relationships (agents, workflows, episodes)
- Reproducible test data across test runs

**Trade-offs:**
- **Pros**: Consistent data, reduced duplication, easier maintenance
- **Cons**: Initial setup complexity, shared data can cause test interference

**Example:**
```python
# backend/tests/fixtures/test_data_manager.py
from sqlalchemy.orm import Session
from core.models import AgentRegistry, AgentExecution, Episode
import factory
from faker import Faker

fake = Faker()

class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session_persistence = 'commit'

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.LazyFunction(lambda: fake.company() + " Agent")
    category = factory.Iterator(['testing', 'automation', 'analysis'])
    confidence_score = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    maturity_level = factory.Iterator(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])

class TestDataManager:
    """Centralized test data management for E2E tests"""

    def __init__(self, db: Session):
        self.db = db
        self.created_data = []

    def setup_test_scenario(self, scenario: str):
        """Setup predefined test scenarios"""
        if scenario == 'single_agent':
            return self._setup_single_agent()
        elif scenario == 'multi_agent_workflow':
            return self._setup_multi_agent_workflow()
        elif scenario == 'episode_memory':
            return self._setup_episode_memory()

    def _setup_single_agent(self):
        """Create a single test agent"""
        agent = AgentFactory.create(
            name="Test Agent",
            maturity_level="INTERN",
            confidence_score=0.75
        )
        self.created_data.append(('agent', agent.id))
        return agent

    def _setup_multi_agent_workflow(self):
        """Create multiple agents for workflow testing"""
        agents = [
            AgentFactory.create(
                name=f"Agent {i}",
                maturity_level=['STUDENT', 'INTERN', 'SUPERVISED'][i % 3]
            )
            for i in range(3)
        ]
        for agent in agents:
            self.created_data.append(('agent', agent.id))
        return agents

    def cleanup(self):
        """Cleanup all created test data"""
        for entity_type, entity_id in reversed(self.created_data):
            if entity_type == 'agent':
                self.db.query(AgentRegistry).filter(
                    AgentRegistry.id == entity_id
                ).delete()
        self.db.commit()
        self.created_data.clear()
```

**Usage in E2E Tests:**
```typescript
// frontend-nextjs/tests/e2e/agents/agent-execution.spec.ts
import { test, expect } from '@playwright/test';
import { setupTestData, cleanupTestData } from '../../fixtures/test-data';

test.describe('Agent Execution E2E', () => {
  let testData: any;

  test.beforeAll(async () => {
    // Setup test data via backend API
    testData = await setupTestData('single_agent');
  });

  test.afterAll(async () => {
    // Cleanup test data
    await cleanupTestData(testData);
  });

  test('executes agent and displays results', async ({ page }) => {
    await page.goto(`/agents/${testData.agent.id}`);
    await page.click('[data-testid="execute-agent"]');
    await expect(page.locator('[data-testid="execution-status"]')).toHaveText('completed');
  });
});
```

---

### Pattern 3: Cross-Platform Test Reuse

**What:** Share test logic across platforms using abstraction layers, with platform-specific implementations for UI interactions.

**When to use:**
- Same user flow exists across web, mobile, and desktop
- Test logic should be consistent, but UI interactions differ
- Reducing test duplication across platforms

**Trade-offs:**
- **Pros**: Reduced duplication, consistent test coverage, easier maintenance
- **Cons**: Abstraction complexity, platform-specific quirks harder to test

**Example:**
```typescript
// test-orchestrator/src/shared/authentication.flow.ts
export interface AuthenticationPage {
  navigateToLogin(): Promise<void>;
  enterEmail(email: string): Promise<void>;
  enterPassword(password: string): Promise<void>;
  submit(): Promise<void>;
  waitForDashboard(): Promise<void>;
}

export class AuthenticationFlow {
  constructor(private page: AuthenticationPage) {}

  async login(email: string, password: string) {
    await this.page.navigateToLogin();
    await this.page.enterEmail(email);
    await this.page.enterPassword(password);
    await this.page.submit();
    await this.page.waitForDashboard();
  }

  async loginWithInvalidCredentials(email: string, password: string) {
    await this.page.navigateToLogin();
    await this.page.enterEmail(email);
    await this.page.enterPassword(password);
    await this.page.submit();
    // Platform-specific error assertion
  }
}

// Web implementation
export class WebAuthPage implements AuthenticationPage {
  constructor(private page: Page) {}

  async navigateToLogin() {
    await this.page.goto('/login');
  }

  async enterEmail(email: string) {
    await this.page.fill('[data-testid="email-input"]', email);
  }

  async enterPassword(password: string) {
    await this.page.fill('[data-testid="password-input"]', password);
  }

  async submit() {
    await this.page.click('[data-testid="login-button"]');
  }

  async waitForDashboard() {
    await this.page.waitForURL('/dashboard');
  }
}

// Mobile implementation
export class MobileAuthPage implements AuthenticationPage {
  constructor(private device: DetoxDevice) {}

  async navigateToLogin() {
    await element(by.id('login-screen')).waitFor();
  }

  async enterEmail(email: string) {
    await element(by.id('email-input')).typeText(email);
  }

  async enterPassword(password: string) {
    await element(by.id('password-input')).typeText(password);
  }

  async submit() {
    await element(by.id('login-button')).tap();
  }

  async waitForDashboard() {
    await element(by.id('dashboard-screen')).waitFor();
  }
}

// Usage in tests
const authFlow = new AuthenticationFlow(new WebAuthPage(page));
await authFlow.login('test@example.com', 'password');
```

---

### Pattern 4: Stress Testing with Load Generation

**What:** Generate concurrent load and failure scenarios to test system resilience, bug discovery, and performance degradation.

**When to use:**
- Testing system behavior under high load
- Discovering race conditions and concurrency bugs
- Validating performance degradation patterns

**Trade-offs:**
- **Pros**: Finds production bugs, validates scalability, tests resilience
- **Cons**: Complex setup, can be flaky, requires test environment isolation

**Example (k6):**
```javascript
// backend/tests/stress/load_test_k6.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 10 },   // Stay at 10 users
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp down to 0
  ],
  thresholds: {
    'errors': ['rate<0.1'],           // Error rate < 10%
    'http_req_duration': ['p(95)<500'], // 95% of requests < 500ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Test agent execution endpoint
  const agentExec = http.post(
    `${BASE_URL}/api/v1/agents/test-agent/execute`,
    JSON.stringify({ prompt: 'Test prompt' }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'AgentExecution' },
    }
  );

  check(agentExec, {
    'agent execution status is 200': (r) => r.status === 200,
    'response has agent_id': (r) => r.json('agent_id') !== undefined,
  }) || errorRate.add(1);

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data),
    'load-test-report.json': JSON.stringify(data),
  };
}
```

---

### Pattern 5: Bug Discovery with Failure Analysis

**What:** Automated analysis of test failures to generate reproducible bug reports with screenshots, logs, and GitHub Issues integration.

**When to use:**
- E2E test failures need detailed context
- Automated bug filing for reproducible failures
- Tracking test flakiness patterns

**Trade-offs:**
- **Pros**: Faster bug triage, automated documentation, reproducible test cases
- **Cons**: GitHub API complexity, false positives, noise in issue tracker

**Example:**
```typescript
// test-orchestrator/src/reporters/bug-reporter.ts
import { Octokit } from 'octokit';

interface TestFailure {
  test: string;
  platform: string;
  error: string;
  screenshot: string;
  logs: string;
  reproducible: boolean;
}

export class BugReporter {
  private octokit: Octokit;

  constructor() {
    this.octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
  }

  async reportFailure(failure: TestFailure) {
    // Check if issue already exists
    const existingIssue = await this.findExistingIssue(failure);

    if (existingIssue) {
      // Add comment to existing issue
      await this.addFailureComment(existingIssue.number, failure);
      return existingIssue.number;
    }

    // Create new issue
    const issue = await this.octokit.rest.issues.create({
      owner: 'atom',
      repo: 'atom-platform',
      title: this.generateIssueTitle(failure),
      body: this.generateIssueBody(failure),
      labels: this.generateLabels(failure),
    });

    return issue.data.number;
  }

  private async findExistingIssue(failure: TestFailure) {
    const query = `is:issue is:open "${failure.test}" in:title`;
    const result = await this.octokit.rest.search.issuesAndPullRequests({
      q: query,
      repo: 'atom/atom-platform',
    });

    if (result.data.items.length > 0) {
      return result.data.items[0];
    }
    return null;
  }

  private generateIssueTitle(failure: TestFailure): string {
    return `[E2E Failure] ${failure.platform}: ${failure.test}`;
  }

  private generateIssueBody(failure: TestFailure): string {
    return `
## E2E Test Failure

**Platform:** ${failure.platform}
**Test:** ${failure.test}
**Reproducible:** ${failure.reproducible ? 'Yes' : 'No'}

### Error
\`\`\`
${failure.error}
\`\`\`

### Screenshot
![Failure Screenshot](${failure.screenshot})

### Logs
\`\`\`
${failure.logs}
\`\`\`

### Reproduction Steps
1. Run test: \`npm run test:e2e -- ${failure.test}\`
2. Observe failure
3. Check logs and screenshot above

### Automated Analysis
This issue was automatically created by E2E test infrastructure.
${failure.reproducible ? 'This failure has been reproduced multiple times.' : ''}
    `.trim();
  }

  private generateLabels(failure: TestFailure): string[] {
    const labels = ['e2e-failure', failure.platform];
    if (failure.reproducible) labels.push('reproducible');
    if (failure.error.includes('timeout')) labels.push('timeout');
    if (failure.error.includes('assertion')) labels.push('assertion-failure');
    return labels;
  }

  private async addFailureComment(issueNumber: number, failure: TestFailure) {
    await this.octokit.rest.issues.createComment({
      owner: 'atom',
      repo: 'atom-platform',
      issue_number: issueNumber,
      body: `
### New Failure Occurred
**Date:** ${new Date().toISOString()}
**Error:** ${failure.error}
${failure.reproducible ? 'This is a recurring failure.' : ''}
      `.trim(),
    });
  }
}
```

## Data Flow

### E2E Test Execution Flow

```
[Developer Push/PR Trigger]
    ↓
[GitHub Actions Workflow Starts]
    ↓
[Test Orchestrator Setup]
    ↓
[Test Data Manager] → Create seed data (agents, workflows, episodes)
    ↓
[Platform Test Runners] (Execute in parallel)
    ├── [Web Runner] → Playwright tests → Chromium/Firefox/WebKit
    ├── [Mobile Runner] → Detox tests → iOS/Android simulators
    └── [Desktop Runner] → Tauri tests → Windows/macOS/Linux
    ↓
[Collect Results]
    ├── Screenshots (on failure)
    ├── Videos (on failure)
    ├── Trace files (Playwright)
    └── Logs (platform-specific)
    ↓
[Unified Reporter] → Aggregate results → HTML report + JSON + JUnit
    ↓
[Bug Discovery] → Analyze failures → Create GitHub Issues (if reproducible)
    ↓
[Test Data Cleanup] → Delete seed data, rollback transactions
    ↓
[CI/CD Result] → Pass/Fail status → Comment on PR
```

### Stress Testing Flow

```
[Stress Test Trigger] (Manual or Scheduled)
    ↓
[Load Generator Setup] (k6/Locust)
    ↓
[Concurrent User Simulation]
    ├── 10 users → 2 min
    ├── 50 users → 5 min
    └── 100 users → 5 min
    ↓
[Metrics Collection]
    ├── Request latency (p50, p95, p99)
    ├── Error rate (by endpoint)
    ├── Database connection pool
    └── Memory/CPU usage
    ↓
[Failure Injection] (Optional - Chaos Engineering)
    ├── Network delays
    ├── Database connection drops
    └── Service crashes
    ↓
[Bug Discovery] → Analyze failures → Document race conditions
    ↓
[Stress Test Report] → Performance baselines → Alerts on degradation
```

### Test Data Management Flow

```
[Test Starts]
    ↓
[Test Data Manager Setup]
    ├── Create isolated database (SQLite in-memory or PostgreSQL schema)
    ├── Run migrations (alembic upgrade head)
    └── Load seed data (JSON fixtures)
    ↓
[Test Execution]
    ├── Read seed data (agents, workflows, episodes)
    ├── Execute test actions
    └── Assert results
    ↓
[Test Data Cleanup]
    ├── Rollback transactions
    ├── Drop test database/schema
    └── Verify no data leakage
```

### Key Data Flows

1. **Authentication Flow**: Test creates user → JWT token generated → Token stored → Platform tests use token → Token invalidated
2. **Agent Execution Flow**: Test creates agent → Agent stored in DB → Test triggers execution → Execution tracked → Result validated → Execution record cleaned up
3. **Episode Memory Flow**: Test creates episode → Episode segmented → Memory stored → Test retrieves episode → Validated → Episode archived
4. **Cross-Platform Flow**: Shared test data → Web test creates resource → Mobile test accesses resource → Desktop test updates resource → All tests pass → Resource cleaned up

## Integration Points

### Existing Atom Architecture Integration

| Atom Component | Integration Pattern | Notes |
|----------------|---------------------|-------|
| **Backend API** (FastAPI) | HTTP endpoints for test data setup, agent operations, workflow execution | Use existing API or add test-specific endpoints (e.g., `/api/v1/test/*`) |
| **Authentication** (JWT) | Test authentication flow: create test user → generate JWT → use in E2E tests | Add test user creation endpoint or use existing auth with test credentials |
| **Database** (SQLite/PostgreSQL) | Test data isolation: separate DB per test run or transaction rollback | Use pytest fixtures for auto-setup/teardown |
| **Agent System** | Test agent creation, execution, state management via API | AgentFactory for test data, API calls for execution |
| **Workflows** | Test workflow creation, execution, state transitions | Seed data for common workflows |
| **Episodic Memory** | Test episode creation, segmentation, retrieval | Validate episode lifecycle in E2E tests |
| **WebSocket/Streaming** | Test real-time agent communication, LLM streaming | Use WebSocket client in E2E tests |
| **Canvas Presentations** | Test canvas rendering, interactivity, state management | Platform-specific canvas assertions (web/mobile/desktop) |
| **CI/CD** (GitHub Actions) | Trigger E2E tests on push/PR, report results, comment on PR | Matrix strategy for parallel execution |

### New Components Integration

| New Component | Integration with Existing | Notes |
|---------------|--------------------------|-------|
| **Test Orchestrator** | Calls existing Playwright/Detox/pytest runners | Wrapper around existing tools, adds coordination |
| **Test Data Manager** | Uses existing backend API, database models | Extends existing fixtures/factories |
| **Unified Reporter** | Aggregates existing test reports (HTML, JSON, JUnit) | Post-processes existing outputs |
| **Bug Reporter** | Integrates with GitHub (already used for issues) | Octokit API for issue creation |
| **Stress Test Runner** | Uses existing backend API for load generation | k6/Locust scripts targeting backend endpoints |
| **Desktop E2E Tests** | Uses Playwright (already configured for web) | Extend Playwright to Tauri via CDP or WebDriver |
| **Mobile E2E Tests** | Uses Detox (already in package.json) | Configure Detox for React Native/Expo |

### External Service Integration

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **GitHub Actions** | CI/CD workflows with matrix strategy for parallel execution | Use existing workflows, add E2E jobs |
| **GitHub Issues API** | Automated bug filing for reproducible failures | Octokit for API access |
| **Playwright** | Web E2E tests (Chromium, Firefox, WebKit) | Already configured, extend to 600+ tests |
| **Detox** | Mobile E2E tests (iOS, Android) | Already in package.json, needs configuration |
| **Tauri Driver** | Desktop E2E tests via Playwright CDP | Use Tauri's WebDriver protocol or CDP connection |
| **k6/Locust** | Load generation for stress testing | New tool, integrate with CI/CD |
| **Allure/Mochawesome** | Unified test reporting (optional, existing HTML reports may suffice) | Consider if existing reports insufficient |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-100 E2E tests** | Single GitHub Actions job, sequential execution, ~15-30min runtime |
| **100-300 E2E tests** | Matrix strategy with 2-3 parallel jobs, ~20-40min runtime |
| **300-600 E2E tests** | Full matrix strategy (web + mobile + desktop), sharding within platforms, ~30-60min runtime |
| **600+ E2E tests** | Test result caching, selective test execution (affected tests only), distributed testing across multiple runners |

### Scaling Priorities

1. **First bottleneck: Test data setup/teardown**
   - **Problem**: Creating test data (agents, workflows, episodes) is slow
   - **Fix**: Use database transactions for rollback, pre-seed common data, parallel data creation

2. **Second bottleneck: Browser/simulator startup time**
   - **Problem**: Chromium, iOS Simulator, Android Emulator slow to start
   - **Fix**: Reuse existing servers (Playwright `reuseExistingServer`), pool of warm simulators

3. **Third bottleneck: Test execution time**
   - **Problem**: Too many tests, slow assertions
   - **Fix**: Sharding, parallel execution, reduce test count (only critical paths), optimize selectors

## Anti-Patterns

### Anti-Pattern 1: Testing Implementation Details

**What people do:** Testing CSS classes, DOM structure, component internals instead of user-facing behavior.

**Why it's wrong:** Tests break on refactoring, don't validate actual user experience, brittle selectors.

**Do this instead:**
- Use semantic selectors (`getByRole`, `getByLabelText`, `getByTestId` for E2E)
- Test user-visible behavior (what user sees and does)
- Example:
```typescript
// BAD - Testing implementation
await expect(page.locator('div.AgentList > ul > li:first-child')).toHaveText('Agent 1');

// GOOD - Testing user behavior
await expect(page.getByRole('listitem').filter({ hasText: 'Agent 1' })).toBeVisible();
```

---

### Anti-Pattern 2: Shared State Between Tests

**What people do:** Tests share database state, global variables, or test data without proper isolation.

**Why it's wrong:** Non-deterministic failures, tests interfere with each other, flaky tests.

**Do this instead:**
- Isolate test data per test (transactions, separate DB)
- Cleanup after each test (`afterEach` hooks)
- Use unique identifiers (UUIDs, timestamps)
- Example:
```typescript
// BAD - Shared state
let agentId: string;

test.beforeAll(async () => {
  agentId = await createAgent(); // Shared across all tests
});

test('updates agent', async () => {
  await updateAgent(agentId, { name: 'Updated' });
});

test('deletes agent', async () => {
  await deleteAgent(agentId); // Breaks other tests!
});

// GOOD - Isolated state
test('updates agent', async () => {
  const agentId = await createAgent(); // Unique to this test
  await updateAgent(agentId, { name: 'Updated' });
  await cleanupAgent(agentId);
});

test('deletes agent', async () => {
  const agentId = await createAgent(); // Different agent
  await deleteAgent(agentId);
});
```

---

### Anti-Pattern 3: Over-Mocking in E2E Tests

**What people do:** Mocking backend responses, database calls, or external services in E2E tests.

**Why it's wrong:** E2E tests should validate integration, mocking defeats the purpose, false confidence.

**Do this instead:**
- Use real backend (staging or test environment)
- Use real database (test DB with rollback)
- Only mock external services you don't control (payment APIs, third-party services)
- Example:
```typescript
// BAD - Over-mocking in E2E
test('executes agent', async ({ page }) => {
  await page.route('**/api/v1/agents/*/execute', route => {
    route.fulfill({
      status: 200,
      body: JSON.stringify({ result: 'Mocked result' })
    });
  });

  await page.click('[data-testid="execute-agent"]');
  // Test passes but doesn't validate real backend!
});

// GOOD - Real backend in E2E
test('executes agent', async ({ page }) => {
  await page.click('[data-testid="execute-agent"]');
  await expect(page.locator('[data-testid="execution-result"]'))
    .toHaveText('Agent executed successfully');
  // Validates real backend integration
});
```

---

### Anti-Pattern 4: Flaky Async Tests

**What people do:** Not waiting for async operations, race conditions, timing-based assertions.

**Why it's wrong:** Non-deterministic failures, tests fail intermittently, loss of trust in test suite.

**Do this instead:**
- Use explicit waits (`waitFor`, `waitForSelector`, `waitForResponse`)
- Avoid `setTimeout` (use polling or events)
- Wait for user-visible state (not loading spinners)
- Example:
```typescript
// BAD - Timing-based
test('executes agent', async ({ page }) => {
  await page.click('[data-testid="execute-agent"]');
  await page.waitForTimeout(5000); // Flaky!
  await expect(page.locator('[data-testid="result"]')).toBeVisible();
});

// GOOD - Explicit wait
test('executes agent', async ({ page }) => {
  await page.click('[data-testid="execute-agent"]');
  await page.waitForSelector('[data-testid="result"]', { state: 'visible' });
  await expect(page.locator('[data-testid="result"]')).toBeVisible();
});
```

---

### Anti-Pattern 5: Testing Third-Party Libraries

**What people do:** Testing React, Next.js, Chakra UI, or other third-party libraries.

**Why it's wrong:** Library authors already test their code, you're testing what you don't control, wasted effort.

**Do this instead:**
- Test your code only (components, hooks, utilities, API integration)
- Trust library authors to test their code
- Focus integration testing on your usage of libraries
- Example:
```typescript
// BAD - Testing React
test('React renders component', async ({ page }) => {
  render(<Button>Click</Button>);
  expect(Button).toBeInTheDocument(); // Tests React, not your code!
});

// GOOD - Testing your component
test('Button component triggers onClick', async ({ page }) => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click</Button>);
  await page.click('button');
  expect(handleClick).toHaveBeenCalled(); // Tests your code
});
```

---

### Anti-Pattern 6: E2E Tests for Everything

**What people do:** Writing E2E tests for every feature, every component, every edge case.

**Why it's wrong:** Slow feedback loop, expensive to maintain, brittle, CI/CD takes too long.

**Do this instead:**
- Testing pyramid: 70% unit, 20% integration, 10% E2E
- E2E tests for critical user flows only (login, agent execution, workflow creation)
- Component/integration tests for everything else
- Example:
```typescript
// BAD - E2E test for component validation
test('email input shows validation error', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[data-testid="email"]', 'invalid-email');
  await page.click('[data-testid="submit"]');
  await expect(page.locator('[data-testid="email-error"]'))
    .toHaveText('Invalid email');
  // Slow E2E test for simple validation!
});

// GOOD - Component test for validation
test('email input shows validation error', () => {
  render(<LoginForm />);
  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'invalid-email' }
  });
  fireEvent.click(screen.getByText('Submit'));
  expect(screen.getByText('Invalid email')).toBeInTheDocument();
  // Fast component test!
});
```

## Platform-Specific Considerations

### Web E2E (Playwright)

**Configuration:**
- **Browsers**: Chromium (default), Firefox (deferred), WebKit/Safari (deferred)
- **Base URLs**: `localhost:3000` (dev), `localhost:3001` (testing)
- **Timeouts**: 60s test timeout, 30s action timeout
- **Retries**: 0 (local), 2 (CI)

**Integration Points:**
- Next.js frontend (port 3000/3001)
- FastAPI backend (port 8000)
- WebSocket for real-time features
- MSW for API mocking (in integration tests, not E2E)

**Test Organization:**
```
frontend-nextjs/tests/e2e/
├── auth/                          # Authentication flows
│   ├── login.spec.ts
│   ├── logout.spec.ts
│   └── session-management.spec.ts
├── agents/                        # Agent interaction flows
│   ├── agent-list.spec.ts
│   ├── agent-execution.spec.ts
│   └── agent-chat.spec.ts
├── workflows/                     # Workflow execution flows
│   ├── workflow-creation.spec.ts
│   ├── workflow-execution.spec.ts
│   └── workflow-automation.spec.ts
├── canvas/                        # Canvas presentation flows
│   ├── canvas-rendering.spec.ts
│   ├── canvas-interactivity.spec.ts
│   └── canvas-types.spec.ts       # Charts, forms, sheets, etc.
└── episodic-memory/               # Episode management flows
    ├── episode-creation.spec.ts
    ├── episode-retrieval.spec.ts
    └── episode-graduation.spec.ts
```

---

### Mobile E2E (Detox)

**Configuration:**
- **Platform**: React Native with Expo
- **Devices**: iOS Simulator, Android Emulator
- **Timeouts**: 30s action timeout, 120s launch timeout
- **Async**: Detox automatic synchronization (gray-box testing)

**Integration Points:**
- React Native mobile app
- Expo CLI for device management
- Backend API (same as web)
- Device features: Camera, Location, Notifications (device permissions)

**Test Organization:**
```
mobile/e2e/
├── auth/                          # Authentication flows
│   ├── login.e2e.js
│   ├── biometric-auth.e2e.js      # Face ID / Touch ID
│   └── session-management.e2e.js
├── agents/                        # Agent interaction flows
│   ├── agent-list.e2e.js
│   ├── agent-execution.e2e.js
│   └── agent-chat.e2e.js          # Mobile-specific chat UI
├── workflows/                     # Workflow execution flows
│   ├── workflow-creation.e2e.js   # Mobile workflow builder
│   └── workflow-execution.e2e.js
├── device-features/               # Device capability tests
│   ├── camera.e2e.js              # Camera integration
│   ├── location.e2e.js            # Location services
│   ├── notifications.e2e.js       # Push notifications
│   └── deep-links.e2e.js          # atom:// protocol handling
└── mobile-specific/               # Mobile-only features
    ├── gestures.e2e.js            # Swipe, pinch, long-press
    ├── orientation.e2e.js         # Portrait/landscape
    └── offline-mode.e2e.js        # Offline behavior
```

**Detox Configuration:**
```javascript
// mobile/configs/detox.config.js
module.exports = {
  testRunner: {
    args: {
      '$0': 'jest',
      config: 'e2e/jest.config.js'
    },
    jest: {
      setupTimeout: 120000
    }
  },
  apps: {
    'ios.debug': {
      type: 'ios.app',
      binaryPath: 'ios/build/Build/Products/Debug-iphonesimulator/atom.app',
      build: 'xcodebuild -workspace ios/atom.xcworkspace -scheme atom -configuration Debug -sdk iphonesimulator -derivedDataPath ios/build',
    },
    'android.debug': {
      type: 'android.apk',
      binaryPath: 'android/app/build/outputs/apk/debug/app-debug.apk',
      build: 'cd android && ./gradlew assembleDebug assembleAndroidTest -DtestBuildType=debug && cd ..',
    }
  },
  devices: {
    simulator: {
      type: 'ios.simulator',
      device: { type: 'iPhone 14' }
    },
    emulator: {
      type: 'android.emulator',
      device: { avdName: 'Pixel_5_API_31' }
    }
  },
  configurations: {
    'ios.sim.debug': {
      device: 'simulator',
      app: 'ios.debug'
    },
    'android.emu.debug': {
      device: 'emulator',
      app: 'android.debug'
    }
  }
};
```

---

### Desktop E2E (Tauri + Playwright)

**Configuration:**
- **Platform**: Tauri desktop app (Windows, macOS, Linux)
- **Testing**: Playwright with CDP connection or Tauri Driver
- **Timeouts**: 60s test timeout, 30s action timeout
- **Windows**: Window management, native dialogs, system tray

**Integration Points:**
- Tauri desktop app (WebView with Rust backend)
- Same frontend as web (Next.js in Tauri WebView)
- Native features: File system, system tray, window controls
- Backend API (same as web, via WebView)

**Test Organization:**
```
desktop-e2e/tests/
├── window-management/             # Desktop-specific window tests
│   ├── window-resize.spec.ts
│   ├── window-minimize.spec.ts
│   ├── window-maximize.spec.ts
│   └── window-controls.spec.ts    # Close, minimize, maximize buttons
├── native-features/               # Native OS integration
│   ├── file-system.spec.ts        # File dialogs, file access
│   ├── system-tray.spec.ts        # Tray icon, tray menu
│   ├── notifications.spec.ts      # OS notifications
│   └── deep-links.spec.ts         # atom:// protocol handling
├── cross-platform/                # Platform-specific behavior
│   ├── windows.spec.ts            # Windows-only features
│   ├── macos.spec.ts              # macOS-only features
│   └── linux.spec.ts              # Linux-only features
└── shared/                        # Tests shared with web
    ├── auth/                      # Same auth flows as web
    ├── agents/                    # Same agent flows as web
    └── workflows/                 # Same workflow flows as web
```

**Tauri Playwright Configuration:**
```typescript
// desktop-e2e/playwright-tauri.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker to avoid window conflicts

  use: {
    // Connect to running Tauri app via CDP
    baseURL: 'http://localhost:4300', // Tauri dev server URL
    headless: false, // Tauri requires visible window
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'tauri-windows',
      use: {
        // Windows-specific configuration
      },
    },
    {
      name: 'tauri-macos',
      use: {
        // macOS-specific configuration
      },
    },
    {
      name: 'tauri-linux',
      use: {
        // Linux-specific configuration
      },
    },
  ],
});
```

**Tauri Test Helper:**
```typescript
// desktop-e2e/tests/helpers/tauri-helper.ts
import { Page } from '@playwright/test';

export class TauriHelper {
  constructor(private page: Page) {}

  async invokeTauriCommand<T>(cmd: string, args?: any): Promise<T> {
    return await this.page.evaluate(async ([cmd, args]) => {
      // @ts-ignore - Tauri API injected in WebView
      return await window.__TAURI__.core.invoke(cmd, args);
    }, [cmd, args]);
  }

  async readFile(filePath: string): Promise<string> {
    return await this.invokeTauriCommand('read_file', { path: filePath });
  }

  async writeFile(filePath: string, content: string): Promise<void> {
    await this.invokeTauriCommand('write_file', { path: filePath, content });
  }

  async showNotification(title: string, body: string): Promise<void> {
    await this.invokeTauriCommand('show_notification', { title, body });
  }

  async getWindowState(): Promise<{ width: number; height: number; x: number; y: number }> {
    return await this.invokeTauriCommand('get_window_state');
  }

  async minimizeWindow(): Promise<void> {
    await this.invokeTauriCommand('minimize_window');
  }

  async maximizeWindow(): Promise<void> {
    await this.invokeTauriCommand('maximize_window');
  }

  async closeWindow(): Promise<void> {
    await this.invokeTauriCommand('close_window');
  }
}
```

## CI/CD Integration

### GitHub Actions Workflow Structure

```yaml
# .github/workflows/e2e-all.yml
name: E2E Tests (All Platforms)

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily 2 AM run

jobs:
  e2e-web:
    name: Web E2E Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        browser: [chromium, firefox, webkit]
        shard: [1/4, 2/4, 3/4, 4/4]  # Split tests into 4 shards
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
          npx playwright install --with-deps ${{ matrix.browser }}
      - name: Install backend dependencies
        run: |
          cd backend
          pip install -e .
      - name: Start backend
        run: |
          cd backend
          python -m uvicorn main:app &
          sleep 10
      - name: Run Playwright tests
        run: |
          cd frontend-nextjs
          npx playwright test --project=${{ matrix.browser }} --shard=${{ matrix.shard }}
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: web-e2e-results-${{ matrix.browser }}-${{ matrix.shard }}
          path: frontend-nextjs/playwright-report/
      - name: Upload screenshots
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: web-e2e-screenshots-${{ matrix.browser }}-${{ matrix.shard }}
          path: frontend-nextjs/test-results/

  e2e-mobile:
    name: Mobile E2E Tests
    runs-on: macos-latest  # macOS required for iOS simulator
    strategy:
      matrix:
        platform: [ios.sim.debug, android.emu.debug]
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Setup Expo
        run: npm install -g expo-cli
      - name: Install dependencies
        run: |
          cd mobile
          npm ci
      - name: Build mobile app
        run: |
          cd mobile
          detox build --configuration ${{ matrix.platform }}
      - name: Run Detox tests
        run: |
          cd mobile
          detox test --configuration ${{ matrix.platform }}
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: mobile-e2e-results-${{ matrix.platform }}
          path: mobile/e2e/results/

  e2e-desktop:
    name: Desktop E2E Tests
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        include:
          - os: ubuntu-latest
            platform: tauri-linux
          - os: macos-latest
            platform: tauri-macos
          - os: windows-latest
            platform: tauri-windows
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - name: Install dependencies
        run: |
          cd frontend-nextjs
          npm ci
      - name: Build Tauri app
        run: |
          cd frontend-nextjs
          npm run tauri:build
      - name: Run Tauri E2E tests
        run: |
          cd desktop-e2e
          npm ci
          npx playwright test --project=${{ matrix.platform }}
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: desktop-e2e-results-${{ matrix.platform }}
          path: desktop-e2e/playwright-report/

  stress-test:
    name: Stress Tests
    runs-on: ubuntu-latest
    needs: [e2e-web, e2e-mobile, e2e-desktop]  # Run after E2E tests
    if: github.event_name == 'schedule'  # Only run on scheduled runs
    steps:
      - uses: actions/checkout@v4
      - name: Setup k6
        run: |
          curl https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz -L | tar xvz
          sudo mv k6-*/k6 /usr/local/bin/
      - name: Install backend dependencies
        run: |
          cd backend
          pip install -e .
      - name: Start backend
        run: |
          cd backend
          python -m uvicorn main:app &
          sleep 10
      - name: Run stress tests
        run: |
          cd backend/tests/stress
          k6 run load_test_k6.js
      - name: Upload stress test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: stress-test-results
          path: backend/tests/stress/load-test-report.json

  aggregate-results:
    name: Aggregate Test Results
    runs-on: ubuntu-latest
    needs: [e2e-web, e2e-mobile, e2e-desktop, stress-test]
    if: always()
    steps:
      - uses: actions/checkout@v4
      - name: Download all artifacts
        uses: actions/download-artifact@v3
      - name: Aggregate results
        run: |
          # Aggregate all test results into unified report
          node test-orchestrator/scripts/aggregate-results.js
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('unified-report.json', 'utf8'));
            const body = `## E2E Test Results\n\n**Total:** ${report.total}\n**Passed:** ${report.passed}\n**Failed:** ${report.failed}\n**Duration:** ${report.duration}`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

## Recommended Build Order

### Phase 1: Foundation (Week 1-2)

**Goal:** Establish test infrastructure and shared utilities.

**Tasks:**
1. **Test Data Management**
   - Extend existing pytest fixtures with factory-boy factories
   - Create TestDataManager service for CRUD orchestration
   - Implement seed data JSON files for common scenarios
   - Add test data isolation (transactions, rollback)
   - **Files:** `backend/tests/fixtures/test_data_manager.py`, `backend/tests/fixtures/factories.py`

2. **Shared Test Utilities**
   - Create test helpers for common operations (auth, agent creation, workflow execution)
   - Implement reusable selectors (Playwright, Detox)
   - Add test configuration management
   - **Files:** `test-orchestrator/src/shared/utils.ts`, `frontend-nextjs/tests/utils/test-helpers.ts`, `mobile/e2e/helpers/test-helpers.js`

3. **Unified Reporter Foundation**
   - Aggregate existing test reports (HTML, JSON, JUnit)
   - Generate unified test report with platform breakdown
   - **Files:** `test-orchestrator/src/reporters/unified-reporter.ts`

**Dependencies:** None (foundational work)

**Validation:**
- Test data manager creates/destroys data correctly
- Shared utilities work across platforms
- Unified reporter aggregates results

---

### Phase 2: Web E2E Expansion (Week 3-4)

**Goal:** Expand existing Playwright tests from basic to comprehensive (300+ tests).

**Tasks:**
1. **Authentication Flows**
   - Login, logout, session management
   - JWT token refresh
   - Multi-factor authentication (if applicable)
   - **Files:** `frontend-nextjs/tests/e2e/auth/*.spec.ts`

2. **Agent Interaction Flows**
   - Agent list, search, filter
   - Agent execution (streaming responses)
   - Agent chat interface
   - Agent settings configuration
   - **Files:** `frontend-nextjs/tests/e2e/agents/*.spec.ts`

3. **Workflow Execution Flows**
   - Workflow creation (builder UI)
   - Workflow execution (manual triggers, automated triggers)
   - Workflow state management
   - Workflow history and logs
   - **Files:** `frontend-nextjs/tests/e2e/workflows/*.spec.ts`

4. **Canvas Presentation Flows**
   - Canvas rendering (charts, forms, sheets, markdown)
   - Canvas interactivity (form submission, button clicks)
   - Canvas state management
   - Canvas accessibility (aria labels, keyboard nav)
   - **Files:** `frontend-nextjs/tests/e2e/canvas/*.spec.ts`

5. **Episodic Memory Flows**
   - Episode creation (automatic segmentation)
   - Episode retrieval (temporal, semantic, contextual)
   - Episode graduation
   - Episode analytics
   - **Files:** `frontend-nextjs/tests/e2e/episodic-memory/*.spec.ts`

**Dependencies:** Phase 1 (test data management, shared utilities)

**Validation:**
- 300+ web E2E tests passing
- Coverage of all critical user flows
- Test execution time <30min (with sharding)

---

### Phase 3: Mobile E2E Foundation (Week 5-6)

**Goal:** Establish Detox E2E testing for React Native mobile app (150+ tests).

**Tasks:**
1. **Detox Configuration**
   - Configure Detox for iOS and Android
   - Set up simulators/emulators in CI/CD
   - Configure test timeouts, retries, async behavior
   - **Files:** `mobile/configs/detox.config.js`

2. **Mobile Authentication**
   - Login, logout, session management
   - Biometric authentication (Face ID, Touch ID)
   - Deep link authentication
   - **Files:** `mobile/e2e/auth/*.e2e.js`

3. **Mobile Agent Interactions**
   - Agent list (mobile-specific UI)
   - Agent execution (mobile chat interface)
   - Agent voice input/output (if applicable)
   - **Files:** `mobile/e2e/agents/*.e2e.js`

4. **Device Features**
   - Camera integration (photo capture, barcode scan)
   - Location services
   - Push notifications
   - Deep links (atom:// protocol)
   - **Files:** `mobile/e2e/device-features/*.e2e.js`

**Dependencies:** Phase 1 (test data management), Phase 2 (shared test flows)

**Validation:**
- 150+ mobile E2E tests passing
- Coverage of mobile-specific features
- Test execution time <20min

---

### Phase 4: Desktop E2E Foundation (Week 7-8)

**Goal:** Establish Tauri E2E testing for desktop app (150+ tests).

**Tasks:**
1. **Tauri Playwright Configuration**
   - Configure Playwright for Tauri (CDP connection or WebDriver)
   - Set up desktop-specific test environment
   - Configure window management, native dialogs
   - **Files:** `desktop-e2e/playwright-tauri.config.ts`, `desktop-e2e/tests/helpers/tauri-helper.ts`

2. **Desktop Window Management**
   - Window resize, minimize, maximize, close
   - Window controls (custom titlebar)
   - Multi-window support (if applicable)
   - **Files:** `desktop-e2e/tests/window-management/*.spec.ts`

3. **Native Features**
   - File system access (file dialogs, read/write)
   - System tray integration
   - OS notifications
   - Deep links (atom:// protocol)
   - **Files:** `desktop-e2e/tests/native-features/*.spec.ts`

4. **Cross-Platform Behavior**
   - Platform-specific features (Windows, macOS, Linux)
   - Platform-specific UI elements
   - **Files:** `desktop-e2e/tests/cross-platform/*.spec.ts`

**Dependencies:** Phase 1 (test data management), Phase 2 (shared test flows)

**Validation:**
- 150+ desktop E2E tests passing
- Coverage of desktop-specific features
- Test execution time <20min

---

### Phase 5: Cross-Platform Orchestration (Week 9-10)

**Goal:** Implement unified test runner for cross-platform coordination.

**Tasks:**
1. **Unified Test Runner**
   - Orchestrate test execution across web, mobile, desktop
   - Manage parallelization and sharding
   - Aggregate test results
   - **Files:** `test-orchestrator/src/orchestrator.ts`

2. **Platform Runners**
   - Web runner wrapper (Playwright)
   - Mobile runner wrapper (Detox)
   - Desktop runner wrapper (Tauri)
   - **Files:** `test-orchestrator/src/runners/*.ts`

3. **Cross-Platform Test Reuse**
   - Share test logic across platforms (authentication, agents, workflows)
   - Platform-specific UI abstractions
   - **Files:** `test-orchestrator/src/shared/*.ts`

4. **CI/CD Integration**
   - GitHub Actions workflows for each platform
   - Unified workflow for all platforms
   - Parallel execution, result aggregation
   - **Files:** `.github/workflows/e2e-*.yml`

**Dependencies:** Phases 2, 3, 4 (platform-specific tests)

**Validation:**
- Unified runner executes all platform tests
- Cross-platform test reuse working
- Total test execution time <60min (with parallelization)

---

### Phase 6: Stress Testing Infrastructure (Week 11-12)

**Goal:** Implement load generation and failure injection for bug discovery.

**Tasks:**
1. **Load Generation (k6/Locust)**
   - Create load test scripts for backend endpoints
   - Simulate concurrent users (10, 50, 100)
   - Measure performance metrics (latency, error rate, throughput)
   - **Files:** `backend/tests/stress/load_test_k6.js`

2. **Failure Injection (Chaos Engineering)**
   - Network delays and failures
   - Database connection drops
   - Service crashes (backend restarts)
   - **Files:** `backend/tests/stress/chaos_test.py`

3. **Stress Test Orchestration**
   - Trigger stress tests in CI/CD (scheduled runs)
   - Collect and analyze metrics
   - Detect performance degradation
   - **Files:** `test-orchestrator/src/stress-tester.ts`

**Dependencies:** Phase 5 (CI/CD integration)

**Validation:**
- Stress tests run successfully
- Performance baselines established
- Performance degradation alerts working

---

### Phase 7: Bug Discovery & Reporting (Week 13-14)

**Goal:** Automate bug discovery and GitHub Issues integration.

**Tasks:**
1. **Failure Analysis**
   - Analyze test failures (screenshots, logs, traces)
   - Identify reproducible failures (same test fails 2+ times)
   - Categorize failures (timeout, assertion, crash)
   - **Files:** `test-orchestrator/src/analyzers/failure-analyzer.ts`

2. **Bug Reporting**
   - GitHub Issues integration (Octokit)
   - Automatic issue creation for reproducible failures
   - Issue deduplication (check for existing issues)
   - **Files:** `test-orchestrator/src/reporters/bug-reporter.ts`

3. **Test Report Enhancement**
   - Unified HTML report with platform breakdown
   - Screenshots, videos, traces for failures
   - Performance metrics, trends over time
   - **Files:** `test-orchestrator/src/reporters/html-reporter.ts`

**Dependencies:** Phase 6 (stress tests, failure data)

**Validation:**
- Reproducible failures automatically create GitHub Issues
- Unified report includes all platforms
- Performance trends tracked over time

---

## Sources

### High Confidence (Official Documentation & Best Practices)

- **[Playwright Documentation](https://playwright.dev/docs/intro)** - Authoritative E2E testing framework documentation
- **[Detox Documentation](https://wix.github.io/Detox/)** - React Native gray-box E2E testing framework
- **[Tauri Testing Guide](https://tauri.app/v1/guides/testing/)** - Official Tauri testing documentation
- **[GitHub Actions Documentation](https://docs.github.com/en/actions)** - CI/CD workflow configuration
- **[k6 Documentation](https://k6.io/docs/)** - Load testing and stress testing framework
- **[factory-boy Documentation](https://factoryboy.readthedocs.io/)** - Test data generation with SQLAlchemy
- **[Atom Backend Test Infrastructure](https://github.com/ruship24/atom/blob/main/backend/tests/conftest.py)** - Existing pytest fixtures, 50+ fixtures, factory-boy setup
- **[Atom Frontend E2E Tests](https://github.com/ruship24/atom/blob/main/playwright.config.ts)** - Existing Playwright configuration (v3.1 shipped)

### Medium Confidence (Industry Best Practices - Codebase Analysis)

- **Atom CI/CD Pipeline** - GitHub Actions workflows, deployment automation, health checks
- **Atom Monitoring Setup** - `/Users/rushiparikh/projects/atom/backend/docs/MONITORING_SETUP.md` - Health check endpoints, Prometheus metrics
- **Atom Deployment Runbook** - `/Users/rushiparikh/projects/atom/backend/docs/DEPLOYMENT_RUNBOOK.md` - Deployment procedures, rollback strategies
- **Cross-Platform Testing Patterns** - Shared test logic across platforms, platform-specific abstractions
- **Stress Testing Best Practices** - Load generation, failure injection, chaos engineering

### Low Confidence (Limited Verification - Needs Validation)

- **Detox + Expo Integration** - Detox supports Expo but configuration complexity unknown
- **Tauri Playwright Integration** - Tauri supports CDP but Playwright driver stability unknown
- **Mobile Simulator Pooling** - CI/CD simulator pooling strategies not well-documented
- **Stress Test Result Analysis** - Automated performance degradation detection patterns evolving

### Gaps Identified

- **Tauri E2E Testing Patterns** - Limited production examples of Playwright + Tauri integration
- **Cross-Platform Test Reuse** - Limited patterns for sharing test logic across web/mobile/desktop
- **Stress Test Baselines** - Unclear industry standards for "acceptable" stress test failure rates
- **Bug Filing Automation** - Risk of GitHub Issues noise, false positives in automated bug filing

**Next Research Phases:**
- Phase-specific research needed for Tauri + Playwright integration patterns
- Investigation into Detox + Expo E2E testing best practices
- Deep dive on cross-platform test reuse strategies
- Research on automated bug filing thresholds and noise reduction

---

*Architecture research for: Atom v7.0 Cross-Platform E2E Testing & Bug Discovery*
*Researched: March 23, 2026*
*Confidence: HIGH (mix of official docs, codebase analysis, industry best practices)*

# Architecture Research: E2E UI Testing with Playwright

**Domain:** End-to-End Testing Architecture for AI Automation Platform
**Researched:** February 23, 2026
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD Layer (GitHub Actions)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Backend Test │  │ Frontend     │  │   E2E UI     │  │  Quality     │   │
│  │   (pytest)   │  │  Build       │  │   Tests      │  │   Gates      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │             │
├─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┤
│         │                 │                 │                 │             │
│  ┌──────▼─────────────────▼─────────────────▼─────────────────▼───────┐    │
│  │                    Test Environment (Docker)                        │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │    │
│  │  │  Backend   │  │  Frontend  │  │  Playwright│  │ PostgreSQL ││    │
│  │  │  FastAPI   │  │  Next.js   │  │  Browsers  │  │   Test DB  ││    │
│  │  │  (port 8000)│ │ (port 3000)│  │  (headed)  │  │  (port 5433)│  │    │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Application Layer                                   │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    Atom Platform Services                          │    │
│  │  Agent Governance │ Episodic Memory │ LLM Integration │ Canvas API │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Playwright Tests** | Browser automation, UI interaction validation | `@playwright/test` with TypeScript, test fixtures |
| **Test Environment** | Isolated runtime with all dependencies | Docker Compose, service containers |
| **Test Database** | Seed data, cleanup, state isolation | PostgreSQL with per-test schemas |
| **GitHub Actions** | CI orchestration, artifact management, reporting | Workflow files, job dependencies |
| **Backend Server** | API endpoints, business logic, state management | FastAPI with test configuration overrides |
| **Frontend Server** | Next.js dev server, React components, state | `next dev` with test environment variables |

## Recommended Project Structure

```
frontend-nextjs/
├── e2e/                    # Playwright E2E tests (NEW)
│   ├── fixtures/           # Test fixtures and data factories
│   │   ├── auth.fixtures.ts      # Authentication state setup
│   │   ├── db.fixtures.ts         # Database seed/cleanup
│   │   ├── agent.fixtures.ts      # Agent creation helpers
│   │   └── canvas.fixtures.ts     # Canvas test data
│   ├── tests/               # Test files
│   │   ├── agent-governance/      # Governance UI tests
│   │   ├── episodic-memory/       # Episode management tests
│   │   ├── canvas-presentations/  # Canvas interaction tests
│   │   ├── llm-interactions/      # LLM streaming tests
│   │   └── smoke/                 # Critical path smoke tests
│   ├── utils/               # Test utilities
│   │   ├── api-helpers.ts         # API request wrappers
│   │   ├── selectors.ts           # Reusable locators
│   │   └── assertions.ts          # Custom assertions
│   ├── playwright.config.ts # Playwright configuration
│   └── tsconfig.json        # TypeScript config for tests
├── src/                    # Application source (unchanged)
│   ├── components/
│   ├── pages/
│   └── ...
├── package.json            # Add @playwright/test dependency
└── .github/
    └── workflows/
        └── playwright-e2e.yml  # CI workflow (NEW)

backend/
├── tests/                  # Existing pytest tests (unchanged)
│   ├── conftest.py         # Existing fixtures
│   └── ...
└── tests-e2e-api/          # Optional: API setup helpers
    ├── seed_data.py        # Database seeding utilities
    └── test_state.py       # State management for E2E
```

### Structure Rationale

- **`e2e/` directory**: Separates E2E tests from unit/integration tests, follows Playwright conventions
- **`fixtures/`**: Reusable test setup/teardown, mirrors backend's `conftest.py` pattern
- **`tests/` grouping**: Organized by feature domain (governance, memory, canvas), aligns with backend pytest markers
- **`utils/`**: Shared helpers prevent duplication, maintainable selectors
- **Top-level `e2e/` vs `tests/e2e/`**: Playwright default is `e2e/`, but can be `tests/e2e/` if preferred

## Architectural Patterns

### Pattern 1: Test Fixture Hierarchy

**What:** Layered fixtures providing test data with proper lifecycle management

**When to use:**
- Setting up complex test state (agents, episodes, canvas presentations)
- Tests requiring pre-conditions (authentication, database seeds)
- Sharing setup across multiple test files

**Trade-offs:**
- Pros: DRY, maintainable, consistent test data
- Cons: Fixture complexity can grow, requires understanding of scoping

**Example:**
```typescript
import { test as base } from '@playwright/test';

type AgentFixtures = {
  authenticatedPage: Page;
  studentAgent: Agent;
  internAgent: Agent;
};

export const test = base.extend<AgentFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Set up auth via API
    const token = await loginViaAPI();
    await page.goto('http://localhost:3000');
    await page.evaluate(({ token }) => {
      localStorage.setItem('auth_token', token);
    }, { token });
    await page.reload();
    await use(page);
  },

  studentAgent: async ({ request }, use) => {
    // Create agent via API
    const response = await request.post('http://localhost:8000/api/v1/agents', {
      data: {
        name: 'E2E Student Agent',
        maturity: 'STUDENT',
        confidence: 0.4
      }
    });
    const agent = await response.json();
    await use(agent);

    // Cleanup
    await request.delete(`http://localhost:8000/api/v1/agents/${agent.id}`);
  }
});
```

### Pattern 2: Worker-Based Database Isolation

**What:** Each Playwright worker gets a dedicated database schema for parallel execution

**When to use:**
- Running tests in parallel with `fullyParallel: true`
- Tests that modify database state
- Preventing test pollution between workers

**Trade-offs:**
- Pros: Safe parallel execution, no test interference
- Cons: More complex setup, database resource usage

**Example:**
```typescript
export const test = base.extend<{
  dbSchema: string;
}>({
  dbSchema: async ({}, use) => {
    // Use worker index for unique schema
    const workerIndex = test.info().workerIndex;
    const schema = `test_worker_${workerIndex}`;

    // Create schema via API
    await request.post('http://localhost:8000/api/v1/test/create-schema', {
      data: { schema }
    });

    await use(schema);

    // Cleanup
    await request.post('http://localhost:8000/api/v1/test/drop-schema', {
      data: { schema }
    });
  }
});
```

### Pattern 3: API-First Test Setup

**What:** Use API requests to set up test state, then use UI for validation

**When to use:**
- Faster test execution (skip slow UI setup steps)
- Complex data scenarios (create multiple entities)
- Testing UI after backend actions

**Trade-offs:**
- Pros: Fast, reliable, tests API contracts
- Cons: Less realistic user journey, API changes break tests

**Example:**
```typescript
test('agent list displays created agents', async ({ page, request }) => {
  // Setup: Create agents via API
  await request.post('http://localhost:8000/api/v1/agents', {
    data: { name: 'Agent 1', maturity: 'STUDENT' }
  });
  await request.post('http://localhost:8000/api/v1/agents', {
    data: { name: 'Agent 2', maturity: 'INTERN' }
  });

  // Test: Navigate and verify UI
  await page.goto('http://localhost:3000/agents');
  await expect(page.getByText('Agent 1')).toBeVisible();
  await expect(page.getByText('Agent 2')).toBeVisible();
});
```

## Data Flow

### Test Execution Flow

```
[GitHub Actions Trigger]
    ↓
[Start Docker Compose Services]
    ├── Backend FastAPI (port 8000)
    ├── Frontend Next.js (port 3000)
    └── PostgreSQL Test DB (port 5433)
    ↓
[Run Migrations & Seed Base Data]
    ↓
[Playwright Tests Execute]
    ├── [Worker 1] → Test File A → Browser Context → API Requests → DB
    ├── [Worker 2] → Test File B → Browser Context → API Requests → DB
    └── [Worker N] → Test File C → Browser Context → API Requests → DB
    ↓
[Collect Artifacts & Reports]
    ├── Screenshots (on failure)
    ├── Traces (on retry)
    ├── HTML Report
    └── Coverage (optional)
    ↓
[Cleanup Docker Containers]
```

### Test Isolation Strategy

```
[Test File 1 - Worker 0]          [Test File 2 - Worker 1]
        ↓                                 ↓
[Browser Context 1]                [Browser Context 2]
[Isolated localStorage]            [Isolated localStorage]
[Isolated cookies]                 [Isolated cookies]
        ↓                                 ↓
[API Request 1] → DB Schema 0      [API Request 2] → DB Schema 1
[Test Data Set A]                  [Test Data Set B]
        ↓                                 ↓
[Cleanup: Context Close]           [Cleanup: Context Close]
[Cleanup: DB Schema Drop]          [Cleanup: DB Schema Drop]
```

### Key Data Flows

1. **Authentication Flow:**
   - API request to `/api/v1/auth/login` → JWT token
   - Store token in `localStorage` → Set `Authorization` header
   - All subsequent requests include auth context

2. **Agent Creation Flow:**
   - Test fixture creates agent via API → `POST /api/v1/agents`
   - Backend stores in PostgreSQL → Returns agent ID
   - Test navigates to UI → Validates agent appears in list

3. **Canvas Presentation Flow:**
   - API creates canvas → `POST /api/v1/canvas`
   - Frontend polls WebSocket for updates
   - Test waits for canvas render → Validates chart/form display

4. **Test Data Cleanup Flow:**
   - `test.afterEach()` hook runs → API delete calls
   - Database schema dropped (worker-specific)
   - Browser context closes → Cookies/localStorage cleared

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-100 tests** | Single GitHub Actions job, `workers: 2`, local testing sufficient |
| **100-500 tests** | Parallel workers (`workers: 4`), test sharding, report merging |
| **500-1000 tests** | Matrix strategy (multiple jobs), docker-compose scaling, optimized fixtures |
| **1000+ tests** | Split into smoke/regression suites, distributed runners, test caching |

### Scaling Priorities

1. **First bottleneck: Test execution time**
   - **Fix:** Enable `fullyParallel: true` in playwright.config.ts
   - Use API-first setup to skip slow UI interactions
   - Optimize fixtures (lazy loading, proper scoping)

2. **Second bottleneck: CI pipeline duration**
   - **Fix:** Implement test sharding: `npx playwright test --shard=1/4`
   - Cache browser installations with GitHub Actions cache
   - Split smoke tests (run on PR) from full suite (run on main)

## Anti-Patterns

### Anti-Pattern 1: Shared Test State

**What people do:**
```typescript
// BAD: Global state shared across tests
let sharedAgentId: string;

test.beforeAll(async ({ request }) => {
  const agent = await request.post('/api/v1/agents', { data: {...} });
  sharedAgentId = agent.id();
});

test('test 1', async ({ page }) => {
  await page.goto(`/agents/${sharedAgentId}`);
});

test('test 2', async ({ page }) => {
  await page.goto(`/agents/${sharedAgentId}`);
});
```

**Why it's wrong:**
- Tests can't run in parallel (race conditions)
- Order-dependent tests (test 2 fails if test 1 fails)
- Difficult to debug which test caused failures

**Do this instead:**
```typescript
// GOOD: Each test creates its own data
test('test 1', async ({ page, request }) => {
  const agent = await request.post('/api/v1/agents', { data: {...} });
  await page.goto(`/agents/${agent.id()}`);
});

test('test 2', async ({ page, request }) => {
  const agent = await request.post('/api/v1/agents', { data: {...} });
  await page.goto(`/agents/${agent.id()}`);
});
```

### Anti-Pattern 2: Hardcoded Waits

**What people do:**
```typescript
// BAD: Arbitrary wait times
await page.goto('/agents');
await page.waitForTimeout(3000); // Wait 3 seconds
await expect(page.getByText('Agent 1')).toBeVisible();
```

**Why it's wrong:**
- Flaky tests (too short = failure, too long = slow tests)
- Wastes time in CI
- Doesn't guarantee what you're waiting for

**Do this instead:**
```typescript
// GOOD: Wait for specific conditions
await page.goto('/agents');
await expect(page.getByText('Agent 1')).toBeVisible();
// Or use web-first assertions with built-in wait
```

### Anti-Pattern 3: Testing Implementation Details

**What people do:**
```typescript
// BAD: Testing CSS classes or internal structure
await expect(page.locator('.agent-card__container')).toHaveClass(/active/);
await expect(page.locator('div > div > span')).toHaveText('Agent 1');
```

**Why it's wrong:**
- Tests break when CSS changes (not functional changes)
- Brittle selectors (div soup)
- Doesn't validate user-facing behavior

**Do this instead:**
```typescript
// GOOD: Test user-visible behavior
await expect(page.getByRole('button', { name: 'Create Agent' })).toBeVisible();
await expect(page.getByText('Agent 1')).toBeVisible();
```

### Anti-Pattern 4: No Test Cleanup

**What people do:**
```typescript
// BAD: No cleanup, test data accumulates
test('creates agent', async ({ request }) => {
  await request.post('/api/v1/agents', { data: {...} });
  // Test ends, agent remains in database
});
```

**Why it's wrong:**
- Database grows unbounded (slow queries)
- Subsequent test runs hit unique constraint violations
- CI environment becomes inconsistent

**Do this instead:**
```typescript
// GOOD: Explicit cleanup
test('creates agent', async ({ request }) => {
  const response = await request.post('/api/v1/agents', { data: {...} });
  const agent = await response.json();

  // Cleanup in test.afterEach
  test.afterAll(async () => {
    await request.delete(`/api/v1/agents/${agent.id}`);
  });
});
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Backend API** | API request fixtures (`request` context) | Use base URL from config, respect auth headers |
| **PostgreSQL** | Via backend API (no direct DB access) | Backend provides test endpoints for schema creation/drop |
| **WebSocket** | Page events for real-time updates | Test waits for WS messages before asserting UI state |
| **LLM Providers** | Mock at backend level | Don't call real OpenAI/Anthropic in E2E tests |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Playwright ↔ Backend** | HTTP/REST API | Tests run against localhost:8000 in CI |
| **Playwright ↔ Frontend** | Browser automation (Chromium) | Tests navigate localhost:3000 |
| **Frontend ↔ Backend** | Existing WebSocket/HTTP | No changes needed, same as production |
| **E2E Tests ↔ Pytest** | Shared test data conventions | Use similar fixture patterns for consistency |

### CI/CD Integration

**GitHub Actions Workflow:**
```yaml
name: E2E Tests

on:
  pull_request:
  push:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: atom_e2e_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend-nextjs/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend-nextjs
        run: npm ci

      - name: Install Playwright Browsers
        working-directory: ./frontend-nextjs
        run: npx playwright install --with-deps

      - name: Start Backend
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost:5433/atom_e2e_test
        run: |
          pip install -r requirements.txt
          uvicorn main:app --host 0.0.0.0 --port 8000 &
          echo "Backend started"

      - name: Start Frontend
        working-directory: ./frontend-nextjs
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
        run: |
          npm run dev &
          echo "Frontend started"

      - name: Run Playwright Tests
        working-directory: ./frontend-nextjs
        run: npx playwright test

      - name: Upload Test Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend-nextjs/playwright-report/
          retention-days: 30
```

## New vs Modified Components

### New Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Playwright Config** | Test configuration, browsers, fixtures | `frontend-nextjs/e2e/playwright.config.ts` |
| **Test Fixtures** | Auth, database, agent setup helpers | `frontend-nextjs/e2e/fixtures/` |
| **Test Files** | Browser automation tests | `frontend-nextjs/e2e/tests/` |
| **Test Utilities** | Selectors, assertions, API wrappers | `frontend-nextjs/e2e/utils/` |
| **CI Workflow** | GitHub Actions job for E2E tests | `.github/workflows/playwright-e2e.yml` |
| **Docker Compose (E2E)** | Test environment services | `docker-compose-e2e.yml` (NEW) |

### Modified Components

| Component | Changes | Impact |
|-----------|---------|--------|
| **package.json** | Add `@playwright/test` dependency | Frontend dev dependency |
| **backend/tests/conftest.py** | Optional: Add E2E helper endpoints | No impact on existing tests |
| **CI Pipeline** | Add E2E job after frontend-build | Longer total CI time |
| **Docker Compose** | Extend for E2E environment | New services or config overrides |

## Build Order

Based on dependencies, recommended component build sequence:

1. **Phase 1: Test Environment Setup**
   - Create `docker-compose-e2e.yml` with backend, frontend, postgres services
   - Verify services start locally with `docker-compose up`
   - Test backend health: `curl http://localhost:8000/health/live`

2. **Phase 2: Playwright Configuration**
   - Install `@playwright/test` in frontend-nextjs
   - Create `e2e/playwright.config.ts` with base configuration
   - Verify: `npx playwright test --help` runs successfully

3. **Phase 3: Test Fixtures & Utilities**
   - Create `e2e/fixtures/auth.fixtures.ts` (API-based login)
   - Create `e2e/fixtures/db.fixtures.ts` (database schema isolation)
   - Create `e2e/utils/selectors.ts` (reusable locators)

4. **Phase 4: Smoke Tests**
   - Write `e2e/tests/smoke/landing.spec.ts` (page loads)
   - Write `e2e/tests/smoke/auth.spec.ts` (login flow)
   - Run locally: `npx playwright test --project=chromium`

5. **Phase 5: Feature Tests**
   - Write agent governance tests
   - Write canvas presentation tests
   - Write episodic memory tests

6. **Phase 6: CI Integration**
   - Create `.github/workflows/playwright-e2e.yml`
   - Configure service containers (postgres)
   - Test in PR: verify artifacts upload

7. **Phase 7: Optimization**
   - Enable parallel execution
   - Add test sharding for large suites
   - Configure report merging for matrix jobs

## Sources

### Official Documentation (HIGH Confidence)
- [Playwright Official Documentation - Introduction](https://playwright.dev/docs/intro)
- [Playwright Docker Integration](https://playwright.dev/docs/docker)
- [Playwright API Testing Guide](https://playwright.dev/docs/api-testing)

### Implementation Examples (MEDIUM-HIGH Confidence)
- [Next.js + FastAPI Full-Stack Template - E2E Testing](https://www.cnblogs.com/lightsong/p/18692486) (Jan 2025)
- [Playwright CI/CD Integration Guide (Aliyun - Jan 2026)](https://developer.aliyun.com/article/1706462)
- [Playwright Test Execution Strategy (Huawei Cloud - Jan 2026)](https://bbs.huaweicloud.com/blogs/472353)
- [Playwright Parallel Testing Configuration (Juejin - Dec 2025)](https://juejin.cn/post/7589093939656081460)

### Best Practices (MEDIUM Confidence)
- [Playwright Best Practices 2026 (BrowserStack)](https://www.browserstack.com/guide/playwright-best-practices)
- [Test Data Isolation with Worker Index (Feb 2026)](https://m.blog.csdn.net/gitblog_00272/article/details/151815506)
- [GitHub Actions Playwright Integration (51Testing - Jan 2026)](http://www.51testing.com/?action-viewnews-itemid-7808411)

### Existing Atom Codebase (HIGH Confidence)
- `/Users/rushiparikh/projects/atom/backend/tests/conftest.py` - Existing pytest fixture patterns
- `/Users/rushiparikh/projects/atom/backend/tests/e2e/conftest.py` - E2E test infrastructure
- `/Users/rushiparikh/projects/atom/.github/workflows/ci.yml` - Existing CI/CD patterns
- `/Users/rushiparikh/projects/atom/docker-compose-personal.yml` - Docker Compose configuration
- `/Users/rushiparikh/projects/atom/frontend-nextjs/package.json` - Frontend dependencies

---
*Architecture research for: E2E UI Testing with Playwright*
*Researched: February 23, 2026*

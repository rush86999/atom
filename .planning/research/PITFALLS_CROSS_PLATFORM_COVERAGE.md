# Pitfalls Research: Cross-Platform 80% Coverage Achievement

**Domain:** Multi-platform test coverage expansion (frontend, backend, mobile, desktop)
**Researched:** March 3, 2026
**Confidence:** HIGH

## Executive Summary

Expanding test coverage to 80% across four platforms simultaneously (frontend: 89.84%, backend: 74.6%, mobile: 16.16%, desktop: TBD) introduces **maintenance scaling** and **CI/CD bottleneck** risks not present in single-platform efforts. Research shows the most critical pitfalls are (1) monolithic test workflows causing 40+ minute feedback loops, (2) coverage measurement inconsistencies across platforms masking regressions, (3) brittle test patterns from over-mocking and async timing issues, (4) test execution time explosion as coverage increases, and (5) platform-specific test failures from device fragmentation and OS differences.

**Key differentiator:** Multi-platform coverage expansion requires **unified quality gates** and **parallel execution strategies** from day one — not after-the-fact aggregation. Frontend's existing 89.84% coverage masks underlying brittleness (40% pass rate on 21 failing tests), mobile's low 16.16% coverage requires different tooling (jest-expo, Detox), and desktop Tauri testing lacks established patterns.

Based on analysis of 1,900+ existing tests, CI/CD workflows, and industry anti-patterns from 2024-2026 testing literature.

---

## Critical Pitfalls

### Pitfall 1: Monolithic Test Workflow (40+ Minute Feedback Loops)

**What goes wrong:**
Single CI job runs all platform tests sequentially (backend → frontend → mobile → desktop), causing 40+ minute feedback cycles. Developers push code, wait 40 minutes for tests, discover failures, fix, push again, wait another 40 minutes. Productivity plummets, team circumvents CI by merging without tests, coverage goals abandoned.

**Why it happens:**
- Path of least resistance: "Let's just add tests to existing workflow"
- CI/CD setup fatigue: Creating separate workflows feels like duplication
- Artifact management overhead: Uploading/downloading coverage reports seems complex
- False economy: "One job = simpler to maintain" (false at scale)

**How to avoid:**
```yaml
# BAD: Sequential execution in single job
jobs:
  all-tests:
    steps:
      - run: pytest backend/tests/          # 10 min
      - run: npm test --prefix frontend     # 10 min
      - run: npm test --prefix mobile       # 10 min
      - run: cargo test --manifest-path=... # 10 min
      - run: python scripts/aggregate_coverage.py

# GOOD: Parallel platform-specific jobs
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps: [...] # 10 min, uploads coverage artifact
  frontend-tests:
    runs-on: ubuntu-latest
    steps: [...] # 10 min, uploads coverage artifact
  mobile-tests:
    runs-on: ubuntu-latest
    steps: [...] # 10 min, uploads coverage artifact
  desktop-tests:
    runs-on: ubuntu-latest
    steps: [...] # 10 min, uploads coverage artifact
  aggregate-coverage:
    needs: [backend-tests, frontend-tests, mobile-tests, desktop-tests]
    runs-on: ubuntu-latest
    steps: [...]
```

**Warning signs:**
- PR comments say "tests still running" 20+ minutes after push
- Team pushes "fix typos" commits without waiting for test results
- CI queue shows 3-5 builds backed up
- Developers run tests locally instead of waiting for CI (defeats purpose)

**Phase to address:** Phase 099-01 (Cross-Platform Integration Planning) — Design parallel workflow architecture before writing tests. Phase 099-02 (Coverage Aggregation Implementation) — Build artifact upload/download infrastructure.

**Platform-specific warning signs:**
- **Backend:** pytest taking >15 min indicates lack of test categorization (unit/integration/E2E should run separately)
- **Frontend:** Jest taking >10 min indicates too many component tests, not enough integration tests
- **Mobile:** jest-expo taking >20 min indicates device feature tests not mocked properly
- **Desktop:** cargo test + Jest taking >15 min indicates Rust tests not parallelized with `--test-threads`

---

### Pitfall 2: Coverage Without Context (Regression Masking)

**What goes wrong:**
Unified coverage percentage masks regressions in specific platforms. "Overall coverage: 65%" hides that frontend dropped from 89% → 82%, backend stagnated at 74%, mobile stayed at 16%, while desktop (TBD) dragged average down. Team celebrates hitting 80% target while critical platforms regress.

**Why it happens:**
- Single-number dashboard simplicity: "Look, we hit 80%!"
- Percentage averaging arithmetic: (89 + 74 + 16 + TBD) / 4 = target
- Leadership pressure: "Show progress on coverage roadmap"
- Aggregation script simplicity: Sum all covered lines / total lines across platforms

**How to avoid:**
```json
// BAD: Single percentage without breakdown
{
  "overall_coverage": 47.8,
  "status": "PASS"
}

// GOOD: Detailed breakdown with trends
{
  "overall_coverage": 47.8,
  "status": "WARNING", // Regression detected
  "platforms": {
    "backend": {
      "percent_covered": 74.6,
      "trend": "+2.1%",
      "status": "IMPROVING"
    },
    "frontend": {
      "percent_covered": 89.84,
      "trend": "-0.5%", // REGRESSION
      "status": "REGRESSING",
      "files_dropped": ["src/components/AgentChat.tsx", "src/hooks/useCanvasState.ts"]
    },
    "mobile": {
      "percent_covered": 16.16,
      "trend": "+1.2%",
      "status": "BELOW_TARGET",
      "gap_to_target": 63.84
    },
    "desktop": {
      "percent_covered": 0,
      "trend": "BASELINE",
      "status": "NOT_MEASURED"
    }
  },
  "alerts": [
    "Frontend coverage dropped by 0.5%",
    "Mobile coverage 63.84 points below 80% target",
    "Desktop coverage not yet measured"
  ]
}
```

**Warning signs:**
- Coverage reports show single percentage without per-platform breakdown
- PR comments say "Coverage +2%" without mentioning which files changed
- Dashboard shows trend line but no drill-down into platforms
- Team can't answer "Which modules lost coverage this week?"

**Phase to address:** Phase 099-03 (Unified Quality Gates) — Implement coverage aggregation with per-platform breakdowns, trend tracking, regression alerts. Phase 099-04 (Dashboard & Reporting) — Build multi-dimensional coverage visualization.

**Platform-specific warning signs:**
- **Frontend:** 89.84% coverage but 40% test pass rate indicates high-coverage/low-quality tests
- **Backend:** 74.6% coverage with 22 missing branches in `agent_governance_service.py` indicates edge case gaps
- **Mobile:** 16.16% coverage with 25+ test files indicates infrastructure exists but coverage incomplete
- **Desktop:** No coverage.json indicates Cargo.toml lacks `tarpaulin` or `covector` configuration

---

### Pitfall 3: Brittle Test Patterns (Over-Mocking, Async Timing, Implementation Coupling)

**What goes wrong:**
Tests become brittle through three anti-patterns: (1) Over-mocking external dependencies (mocking value objects, internal functions), (2) Async timing issues (asserting before state updates complete), (3) Testing implementation details (CSS classes, function call counts, internal state). Tests fail during refactoring despite no logic changes, team stops trusting tests, disables flaky tests with `.skip`, coverage becomes meaningless.

**Why it happens:**
- Frontend component tests mock everything: "Mock React context, mock API, mock router"
- Async confusion: `await waitFor()` not used, `fireEvent.click()` doesn't wait for React state updates
- React Testing Library misused: `getByTestId()` instead of `getByRole()`, testing `className` instead of visible text
- Backend tests mock database: "Mock Session, mock query, mock result" instead of using test database
- Property tests over-used: Testing every function with Hypothesis when example-based tests suffice

**How to avoid:**
```typescript
// BAD: Over-mocked, tests implementation, brittle
test('AgentChat component updates', () => {
  const mockSetState = jest.fn();
  const mockRouter = jest.mocked useRouter();
  const mockContext = jest.mocked(useAgentContext());
  const mockApi = jest.spyOn(api, 'getAgents');

  mockRouter.push.mockImplementation(() => {});
  mockContext.setState.mockImplementation(() => {});
  mockApi.mockResolvedValue({ agents: [] });

  render(<AgentChat />);
  fireEvent.click(screen.getByTestId('submit-button')); // Wrong query method

  expect(mockSetState).toHaveBeenCalledWith({ loading: true }); // Tests internal call
  expect(screen.getByClassName('agent-chat--loading')).toBeInTheDocument(); // Tests CSS
});

// GOOD: Tests behavior, minimal mocking, stable queries
test('AgentChat displays agents after loading', async () => {
  // Only mock external API dependency, not internal state
  jest.spyOn(api, 'getAgents').mockResolvedValue({
    agents: [{ id: '1', name: 'Agent 1' }]
  });

  render(<AgentChat />);

  // Use waitFor for async state updates
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
  });

  // Test visible behavior, not CSS classes or internal calls
  expect(screen.getByText('Agent 1')).toBeInTheDocument();
  expect(screen.getByLabelText('loading agents')).not.toBeInTheDocument(); // ARIA labels
});
```

**Warning signs:**
- 21/35 frontend tests failing (40% pass rate) indicates widespread brittleness
- Tests disabled with `.skip`, `xit`, or `@pytest.mark.skipif`
- Team comments: "Tests fail after refactoring, code works though"
- CI flaky: "Test passes on re-run, failed first time"
- Mock verification: `expect(mockFn).toHaveBeenCalledWith(...)` tests implementation, not behavior

**Phase to address:** Phase 099-05 (Test Standardization & Guidelines) — Create testing style guide with examples of brittle vs. robust patterns. Phase 099-06 (Test Refactoring) — Fix existing brittle tests, prevent new ones via PR reviews.

**Platform-specific warning signs:**
- **Frontend:** React Testing Library misused → `getByTestId()` everywhere instead of `getByRole()`, `getByLabelText()`
- **Backend:** Hypothesis tests over-used → `@given` decorators on simple CRUD operations better tested with example-based tests
- **Mobile:** Expo modules over-mocked → Mocking `expo-camera`, `expo-location` instead of using `expo-mock`
- **Desktop:** Tauri invoke calls mocked → Testing internal Rust commands instead of public API contracts

---

### Pitfall 4: Test Execution Time Explosion (Linear Scaling with Coverage)

**What goes wrong:**
As coverage expands from 60% → 80%, test execution time increases linearly. Backend pytest grows from 5 min → 15 min, frontend Jest from 2 min → 8 min, mobile jest-expo from 3 min → 12 min, desktop from 1 min → 6 min. Total CI time: 40+ min despite parallelization. Team reduces coverage to save time, abandons 80% goal.

**Why it happens:**
- No test categorization: All tests run on every commit (unit + integration + E2E)
- No parallelization: Single-threaded test runners (pytest, Jest without workers)
- No incremental testing: All 1,900+ tests run regardless of changed files
- No caching: Dependencies downloaded every run, database rebuilt from scratch
- No selective execution: Property tests with 1000 examples run on every commit

**How to avoid:**
```yaml
# Test categorization with pytest marks
# backend/tests/conftest.py
import pytest

@pytest.mark.unit
def test_agent_governance_permission():
    # Fast unit test, runs on every commit
    pass

@pytest.mark.integration
def test_agent_execution_with_database():
    # Slower integration test, runs on merge to main
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_full_workflow_from_ui_to_backend():
    # Very slow E2E test, runs nightly
    pass

# .github/workflows/backend-tests.yml
jobs:
  backend-unit:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -m "unit" -n auto --cov=core --cov-report=json  # < 2 min

  backend-integration:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - run: pytest -m "integration" -n auto --cov=core --cov-append  # < 5 min

  backend-e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - run: pytest -m "e2e" --cov=core --cov-append  # < 10 min
```

**Warning signs:**
- pytest runs >10 min on average commit
- Jest `--testTimeout=10000` increased to 30000 because tests timing out
- CI logs show "Running 1900 tests..." on every PR (should be subset)
- Team removes tests to speed up CI
- Developers run tests locally instead of waiting for CI

**Phase to address:** Phase 099-07 (Performance Optimization) — Implement test categorization (unit/integration/E2E), parallel execution (pytest-xdist, Jest workers), incremental testing (pytest-testmon, Jest --onlyChanged). Phase 099-08 (Caching & Infrastructure) — Add dependency caching, Docker layer caching, database fixtures.

**Platform-specific execution times:**
- **Backend:** 74.6% coverage with pytest taking 5-10 min → Target <5 min via `-n auto`, test categorization
- **Frontend:** 89.84% coverage with Jest taking 2-5 min → Target <2 min via `--maxWorkers=4`, mark slow tests
- **Mobile:** 16.16% coverage with jest-expo taking 3-8 min → Target <3 min via device API mocking, test grouping
- **Desktop:** TBD coverage with cargo test + Jest → Target <5 min via `--test-threads`, parallel Rust compilation

---

### Pitfall 5: Platform-Specific Test Failures (Device Fragmentation, OS Differences)

**What goes wrong:**
Tests pass locally but fail in CI due to platform-specific differences: (1) Mobile tests fail on Android but pass on iOS (device permissions, custom ROMs), (2) Desktop tests fail on Windows CI but pass on macOS (filesystem paths, line endings), (3) Frontend tests fail in CI jsdom but pass locally (browser API differences), (4) Backend tests fail in CI PostgreSQL but pass locally with SQLite.

**Why it happens:**
- Mobile: Device fragmentation (20,000+ Android models, custom ROMs like MIUI/OneUI, iOS 16-18 differences)
- Desktop: OS differences (Windows backslashes vs macOS forward slashes, case-sensitive filenames)
- Frontend: Browser API differences (jsdom lacks `ResizeObserver`, CI missing `localStorage`)
- Backend: Database differences (SQLite for local dev, PostgreSQL in CI, connection pooling issues)

**How to avoid:**
```typescript
// Mobile: Platform-specific test mocking
// mobile/src/__tests__/helpers/deviceMocks.ts
import * as Platform from 'react-native';

Platform.OS = 'ios'; // Force iOS behavior in tests

jest.mock('expo-camera', () => ({
  requestCameraPermissionsAsync: jest.fn(() =>
    Platform.OS === 'ios'
      ? Promise.resolve({ status: 'granted' })
      : Promise.resolve({ status: 'denied' }) // Android requires user approval
  ),
}));

// Desktop: OS-agnostic path handling
// frontend-nextjs/src-tauri/tests/fileUtil.test.ts
import path from 'path';

// BAD: Assumes Unix paths
expect(filePath).toBe('/home/user/Documents/file.txt');

// GOOD: OS-agnostic assertion
expect(path.normalize(filePath)).toMatch(/file\.txt$/);
expect(filePath).toContain(path.sep);

// Frontend: jsdom polyfills for missing browser APIs
// frontend-nextjs/tests/setup.ts
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Backend: Test container configuration
# .github/workflows/backend-tests.yml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_HOST_AUTH_METHOD: trust
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

**Warning signs:**
- CI logs show "Error: EPERM: operation not permitted" on Windows, not macOS
- iOS tests pass, Android tests fail: "Permission denied: CAMERA"
- Frontend tests fail: "ResizeObserver is not defined"
- Backend tests fail: "relation does not exist" (SQLite vs PostgreSQL schema mismatch)
- Team comments: "Works on my machine" in PR discussions

**Phase to address:** Phase 099-09 (Cross-Platform Validation) — Add Android/iOS matrix testing for mobile, Windows/macOS/Linux matrix for desktop, browser matrix for frontend. Phase 099-10 (Environment Standardization) — Dockerize test environments, use same database across dev/CI.

**Platform-specific failure patterns:**
- **Mobile:** iOS 13+ vs Android 8+ permission differences (camera, location, biometrics)
- **Desktop:** Windows file locking (can't delete open files), macOS sandbox restrictions
- **Frontend:** jsdom lacks `IntersectionObserver`, `matchMedia` incomplete
- **Backend:** SQLite supports partial indexes, PostgreSQL doesn't (migration failures)

---

### Pitfall 6: Test Maintenance Scaling (Linear Maintenance Burden)

**What goes wrong:**
As test count grows from 1,900 → 3,000+ to hit 80% coverage, maintenance burden scales linearly. Every feature update requires updating 10+ tests. Test suite becomes legacy code, team stops maintaining tests, coverage goal abandoned. "Technical debt" becomes "test debt."

**Why it happens:**
- Brittle tests (Pitfall 3) require constant updating after refactoring
- No test helpers: Duplication across test files (same setup/teardown code everywhere)
- No page object pattern: UI tests hardcoded with selectors, break on HTML changes
- No test factories: Manual object creation in every test, breaks when models change
- No golden master testing: Snapshot tests become outdated, ignored

**How to avoid:**
```python
# backend/tests/fixtures/agent_fixtures.py
# GOOD: Centralized test data factories
import factory
from core.models import AgentRegistry

class AgentFactory(factory.Factory):
    class Meta:
        model = AgentRegistry

    id = factory.Faker('uuid4')
    name = factory.Faker('name')
    maturity_level = AgentMaturity.STUDENT

# backend/tests/integration/test_agent_execution.py
# GOOD: Uses factories, not manual construction
def test_agent_executes_task(db_session):
    agent = AgentFactory(maturity_level=AgentMaturity.AUTONOMOUS)
    task = TaskFactory()

    result = agent.execute(task)

    assert result.status == ExecutionStatus.COMPLETED
```

```typescript
// frontend-nextjs/tests/utils/testHelpers.ts
// GOOD: Reusable test helpers
export function renderWithProviders(
  ui: React.ReactElement,
  { agentContext = true, router = true } = {}
) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <AgentContextProvider>
        <Router>{children}</Router>
      </AgentContextProvider>
    );
  }

  return render(ui, { wrapper: Wrapper });
}

// frontend-nextjs/tests/integration/testAgentFlow.test.tsx
// GOOD: Uses helper, no repeated setup
test('agent executes task', async () => {
  renderWithProviders(<AgentExecution agentId="agent-1" />);

  await waitFor(() => {
    expect(screen.getByText('Task completed')).toBeInTheDocument();
  });
});
```

**Warning signs:**
- Same setup code copied across 10+ test files
- Feature update requires updating 20+ tests
- Snapshot tests with 500+ outdated snapshots
- Team comments: "Tests take longer to update than feature code"
- Test files longer than source files (2000+ lines of test code for 500 lines of production code)

**Phase to address:** Phase 099-11 (Test Infrastructure Investment) — Build test utilities, page object patterns, test data factories. Phase 099-12 (Test Debt Reduction) — Refactor duplicated test code, consolidate helpers.

**Platform-specific maintenance patterns:**
- **Backend:** Use `factory-boy` for test data, `pytest fixtures` for setup/teardown
- **Frontend:** Create `renderWithProviders()` helper, use `@testing-library/userEvent` instead of `fireEvent`
- **Mobile:** Share test helpers between iOS/Android, use `@testing-library/react-native` screen queries
- **Desktop:** Reuse frontend test helpers for Tauri WebView, separate Rust test fixtures

---

## Technical Debt Patterns

Shortcuts that seem reasonable during coverage expansion but create long-term maintenance problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Coverage-only tests** (test for coverage, not quality) | Quickly hit 80% metric | False confidence, bugs in production | Never — 80% coverage is meaningless if tests don't catch bugs |
| **Property tests for everything** | Impressive test count, academic rigor | 100x slower execution, hard to debug failures | Use for critical invariants only (state machines, data transformations) |
| **Snapshot testing as main strategy** | One-line test for entire component | Brittle, false positives, review burden | Use only for critical UI regression detection, not primary testing |
| **Mocking external services** | Fast tests, no dependencies | Tests pass but integration fails in production | Only mock truly external services (payment gateways, third-party APIs) |
| **Test data duplication** | Quick to write, no abstraction | Maintenance nightmare when models change | Only for MVP, refactor to factories once test suite grows >50 tests |
| **Skipping slow tests** | Faster CI feedback | Integration bugs slip through | Acceptable if slow tests run nightly and block deployment, not PR merge |
| **Covering trivial code** (getters, constants) | Easy percentage points | False confidence, test bloat | Only if required by strict corporate policy, otherwise focus on complex logic |
| **Testing private methods** | Easy to write, direct access | Brittle, couples tests to implementation | Never — test public APIs only, refactor private methods to public if critical |

---

## Integration Gotchas

Common mistakes when connecting test infrastructure across platforms.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **pytest ↔ Jest coverage aggregation** | Parse Jest JSON incorrectly (different schema than pytest) | Use platform-specific parsers: pytest-cov JSON, Jest `coverage-final.json`, Rust `tarpaulin` JSON |
| **Backend ↔ Frontend contract testing** | Frontend mocks outdated, backend API changed | Use OpenAPI schema as source of truth, generate frontend types from backend spec |
| **Mobile ↔ Desktop shared code** | Tests fail on mobile due to missing Expo modules | Use `Platform.OS` conditional logic in tests, mock platform-specific modules |
| **CI artifact upload/download** | Coverage artifacts too large (>50MB), slow downloads | Compress JSON, upload only changed files, use GitHub Actions cache |
| **Flaky test detection** | Retry failed tests automatically, mask real issues | Detect flaky tests with 3-run verification, quarantine and fix, don't hide |
| **Parallel test execution** | Tests interfere via shared database, filesystem | Use test databases per worker, unique temp directories, transaction rollback |
| **Property test execution time** | `max_examples=1000` runs forever in CI | Use `max_examples=100` for CI, `max_examples=1000` for local development |
| **E2E test environment** | Tests use production database, delete real data | Docker compose test environment, seed data fixtures, isolation |
| **Mobile device tests in CI** | Real device required, CI can't provision | Use Android emulator (fast), iOS simulator (slow), real devices only for release |
| **Desktop OS-specific tests** | Assume macOS availability, Windows tests fail | Matrix strategy: `runs-on: [macos-latest, windows-latest, ubuntu-latest]` |

---

## Performance Traps

Patterns that work at 1,900 tests but fail as coverage expands to 80% across 4 platforms.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Linear test execution** | CI time doubles when test count doubles | Parallel execution (pytest-xdist, Jest workers, cargo parallel) | Breaks at >1,000 tests (current: 1,900 tests, already slow) |
| **No incremental testing** | All 1,900 tests run on 5-line change | Use pytest-testmon, Jest `--onlyChanged`, git diff-based selection | Breaks at >1,000 tests or 10+ min CI time |
| **No test categorization** | E2E tests run on every commit | Mark tests as unit/integration/E2E, run selectively | Breaks at >500 integration tests or 20+ E2E tests |
| **No dependency caching** | 5 min to download node_modules every run | Cache `node_modules`, `~/.gradle/caches`, Python `site-packages` | Breaks immediately (5-10 min wasted per run) |
| **No database fixtures** | Every test rebuilds database from migrations | Use `pytest-fixtureized` or Docker volume cache | Breaks at >100 database-dependent tests |
| **Property tests with 1000+ examples** | Property tests take 5+ minutes | Use `max_examples=100` in CI, `max_examples=1000` locally | Breaks at >20 property tests or Hypothesis settings not configured |
| **No parallel test isolation** | Tests interfere, random failures | Unique database per worker, temp directories, transaction rollback | Breaks with pytest-xdist or Jest parallel workers enabled |
| **Test pollution between files** | Tests pass individually, fail in suite | Proper cleanup in `afterEach`, `teardown`, fixtures | Breaks at >200 tests or complex state management |
| **Large coverage artifacts** | 50MB JSON files, slow upload/download | Compress with gzip, upload only changed files | Breaks with 4+ platforms generating coverage |
| **Screenshot/video artifacts in E2E** | 5GB of screenshots per test run | Upload only on failure, cleanup after 7 days | Breaks with >50 E2E tests or Playwright/Detox tracing enabled |

**Scale thresholds for Atom:**
- Current: 1,900 tests, ~60% overall coverage
- Target: 3,000+ tests (add 1,100 tests), 80% overall coverage
- Backend: 74.6% → 80% (add ~200 tests)
- Frontend: 89.84% → maintain (fix 21 failing tests)
- Mobile: 16.16% → 80% (add ~600 tests)
- Desktop: 0% → 60% (add ~300 tests, realistic target for Rust + WebView)

---

## Platform-Specific Pitfalls

### Frontend (Next.js + React Testing Library)

**Pitfall: Async State Updates Not Awaited**
```typescript
// BAD: Asserts before React state update completes
test('filters agents', () => {
  render(<AgentList />);
  fireEvent.change(screen.getByTestId('search'), { target: { value: 'Agent' } });
  expect(screen.getAllByTestId('agent')).toHaveLength(1); // Fails: UI not updated
});

// GOOD: Waits for React state update
test('filters agents', async () => {
  render(<AgentList />);
  fireEvent.change(screen.getByLabelText('Search agents'), { target: { value: 'Agent' } });
  await waitFor(() => {
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });
});
```

**Detection:** 21/35 frontend tests failing (40% pass rate), tests use `getByTestId()` instead of `getByRole()`, `getByLabelText()`.

**Prevention:** Use Testing Library's async utilities (`waitFor`, `findBy*`), prioritize user-centric queries (`getByRole`), test behavior not implementation.

---

### Backend (Python + pytest + Hypothesis)

**Pitfall: Property Tests Used Inappropriately**
```python
# BAD: Property test for simple CRUD better tested with examples
@given(st.builds(Agent))
def test_create_agent(db_session, agent):
    """Property: Creating agent succeeds"""
    # Trivial, slow, doesn't find bugs
    db_session.add(agent)
    db_session.commit()
    assert agent.id is not None

# GOOD: Example test for CRUD, property test for invariants
def test_create_autonomous_agent(db_session):
    """Example: Autonomous agent can be created"""
    agent = AgentFactory(maturity=AgentMaturity.AUTONOMOUS)
    db_session.add(agent)
    db_session.commit()
    assert agent.id is not None

@given(st.builds(Agent), st.builds(Task))
def test_agent_maturity_gates(agent, task):
    """Property: Maturity gates prevent inappropriate actions"""
    # Tests invariant: maturity enforcement always works
    result = agent.can_perform_action(task)
    assert result.is_allowed == (agent.maturity_level >= task.complexity)
```

**Detection:** 60+ property test files, some testing trivial CRUD operations, test execution time >5 min for property tests alone.

**Prevention:** Use property tests for state machine invariants, data transformations, API contracts. Use example-based tests for CRUD, happy paths, specific business rules.

---

### Mobile (React Native + jest-expo + Detox)

**Pitfall: Device Fragmentation Not Accounted For**
```typescript
// BAD: Assumes iOS behavior, fails on Android
test('requests camera permission', async () => {
  const { status } = await Camera.requestCameraPermissionsAsync();
  expect(status).toBe('granted'); // Fails on Android: user must approve
});

// GOOD: Platform-specific mocking
import * as Platform from 'react-native';

Platform.OS = 'ios'; // Test iOS behavior
jest.mock('expo-camera', () => ({
  requestCameraPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' }) // iOS auto-grants in tests
  ),
}));

test('requests camera permission on iOS', async () => {
  const { status } = await Camera.requestCameraPermissionsAsync();
  expect(status).toBe('granted');
});
```

**Detection:** 16.16% coverage indicates mobile tests incomplete, device-specific tests (camera, location, biometrics) likely missing or mocked incorrectly.

**Prevention:** Use `expo-mock` for Expo modules, write platform-conditional tests, test on real devices (iOS simulator, Android emulator) before merge.

---

### Desktop (Tauri + Rust + WebView)

**Pitfall: OS-Specific Behavior Not Handled**
```rust
// BAD: Assumes Unix paths, fails on Windows
#[test]
fn test_file_path() {
    let path = read_file("/home/user/Documents/file.txt");
    assert_eq!(path, "content");
}

// GOOD: OS-agnostic paths
#[test]
fn test_file_path() {
    let path = read_file("file.txt"); // Use relative paths
    assert!(path.contains("file.txt"));
}
```

```typescript
// BAD: Assumes macOS, fails on Windows
test('Tauri invoke reads file', async () => {
  (invoke as jest.Mock).mockResolvedValue('content');
  const result = await readFile('/Users/test/file.txt');
  expect(result).toBe('content');
});

// GOOD: OS-agnostic path handling
test('Tauri invoke reads file', async () => {
  (invoke as jest.Mock).mockResolvedValue('content');
  const result = await readFile('file.txt'); // Relative path
  expect(result).toBe('content');
});
```

**Detection:** Desktop coverage TBD (no coverage.json exists), likely indicates lack of Tauri testing infrastructure.

**Prevention:** Use `std::path` for cross-platform paths, test on Windows/macOS/Linux via CI matrix, mock Tauri APIs correctly.

---

## "Looks Done But Isn't" Checklist

Things that appear to achieve 80% coverage but are missing critical pieces.

- [ ] **Frontend 89.84% coverage:** Often missing — test quality checks. Verify: Run tests with `--coverage --passWithNoTests` to confirm tests actually pass, check 21 failing tests are fixed, verify no tests are `.skip`-ed.
- [ ] **Backend 74.6% coverage:** Often missing — edge case coverage. Verify: Check missing branches in coverage report, validate error paths tested, confirm async paths covered (20+ missing branches in `agent_governance_service.py`).
- [ ] **Mobile 16.16% coverage:** Often missing — device feature tests. Verify: Camera, location, biometric, notification tests exist, offline sync tests implemented, platform permissions tested.
- [ ] **Desktop TBD coverage:** Often missing — baseline measurement. Verify: Run `cargo test -- --nocapture` to confirm Rust tests execute, check Jest runs Tauri frontend tests, generate coverage with `tarpaulin` or `covector`.
- [ ] **Unified coverage aggregation:** Often missing — per-platform breakdown. Verify: Coverage report shows frontend/backend/mobile/desktop separately, trends tracked over time, regressions flagged.
- [ ] **Parallel CI execution:** Often missing — true parallelization. Verify: Backend/frontend/mobile/desktop jobs run simultaneously (not sequentially), total CI time <15 min, not 40+ min.
- [ ] **Quality gates enforcement:** Often missing — automated blocking. Verify: PRs blocked when coverage drops below threshold, 98% pass rate enforced, flaky tests quarantine and fixed.
- [ ] **Test infrastructure:** Often missing — test utilities and helpers. Verify: Shared test helpers exist, test data factories implemented, page object patterns for E2E tests.
- [ ] **Property test strategy:** Often missing — focused invariants. Verify: Property tests target critical invariants only (not everything), `max_examples` configured for CI (100, not 1000), failures reproducible with minimal examples.
- [ ] **Cross-platform validation:** Often missing — matrix testing. Verify: Mobile tests run on iOS and Android, desktop tests run on Windows/macOS/Linux, frontend tests run on Chrome/Safari/Firefox.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Monolithic workflow (40+ min CI)** | HIGH (2-3 days) | 1. Split single workflow into platform-specific jobs. 2. Add artifact upload/download. 3. Create aggregation job. 4. Verify parallel execution. 5. Update CI documentation. |
| **Coverage regression masked** | MEDIUM (1 day) | 1. Add per-platform breakdown to aggregation script. 2. Implement trend tracking (compare to previous run). 3. Add regression alerts (email/Slack). 4. Update dashboard. 5. Add PR comment with breakdown. |
| **Brittle test patterns** | HIGH (1-2 weeks) | 1. Identify brittle tests (grep `getByTestId`, `expect(mockFn).toHaveBeenCalled`). 2. Refactor to use stable queries (`getByRole`, `getByLabelText`). 3. Remove over-mocking (only mock external dependencies). 4. Add async utilities (`waitFor`, `findBy*`). 5. Update testing style guide. 6. PR review enforcement. |
| **Test execution time explosion** | MEDIUM (3-5 days) | 1. Profile test execution (find slow tests). 2. Mark slow tests with `@pytest.mark.slow` or `test.skip()` temporarily. 3. Categorize tests (unit/integration/E2E). 4. Add parallel execution (`pytest -n auto`, Jest `--maxWorkers=4`). 5. Enable incremental testing (`pytest-testmon`, Jest `--onlyChanged`). 6. Add caching (Docker, node_modules). |
| **Platform-specific failures** | MEDIUM (2-4 days) | 1. Identify failing platform via CI logs. 2. Reproduce failure locally (use Docker for cross-platform testing). 3. Add platform-specific mocks (Expo modules, Tauri APIs). 4. Add matrix strategy to CI (test on all platforms). 5. Standardize test environments (Docker compose). |
| **Test maintenance scaling** | HIGH (1-2 weeks) | 1. Audit test code for duplication. 2. Extract test helpers and utilities. 3. Create page object patterns for E2E tests. 4. Build test data factories (factory-boy, Jest fixtures). 5. Refactor existing tests to use new infrastructure. 6. Add PR review checklist for test quality. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Monolithic test workflow** | Phase 099-01 (Planning), Phase 099-02 (Aggregation) | CI executes 4 platform jobs in parallel, total time <15 min |
| **Coverage without context** | Phase 099-03 (Quality Gates), Phase 099-04 (Dashboard) | Coverage report shows per-platform breakdown, trends, regressions flagged |
| **Brittle test patterns** | Phase 099-05 (Standardization), Phase 099-06 (Refactoring) | Frontend test pass rate 40% → 98%+, test style guide followed in PRs |
| **Execution time explosion** | Phase 099-07 (Performance), Phase 099-08 (Caching) | pytest <5 min, Jest <2 min, jest-expo <3 min, cargo test <5 min |
| **Platform-specific failures** | Phase 099-09 (Cross-Platform), Phase 099-10 (Environment) | Matrix tests pass on iOS/Android/Win/macOS/Linux |
| **Maintenance scaling** | Phase 099-11 (Infrastructure), Phase 099-12 (Debt Reduction) | Test helper usage >80%, duplication <10%, test debt tracked and reducing |

**Phase sequencing rationale:**
1. **099-01/099-02** (Planning & Aggregation): Foundation for parallel execution, prevents monolithic workflow
2. **099-03/099-04** (Quality Gates & Dashboard): Visibility into coverage, prevents regression masking
3. **099-05/099-06** (Standardization & Refactoring): Fix existing brittleness, prevents test debt accumulation
4. **099-07/099-08** (Performance & Caching): Optimize execution time, prevents CI bottlenecks
5. **099-09/099-10** (Cross-Platform & Environment): Validate platform parity, prevents OS-specific failures
6. **099-11/099-12** (Infrastructure & Debt Reduction): Invest in maintainability, prevents scaling problems

---

## Sources

### High Confidence (Official Documentation & Verified Resources)

- **[Smashing Magazine: Frontend Testing Pitfalls](https://www.smashingmagazine.com/2021/07/frontend-testing-pitfalls/)** — Six common frontend testing pitfalls with solutions (HIGH confidence: official testing patterns)
- **[pytest Documentation: Test Configuration](https://docs.pytest.org/)** — Test discovery, fixtures, marks, parallel execution with pytest-xdist (HIGH confidence: official docs)
- **[React Testing Library: Guidelines](https://testing-library.com/docs/react-testing-library/intro/)** — Async utilities, query priority, anti-patterns (HIGH confidence: official docs)
- **[Jest Documentation: Parallel Execution](https://jestjs.io/docs/configuration#maxworkers-numberstring)** — Worker configuration, test caching, performance optimization (HIGH confidence: official docs)
- **[GitHub Actions: Workflow Optimization](https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow)** — Parallel jobs, matrix strategy, artifact management (HIGH confidence: official docs)
- **[Detox: Grey-Box E2E Testing](https://wix.github.io/Detox/)** — React Native testing patterns, device-specific testing (HIGH confidence: official docs)
- **[Tauri Testing Guide](https://tauri.app/v2/guides/testing/)** — Desktop testing patterns, cross-platform considerations (HIGH confidence: official docs)
- **[Hypothesis: Test Strategies](https://hypothesis.readthedocs.io/)** — Property-based testing best practices, when to use vs. example-based tests (HIGH confidence: official docs)
- **[fast-check: Property-Based Testing](https://fast-check.dev/)** — TypeScript/JavaScript property testing, invariant testing (HIGH confidence: official docs)
- **[Atom Existing Research: SUMMARY.md](/.planning/research/SUMMARY.md)** — Platform-first testing architecture, existing infrastructure analysis (HIGH confidence: verified research)
- **[Atom Existing Research: ARCHITECTURE.md](/.planning/research/ARCHITECTURE.md)** — Multi-platform testing architecture, component boundaries (HIGH confidence: verified research)

### Medium Confidence (Industry Analysis & Codebase Review)

- **[CSDN: 80%+ Unit Test Coverage Guide](https://m.blog.csdn.net/gitblog_00236/article/details/153855060)** — October 2025 frontend coverage expansion strategies (MEDIUM confidence: recent but Chinese source, translated)
- **[CSDN: CI/CD Pipeline Optimization](https://blog.csdn.net/ProceShoal/article/details/153415314)** — 2025 CI bottleneck analysis, parallel testing strategies (MEDIUM confidence: specific examples, real-world results)
- **[Tencent Cloud: Mobile Testing Strategy](https://cloud.tencent.com/developer/article/1838172)** — Device fragmentation challenges, simulator vs. real device testing (MEDIUM confidence: mobile-specific, practical examples)
- **[Atom Codebase: Backend Coverage](/backend/tests/coverage_reports/metrics/coverage.json)** — 74.6% coverage, 22 missing branches in `agent_governance_service.py` (MEDIUM confidence: direct measurement, verified)
- **[Atom Codebase: Frontend Tests](/frontend-nextjs/tests/)** — 35 tests, 14 passing (40% pass rate), brittleness indicators (MEDIUM confidence: direct observation)
- **[Hacker News: AI Code Review Discussion](https://news.ycombinator.com/item?id=46766961)** — January 2026 discussion on testing implementation details vs. behavior (MEDIUM confidence: community consensus, expert opinions)
- **[Microsoft Azure: Parallel Testing](https://learn.microsoft.com/zh-cn/azure/devops/pipelines/test/parallel-testing-any-test-runner)** — Test slicing strategies, parallel job configuration (MEDIUM confidence: vendor docs, practical examples)
- **[PHPUnit Testing Anti-patterns](https://m.blog.csdn.net/gitblog_00945/article/details/154894056)** — November 2025 analysis of brittle tests, over-mocking (MEDIUM confidence: practical examples, translated)
- **[Don't Over-Mock Principle](https://m.blog.csdn.net/oscar999/article/details/147103108)** — April 2025 discussion of mocking anti-patterns (MEDIUM confidence: good examples, translated)

### Low Confidence (WebSearch Only — Needs Validation)

- **[CSDN: Python Mock Library Guide](https://www.geeksforgeeks.org/python/python-mock-library/)** — Mocking best practices (LOW confidence: general tutorial, not specific to multi-platform)
- **[CSDN: Code Coverage Issues](https://blog.csdn.net/weixin_51960949/article/details/150218934)** — Coverage measurement challenges (LOW confidence: general discussion, lacks specific multi-platform context)
- **[BrowserStack: Device Fragmentation](https://www.browserstack.com/guide/device-fragmentation)** — Mobile testing challenges (LOW confidence: vendor content, marketing mixed with technical content)
- **[Kotlin Testing Pitfalls](https://m.blog.csdn.net/CompiShoal/article/details/153194276)** — October 2025 mock object abuse analysis (LOW confidence: Kotlin-specific, apply patterns carefully to TypeScript/Python)

### Gaps Identified

- **FastCheck adoption patterns:** Low production adoption, few real-world examples for React state management — May need phase-specific research during implementation
- **Tauri testing best practices:** Less documented than web/mobile, desktop testing patterns immature — Mitigation: Start with cargo test for Rust, defer complex WebView integration
- **Cross-platform test sharing:** Limited patterns for shared test suites across web/mobile/desktop — Mitigation: Start with platform-specific tests, consolidate in Phase 099-09
- **CI/CD cost optimization:** Parallel execution increases CI minutes usage — Mitigation: Reserve full matrix for nightly builds, PRs use subset

---

*Pitfalls research for: Cross-Platform 80% Coverage Achievement*
*Researched: March 3, 2026*
*Focus: Multi-platform testing pitfalls specific to 80% coverage expansion across frontend, backend, mobile, desktop*

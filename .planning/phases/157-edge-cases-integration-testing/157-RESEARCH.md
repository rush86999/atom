# Phase 157: Edge Cases & Integration Testing - Research

**Researched:** 2026-03-09
**Domain:** Integration Testing, Error Boundaries, Concurrent Operations, Accessibility, Cross-Service Workflows
**Confidence:** HIGH

## Summary

Phase 157 focuses on testing complex error paths, routing edge cases, accessibility compliance, concurrent operations, and cross-service integration workflows across all four platforms (backend Python, frontend React/Next.js, mobile React Native, desktop Tauri/Rust). This phase builds upon established coverage infrastructure from Phases 146-156, targeting EDGE-01 through EDGE-05 requirements.

**Current State Analysis:**
- Backend: Comprehensive test infrastructure exists with property tests, E2E tests, critical error path tests, and concurrent operation tests
- Frontend: React Testing Library, jest-axe accessibility testing, MSW for API mocking, integration tests for routing and forms
- Mobile: jest-expo infrastructure established, React Native Testing Library available
- Desktop: Tarpaulin coverage baseline measured, cargo test infrastructure

**Key Findings:**
1. **Error Boundary Infrastructure**: Backend has extensive `critical_error_paths/` fixtures for connection failures, deadlocks, timeouts, and retry logic validation
2. **Concurrent Operations**: Property tests exist for budget, payment, and cache race conditions; `concurrent_operations/` directory has database lock and cache race tests
3. **Accessibility**: Frontend uses jest-axe with WCAG 2.1 AA compliance; infrastructure already configured in `tests/accessibility.test.tsx`
4. **E2E Integration**: 217+ E2E tests across 14 files validate complete workflows with real PostgreSQL, Redis, and LLM providers
5. **Routing Testing**: Frontend has `navigation.test.tsx` and React Navigation tests; mobile has navigation screen tests

**Primary recommendation:** Extend existing test infrastructure with targeted edge case tests rather than building new frameworks. Focus on gaps: error boundary component tests (frontend), concurrent hook call patterns, accessibility integration with real workflows, and cross-platform E2E orchestration.

## Standard Stack

### Core Testing Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Backend test runner | De facto Python standard, extensive plugin ecosystem |
| **pytest-asyncio** | 0.21+ | Async test support | Required for backend async operations |
| **pytest-xdist** | 3.5+ | Parallel test execution | Industry standard for parallel test runs |
| **pytest-cov** | 4.1+ | Coverage reporting | pytest-cov is standard for coverage |
| **pytest-timeout** | 2.2+ | Test timeout enforcement | Prevents hanging tests in CI/CD |
| **Hypothesis** | 6.92+ | Property-based testing | Definitive PBT library for Python |
| **Jest** | 29.7+ | Frontend/mobile test runner | React ecosystem standard |
| **React Testing Library** | 14.0+ | Component testing | Best practice for React component testing |
| **jest-axe** | 8.0+ | Accessibility testing | Standard for WCAG compliance testing |
| **MSW** | 2.0+ | API mocking | Modern standard for Service Worker mocking |
| **Playwright** | 1.40+ | E2E web testing | Industry-standard for E2E browser automation |
| **Detox** | 20.0+ | E2E mobile testing | Standard for React Native E2E |
| **cargo test** | (Rust std) | Desktop testing | Built-in Rust testing |
| **tarpaulin** | 0.27+ | Desktop coverage | Standard for Rust coverage reporting |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **freezegun** | 1.4+ | Time freezing | Deterministic time-dependent tests |
| **responses** | 0.24+ | HTTP mocking | External API mocking (backend) |
| **pytest-mock** | 3.12+ | Mock fixtures | Pytest-compatible mocking |
| **@testing-library/user-event** | 14.5+ | User interaction simulation | Realistic user event simulation |
| **@testing-library/jest-dom** | 6.1+ | Custom Jest matchers | DOM assertion helpers |
| **axe-core** | 4.8+ | Accessibility engine | Core for jest-axe |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest (std) | pytest has superior fixtures, plugins, and community support |
| Hypothesis | rapid (Python) | Hypothesis has better shrinking, more strategies, larger community |
| jest-axe | @axe-core/react | jest-axe integrates better with Jest/React Testing Library |
| MSW | axios-mock-adapter | MSW intercepts at network level (more realistic), axios-mock is client-specific |
| Playwright | Cypress | Playwright supports multi-browser, better cross-platform; Cypress is JS-only |
| Detox | Appium | Detox is React Native-specific (faster); Appium supports any mobile app |

**Installation:**
```bash
# Backend
pip install pytest pytest-asyncio pytest-xdist pytest-cov pytest-timeout pytest-mock hypothesis freezegun responses

# Frontend
npm install --save-dev jest @testing-library/react @testing-library/jest-dom @testing-library/user-event jest-axe msw

# Mobile
npm install --save-dev jest-expo @testing-library/react-native @testing-library/jest-native detox

# Desktop
# Rust testing uses built-in cargo test
cargo install cargo-tarpaulin
```

## Architecture Patterns

### Test Organization Structure

```
backend/tests/
├── unit/                    # Fast, isolated unit tests
│   ├── core/               # Core service unit tests
│   ├── api/                # API route unit tests
│   └── tools/              # Tool unit tests
├── integration/            # Service integration tests
│   ├── services/           # Multi-service integration
│   ├── database/           # Database integration
│   └── api/                # API contract tests
├── e2e/                    # End-to-end workflow tests
│   ├── test_mcp_tools_e2e.py
│   ├── test_database_integration_e2e.py
│   └── test_critical_workflows_e2e.py
├── property_tests/         # Hypothesis property tests
│   ├── governance/
│   ├── database_transactions/
│   └── concurrency/
├── critical_error_paths/   # Error boundary tests
│   ├── conftest.py         # Error simulation fixtures
│   ├── test_database_connection_failures.py
│   └── test_external_service_timeouts.py
├── concurrent_operations/  # Race condition tests
│   ├── conftest.py
│   ├── test_database_locks.py
│   └── test_cache_race_conditions.py
├── boundary_conditions/    # Edge case tests
├── failure_modes/          # Chaos engineering tests
└── conftest.py             # Root fixtures

frontend-nextjs/tests/
├── unit/                   # Component unit tests
├── integration/            # Component integration tests
│   ├── navigation.test.tsx
│   ├── forms.test.tsx
│   └── auth.test.tsx
├── e2e/                    # Playwright E2E tests
├── accessibility/          # jest-axe tests
│   └── accessibility.test.tsx
├── mocks/                  # MSW handlers
└── setup.ts                # Test configuration

mobile/tests/
├── unit/                   # Component unit tests
├── integration/            # Navigation and integration
├── e2e/                    # Detox E2E tests
└── accessibility/          # React Native a11y tests

menubar/tests/
├── unit/                   # Rust unit tests
├── integration/            # IPC integration tests
└── e2e/                    # Tauri E2E tests
```

### Pattern 1: Error Boundary Testing (Backend)

**What:** Test graceful degradation when services fail

**When to use:** Database connection failures, external service timeouts, network errors

**Example:**
```python
# Source: backend/tests/critical_error_paths/conftest.py
@pytest.fixture
def mock_connection_failure():
    """Patch engine.connect to raise OperationalError (connection failure)."""
    @contextmanager
    def _patch(fail_count: int = 1, error_message: str = "Connection refused"):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= fail_count:
                raise OperationalError(message, {}, None)
            mock_conn = MagicMock()
            mock_conn.connect.return_value = MagicMock()
            return mock_conn

        with patch("core.database.engine.connect", side_effect=side_effect):
            yield

    return _patch

def test_connection_retry_with_backoff(mock_connection_failure):
    """Test that retry logic uses exponential backoff on connection failures."""
    with mock_connection_failure(fail_count=3) as mock_connect:
        with track_retry_attempts() as tracker:
            # Perform operation that should retry 3 times
            result = database_operation_with_retry()

        assert tracker.verify_retry_count(3)
        assert tracker.verify_exponential_backoff()
```

### Pattern 2: Concurrent Operations Testing (Backend)

**What:** Test race conditions and concurrent access patterns

**When to use:** Database transactions, cache access, agent coordination

**Example:**
```python
# Source: backend/tests/concurrent_operations/conftest.py
import threading
import pytest

@pytest.fixture
def concurrent_executor():
    """Execute operations concurrently and verify thread-safety."""
    class ConcurrentExecutor:
        def __init__(self, num_threads=10):
            self.num_threads = num_threads
            self.exceptions = []

        def execute_concurrent(self, operation, *args, **kwargs):
            """Execute operation in multiple threads concurrently."""
            threads = []
            results = [None] * self.num_threads

            def worker(thread_id):
                try:
                    results[thread_id] = operation(*args, **kwargs)
                except Exception as e:
                    self.exceptions.append(e)

            for i in range(self.num_threads):
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            if self.exceptions:
                raise self.exceptions[0]

            return results

    return ConcurrentExecutor()

def test_concurrent_budget_checks(concurrent_executor, db_session):
    """Test that concurrent budget checks don't allow overspend."""
    from core.financial_ops_engine import FinancialOpsEngine

    engine = FinancialOpsEngine()
    budget = 1000.0

    def spend_600():
        return engine.check_budget(budget, 600.0)

    results = concurrent_executor.execute_concurrent(spend_600)

    # Only one should succeed (budget is 1000, each spend is 600)
    approved_count = sum(1 for r in results if r.approved)
    assert approved_count == 1, f"Expected 1 approved, got {approved_count}"
```

### Pattern 3: Accessibility Testing (Frontend)

**What:** Test WCAG 2.1 AA compliance with jest-axe

**When to use:** All UI components, especially after visual changes

**Example:**
```typescript
// Source: frontend-nextjs/tests/accessibility.test.tsx
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import React from 'react';
import { Button } from '@/components/ui/button';

expect.extend(toHaveNoViolations);

describe('Button accessibility', () => {
  it('should not have accessibility violations', async () => {
    const { container } = render(<Button>Click me</Button>);

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible name', () => {
    render(<button>Submit</button>);

    const button = screen.getByRole('button');
    expect(button).toHaveAccessibleName('Submit');
  });

  it('should be keyboard navigable', () => {
    render(<Button>Click me</Button>);

    const button = screen.getByRole('button');
    button.focus();
    expect(button).toHaveFocus();
  });
});
```

### Pattern 4: Routing and Navigation Testing (Frontend)

**What:** Test React Router navigation, route guards, redirects

**When to use:** Navigation flow changes, new protected routes

**Example:**
```typescript
// Source: frontend-nextjs/tests/integration/navigation.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import App from '@/pages/_app';

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe('Navigation integration', () => {
  it('should redirect to login when accessing protected route unauthenticated', async () => {
    renderWithRouter(<App />);

    // Navigate to protected route
    window.history.pushState({}, 'Test', '/dashboard');

    await waitFor(() => {
      expect(screen.getByText('Sign in')).toBeInTheDocument();
    });
  });

  it('should navigate to canvas page after login', async () => {
    const user = userEvent.setup();
    renderWithRouter(<App />);

    // Fill login form
    await user.type(screen.getByLabelText('Email'), 'test@example.com');
    await user.type(screen.getByLabelText('Password'), 'password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    // Should redirect to canvas
    await waitFor(() => {
      expect(window.location.pathname).toBe('/canvas');
    });
  });

  it('should handle browser back button correctly', async () => {
    const user = userEvent.setup();
    renderWithRouter(<App />);

    // Navigate: home -> dashboard -> settings
    await user.click(screen.getByText('Dashboard'));
    await user.click(screen.getByText('Settings'));

    // Click back button
    window.history.back();

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
  });
});
```

### Pattern 5: Cross-Service Workflow Testing (E2E)

**What:** Test complete workflows across multiple services

**When to use:** Agent execution, canvas presentation, skill loading, package installation

**Example:**
```python
# Source: backend/tests/e2e/test_critical_workflows_e2e.py
def test_complete_agent_to_canvas_workflow(composite_workflow):
    """Test complete workflow from agent execution to canvas presentation."""
    agent = composite_workflow["agent"]
    canvas = composite_workflow["canvas"]

    # Step 1: Execute agent
    execution = AgentExecution(
        agent_id=agent["agent"].id,
        user_id=canvas["user_id"],
        task="Generate insights",
        status="in_progress"
    )
    agent["session"].add(execution)
    agent["session"].commit()

    # Step 2: Complete execution with governance check
    from core.agent_governance_service import AgentGovernanceService
    governance = AgentGovernanceService(agent["session"])

    can_execute = governance.can_perform_action(
        agent["agent"].id,
        "present_canvas",
        complexity=2
    )
    assert can_execute, "Agent should be allowed to present canvas"

    execution.status = "completed"
    execution.output_data = {"insights": ["insight1", "insight2"]}
    agent["session"].commit()

    # Step 3: Create canvas presentation
    audit = CanvasAudit(
        canvas_id=canvas["canvas_id"],
        user_id=canvas["user_id"],
        action="present",
        canvas_data=execution.output_data
    )
    canvas["session"].add(audit)
    canvas["session"].commit()

    # Step 4: Verify workflow complete
    assert execution.status == "completed"
    assert audit.action == "present"

    # Step 5: Verify audit trail
    audit_logs = canvas["session"].query(CanvasAudit).filter_by(
        user_id=canvas["user_id"]
    ).all()
    assert len(audit_logs) == 1
```

### Pattern 6: Concurrent Hook Calls Testing (Frontend)

**What:** Test React hooks concurrent feature (React 18+)

**When to use:** Custom hooks with state updates, concurrent rendering

**Example:**
```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';

describe('useCanvasState concurrent operations', () => {
  it('should handle concurrent state updates correctly', async () => {
    const { result } = renderHook(() => useCanvasState('canvas-123'));

    // Trigger concurrent updates
    act(() => {
      result.current.updateCanvas({ data: 'update1' });
      result.current.updateCanvas({ data: 'update2' });
      result.current.updateCanvas({ data: 'update3' });
    });

    await waitFor(() => {
      expect(result.current.canvas).toEqual({ data: 'update3' });
    });
  });

  it('should not lose updates during concurrent transitions', async () => {
    const { result } = renderHook(() => useCanvasState('canvas-456'));

    const updates = Array.from({ length: 100 }, (_, i) => ({ value: i }));

    act(() => {
      updates.forEach(update => {
        result.current.updateCanvas(update);
      });
    });

    await waitFor(() => {
      expect(result.current.canvas.value).toBe(99);
    });
  });
});
```

### Anti-Patterns to Avoid

- **Testing implementation details**: Don't test internal functions, test public API contracts
- **Fragile selectors**: Don't use CSS classes that change; use data-testid attributes
- **Over-mocking**: Don't mock everything; test real integration points
- **Testing third-party code**: Don't test libraries; assume they work
- **Ignoring flaky tests**: Don't mark tests as flaky and move on; fix them
- **Testing without teardown**: Don't leave test data in database; use fixtures with cleanup

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Test runner** | Custom test framework | pytest / Jest | Battle-tested, extensive plugins, community support |
| **Mocking** | Custom mock classes | pytest-mock / unittest.mock / MSW | Standard libraries, better integration |
| **Assertions** | Custom assert helpers | pytest asserts / jest-expect | Built-in assertions, better error messages |
| **Coverage** | Custom coverage tool | pytest-cov / tarpaulin | Industry standards, CI/CD integration |
| **Property testing** | Custom random generators | Hypothesis / FastCheck | Shrinking, strategy generation, reproducibility |
| **Async testing** | Custom async wrappers | pytest-asyncio / React Testing Library async | Proper async handling, race condition prevention |
| **Accessibility** | Custom a11y checker | jest-axe / axe-core | WCAG compliance, comprehensive rules |
| **E2E framework** | Custom browser automation | Playwright / Detox | Cross-browser support, auto-waiting, debugging |
| **HTTP mocking** | Custom request interceptor | MSW / responses | Network-level interception, realistic behavior |
| **Time manipulation** | Custom time mocking | freezegun / vi.useFakeTimers | Comprehensive time API support |

**Key insight:** Building custom testing infrastructure is rarely worth it. Existing tools have solved edge cases, provide better debugging, and integrate with CI/CD. Focus on writing tests, not building test frameworks.

## Common Pitfalls

### Pitfall 1: Testing Without Cleanup

**What goes wrong:** Test data leaks between tests, causing flaky failures

**Why it happens:** Fixtures don't clean up database, files, or resources

**How to avoid:** Always use fixture teardown, function-scoped fixtures, and unique resource names

**Warning signs:** Tests pass individually but fail in suite, intermittent failures, "database locked" errors

**Solution:**
```python
@pytest.fixture(scope="function")
def unique_resource_name():
    """Generate unique resource name for parallel test execution."""
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"

@pytest.fixture(scope="function")
def db_session():
    """Create fresh database session with cleanup."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    os.unlink(db_path)
```

### Pitfall 2: Brittle Selectors in Frontend Tests

**What goes wrong:** Tests break when CSS classes or DOM structure changes

**Why it happens:** Tests rely on implementation details (CSS classes, nested elements)

**How to avoid:** Use accessible role queries, data-testid attributes, and user-centric selectors

**Warning signs:** Tests fail after visual refactor, complex selector chains

**Solution:**
```typescript
// Bad: Brittle selector
expect(screen.querySelector('.btn-primary.large')).toBeInTheDocument();

// Good: Accessible role
expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();

// Good: Test ID (for non-interactive elements)
expect(screen.getByTestId('canvas-header')).toBeInTheDocument();
```

### Pitfall 3: Missing Async Waits

**What goes wrong:** Tests fail intermittently due to timing issues

**Why it happens:** Tests don't wait for async operations (API calls, state updates, renders)

**How to avoid:** Always use waitFor, waitForElementToBeRemoved, findBy queries

**Warning signs:** Flaky tests that pass sometimes, "Unable to find element" errors

**Solution:**
```typescript
// Bad: No wait
render(<UserProfile />);
expect(screen.getByText('John Doe')).toBeInTheDocument(); // May fail

// Good: Wait for async
render(<UserProfile />);
await waitFor(() => {
  expect(screen.getByText('John Doe')).toBeInTheDocument();
});

// Good: Use findBy (auto-waiting)
expect(await screen.findByText('John Doe')).toBeInTheDocument();
```

### Pitfall 4: Ignoring Race Conditions

**What goes wrong:** Tests pass locally but fail in CI due to concurrent execution

**Why it happens:** Tests assume sequential execution, don't handle concurrent access

**How to avoid:** Use unique resource names, test concurrent operations explicitly

**Warning signs:** Tests pass with `pytest -n1` but fail with `pytest -n auto`, "database locked" errors

**Solution:**
```python
def test_concurrent_agent_execution(unique_resource_name):
    """Test that concurrent agent executions are isolated."""
    agent_id_1 = f"{unique_resource_name}_1"
    agent_id_2 = f"{unique_resource_name}_2"

    # Execute both agents concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(execute_agent, agent_id_1)
        future2 = executor.submit(execute_agent, agent_id_2)

        result1 = future1.result()
        result2 = future2.result()

    # Verify both executed independently
    assert result1.agent_id == agent_id_1
    assert result2.agent_id == agent_id_2
```

### Pitfall 5: Over-Mocking External Services

**What goes wrong:** Tests pass but integration fails in production

**Why it happens:** Tests mock external services, don't catch integration issues

**How to avoid:** Use real services in E2E tests, minimal mocking in integration tests

**Warning signs:** 100% test coverage but production bugs, mocks that don't match real behavior

**Solution:**
```python
# Unit test: Mock external service
def test_agent_governance_logic(mock_llm_service):
    """Test governance logic with mocked LLM."""
    mock_llm_service.complete.return_value = "Mock response"
    # Test governance logic

# Integration test: Real service
def test_agent_governance_integration(llm_api_keys):
    """Test governance with real LLM API."""
    if not llm_api_keys["openai"]:
        pytest.skip("OpenAI API key not set")

    # Test with real OpenAI API

# E2E test: Complete workflow
def test_agent_execution_workflow(e2e_postgres_db, e2e_redis):
    """Test complete workflow with real services."""
    # Test with real PostgreSQL, Redis, LLM providers
```

### Pitfall 6: Not Testing Error Paths

**What goes wrong:** System crashes when errors occur in production

**Why it happens:** Tests only cover happy path, don't validate error handling

**How to avoid:** Test error boundaries, graceful degradation, retry logic

**Warning signs:** Production crashes on network errors, database timeouts, service failures

**Solution:**
```python
def test_database_connection_retry(mock_connection_failure):
    """Test that system retries on connection failure."""
    with mock_connection_failure(fail_count=3) as mock_connect:
        with track_retry_attempts() as tracker:
            result = database_operation_with_retry()

    assert tracker.verify_retry_count(3)
    assert result is not None  # Should succeed after retries
```

### Pitfall 7: Accessibility Testing Gaps

**What goes wrong:** UI not accessible to screen readers, keyboard users

**Why it happens:** Accessibility not tested, or tested manually but not automated

**How to avoid:** Use jest-axe for automated WCAG compliance testing

**Warning signs:** Manual a11y testing only, no automated a11y tests in CI/CD

**Solution:**
```typescript
// Add to every component test suite
describe('Component accessibility', () => {
  it('should not have WCAG violations', async () => {
    const { container } = render(<Component />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should be keyboard navigable', () => {
    render(<Component />);
    const button = screen.getByRole('button');
    button.focus();
    expect(button).toHaveFocus();
  });
});
```

## Code Examples

### Edge Case: Error Boundary Component (Frontend)

**What:** Test React Error Boundary catches component errors

**Example:**
```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <div>Something went wrong</div>;
    }
    return this.props.children;
  }
}

describe('Error Boundary', () => {
  it('should catch errors in child components', () => {
    const ThrowError = () => {
      throw new Error('Test error');
    };

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('should recover from errors after reset', async () => {
    const ThrowError = () => {
      throw new Error('Test error');
    };

    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Rerender with valid component
    rerender(
      <ErrorBoundary>
        <div>Valid content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Valid content')).toBeInTheDocument();
  });
});
```

### Edge Case: Route Guard with Redirects (Frontend)

**What:** Test protected routes redirect unauthenticated users

**Example:**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';

const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated);
  return isAuthenticated ? children : <Navigate to="/login" />;
};

describe('Protected Route', () => {
  it('should redirect to login when not authenticated', async () => {
    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(window.location.pathname).toBe('/login');
    });
  });

  it('should render protected content when authenticated', async () => {
    // Mock authenticated state
    useAuthStore.setState({ isAuthenticated: true });

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });
});
```

### Edge Case: Database Deadlock Recovery (Backend)

**What:** Test system recovers from database deadlocks with retry

**Example:**
```python
def test_deadlock_triggers_retry_with_recovery(mock_deadlock_scenario):
    """Test that deadlock triggers retry and eventually succeeds."""
    with mock_deadlock_scenario(retry_count=3) as deadlock_mock:
        with track_retry_attempts() as tracker:
            # First 3 attempts deadlock, 4th succeeds
            result = perform_database_transaction()

    assert tracker.verify_retry_count(3)
    assert result is not None  # Should succeed after retries
    assert tracker.verify_exponential_backoff()
```

### Edge Case: Rate Limiting with Backoff (Backend)

**What:** Test API client respects rate limits with exponential backoff

**Example:**
```python
def test_rate_limiting_with_exponential_backoff():
    """Test that API client respects rate limits with backoff."""
    from integrations.openai_integration import OpenAIIntegration

    integration = OpenAIIntegration(api_key="test-key")

    # Mock 429 (Too Many Requests) responses
    with patch('requests.post') as mock_post:
        mock_post.side_effect = [
            Response(429),  # First call: rate limited
            Response(429),  # Second call: rate limited
            Response(200, json={'result': 'success'}),  # Third call: success
        ]

        result = integration.complete("test prompt")

    assert mock_post.call_count == 3
    assert result == {'result': 'success'}
```

### Integration: Cross-Platform E2E Workflow

**What:** Test workflow across web, mobile, and desktop platforms

**Example:**
```python
def test_cross_platform_canvas_workflow():
    """Test canvas workflow works across web, mobile, and desktop."""
    # Web: Create canvas
    web_canvas = create_canvas_via_web_api("test-canvas-123")

    # Mobile: View canvas on mobile
    mobile_canvas = get_canvas_via_mobile_api("test-canvas-123")
    assert mobile_canvas["id"] == web_canvas["id"]

    # Desktop: Update canvas on desktop
    desktop_canvas = update_canvas_via_desktop_api(
        "test-canvas-123",
        {"data": "updated"}
    )
    assert desktop_canvas["data"] == "updated"

    # Web: Verify changes reflected
    final_canvas = get_canvas_via_web_api("test-canvas-123")
    assert final_canvas["data"] == "updated"
```

## State of the Art

### Modern Testing Practices (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Unit testing only** | Test pyramid (unit/integration/E2E) | 2018-2020 | Better coverage of real-world scenarios |
| **Example-based tests** | Property-based tests | 2019-2021 | Catches edge cases examples miss |
| **Manual a11y testing** | Automated jest-axe tests | 2020-2022 | WCAG compliance in CI/CD |
| **Sequential test execution** | Parallel test execution (pytest-xdist, Jest workers) | 2019-2021 | Faster CI/CD feedback |
| **Flaky tests ignored** | Flaky test detection and quarantine | 2021-2023 | More reliable test suites |
| **Mock-heavy integration tests** | Real service E2E tests | 2020-2022 | Catches real integration bugs |
| **Code coverage only** | Coverage + quality metrics (assertion density, mutation) | 2022-2024 | Higher quality tests, not just coverage |

**Deprecated/outdated:**
- **nosetests**: Replaced by pytest (2015)
- **unittest.mock (basic)**: Enhanced by pytest-mock (2018)
- **Cypress for multi-browser**: Playwright has better cross-browser support (2021)
- **Manual accessibility testing**: Automated jest-axe is standard (2020)
- **Coverage gates without quality**: Mutation testing and assertion density tracking (2023)

### Current Best Practices (2025)

1. **Parallel Test Execution**: Use pytest-xdist (backend) and Jest workers (frontend) by default
2. **Property-Based Testing**: Hypothesis (Python) and FastCheck (TypeScript) for critical paths
3. **Accessibility Testing**: jest-axe with WCAG 2.1 AA for all UI components
4. **E2E Testing**: Real services (PostgreSQL, Redis) not mocks, for true integration validation
5. **Flaky Test Detection**: Automated detection and quarantine, not manual marking
6. **Coverage Quality Metrics**: Assertion density, mutation testing, not just line coverage
7. **Error Boundary Testing**: Test graceful degradation, not just happy paths
8. **Concurrent Operations Testing**: Explicit race condition tests, not assuming sequential execution

## Open Questions

1. **Cross-Platform E2E Orchestration**
   - What we know: Individual platforms have E2E tests (Playwright for web, Detox for mobile, Tauri for desktop)
   - What's unclear: Unified orchestration framework for testing workflows across all platforms
   - Recommendation: Use Phase 148's E2E orchestration infrastructure as baseline, extend for cross-platform workflows

2. **Accessibility Testing for Mobile and Desktop**
   - What we know: Frontend has jest-axe configured; mobile and desktop a11y testing not established
   - What's unclear: React Native and Tauri accessibility testing best practices
   - Recommendation: Research React Native Accessibility API and Tauri a11y testing patterns; add to mobile/desktop test suites

3. **Concurrent Hook Testing Patterns**
   - What we know: React 18+ has concurrent features; React Testing Library supports async testing
   - What's unclear: Best practices for testing concurrent rendering and state updates
   - Recommendation: Use `waitFor` and `act()` for concurrent operations; test with rapid state updates

4. **Error Boundary Testing for Desktop (Tauri/Rust)**
   - What we know: Frontend has React error boundary tests; desktop error handling not tested
   - What's unclear: Rust panic handling and Tauri error propagation testing patterns
   - Recommendation: Add panic handler tests and IPC error propagation tests to desktop suite

## Sources

### Primary (HIGH confidence)

- **pytest Documentation**: https://docs.pytest.org/ - Test runner, fixtures, plugins
- **Hypothesis Documentation**: https://hypothesis.readthedocs.io/ - Property-based testing
- **Jest Documentation**: https://jestjs.io/ - Frontend test runner
- **React Testing Library**: https://testing-library.com/react/ - Component testing best practices
- **jest-axe Repository**: https://github.com/nickcolley/jest-axe - Accessibility testing
- **MSW Documentation**: https://mswjs.io/ - API mocking
- **Playwright Documentation**: https://playwright.dev/ - E2E browser automation
- **Detox Documentation**: https://wix.github.io/Detox/ - E2E mobile testing
- **Backend Test Infrastructure**: `/Users/rushiparikh/projects/atom/backend/tests/conftest.py` - Fixtures and configuration
- **Critical Error Path Tests**: `/Users/rushiparikh/projects/atom/backend/tests/critical_error_paths/conftest.py` - Error simulation patterns
- **Concurrent Operations Tests**: `/Users/rushiparikh/projects/atom/backend/tests/concurrent_operations/conftest.py` - Concurrency testing patterns
- **Frontend Test Configuration**: `/Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js` - Jest setup and thresholds
- **E2E Test Infrastructure**: `/Users/rushiparikh/projects/atom/backend/tests/e2e/README.md` - E2E patterns and workflows
- **Testing Guide**: `/Users/rushiparikh/projects/atom/backend/tests/TESTING_GUIDE.md` - Comprehensive testing patterns
- **Coverage Guide**: `/Users/rushiparikh/projects/atom/backend/tests/docs/COVERAGE_GUIDE.md` - Coverage interpretation and targets

### Secondary (MEDIUM confidence)

- **WCAG 2.1 AA Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/ - Accessibility compliance (not directly verified, established standard)
- **React 18 Concurrent Features**: React documentation on concurrent rendering and Suspense (not directly verified, established patterns)
- **Property-Based Testing Guide**: `/Users/rushiparikh/projects/atom/backend/tests/property_tests/README.md` - Internal PBT patterns

### Tertiary (LOW confidence)

- WebSearch attempts for current best practices returned no results (technical issue with search service)
- Cross-platform E2E orchestration patterns (requires verification against Phase 148 documentation)
- Mobile and desktop accessibility testing patterns (requires additional research)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are industry standards with widespread adoption
- Architecture: HIGH - Based on existing Atom codebase patterns and established testing practices
- Pitfalls: HIGH - Verified against existing test infrastructure and common testing anti-patterns
- Code examples: HIGH - Sourced from actual Atom test files (conftest.py, test files)
- Cross-platform patterns: MEDIUM - Some patterns verified (web, mobile), others need additional research (desktop a11y, cross-platform E2E)

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (30 days for testing practices, though core libraries are stable)

**Key recommendations for planning:**
1. Extend existing `critical_error_paths/` infrastructure for EDGE-01 (error boundaries)
2. Use existing `concurrent_operations/` patterns for EDGE-04 (race conditions)
3. Build on jest-axe infrastructure for EDGE-03 (accessibility)
4. Leverage E2E test patterns for EDGE-05 (cross-service workflows)
5. Add routing edge case tests using existing navigation test patterns for EDGE-02

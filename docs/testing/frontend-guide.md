# Frontend Testing Guide

**Platform:** Next.js (React)
**Frameworks:** Jest, React Testing Library, MSW, jest-axe
**Target:** 80%+ coverage across all modules
**Last Updated:** March 7, 2026

---

## Table of Contents

1. [Quick Start (5 min)](#quick-start-5-min)
2. [Test Structure](#test-structure)
3. [Jest Patterns](#jest-patterns)
4. [Mock Server (MSW)](#mock-server-msw)
5. [Accessibility Testing (jest-axe)](#accessibility-testing-jest-axe)
6. [Coverage](#coverage)
7. [CI/CD](#cicd)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [Further Reading](#further-reading)
11. [See Also](#see-also)

---

## Quick Start (5 min)

### Run All Tests

```bash
cd frontend-nextjs
npm test -- --watchAll=false
# Expected: 1753 tests pass, 99.6s execution
```

### Run Tests with Coverage

```bash
npm test -- --coverage --watchAll=false
# Expected: 80%+ overall coverage
# HTML report: open coverage/lcov-report/index.html
```

### Run Specific Test File

```bash
npm test -- AgentForm.test
```

### Run Tests in Watch Mode

```bash
npm test
# Runs tests in watch mode for development
```

---

## Test Structure

Frontend tests are organized by type and module:

```
frontend-nextjs/
├── components/
│   ├── __tests__/
│   │   ├── canvas/           # Canvas component tests
│   │   ├── integrations/     # Integration component tests
│   │   └── ui/              # UI component tests
│   └── **/*.a11y.test.tsx   # Accessibility tests
├── hooks/
│   └── __tests__/           # Custom hook tests
├── lib/
│   └── __tests__/           # Utility library tests
├── pages/
│   └── __tests__/           # Next.js page tests
└── tests/
    ├── integration/         # API integration tests (MSW)
    └── mocks/
        ├── handlers.ts      # MSW API handlers
        └── server.ts        # MSW server setup
```

### Test File Naming

- Unit tests: `*.test.ts` or `*.test.tsx`
- Accessibility tests: `*.a11y.test.tsx`
- Integration tests: `integration/*.test.tsx`

---

## Jest Patterns

### Component Testing (React Testing Library)

React Testing Library encourages testing behavior, not implementation details.

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentForm } from './AgentForm';

describe('AgentForm', () => {
  it('submit button enables when form is valid', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();

    render(<AgentForm onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /submit/i });

    // Initially disabled
    expect(submitButton).toBeDisabled();

    // Fill required fields
    await user.type(screen.getByLabelText(/name/i), 'Agent 1');
    await user.type(screen.getByLabelText(/description/i), 'Test Agent');

    // Now enabled
    expect(submitButton).toBeEnabled();

    // Submit form
    await user.click(submitButton);

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Agent 1',
      description: 'Test Agent',
    });
  });

  it('displays validation error for invalid name', async () => {
    const user = userEvent.setup();
    render(<AgentForm onSubmit={jest.fn()} />);

    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'AB'); // Too short (min 3 chars)

    await waitFor(() => {
      expect(screen.getByText(/name must be at least 3 characters/i)).toBeInTheDocument();
    });
  });
});
```

### Custom Hook Testing (renderHook pattern)

Test custom hooks with `renderHook` from React Testing Library:

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAgentCounter } from './useAgentCounter';

describe('useAgentCounter', () => {
  it('initializes with count of 0', () => {
    const { result } = renderHook(() => useAgentCounter());
    expect(result.current.count).toBe(0);
  });

  it('increments count when increment is called', async () => {
    const { result } = renderHook(() => useAgentCounter());

    act(() => {
      result.current.increment();
    });

    expect(result.current.count).toBe(1);
  });

  it('decrements count when decrement is called', async () => {
    const { result } = renderHook(() => useAgentCounter());

    act(() => {
      result.current.increment();
      result.current.increment();
      result.current.decrement();
    });

    expect(result.current.count).toBe(1);
  });

  it('resets count to 0 when reset is called', async () => {
    const { result } = renderHook(() => useAgentCounter());

    act(() => {
      result.current.increment();
      result.current.increment();
      result.current.reset();
    });

    expect(result.current.count).toBe(0);
  });
});
```

### Async Component Testing

Use `waitFor` for async operations:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { AgentList } from './AgentList';

describe('AgentList', () => {
  it('loads and displays agents', async () => {
    render(<AgentList />);

    // Initially shows loading
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

    // Waits for data to load
    await waitFor(() => {
      expect(screen.getByText('Test Agent 1')).toBeInTheDocument();
    });

    // Loading spinner removed
    expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
  });

  it('displays error message on fetch failure', async () => {
    // Mock failed fetch
    jest.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('Network error'));

    render(<AgentList />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load agents/i)).toBeInTheDocument();
    });
  });
});
```

### User Interactions

Use `userEvent` over `fireEvent` for more realistic interactions:

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginForm } from './LoginForm';

describe('LoginForm', () => {
  it('submits form with valid credentials', async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();

    render(<LoginForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
      });
    });
  });
});
```

---

## Mock Server (MSW)

MSW (Mock Service Worker) intercepts HTTP requests and returns mock responses for integration testing.

### Setup

```typescript
// tests/mocks/server.ts
import { setupServer } from 'msw/node';
import { rest } from 'msw';
import { handlers } from './handlers';

export const server = setupServer(...handlers);

// Setup Jest lifecycle hooks
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Define Handlers

```typescript
// tests/mocks/handlers.ts
import { rest } from 'msw';

export const handlers = [
  // Agent API handlers
  rest.get('/api/atom-agent/agents', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        agents: [
          { id: 'agent-1', name: 'Test Agent 1', status: 'active' },
          { id: 'agent-2', name: 'Test Agent 2', status: 'inactive' },
        ],
      })
    );
  }),

  rest.post('/api/atom-agent/agents', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'agent-123',
        name: 'New Agent',
        status: 'active',
      })
    );
  }),

  // Canvas API handlers
  rest.post('/api/canvas/present', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        canvas_id: 'canvas-123',
        status: 'presenting',
      })
    );
  }),
];
```

### Override Handlers in Tests

```typescript
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';
import { AgentList } from './AgentList';

describe('AgentList with error scenarios', () => {
  it('displays error message on 500 response', async () => {
    // Override handler for this test
    server.use(
      rest.get('/api/atom-agent/agents', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({ error: 'Internal Server Error' })
        );
      })
    );

    render(<AgentList />);

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
  });

  it('handles rate limiting (429)', async () => {
    server.use(
      rest.get('/api/atom-agent/agents', (req, res, ctx) => {
        return res(
          ctx.status(429),
          ctx.json({ error: 'Too Many Requests' }),
          ctx.set('retry-after', '60')
        );
      })
    );

    render(<AgentList />);

    await waitFor(() => {
      expect(screen.getByText(/too many requests/i)).toBeInTheDocument();
      expect(screen.getByText(/please try again in 60 seconds/i)).toBeInTheDocument();
    });
  });
});
```

### Test API Integration

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';
import { useCreateAgent } from './useCreateAgent';

const wrapper = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('useCreateAgent', () => {
  it('creates agent via API', async () => {
    const { result } = renderHook(() => useCreateAgent(), { wrapper });

    await waitFor(async () => {
      await result.current.mutateAsync({ name: 'Test Agent' });
    });

    expect(result.current.data).toEqual({
      id: 'agent-123',
      name: 'Test Agent',
      status: 'active',
    });
  });

  it('handles API errors', async () => {
    server.use(
      rest.post('/api/atom-agent/agents', (req, res, ctx) => {
        return res(ctx.status(400), ctx.json({ error: 'Invalid name' }));
      })
    );

    const { result } = renderHook(() => useCreateAgent(), { wrapper });

    let error;
    try {
      await result.current.mutateAsync({ name: '' });
    } catch (e) {
      error = e;
    }

    expect(error).toBeDefined();
    expect(error.message).toContain('Invalid name');
  });
});
```

### Network Error Simulation

```typescript
it('handles network errors', async () => {
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res.networkError('Network connection failed');
    })
  );

  render(<AgentList />);

  await waitFor(() => {
    expect(screen.getByText(/unable to connect/i)).toBeInTheDocument();
  });
});
```

---

## Accessibility Testing (jest-axe)

jest-axe validates WCAG 2.1 AA compliance for accessibility.

### Setup

```typescript
// tests/setup.ts
import { toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);
```

### Basic Accessibility Test

```typescript
import { axe, toHaveNoViolations } from 'jest-axe';
import { render } from '@testing-library/react';
import { CanvasViewer } from './CanvasViewer';

expect.extend(toHaveNoViolations);

describe('CanvasViewer accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(<CanvasViewer />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### Test with Interactions

```typescript
it('has no violations after opening dialog', async () => {
  const { container, getByRole } = render(<CanvasViewer />);

  // Open dialog
  fireEvent.click(getByRole('button', { name: /open canvas/i }));

  // Check accessibility
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### Test Specific WCAG Rules

```typescript
it('has no color contrast violations', async () => {
  const { container } = render(<CanvasViewer />);
  const results = await axe(container, {
    rules: {
      'color-contrast': { enabled: true },
    },
  });
  expect(results).toHaveNoViolations());
});
```

### Accessibility for Form Controls

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentForm } from './AgentForm';

describe('AgentForm accessibility', () => {
  it('has accessible form labels', async () => {
    render(<AgentForm onSubmit={jest.fn()} />);

    // All inputs have accessible labels
    expect(screen.getByLabelText(/agent name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();

    // Submit button is accessible
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
  });

  it('associates errors with form inputs', async () => {
    const user = userEvent.setup();
    render(<AgentForm onSubmit={jest.fn()} />);

    const nameInput = screen.getByLabelText(/agent name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'AB');

    await waitFor(() => {
      const errorMessage = screen.getByText(/name must be at least 3 characters/i);
      expect(errorMessage).toBeInTheDocument();

      // Error message is associated with input via aria-describedby
      expect(nameInput).toHaveAttribute('aria-describedby');
    });
  });
});
```

---

## Coverage

### Coverage Targets by Module

| Module | Target | Current |
|--------|--------|---------|
| Utility Libraries (`lib/**`) | 90% | TBD |
| React Hooks (`hooks/**`) | 85% | TBD |
| Canvas Components (`components/canvas/**`) | 85% | TBD |
| UI Components (`components/ui/**`) | 80% | TBD |
| Integration Components (`components/integrations/**`) | 80% | TBD |
| Next.js Pages (`pages/**`) | 80% | TBD |
| **Global Floor** | **80%** | TBD |

### Generate Coverage Report

```bash
# Generate coverage report
npm test -- --coverage --watchAll=false

# View HTML report
open coverage/lcov-report/index.html

# View JSON summary
cat coverage/coverage-summary.json
```

### Coverage Threshold Enforcement

Coverage thresholds are enforced in `jest.config.js`:

```javascript
coverageThreshold: {
  global: {
    branches: 75,
    functions: 80,
    lines: 80,
    statements: 75,
  },
  './lib/**/*.{ts,tsx}': {
    branches: 85,
    functions: 90,
    lines: 90,
    statements: 90,
  },
  './hooks/**/*.{ts,tsx}': {
    branches: 80,
    functions: 85,
    lines: 85,
    statements: 85,
  },
  // ... (see jest.config.js for full configuration)
}
```

### Check Coverage for Specific File

```bash
# Check coverage for specific component
npm test -- AgentForm --coverage --collectCoverageFrom=components/agent/AgentForm.tsx
```

### Per-Module Coverage Audit

```bash
# Run module coverage audit script
node scripts/coverage-audit.js

# Run coverage gaps script
node scripts/coverage-gaps.js

# Check module thresholds
node scripts/check-module-coverage.js
```

---

## CI/CD

### GitHub Actions Workflow

Frontend tests run automatically on every pull request to `main` or `develop`.

**Workflow:** `.github/workflows/frontend-tests.yml`

### Quality Gates

```yaml
# .github/workflows/frontend-tests.yml
- name: Run tests with coverage
  run: npm test -- --coverage --watchAll=false

- name: Enforce coverage thresholds
  run: |
    if [ $(coverage_percent) -lt 80 ]; then
      echo "Coverage below 80% threshold"
      exit 1
    fi
```

### PR Comments

Each PR receives a coverage comment with:
- Overall coverage percentage
- Module-level breakdown (passed/failed status)
- Files below threshold (with coverage %)
- Worst files per module (top 5)

**Comment Pattern:** Uses find/update pattern to avoid duplicates.

### Artifact Retention

- Coverage artifacts: 30 days
- Coverage trend data: 90 days
- Test results: 7 days

### Local CI Testing

```bash
# Run tests in CI mode (max 2 workers, no watch)
npm run test:ci

# Verify coverage thresholds
npm run test:check-coverage
```

---

## Troubleshooting

### MSW Handlers Not Matching Requests

**Problem:** Test shows real network error instead of mocked response.

**Solution:**

1. Check request method (GET vs POST)
2. Check URL path matches exactly
3. Check request body format

```typescript
// Debug MSW handlers
server.printHandlers() // List all active handlers

// Check if handler is defined
server.events.on('request:start', ({ request }) => {
  console.log('MSW intercepted:', request.method, request.url);
});
```

**See:** `frontend-nextjs/docs/API_ROBUSTNESS.md`

### Accessibility Tests Failing

**Problem:** jest-axe reports WCAG violations.

**Common issues:**

1. Missing ARIA labels
2. Insufficient color contrast
3. Missing alt text for images
4. Keyboard navigation issues

**Solution:**

```typescript
// Add accessible label
<input
  aria-label="Agent name"  // or use htmlFor + <label>
  {...props}
/>

// Add alt text
<img src="..." alt="Agent logo" />

// Ensure keyboard navigability
<button onClick={...}>Click me</button> // GOOD
<div onClick={...}>Click me</div>      // BAD - use button
```

**See:** jest-axe documentation, WCAG 2.1 AA guidelines

### Async Timing Issues

**Problem:** Test fails with "element not found" but element exists.

**Solution:** Use `waitFor` or `findBy*` queries instead of `getBy*`.

```typescript
// ❌ Fails: Element appears after getBy* check
test('loads agents', () => {
  render(<AgentList />);
  expect(screen.getByText('Test Agent')).toBeInTheDocument(); // Fails!
});

// ✅ Works: findBy* waits for element
test('loads agents', async () => {
  render(<AgentList />);
  expect(await screen.findByText('Test Agent')).toBeInTheDocument();
});

// ✅ Works: waitFor with timeout
test('loads agents', async () => {
  render(<AgentList />);
  await waitFor(() => {
    expect(screen.getByText('Test Agent')).toBeInTheDocument();
  }, { timeout: 3000 });
});
```

### Test Not Isolated

**Problem:** Test passes alone but fails when run with other tests.

**Solution:** Ensure proper cleanup in `afterEach`.

```typescript
// Clear all mocks after each test
afterEach(() => {
  jest.clearAllMocks();
  jest.resetAllMocks();
});

// Reset MSW handlers
afterEach(() => {
  server.resetHandlers();
});

// Clean up database/localStorage
afterEach(() => {
  localStorage.clear();
  cleanup(); // From React Testing Library
});
```

### Coverage Not Increasing

**Problem:** Adding tests but coverage stays same.

**Solution:**

1. Verify tests are actually calling target code
2. Check for conditional branches not tested
3. Add edge case tests
4. Review test assertions (may be passing without executing code)

```bash
# Check which lines are covered
npm test -- --coverage --watchAll=false

# View HTML report for visual inspection
open coverage/lcov-report/index.html
```

---

## Best Practices

### 1. Test Behavior, Not Implementation

**React Testing Library Philosophy:**

```typescript
// ❌ BAD: Test implementation details
test('agent count state', () => {
  render(<AgentList />);
  expect(component.state.count).toBe(0); // Tests private state
});

// ✅ GOOD: Test observable behavior
test('displays agent count', () => {
  render(<AgentList />);
  expect(screen.getByText(/0 agents/i)).toBeInTheDocument();
});
```

### 2. Mock External Dependencies

```typescript
// ✅ GOOD: Mock API with MSW
import { server } from '@/tests/mocks/server';

test('loads agents from API', async () => {
  server.use(
    rest.get('/api/agents', (req, res, ctx) => {
      return res(ctx.json({ agents: mockAgents }));
    })
  );

  render(<AgentList />);
  // Test component behavior with mocked API
});

// ✅ GOOD: Mock modules with jest.mock
jest.mock('@/lib/api', () => ({
  fetchAgents: jest.fn(() => Promise.resolve(mockAgents)),
}));
```

### 3. Test Accessibility

```typescript
// ✅ GOOD: Test WCAG compliance
import { axe, toHaveNoViolations } from 'jest-axe';

test('has no accessibility violations', async () => {
  const { container } = render(<CanvasViewer />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});

// ✅ GOOD: Test keyboard navigation
test('submit button accessible via keyboard', async () => {
  const user = userEvent.setup();
  render(<AgentForm />);

  // Tab to submit button
  await user.tab();
  await user.tab();

  // Press Enter to submit
  await user.keyboard('{Enter}');

  expect(onSubmit).toHaveBeenCalled();
});
```

### 4. Use Property Tests for Complex Logic

```typescript
// ✅ GOOD: Property tests for state machines
import fc from 'fast-check';

test('state machine preserves data during transitions', () => {
  fc.assert(
    fc.property(fc.record({ id: fc.string() }), (data) => {
      const state = { status: 'idle', data };
      const nextState = stateMachine(state, { type: 'START' });
      expect(nextState.data).toEqual(data); // Data preserved
    }),
    { numRuns: 100, seed: 23001 }
  );
});
```

**See:** `docs/PROPERTY_TESTING_PATTERNS.md` (FastCheck section)

### 5. Isolate Tests

```typescript
// ✅ GOOD: Each test creates fresh data
test('creates agent', async () => {
  const agent = createTestAgent();
  expect(agent.id).toBeDefined();
});

test('deletes agent', async () => {
  const agent = createTestAgent(); // Fresh data
  await deleteAgent(agent.id);
  expect(agentExists(agent.id)).toBe(false);
});

// ✅ GOOD: Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
  cleanup();
  server.resetHandlers();
});
```

---

## Further Reading

### Property Testing

- **PROPERTY_TESTING_PATTERNS.md** - FastCheck property testing guide for complex state machines and invariants

### E2E Testing

- **E2E_TESTING_GUIDE.md** - Playwright end-to-end testing patterns

### Cross-Platform Coverage

- **CROSS_PLATFORM_COVERAGE.md** - Weighted coverage thresholds across all platforms

### API Robustness

- **frontend-nextjs/docs/API_ROBUSTNESS.md** - MSW patterns for error handling, retry logic, and loading states

### Frontend Coverage

- **frontend-nextjs/docs/FRONTEND_COVERAGE.md** - Detailed coverage analysis and trending

---

## See Also

### Testing Documentation Index

- [Testing Documentation Index](TESTING_INDEX.md) - Central hub for all testing documentation

### Platform-Specific Guides

- [Backend Coverage Guide](TESTING_INDEX.md) - Python/pytest testing patterns
- [Mobile Testing Guide](MOBILE_TESTING_GUIDE.md) - React Native testing patterns (to be created in Phase 152-03)
- [Desktop Testing Guide](DESKTOP_TESTING_GUIDE.md) - Rust/Tauri testing patterns (to be created in Phase 152-04)

### Quality Standards

- [Test Quality Standards](CODE_QUALITY_GUIDE.md) - Backend test independence, pass rates, performance standards

---

## Quick Reference

### Common Commands

```bash
# Run all tests
npm test -- --watchAll=false

# Run with coverage
npm test -- --coverage --watchAll=false

# Run specific file
npm test -- AgentForm.test

# Watch mode (development)
npm test

# CI mode
npm run test:ci

# View coverage report
open coverage/lcov-report/index.html
```

### Import Shortcuts

```typescript
// React Testing Library
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// MSW
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// jest-axe
import { axe, toHaveNoViolations } from 'jest-axe';

// Jest utilities
import { renderHook, act } from '@testing-library/react';
```

### Query Strategies

```typescript
// Priority order (use first available)
screen.getByRole('button', { name: /submit/i })        // 1. Role (best)
screen.getByLabelText(/email/i)                         // 2. Label
screen.getByPlaceholderText(/search/i)                  // 3. Placeholder
screen.getByText(/submit/i)                             // 4. Text content
screen.getByTestId('submit-button')                     // 5. Test ID (last resort)

// Async variants
await screen.findByRole('button', { name: /submit/i })
screen.queryByRole('button') // Returns null if not found
```

---

**Document Version:** 1.0
**Last Updated:** March 7, 2026
**Maintainer:** Frontend Team

**For questions or contributions, see:** [Testing Documentation Index](TESTING_INDEX.md)

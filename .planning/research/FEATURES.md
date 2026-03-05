# Feature Landscape

**Domain:** Frontend Testing Coverage (React/Next.js)
**Researched:** March 3, 2026
**Overall confidence:** HIGH

## Executive Summary

Comprehensive frontend testing for consistent 80%+ coverage requires a systematic approach across multiple categories: component testing (leaf vs composite), state management testing (Redux/Context/hooks), API client testing (MSW, axios), form validation, error boundaries, routing, and accessibility. Based on analysis of React testing best practices, Testing Library patterns, and the current Atom codebase (89.84% overall coverage but inconsistent across modules), this document outlines table stakes features for achieving consistent coverage, differentiators that distinguish excellent test suites, and anti-patterns to avoid.

**Key Findings:**
- **Current state**: Atom has 89.84% overall coverage with 1,004+ tests, FastCheck property tests (84 tests), but inconsistent coverage across modules
- **Table stakes for 80% coverage**: Component rendering tests, state management tests, API mocking with MSW, form validation, error boundaries, routing tests
- **Critical gaps**: Leaf component coverage, composite component integration tests, state machine tests, API contract tests, accessibility coverage
- **Testing pyramid balance**: 70% unit tests, 20% integration tests, 10% E2E tests for optimal coverage
- **Key anti-patterns**: Over-mocking, testing implementation details, brittle selectors, missing error path tests

## Table Stakes

Features expected in ANY frontend codebase aiming for 80%+ coverage. Missing = inconsistent coverage or fragile test suite.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Leaf Component Tests** | Individual UI components must render correctly with props | Low | Button, Input, Card - test render, props, interactions |
| **Composite Component Tests** | Component composition (parent-child) must work correctly | Medium | Forms, layouts, containers - test data flow, event propagation |
| **State Rendering Tests** | Components must display state correctly (Redux/Context/hooks) | Medium | Test initial state, state updates, derived state |
| **User Interaction Tests** | Buttons, forms, navigation must respond to user actions | Low | Click events, form input, keyboard shortcuts |
| **API Mocking with MSW** | Tests must run without real backend, validate request/response shapes | Medium | Mock Service Worker for REST/GraphQL, test error handling |
| **Form Validation Tests** | Forms must validate inputs and show errors | Low | Required fields, format validation, error messages |
| **Async State Tests** | Loading/error/success states for async operations | Medium | Data fetching, mutations, optimistic updates |
| **Error Boundary Tests** | React error boundaries must catch errors gracefully | Low | Test error fallback UI, error logging |
| **Routing Tests** | Navigation must work correctly (Next.js/React Router) | Low | Mock router, test navigation, route params |
| **Hook Tests** | Custom hooks must work correctly | Medium | renderHook for testing hook logic |
| **Accessibility Tests** | Basic accessibility (ARIA, keyboard nav) must work | Low | jest-axe for automated a11y checks |
| **Snapshot Tests** | Detect unintended UI changes | Low | Jest snapshots for component output (use sparingly) |

## Differentiators

Features that distinguish EXCELLENT test suites (80%+) from ADEQUATE ones. Not expected, but highly valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Property-Based Testing** | FastCheck generates hundreds of test cases, finds edge cases unit tests miss | High | State machine invariants, reducer purity, data transformation properties |
| **State Machine Tests** | Explicit state transition validation catches state bugs | Medium | XState, custom state machines - test all transitions, invalid states unreachable |
| **Visual Regression Tests** | Detect unintended CSS/layout changes | Medium | Percy, Chromatic, Playwright screenshots |
| **Contract Testing** | Validate API contracts between frontend and backend | High | OpenAPI schema validation, MSW + TypedRequest |
| **Mutation Testing** | Verify test quality by measuring what mutations tests catch | Medium | StrykerJS - identifies weak tests, dead code |
| **Performance Tests** | Detect rendering performance regressions | Medium | Lighthouse CI, render time budgets, bundle size tracking |
| **Cross-Browser Tests** | Verify consistent behavior across browsers | High | Playwright, BrowserStack - Chrome/Safari/Firefox/Edge |
| **Network Failure Tests** | Test app behavior under poor network conditions | Medium | MSW slow responses, offline mode, retry logic |
| **Memory Leak Tests** | Find memory leaks in long-running sessions | High | Test component unmount, cleanup, subscription disposal |
| **Internationalization Tests** | Verify UI works across languages/locales | Medium | Test translations, date/currency formatting, RTL languages |
| **E2E Critical Path Tests** | Test complete user workflows from UI to backend | High | Playwright, Cypress - 5-10 critical flows only |
| **Component Contract Tests** | Verify props, events, behavior contracts | Medium | TypeScript type validation, prop-type error tests |

## Anti-Features

Testing approaches to explicitly AVOID. These create brittle, unmaintainable tests.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Testing Implementation Details** | Tests break on refactoring, test internal state instead of behavior | Test user-facing behavior, use getByRole/getByLabelText over CSS selectors |
| **Over-Mocking External Libraries** | Tests mock too much, don't validate real integration | Only mock network, device APIs, time - test real component logic |
| **Brittle Selector Tests** | CSS classes break tests, deeply nested selectors fragile | Use data-testid attributes for stable selectors, semantic queries (getByRole) |
| **Testing Third-Party Libraries** | Don't test what library authors already test | Trust React, Next.js, Chakra UI - test your code only |
| **Shared State Between Tests** | Tests interfere with each other, non-deterministic failures | Isolate test data, cleanup after each test, use fixtures |
| **Hardcoded Test Data** | Doesn't test edge cases, misses boundary conditions | Use property-based testing (FastCheck), data generators |
| **Missing Error Path Tests** | Only testing happy path misses critical bugs | Test 401, 500, network errors, malformed responses, timeouts |
| **Testing Browser APIs Directly** | Different browsers behave differently | Use jsdom for unit tests, Playwright for real browser validation |
| **Flaky Async Tests** | Non-deterministic failures destroy trust in tests | Use proper async/await, waitFor, fake timers, clear async patterns |
| **E2E Tests for Everything** | Slow, brittle, expensive to maintain | Use component/integration tests for speed, E2E for 5-10 critical paths |
| **Snapshot Tests Without Review** | Snapshots checked in without review, test wrong behavior | Review snapshot diffs, ensure they capture intentional changes |
| **Testing Private Methods** | Implementation detail, breaks on refactoring | Test public API only, behavior over implementation |

## Component Coverage Patterns

### Leaf Components (Simple)

**Definition**: Presentational components with no children, accept props, render UI.

**Examples**: Button, Input, Card, Badge, Icon.

**Testing Approach**:
```typescript
// Example: Button component test
describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const handleClick = jest.fn();
    const user = userEvent.setup();

    render(<Button onClick={handleClick}>Click me</Button>);
    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

**Coverage Targets**:
- **Lines**: 90%+ (simple logic, easy to cover)
- **Branches**: 80%+ (conditional rendering)
- **Functions**: 100% (event handlers)

**Test Count**: 3-5 tests per component (render, interactions, variants).

---

### Composite Components (Complex)

**Definition**: Components that compose other components, manage state, handle logic.

**Examples**: Form, Modal, Table, List, Chart.

**Testing Approach**:
```typescript
// Example: Form component test
describe('LoginForm', () => {
  it('renders form fields', () => {
    render(<LoginForm onSubmit={jest.fn()} />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup();
    render(<LoginForm onSubmit={jest.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Submit' }));

    expect(await screen.findByText('Email is required')).toBeInTheDocument();
    expect(await screen.findByText('Password is required')).toBeInTheDocument();
  });

  it('submits form with valid data', async () => {
    const handleSubmit = jest.fn();
    const user = userEvent.setup();

    render(<LoginForm onSubmit={handleSubmit} />);

    await user.type(screen.getByLabelText('Email'), 'test@example.com');
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });
});
```

**Coverage Targets**:
- **Lines**: 85%+ (complex logic)
- **Branches**: 75%+ (multiple code paths)
- **Functions**: 90%+ (lifecycle methods, handlers)

**Test Count**: 5-10 tests per component (render, validation, submission, error states, edge cases).

---

### Container Components (Smart)

**Definition**: Components that connect to state management (Redux/Context), fetch data, dispatch actions.

**Examples**: AgentList, Dashboard, CanvasViewer.

**Testing Approach**:
```typescript
// Example: Container component with Redux
import { renderWithProviders } from '@/tests/utils';
import { store } from '@/store';

describe('AgentList', () => {
  it('renders loading state initially', () => {
    renderWithProviders(<AgentList />);
    expect(screen.getByText('Loading agents...')).toBeInTheDocument();
  });

  it('renders agents after fetching', async () => {
    // Mock API response
    jest.spyOn(api, 'getAgents').mockResolvedValue({
      agents: [{ id: '1', name: 'Agent 1' }],
    });

    renderWithProviders(<AgentList />);

    await waitFor(() => {
      expect(screen.getByText('Agent 1')).toBeInTheDocument();
    });
  });

  it('dispatches deleteAgent action when delete clicked', async () => {
    const user = userEvent.setup();
    const mockStore = store;

    renderWithProviders(<AgentList />, { store: mockStore });

    await user.click(screen.getByRole('button', { name: 'Delete' }));

    const actions = mockStore.getActions();
    expect(actions).toContainEqual(deleteAgent('1'));
  });
});
```

**Coverage Targets**:
- **Lines**: 80%+ (integration logic)
- **Branches**: 70%+ (async states)
- **Functions**: 85%+ (thunks, selectors)

**Test Count**: 8-15 tests per component (render, loading, success, error, interactions, state updates).

---

## State Management Testing

### Redux/Reducer Tests

**What to Test**:
- Reducer purity (same input → same output)
- State immutability (no mutations)
- Action handling (all action types)
- Initial state
- Selector correctness

**Testing Approach**:
```typescript
describe('agents reducer', () => {
  it('returns initial state', () => {
    expect(reducer(undefined, { type: 'unknown' })).toEqual(initialState);
  });

  it('handles fetchAgents.pending', () => {
    const state = reducer(initialState, fetchAgents.pending());
    expect(state.loading).toBe(true);
  });

  it('handles fetchAgents.fulfilled', () => {
    const agents = [{ id: '1', name: 'Agent 1' }];
    const state = reducer(initialState, fetchAgents.fulfilled(agents));

    expect(state.loading).toBe(false);
    expect(state.agents).toEqual(agents);
  });

  it('handles deleteAgent', () => {
    const stateWithAgents = {
      ...initialState,
      agents: [{ id: '1', name: 'Agent 1' }],
    };

    const state = reducer(stateWithAgents, deleteAgent('1'));
    expect(state.agents).toEqual([]);
  });
});
```

**Complexity**: **Medium** - Reducers are pure functions, straightforward to test.

---

### Context Provider Tests

**What to Test**:
- Context value correctness
- Consumer receives updates
- Provider renders children
- Default values

**Testing Approach**:
```typescript
describe('AuthContext', () => {
  it('provides default auth state', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('updates auth state on login', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await act(async () => {
      await result.current.login('user@example.com', 'password');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual({
      email: 'user@example.com',
    });
  });

  it('clears auth state on logout', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await act(async () => {
      await result.current.login('user@example.com', 'password');
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });
});
```

**Complexity**: **Medium** - Requires renderHook wrapper for Context providers.

---

### Custom Hook Tests

**What to Test**:
- Hook returns correct values
- Hook updates on dependency changes
- Hook cleanup on unmount
- Error handling

**Testing Approach**:
```typescript
import { renderHook, act } from '@testing-library/react';

describe('useWebSocket', () => {
  it('connects to WebSocket on mount', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:3000'));

    expect(result.current.connected).toBe(true);
  });

  it('sends messages', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:3000'));

    act(() => {
      result.current.send({ type: 'message', data: 'test' });
    });

    expect(WebSocket).toHaveBeenCalledWith('ws://localhost:3000');
  });

  it('disconnects on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket('ws://localhost:3000'));

    unmount();

    expect(mockWebSocket.close).toHaveBeenCalled();
  });
});
```

**Complexity**: **Medium** - Requires renderHook, act for state updates.

---

## API Client Testing

### MSW (Mock Service Worker) Setup

**What to Test**:
- Request serialization (body matches API schema)
- Response deserialization (response matches expected types)
- Error handling (401, 500, network errors, timeouts)
- Retry logic
- Loading states

**Testing Approach**:
```typescript
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/agents', (req, res, ctx) => {
    return res(ctx.json({ agents: [] }));
  }),

  rest.post('/api/agents', (req, res, ctx) => {
    return res(ctx.status(201), ctx.json({ id: '1', ...req.body }));
  }),

  rest.get('/api/agents/:id', (req, res, ctx) => {
    const { id } = req.params;
    if (id === '404') {
      return res(ctx.status(404), ctx.json({ error: 'Agent not found' }));
    }
    return res(ctx.json({ id, name: 'Agent 1' }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('agent API', () => {
  it('fetches agents successfully', async () => {
    const { result } = renderHook(() => useAgents());

    await waitFor(() => expect(result.current.agents).toEqual([]));
  });

  it('handles 404 error', async () => {
    const { result } = renderHook(() => useAgent('404'));

    await waitFor(() => {
      expect(result.current.error).toBe('Agent not found');
    });
  });

  it('retries on failure', async () => {
    let attemptCount = 0;
    server.use(
      rest.get('/api/agents', (req, res, ctx) => {
        attemptCount++;
        if (attemptCount < 3) {
          return res(ctx.status(500));
        }
        return res(ctx.json({ agents: [] }));
      })
    );

    const { result } = renderHook(() => useAgents());

    await waitFor(() => expect(result.current.agents).toEqual([]));
    expect(attemptCount).toBe(3);
  });
});
```

**Complexity**: **Medium** - Requires MSW setup, async handling, waitFor.

---

### Axios Interceptor Tests

**What to Test**:
- Request interceptor modifies headers (auth tokens)
- Response interceptor transforms data
- Error interceptor handles errors globally
- Interceptor order

**Testing Approach**:
```typescript
describe('axios interceptors', () => {
  it('adds auth token to requests', async () => {
    const mockToken = 'test-token';
    localStorage.setItem('token', mockToken);

    const response = await api.get('/protected');

    expect(api.defaults.headers.common.Authorization).toBe(`Bearer ${mockToken}`);
  });

  it('handles 401 errors globally', async () => {
    const mockRefreshToken = jest.fn().mockResolvedValue('new-token');

    server.use(
      rest.get('/api/protected', (req, res, ctx) => {
        return res(ctx.status(401));
      })
    );

    await api.get('/protected');

    expect(mockRefreshToken).toHaveBeenCalled();
  });

  it('transforms response data', async () => {
    server.use(
      rest.get('/api/agents', (req, res, ctx) => {
        return res(ctx.json({ data: { agents: [] } }));
      })
    );

    const response = await api.get('/agents');

    expect(response.data).toEqual({ agents: [] });
  });
});
```

**Complexity**: **Medium** - Requires interceptor setup, global error handling.

---

## Form Validation Testing

**What to Test**:
- Required field validation
- Format validation (email, password strength)
- Error message display
- Successful submission
- Real-time vs on-blur validation

**Testing Approach**:
```typescript
describe('LoginForm validation', () => {
  it('shows error for empty email on blur', async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    const emailInput = screen.getByLabelText('Email');
    await user.click(emailInput);
    await user.tab(); // Blur

    expect(await screen.findByText('Email is required')).toBeInTheDocument();
  });

  it('shows error for invalid email format', async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText('Email'), 'invalid-email');
    await user.tab();

    expect(await screen.findByText('Invalid email format')).toBeInTheDocument();
  });

  it('shows error for weak password', async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText('Password'), '123');
    await user.tab();

    expect(await screen.findByText('Password must be at least 8 characters')).toBeInTheDocument();
  });

  it('submits form with valid data', async () => {
    const handleSubmit = jest.fn();
    const user = userEvent.setup();

    render(<LoginForm onSubmit={handleSubmit} />);

    await user.type(screen.getByLabelText('Email'), 'test@example.com');
    await user.type(screen.getByLabelText('Password'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });
});
```

**Complexity**: **Low** - Straightforward user interaction simulation.

---

## Error Boundary Testing

**What to Test**:
- Error boundary catches child component errors
- Fallback UI displays correctly
- Error logging works
- Production vs development behavior

**Testing Approach**:
```typescript
describe('ErrorBoundary', () => {
  // Mock console.error to avoid test noise
  beforeEach(() => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders fallback UI when error occurs', () => {
    const ThrowError = () => {
      throw new Error('Test error');
    };

    render(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('logs error to error logging service', () => {
    const mockLogError = jest.spyOn(logger, 'logError');

    const ThrowError = () => {
      throw new Error('Test error');
    };

    render(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(mockLogError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Test error',
      })
    );
  });

  it('resets error state after retry', async () => {
    const ThrowError = ({ shouldThrow }) => {
      if (shouldThrow) throw new Error('Test error');
      return <div>No error</div>;
    };

    const { rerender } = render(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Reset and retry
    rerender(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('No error')).toBeInTheDocument();
  });
});
```

**Complexity**: **Low** - Component throws error, boundary catches it.

---

## Routing Testing

**What to Test**:
- Navigation between pages
- Route parameters passed correctly
- Query string parsing
- Deep links work correctly
- 404 pages for unknown routes

**Testing Approach (Next.js)**:
```typescript
import { useRouter } from 'next/router';

jest.mock('next/router');

describe('AgentDetailPage', () => {
  it('renders agent from route param', () => {
    (useRouter as jest.Mock).mockReturnValue({
      query: { id: 'agent-1' },
      push: jest.fn(),
      pathname: '/agents/[id]',
    });

    render(<AgentDetailPage />);

    expect(screen.getByText('Agent 1')).toBeInTheDocument();
  });

  it('navigates to agent list on back click', async () => {
    const mockPush = jest.fn();
    (useRouter as jest.Mock).mockReturnValue({
      query: { id: 'agent-1' },
      push: mockPush,
    });

    const user = userEvent.setup();
    render(<AgentDetailPage />);

    await user.click(screen.getByRole('button', { name: 'Back' }));

    expect(mockPush).toHaveBeenCalledWith('/agents');
  });
});
```

**Testing Approach (React Router)**:
```typescript
import { MemoryRouter } from 'react-router-dom';

describe('AgentDetailPage', () => {
  it('renders agent from route param', () => {
    render(
      <MemoryRouter initialEntries={['/agents/agent-1']}>
        <AgentDetailPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Agent 1')).toBeInTheDocument();
  });

  it('navigates to agent list on back click', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/agents/agent-1']}>
        <AgentDetailPage />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'Back' }));

    expect(screen.getByText('Agent List')).toBeInTheDocument();
  });

  it('shows 404 for unknown route', () => {
    render(
      <MemoryRouter initialEntries={['/unknown-route']}>
        <Routes>
          <Route path="/agents/:id" element={<AgentDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Page not found')).toBeInTheDocument();
  });
});
```

**Complexity**: **Low** - Router mocking is straightforward.

---

## Accessibility Testing

**What to Test**:
- ARIA roles and attributes
- Keyboard navigation
- Screen reader compatibility
- Color contrast (automated)
- Focus management

**Testing Approach (jest-axe)**:
```typescript
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

describe('Button accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(<Button>Click me</Button>);

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('Form accessibility', () => {
  it('has proper labels for all inputs', () => {
    render(<LoginForm />);

    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('can be submitted with keyboard', async () => {
    const handleSubmit = jest.fn();
    const user = userEvent.setup();

    render(<LoginForm onSubmit={handleSubmit} />);

    await user.tab(); // Focus email
    await user.keyboard('test@example.com');
    await user.tab(); // Focus password
    await user.keyboard('password123');
    await user.keyboard('{Enter}'); // Submit

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalled();
    });
  });
});
```

**Complexity**: **Low** - jest-axe is straightforward, automated checks.

---

## Testing Pyramid Balance

**Recommended Distribution for 80% Coverage**:

```
▲
│ E2E Tests (10%) - 5-10 critical user flows
├────────────────────────────────────────────
│ Integration Tests (20%) - Component + State + API
├────────────────────────────────────────────
│ Unit Tests (70%) - Components, hooks, utils, reducers
└────────────────────────────────────────────
```

### Unit Tests (70%) - Target: <100ms runtime

**Scope**: Individual functions, components, hooks in isolation.

**What to Test**:
- Pure functions (utils, formatters, validators)
- Component rendering with props
- Reducer logic
- Custom hooks
- Helper functions

**Test Count**: 500-1000 tests for large app.

---

### Integration Tests (20%) - Target: <5s runtime

**Scope**: Multiple modules working together (component + state + API).

**What to Test**:
- Component + Redux/Context
- Component + API calls (MSW)
- Component + Routing
- Form submission + API
- Multi-step workflows

**Test Count**: 100-200 tests for large app.

---

### E2E Tests (10%) - Target: <15min runtime

**Scope**: Complete user flows from UI to backend (real server).

**What to Test**:
- Login/logout flow
- Critical business paths (checkout, agent creation)
- Cross-page workflows
- Third-party integrations (OAuth, payments)

**Test Count**: 5-10 tests for large app.

---

## Coverage Targets by Category

| Category | Target Lines | Target Branches | Target Functions | Rationale |
|----------|--------------|-----------------|------------------|-----------|
| **Leaf Components** | 90%+ | 80%+ | 100% | Simple logic, easy to cover |
| **Composite Components** | 85%+ | 75%+ | 90%+ | More complex, but still straightforward |
| **Container Components** | 80%+ | 70%+ | 85%+ | Integration logic, harder to test |
| **State Management** | 90%+ | 85%+ | 95%+ | Pure functions, critical to app behavior |
| **API Layer** | 85%+ | 80%+ | 90%+ | Error handling, edge cases |
| **Utilities/Helpers** | 95%+ | 90%+ | 100% | Pure functions, easy to test |
| **Hooks** | 85%+ | 80%+ | 90%+ | Encapsulated logic, moderate complexity |
| **Forms** | 85%+ | 75%+ | 85%+ | Validation logic, error paths |
| **Routing** | 75%+ | 70%+ | 80%+ | Mostly navigation, some edge cases |

**Overall Target**: 80% lines, 75% branches, 85% functions.

---

## Complexity Assessment

| Area | Complexity | Why |
|------|------------|-----|
| **Leaf Component Tests** | **Low** | Simple render/assert patterns, well-documented |
| **Composite Component Tests** | **Medium** | Component composition, event propagation, data flow |
| **State Management Tests** | **Medium** | Reducer purity, async actions, selector consistency |
| **API Client Tests** | **Medium** | MSW setup, async handling, error scenarios |
| **Form Validation Tests** | **Low** | Straightforward validation rules, user input simulation |
| **Error Boundary Tests** | **Low** | Component throws error, boundary catches it |
| **Routing Tests** | **Low** | Router mocking, navigation assertions |
| **Hook Tests** | **Medium** | renderHook, act for state updates, cleanup |
| **Accessibility Tests** | **Low** | jest-axe automated checks, keyboard nav |
| **Property-Based Tests** | **High** | FastCheck learning curve, invariant identification, generator design |
| **Visual Regression Tests** | **Medium** | Screenshot infrastructure, baseline management |
| **Mutation Tests** | **Low** | StrykerJS setup easy, but requires good baseline tests |

---

## Feature Dependencies

```
Leaf Component Tests → Composite Component Tests (compose leaf components)
Composite Component Tests → Container Component Tests (connect to state)
API Client Tests → Integration Tests (component + API)
State Management Tests → Container Component Tests (need state)
Form Validation Tests → Integration Tests (form + API)
Hook Tests → Component Tests (components use hooks)
Error Boundary Tests → Integration Tests (error handling in flows)
Routing Tests → E2E Tests (navigation flows)
Property-Based Tests → State Management Tests (invariants)
```

---

## MVP Recommendation for Consistent 80%+ Coverage

**Prioritize for v5.2 (Gap Closure):**

### Phase 1: Foundation (Week 1)
- **Fix Failing Tests**: Resolve 21 failing frontend tests (40% → 100% pass rate)
- **Leaf Component Coverage**: Add tests for all leaf components (Button, Input, Card, Badge, Icon)
- **Utility Function Coverage**: Add tests for all utils/helpers (validators, formatters)
- **Target**: 90%+ coverage for utilities and leaf components

### Phase 2: Component Integration (Week 2-3)
- **Composite Component Tests**: Add tests for all composite components (forms, modals, tables)
- **Container Component Tests**: Add tests for all container components (AgentList, Dashboard, CanvasViewer)
- **Hook Tests**: Add tests for all custom hooks (useCanvasState, useWebSocket, useAuth)
- **Target**: 85%+ coverage for components and hooks

### Phase 3: State & API (Week 4-5)
- **State Management Tests**: Add tests for Redux reducers, Context providers, selectors
- **API Client Tests**: Add MSW tests for all API endpoints (success, error, retry)
- **Form Validation Tests**: Add tests for all forms (validation, submission, error handling)
- **Target**: 90%+ coverage for state management, 85%+ for API layer

### Phase 4: Edge Cases & Integration (Week 6)
- **Error Boundary Tests**: Add tests for all error boundaries
- **Routing Tests**: Add tests for all navigation flows
- **Accessibility Tests**: Add jest-axe tests for all components
- **Integration Tests**: Add component + state + API integration tests
- **Target**: 80%+ overall coverage, consistent across all modules

### Phase 5: Advanced Testing (Week 7-8) - Differentiators
- **Property-Based Tests**: Add FastCheck tests for state machines, reducers, data transformations
- **Contract Tests**: Add OpenAPI schema validation tests for all endpoints
- **Mutation Tests**: Run StrykerJS to identify weak tests
- **Target**: 20-30 property tests, 90%+ mutation score

---

## Defer to Future Releases

**Why defer**: These require additional infrastructure or are lower priority for achieving 80% coverage.

- **Visual Regression Testing** - Requires screenshot infrastructure, baseline management
- **Performance Regression Testing** - Requires performance budgets, Lighthouse CI setup
- **Cross-Browser Testing** - Requires BrowserStack/Playwright, higher maintenance
- **E2E Testing** - Requires test environment setup, slow feedback loop (5-10 critical flows only)
- **Memory Leak Testing** - Requires specialized tooling, complex setup

---

## Sources

### High Confidence (Official Documentation & Best Practices)
- **[React Testing Library Documentation](https://testing-library.com/docs/react-testing-library/intro/)** - Authoritative component testing patterns
- **[Jest Documentation](https://jestjs.io/docs/getting-started)** - Test runner configuration, mocking, async testing
- **[MSW (Mock Service Worker)](https://mswjs.io/)** - API mocking for integration tests
- **[fast-check Documentation](https://fast-check.dev/)** - Property-based testing for TypeScript/JavaScript
- **[jest-axe Documentation](https://github.com/nickcolley/jest-axe)** - Accessibility testing for React

### Medium Confidence (Industry Best Practices - WebSearch)
- **[React-Boilerplate测试体系](https://m.blog.csdn.net/gitblog_00249/article/details/151083249)** - 98% coverage standards (Feb 2026)
- **[NextUI组件测试覆盖率提升](https://m.blog.csdn.net/gitblog_00056/article/details/152686313)** - From 70% to 95% coverage improvements
- **[Vitest Component Testing Guide](https://cn.vitest.dev/guide/browser/component-testing)** - Modern error boundary testing patterns (Jan 2026)
- **[React Error Boundary Testing Guide](https://m.blog.csdn.net/gitblog_00277/article/details/154894355)** - Error boundary testing with React Testing Library (Feb 2026)
- **[Frontend Testing Anti-Patterns](https://www.selenium.dev/documentation/test_design/avoid_couple_to_impl/)** - Brittle selectors, implementation details testing

### Medium Confidence (Codebase Analysis - Atom)
- **Atom Frontend Test Infrastructure** - Jest + React Testing Library configured, 1,004+ tests passing
- **Atom Frontend Coverage** - 89.84% overall coverage (but inconsistent across modules)
- **Atom Property Tests** - FastCheck property tests (84 tests) for state machines, reducers, validation
- **Atom MSW Setup** - Mock Service Worker configured for API mocking
- **Atom Test Configuration** - `jest.config.js`, `tests/setup.ts`, test utilities

### Low Confidence (Limited WebSearch Verification - Needs Validation)
- **Cross-platform testing patterns** - Limited patterns for shared test suites across web/mobile/desktop
- **Visual regression testing** - Tool fragmentation (Percy vs Chromatic), unclear industry standards
- **Performance regression testing** - Lighthouse CI patterns still evolving
- **Mutation testing adoption** - StrykerJS usage patterns not widely documented

### Gaps Identified
- **Specific FastCheck patterns for React** - Limited adoption, few production examples
- **Component contract testing** - TypeScript-based contract validation patterns not well-documented
- **Testing Next.js Server Components** - Emerging patterns for Next.js 13+ App Router
- **Accessibility testing coverage targets** - Unclear industry standards for a11y coverage percentages

**Next Research Phases:**
- Phase-specific research needed for property-based test design (which invariants matter most)
- Investigation into FastCheck generator strategies for complex UI state
- Deep dive on Next.js Server Component testing patterns
- Research on component contract testing with TypeScript

---

*Feature research for: Atom v5.2 Frontend Testing Coverage Expansion*
*Researched: March 3, 2026*
*Confidence: HIGH (mix of official docs, industry best practices, codebase analysis)*

# API Robustness Testing Guide

**Purpose**: Ensure frontend applications gracefully handle API failures, network issues, and edge cases.

**Tech Stack**: MSW (Mock Service Worker) + @lifeomic/attempt + React Testing Library

**Goals**:
- Retry transient failures with exponential backoff
- Display user-friendly error messages (not technical jargon)
- Show loading states during async operations
- Test error recovery flows end-to-end

---

## Table of Contents

1. [Overview](#overview)
2. [MSW Handler Usage](#msw-handler-usage)
3. [Error Message Mapping](#error-message-mapping)
4. [Retry Logic Configuration](#retry-logic-configuration)
5. [Loading State Testing](#loading-state-testing)
6. [Integration Testing Patterns](#integration-testing-patterns)
7. [Common Pitfalls](#common-pitfalls)
8. [CI/CD Integration](#cicd-integration)
9. [Troubleshooting](#troubleshooting)

---

## Overview

API robustness testing ensures your frontend app handles real-world API failures gracefully. Instead of only testing happy paths, we test:

- **Network failures**: Connection drops, timeouts
- **Server errors**: 500, 503, 504 responses
- **Client errors**: 401, 403, 404, 429 responses
- **Retry logic**: Exponential backoff, jitter
- **User experience**: Loading states, error messages, recovery actions

### Why API Robustness Matters

1. **Production reliability**: APIs fail unpredictably (network blips, server overload, rate limits)
2. **User trust**: Users see helpful messages, not technical errors
3. **Debugging**: Retry logic prevents false positives in monitoring
4. **Compliance**: Governance errors (403) require proper user feedback

### Testing Philosophy

```typescript
// ❌ Anti-pattern: Only test success path
test('loads agents', async () => {
  const { result } = renderHook(() => useAgents());
  await waitFor(() => expect(result.current.agents).toHaveLength(2));
});

// ✅ Pattern: Test success + failure + recovery
test('loads agents with retry on 503', async () => {
  server.use(...agentErrorHandlers.serviceUnavailable);
  const { result } = renderHook(() => useAgents());

  // Initial loading state
  expect(result.current.isLoading).toBe(true);

  // Service unavailable error
  await waitFor(() => expect(result.current.error).toBeTruthy());

  // Retry succeeds after error
  server.use(...agentHandlers); // Restore handler
  await waitFor(() => expect(result.current.agents).toHaveLength(2));
});
```

---

## MSW Handler Usage

MSW (Mock Service Worker) intercepts HTTP requests and returns mock responses. This enables testing API interactions without hitting real servers.

### Default Handlers

Default handlers simulate successful API responses:

```typescript
import { server } from '@/tests/mocks/server';
import { allHandlers } from '@/tests/mocks/handlers';

// In setupTests.ts or test file
beforeAll(() => {
  server.use(...allHandlers);
});

afterEach(() => {
  // Reset to default handlers after each test
  server.resetHandlers();
});
```

### Overriding Handlers for Error Scenarios

Override specific handlers to test error conditions:

```typescript
import { agentErrorHandlers } from '@/tests/mocks/handlers';
import { server } from '@/tests/mocks/server';

test('handles 500 error gracefully', async () => {
  // Override handler for this test
  server.use(...agentErrorHandlers.internalServerError);

  const { result } = renderHook(() => useAgents());
  await waitFor(() => {
    expect(result.current.error).toEqual('Something went wrong. Please try again.');
  });
});
```

### Available Error Scenario Handlers

#### Agent API Errors (`agentErrorHandlers`)

```typescript
import { agentErrorHandlers } from '@/tests/mocks/handlers';

// 500 Internal Server Error
server.use(...agentErrorHandlers.internalServerError);

// 503 Service Unavailable (with retry_after: 60)
server.use(...agentErrorHandlers.serviceUnavailable);

// 429 Rate Limited (with retry_after: 60)
server.use(...agentErrorHandlers.rateLimited);

// 404 Agent Not Found
server.use(...agentErrorHandlers.agentNotFound);

// 500 for agent status endpoint
server.use(...agentErrorHandlers.agentStatusError);

// Timeout (35s delay for chat/stream endpoint)
server.use(...agentErrorHandlers.chatStreamTimeout);

// 503 for chat/stream endpoint
server.use(...agentErrorHandlers.chatStreamUnavailable);
```

#### Canvas API Errors (`canvasErrorHandlers`)

```typescript
import { canvasErrorHandlers } from '@/tests/mocks/handlers';

// 403 Governance Check Failed (maturity level gate)
server.use(...canvasErrorHandlers.governanceCheckFailed);

// 500 for form submission
server.use(...canvasErrorHandlers.submitServerError);

// 503 for canvas service
server.use(...canvasErrorHandlers.submitServiceUnavailable);

// 404 Canvas Not Found
server.use(...canvasErrorHandlers.canvasNotFound);

// 504 Gateway Timeout for canvas status
server.use(...canvasErrorHandlers.canvasStatusTimeout);

// 403 for canvas execute action
server.use(...canvasErrorHandlers.executeGovernanceFailed);

// 500 for canvas execute
server.use(...canvasErrorHandlers.executeServerError);
```

#### Device API Errors (`deviceErrorHandlers`)

```typescript
import { deviceErrorHandlers } from '@/tests/mocks/handlers';

// 503 Camera Unavailable
server.use(...deviceErrorHandlers.cameraUnavailable);

// Timeout (35s delay) for camera snap
server.use(...deviceErrorHandlers.cameraTimeout);

// 403 Screen Recording Governance Failed
server.use(...deviceErrorHandlers.screenRecordingGovernanceFailed);

// 500 for screen recording
server.use(...deviceErrorHandlers.screenRecordingError);

// 503 Location Service Unavailable
server.use(...deviceErrorHandlers.locationUnavailable);

// 503 Network Error for location API
server.use(...deviceErrorHandlers.locationNetworkError);
```

#### Integration API Errors (`integrationErrorHandlers`)

```typescript
import { integrationErrorHandlers } from '@/tests/mocks/handlers';

// OAuth Access Denied (401) for all integrations
server.use(...integrationErrorHandlers.oauthAccessDenied);

// OAuth Timeout (35s delay)
server.use(...integrationErrorHandlers.oauthTimeout);

// 429 API Rate Limited (Jira, Slack)
server.use(...integrationErrorHandlers.apiRateLimited);

// 503 Service Unavailable
server.use(...integrationErrorHandlers.serviceUnavailable);
```

### Network Errors and Timeouts

```typescript
import { errorHandlers } from '@/tests/mocks/errors';

// Generic network failure
server.use(...errorHandlers.networkError);

// Request timeout
server.use(...errorHandlers.timeout);

// Slow response (5s delay for testing loading states)
server.use(...errorHandlers.slowResponse);

// Malformed JSON response
server.use(...errorHandlers.malformedResponse);

// Rate limited with retry-after header
server.use(...errorHandlers.rateLimited);
```

### Custom Error Handlers

Create custom error handlers for specific scenarios:

```typescript
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

test('handles custom error scenario', async () => {
  server.use(
    rest.post('/api/custom/endpoint', (req, res, ctx) => {
      return res(
        ctx.status(418), // I'm a teapot
        ctx.json({
          success: false,
          error_code: 'TEAPOT_ERROR',
          error: 'I am a teapot',
          message: 'This endpoint is a teapot.',
        })
      );
    })
  );

  // Test your component
});
```

---

## Error Message Mapping

Technical error responses from APIs must be translated to user-friendly messages. Use `error-mapping.ts` utilities.

### getUserFriendlyErrorMessage()

Converts API errors to user-facing messages:

```typescript
import { getUserFriendlyErrorMessage } from '@/lib/error-mapping';

// API error response
const apiError = {
  response: {
    status: 500,
    data: {
      error_code: 'INTERNAL_SERVER_ERROR',
      message: 'Database connection failed',
    },
  },
};

const userMessage = getUserFriendlyErrorMessage(apiError);
// Returns: "Something went wrong. Please try again later."
```

**Supported error codes**:

| Error Code | User Message |
|------------|--------------|
| `NETWORK_ERROR` | "Unable to connect. Please check your internet connection." |
| `TIMEOUT` | "Request timed out. Please try again." |
| `RATE_LIMIT_EXCEEDED` | "Too many requests. Please wait a few minutes." |
| `UNAUTHORIZED` | "Please log in to continue." |
| `FORBIDDEN` | "You don't have permission to perform this action." |
| `NOT_FOUND` | "The requested resource was not found." |
| `INTERNAL_SERVER_ERROR` | "Something went wrong. Please try again later." |
| `SERVICE_UNAVAILABLE` | "Service temporarily unavailable. Please try again later." |
| `GOVERNANCE_CHECK_FAILED` | "Agent maturity level insufficient for this action." |

### getErrorAction()

Provides recommended user actions for errors:

```typescript
import { getErrorAction } from '@/lib/error-mapping';

const action = getErrorAction({
  response: { status: 401 },
});
// Returns: "Please log in and try again."
```

### getErrorSeverity()

Categorizes errors by severity for UI treatment:

```typescript
import { getErrorSeverity } from '@/lib/error-mapping';

const severity = getErrorSeverity({
  response: { status: 500 },
});
// Returns: "high" (show error banner)

const severity = getErrorSeverity({
  response: { status: 404 },
});
// Returns: "medium" (show inline error)
```

### enhanceError()

Enriches error objects with user-friendly properties:

```typescript
import { enhanceError } from '@/lib/error-mapping';

const error = new Error('Network request failed');
const enhanced = enhanceError(error);

console.log(enhanced.userMessage); // "Unable to connect..."
console.log(enhanced.severity); // "high"
console.log(enhanced.action); // "Check your internet connection..."
console.log(enhanced.isRetryable); // true
```

### Testing Error Messages

```typescript
import { getUserFriendlyErrorMessage } from '@/lib/error-mapping';
import { agentErrorHandlers } from '@/tests/mocks/handlers';

test('shows user-friendly error on 500', async () => {
  server.use(...agentErrorHandlers.internalServerError);

  render(<AgentList />);

  // Wait for error message
  await waitFor(() => {
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  // Verify no technical jargon
  expect(screen.queryByText(/internal server error/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/500/i)).not.toBeInTheDocument();
});
```

---

## Retry Logic Configuration

Atom uses `@lifeomic/attempt` for automatic retry with exponential backoff and jitter.

### Retry Configuration

```typescript
// lib/api.ts
import { retry } from '@lifeomic/attempt';

const response = await retry(
  async () => {
    return await apiClient(originalRequest);
  },
  {
    maxAttempts: 3,           // Maximum retry attempts
    delay: 1000,              // Initial delay (1 second)
    factor: 2,                // Exponential backoff: 1s, 2s, 4s
    jitter: true,             // Add randomness to prevent retry storms
    minDelay: 500,            // Minimum delay (500ms)
    maxDelay: 10000,          // Maximum delay (10 seconds)
    timeout: 10000,           // Request timeout (10 seconds)
    handleError: (attemptError) => {
      // Return true to retry, false to stop
      return isRetryableError(attemptError);
    },
    beforeAttempt: (context) => {
      // Log retry attempts
      if (context.attemptNum > 1) {
        console.log(`Retry attempt ${context.attemptNum} of ${MAX_RETRIES}`);
      }
    },
  }
);
```

### Retryable vs Non-Retryable Errors

```typescript
// lib/error-mapping.ts
export const isRetryableError = (error: any): boolean => {
  const status = error.response?.status;

  // Retry on network errors and 5xx errors
  if (!status) return true; // Network error
  if (status >= 500) return true; // Server errors
  if (status === 429) return true; // Rate limit
  if (status === 408 || status === 504) return true; // Timeouts

  // Don't retry client errors (4xx except 429)
  return false;
};
```

**Retryable errors**:
- Network failures (no status code)
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout
- 429 Rate Limited
- 408 Request Timeout

**Non-retryable errors**:
- 400 Bad Request (validation error)
- 401 Unauthorized (authentication required)
- 403 Forbidden (authorization/governance failed)
- 404 Not Found (resource missing)
- 422 Unprocessable Entity (validation error)

### Exponential Backoff with Jitter

Exponential backoff increases delay between retries:
- Attempt 1: 1s (base delay)
- Attempt 2: 2s (1s × 2)
- Attempt 3: 4s (2s × 2)

**Jitter** adds randomness to prevent retry storms (synchronized retries from multiple clients):

```typescript
// Without jitter (synchronized retries)
Client 1: 1s → 2s → 4s
Client 2: 1s → 2s → 4s
Client 3: 1s → 2s → 4s
// Result: Server receives 3 requests at 1s, 3 requests at 2s, 3 requests at 4s

// With jitter (randomized delays)
Client 1: 1.2s → 2.3s → 4.1s
Client 2: 0.8s → 1.7s → 3.9s
Client 3: 1.5s → 2.8s → 4.5s
// Result: Requests spread out over time, reducing server load
```

### Testing Retry Logic

```typescript
import { agentErrorHandlers } from '@/tests/mocks/handlers';

test('retries 503 error before showing error', async () => {
  // Track request count
  let requestCount = 0;
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      requestCount++;
      return res(
        ctx.status(503),
        ctx.json({ error: 'Service unavailable' })
      );
    })
  );

  render(<AgentList />);

  // Wait for retry attempts (maxAttempts: 3)
  await waitFor(() => {
    expect(requestCount).toBe(3);
  });

  // Verify error message shown after retries exhausted
  expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
});
```

```typescript
test('recovers from 503 on second attempt', async () => {
  let requestCount = 0;
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      requestCount++;
      if (requestCount === 1) {
        // First attempt fails
        return res(ctx.status(503), ctx.json({ error: 'Service unavailable' }));
      }
      // Second attempt succeeds
      return res(ctx.status(200), ctx.json({ agents: [] }));
    })
  );

  render(<AgentList />);

  // Verify success after retry
  await waitFor(() => {
    expect(screen.getByText(/no agents/i)).toBeInTheDocument();
  });
});
```

---

## Loading State Testing

Loading states provide feedback during async operations. Test them with `waitFor` and `findBy*` queries.

### Testing Skeleton Loaders

```typescript
import { waitFor, findByText } from '@testing-library/react';
import { canvasErrorHandlers } from '@/tests/mocks/handlers';

test('shows skeleton loader while loading agents', async () => {
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(ctx.delay(2000), ctx.json({ agents: [] }));
    })
  );

  render(<AgentList />);

  // Skeleton loader visible immediately
  expect(screen.getByTestId('agent-list-skeleton')).toBeInTheDocument();

  // Skeleton loader removed after data loads
  await waitFor(() => {
    expect(screen.queryByTestId('agent-list-skeleton')).not.toBeInTheDocument();
  });
});
```

### Testing Submit Button Disabled State

```typescript
test('disables submit button while submitting form', async () => {
  server.use(
    rest.post('/api/canvas/submit', (req, res, ctx) => {
      return res(ctx.delay(2000), ctx.json({ success: true }));
    })
  );

  render(<CanvasForm />);

  const submitButton = screen.getByRole('button', { name: /submit/i });

  // Button enabled initially
  expect(submitButton).not.toBeDisabled();

  // Click submit
  fireEvent.click(submitButton);

  // Button disabled during submission
  await waitFor(() => {
    expect(submitButton).toBeDisabled();
    expect(submitButton).toHaveTextContent(/submitting/i);
  });

  // Button re-enabled after submission
  await waitFor(() => {
    expect(submitButton).not.toBeDisabled();
    expect(submitButton).toHaveTextContent(/submit/i);
  });
});
```

### Testing Slow Endpoints with ctx.delay()

```typescript
test('shows loading indicator for slow endpoint', async () => {
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      // Simulate 3 second delay
      return res(ctx.delay(3000), ctx.json({ agents: [] }));
    })
  );

  render(<AgentList />);

  // Loading indicator visible
  expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

  // Wait for data to load
  await waitFor(() => {
    expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
  }, { timeout: 5000 });
});
```

### Testing Timeout Handling

```typescript
test('shows timeout message after 10s delay', async () => {
  server.use(
    rest.post('/api/canvas/submit', async (req, res, ctx) => {
      // Delay exceeds API_TIMEOUT (10s)
      await new Promise((resolve) => setTimeout(resolve, 35000));
      return res(ctx.status(200), ctx.json({ success: true }));
    })
  );

  render(<CanvasForm />);

  fireEvent.click(screen.getByRole('button', { name: /submit/i }));

  // Wait for timeout error
  await waitFor(() => {
    expect(screen.getByText(/request timed out/i)).toBeInTheDocument();
  }, { timeout: 40000 });
});
```

---

## Integration Testing Patterns

Integration tests verify complete error recovery flows from UI to API.

### Pattern 1: Error Recovery Flow

```typescript
test('recovers from 503 error and loads data', async () => {
  let shouldFail = true;
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      if (shouldFail) {
        return res(ctx.status(503), ctx.json({ error: 'Service unavailable' }));
      }
      return res(ctx.status(200), ctx.json({ agents: mockAgents }));
    })
  );

  render(<AgentList />);

  // Show error state
  await waitFor(() => {
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
  });

  // Show retry button
  const retryButton = screen.getByRole('button', { name: /retry/i });
  expect(retryButton).toBeInTheDocument();

  // Simulate server recovery
  shouldFail = false;
  fireEvent.click(retryButton);

  // Verify success state
  await waitFor(() => {
    expect(screen.getByText('Test Agent 1')).toBeInTheDocument();
  });
});
```

### Pattern 2: Component-Level Error Handling

```typescript
test('component handles error boundary gracefully', async () => {
  // Mock console.error to reduce test noise
  const consoleError = jest.spyOn(console, 'error').mockImplementation();

  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
    })
  );

  render(<AgentList />);

  // Verify error fallback UI
  await waitFor(() => {
    expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  consoleError.mockRestore();
});
```

### Pattern 3: Mocking Network Recovery

```typescript
test('automatically retries on network recovery', async () => {
  let isOnline = false;
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      if (!isOnline) {
        // Simulate network error (503 in Node.js)
        return res(ctx.status(503), ctx.json({ error: 'Network error' }));
      }
      return res(ctx.status(200), ctx.json({ agents: mockAgents }));
    })
  );

  render(<AgentList />);

  // Show offline message
  await waitFor(() => {
    expect(screen.getByText(/offline/i)).toBeInTheDocument();
  });

  // Simulate network recovery
  isOnline = true;
  window.dispatchEvent(new Event('online'));

  // Verify data loads after recovery
  await waitFor(() => {
    expect(screen.getByText('Test Agent 1')).toBeInTheDocument();
  });
});
```

### Pattern 4: Testing Retry Exhaustion

```typescript
test('shows error after 3 retry attempts', async () => {
  let attemptCount = 0;
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      attemptCount++;
      return res(ctx.status(503), ctx.json({ error: 'Service unavailable' }));
    })
  );

  render(<AgentList />);

  // Wait for all retries to exhaust (maxAttempts: 3)
  await waitFor(() => {
    expect(attemptCount).toBe(3);
  }, { timeout: 10000 });

  // Verify final error state
  expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
  expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
});
```

---

## Common Pitfalls

### Pitfall 1: Using fakeTimers for Loading Tests

```typescript
// ❌ Anti-pattern: fakeTimers don't work with real async operations
jest.useFakeTimers();
test('shows loading state', () => {
  render(<AgentList />);
  jest.advanceTimersByTime(1000);
  expect(screen.getByText(/loading/i)).toBeInTheDocument();
});

// ✅ Pattern: Use waitFor with real timers
test('shows loading state', async () => {
  render(<AgentList />);
  await waitFor(() => {
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
```

**Why**: fakeTimers don't advance real Promises/Microtasks. Use `waitFor` for async operations.

### Pitfall 2: Testing Technical Error Messages

```typescript
// ❌ Anti-pattern: Test technical error details
test('shows 500 error', async () => {
  server.use(...agentErrorHandlers.internalServerError);
  render(<AgentList />);
  await waitFor(() => {
    expect(screen.getByText(/500 internal server error/i)).toBeInTheDocument();
  });
});

// ✅ Pattern: Test user-friendly error messages
test('shows user-friendly error on 500', async () => {
  server.use(...agentErrorHandlers.internalServerError);
  render(<AgentList />);
  await waitFor(() => {
    expect(screen.getByText(/something went wrong. please try again later/i)).toBeInTheDocument();
  });
});
```

**Why**: Users shouldn't see technical jargon. Test what users actually see.

### Pitfall 3: Retrying 4xx Errors

```typescript
// ❌ Anti-pattern: Retry all errors including 4xx
handleError: (error) => {
  return error.response?.status >= 400; // Wrong!
}

// ✅ Pattern: Only retry 5xx and network errors
handleError: (error) => {
  return isRetryableError(error); // Correct
}
```

**Why**: 4xx errors (400, 401, 403, 404) are client errors and won't fix themselves with retries.

### Pitfall 4: Missing Jitter in Exponential Backoff

```typescript
// ❌ Anti-pattern: No jitter (synchronized retries)
{
  delay: 1000,
  factor: 2,
  jitter: false, // Missing!
}

// ✅ Pattern: Always use jitter
{
  delay: 1000,
  factor: 2,
  jitter: true, // Prevents retry storms
}
```

**Why**: Synchronized retries cause "retry storms" that overload servers.

### Pitfall 5: Not Testing Loading States

```typescript
// ❌ Anti-pattern: Skip loading state testing
test('loads agents', async () => {
  render(<AgentList />);
  await waitFor(() => {
    expect(screen.getByText('Test Agent 1')).toBeInTheDocument();
  });
});

// ✅ Pattern: Test loading state transition
test('shows loading state while loading agents', async () => {
  server.use(
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(ctx.delay(2000), ctx.json({ agents: mockAgents }));
    })
  );

  render(<AgentList />);

  // Verify loading state
  expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();

  // Verify success state
  await waitFor(() => {
    expect(screen.getByText('Test Agent 1')).toBeInTheDocument();
    expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
  });
});
```

**Why**: Users need feedback during async operations. Test the complete UX.

---

## CI/CD Integration

API robustness tests run automatically in CI/CD on every pull request.

### Running Tests Locally

```bash
# Run all API robustness tests
npm test -- lib/__tests__/api/

# Run specific test file
npm test -- lib/__tests__/api/retry-logic.test.ts

# Run with coverage
npm test -- lib/__tests__/api/ --coverage
```

### CI/CD Workflow

`.github/workflows/frontend-api-robustness.yml`:

```yaml
name: Frontend API Robustness Tests

on:
  push:
    paths:
      - 'frontend-nextjs/lib/api.ts'
      - 'frontend-nextjs/lib/__tests__/api/**'
  pull_request:
    paths:
      - 'frontend-nextjs/lib/api.ts'
      - 'frontend-nextjs/lib/__tests__/api/**'

jobs:
  retry-logic-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend-nextjs/package-lock.json
      - name: Install dependencies
        working-directory: ./frontend-nextjs
        run: npm ci --legacy-peer-deps
      - name: Run retry logic tests
        working-directory: ./frontend-nextjs
        run: npm test -- lib/__tests__/api/retry-logic.test.ts

  error-message-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Run error message tests
        working-directory: ./frontend-nextjs
        run: npm test -- lib/__tests__/api/user-friendly-errors.test.ts

  loading-state-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Run loading state tests
        working-directory: ./frontend-nextjs
        run: npm test -- lib/__tests__/api/loading-states.test.ts

  integration-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Run integration tests
        working-directory: ./frontend-nextjs
        run: npm test -- tests/integration/api-robustness.test.tsx

  coverage-check:
    runs-on: ubuntu-latest
    needs: [retry-logic-tests, error-message-tests, loading-state-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Check api.ts coverage (80% minimum)
        working-directory: ./frontend-nextjs
        run: |
          npm test -- lib/__tests__/api/ --coverage --testNamePattern="api"
          if [ $(cat coverage/coverage-summary.json | jq '.total.lines.pct') -lt 80 ]; then
            echo "Coverage below 80% threshold"
            exit 1
          fi
```

### Coverage Requirements

- `lib/api.ts`: **80% minimum** coverage
- `lib/error-mapping.ts`: **90% minimum** coverage
- Overall API integration: **75% minimum** coverage

### Test Execution Time

| Test Suite | Expected Time | Timeout |
|------------|---------------|---------|
| Retry logic tests | ~30s | 2min |
| Error message tests | ~20s | 1min |
| Loading state tests | ~40s | 2min |
| Integration tests | ~90s | 5min |

**Total**: ~3 minutes for full API robustness test suite

---

## Troubleshooting

### MSW Handler Not Responding

**Problem**: Test shows real network error instead of mocked response

```typescript
// Test fails with "Network request failed"
test('loads agents', async () => {
  server.use(...agentHandlers);
  render(<AgentList />);
  // Error: Network request failed
});
```

**Solution**: Ensure MSW server is listening

```typescript
// In setupTests.ts or test file
import { server } from '@/tests/mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Retry Not Triggering

**Problem**: 503 error doesn't trigger retry

**Solution**: Check `isRetryableError` function

```typescript
// lib/error-mapping.ts
export const isRetryableError = (error: any): boolean => {
  const status = error.response?.status;

  // Log for debugging
  console.log('isRetryableError:', { status, error });

  if (!status) return true; // Network error
  if (status >= 500) return true; // Server errors
  if (status === 429) return true; // Rate limit

  return false; // Don't retry 4xx errors
};
```

### Loading State Not Visible

**Problem**: Test doesn't catch loading state before data loads

**Solution**: Use `findBy*` queries or `waitFor`

```typescript
// ❌ Fails: Loading state disappears before getBy* checks
test('shows loading state', () => {
  render(<AgentList />);
  expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
});

// ✅ Works: findBy* waits for element to appear
test('shows loading state', async () => {
  render(<AgentList />);
  expect(await screen.findByTestId('loading-spinner')).toBeInTheDocument();
});
```

### Test Flakiness with Async Operations

**Problem**: Test passes sometimes, fails sometimes

**Solution**: Increase `waitFor` timeout or use `waitForElementToBeRemoved`

```typescript
// Default timeout is 1000ms, may be too short
await waitFor(() => {
  expect(screen.getByText('Test Agent')).toBeInTheDocument();
}, { timeout: 3000 });

// Or use waitForElementToBeRemoved for loading states
await waitForElementToBeRemoved(() => screen.queryByTestId('loading-spinner'));
```

### Coverage Below Threshold

**Problem**: CI fails due to coverage below 80%

**Solution**: Check uncovered lines and add tests

```bash
# Generate coverage report
npm test -- lib/__tests__/api/ --coverage

# View uncovered lines
open coverage/lcov-report/index.html

# Add tests for uncovered branches
```

---

## Summary

API robustness testing ensures your frontend app handles real-world API failures gracefully:

1. **MSW handlers**: Mock success and error scenarios
2. **Error messages**: User-friendly, not technical
3. **Retry logic**: Exponential backoff with jitter
4. **Loading states**: Visual feedback during async operations
5. **Integration tests**: Complete error recovery flows

**Key takeaways**:
- Test both success and failure paths
- Use user-friendly error messages
- Add jitter to retry logic
- Test loading state transitions
- Avoid fakeTimers for async tests

**Resources**:
- [MSW Documentation](https://mswjs.io/)
- [@lifeomic/attempt Documentation](https://github.com/lifeomic/attempt)
- [React Testing Library](https://testing-library.com/react)
- [Error Mapping Utilities](../lib/error-mapping.ts)
- [MSW Handlers](../tests/mocks/handlers.ts)

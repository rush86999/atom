# Phase 131: Frontend Custom Hook Testing - Research

**Researched:** March 3, 2026
**Domain:** React Hook Testing with @testing-library/react
**Confidence:** HIGH

## Summary

Phase 131 requires testing React custom hooks in isolation to achieve 85% coverage (up from 14.56% current). The codebase has 26 custom hooks with only 3 test files currently. The project uses `@testing-library/react` v16.3.0 which includes `renderHook` functionality (the standalone `@testing-library/react-hooks` package is deprecated).

Hook testing follows the "renderHook" pattern where hooks are called directly in a test environment without requiring wrapper components. Key testing challenges include: async operations (fetch, WebSocket), side effects (useEffect cleanup), browser APIs (SpeechRecognition, WebSocket), state transitions, and error handling.

**Primary recommendation:** Use `renderHook` from `@testing-library/react` with proper `act()` wrapping for state updates, `waitFor` for async operations, and comprehensive cleanup testing to prevent memory leaks. Focus on behavior testing over implementation details, and ensure all 26 hooks have dedicated test files covering mount/update/unmount lifecycles.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@testing-library/react` | 16.3.0 | Hook testing via renderHook | Merged from @testing-library/react-hooks in v13, official React testing library |
| `jest` | 30.0.5 | Test runner | Project standard, full ecosystem support |
| `jest-environment-jsdom` | 30.0.5 | Browser environment simulation | Required for DOM/testing-library |
| `@testing-library/jest-dom` | 6.6.3 | DOM matchers | Enhanced Jest assertions for DOM elements |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@testing-library/user-event` | 14.6.1 | User interaction simulation | Not directly for hooks, but for integration tests |
| `msw` | 1.3.5 | API mocking | For hooks that make fetch calls (useChatMemory, useUserActivity) |
| `jest-fetch-mock` | (add if needed) | Fetch API mocking | Alternative to MSW for simpler fetch mocking |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@testing-library/react` renderHook | `@testing-library/react-hooks` | Deprecated, merged into main package in v13 |
| `msw` | `jest.spyOn(global, 'fetch')` | MSW provides more realistic interception, spyOn is simpler but less comprehensive |
| `renderHook` | Component wrapper tests | renderHook is designed for hooks, component tests are integration-level |

**Installation:**
```bash
# Already installed in project
npm install --save-dev @testing-library/react@16.3.0 jest@30.0.5

# For fetch mocking (optional, currently using jest.fn())
npm install --save-dev msw@1.3.5
```

## Architecture Patterns

### Recommended Test Structure
```
frontend-nextjs/
├── hooks/
│   ├── useCanvasState.ts
│   ├── useChatMemory.ts
│   ├── useWebSocket.ts
│   ├── useUserActivity.ts
│   ├── useSpeechRecognition.ts
│   └── ... (26 total hooks)
└── hooks/__tests__/
    ├── useCanvasState.test.ts
    ├── useChatMemory.test.ts
    ├── useWebSocket.test.ts
    ├── useUserActivity.test.ts
    ├── useSpeechRecognition.test.ts
    └── ... (one test file per hook)
```

### Pattern 1: Basic Hook Testing with renderHook
**What:** Test custom hooks in isolation without requiring wrapper components
**When to use:** All custom hook testing
**Example:**
```typescript
// Source: @testing-library/react v16+ documentation
import { renderHook, act } from '@testing-library/react';
import { useCounter } from '../useCounter';

test('increments count', () => {
  const { result } = renderHook(() => useCounter());

  expect(result.current.count).toBe(0);

  act(() => {
    result.current.increment();
  });

  expect(result.current.count).toBe(1);
});
```

### Pattern 2: Async Hook Testing with waitFor
**What:** Test hooks with async operations (fetch, timers)
**When to use:** Hooks with useEffect performing async operations
**Example:**
```typescript
// Source: React Hooks Testing Strategy Guide (2026)
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatMemory } from '../useChatMemory';

test('stores memory successfully', async () => {
  const mockResponse = { status: 'success', memory_id: 'mem-123' };
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => mockResponse,
  });

  const { result } = renderHook(() =>
    useChatMemory({
      userId: 'user-1',
      sessionId: 'session-1',
      enableMemory: true,
    })
  );

  await act(async () => {
    await result.current.storeMemory({
      userId: 'user-1',
      sessionId: 'session-1',
      role: 'user',
      content: 'test message',
      metadata: {
        messageType: 'text',
        importance: 0.5,
        accessCount: 0,
        lastAccessed: new Date(),
      },
    });
  });

  await waitFor(() => {
    expect(result.current.memories).toHaveLength(1);
    expect(result.current.memories[0].id).toBe('mem-123');
  });
});
```

### Pattern 3: Cleanup Testing for Memory Leaks
**What:** Verify useEffect cleanup functions prevent memory leaks
**When to use:** Hooks with subscriptions, timers, event listeners, WebSocket connections
**Example:**
```typescript
// Source: React Hooks Side Effects Testing Guide (2025)
import { renderHook } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

test('cleans up WebSocket connection on unmount', () => {
  const wsCloseSpy = jest.fn();
  global.WebSocket = jest.fn(() => ({
    close: wsCloseSpy,
    send: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  })) as any;

  const { unmount } = renderHook(() => useWebSocket({ url: 'ws://localhost:8000' }));

  expect(wsCloseSpy).not.toHaveBeenCalled();

  unmount();

  expect(wsCloseSpy).toHaveBeenCalledTimes(1);
});
```

### Pattern 4: Testing Browser API Mocking
**What:** Mock browser APIs (SpeechRecognition, Navigator, WebSocket)
**When to use:** Hooks that access window/global browser APIs
**Example:**
```typescript
// Source: Custom pattern for useSpeechRecognition
import { renderHook, act } from '@testing-library/react';
import { useSpeechRecognition } from '../useSpeechRecognition';

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

test('initializes speech recognition', () => {
  const mockRecognition = {
    start: jest.fn(),
    stop: jest.fn(),
    continuous: true,
    interimResults: true,
    lang: 'en-US',
    onresult: null,
    onerror: null,
    onend: null,
  };

  window.SpeechRecognition = jest.fn(() => mockRecognition) as any;

  const { result } = renderHook(() => useSpeechRecognition());

  expect(result.current.browserSupportsSpeechRecognition).toBe(true);
  expect(window.SpeechRecognition).toHaveBeenCalledWith();
});
```

### Pattern 5: State Transition Testing
**What:** Test all possible state changes in a hook
**When to use:** Hooks with complex state machines (loading, success, error, idle)
**Example:**
```typescript
// Source: useChatMemory test pattern
import { renderHook, act, waitFor } from '@testing-library/react';

test('transitions through loading states', async () => {
  const { result } = renderHook(() =>
    useChatMemory({
      userId: 'user-1',
      sessionId: 'session-1',
      enableMemory: true,
    })
  );

  // Initial state
  expect(result.current.isLoading).toBe(false);
  expect(result.current.error).toBeNull();

  // Trigger loading
  await act(async () => {
    result.current.getMemoryContext('test message');
  });

  // Loading state
  expect(result.current.isLoading).toBe(true);

  // Wait for completion
  await waitFor(() => {
    expect(result.current.isLoading).toBe(false);
  });
});
```

### Anti-Patterns to Avoid
- **Testing implementation details**: Don't test internal useState calls, test behavior
- **Destructuring result.current**: `const { count } = result.current` is stale after updates, always access directly
- **Forgetting act()**: State updates must be wrapped in `act()` to avoid React warnings
- **Ignoring cleanup**: Always test unmount/cleanup to prevent memory leaks
- **Testing without waitFor**: Async assertions need `waitFor` to avoid flaky tests
- **Over-mocking**: Don't mock React itself or the hook being tested

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hook test runner | Custom wrapper component with hooks | `renderHook` from @testing-library/react | Designed for hook testing, handles unmounting, rerendering, and result tracking |
| Async waiting | Custom setTimeout/setInterval loops | `waitFor` from @testing-library/react | Built-in timeout, retry logic, integrates with React's act() |
| Fetch mocking | Manual XMLHttpRequest mocking | `jest.spyOn(global, 'fetch')` or `msw` | Simpler, more reliable, supports network interception |
| DOM environment | Custom jsdom setup | `jest-environment-jsdom` | Official Jest environment, maintained by Jest team |
| Timer mocking | Custom date/time manipulation | `jest.useFakeTimers()` | Built-in Jest feature, handles setTimeout/setInterval/clearInterval |

**Key insight:** Custom solutions for hook testing are error-prone and miss edge cases. The @testing-library/react ecosystem handles React's batching, unmounting, and effect scheduling correctly.

## Common Pitfalls

### Pitfall 1: Missing act() Wrappers
**What goes wrong:** Tests pass but React warns "An update to TestComponent inside a test was not wrapped in act(...)"
**Why it happens:** State updates outside act() aren't batched properly by React
**How to avoid:** Always wrap state-triggering functions in `act(() => { ... })`
**Warning signs:** React console warnings in test output, flaky tests

### Pitfall 2: Async Operations Without waitFor
**What goes wrong:** Tests fail intermittently because assertions run before async operations complete
**Why it happens:** fetch/promises aren't awaited in tests
**How to avoid:** Use `await waitFor(() => expect(...))` for async assertions
**Warning signs:** Flaky tests that pass sometimes and fail other times

### Pitfall 3: Not Testing Cleanup Functions
**What goes wrong:** Memory leaks in production from unsubscribed events, open WebSocket connections, running timers
**Why it happens:** Cleanup functions in useEffect return statements aren't tested
**How to avoid:** Always test unmounting with `unmount()` and verify cleanup was called
**Warning signs:** Browser console warnings about memory leaks, performance degradation

### Pitfall 4: Mocking Browser APIs Incorrectly
**What goes wrong:** Tests fail because browser APIs (SpeechRecognition, WebSocket) don't exist in jsdom
**Why it happens:** jsdom doesn't implement all browser APIs
**How to avoid:** Mock global browser APIs before rendering hooks
**Warning signs:** "undefined is not a constructor", "X is not defined" errors

### Pitfall 5: Testing Component Integration Instead of Hook Behavior
**What goes wrong:** Tests become integration tests, harder to maintain, slower to run
**Why it happens:** Testing hooks through component wrappers instead of renderHook
**How to avoid:** Use `renderHook()` for isolated hook testing, component tests for integration
**Warning signs:** Test file imports React components just to test a hook

### Pitfall 6: Forgetting to Clear Mocks Between Tests
**What goes wrong:** Mock state from previous tests leaks into subsequent tests
**Why it happens:** jest.fn() mocks accumulate calls across tests
**How to avoid:** Use `beforeEach(() => jest.clearAllMocks())` in test suites
**Warning signs:** Tests pass in isolation but fail when run with other tests

## Code Examples

Verified patterns from official sources and existing codebase:

### Testing useCanvasState with Mock Global API
```typescript
// Source: frontend-nextjs/hooks/__tests__/useCanvasState.api.test.ts (existing)
import { renderHook, act, waitFor } from '@testing-library/react';
import useCanvasState from '@/hooks/useCanvasState';

function setupWindowAtomCanvas() {
  if (typeof window !== 'undefined') {
    delete (window as any).atom;

    const subscribers = new Set<(state: any) => void>();
    const states = new Map<string, any>();

    (window as any).atom = {
      canvas: {
        getState: (canvasId: string) => states.get(canvasId) || null,
        subscribe: (callback: (state: any) => void) => {
          subscribers.add(callback);
          return () => subscribers.delete(callback);
        },
        _setState: (canvasId: string, state: any) => {
          states.set(canvasId, state);
          subscribers.forEach(cb => cb(state));
        },
      },
    };
  }
}

test('subscribes to specific canvas state', () => {
  setupWindowAtomCanvas();

  const { result } = renderHook(() => useCanvasState('canvas-123'));

  expect(result.current.state).toBeNull();

  act(() => {
    (window as any).atom.canvas._setState('canvas-123', {
      canvas_id: 'canvas-123',
      canvas_type: 'generic',
      status: 'active',
    });
  });

  expect(result.current.state).toEqual(
    expect.objectContaining({ canvas_id: 'canvas-123', status: 'active' })
  );
});
```

### Testing useWebSocket with Lifecycle
```typescript
// Source: frontend-nextjs/hooks/__tests__/useWebSocket.test.ts (existing pattern)
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

test('connects and disconnects WebSocket', () => {
  const mockWs = {
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    readyState: WebSocket.CONNECTING,
  };

  global.WebSocket = jest.fn(() => mockWs) as any;

  const { unmount } = renderHook(() =>
    useWebSocket({ url: 'ws://localhost:8000', autoConnect: true })
  );

  expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws?token=dev-token');

  unmount();

  expect(mockWs.close).toHaveBeenCalled();
});
```

### Testing useUserActivity with Timers
```typescript
// Source: Pattern from useUserActivity.ts implementation
import { renderHook, act } from '@testing-library/react';
import { useUserActivity } from '../useUserActivity';

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
});

test('sends heartbeat on interval', () => {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({ state: 'online', last_activity_at: new Date().toISOString() }),
  });

  const { result } = renderHook(() =>
    useUserActivity({
      userId: 'user-1',
      enabled: true,
      interval: 30000,
    })
  );

  // Initial heartbeat
  expect(global.fetch).toHaveBeenCalledWith(
    '/api/users/user-1/activity/heartbeat',
    expect.objectContaining({
      method: 'POST',
    })
  );

  // Fast-forward 30 seconds
  act(() => {
    jest.advanceTimersByTime(30000);
  });

  // Second heartbeat
  expect(global.fetch).toHaveBeenCalledTimes(2);
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@testing-library/react-hooks` standalone | Merged into `@testing-library/react` v13+ | 2022 (React 18 era) | Single import for all React testing, better TypeScript support |
| Component wrapper tests | `renderHook()` for isolation | 2019 | Hooks testable without components, faster test execution |
| Manual setTimeout for async | `waitFor()` with built-in retry | 2020 | More reliable async tests, custom timeouts, better error messages |
|jest.useFakeTimers() required for all async tests | `waitFor()` can handle real promises in most cases | 2021 | Simpler async testing, fake timers only when needed |

**Deprecated/outdated:**
- **@testing-library/react-hooks**: Merged into main package, use `@testing-library/react` instead
- **Enzyme for hooks**: Enzyme doesn't support hooks well, use Testing Library
- **Shallow rendering hooks**: Doesn't work, must use `renderHook()` or full rendering

## Open Questions

1. **WebSocket testing complexity**
   - What we know: useWebSocket uses native WebSocket API, needs mocking
   - What's unclear: How to test WebSocket message events and reconnection logic thoroughly
   - Recommendation: Use jest.fn() to mock WebSocket class, trigger onmessage callbacks manually in tests

2. **SpeechRecognition browser API support**
   - What we know: useSpeechRecognition requires window.SpeechRecognition or webkitSpeechRecognition
   - What's unclear: Full test coverage for wake word logic and auto-restart behavior
   - Recommendation: Mock SpeechRecognition constructor, test onresult/onerror/onend callbacks by calling them directly

3. **Timer cleanup in production**
   - What we know: useUserActivity uses setInterval and clearTimeout in cleanup
   - What's unclear: Whether all timer-based hooks properly clean up on unmount
   - Recommendation: Add unmount tests for all hooks with timers (useUserActivity, useSpeechRecognition, useWebSocket)

## Sources

### Primary (HIGH confidence)
- `@testing-library/react` v16.3.0 - renderHook API documentation (installed in project)
- `frontend-nextjs/hooks/__tests__/useCanvasState.api.test.ts` - Existing test patterns (verified in codebase)
- `frontend-nextjs/hooks/__tests__/useChatMemory.test.ts` - Async hook testing patterns (verified in codebase)
- `frontend-nextjs/hooks/__tests__/useWebSocket.test.ts` - WebSocket testing patterns (verified in codebase)
- `frontend-nextjs/hooks/useCanvasState.ts` - Hook implementation complexity (verified in codebase)
- `frontend-nextjs/hooks/useChatMemory.ts` - Async state management (verified in codebase)
- `frontend-nextjs/hooks/useWebSocket.ts` - Side effects and cleanup (verified in codebase)
- `frontend-nextjs/hooks/useUserActivity.ts` - Timer and event listener patterns (verified in codebase)
- `frontend-nextjs/hooks/useSpeechRecognition.ts` - Browser API integration (verified in codebase)
- `frontend-nextjs/jest.config.js` - Jest configuration and coverage thresholds (verified in codebase)

### Secondary (MEDIUM confidence)
- [React Hooks Testing Strategy Guide](https://m.blog.csdn.net/2509_93945744/article/details/155161142) (November 2025) - Comprehensive testing strategies
- [React Hooks Side Effects Testing Guide](https://m.blog.csdn.net/gitblog_00803/article/details/153761497) (December 2025) - useEffect and cleanup testing
- [React Hooks Testing Anti-Patterns](https://m.blog.csdn.net/gitblog_00279/article/details/155516672) (January 2026) - Common mistakes to avoid
- [Async Testing with act() and waitFor](https://m.blog.csdn.net/gitblog_00420/article/details/151447654) (February 2026) - act() warning solutions
- [React 18 Hooks Testing Migration](https://m.blog.csdn.net/gitblog_01021/article/details/153756283) - react-hooks-testing-library migration guide
- [React Testing Library Async Solutions](https://m.blog.csdn.net/gitblog_00766/article/details/154894551) (November 2025) - waitFor and findBy queries
- [5 Common React Hooks Testing Scenarios](https://m.blog.csdn.net/gitblog_00214/article/details/153755537) - Scenario-based testing patterns
- [State Management Hooks Testing](https://blog.csdn.net/gitblog_00926/article/details/153761731) - useState/useReducer testing

### Tertiary (LOW confidence)
- [React Hooks Deep Dive: Patterns, Pitfalls](https://dev.to/a1guy/react-hooks-deep-dive-patterns-pitfalls-and-practical-hooks-424k) (August 2025) - General hook patterns, not testing-specific
- [Frontend Testing Ultimate Guide](https://m.blog.csdn.net/gitblog_00537/article/details/151171098) (February 2026) - Broad testing overview, needs verification for 2026 best practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in package.json, official documentation confirms renderHook merge
- Architecture: HIGH - Existing test files in codebase demonstrate working patterns, verified renderHook usage
- Pitfalls: HIGH - Multiple sources corroborate common issues (act warnings, async without waitFor, cleanup testing)

**Research date:** March 3, 2026
**Valid until:** April 2, 2026 (30 days - stable ecosystem, mature testing patterns)

**Key Implementation Insights:**
1. 26 hooks need test files (currently only 3 exist: useCanvasState, useChatMemory, useWebSocket)
2. Current hooks coverage: 14.56% → Target: 85% (70.44 percentage point gap)
3. Complex hooks requiring special attention:
   - `useUserActivity`: Timers (setInterval), event listeners, fetch calls
   - `useSpeechRecognition`: Browser API (SpeechRecognition), wake word logic
   - `useWebSocket`: Native WebSocket API, reconnection logic
   - `useChatMemory`: Async fetch operations, error handling
   - `useCanvasState`: Global window.atom.canvas API
4. Coverage thresholds defined in jest.config.js: branches 80%, functions 85%, lines 85%, statements 85% for hooks directory

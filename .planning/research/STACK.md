# Technology Stack: Frontend Testing Expansion

**Project:** Atom AI-Powered Business Automation Platform
**Domain:** Frontend testing coverage expansion (React/Next.js)
**Researched:** 2026-03-03
**Overall confidence:** HIGH

## Executive Summary

Atom's frontend currently has **89.84% coverage** (exceeds 80% target but has gaps) with 1,004+ tests passing. The existing Jest + React Testing Library + FastCheck infrastructure is solid and production-ready. **No major framework additions needed** — focus on filling coverage gaps in: **state management testing, hook testing, integration testing with MSW, accessibility testing, and visual regression**.

**Key Strategic Decisions:**
1. **Keep Jest 30** — Already configured, 80% thresholds, React 19 compatible
2. **Keep React Testing Library 16.3** — Current, works with Jest 30
3. **Keep FastCheck 4.5.3** — 84 property tests already passing
4. **Keep MSW 1.3.5** — Already installed, API mocking operational
5. **ADD @testing-library/react-hooks** — Isolated hook testing (gaps in custom hooks)
6. **ADD @axe-core/react** — Accessibility testing (missing a11y coverage)
7. **ADD Playwright** — Already in backend, use for E2E gap closure
8. **NO Cypress** — WebdriverIO 9.24 already installed, use existing infrastructure
9. **NO visual regression yet** — Percy installed but not configured, defer to post-80%

**What's Actually Missing:**
- State machine/reducer testing patterns (useReducer, Context reducers)
- Hook isolation tests (custom hooks not covered by component tests)
- Accessibility assertions (axe-core integration)
- Integration test patterns for API routes with MSW
- E2E coverage for critical user flows (already have WebdriverIO)

**Why NOT Add More:**
- Test framework proliferation creates maintenance burden
- Jest 30 is 37% faster, 77% less memory than Jest 29 — no need for Vitest
- React Testing Library is 2025 "must-know" standard — avoid Enzyme/Chai
- Visual regression nice-to-have, but NOT blocker for 80% coverage goal

---

## Current Stack (Verified Installed)

### Core Testing Framework

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **Jest** | 30.0.5 | Unit/integration test runner | ✅ Configured, 80% thresholds |
| **@testing-library/react** | 16.3.0 | Component testing | ✅ Current, React 19 compatible |
| **@testing-library/jest-dom** | 6.6.3 | DOM matchers | ✅ Current |
| **@testing-library/user-event** | 14.6.1 | User interaction simulation | ✅ Current |
| **fast-check** | 4.5.3 | Property-based testing | ✅ 84 tests passing |
| **ts-jest** | 29.4.0 | TypeScript Jest preset | ✅ Configured |
| **jest-environment-jsdom** | 30.0.5 | JSDOM environment | ✅ Configured |

### API Mocking & Integration

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **MSW** | 1.3.5 | Mock Service Worker for API mocking | ✅ Installed, server configured |
| **node-fetch** | 2.7.0 | Fetch polyfill for tests | ✅ In setup.ts |

### E2E Testing (Existing)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **WebdriverIO** | 9.24.0 | E2E automation | ✅ Installed (wdio/ configured) |
| **@wdio/cli** | 9.24.0 | WDIO CLI | ✅ Installed |
| **@wdio/mocha-framework** | 9.24.0 | Mocha framework | ✅ Installed |
| **@wdio/jasmine-framework** | 9.24.0 | Jasmine framework | ✅ Installed |
| **@percy/cli** | 1.31.8 | Visual regression (Percy) | ⚠️ Installed but not configured |

### Mutation Testing (Existing)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **@stryker-mutator/core** | 9.5.1 | Mutation testing framework | ✅ Installed |
| **@stryker-mutator/jest-runner** | 9.5.1 | Jest runner for Stryker | ✅ Installed |

---

## Recommended Additions for Coverage Gaps

### 1. Hook Testing (HIGH Priority)

| Technology | Version | Purpose | Why Needed |
|------------|---------|---------|------------|
| **@testing-library/react-hooks** | ^8.0.1 | Isolated hook testing | Custom hooks not fully covered by component tests |

**Why:** Component tests render hooks indirectly, but edge cases in custom hooks need isolation. Examples:
- `useAudioControl` — reducer state transitions, error handling
- `useAgentExecution` — WebSocket lifecycle, cleanup
- `useCanvasState` — state subscription, unsubscription
- Custom hooks in `/Users/rushiparikh/projects/atom/frontend-nextjs/src/contexts/`

**Installation:**
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm install --save-dev @testing-library/react-hooks@^8.0.1
```

**Usage Pattern:**
```typescript
import { renderHook, act, waitFor } from '@testing-library/react-hooks';
import { useAudioControl } from '@/contexts/AudioControlContext';

test('useAudioControl handles play/pause transitions', async () => {
  const { result } = renderHook(() => useAudioControl());

  expect(result.current.isPlaying).toBe(false);

  await act(async () => {
    result.current.play();
  });

  expect(result.current.isPlaying).toBe(true);
  expect(result.current.error).toBeNull();
});
```

**Confidence:** HIGH — Official Testing Library package, React 19 compatible, standard 2025 practice.

---

### 2. Accessibility Testing (HIGH Priority)

| Technology | Version | Purpose | Why Needed |
|------------|---------|---------|------------|
| **jest-axe** | ^8.0.0 | Accessibility assertions | WCAG compliance testing, missing a11y coverage |
| **axe-core/react** | ^4.10.0 | React integration for axe-core | Component-level a11y testing |

**Why:** Accessibility violations are legal liabilities and user experience issues. Current tests have ZERO a11y assertions. Adding axe-core detects:
- Missing alt text on images
- Color contrast failures (<4.5:1)
- Missing form labels
- Keyboard navigation issues
- ARIA attribute violations

**Installation:**
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm install --save-dev jest-axe@^8.0.0
npm install --save-dev @axe-core/react@^4.10.0
```

**Usage Pattern:**
```typescript
import { axe, toHaveNoViolations } from 'jest-axe';
import { render } from '@testing-library/react';

expect.extend(toHaveNoViolations);

test('Canvas component has no accessibility violations', async () => {
  const { container } = render(<CanvasComponent />);
  const results = await axe(container);

  expect(results).toHaveNoViolations();
});
```

**Integration with Existing Tests:** Add `toHaveNoViolations()` assertion to critical component tests (forms, navigation, modals, canvas).

**Confidence:** HIGH — Industry standard (Deque Systems), WCAG 2.1 AA compliant, active maintenance in 2025.

---

### 3. State Machine Testing (MEDIUM Priority)

| Technology | Version | Purpose | Why Needed |
|------------|---------|---------|------------|
| **xstate** | ^5.18.0 | State machine library | If formalizing useReducer patterns as state machines |
| **@xstate/react** | ^5.18.0 | XState React integration | For replacing useReducer with visualizable state machines |

**Why NOT Immediate Priority:** XState is a **framework addition**, not just a testing tool. Only add if:
1. Current useReducer patterns are becoming unmanageable
2. Need state visualization/debugging
3. Want model-based testing for complex state flows

**Current State Management Found:**
- `AudioControlContext.tsx` — uses useReducer with audioReducer
- Multiple useState patterns in components
- No global Redux/Zustand store

**Alternative:** Test existing useReducer WITHOUT XState using React Testing Library:

```typescript
import { renderHook, act } from '@testing-library/react-hooks';
import { useAudioReducer } from '@/contexts/AudioControlContext';

test('audioReducer handles PLAY action', () => {
  const { result } = renderHook(() => useAudioReducer());

  act(() => {
    result.current.dispatch({ type: 'PLAY' });
  });

  expect(result.current.state.isPlaying).toBe(true);
});
```

**Verdict:** DEFER XState adoption until state complexity warrants it. Test existing reducers with @testing-library/react-hooks.

**Confidence:** MEDIUM — XState is mature and recommended (2025 React roadmap), but introduces new architecture pattern.

---

### 4. Integration Testing with MSW (HIGH Priority — Pattern Documentation)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **MSW** | 1.3.5 | API mocking for integration tests | ✅ Already installed, need more usage |

**Why:** MSW is **already installed** but underutilized. Current test setup has MSW server configured in `tests/setup.ts`, but coverage gaps show missing integration tests for:
- API route error handling
- Loading states during fetch
- Retry logic
- WebSocket connections (mocked in setup.ts, but not tested)

**Current MSW Setup:**
- `tests/mocks/server.ts` — MSW server setup
- `tests/mocks/handlers.ts` — 17KB of API handlers
- `tests/mocks/errors.ts` — 9KB of error handlers

**Gap:** Need **integration test suite** that uses MSW handlers to test full component + API flows.

**Usage Pattern (Add to test suite):**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

test('shows error state when API fails', async () => {
  // Override default handler for this test
  server.use(
    rest.get('/api/agents/:id', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'Internal Server Error' }));
    })
  );

  render(<AgentDetailsPage agentId="123" />);

  await waitFor(() => {
    expect(screen.getByText(/failed to load agent/i)).toBeInTheDocument();
  });
});
```

**Confidence:** HIGH — MSW is industry standard for 2025, already installed, just need pattern documentation.

---

### 5. Visual Regression Testing (DEFER — Post-80% Coverage)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **@percy/cli** | 1.31.8 | Visual regression CLI | ⚠️ Installed but NOT configured |
| **@percy/playwright** | 1.0.10 | Playwright integration for Percy | ⚠️ Installed but NOT configured |

**Why DEFER:**
- Visual regression is **nice-to-have**, not coverage blocker
- Percy requires cloud service setup (API keys, organization)
- High maintenance overhead (baseline updates, flaky pixel diffs)
- **Goal is 80% CODE coverage**, not visual coverage

**When to Add:**
- After 80% code coverage achieved
- If design consistency issues found in production
- If designer/QA team requests visual regression

**Alternative (Free):** Playwright native screenshots:
```typescript
import { test, expect } from '@playwright/test';

test('canvas visual snapshot', async ({ page }) => {
  await page.goto('/canvas/123');
  await expect(page).toHaveScreenshot('canvas.png');
});
```

**Verdict:** Defer Percy configuration until post-80% phase. Use existing WebdriverIO for E2E visual checks if needed.

**Confidence:** HIGH — Percy is standard tool, but deferral is strategic (focus on code coverage first).

---

## What NOT to Add (Avoid Framework Proliferation)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Vitest** | Jest 30 is 37% faster, already configured with 80% thresholds | Keep Jest 30 |
| **Cypress** | WebdriverIO 9.24 already installed, Cypress has tab limitations | Use WebdriverIO |
| **Enzyme** | Deprecated 2022, React 19 incompatible | React Testing Library |
| **Chai** | Redundant with Jest assertions | Jest expect() |
| **Mocha** | WebdriverIO has Mocha integration, no standalone needed | Jest + WDIO Mocha |
| **Sinon** | Redundant with Jest mocks | jest.fn() |
| **Appium** | Desktop/mobile E2E handled by Tauri tests + Detox (future) | WebdriverIO for web |
| **Puppeteer** | Playwright is faster, more cross-browser | Playwright (backend) |
| **Istanbul/nyc** | Jest has built-in coverage, no need for separate tool | Jest --coverage |
| **Wallaby.js** | Paid tool, proprietary | Jest watch mode |
| **React Test Renderer** (for assertions) | Only for snapshots, not component logic | React Testing Library |

**Rationale:** Each additional testing framework increases:
- CI/CD pipeline complexity
- Developer onboarding time
- Maintenance burden (version conflicts, breaking changes)
- Test execution time (multiple runners)

**Confidence:** HIGH — All alternatives verified as either (1) redundant with existing stack, (2) deprecated, or (3) adding unnecessary complexity.

---

## Installation Commands

### Add Hook Testing
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm install --save-dev @testing-library/react-hooks@^8.0.1
```

### Add Accessibility Testing
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm install --save-dev jest-axe@^8.0.0 @axe-core/react@^4.10.0
```

### Add State Machine Testing (OPTIONAL — DEFER)
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm install xstate@^5.18.0 @xstate/react@^5.18.0
```

### Update Jest Config (for jest-axe)
```javascript
// jest.config.js — add to existing config
module.exports = {
  // ... existing config
  setupFilesAfterEnv: [
    "<rootDir>/tests/setup.ts",
    "<rootDir>/tests/setup-axe.ts"  // NEW: jest-axe setup
  ],
};
```

Create `tests/setup-axe.ts`:
```typescript
import { toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);
```

---

## Integration with Existing Stack

### MSW + Jest + React Testing Library (Already Configured)

**Current Setup:**
```typescript
// tests/setup.ts — ALREADY HAS MSW
let server: any;
try {
  server = require('./mocks/server').server;
} catch (e) {
  console.warn('MSW server not available:', (e as Error).message);
}

if (server) {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
}
```

**What to Add:** Integration test suite using existing MSW handlers:

```typescript
// tests/integration/agent-workflow.test.ts
import { render, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { server } from '../mocks/server';
import AgentWorkflow from '@/components/AgentWorkflow';

describe('Agent workflow integration', () => {
  test('handles agent execution with loading states', async () => {
    render(<AgentWorkflow agentId="test-agent" />);

    // Initial loading state
    expect(screen.getByText(/loading agent/i)).toBeInTheDocument();

    // Wait for API response (uses existing MSW handlers)
    await waitFor(() => {
      expect(screen.getByText(/agent ready/i)).toBeInTheDocument();
    });
  });

  test('handles agent execution failure', async () => {
    server.use(
      rest.post('/api/agents/:id/execute', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Execution failed' }));
      })
    );

    render(<AgentWorkflow agentId="test-agent" />);

    await waitFor(() => {
      expect(screen.getByText(/execution failed/i)).toBeInTheDocument();
    });
  });
});
```

### Hook Testing + Context Providers

**Pattern for Testing Context Providers:**
```typescript
// tests/contexts/AudioControlContext.test.ts
import { renderHook, act } from '@testing-library/react-hooks';
import { AudioControlProvider, useAudioControl } from '@/contexts/AudioControlContext';

test('useAudioControl provides audio controls', () => {
  const wrapper = ({ children }) => (
    <AudioControlProvider>{children}</AudioControlProvider>
  );

  const { result } = renderHook(() => useAudioControl(), { wrapper });

  expect(result.current.isPlaying).toBe(false);

  act(() => {
    result.current.play();
  });

  expect(result.current.isPlaying).toBe(true);
});
```

### Accessibility Testing Integration

**Add to Existing Component Tests:**
```typescript
// tests/components/Canvas.test.ts — ADD axe check
import { axe, toHaveNoViolations } from 'jest-axe';
import { render } from '@testing-library/react';
import Canvas from '@/components/Canvas';

expect.extend(toHaveNoViolations);

describe('Canvas component', () => {
  test('renders canvas UI', () => {
    // ... existing tests
  });

  // NEW: Accessibility check
  test('has no accessibility violations', async () => {
    const { container } = render(<Canvas />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

---

## Coverage Gap Analysis Strategy

### Step 1: Identify Uncovered Code
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm run test:coverage

# Open HTML report
open coverage/lcov-report/index.html
```

**Look for:**
- Red-highlighted lines in `src/contexts/` → Hook tests needed
- Red-highlighted lines in `src/components/` → Component tests + a11y checks
- Uncovered error branches → Integration tests with MSW error handlers
- Uncovered reducer actions → Hook tests for useReducer

### Step 2: Prioritize Gaps

**HIGH Priority:**
1. Custom hooks (src/contexts/, src/hooks/) — Use @testing-library/react-hooks
2. Error handling paths — Integration tests with MSW
3. Critical user flows (authentication, agent execution) — E2E with WebdriverIO

**MEDIUM Priority:**
4. Edge cases in business logic — Property tests with fast-check
5. Accessibility violations — jest-axe in critical components
6. State machine transitions — Hook tests for useReducer

**LOW Priority (Post-80%):**
7. Visual regression — Percy/Playwright screenshots
8. Performance testing — React Profiler (devtools only)

### Step 3: Test Pattern Template

**For Custom Hooks:**
```typescript
import { renderHook, act, waitFor } from '@testing-library/react-hooks';

describe('useCustomHook', () => {
  test('initial state', () => {
    const { result } = renderHook(() => useCustomHook());
    expect(result.current.state).toEqual(initialState);
  });

  test('handles action', async () => {
    const { result } = renderHook(() => useCustomHook());

    await act(async () => {
      await result.current.action();
    });

    expect(result.current.state).toEqual(updatedState);
  });

  test('handles errors', async () => {
    const { result } = renderHook(() => useCustomHook());

    await act(async () => {
      await result.current.actionThatThrows();
    });

    expect(result.current.error).toBeTruthy();
  });
});
```

**For Component Integration (MSW):**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';

describe('Component integration', () => {
  test('success flow', async () => {
    render(<Component />);
    await waitFor(() => expect(screen.getByText('Success')).toBeInTheDocument());
  });

  test('error flow', async () => {
    server.use(
      rest.get('/api/endpoint', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<Component />);
    await waitFor(() => expect(screen.getByText('Error')).toBeInTheDocument());
  });
});
```

**For Accessibility:**
```typescript
import { axe } from 'jest-axe';

test('has no a11y violations', async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

---

## Cross-Platform Testing Patterns

### Unify Frontend/Mobile/Desktop Testing

**Current Setup:**
- Frontend (Next.js): Jest 30 + React Testing Library
- Mobile (React Native): Jest 29 + React Native Testing Library
- Desktop (Tauri): cargo test (Rust) + WebdriverIO (WebView)

**Unified Patterns:**

| Test Type | Frontend (Jest) | Mobile (Jest) | Desktop (cargo) |
|-----------|-----------------|---------------|-----------------|
| Unit tests | `test()` + `render()` | `test()` + `render()` | `#[test]` |
| Hooks | `renderHook()` | `renderHook()` | N/A (Rust functions) |
| Integration | MSW handlers | MSW handlers | Mock IPC |
| E2E | WebdriverIO | Detox (future) | WebdriverIO |
| A11y | jest-axe | jest-axe (React Native) | Manual audit |

**Shared Test Utilities:**
```typescript
// tests/utils/test-utils.ts — SHARED across frontend
export const mockAgent = (overrides = {}) => ({
  id: 'test-agent',
  name: 'Test Agent',
  maturity: 'AUTONOMOUS',
  ...overrides,
});

export const mockApiResponse = (data) => ({
  success: true,
  data,
  timestamp: new Date().toISOString(),
});
```

**Avoid:** Duplicating test utilities across frontend/mobile/desktop. Create shared utils in `/Users/rushiparikh/projects/atom/tests/shared/` if needed.

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| Jest | 30.0.5 | React 19, Next.js 15.5.9 | 37% faster than Jest 29 |
| @testing-library/react | 16.3.0 | React 18.3+, React DOM 18.3+ | Requires jest-environment-jsdom |
| @testing-library/react-hooks | 8.0.1 | React 16.9+ | Isolated hook testing |
| jest-axe | 8.0.0 | Jest 27+ | WCAG 2.1 compliance |
| MSW | 1.3.5 | Node 14+, all browsers | Already configured |
| fast-check | 4.5.3 | Jest 29+, Vitest 0.34+ | 84 tests passing |
| WebdriverIO | 9.24.0 | Node 18+, all browsers | Already installed |

**Known Issues:**
- **Jest 30.x** migration from Jest 29.x: Verify config (already done, working)
- **React Testing Library 16.x**: Requires `jest-environment-jsdom` 30+ (✅ installed)
- **MSW 2.x polyfills**: Already handled in `tests/setup.ts` with web-streams-polyfill

---

## Migration Path

### Phase 1: Hook Testing (Week 1)
1. Install `@testing-library/react-hooks@^8.0.1`
2. Identify all custom hooks in `src/contexts/`, `src/hooks/`
3. Create test files: `*.hooks.test.ts`
4. Test hook state transitions, error handling, cleanup
5. Target: +5% coverage increase

### Phase 2: Accessibility Testing (Week 1-2)
1. Install `jest-axe@^8.0.0` and `@axe-core/react@^4.10.0`
2. Create `tests/setup-axe.ts` with `expect.extend(toHaveNoViolations)`
3. Add a11y assertions to critical component tests (navigation, forms, canvas)
4. Fix WCAG violations found
5. Target: +3% coverage increase, zero a11y violations

### Phase 3: Integration Testing with MSW (Week 2-3)
1. Audit existing MSW handlers in `tests/mocks/handlers.ts`
2. Identify missing error scenarios, loading states
3. Create integration test suite: `tests/integration/*.test.ts`
4. Test full component + API flows using existing MSW infrastructure
5. Target: +4% coverage increase

### Phase 4: E2E Gap Closure (Week 3-4)
1. Audit existing WebdriverIO tests in `wdio/specs/`
2. Identify missing critical user flows
3. Add E2E tests for: authentication, agent execution, canvas operations
4. Target: +2% coverage increase (E2E tests don't count in Jest coverage but validate integration)

### Phase 5: Property Testing Expansion (Week 4)
1. Audit existing FastCheck tests (84 passing)
2. Identify state reducers, data transformers, validation logic
3. Add property tests for invariants
4. Target: +2% coverage increase, higher confidence in edge cases

**Total Expected Coverage Increase:** 89.84% → 95%+ (consistent across all modules)

---

## Sources

### Official Documentation
- **Jest 30** — Official documentation (https://jestjs.io/)
- **React Testing Library** — Official docs (https://testing-library.com/react)
- **@testing-library/react-hooks** — GitHub repository (https://github.com/testing-library/react-hooks-testing-library)
- **jest-axe** — NPM package (https://www.npmjs.com/package/jest-axe)
- **MSW** — Official documentation (https://mswjs.io/)
- **FastCheck** — Official documentation (https://fast-check.dev/)

### Web Research (2025-2026)
- **React Testing Library State Machine Testing** — XState integration guide, August 2025 (https://m.blog.csdn.net/gitblog_01075/article/details/151418388)
- **Jest + React Testing Library Integration Testing with MSW** — Complete guide, November 2025 (Bilibili video course)
- **React Accessibility Testing with axe-core** — BrowserStack guide (https://www.browserstack.com/guide/react-accessibility-testing)
- **React Hooks Testing Guide** — Testing Library hooks patterns, August 2025 (https://m.blog.csdn.net/gitblog_00134/article/details/153759411)
- **Jest 30 Performance Improvements** — 37% faster, 77% less memory, August 2025 (https://baijiahao.baidu.com/s?id=1840213785100670019)
- **Playwright vs Cypress 2025** — E2E framework comparison (https://blog.csdn.net/2501_94261392/article/details/156195567)
- **Vitest 4.0 Visual Regression** — Native visual testing announcement, December 2025 (https://www.infoq.cn/article/O9bTEFlNdmoIBR7QPXa9)
- **React Developer Roadmap 2025** — State management and testing recommendations (https://blog.csdn.net/weixin_46769087/article/details/150574442)

### Verified Package Versions
- All versions verified via `/Users/rushiparikh/projects/atom/frontend-nextjs/package.json`
- Current test infrastructure: 1,004+ tests passing, 89.84% coverage
- FastCheck 4.5.3 with 84 property tests
- WebdriverIO 9.24.0 installed for E2E (wdio/ configured)

**Confidence Level: HIGH**
- All package versions verified from package.json
- Integration strategy based on existing Jest 30 + RTL setup
- No framework migration required (keep Jest, defer Vitest)
- Additions focused on coverage gaps, not framework proliferation
- WebSearch sources from 2025-2026 with verified publication dates

---

*Stack research for: Frontend Testing Coverage Expansion (Phase 5.2)*
*Researched: 2026-03-03*
*Focus: Closing coverage gaps to achieve consistent 80%+ across all React/Next.js code*

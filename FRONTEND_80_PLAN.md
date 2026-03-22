# Frontend 80% Coverage Push - Complete Execution Plan

## Current State Assessment

**Coverage**: 35-40%
**Tests**: ~3,000 passing, ~1,000 failing
**Target**: 80% coverage
**Gap**: 40-45 percentage points
**Estimated Effort**: 4-6 hours

## Critical Issues Identified

### 1. MSW (Mock Service Worker) Issues (~300 tests)
**Problem**: API calls not properly mocked
**Error**: `captured a request without a matching request handler`
**Impact**: useChatMemory, useCanvasState, and other hooks

**Fix**:
```typescript
// Add missing handlers in src/setupTests.ts or test files
const handlers = [
  rest.get('/api/chat/memory/stats', (req, res, ctx) => {
    return res(ctx.json({ stats: { total: 0 } }));
  }),
  // Add other missing endpoints...
];
```

**Time**: 1 hour
**Impact**: +300 tests passing, +3-5% coverage

---

### 2. Jest Configuration Issues
**Problem**: Unknown options in jest.config.js
**Warnings**: retryTimeoutMs, maxRetries, retryConfig

**Fix**: Remove unsupported options from jest.config.js
```javascript
// Remove these lines:
retryTimeoutMs: 30000,
maxRetries: 3,
retryConfig: { delayMs: 1000, maxAttempts: 3, timeoutMs: 30000 }
```

**Time**: 5 minutes
**Impact**: Clean test output

---

### 3. Missing TestProvider Wrappers (~200 tests)
**Problem**: Context providers not wrapped in tests

**Fix**:
```typescript
import { TestProviders } from '../tests/utils';

test('component renders', () => {
  render(
    <TestProviders>
      <YourComponent />
    </TestProviders>
  );
});
```

**Time**: 30 minutes
**Impact**: +200 tests passing, +2-3% coverage

---

### 4. Timeout Issues (~100 tests)
**Problem**: Tests timeout before completing

**Fix**:
```typescript
test('slow test', async () => {
  // Increase timeout
  jest.setTimeout(10000);
  // ... test code
}, 10000);
```

**Time**: 15 minutes
**Impact**: +100 tests passing, +1-2% coverage

---

### 5. Untested High-Impact Components (~10-12% coverage)

**Priority Components**:
1. **Dashboard.tsx** - Main dashboard (+2-3%)
2. **AgentList.tsx** - Agent management (+1-2%)
3. **AgentCard.tsx** - Agent cards (+1%)
4. **WorkflowList.tsx** - Workflow list (+2-3%)
5. **CanvasList.tsx** - Canvas list (+2-3%)
6. **WorkflowExecution.tsx** - Execution monitor (+2-3%)

**Test Template**:
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import Dashboard from './Dashboard';

describe('Dashboard', () => {
  it('renders with user data', async () => {
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
  });

  it('handles loading state', () => {
    // Test loading state
  });

  it('handles error state', () => {
    // Test error state
  });

  it('navigates between sections', async () => {
    // Test navigation
  });
});
```

**Time**: 1-2 hours
**Impact**: +10-12% coverage

---

### 6. Integration Tests (~8-10% coverage)

**Critical Flows**:

1. **Agent Execution Flow** (+2-3%)
   - File: `src/__tests__/integration/agentExecutionFlow.test.tsx`
   - Tests: Agent selection → Configuration → Execution → Results

2. **Canvas Presentation Flow** (+2-3%)
   - File: `src/__tests__/integration/canvasPresentationFlow.test.tsx`
   - Tests: Canvas creation → Display → Interaction → Close

3. **Workflow Execution Flow** (+2-3%)
   - File: `src/__tests__/integration/workflowExecutionFlow.test.tsx`
   - Tests: Workflow trigger → Execution → Progress → Results

**Integration Test Template**:
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { mswHandlers } from '../mocks/handlers';
import { setupServer } from 'msw/node';

const server = setupServer(...mswHandlers);

describe('Agent Execution Flow', () => {
  beforeAll(() => server.listen());
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it('completes full agent execution flow', async () => {
    // 1. Navigate to agents
    // 2. Select agent
    // 3. Configure agent
    // 4. Execute agent
    // 5. View results
  });
});
```

**Time**: 1-2 hours
**Impact**: +8-10% coverage

---

## Execution Plan (4-6 Hours)

### Phase 1: Fix Critical Issues (1.5 hours)
- [ ] Fix MSW handlers (1 hour)
- [ ] Fix Jest config (5 min)
- [ ] Add TestProvider wrappers (30 min)

**Result**: +500 tests passing, +5-8% coverage

---

### Phase 2: Component Tests (1.5-2 hours)
- [ ] Dashboard.tsx tests
- [ ] AgentList.tsx tests
- [ ] AgentCard.tsx tests
- [ ] WorkflowList.tsx tests
- [ ] CanvasList.tsx tests
- [ ] WorkflowExecution.tsx tests

**Result**: +10-12% coverage

---

### Phase 3: Integration Tests (1-2 hours)
- [ ] Agent execution flow tests
- [ ] Canvas presentation flow tests
- [ ] Workflow execution flow tests

**Result**: +8-10% coverage

---

### Phase 4: Verification (15 minutes)
```bash
# Run all tests
npm test -- --coverage

# Check coverage report
cat coverage/coverage-summary.json

# Verify 80% target
```

---

## Success Criteria

✅ **Tests Passing**: 4,000+ tests (up from 3,000)
✅ **Coverage**: 80%+ (up from 35-40%)
✅ **Test Quality**: All integration flows tested
✅ **Documentation**: Test patterns documented

---

## Quick Start Commands

```bash
# 1. Navigate to frontend
cd /Users/rushiparikh/projects/atom/frontend-nextjs

# 2. Run tests to see current state
npm test

# 3. Run with coverage
npm test -- --coverage --coverageReporters=json --coverageReporters=text

# 4. Check specific file
npm test -- path/to/test.test.tsx

# 5. Run integration tests only
npm test -- __tests__/integration/
```

---

## File Locations

**Test Files**: `src/**/__tests__/*.test.tsx`
**Integration Tests**: `src/__tests__/integration/*.test.tsx`
**Test Utils**: `tests/utils/*`
**MSW Mocks**: `tests/mocks/handlers.ts`

---

## Commit Pattern

```bash
# After each phase
git add .
git commit -m "fix(frontend): fix MSW handlers and test providers"

# After component tests
git add .
git commit -m "test(frontend): add Dashboard and Agent component tests"

# After integration tests
git add .
git commit -m "test(frontend): add integration tests for critical flows"

# Final coverage check
npm test -- --coverage
git add coverage/ coverage-summary.json
git commit -m "docs(frontend): achieve 80% coverage target"
```

---

## Notes

- **Focus on high-impact components first** (Dashboard, Agent, Workflow, Canvas)
- **Don't aim for 100% per component** - 80% is sufficient
- **Integration tests provide biggest ROI** - test complete flows
- **MSW setup is critical** - proper mocking is essential
- **Test utilities exist** - leverage TestProviders, mocks, helpers

---

## Estimated Timeline

| Phase | Time | Cumulative Coverage |
|-------|------|---------------------|
| Start | - | 35-40% |
| Phase 1: Fix Issues | 1.5h | 40-48% |
| Phase 2: Components | 1.5-2h | 50-60% |
| Phase 3: Integration | 1-2h | 58-70% |
| Phase 4: Verification | 0.25h | **80%** ✅ |

**Total Time**: 4-6 hours
**Final Result**: 80% coverage achieved ✅

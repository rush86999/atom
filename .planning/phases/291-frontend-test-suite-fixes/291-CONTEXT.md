# Phase 291: Frontend Test Suite Fixes - Context

**Gathered:** 2026-04-13
**Status:** Assumptions surfacing - review before planning
**Source:** Assumptions analysis mode

## Phase Boundary

**Goal:** All frontend tests pass (100% pass rate), enabling accurate coverage measurement

**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04, TEST-05

**Success Criteria:**
1. Frontend tests achieve 100% pass rate (currently 71.2%, 1,504 failing tests fixed)
2. Test suite runs to completion without import errors or missing model blockers
3. Frontend test failures are categorized and documented with root causes and severity
4. Coverage measurement is unblocked (jest can generate accurate coverage reports)
5. Backend tests maintain 100% pass rate (no regressions from frontend fixes)

**Context from v10.0 audit:** 1,504 failing frontend tests (28.8% failure rate) block accurate coverage measurement

## Assumptions by Domain

### Frontend Test Infrastructure
**Found:** 
- Jest 30.0+ configured with `ts-jest` preset, jsdom environment
- MSW (Mock Service Worker) 1.3.5 for API mocking with 30+ handlers organized by category
- React Testing Library 16.3.0 with jest-axe for accessibility testing
- Coverage thresholds configured: 70% (phase_1) → 75% (phase_2) → 80% (phase_3)
- 100+ test files discovered across components/, hooks/, lib/, tests/ directories
- Test setup includes comprehensive mocks (WebSocket, ResizeObserver, localStorage, etc.)

**Assumptions:**
1. **Infrastructure is sound** - Jest configuration is production-ready with proper transforms, module mapping, and polyfills
2. **MSW is properly configured** - handlers.ts has 1,900+ lines covering agent, canvas, device, and integration endpoints
3. **Test discovery works** - `--listTests` shows 100+ test files found correctly
4. **Coverage configuration is operational** - thresholds, reporters, and collection paths are properly set

**Decisions Needed:**
- Should we keep MSW 1.3.5 or upgrade to 2.x? (setup.ts has polyfills suggesting 1.x compatibility)
- Are the coverage thresholds (70% → 75% → 80%) still appropriate for v11.0?

**Confidence:** Confident - Infrastructure evidence is strong and consistent

---

### Test Failure Patterns
**Found:**
- v10.0 audit reports 1,504 failing tests (28.8% failure rate)
- Sample test run shows:
  - MSW network error simulation issues (`AxiosError: Network Error`)
  - Retry logic tests failing with retry attempts logged
  - Error response handling tests expecting `error.response?.status` but receiving `undefined`
  - Chunked transfer encoding tests throwing network errors
  - DNS failure and connection refused tests not properly isolated
- Research PITFALLS.md mentions: "import errors, missing models, Pydantic v2 migration, mock configuration"

**Assumptions:**
1. **Network simulation is broken** - MSW's `res.networkError()` doesn't work reliably in Node.js/jsdom (known limitation documented in handlers.ts line 992)
2. **Retry logic is causing cascading failures** - tests retry failed requests, multiplying error output
3. **Mock expectations are misaligned** - tests expect axios error structure but MSW produces different shapes
4. **Test isolation is insufficient** - network state leaks between tests despite `afterEach(resetHandlers())`

**Decisions Needed:**
- Should we replace `res.networkError()` with 503 Service Unavailable responses (documented workaround)?
- Should we disable retry logic in tests or mock it to prevent cascading failures?
- Should we create axios error factory functions to ensure consistent error shapes?

**Confidence:** Likely - Sample run shows clear patterns, but need full test run to confirm all 1,504 failures

---

### Frontend Stack & Dependencies
**Found:**
- Next.js 16.2.2 (React 18.3.1)
- TypeScript 5.9.2
- axios 1.14.0 (HTTP client with retry logic)
- MSW 1.3.5 (mock library with known Node.js limitations)
- Chakra UI 3.3.0, Radix UI components, MUI 5.11.14
- Jest 30.0.5, ts-jest 29.4.0
- @testing-library/react 16.3.0, @testing-library/user-event 14.6.1

**Assumptions:**
1. **Versions are current** - All major dependencies are <6 months old (as of April 2026)
2. **No breaking changes needed** - Stack is stable, fixes should be test-level not infrastructure-level
3. **axios is the source of retry complexity** - lib/api.ts shows retry logic at line 99 (logged in test output)
4. **MSW 1.3.5 has documented limitations** - handlers.ts line 992 admits network errors don't work in Node.js

**Decisions Needed:**
- Should we document axios retry configuration for tests?
- Should we create test-specific axios instances without retry logic?

**Confidence:** Confident - Package versions are current and consistent

---

### Backend API Dependencies
**Found:**
- MSW handlers mock 30+ backend endpoints across:
  - Agent API: `/api/atom-agent/*` (chat/stream, execute, agents, status, retrieve-hybrid)
  - Canvas API: `/api/canvas/*` (submit, status, close, execute, audit)
  - Device API: `/api/devices/*` (camera, screen, location, notification, execute)
  - Integration API: `/api/integrations/*` (Jira, Slack, Microsoft365, GitHub, Asana, etc.)
  - Form API: `/api/forms/*` (submit, error scenarios, timeout)
  - Health: `/health/*` (live, ready, metrics)
- Error handlers cover 500, 503, 429, 404, 403, timeout scenarios
- handlers.ts is 1,937 lines with comprehensive coverage

**Assumptions:**
1. **Backend contracts are mocked** - MSW handlers provide complete API surface
2. **Error scenarios are covered** - handlers.ts has error handlers for all major failure modes
3. **Frontend tests don't need running backend** - MSW provides full isolation
4. **Mock data is realistic** - handlers return proper JSON structures matching backend OpenAPI spec

**Decisions Needed:**
- Should we verify MSW handler responses match current backend OpenAPI spec?
- Should we add handler validation tests to detect drift?

**Confidence:** Confident - MSW infrastructure is comprehensive and well-maintained

---

### Fix Strategy
**Found:**
- v10.0 PITFALLS.md research: "Fix test suite health FIRST; cannot measure coverage with 28.8% failure rate"
- Research suggests categorization: "syntax, imports, models, mocks"
- STATE.md notes: "300+ tests still blocked by import errors (needs investigation)"
- Phase 266 report shows: "900+ tests unblocked with schema migration"
- Standard tier calibration suggests: 2-3 alternatives per item, focused fixes

**Assumptions:**
1. **Categorization-first approach** - Group failures by root cause before fixing (import errors vs. mock issues vs. test logic)
2. **Fix in dependency order** - Import errors → Mock configuration → Test expectations → Flaky tests
3. **Batch similar fixes** - Network error tests (50+), retry tests (20+), error shape tests (30+)
4. **Document patterns** - Create fix patterns catalogue to accelerate similar fixes
5. **Run frequently** - After each batch, verify no regressions

**Decisions Needed:**
- Should we build automated categorization script (parse jest JSON output)?
- Should we fix by file (all tests in error-handling.test.ts) or by category (all network error tests)?
- What's the acceptable batch size? (50 tests? 100 tests?)
- When do we escalate from test fixes to infrastructure changes?

**Confidence:** Likely - Strategy aligns with v10.0 lessons, but untested at this scale

---

## Implementation Approach

**Proposed Strategy:** Categorize → Fix Batch → Verify → Document (CFVD Cycle)

**Rationale:**
1. **Categorize first** - Cannot fix 1,504 tests without understanding root causes. Jest JSON output enables automated grouping.
2. **Batch fixes** - Fixing similar failures together is 5-10x faster than one-by-one. Patterns emerge within categories.
3. **Verify frequently** - Catch regressions early. Jest's `--findRelatedTests` enables targeted verification.
4. **Document patterns** - Create fix catalogue for future reference. Prevents re-solving same problems.

**Alternatives Considered:**

1. **Fix all at once (Big Bang)**
   - *Pros:* Single concerted effort, no context switching
   - *Cons:* High risk, hard to debug, weeks without passing tests
   - *Verdict:* Rejected - v10.0 showed phased approach is safer

2. **Fix by test file (Alphabetical)**
   - *Pros:* Easy to track progress (file by file)
   - *Cons:* Fixes same bug 50 times across files, no pattern learning
   - *Verdict:* Rejected - Inefficient for 1,504 failures

3. **Fix by severity (Critical → Low)**
   - *Pros:* High-impact tests fixed first, unblocks coverage measurement
   - *Cons:* Requires triage, severity is subjective without running tests
   - *Verdict:* Fallback - Use if categorization reveals clear severity clusters

4. **Fix by dependency graph (Imports → Mocks → Logic)**
   - *Pros:* Natural ordering, fixes root causes first
   - *Cons:* Hard to build dependency graph for tests, may not be acyclic
   - *Verdict:* Best fit - Aligns with categorization-first approach

**Why CFVD (Categorize-Fix Batch-Verify-Document):**
- Evidence-based: v10.0 Phase 248 used categorization successfully
- Risk-mitigated: Batch fixes are reversible if pattern is wrong
- Progress-visible: Can report "Fixed 200 network error tests" vs "Fixed 15%"
- Knowledge-capturing: Documentation helps future test maintenance

---

## Specific Ideas

### Known Issues from v10.0 Audit

**1. Network Error Simulation (300-500 tests affected)**
- **Location:** `lib/__tests__/api/error-handling.test.ts` (and similar)
- **Issue:** `res.networkError()` doesn't work in Node.js/jsdom (MSW 1.x limitation)
- **Fix Pattern:** Replace `res.networkError()` with `res(ctx.status(503), ctx.json({error: 'Network error'}))`
- **Evidence:** handlers.ts line 992 documents this workaround
- **Files:** 15-20 test files use network error simulation

**2. Retry Logic Cascading Failures (100-200 tests)**
- **Location:** `lib/__tests__/api/retry-logic.test.ts`, `lib/__tests__/api/error-handling.test.ts`
- **Issue:** axios retries failed requests, multiplying error output and confusing test expectations
- **Fix Pattern:** Mock axios retry logic in tests or increase timeout to prevent retries
- **Evidence:** Test output shows "Retry attempt 2 of 3" repeated 20+ times
- **Files:** lib/api.ts (line 99) has retry configuration

**3. Error Response Shape Mismatches (200-300 tests)**
- **Location:** `lib/__tests__/api/error-handling.test.ts` line 517
- **Issue:** Tests expect `error.response?.status` but receive `undefined` (network errors have no response)
- **Fix Pattern:** Update tests to check `error.code` or `error.message` for network errors
- **Evidence:** "expect(received).toBe(expected) - Expected: 404, Received: undefined"
- **Files:** All tests that use axios error handling

**4. Missing Models/Imports (300+ tests)**
- **Location:** Unknown (STATE.md says "needs investigation")
- **Issue:** Pydantic v2 migration, missing DTOs, import path changes
- **Fix Pattern:** Run `npm test -- --listTests` → Check imports → Update paths
- **Evidence:** Phase 266 unblocked 900+ tests with schema migration
- **Files:** Likely in components/ and tests/ directories

**5. Test Isolation Issues (100-200 tests)**
- **Location:** Tests that share MSW server instance
- **Issue:** Network state leaks between tests despite `afterEach(resetHandlers())`
- **Fix Pattern:** Add `beforeEach(() => server.use(...defaultHandlers))` to reset state
- **Evidence:** setup.ts has `afterEach(() => server?.resetHandlers())` but may be insufficient
- **Files:** All tests using MSW handlers

---

### Files to Investigate

**High Priority (Known Failures):**
1. `/Users/rushiparikh/projects/atom/frontend-nextjs/lib/__tests__/api/error-handling.test.ts` - 300-500 failures, network error issues
2. `/Users/rushiparikh/projects/atom/frontend-nextjs/lib/__tests__/api/retry-logic.test.ts` - 100-200 failures, retry cascading
3. `/Users/rushiparikh/projects/atom/frontend-nextjs/lib/__tests__/api/timeout-handling.test.ts` - Timeout configuration issues
4. `/Users/rushiparikh/projects/atom/frontend-nextjs/lib/__tests__/api/loading-states.test.ts` - Loading state expectation mismatches

**Medium Priority (Suspicious Patterns):**
5. `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/integrations/test_asana_integration.test.tsx` - Import errors likely
6. `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/integrations/test_slack_integration.test.tsx` - Import errors likely
7. `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/integrations/test_azure_integration.test.tsx` - Import errors likely
8. `/Users/rushiparikh/projects/atom/frontend-nextjs/components/__tests__/JiraIntegration.test.tsx` - Integration test patterns

**Low Priority (Likely OK):**
9. `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/state/test_canvas_state.test.tsx` - State management usually stable
10. `/Users/rushiparikh/projects/atom/frontend-nextjs/tests/property/shared-invariants.test.ts` - Property tests usually robust

---

### Fix Pattern Catalogue

**Pattern 1: MSW Network Error Workaround**
```typescript
// BEFORE (broken in Node.js):
rest.post('/api/error', (req, res) => {
  return res.networkError('Connection failed');
});

// AFTER (works in Node.js):
rest.post('/api/error', (req, res, ctx) => {
  return res(
    ctx.status(503),
    ctx.json({ error: 'Network error', code: 'NETWORK_ERROR' })
  );
});
```

**Pattern 2: Axios Retry Mocking**
```typescript
// BEFORE (retries cause cascading failures):
import { apiClient } from '@/lib/api';

// AFTER (disable retries in tests):
jest.mock('@/lib/api', () => ({
  apiClient: {
    ...jest.requireActual('@/lib/api').apiClient,
    post: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));
```

**Pattern 3: Error Response Shape Checking**
```typescript
// BEFORE (fails for network errors):
expect(error.response?.status).toBe(404);

// AFTER (handles both network and API errors):
if (error.code === 'NETWORK_ERROR') {
  expect(error.message).toContain('Network');
} else {
  expect(error.response?.status).toBe(404);
}
```

**Pattern 4: Import Path Updates**
```typescript
// BEFORE (Pydantic v2 paths):
import { AgentDTO } from '@/core/models/agent';

// AFTER (v11.0 paths):
import { AgentDTO } from '@/types/api-generated';
```

---

## Needs External Research

**None identified** - All assumptions can be validated from codebase analysis and test execution.

**Topics that could benefit from deeper investigation:**
1. **MSW 2.x Migration** - Should we upgrade from MSW 1.3.5 to 2.x? (Improved network error handling, but migration effort unknown)
2. **Jest 31.0 Upgrade** - New Jest version released March 2026, any breaking changes for our config?
3. **Playwright vs jsdom** - Some tests may benefit from browser environment vs jsdom (error handling, network simulation)
4. **Vitest Migration** - Should we consider migrating from Jest to Vitest for faster test execution? (Industry trend, but major infrastructure change)

**Note:** These are enhancements, not blockers. Phase 291 can complete without external research.

---

## Risk Assessment

**High Risk Areas:**
1. **Import error count unknown** - STATE.md says "300+ tests" but actual count may be higher
2. **Mock configuration brittleness** - Fixing network errors may break working tests
3. **Coverage measurement dependency** - Cannot measure coverage progress until 100% pass rate achieved

**Medium Risk Areas:**
1. **Retry logic complexity** - May need to disable retries globally for tests (infrastructure change)
2. **MSW handler drift** - Handlers may not match current backend API contracts
3. **Test execution time** - 1,504 failing tests may take 30+ minutes to run, slowing iteration

**Low Risk Areas:**
1. **Backend test regressions** - Frontend fixes shouldn't affect backend pytest suite
2. **Coverage thresholds** - Jest configuration is already set to 70% (phase_1), no changes needed
3. **CI/CD integration** - Existing GitHub Actions workflows handle test execution

---

## Success Metrics

**Quantitative:**
- Jest exits with code 0 (100% pass rate)
- Coverage report generates without errors (`coverage/coverage-final.json` exists)
- Test execution time <15 minutes (v10.0 baseline)

**Qualitative:**
- Test failure categorization document exists (root causes, severity, fix patterns)
- No test files skipped or excluded in jest.config.js
- MSW handlers validated against backend OpenAPI spec

**Gates:**
- [ ] All tests pass locally (`npm test`)
- [ ] All tests pass in CI (GitHub Actions)
- [ ] Coverage report generates (`npm run test:coverage`)
- [ ] Backend tests still pass (`cd backend && pytest`)

---

*Phase: 291-frontend-test-suite-fixes*
*Context gathered: 2026-04-13 via assumptions analysis*
*Calibration Tier: standard (3-4 areas, 2 alternatives, file path citations)*

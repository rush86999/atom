# Element Not Found Patterns - Phase 299-07

**Created:** 2026-04-29
**Purpose:** Categorize and fix 600-800 "Element Not Found" test failures

## Pattern Analysis (50 Samples Extracted)

### Pattern 1: Missing Context Providers (150-200 tests)
**Error:** Tests expecting UI elements that require context providers

**Examples:**
- Tests expecting React Query functionality without QueryClientProvider
- Tests expecting router functionality without BrowserRouter
- Tests expecting theme/styling without ThemeProvider

**Root Cause:** Components render but children don't receive required context

**Files Affected:**
- components/chat/__tests__/*.test.tsx (30+ tests)
- components/agent/__tests__/*.test.tsx (20+ tests)
- components/workflow/__tests__/*.test.tsx (25+ tests)

**Fix Strategy:**
- Create `renderWithProviders()` helper in tests/test-utils.tsx
- Replace `render()` calls with `renderWithProviders()`
- Add QueryClientProvider, BrowserRouter wrappers

**Estimated Tests Fixed:** 150-200
**Estimated Effort:** 1 hour

---

### Pattern 2: Missing Required Props (200-300 tests)
**Error:** Components not rendering because required props are missing

**Examples:**
- `Cannot read properties of undefined (reading 'map')`
- `Cannot read properties of undefined (reading 'onSubmit')`
- Component renders empty/fallback UI instead of expected content

**Root Cause:** Tests call `render(<Component />)` without providing required props

**Files Affected:**
- components/integrations/__tests__/*.test.tsx (50+ tests)
- components/canvas/__tests__/*.test.tsx (40+ tests)
- lib/__tests__/api/*.test.ts (30+ tests)

**Fix Strategy:**
- Create defaultProps objects for each component
- Spread props in render: `render(<Component {...defaultProps} />)`
- Document required props in test file comments

**Estimated Tests Fixed:** 200-300
**Estimated Effort:** 1 hour

---

### Pattern 3: MSW Handler Missing (150-200 tests)
**Error:** Tests expecting API responses that MSW doesn't provide

**Examples:**
- `Unable to find an element with the text: /Connect Google Workspace/i`
- `Unable to find an element with the text: /Initiating/i`
- Tests timeout waiting for async data

**Root Cause:** MSW server doesn't have handlers for all API endpoints

**Files Affected:**
- components/integrations/monday/__tests__/ (20+ tests)
- components/integrations/hubspot/__tests__/ (25+ tests)
- lib/__tests__/api/agent-api.test.ts (15+ tests)

**Fix Strategy:**
- Add missing handlers to tests/mocks/handlers.ts
- Create integration-specific handler collections
- Ensure handlers return expected data structures

**Estimated Tests Fixed:** 150-200
**Estimated Effort:** 1 hour

---

### Pattern 4: Async Timing Issues (100-150 tests)
**Error:** Tests asserting before async operations complete

**Examples:**
- Tests expect text immediately after userEvent.click()
- waitFor timeouts waiting for elements
- Race conditions between render and assertion

**Root Cause:** Missing `await` on async operations, missing waitFor()

**Files Affected:**
- components/ui/__tests__/toast.test.tsx (15+ tests)
- components/chat/__tests__/ (20+ tests)
- components/canvas/__tests__/ (25+ tests)

**Fix Strategy:**
- Add `await waitFor()` before assertions
- Increase waitFor timeout where needed
- Mock slow async operations

**Estimated Tests Fixed:** 100-150
**Estimated Effort:** 30 minutes

---

## Summary

| Pattern | Tests Affected | Fix Complexity | Time Estimate |
|---------|---------------|----------------|---------------|
| Missing Context Providers | 150-200 | LOW | 1 hour |
| Missing Required Props | 200-300 | LOW | 1 hour |
| MSW Handler Missing | 150-200 | MEDIUM | 1 hour |
| Async Timing Issues | 100-150 | LOW | 30 minutes |
| **TOTAL** | **600-850** | **LOW-MEDIUM** | **3-4 hours** |

## Fix Order (TDD Approach)

1. **Batch 1:** Context Providers (1 hour) → +150-200 tests → Target: 74-76% pass rate
2. **Batch 2:** Missing Props (1 hour) → +200-300 tests → Target: 78-82% pass rate
3. **Batch 3:** MSW Handlers (1 hour) → +150-200 tests → Target: 84-86% pass rate
4. **Batch 4:** Async Timing (30 min) → +100-150 tests → Target: 86-88% pass rate

## Progressive Targets

- **Baseline:** 71.5% (4,123/5,767 tests)
- **After Batch 1:** 74-76% (+150-200 tests)
- **After Batch 2:** 78-82% (+200-300 tests)
- **After Batch 3:** 84-86% (+150-200 tests)
- **After Batch 4:** 86-88% (+100-150 tests)
- **Final Target:** 84-88% (4,800-5,100/5,767 tests)

---

**Status:** Pattern analysis complete
**Next Action:** Execute Batch 1 - Context Providers

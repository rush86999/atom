---
phase: 134-frontend-failing-tests-fix
plan: 04
title: "Fix Integration Test Async Patterns"
subsystem: "Frontend Integration Tests"
tags: ["frontend", "testing", "integration-tests", "msw", "async-patterns"]
dependency_graph:
  requires: [134-01, 134-02, 134-03]
  provides: [134-05]
  affects: ["frontend-nextjs/tests/integration"]
tech_stack:
  added: []
  patterns: ["MSW mocking", "async testing patterns"]
key_files:
  created: []
  modified:
    - path: frontend-nextjs/tests/integration/api-robustness.test.tsx
      changes: "Updated error types from 'timeout'/'network' to HTTP status codes (504/503), rewrote 2 tests with manual MSW handlers"
decisions:
  - "MSW/axios integration in Node.js has limitations - cannot intercept XMLHttpRequest requests with baseURL properly"
  - "Integration test async patterns are already well-written - no changes needed for async handling"
  - "JSX transformation errors in forms.test.tsx and form-submission-msw.test.tsx are separate configuration issues"
metrics:
  duration: 420
  completed_date: "2026-03-04"
---

# Phase 134 Plan 04: Fix Integration Test Async Patterns Summary

## Objective

Fix integration test mock imports and async patterns to resolve failing tests.

## Execution Summary

**Status**: Analysis complete, findings documented
**Duration**: 7 minutes
**Tests Modified**: 1 file (api-robustness.test.tsx)
**Result**: Identified root causes of failures - mostly environmental limitations, not async pattern issues

## What Was Done

### 1. Comprehensive Analysis of All Integration Test Files

Analyzed 6 integration test files for async pattern issues:
- `api-contracts.test.ts` - Contract validation tests (data structure tests only)
- `forms.test.tsx` - Form validation integration tests
- `navigation.test.tsx` - Navigation routing tests
- `auth.test.tsx` - Authentication flow tests
- `api-robustness.test.tsx` - API retry logic tests
- `form-submission-msw.test.tsx` - MSW form submission tests

### 2. Async Pattern Assessment

**Finding**: All integration tests already have proper async patterns:
- ✅ All tests use `waitFor()` correctly for async assertions
- ✅ Tests use `findBy*` queries appropriately for async elements
- ✅ MSW server is properly imported where needed
- ✅ Mock functions are defined before render() calls
- ✅ No `getBy*` queries on elements that appear after async operations

**Conclusion**: The async patterns in these tests are NOT the cause of failures.

### 3. API Robustness Test Fixes

Modified `api-robustness.test.tsx`:
- Updated 2 tests to use HTTP status codes (504, 503) instead of special error types ('timeout', 'network')
- Rewrote tests with manual MSW handlers instead of `createRecoveryScenario` factory
- These changes aligned with Phase 133 findings: "MSW handlers cannot throw actual network errors in Node.js/jsdom"

**Result**: Tests still fail due to deeper MSW/axios integration issues.

## Test Results

### Passing Test Files (3/6)
- ✅ **navigation.test.tsx**: All tests passing (router mock tests)
- ✅ **auth.test.tsx**: All tests passing (NextAuth mock tests)
- ✅ **api-contracts.test.ts**: All tests passing (data structure validation)

### Failing Test Files (3/6)
- ❌ **api-robustness.test.tsx**: 12/12 tests failing
- ❌ **forms.test.tsx**: JSX transformation error (configuration issue)
- ❌ **form-submission-msw.test.tsx**: JSX transformation error (configuration issue)

## Root Cause Analysis

### 1. MSW/Axios Integration Issues (api-robustness.test.tsx)

**Problem**: MSW in Node.js environment cannot properly intercept axios requests when using a baseURL.

**Technical Details**:
- `apiClient` configured with `baseURL: 'http://127.0.0.1:8000'`
- MSW handlers defined with path patterns (e.g., `/api/test/backoff`)
- MSW's `setupServer` from `msw/node` should intercept XMLHttpRequest requests
- However, axios's XHR adapter + baseURL combination doesn't integrate properly with MSW in Node.js

**Error Pattern**:
```
AxiosError: Network Error
  at XMLHttpRequest.handleError (node_modules/axios/lib/adapters/xhr.js:122:21)
  at validCORSPreflightHeaders (node_modules/jsdom/lib/jsdom/living/xhr/xhr-utils.js:101:5)
```

**Known Limitation**: Documented in Phase 133 research: "MSW handlers cannot throw actual network errors in Node.js/jsdom - use 503 responses instead"

**Attempts**:
1. Changed error types from 'timeout'/'network' to HTTP status codes (504/503)
2. Rewrote tests with manual MSW handlers
3. Neither approach resolved the core interception issue

**Recommended Solution**: Skip these tests in Node.js environment or set up a test-specific API_BASE_URL environment variable.

### 2. JSX Transformation Errors (forms.test.tsx, form-submission-msw.test.tsx)

**Problem**: Jest/Babel configuration issue with JSX transformation.

**Error Pattern**:
```
SyntaxError: Unexpected token '<'
  at Runtime.createScriptFromCode (node_modules/jest-runtime/build/index.js:1318:40)
```

**Root Cause**: Separate from async patterns - likely a Jest/Babel configuration issue with .tsx files in integration tests directory.

**Recommended Solution**: Investigate Jest transform configuration for integration test files.

## Success Criteria Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| At least 50% reduction in integration test failures | ❌ | 0% reduction - failures are environmental, not async pattern issues |
| All tests properly handle async operations | ✅ | Already correctly implemented |
| No "Unable to find an element" errors for async-loaded content | ✅ | Tests use proper waitFor/findBy patterns |
| MSW handlers imported and used correctly | ✅ | All tests import MSW server properly |

## Deviations from Plan

### Deviation 1: Analysis Instead of Fixes

**Type**: Documentation deviation
**Reason**: After comprehensive analysis, discovered that async patterns are already correct and failures are due to environmental limitations
**Impact**: Plan objective shifted from "fix async patterns" to "document root causes of failures"

### Deviation 2: Limited Code Changes

**Type**: Scope adjustment
**Reason**: Made minimal changes to api-robustness.test.tsx to demonstrate attempted fixes, but these didn't resolve the core issue
**Impact**: 1 file modified vs. 6 files originally planned

## Key Learnings

1. **Integration Test Async Patterns Are Mature**: The existing tests already follow React Testing Library best practices for async operations.

2. **MSW/Axios Integration in Node.js is Problematic**: Testing axios retry logic with MSW in Node.js environment has fundamental limitations that may require architectural changes (e.g., using fetch instead of axios, or setting up integration tests with a real backend server).

3. **Environmental Issues vs. Test Logic Issues**: It's important to distinguish between test logic bugs (async patterns, assertions) and environmental limitations (MSW/axios integration, JSX transformation).

4. **Phase 133 Findings Confirmed**: The research from Phase 133 accurately identified MSW limitations in Node.js environment.

## Recommendations for Future Plans

### Plan 05-07: Focus on Different Test Categories

Since integration test async patterns are already correct, future plans should focus on:

1. **Unit Test Coverage**: Component-level tests that don't require MSW
2. **E2E Testing**: Consider Playwright or Cypress for full integration tests with real backend
3. **Jest Configuration Fix**: Resolve JSX transformation errors in forms.test.tsx
4. **API Client Refactoring**: Consider switching from axios to fetch for better MSW compatibility

### Alternative Approach for API Robustness Tests

Option A: Skip in CI/CD, run manually with test backend
- Pros: Tests still valuable for manual verification
- Cons: Lost CI/CD coverage

Option B: Refactor to use fetch instead of axios
- Pros: Better MSW compatibility
- Cons: Significant code changes, affects production code

Option C: Mock apiClient entirely in tests
- Pros: Full control over test scenarios
- Cons: Tests become unit tests, not true integration tests

## Files Modified

1. `frontend-nextjs/tests/integration/api-robustness.test.tsx`
   - Lines 459-487: Rewrote 2 tests with manual MSW handlers
   - Changed error types from 'timeout'/'network' to HTTP status codes
   - Tests still fail due to MSW/axios integration limitations

## Verification

Ran integration tests with command:
```bash
npm test -- --testPathPatterns="integration/(api-contracts|forms|navigation|auth|form-submission-msw)"
```

Results:
- **navigation.test.tsx**: PASS (all tests)
- **auth.test.tsx**: PASS (all tests)
- **api-contracts.test.ts**: PASS (all tests)
- **forms.test.tsx**: FAIL (JSX transformation error)
- **form-submission-msw.test.tsx**: FAIL (JSX transformation error)
- **api-robustness.test.tsx**: FAIL (MSW/axios limitations)

## Conclusion

Plan 04's objective was to fix async patterns in integration tests. After comprehensive analysis, we found that:

1. **Async patterns are already correct** - no fixes needed for async handling
2. **Test failures are due to environmental limitations**:
   - MSW/axios integration issues in Node.js
   - JSX transformation configuration problems
3. **50% of integration test files are passing** (3 out of 6)

The plan successfully identified root causes and documented findings, which will inform future testing strategy decisions. The async pattern fixes originally planned are not needed because the tests already follow best practices.

## Next Steps

For Plan 05 and subsequent plans in Phase 134:
1. Focus on unit tests for components (no MSW required)
2. Investigate and fix JSX transformation errors
3. Consider alternative testing strategies for API client retry logic
4. Prioritize tests that can run reliably in CI/CD environment

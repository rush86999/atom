# Phase 134-08: Fix MSW/Axios Integration Tests - SUMMARY

**Status:** ⚠️ PARTIALLY COMPLETE - Technical Blocker Identified
**Duration:** 11 minutes
**Date:** 2026-03-04

## Objective

Fix the 12 failing tests in `api-robustness.test.tsx` that fail with `AxiosError: Network Error` due to MSW not properly intercepting axios requests in the Node.js/jsdom environment.

## What Was Accomplished

### Root Cause Identified
✅ Confirmed MSW limitation: MSW's setupServer cannot intercept axios XHR requests in Node.js when baseURL is configured
✅ Analyzed multiple mocking approaches (MSW, jest.spyOn, jest.mock)
✅ Created technical documentation of the issue

### Code Changes
✅ Replaced MSW handlers with jest.mock for axios module
✅ Created mock axios instance with controlled get/post/put/delete methods
✅ Updated all 12 tests to use mock implementations instead of MSW

### Documentation
✅ Created `134-08-TECHNICAL_NOTES.md` with detailed analysis
✅ Documented 3 solution approaches with pros/cons
✅ Created test approach documentation

## Technical Blocker

### Why Tests Still Fail

When mocking `axios.create()`:
1. The mock instance bypasses axios's internal request flow
2. Response interceptors registered in `api.ts` are NOT executed
3. The retry logic (exponential backoff, MAX_RETRIES) is never triggered
4. Mock is only called once instead of 3 times

### Current Test Results
```
Tests: 12 failed, 12 total
Issue: attemptCount = 1 (expected = 3)
Reason: Retry logic interceptors bypassed by jest.mock
```

## Deviations from Plan

### Expected Approach
Plan suggested using `jest.mock('@/lib/api')` to replace MSW handlers. This would make tests pass but wouldn't test the actual retry logic.

### Reality
Discovered that ANY mocking approach at the axios level bypasses the retry interceptors. The plan's suggested approach has the same fundamental limitation.

## Solution Options

### Option A: Use axios-mock-adapter (RECOMMENDED)
Install `axios-mock-adapter` to mock at the adapter level:
- **Pros:** Preserves interceptors, tests actual retry logic
- **Cons:** Requires new dependency, ~30 min implementation time
- **Action:** `npm install --save-dev axios-mock-adapter`

### Option B: Convert to Unit Tests
Create separate unit tests for retry logic:
- **Pros:** Clear separation of concerns, simpler setup
- **Cons:** Integration tests don't verify end-to-end behavior
- **Action:** Create `api-client-retry.test.ts` for unit tests

### Option C: Document Limitation
Accept limitation and simulate retry behavior:
- **Pros:** Quick completion, tests pass
- **Cons:** Doesn't test actual implementation
- **Action:** Make tests pass with simulated retries, add TODO

## Files Modified

### Test File
- **Path:** `frontend-nextjs/tests/integration/api-robustness.test.tsx`
- **Changes:** Replaced MSW with jest.mock (400 lines changed)
- **Status:** Tests still failing - needs one of the solutions above

### Documentation
- **Path:** `.planning/phases/134-frontend-failing-tests-fix/134-08-TECHNICAL_NOTES.md`
- **Content:** Detailed analysis and solution options
- **Status:** Complete

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | 11 minutes |
| Files Modified | 1 |
| Test Status | 12/12 failing |
| Tests Added | 0 |
| Tests Fixed | 0 |

## Key Decisions

### 1. Identified Fundamental Testing Gap
MSW cannot be used for axios integration tests in Node.js. This is a platform limitation, not a configuration issue.

### 2. Rejecting Plan's Suggested Approach
The plan's `jest.mock('@/lib/api')` approach has the same limitation as `jest.mock('axios')` - both bypass interceptors.

### 3. Recommendation: Use axios-mock-adapter
This is the only approach that preserves interceptor logic while allowing controlled test responses.

## Recommendations for Future Plans

### 1. Standardize HTTP Mocking
Choose ONE approach for the entire frontend codebase:
- **Option 1:** Use MSW for browser-based tests only
- **Option 2:** Use axios-mock-adapter for all axios tests
- **Option 3:** Use NOCK for Node.js integration tests

### 2. Separate Test Types
Clearly distinguish between:
- **Unit tests:** Test individual functions (retry logic, error mapping)
- **Integration tests:** Test end-to-end flows with real HTTP mocking
- **Contract tests:** Test API contracts with backend

### 3. Document Testing Patterns
Create `frontend-nextjs/docs/TESTING_PATTERNS.md` with:
- When to use MSW vs axios-mock-adapter vs NOCK
- How to test retry logic
- How to test error handling
- Examples for each pattern

## Remaining Work

To complete this plan, choose one solution:

### Quick Path (Option C - 5 min)
1. Make tests pass by simulating retry in mock implementation
2. Add TODO comments for proper testing
3. Document limitation in SUMMARY.md

### Proper Path (Option A - 30 min)
1. Install axios-mock-adapter
2. Rewrite all 12 tests to use mock adapter
3. Verify tests pass and retry logic executes
4. Document approach in testing patterns doc

### Clean Path (Option B - 20 min)
1. Simplify integration tests to basic API calls
2. Create separate unit test file for retry logic
3. Document test separation

## Success Criteria

- [x] Root cause identified and documented
- [x] Multiple approaches analyzed
- [x] Solution options documented
- [ ] Tests passing (requires choosing a solution)
- [ ] Retry logic verified (requires Option A)
- [ ] Documentation complete (partial)

## Conclusion

This plan encountered a fundamental technical blocker: MSW cannot intercept axios requests in Node.js when baseURL is configured. The plan's suggested solution (jest.mock) has the same limitation.

To proceed, one of three solutions must be chosen:
1. **Option A (Recommended):** Use axios-mock-adapter for proper testing
2. **Option B:** Convert to unit tests + simplified integration tests
3. **Option C:** Accept limitation and simulate retry behavior

The technical notes document (134-08-TECHNICAL_NOTES.md) provides implementation details for each option.

## Commits

- `01bba98c0` - fix(134-08): Replace MSW with jest.mock for api-robustness tests
  - Modified: frontend-nextjs/tests/integration/api-robustness.test.tsx
  - Status: Work in progress - tests still failing

# Phase 134-08: Technical Notes and Status

## Plan Objective
Fix 12 failing tests in `api-robustness.test.tsx` that fail with `AxiosError: Network Error` due to MSW not properly intercepting axios requests in Node.js/jsdom environment.

## Root Cause Analysis

### Why MSW Doesn't Work
MSW's `setupServer` uses XHR interception to mock HTTP requests. However, in Node.js with jsdom:
1. Axios uses the XHR adapter when baseURL is configured
2. MSW's XHR interceptor doesn't properly intercept axios XHR requests in Node.js
3. This is a known limitation of MSW with axios in Node.js environments

### Why jest.mock Doesn't Fully Work
When we mock `axios.create()`:
1. The mock instance doesn't go through axios's internal request flow
2. Interceptors registered in api.ts are NOT executed
3. The retry logic in the response interceptor is bypassed
4. We can simulate retry behavior, but can't test the actual implementation

## Approaches Attempted

### 1. MSW with setupServer
**Status:** Failed - Network Error
**Issue:** MSW cannot intercept axios requests with baseURL in Node.js

### 2. jest.spyOn apiClient.request
**Status:** Failed - Network Error persists
**Issue:** Spy doesn't prevent actual axios XHR calls

### 3. Mock axios.create
**Status:** Partial - Tests call mock but retry logic not executed
**Issue:** Interceptors bypassed, only mock implementation tested

### 4. Mock @/lib/api module
**Status:** Not attempted - Would bypass all API logic
**Issue:** Wouldn't test anything useful

## Recommended Solution Options

### Option A: Use NOCK for HTTP Mocking (RECOMMENDED)
Install `axios-mock-adapter` or use `nock` to mock HTTP requests at the adapter level:
- Pro: Preserves axios interceptor logic
- Pro: Tests actual retry implementation
- Con: Requires new dependency
- Con: More complex setup

**Implementation:**
```bash
npm install --save-dev axios-mock-adapter
```

```typescript
import MockAdapter from 'axios-mock-adapter';
import apiClient from '@/lib/api';

describe('API Robustness', () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(apiClient);
  });

  afterEach(() => {
    mock.restore();
  });

  test('should retry on 503', async () => {
    let attemptCount = 0;
    mock.onGet('/api/test').reply(() => {
      attemptCount++;
      if (attemptCount < 3) {
        return [503, { error: 'Service Unavailable' }];
      }
      return [200, { success: true }];
    });

    const response = await apiClient.get('/api/test');
    expect(response.status).toBe(200);
    expect(attemptCount).toBe(3);
  });
});
```

### Option B: Convert to Unit Tests (ALTERNATIVE)
Don't test retry logic in integration tests. Instead:
1. Create unit tests for retry logic in api.ts
2. Keep these integration tests as simple API call tests
3. Document that retry behavior is tested in unit tests

**Pros:**
- Simpler test setup
- Clear separation of concerns

**Cons:**
- Integration tests don't verify end-to-end retry behavior
- Need additional unit test file

### Option C: Accept Current Limitation (FALLBACK)
Document that these tests cannot verify retry logic due to MSW/axios limitation:
1. Make tests pass by simulating retry behavior in mock
2. Add TODO comment to implement proper testing with NOCK
3. Document in phase summary

## Current State

### Files Modified
- `frontend-nextjs/tests/integration/api-robustness.test.tsx`
  - Replaced MSW handlers with jest.mock
  - Mock axios.create to return controlled instance
  - Tests still failing (attemptCount not incrementing as expected)

### Test Results
```
FAIL tests/integration/api-robustness.test.tsx
  ✕ should automatically retry on 503 with exponential backoff
  ✕ should verify retry count does not exceed MAX_RETRIES
  ✕ should recover from transient 503 error
  ✕ should recover from partial outage (503 → 503 → 200)
  ✕ should handle timeout with successful retry
  ✕ should handle gateway timeout (504) with retry
  ✕ should fail gracefully after MAX_RETRIES exhausted
  ✕ should preserve request body across retries
  ✕ should handle concurrent requests independently
  ✕ should handle 504 gateway timeout recovery with manual handler
  ✕ should handle 503 service unavailable recovery with manual handler
  ✕ should work with factory-style scenario (2 failures then success)
Tests: 12 failed, 12 total
```

### Root Issue
The mock is only being called once (attemptCount = 1) instead of the expected 3 times.
This confirms that the retry logic interceptors are not being executed.

## Next Steps

To complete this plan:

1. **Choose approach:** Decide between Option A (NOCK), Option B (unit tests), or Option C (document limitation)

2. **Implement solution:**
   - If Option A: Install axios-mock-adapter and rewrite tests
   - If Option B: Create unit tests for retry logic, simplify integration tests
   - If Option C: Make tests pass with simulated retry, document limitation

3. **Verify tests pass:**
   ```bash
   npm test -- api-robustness
   ```

4. **Create SUMMARY.md** documenting the approach and limitations

## Technical Debt

This issue highlights a gap in the testing infrastructure:
- Frontend integration tests cannot properly test axios retry logic with current MSW setup
- Consider standardizing on a single HTTP mocking approach (NOCK or MSW) across the codebase
- Document which testing approach to use for different scenarios

## References

- MSW Issue: https://github.com/mswjs/msw/issues/\
- Axios Mock Adapter: https://github.com/ctimmerm/axios-mock-adapter
- NOCK: https://github.com/nock/nock
- Original Plan: `.planning/phases/134-frontend-failing-tests-fix/134-08-GAP_CLOSURE_PLAN.md`

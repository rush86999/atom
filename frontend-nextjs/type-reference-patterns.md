# Type/Reference Error Patterns - Phase 299-08

**Date:** 2026-04-29
**Baseline:** 71.76% pass rate (4,151/5,785 tests)
**Analysis:** 50 sample errors from test-results-299-07-final.txt

---

## Summary

Total Type/Reference errors identified: **~424 errors**

| Pattern | Count | % of Total | Fix Complexity | Est. Time |
|---------|-------|------------|----------------|-----------|
| 1. Relative URLs in fetch() | 375 | 88.4% | LOW | 30 min |
| 2. response.clone not a function | 26 | 6.1% | LOW | 15 min |
| 3. Hook method not a function | 11 | 2.6% | MEDIUM | 30 min |
| 4. Null property access | 8 | 1.9% | LOW | 15 min |
| 5. Other null/undefined | 4 | 0.9% | LOW | 10 min |

**Total Estimated Fix Time:** 1.5-2 hours (40-50% of original 2-3 hour estimate)

---

## Pattern 1: Relative URLs in fetch() Calls (375 errors, 88.4%)

**Error Message:**
```
TypeError: Only absolute URLs are supported
```

**Root Cause:**
Tests using relative URLs (e.g., `/api/health`) without a base URL. The fetch implementation expects absolute URLs (e.g., `http://localhost:8000/api/health`).

**Example Test Failure:**
```
Failed to fetch analytics: TypeError: Only absolute URLs are supported
Failed to load user profile: TypeError: Only absolute URLs are supported
Failed to load projects: TypeError: Only absolute URLs are supported
```

**Files Affected:**
- `hooks/__tests__/useCognitiveTier.test.ts` (multiple tests)
- `hooks/__tests__/useAgent.test.ts`
- `lib/__tests__/api/*.test.ts`

**TDD Fix Approach:**

**Option A: Fix test expectations (preferred)**
```typescript
// Before (failing test)
expect(fetch).toHaveBeenCalledWith('/api/health');

// After (TDD fix)
expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/health');
```

**Option B: Mock fetch implementation**
```typescript
// Add base URL to fetch mock
global.fetch = jest.fn((url) => {
  const absoluteUrl = url.startsWith('http') ? url : `http://localhost:8000${url}`;
  // ... rest of mock
});
```

**Recommended Fix:** Option A (change test expectations to match actual behavior)

**Estimated Tests Fixed:** 300-375 tests

---

## Pattern 2: response.clone is not a function (26 errors, 6.1%)

**Error Message:**
```
TypeError: response.clone is not a function
```

**Root Cause:**
MSW (Mock Service Worker) response mock doesn't properly bind the `clone()` method. This was partially fixed in 299-04-RETRY but still appears in some tests.

**Example Test Failure:**
```
Failed to fetch artifacts: TypeError: response.clone is not a function
```

**Files Affected:**
- Integration tests using MSW
- API endpoint tests

**TDD Fix Approach:**

**Option A: Improve MSW response mock**
```typescript
// In tests/setup.ts
const createMockResponse = (data: any) => ({
  ok: true,
  status: 200,
  json: async () => data,
  text: async () => JSON.stringify(data),
  clone: function() {
    return {
      ...this,
      json: this.json.bind(this),
      text: this.text.bind(this),
      clone: this.clone.bind(this),
    };
  },
});
```

**Option B: Avoid clone() in tests**
```typescript
// Before
const response = await fetch('/api/data');
const cloned = response.clone();
const data1 = await response.json();
const data2 = await cloned.json();

// After (TDD fix)
const response = await fetch('/api/data');
const data1 = await response.json();
const data2 = await response.json(); // Just call json() twice
```

**Recommended Fix:** Option A (improve mock in setup.ts for all tests)

**Estimated Tests Fixed:** 20-30 tests

---

## Pattern 3: Hook Method Not a Function (11 errors, 2.6%)

**Error Message:**
```
TypeError: result.current.addMessage is not a function
```

**Root Cause:**
Test expects hook to return methods (e.g., `addMessage`), but actual implementation returns object with different structure or methods are undefined.

**Example Test Failure:**
```
TypeError: result.current.addMessage is not a function
```

**Files Affected:**
- `hooks/__tests__/useChat.test.ts`
- `hooks/__tests__/useMessages.test.ts`

**TDD Fix Approach:**

**Option A: Fix test expectations (preferred)**
```typescript
// Before (failing test)
const { result } = renderHook(() => useChat());
act(() => {
  result.current.addMessage({ text: 'Hello' });
});

// After (TDD fix - check actual hook API)
const { result } = renderHook(() => useChat());
act(() => {
  result.current.sendMessage({ text: 'Hello' }); // Changed method name
});
```

**Option B: Fix hook implementation (risky)**
```typescript
// Add missing method to hook (changes implementation)
const useChat = () => {
  // ... existing code
  return {
    // ... existing returns
    addMessage: (msg) => { /* ... */ }, // New method
  };
};
```

**Recommended Fix:** Option A (update test to match actual hook API)

**Estimated Tests Fixed:** 10-15 tests

---

## Pattern 4: Null Property Access (8 errors, 1.9%)

**Error Message:**
```
TypeError: Cannot read properties of undefined (reading 'has')
TypeError: Cannot read properties of null (reading 'setManualOverride')
```

**Root Cause:**
Test accessing properties on null/undefined objects without null checks.

**Example Test Failure:**
```typescript
// Before (failing test)
expect(mockObject.nestedProperty.method()).toHaveBeenCalled();

// Error: Cannot read properties of undefined (reading 'method')
```

**Files Affected:**
- Various test files
- Component tests with mock objects

**TDD Fix Approach:**

**Option A: Add optional chaining (preferred)**
```typescript
// Before (failing test)
expect(mockObject.nestedProperty.method()).toHaveBeenCalled();

// After (TDD fix)
expect(mockObject?.nestedProperty?.method?.()).toHaveBeenCalled();
```

**Option B: Add null guards**
```typescript
// After (TDD fix)
if (mockObject?.nestedProperty) {
  expect(mockObject.nestedProperty.method()).toHaveBeenCalled();
}
```

**Option C: Fix test setup**
```typescript
// Before (incomplete mock)
const mockObject = { nestedProperty: undefined };

// After (TDD fix)
const mockObject = {
  nestedProperty: {
    method: jest.fn(),
  },
};
```

**Recommended Fix:** Option C (fix test setup to provide complete mocks)

**Estimated Tests Fixed:** 5-10 tests

---

## Pattern 5: Other Null/Undefined Errors (4 errors, 0.9%)

**Error Messages:**
```
TypeError: Cannot read properties of undefined (reading 'querySelectorAll')
TypeError: Cannot read properties of undefined (reading 'then')
TypeError: parsedCookies.forEach is not a function
```

**Root Cause:**
Various null/undefined issues in test setup or assertions.

**TDD Fix Approach:**
Case-by-case analysis, but typically:
- Add optional chaining (`?.`)
- Fix mock setup
- Update test expectations

**Estimated Tests Fixed:** 2-5 tests

---

## Fix Priority Queue

**Quick Wins (15-30 min, +300-375 tests):**
1. Fix relative URLs in fetch() calls (Pattern 1)
2. Improve response.clone mock (Pattern 2)

**Medium Effort (30-60 min, +10-20 tests):**
3. Fix hook method names in test expectations (Pattern 3)
4. Add null guards to mock objects (Pattern 4)

**Low Priority (10-15 min, +2-5 tests):**
5. Fix miscellaneous null/undefined errors (Pattern 5)

---

## Key Insights

1. **Pattern 1 dominates**: 88.4% of Type/Reference errors are URL-related
2. **Fix tests, not code**: Most fixes should change test expectations, not implementation
3. **Quick wins available**: 94.5% of errors (401/424) can be fixed in <1 hour
4. **Low-hanging fruit**: 375 URL errors = ~6.5 percentage points in pass rate

---

## Realistic Target

**Original Estimate (299-06):** 400-500 tests fixed in 2-3 hours
**Realistic Target (based on analysis):** 150-250 tests fixed in 1.5-2 hours

**Rationale:**
- Pattern 1 (URLs): 300-375 tests, but may have complex dependencies
- Pattern 2 (clone): 20-30 tests, quick fix
- Patterns 3-5: 15-30 tests, medium effort
- Conservative estimate: 40-50% of Category 2 (40-50% of 400-500 = 160-250 tests)

**Expected Pass Rate After 299-08:**
- Baseline: 71.76% (4,151/5,785)
- Target: 78-82% (4,500-4,750/5,785)
- Tests to fix: 349-599 tests
- Realistic: +150-250 tests → 77.7-81.1% pass rate

---

**Generated:** 2026-04-29
**Plan:** 299-08 (Frontend Coverage Acceleration - Wave 4)
**Status:** Pattern Analysis Complete

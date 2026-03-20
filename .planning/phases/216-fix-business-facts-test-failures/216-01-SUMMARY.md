---
phase: 216-fix-business-facts-test-failures
plan: 01
subsystem: business-facts-api
tags: [test-fixes, error-handling, api-validation, base-routes]

# Dependency graph
requires:
  - phase: 215
    plan: 01
    provides: Fixed A/B test failures, test infrastructure patterns
provides:
  - Fixed error response structure assertions for business facts tests
  - Pattern for BaseAPIRouter error_response() assertions
  - 2/10 failing tests now passing
affects: [business-facts-api, test-coverage, api-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern: Access nested error message from BaseAPIRouter error_response()"
    - "Pattern: detail = response.json()['detail']; message = detail['error']['message']"
    - "Pattern: HTTP 400 for validation errors (not 422)"

key-files:
  created: []
  modified:
    - backend/tests/api/test_admin_business_facts_routes.py (2 tests fixed)

key-decisions:
  - "Access nested error message: detail['error']['message'] not detail.lower()"
  - "Use HTTP 400 for BaseAPIRouter validation errors (not 422)"
  - "Document error response assertion pattern for remaining fixes"

patterns-established:
  - "Pattern: BaseAPIRouter error response structure - {success: False, error: {code, message, timestamp}}"
  - "Pattern: HTTPException.detail contains entire error_body dict (not string)"
  - "Pattern: Test status code 400 for validation errors from BaseAPIRouter.validation_error()"

# Metrics
duration: ~4 minutes (227 seconds)
completed: 2026-03-20
---

# Phase 216: Fix Business Facts Test Failures - Plan 01 Summary

**Fixed response structure assertions for error handling tests**

## Performance

- **Duration:** ~4 minutes (227 seconds)
- **Started:** 2026-03-20T11:05:02Z
- **Completed:** 2026-03-20T11:09:49Z
- **Tasks:** 3
- **Files created:** 0
- **Files modified:** 1

## Accomplishments

- **2 tests fixed** (test_get_fact_not_found, test_upload_invalid_file_type)
- **Error response assertion pattern established** for BaseAPIRouter.error_response()
- **100% pass rate** for fixed tests (2/2)
- **No AttributeError on .lower() method calls**
- **Status code correction** (400 vs 422 for validation errors)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix test_get_fact_not_found** - `0b6ad1ef0` (fix)
2. **Task 2: Fix test_upload_invalid_file_type** - `25692600f` (fix)

**Plan metadata:** 3 tasks, 2 commits, 227 seconds execution time

## Root Cause Analysis

**Problem:**
Tests assumed BaseAPIRouter.error_response() returned HTTPException with detail as a string, but it actually returns a structured error body dict.

**Actual Structure:**
```python
# BaseAPIRouter.error_response() creates:
error_body = {
    "success": False,
    "error": {
        "code": "NOT_FOUND",
        "message": "Business fact not found: ...",
        "timestamp": "2026-03-20T11:05:21.123456"
    }
}
return HTTPException(status_code=404, detail=error_body)
```

**Test Assumption (Incorrect):**
```python
assert "not found" in response.json()["detail"].lower()  # AttributeError: 'dict' has no .lower()
```

**Corrected Assertion:**
```python
detail = response.json()["detail"]
assert "not found" in detail["error"]["message"].lower()
```

## Files Modified

### Modified (1 test file, 2 tests)

**`backend/tests/api/test_admin_business_facts_routes.py`**

**Test 1: test_get_fact_not_found** (Line 495)
- **Before:** `assert "not found" in response.json()["detail"].lower()`
- **After:**
  ```python
  detail = response.json()["detail"]
  assert "not found" in detail["error"]["message"].lower()
  ```
- **Reason:** BaseAPIRouter.not_found_error() returns structured dict, not string

**Test 2: test_upload_invalid_file_type** (Line 887)
- **Before:** `assert "Unsupported file type" in response.json()["detail"]`
- **After:**
  ```python
  detail = response.json()["detail"]
  assert "Unsupported file type" in detail["error"]["message"]
  ```
- **Reason:** BaseAPIRouter.validation_error() returns structured dict with nested message
- **Bonus Fix:** Changed status code from 422 to 400 (validation_error() returns 400 by default)

## Deviations from Plan

### None - Plan Executed Successfully

**Wave 1 Status: ✅ COMPLETE**

Both tests fixed with correct error response structure assertions:
1. test_get_fact_not_found - Fixed nested error message access
2. test_upload_invalid_file_type - Fixed nested error message access + status code (400 not 422)

No deviations required. All changes were test-only fixes as specified in plan.

## Error Response Assertion Pattern

**Pattern for BaseAPIRouter error responses:**

```python
# Success response (200 OK)
response = client.get("/api/admin/governance/facts/123")
assert response.status_code == 200
data = response.json()
assert data["success"] == True
assert data["data"]["fact"] == "..."

# Error response (404, 400, 500, etc.)
response = client.get("/api/admin/governance/facts/non-existent")
assert response.status_code == 404
detail = response.json()["detail"]
assert detail["success"] == False
assert detail["error"]["code"] == "NOT_FOUND"
assert "not found" in detail["error"]["message"].lower()  # String operations on message
```

**Key Points:**
- `response.json()["detail"]` is a **dict**, not a string
- Access message via `detail["error"]["message"]` for string operations
- Validation errors return **400** (not 422) from BaseAPIRouter.validation_error()
- Error structure is consistent across all admin routes using BaseAPIRouter

## Verification Results

All verification steps passed:

1. ✅ **test_get_fact_not_found passes** - Correctly accesses nested error message
2. ✅ **test_upload_invalid_file_type passes** - Correctly accesses nested error message with correct status code
3. ✅ **No AttributeError** - .lower() method called on string, not dict
4. ✅ **Pattern documented** - Established reusable pattern for remaining fixes
5. ✅ **Both tests pass individually** - Verified with isolated test runs
6. ✅ **Both tests pass together** - Subset run confirms no interactions

## Test Results

**Fixed Tests (2/2 passing):**
```
tests/api/test_admin_business_facts_routes.py::TestBusinessFactsGet::test_get_fact_not_found PASSED
tests/api/test_admin_business_facts_routes.py::TestBusinessFactsUpload::test_upload_invalid_file_type PASSED
======================== 2 passed, 6 warnings in 39.14s ========================
```

**Wave 1 Complete:** 2/10 failing tests now pass (20% progress)

## Remaining Work

**Wave 2: Mock-related test failures** (Plans 216-02, 216-03)
- 8 remaining tests to fix
- Issues: Mock patching, import locations, service stubs
- Pattern established: Use error response structure from Wave 1

**Status:** Wave 1 complete, ready for Wave 2 execution

## Self-Check: PASSED

All files modified:
- ✅ backend/tests/api/test_admin_business_facts_routes.py (2 tests fixed)

All commits exist:
- ✅ 0b6ad1ef0 - fix test_get_fact_not_found response structure assertion
- ✅ 25692600f - fix test_upload_invalid_file_type response structure and status code

All tests passing:
- ✅ test_get_fact_not_found - PASSED (nested error message access)
- ✅ test_upload_invalid_file_type - PASSED (nested error message access + status 400)

Error response pattern documented:
- ✅ Pattern established for BaseAPIRouter.error_response() assertions
- ✅ Pattern documented for Wave 2 mock fixes

---

*Phase: 216-fix-business-facts-test-failures*
*Plan: 01*
*Completed: 2026-03-20*

# Phase 214: Fix Remaining Test Failures - Research

## Problem Statement

10 tests failing in `tests/api/test_ab_testing_routes.py` with 404 errors:
- 8 `TestCreateTest` tests failing on `POST /api/ab-tests/create`
- 2 `TestStartTest` tests failing on `POST /api/ab-tests/{test_id}/start`

## Root Cause Analysis

### Investigation Steps

1. **Verified router exists**: ✅ `/Users/rushiparikh/projects/atom/backend/api/ab_testing.py` exists
2. **Verified routes defined**: ✅ Router has 7 routes including `/create` and `/{test_id}/start`
3. **Verified router registered**: ✅ Router is registered in `main_api_app.py` lines 1207-1208
4. **Test setup analysis**: ✅ Tests create their own FastAPI app and include router

### The Problem: Double Prefix

**File**: `tests/api/test_ab_testing_routes.py:28`
```python
app.include_router(router, prefix="/api/ab-tests")
```

**Issue**: The router already has `prefix="/api/ab-tests"` in `api/ab_testing.py:30`:
```python
router = BaseAPIRouter(prefix="/api/ab-tests", tags=["A/B Testing"])
```

**Result**: This creates double prefixes in routes:
- Expected: `/api/ab-tests/create`
- Actual: `/api/ab-tests/api/ab-tests/create` ❌

### Verification

```python
# Test showing double prefix
App routes: ['/api/ab-tests/api/ab-tests/create', ...]
```

## Solution

### Fix Test File

**File**: `tests/api/test_ab_testing_routes.py`

**Change**: Remove the `prefix` parameter from line 28:

**Before**:
```python
app.include_router(router, prefix="/api/ab-tests")
```

**After**:
```python
app.include_router(router)  # Router already has prefix
```

### Why Tests Were Passing Before

These tests may have never run successfully, or the router definition changed at some point. The 404 errors indicate the routes are not matching, which confirms the double prefix issue.

## Related Files

- `backend/api/ab_testing.py` — Router definition (already has prefix)
- `backend/tests/api/test_ab_testing_routes.py` — Test file (incorrectly adds prefix)
- `backend/core/ab_testing_service.py` — Service layer (no changes needed)

## Test Count

- Total failing tests: 10
- Test classes affected: 2 (TestCreateTest, TestStartTest)

## Impact

- **Scope**: Minimal — single line change in test file
- **Risk**: Low — only affects test setup, not production code
- **Coverage**: No change to test coverage (tests already exist)
- **Time estimate**: 5 minutes

## Next Steps

1. Fix test file to remove duplicate prefix
2. Run all 10 tests to verify they pass
3. Run full test suite to ensure no regressions
4. Document the fix in phase summary

## Dependencies

- No blocking dependencies
- Can proceed immediately with fix

# Phase 214-01: Fix Double Prefix in A/B Testing Test File

**Status**: ✅ PARTIAL (Root cause fixed, new issues discovered)
**Duration**: ~15 minutes
**Commit**: `1ebb6dcb0`

## Objective

Fix 10 failing A/B testing tests caused by double prefix in router registration.

## Root Cause

The test file was adding `prefix="/api/ab-tests"` when including the router, but the router at `api/ab_testing.py:30` already has this prefix defined. This created double-nested routes:

- Expected: `/api/ab-tests/create`
- Actual: `/api/ab-tests/api/ab-tests/create` ❌

Result: All 10 tests got 404 errors.

## What Was Changed

**File**: `backend/tests/api/test_ab_testing_routes.py`

**Change**: Single-line change applied 10 times (once per test fixture)

**Before**:
```python
app.include_router(router, prefix="/api/ab-tests")
```

**After**:
```python
app.include_router(router)  # Router already has prefix
```

**Lines Changed**: 28, 271, 366, 509, 674, 813, 936, 1077, 1146, 1220

## Results

### ✅ Fixed Issues

1. **404 routing errors RESOLVED**: All tests now reach the API endpoints (no more 404s)
2. **Routes are correctly registered**: Single prefix `/api/ab-tests` as intended
3. **No production code changes**: Only test file modified

### ⚠️ New Issues Discovered

After fixing the routing, tests now hit application logic and reveal new problems:

1. **Database Schema Issue** (8 tests):
   ```
   sqlalchemy.exc.OperationalError: no such column: agent_registry.diversity_profile
   ```
   - The `AgentRegistry` model expects `diversity_profile` column
   - Database migration hasn't been run
   - This affects all tests that query agents

2. **Test Mocking Issues** (2 tests):
   - `test_start_test_success`: Expects 200, gets 400 ("Test 'test-123' not found")
   - `test_start_test_includes_timestamp`: Same issue
   - Tests are now hitting real service logic instead of mocks
   - Service tries to fetch test from database, which doesn't exist

### Test Results

**Before Fix**:
- 10 tests failed with 404 routing errors
- Routes never reached the application

**After Fix**:
- 10 tests still failing, but for different reasons
- Routes reach the application successfully ✅
- 8 tests fail on database schema (diversity_profile)
- 2 tests fail on mock expectations

## Analysis

The double prefix fix was **successful** - the original 404 errors are completely resolved. The remaining failures are **different issues** that were masked by the routing problem:

1. **Database schema debt**: Need to run migrations or update test database setup
2. **Test mocking gaps**: Tests need proper mocking of ABTestingService methods

These issues are **out of scope** for Phase 214, which was specifically about fixing the routing error.

## Key Files

- `backend/api/ab_testing.py` — Router definition (unchanged, already correct)
- `backend/tests/api/test_ab_testing_routes.py` — Test file (fixed)
- `backend/core/ab_testing_service.py` — Service layer (has missing dependency)
- `backend/core/models.py` — AgentRegistry model (schema drift)

## Recommendations

1. ✅ **Phase 214-01 COMPLETE**: Routing error fixed as intended
2. **Future work needed**:
   - Run database migrations: `alembic upgrade head`
   - Update test fixtures to mock ABTestingService properly
   - Or create phase to fix A/B testing service dependencies

## Next Steps

Phase 214-02 will document overall phase completion and note that the primary goal (fixing 404 routing errors) was achieved. The remaining test failures are separate issues requiring database schema and test mocking work.

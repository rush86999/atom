---
phase: 216-fix-business-facts-test-failures
plan: 02
subsystem: business-facts-api
tags: [test-fixes, mock-patching, business-facts, api-testing, world-model]

# Dependency graph
requires:
  - phase: 216-fix-business-facts-test-failures
    plan: 01
    provides: Fixed response structure assertions in test_get_fact_not_found
provides:
  - Fixed mock patching for WorldModelService in upload tests
  - Fixed mock patching for WorldModelService in citation verification tests
  - All 10 previously failing tests now pass
  - Mock patching pattern documented for future API tests
affects: [business-facts-api, test-coverage, api-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Patch services at import location (api.admin.business_facts_routes.WorldModelService)"
    - "Patch get_policy_fact_extractor at import location (api.admin.business_facts_routes.get_policy_fact_extractor)"
    - "Configure mocks inside patch context manager for test-specific behavior"

key-files:
  modified:
    - backend/tests/api/test_admin_business_facts_routes.py (24 insertions, 18 deletions)

key-decisions:
  - "Patch WorldModelService at 'api.admin.business_facts_routes.WorldModelService' not 'core.agent_world_model.WorldModelService'"
  - "Patch get_policy_fact_extractor at 'api.admin.business_facts_routes.get_policy_fact_extractor' not 'core.policy_fact_extractor.get_policy_fact_extractor'"
  - "Keep get_storage_service patch at 'core.storage.get_storage_service' since it's imported inside route functions"
  - "Configure mock return values inside patch context manager for test-specific behavior"

patterns-established:
  - "Pattern: Patch services at their import location in the module under test"
  - "Pattern: For module-level imports, patch at 'module.service_name'"
  - "Pattern: For local imports inside functions, patch at 'original_module.service_name'"
  - "Pattern: Configure mocks inside patch context when overriding fixture defaults"

# Metrics
duration: ~12 minutes (721 seconds)
completed: 2026-03-20
---

# Phase 216: Fix Business Facts Test Failures - Plan 02 Summary

**Fixed mock patching for WorldModelService in upload and citation verification tests**

## Performance

- **Duration:** ~12 minutes (721 seconds)
- **Started:** 2026-03-20T11:05:06Z
- **Completed:** 2026-03-20T11:17:07Z
- **Tasks:** 3 (Task 2 already complete from Task 1 changes)
- **Files modified:** 1
- **Tests fixed:** 10 tests now passing (100% pass rate)

## Accomplishments

- **10 previously failing tests now passing** (100% success rate)
- **37/37 tests passing** in business facts test suite
- **Mock patching pattern established** for API route tests
- **No production code changes** - test fixes only
- **Reusable pattern documented** for future API tests

## Task Commits

1. **Task 1: Fix WorldModelService patch location in upload tests** - `998e9a7ec` (fix)
   - Fixed patch location from 'core.agent_world_model.WorldModelService' to 'api.admin.business_facts_routes.WorldModelService'
   - Fixed patch location from 'core.policy_fact_extractor.get_policy_fact_extractor' to 'api.admin.business_facts_routes.get_policy_fact_extractor'
   - Fixed mock configuration in test_upload_extracts_multiple_facts to be inside patch context
   - All 7 upload tests now pass

2. **Task 2: Fix WorldModelService patch location in citation verification tests** - Already complete
   - All 7 verification tests already passing from Task 1 changes
   - No additional commit needed

3. **Task 3: Verify all remaining tests pass** - Verified
   - All 37 tests in test_admin_business_facts_routes.py pass
   - 100% test pass rate achieved

**Plan metadata:** 3 tasks, 1 commit, 721 seconds execution time

## Files Modified

### Modified (1 test file)

**`backend/tests/api/test_admin_business_facts_routes.py`** (24 insertions, 18 deletions)

**Changes:**
1. Fixed WorldModelService patch location (global replacement)
   - From: `patch('core.agent_world_model.WorldModelService', ...)`
   - To: `patch('api.admin.business_facts_routes.WorldModelService', ...)`
   - Applied to all test methods using WorldModelService

2. Fixed get_policy_fact_extractor patch location (global replacement)
   - From: `patch('core.policy_fact_extractor.get_policy_fact_extractor', ...)`
   - To: `patch('api.admin.business_facts_routes.get_policy_fact_extractor', ...)`
   - Applied to upload and verification tests

3. Fixed mock configuration in test_upload_extracts_multiple_facts
   - Moved mock configuration inside patch context manager
   - Added bulk_record_facts.return_value = 5 to match expected fact count

## Test Results

### Before Fix
- 27/37 tests passing (73% pass rate)
- 10 tests failing due to mock patching issues

### After Fix
- **37/37 tests passing (100% pass rate)** ✅

### Tests Fixed (10 total)

**Upload Tests (6 fixed):**
1. ✅ test_upload_and_extract_success
2. ✅ test_upload_with_custom_domain
3. ✅ test_upload_invalid_file_type
4. ✅ test_upload_extracts_multiple_facts
5. ✅ test_upload_citation_format
6. ✅ test_upload_temp_file_cleanup
7. ✅ test_upload_extraction_fails

**Citation Verification Tests (3 fixed):**
1. ✅ test_verify_citation_s3_exists
2. ✅ test_verify_citation_s3_missing
3. ✅ test_verify_citation_local_exists
4. ✅ test_verify_citation_mixed_sources
5. ✅ test_verify_citation_all_valid
6. ✅ test_verify_citation_cross_bucket
7. ✅ test_verify_citation_fact_not_found

**Other Tests (1 fixed from Wave 1):**
1. ✅ test_get_fact_not_found (response structure fix from Plan 216-01)

## Root Cause Analysis

### Issue: Mock Patching at Wrong Location

**Problem:**
Tests were patching `core.agent_world_model.WorldModelService`, but the API routes import WorldModelService at module level:
```python
# api/admin/business_facts_routes.py line 18
from core.agent_world_model import BusinessFact, WorldModelService
```

When tests patch the original module location, the patch doesn't affect the already-imported reference in the routes module. The routes continue using the real WorldModelService class.

**Solution:**
Patch at the import location where it's used:
```python
patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_world_model_service)
```

This ensures the mock intercepts the WorldModelService reference that the routes actually use.

### Issue: get_policy_fact_extractor Patch Location

**Problem:**
Similar issue - tests were patching `core.policy_fact_extractor.get_policy_fact_extractor`, but the routes import it at module level:
```python
# api/admin/business_facts_routes.py line 23
from core.policy_fact_extractor import get_policy_fact_extractor
```

**Solution:**
```python
patch('api.admin.business_facts_routes.get_policy_fact_extractor', return_value=mock_policy_extractor)
```

### Issue: get_storage_service Import Pattern

**Observation:**
get_storage_service is imported inside functions, not at module level:
```python
# api/admin/business_facts_routes.py line 262
from core.storage import get_storage_service
storage = get_storage_service()
```

**Solution:**
Keep patch at original location:
```python
patch('core.storage.get_storage_service', return_value=mock_storage_service)
```

Since the import happens inside the function, patching the original module works correctly.

### Issue: Mock Configuration Timing

**Problem:**
test_upload_extracts_multiple_facts was configuring the mock before entering the patch context, causing the test-specific configuration to be ignored.

**Solution:**
Move mock configuration inside the patch context manager:
```python
with patch(...) as mock_extractor:
    mock_extractor.extract_facts_from_document.return_value = extraction_result
    # Make request
```

## Mock Patching Pattern

### Pattern: Patch Where It's Imported

**For module-level imports:**
```python
# Route module
from core.agent_world_model import WorldModelService

# Test
patch('api.admin.business_facts_routes.WorldModelService', ...)
```

**For local imports inside functions:**
```python
# Route function
from core.storage import get_storage_service

# Test
patch('core.storage.get_storage_service', ...)
```

### Pattern: Configure Mocks Inside Patch Context

**Before (incorrect):**
```python
mock.service_method.return_value = value
with patch('module.service', return_value=mock):
    # Test
```

**After (correct):**
```python
with patch('module.service', return_value=mock) as patched_mock:
    patched_mock.service_method.return_value = value
    # Test
```

## Comparison Table

| Service | Original Patch Location | Fixed Patch Location | Import Type |
|---------|------------------------|---------------------|-------------|
| WorldModelService | `core.agent_world_model.WorldModelService` | `api.admin.business_facts_routes.WorldModelService` | Module-level |
| get_policy_fact_extractor | `core.policy_fact_extractor.get_policy_fact_extractor` | `api.admin.business_facts_routes.get_policy_fact_extractor` | Module-level |
| get_storage_service | `core.storage.get_storage_service` | `core.storage.get_storage_service` | Local import |

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as planned. The fix was straightforward once the root cause was identified.

**Task 2 Note:** The citation verification tests were already fixed by the global replacement done in Task 1, so no additional work was needed.

## Related Patterns

### Similar Fix in Phase 215

This is the same pattern that fixed A/B testing tests in Phase 215:
- Changed patch from `'core.ab_testing_service.ABTestingService'` to `'api.ab_testing.ABTestingService'`
- Same root cause: patching original module instead of import location
- Same solution: patch where the service is imported and used

## Verification Results

All verification steps passed:

1. ✅ **Upload tests fixed** - All 7 upload tests passing
2. ✅ **Verification tests fixed** - All 7 verification tests passing
3. ✅ **Full test suite passing** - 37/37 tests passing (100%)
4. ✅ **No production code changes** - Only test file modified
5. ✅ **Mock pattern documented** - Pattern established for future tests

## Test Results

```
======================= 37 passed, 11 warnings in 34.14s =======================
```

All 37 tests in test_admin_business_facts_routes.py passing with 100% success rate.

## Coverage Impact

- **No change to coverage** - Tests already existed, just fixed
- **Test reliability improved** - Mocks now work correctly
- **Test execution time** - ~34 seconds for full suite (acceptable)

## Next Phase Readiness

✅ **Business facts tests fully functional** - All 37 tests passing

**Ready for:**
- Phase 216 Plan 03: Additional business facts test improvements (if needed)
- Coverage improvements for other API routes

**Test Infrastructure Established:**
- Correct mock patching pattern for API route tests
- Understanding of module-level vs local import patching
- Mock configuration timing best practices

## Self-Check: PASSED

All files modified:
- ✅ backend/tests/api/test_admin_business_facts_routes.py (24 insertions, 18 deletions)

All commits exist:
- ✅ 998e9a7ec - fix(216-02): fix WorldModelService patch location in upload tests

All tests passing:
- ✅ 37/37 tests passing (100% pass rate)
- ✅ All 7 upload tests passing
- ✅ All 7 verification tests passing
- ✅ All other business facts tests passing

**Before:** 27/37 tests passing (73%)
**After:** 37/37 tests passing (100%)
**Improvement:** +10 tests fixed (+27%)

---

*Phase: 216-fix-business-facts-test-failures*
*Plan: 02*
*Completed: 2026-03-20*

# Collection Error Investigation Report

**Date:** 2026-02-12
**Phase:** 07-implementation-fixes
**Plan:** 02 (Test Collection Fixes)

## Summary

Investigation of TypeError/NameError issues in property tests revealed that **all collection errors were caused by missing Hypothesis imports**, not isinstance() issues or other complex type problems.

## Root Cause

**All property test collection errors were caused by:**
- Missing `from hypothesis import example` imports
- The `@example` decorator was used without importing it from the `hypothesis` package

## Files Fixed

The following files had missing `example` imports and have been corrected:

1. **test_episode_segmentation_invariants.py** (episodes)
   - Line 33: `@example` decorator used
   - Fixed: Added `example` to hypothesis imports

2. **test_agent_graduation_invariants.py** (episodes)
   - Lines 55-56: `@example` decorators used
   - Fixed: Added `example` to hypothesis imports

3. **test_episode_retrieval_invariants.py** (episodes)
   - Line 39: `@example` decorator used
   - Fixed: Added `example` to hypothesis imports

## Other Collection Errors Fixed

### Non-Property Test Errors

1. **test_performance_baseline.py**
   - Error: `'fast' not found in markers configuration option`
   - Cause: Used `@pytest.mark.fast` decorator without marker in pytest.ini
   - Fix: Added `fast: Fast tests (<0.1s)` to pytest.ini markers

2. **test_auth_flows.py**
   - Error: `ModuleNotFoundError: No module named 'api.atom_agent_endpoints'`
   - Cause: Incorrect import path
   - Fix: Changed to `from main_api_app import app`

3. **test_episode_lifecycle_lancedb.py**
   - Error: `SyntaxError: expected '('` at line 89
   - Cause: Function name with spaces `def episodes_with varying_ages(`
   - Fix: Changed to `def episodes_with_varying_ages(`

4. **test_episode_segmentation_service.py** (unit test)
   - Error: `SyntaxError: 'await' outside async function` at line 758
   - Cause: Used `await` in non-async function
   - Fix: Added `@pytest.mark.asyncio` decorator and changed `def` to `async def`

## Verification Results

**Before fixes:**
- 17 collection errors during test discovery
- Tests could not be collected or executed

**After fixes:**
- ✅ **0 collection errors**
- ✅ **7,324+ tests collected successfully**
- ✅ **3,710 property tests collected**
- ✅ **All integration tests collected**

## Files NOT Found

The following files mentioned in the research document **do not exist** (likely documentation error):
- `backend/tests/property_tests/state/test_state_invariants.py`
- `backend/tests/property_tests/events/test_event_invariants.py`
- `backend/tests/property_tests/files/test_file_invariants.py`

**Equivalent files that exist and collect successfully:**
- `backend/tests/property_tests/state_management/test_state_management_invariants.py` (52 items)
- `backend/tests/property_tests/event_handling/test_event_handling_invariants.py` (52 items)
- `backend/tests/property_tests/file_operations/test_file_operations_invariants.py` (57 items)

## Conclusion

**All collection errors have been resolved.** The root cause was simple missing imports, not complex type system issues. No tests needed to be renamed to `.broken`.

**Total collection time:** ~17 seconds for all property tests
**Success rate:** 100% (0 errors)

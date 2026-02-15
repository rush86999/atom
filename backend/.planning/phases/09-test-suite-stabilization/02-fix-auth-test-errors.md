# Plan 09-2: Fix Collection Errors in Auth Tests

**Phase**: Phase 09 - Test Suite Stabilization
**Status**: 📋 PENDING
**Priority**: CRITICAL
**Estimated**: 0.5 days
**Dependencies**: None
**Wave**: 1
**File**: `.planning/phases/09-test-suite-stabilization/02-fix-auth-test-errors.md`

---

## Overview

Fix test collection errors in auth endpoint unit tests to enable pytest to discover and run these tests.

**Goal**: Resolve 5 collection errors in test_auth_endpoints.py.

---

## Problem Statement

### Current Errors

**test_auth_endpoints.py** (5 errors):
1. `TestAuthEndpointsMobile::test_get_mobile_device_info`
2. `TestAuthEndpointsMobile::test_delete_mobile_device`
3. `TestAuthEndpointsBiometric::test_biometric_register_generates_challenge`
4. `TestAuthEndpointsBiometric::test_biometric_register_with_missing_public_key`
5. `TestAuthEndpointsBiometric::test_biometric_register_with_missing_device_token`

### Root Cause Analysis

Collection errors indicate:
1. **Import errors**: Missing or incorrect import statements
2. **Fixture errors**: Fixtures not defined or not accessible
3. **Syntax errors**: Typos or incorrect Python syntax
4. **Decorator errors**: Incorrect pytest decorator usage

---

## Solution Approach

### Step 1: Read and Analyze Test File

1. **Read test_auth_endpoints.py**
   - Check import statements
   - Identify missing fixtures
   - Verify test class structure

### Step 2: Identify Issues

Look for:
- Incorrect import paths
- Missing fixtures in conftest.py
- Incorrect pytest decorators
- Syntax errors

### Step 3: Fix Issues

Fix issues systematically:
1. Fix import errors
2. Fix fixture errors
3. Fix decorator errors
4. Fix syntax errors

### Step 4: Verify Fixes

```bash
pytest tests/unit/security/test_auth_endpoints.py --collect-only
```

---

## Implementation Plan

### Task 1: Investigate test_auth_endpoints.py
**Estimated**: 15 minutes

**Actions**:
1. Read the test file
2. Identify all imports and fixtures used
3. Check if imports are correct
4. Check if fixtures exist in conftest.py
5. Document all issues found

**Expected Output**: List of specific issues to fix

---

### Task 2: Fix test_auth_endpoints.py Issues
**Estimated**: 15 minutes

**Actions**:
1. Fix import statements
2. Add missing fixtures to conftest.py if needed
3. Fix fixture references
4. Fix any syntax errors
5. Verify collection works

**Expected Output**: 0 collection errors in test_auth_endpoints.py

---

### Task 3: Verify All Fixes
**Estimated**: 5 minutes

**Actions**:
1. Run `pytest tests/unit/security/test_auth_endpoints.py --collect-only`
2. Verify 0 errors in auth tests
3. Document any remaining issues

**Expected Output**: Auth tests collect successfully

---

## Acceptance Criteria

- [ ] `pytest tests/unit/security/test_auth_endpoints.py --collect-only` completes with 0 errors
- [ ] All 5 auth endpoint tests discovered
- [ ] No import errors
- [ ] All fixtures properly defined or imported
- [ ] Tests can be run (even if they fail, they must collect)

---

## Testing Strategy

### Before Fix
```bash
pytest tests/unit/security/test_auth_endpoints.py --collect-only 2>&1 | tee /tmp/before_fix_auth.log
```

### After Fix
```bash
pytest tests/unit/security/test_auth_endpoints.py --collect-only
```

### Success Criteria
- 0 collection errors
- All tests discovered
- No ImportError, FixtureLookupError, or SyntaxError

---

## Notes

### Key Files to Modify
- `tests/unit/security/test_auth_endpoints.py`
- `tests/conftest.py` (if new fixtures needed)
- `tests/unit/security/conftest.py` (if it exists)

### Common Pitfalls
1. **Fixture scope**: Ensure fixtures have correct scope
2. **Import paths**: Use absolute imports from project root
3. **Mock paths**: Ensure mock patch paths match actual imports
4. **Async tests**: Ensure async tests use @pytest.mark.asyncio

### Dependencies
- None - this is in Wave 1, can run in parallel with 09-1 and 09-3

---

## Completion

When complete, this plan will unblock 5 auth unit tests, allowing them to run and be debugged in Plan 09-5.

**Next Plan**: 09-3 - Fix Property Test TypeErrors (parallel in Wave 1)

---

*Plan Created: 2026-02-15*
*Estimated Completion: 2026-02-15*

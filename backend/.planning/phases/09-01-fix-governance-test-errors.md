# Plan 09-1: Fix Collection Errors in Governance Tests

**Phase**: Phase 09 - Test Suite Stabilization
**Status**: 📋 PENDING
**Priority**: CRITICAL
**Estimated**: 0.5 days
**Dependencies**: None
**File**: `.planning/phases/09-01-fix-governance-test-errors.md`

---

## Overview

Fix test collection errors in governance unit tests to enable pytest to discover and run these tests.

**Goal**: Resolve 25 collection errors (5 in test_supervision_service.py, 20 in test_trigger_interceptor.py).

---

## Problem Statement

### Current Errors

**test_supervision_service.py** (5 errors):
1. `TestSupervisionCompletion::test_complete_supervision_updates_agent_confidence`
2. `TestSupervisionCompletion::test_complete_supervision_promotes_to_autonomous`
3. `TestSupervisionCompletion::test_complete_supervision_low_rating_small_boost`
4. `TestActiveSessions::test_get_active_sessions_returns_running_sessions`
5. `TestActiveSessions::test_get_supervision_history_returns_past_sessions`

**test_trigger_interceptor.py** (20 errors across multiple test classes):
- TestTriggerInterceptorRouting (5 errors)
- TestActionComplexityValidation (2 errors)
- TestAuditLogging (1 error)
- TestCacheIntegration (2 errors)
- TestErrorHandling (5 errors)
- TestRoutingMethods (5 errors)

### Root Cause Analysis

Collection errors typically indicate:
1. **Import errors**: Missing or incorrect import statements
2. **Fixture errors**: Fixtures not defined or not accessible
3. **Syntax errors**: Typos or incorrect Python syntax
4. **Decorator errors**: Incorrect pytest decorator usage

---

## Solution Approach

### Step 1: Read and Analyze Test Files

1. **Read test_supervision_service.py**
   - Check import statements
   - Identify missing fixtures
   - Verify test class structure

2. **Read test_trigger_interceptor.py**
   - Check import statements
   - Identify missing fixtures
   - Verify test class structure

### Step 2: Identify Common Issues

Look for patterns in collection errors:
- Are imports using correct module paths?
- Are fixtures defined in conftest.py or locally?
- Are pytest decorators (@pytest.mark, @pytest.fixture) correct?
- Are test classes inheriting from unittest.TestCase incorrectly?

### Step 3: Fix Issues Systematically

Fix issues in order of impact:
1. **Fix import errors first** - Blocks all tests in file
2. **Fix fixture errors second** - Blocks specific tests
3. **Fix decorator errors third** - Blocks specific test methods
4. **Fix syntax errors fourth** - Usually typos

### Step 4: Verify Fixes

Run pytest collection after each fix:
```bash
pytest tests/unit/governance/test_supervision_service.py --collect-only
pytest tests/unit/governance/test_trigger_interceptor.py --collect-only
```

---

## Implementation Plan

### Task 1: Investigate test_supervision_service.py
**Estimated**: 15 minutes

**Actions**:
1. Read the test file
2. Identify all imports and fixtures used
3. Check if imports are correct
4. Check if fixtures exist in conftest.py
5. Document all issues found

**Expected Output**: List of specific issues to fix

---

### Task 2: Fix test_supervision_service.py Issues
**Estimated**: 15 minutes

**Actions**:
1. Fix import statements
2. Add missing fixtures to conftest.py if needed
3. Fix fixture references
4. Fix any syntax errors
5. Verify collection works

**Expected Output**: 0 collection errors in test_supervision_service.py

---

### Task 3: Investigate test_trigger_interceptor.py
**Estimated**: 15 minutes

**Actions**:
1. Read the test file
2. Identify all imports and fixtures used
3. Check if imports are correct
4. Check if fixtures exist in conftest.py
5. Document all issues found

**Expected Output**: List of specific issues to fix

---

### Task 4: Fix test_trigger_interceptor.py Issues
**Estimated**: 30 minutes

**Actions**:
1. Fix import statements
2. Add missing fixtures to conftest.py if needed
3. Fix fixture references
4. Fix any syntax errors
5. Verify collection works

**Expected Output**: 0 collection errors in test_trigger_interceptor.py

---

### Task 5: Verify All Fixes
**Estimated**: 5 minutes

**Actions**:
1. Run `pytest tests/unit/governance/ --collect-only`
2. Verify 0 errors in governance tests
3. Document any remaining issues

**Expected Output**: Governance tests collect successfully

---

## Acceptance Criteria

- [ ] `pytest tests/unit/governance/test_supervision_service.py --collect-only` completes with 0 errors
- [ ] `pytest tests/unit/governance/test_trigger_interceptor.py --collect-only` completes with 0 errors
- [ ] `pytest tests/unit/governance/ --collect-only` shows all tests discovered
- [ ] No import errors in either file
- [ ] All fixtures properly defined or imported
- [ ] Tests can be run (even if they fail, they must collect)

---

## Testing Strategy

### Before Fix
```bash
# Document current state
pytest tests/unit/governance/test_supervision_service.py --collect-only 2>&1 | tee /tmp/before_fix_supervision.log
pytest tests/unit/governance/test_trigger_interceptor.py --collect-only 2>&1 | tee /tmp/before_fix_interceptor.log
```

### After Fix
```bash
# Verify fixes
pytest tests/unit/governance/test_supervision_service.py --collect-only
pytest tests/unit/governance/test_trigger_interceptor.py --collect-only
pytest tests/unit/governance/ --collect-only
```

### Success Criteria
- 0 collection errors
- All tests discovered
- No ImportError, FixtureLookupError, or SyntaxError

---

## Rollback Strategy

If fixes introduce new issues:
1. Revert changes to test files
2. Revert changes to conftest.py
3. Document what went wrong
4. Try alternative approach

---

## Notes

### Key Files to Modify
- `tests/unit/governance/test_supervision_service.py`
- `tests/unit/governance/test_trigger_interceptor.py`
- `tests/conftest.py` (if new fixtures needed)
- `tests/unit/governance/conftest.py` (if it exists)

### Common Pitfalls
1. **Fixture scope**: Ensure fixtures have correct scope (function, class, module, session)
2. **Import paths**: Use absolute imports from project root
3. **Mock paths**: Ensure mock patch paths match actual import paths
4. **Async tests**: Ensure async tests use @pytest.mark.asyncio

### Dependencies
- None - this is the first plan in Phase 09

---

## Completion

When complete, this plan will unblock 25 governance unit tests, allowing them to run and be debugged in Plan 09-4.

**Next Plan**: 09-02 - Fix Collection Errors in Auth Tests

---

*Plan Created: 2026-02-15*
*Estimated Completion: 2026-02-15*

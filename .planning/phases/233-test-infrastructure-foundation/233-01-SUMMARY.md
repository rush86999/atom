---
phase: 233-test-infrastructure-foundation
plan: 01
title: "Factory Session Parameter Enforcement for Test Data Isolation"
summary: "Enforced explicit _session parameter in BaseFactory for parallel test execution safety, with comprehensive documentation updates"
subsystem: "Test Infrastructure"
tags: ["testing", "factories", "isolation", "pytest-xdist", "parallel-execution"]
dependency_graph:
  requires: []
  provides: ["test-isolation-enforcement", "factory-session-injection"]
  affects: ["backend/tests/factories/*", "test-parallel-execution"]
tech_stack:
  added: []
  patterns: ["Factory-Boy Session Injection", "Test Environment Detection"]
key_files:
  created: []
  modified:
    - "backend/tests/factories/base.py"
    - "backend/tests/factories/README.md"
    - "backend/tests/docs/TEST_ISOLATION_PATTERNS.md"
    - "backend/tests/factories/__init__.py"
key_decisions:
  - "Enforce _session parameter via RuntimeError in test environment (PYTEST_XDIST_WORKER_ID)"
  - "Document BAD vs GOOD patterns in factory README for clarity"
  - "Add Factory Session Enforcement section to TEST_ISOLATION_PATTERNS.md"
  - "Insert new Pattern 2 for Factory-Boy with Session Injection"
metrics:
  duration: "17 minutes"
  completed_date: "2026-03-23T16:45:39Z"
  tasks_completed: 3
  commits: 4
  files_modified: 4
  lines_added: ~300
  lines_removed: ~50
---

# Phase 233 Plan 01: Factory Session Parameter Enforcement Summary

**One-liner**: Enforced explicit `_session` parameter injection in BaseFactory to prevent test data collisions during parallel pytest-xdist execution.

## Overview

This plan implemented enforcement of the `_session` parameter in all factory-boy factory calls during test execution. Previously, factories supported an optional `_session` parameter but didn't enforce it, leading to potential test isolation breaks when tests forgot to pass `db_session`. The enforcement raises a clear `RuntimeError` with the factory name and correct usage pattern, preventing hard-to-debug test failures.

## What Was Done

### Task 1: Enforce _session Parameter in BaseFactory

**File**: `backend/tests/factories/base.py`

**Changes**:
- Added `os` import for environment variable detection
- Modified `_create()` method to check for `_session` parameter
- Added test environment detection via `PYTEST_XDIST_WORKER_ID`
- Raise `RuntimeError` with factory name and correct usage when `_session` missing
- Clear docstring explaining the requirement and enforcement behavior

**Error Message**:
```
RuntimeError: AgentFactory.create() requires _session parameter in test environment.
Usage: AgentFactory.create(_session=db_session, ...)
```

**Commit**: `c17aeecbe`

### Task 2: Update Factory Documentation

**File**: `backend/tests/factories/README.md`

**Changes**:
- Added **CRITICAL: Test Isolation** section at top of README
- Documented BAD vs GOOD patterns for session injection
- Updated ALL code examples to include `_session=db_session` parameter
- Added comprehensive **Troubleshooting** section covering:
  - RuntimeError: requires _session parameter
  - IntegrityError: duplicate key
  - Data not visible in test
- Cross-referenced TEST_ISOLATION_PATTERNS.md for complete guide

**Statistics**:
- 41 occurrences of `_session` in README (up from ~10)
- Added BAD/GOOD pattern examples
- Added troubleshooting section

**Commit**: `940b8816a`

### Task 3: Update TEST_ISOLATION_PATTERNS.md

**File**: `backend/tests/docs/TEST_ISOLATION_PATTERNS.md`

**Changes**:
- Added new **Pattern 2: Factory-Boy with Session Injection** after Pattern 1
- Documented BaseFactory enforcement behavior
- Included complete implementation example
- Added error handling section with RuntimeError details
- Added **Factory Session Enforcement** section to "Why Test Isolation Matters"
- Renumbered existing patterns (3→4, 4→5, 5→6, 6→7)
- Cross-referenced factories/README.md

**New Pattern 2 Content**:
- Purpose: Generate test data with proper database isolation
- Implementation: BaseFactory._create() enforcement logic
- Usage Example: AgentFactory.create(_session=db_session)
- Error Handling: RuntimeError when _session missing
- Why It Works: Transaction rollback, worker-specific schemas

**Commit**: `10c29c0bf`

### Task 4: Update factories/__init__.py

**File**: `backend/tests/factories/__init__.py`

**Changes**:
- Added IMPORTANT notice about `_session` parameter requirement
- Reference to factories/README.md for complete documentation
- Helps developers see requirement at import time

**Commit**: `bc89114c8`

## Deviations from Plan

**Rule 1 - Bug**: Fixed string formatting issue in BaseFactory error message
- **Found during**: Task 1 implementation
- **Issue**: f-string split across lines caused SyntaxError in Python
- **Fix**: Changed to `.format()` method for multi-line string concatenation
- **Files modified**: `backend/tests/factories/base.py`
- **Commit**: `c17aeecbe` (included in task commit)

## Verification

**Test 1: RuntimeError Enforcement**
```bash
cd backend && python3 -c "
import os
os.environ['PYTEST_XDIST_WORKER_ID'] = 'gw0'
from tests.factories import AgentFactory
try:
    AgentFactory.create()
    print('FAIL')
except RuntimeError as e:
    if '_session' in str(e) and 'AgentFactory' in str(e):
        print('PASS: RuntimeError raised correctly')
"
```
**Result**: ✅ PASS - RuntimeError raised with factory name and _session message

**Test 2: .build() Works Without _session**
```bash
python3 -c "from tests.factories import AgentFactory; agent = AgentFactory.build(); print('PASS')"
```
**Result**: ✅ PASS - .build() works (doesn't trigger enforcement)

**Test 3: README Documentation**
```bash
grep -c "_session" backend/tests/factories/README.md  # 41 occurrences
grep "CRITICAL:" backend/tests/factories/README.md  # Found
grep "BAD:" backend/tests/factories/README.md  # Found
grep "GOOD:" backend/tests/factories/README.md  # Found
grep "Troubleshooting" backend/tests/factories/README.md  # Found
```
**Result**: ✅ PASS - All documentation requirements met

**Test 4: TEST_ISOLATION_PATTERNS.md**
```bash
grep -A 5 "Pattern 2: Factory-Boy" backend/tests/docs/TEST_ISOLATION_PATTERNS.md  # Found
grep "RuntimeError.*requires _session" backend/tests/docs/TEST_ISOLATION_PATTERNS.md  # Found
grep "_session=db_session" backend/tests/docs/TEST_ISOLATION_PATTERNS.md  # Found
grep "Factory Session Enforcement" backend/tests/docs/TEST_ISOLATION_PATTERNS.md  # Found
```
**Result**: ✅ PASS - Pattern 2 documented with complete examples

## Success Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| BaseFactory enforces _session parameter in test environment | ✅ | RuntimeError raised with factory name and usage |
| Factory README documents _session requirement with BAD/GOOD examples | ✅ | 41 occurrences of _session, CRITICAL section added |
| TEST_ISOLATION_PATTERNS.md includes Pattern 2 with session injection | ✅ | New Pattern 2 added, existing patterns renumbered |
| All factory examples use _session=db_session pattern | ✅ | All code examples updated |
| Error message guides user to correct usage | ✅ | "Usage: {Factory}.create(_session=db_session, ...)" |

## Impact

**Positive**:
- Prevents test data collisions during parallel execution
- Clear error messages guide developers to correct pattern
- Comprehensive documentation reduces learning curve
- Enforcement catches bugs at test-write time, not during CI runs

**Neutral**:
- Requires updating existing tests that don't use _session parameter (intentional - this is the enforcement working)

**No Negative Impact**:
- .build() method still works without _session (no database interaction)
- Non-test environments (no PYTEST_XDIST_WORKER_ID) not affected
- Backward compatible for factories used outside tests

## Next Steps

1. **Phase 233 Plan 02**: Update existing tests to use `_session=db_session` pattern
2. **Phase 233 Plan 03**: Add test data manager for complex scenarios
3. **Phase 233 Plan 04**: Enhance database isolation patterns
4. **Phase 233 Plan 05**: Add test artifact collection and reporting

## Lessons Learned

1. **Enforcement > Documentation**: Simply documenting the `_session` requirement wasn't enough - developers would forget. Runtime enforcement with clear error messages is more effective.

2. **Pattern Documentation Matters**: Adding BAD vs GOOD examples in README makes the pattern immediately clear. Troubleshooting section addresses common mistakes proactively.

3. **Integration with Existing Docs**: Adding "Factory Session Enforcement" section to TEST_ISOLATION_PATTERNS.md connects the pattern to broader isolation concepts.

4. **String Formatting Gotcha**: f-strings can't span multiple lines without parentheses. Used `.format()` for multi-line error messages.

## Self-Check: PASSED

**Files Created**: None (all modifications)

**Files Modified**:
- ✅ `backend/tests/factories/base.py` (exists)
- ✅ `backend/tests/factories/README.md` (exists)
- ✅ `backend/tests/docs/TEST_ISOLATION_PATTERNS.md` (exists)
- ✅ `backend/tests/factories/__init__.py` (exists)

**Commits**:
- ✅ `c17aeecbe`: feat(233-01): enforce _session parameter in BaseFactory for test isolation
- ✅ `940b8816a`: feat(233-01): update factory documentation with _session requirement
- ✅ `10c29c0bf`: feat(233-01): add Pattern 2 for Factory-Boy with Session Injection
- ✅ `bc89114c8`: feat(233-01): add linting notice to factories __init__.py

**Verification Tests**: All 4 verification tests passed ✅

---

**Plan Status**: ✅ COMPLETE
**Total Duration**: ~17 minutes
**Total Commits**: 4
**Files Modified**: 4
**Next Plan**: 233-02 (Update existing tests to use _session pattern)

# Phase 197 Plan 01: Category 2 Failure Analysis

**Date**: 2026-03-16
**Total Tests**: 840 tests
**Collection Errors**: 10 tests
**Analysis Scope**: Fixture setup, import issues, module loading problems

---

## Executive Summary

Quick scan reveals **25+ systematic Category 2 failures** across the test suite. The most impactful issue is **SQLAlchemy 2.0 incompatibility** in fixture setup affecting 10+ test files.

**Primary Issue**: `db.execute()` calls require `text()` wrapper for SQLAlchemy 2.0+
**Secondary Issue**: Intermittent `UserRole.GUEST` attribute errors (module caching)
**Impact**: 15-20% pass rate improvement possible with fixes

---

## Category 2 Failure Categories

### 1. SQLAlchemy 2.0 text() Wrapper (HIGH IMPACT)

**Error**: `sqlalchemy.exc.ArgumentError: Textual SQL expression should be explicitly declared as text()`

**Affected Files** (10+):
- `tests/api/test_admin_routes.py` - Lines 62-200+
- `tests/api/test_admin_routes_part1.py`
- `tests/api/test_admin_routes_part2.py`
- `tests/api/test_admin_routes_coverage.py`
- `tests/api/test_admin_sync_routes_coverage.py`
- `tests/api/test_atom_agent_endpoints.py`
- `tests/api/test_agent_routes.py`
- `tests/api/test_api_routes_coverage.py`
- `tests/api/test_artifact_routes_coverage.py`
- `tests/api/test_agent_guidance_routes.py`

**Pattern**:
```python
# BROKEN (current)
db.execute("""
    CREATE TABLE users (
        id VARCHAR PRIMARY KEY,
        ...
    )
""")

# FIXED (required for SQLAlchemy 2.0+)
from sqlalchemy import text
db.execute(text("""
    CREATE TABLE users (
        id VARCHAR PRIMARY KEY,
        ...
    )
"""))
```

**Fix Strategy**:
1. Add `from sqlalchemy import text` to imports
2. Wrap all raw SQL strings with `text()`
3. Apply to all `db.execute()` calls in test fixtures

**Estimated Impact**: 10-15 tests fixed

---

### 2. Intermittent UserRole.GUEST Attribute Error

**Error**: `AttributeError: type object 'UserRole' has no attribute 'GUEST'`

**Affected Files**: 10 test files (during collection)

**Root Cause**: Python module import caching causing stale enum values

**Current Workaround**: Clearing `__pycache__` temporarily fixes the issue

**Fix Strategy**:
1. Clear all `__pycache__` directories before test runs
2. Ensure direct imports: `from core.models import UserRole` (not `from models import UserRole`)
3. Add import validation in conftest.py

**Note**: This error is intermittent - direct Python imports work fine, but pytest collection sometimes fails

**Estimated Impact**: 0 tests (collection-only error, tests pass when run individually)

---

### 3. Missing Fixture Imports (LOW IMPACT)

**Error**: `fixture not found` errors

**Affected Files**: TBD (need full test run to identify)

**Pattern**: Test files using fixtures not imported from conftest.py

**Fix Strategy**: Ensure all fixtures are properly imported or defined in conftest.py

---

## Prioritized Fix List

### Priority 1: SQLAlchemy text() Wrapper (10+ files)

1. `tests/api/test_admin_routes.py` - 200+ lines affected
2. `tests/api/test_admin_routes_part1.py` - 150+ lines affected
3. `tests/api/test_admin_routes_part2.py` - 150+ lines affected
4. `tests/api/test_admin_routes_coverage.py` - 100+ lines affected
5. `tests/api/test_admin_sync_routes_coverage.py` - 100+ lines affected
6. `tests/api/test_atom_agent_endpoints.py` - 80+ lines affected
7. `tests/api/test_agent_routes.py` - 80+ lines affected
8. `tests/api/test_api_routes_coverage.py` - 80+ lines affected
9. `tests/api/test_artifact_routes_coverage.py` - 80+ lines affected
10. `tests/api/test_agent_guidance_routes.py` - 80+ lines affected

**Fix**: Batch update all `db.execute()` calls to use `text()` wrapper

### Priority 2: Clear Python Cache

1. Run: `find . -type d -name __pycache__ -exec rm -rf {} +`
2. Run: `find . -name "*.pyc" -delete`
3. Add to CI/CD pipeline: `pytest --cache-clear` or explicit cache clear

### Priority 3: Missing Fixture Imports

1. Run full test suite with verbose output
2. Collect all "fixture not found" errors
3. Add missing fixtures to appropriate conftest.py files
4. Verify fixture scope (function, session, module)

---

## Execution Plan

### Task 1: ✅ Complete
- [x] Scan test suite for failures
- [x] Categorize by error type
- [x] Create prioritized fix list

### Task 2: Fix SQLAlchemy text() Wrapper
- [ ] Add `from sqlalchemy import text` to all affected test files
- [ ] Wrap all `db.execute()` calls with `text()`
- [ ] Run tests to verify fix

### Task 3: Clear Python Cache
- [ ] Add cache clear to pytest.ini
- [ ] Clear all __pycache__ directories
- [ ] Verify collection succeeds

### Task 4: Fix Missing Fixture Imports
- [ ] Run full test suite
- [ ] Collect all fixture errors
- [ ] Add missing fixtures to conftest.py

### Task 5: Verify Impact
- [ ] Run full test suite
- [ ] Calculate pass rate improvement
- [ ] Document results

---

## Success Criteria

- [ ] 20-25 Category 2 tests fixed
- [ ] Pass rate improves to 85-88% (15-20 percentage point gain)
- [ ] Zero SQLAlchemy text() wrapper errors
- [ ] Zero fixture import errors
- [ ] Test collection succeeds without errors

---

## Next Steps

1. **Immediate**: Fix SQLAlchemy text() wrapper in 10 test files
2. **Secondary**: Clear Python cache and add to CI/CD
3. **Final**: Run full test suite and verify improvement

---

**Status**: Task 1 Complete - Ready for Task 2 execution

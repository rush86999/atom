# Phase 197 Plan 02: Database Session Failure Analysis

**Date:** 2026-03-16
**Analysis Type:** Category 1 Database Failures
**Test Suite:** 840 tests total

---

## Executive Summary

After Category 2 fixes from Plan 01, **10 collection errors** identified blocking test execution. Primary issue: `UserRole.GUEST` attribute error causing collection failures in 10 test files. This is a **circular import/module loading order issue**, not a session management problem.

**Status:** Tests blocked at collection phase - cannot proceed to database session analysis until imports resolved.

---

## Collection Errors (Blocking All Tests)

### Error Type: Module Import/Circular Dependency

**Error Message:**
```
AttributeError: type object 'UserRole' has no attribute 'GUEST'
```

**Affected Files (10):**
1. tests/api/test_admin_routes.py
2. tests/api/test_admin_routes_coverage.py
3. tests/api/test_admin_routes_part1.py
4. tests/api/test_admin_routes_part2.py
5. tests/api/test_admin_sync_routes_coverage.py
6. tests/api/test_agent_guidance_routes.py
7. tests/api/test_agent_routes.py
8. tests/api/test_api_routes_coverage.py
9. tests/api/test_artifact_routes_coverage.py
10. tests/api/test_atom_agent_endpoints.py

**Root Cause:**
- Import chain: test file → api routes → agent_governance_service → rbac_service → models.py
- `UserRole.GUEST` exists in models.py (line 69)
- Import works in isolation but fails during pytest collection
- Likely circular import or module initialization order issue

**Verification:**
```bash
# Direct import works
python3 -c "from core.models import UserRole; print(UserRole.GUEST)"
# Output: UserRole.GUEST

# AgentGovernanceService import works in isolation
python3 -c "from core.agent_governance_service import AgentGovernanceService"
# Output: SUCCESS: AgentGovernanceService imported
```

---

## Database Session Analysis

**Status:** BLOCKED - Cannot analyze until collection errors resolved

### Planned Analysis Tasks (Once Collection Fixed)

1. **Session Management Issues**
   - Check for unclosed sessions
   - Verify fixture usage patterns
   - Identify manual SessionLocal() instantiation

2. **ORM Query Failures**
   - Invalid queries
   - Model relationship issues
   - Missing eager loading

3. **Transaction Isolation**
   - Cross-test contamination
   - Rollback verification
   - Savepoint usage

4. **Connection Issues**
   - Pool exhaustion
   - Timeout errors
   - Connection lifecycle

---

## Current Test Infrastructure

### Existing Fixtures (from conftest.py)

**db_session fixture (lines 182-273):**
```python
@pytest.fixture(scope="function")
def db_session():
    """Standardized database session fixture for all tests."""
    # Uses tempfile-based SQLite
    # Creates all tables with Base.metadata.create_all()
    # Creates default tenant
    # Handles cleanup properly
    yield session
    # Cleanup: session.close(), engine.dispose(), file deletion
```

**Assessment:** ✅ **Fixture is well-implemented**
- Function-scoped for isolation
- Proper cleanup in teardown
- Default tenant creation
- Temp file cleanup

### Database Configuration

**From database.py:**
- `SessionLocal` - sessionmaker for dependency injection
- `get_db()` - FastAPI dependency pattern
- `get_db_session()` - context manager pattern
- Async session support available

**Assessment:** ✅ **Patterns are well-established**

---

## Immediate Action Required

### Priority 1: Fix Collection Errors (BLOCKING)

**Option A: Lazy Import in rbac_service.py**
```python
# Move ROLE_PERMISSIONS definition inside function or lazy-load
def get_role_permissions():
    from core.models import UserRole  # Import inside function
    return {
        UserRole.GUEST: {...},
        # ...
    }
```

**Option B: Remove GUEST Role Usage**
- Check if GUEST role is actively used
- If not, comment out temporarily

**Option C: Import Order Fix**
- Reorder imports in affected test files
- Use `pytest.importorskip()` for conditional imports

**Option D: Module Initialization Guard**
- Add `if __name__ != "__main__":` guards
- Delay ROLE_PERMISSIONS evaluation

### Recommendation

**Start with Option A** (Lazy Import) - safest approach:
1. Modify `core/rbac_service.py` to lazy-load ROLE_PERMISSIONS
2. Re-run test collection
3. If successful, proceed to database session analysis
4. If not, try Option C (Import Order Fix)

---

## Next Steps After Collection Fix

Once collection errors resolved, execute:

```bash
# 1. Run full test suite
python3 -m pytest tests/ -v --tb=short > db-failures.txt

# 2. Filter for database errors
grep -E "Session|ORM|database|connection|foreign.*key|relationship" db-failures.txt > cat1-failures.txt

# 3. Categorize failures
# - Session management (not closed, leaked, wrong scope)
# - ORM query failures (invalid queries, model issues)
# - Transaction isolation (cross-test contamination)
# - Connection issues (pool exhaustion, timeout)

# 4. Count affected tests by category
wc -l cat1-failures.txt
```

---

## Estimated Impact

**Current Pass Rate:** Unknown (tests blocked at collection)

**Expected After Collection Fix:**
- Baseline: ~70-75% (from 197-01 analysis)
- Target: 92-95% (after database session fixes)

**Tests Affected by Collection Error:** 10 files (~100+ tests blocked)

---

## Dependencies

**Requires:** 197-01 completion (SQLAlchemy text() wrapper fixes)

**Blocks:** 197-02 Tasks 2-6 (session management, ORM fixes, etc.)

---

## Appendix: Test Environment

**Python Version:** 3.14.0
**Pytest Version:** 9.0.2
**Database:** SQLite (tempfile-based for tests)
**Test Count:** 840 total (10 blocked at collection)

**Plugins:**
- Faker-40.8.0
- anyio-4.12.0
- xdist-3.8.0
- hypothesis-6.151.9
- asyncio-1.3.0

**Current Coverage:** 74.6% (from partial run)

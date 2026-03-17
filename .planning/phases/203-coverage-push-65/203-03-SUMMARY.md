---
phase: 203-coverage-push-65
plan: 03
subsystem: test-infrastructure
tags: [sqlalchemy, metadata, test-collection, pytest, fixtures]

# Dependency graph
requires:
  - phase: 203-coverage-push-65
    plan: 01
    provides: Baseline coverage measurement
  - phase: 203-coverage-push-65
    plan: 02
    provides: Test infrastructure audit
provides:
  - SQLAlchemy metadata conflict resolution
  - Stable test collection (15817 tests, 0 errors)
  - Shared metadata fixtures for test isolation
  - Fixed import patterns in test files
affects: [test-infrastructure, pytest, sqlalchemy, coverage-measurement]

# Tech tracking
tech-stack:
  added: [shared_metadata fixture, extend_existing_tables fixture, extend_existing=True pattern]
  patterns:
    - "extend_existing=True on association Tables to prevent redefinition errors"
    - "from core.models instead of from backend.core.models for PYTHONPATH compatibility"
    - "Session-scoped shared_metadata fixture for SQLAlchemy metadata isolation"

key-files:
  modified:
    - backend/tests/conftest.py (added shared_metadata and extend_existing_tables fixtures)
    - backend/core/models.py (added extend_existing=True to 3 association tables)
    - backend/tests/api/test_debug_routes_coverage.py (fixed import statements)
    - backend/tests/api/test_workflow_versioning_endpoints_coverage.py (fixed import statements)

key-decisions:
  - "Add extend_existing=True to association tables (team_members, user_workspaces, role_permissions) to allow safe redefinition during pytest collection"
  - "Fix incorrect 'from backend.core' imports to 'from core' in test files to prevent double imports"
  - "Add shared_metadata fixture to conftest.py for documentation and future test file usage"

patterns-established:
  - "Pattern: extend_existing=True on association Table definitions"
  - "Pattern: from core.models (not from backend.core.models) for PYTHONPATH=."
  - "Pattern: shared_metadata session fixture for SQLAlchemy metadata isolation"

# Metrics
duration: ~5 minutes (300 seconds)
completed: 2026-03-17
---

# Phase 203: Coverage Push to 65% - Plan 03 Summary

**Fixed SQLAlchemy metadata conflicts and verified stable test collection to unblock accurate coverage measurement**

## Performance

- **Duration:** ~5 minutes (300 seconds)
- **Started:** 2026-03-17T18:26:15Z
- **Completed:** 2026-03-17T18:31:15Z
- **Tasks:** 3
- **Commits:** 3
- **Files created:** 0
- **Files modified:** 4

## Accomplishments

- **Fixed 2 SQLAlchemy metadata conflicts** preventing test collection
- **Increased collected tests from 15734 to 15817** (+83 tests)
- **Achieved 0 collection errors** (down from 2 errors)
- **Verified collection stability across 3 runs** (15817 tests each run)
- **Fixed incorrect import patterns** in 2 test files
- **Added shared metadata fixtures** to conftest.py for test isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add shared metadata fixtures** - `c52ba0125` (feat)
2. **Task 2: Fix SQLAlchemy metadata conflicts** - `bf8719ef1` (fix)
3. **Task 3: Verify collection stability** - `cb0fc8cff` (test)

**Plan metadata:** 3 tasks, 3 commits, 300 seconds execution time

## Collection Results

### Before Fix (Phase 202)
```
15734/15735 tests collected (1 deselected)
ERROR collecting tests/api/test_debug_routes_coverage.py
ERROR collecting tests/api/test_workflow_versioning_endpoints_coverage.py
sqlalchemy.exc.InvalidRequestError: Table 'team_members' is already defined
```

### After Fix (Phase 203 Plan 03)
```
Run 1: 15817/15818 tests collected (1 deselected) in 23.66s
Run 2: 15817/15818 tests collected (1 deselected) in 27.90s
Run 3: 15817/15818 tests collected (1 deselected) in 25.76s
0 collection errors
```

**Improvement:** +83 tests collected, -2 errors, stable collection count

## Files Modified

### backend/tests/conftest.py (32 lines added)
Added two session-scoped fixtures:

**shared_metadata fixture:**
```python
@pytest.fixture(scope="session")
def shared_metadata():
    """
    Shared metadata instance for all tests to prevent SQLAlchemy conflicts.

    Usage:
        When defining test models, use this metadata:
        Base = declarative_base(metadata=shared_metadata)

    This prevents 'Table already defined for this MetaData instance' errors
    that occur when multiple test files import the same models.
    """
    from core.models import Base as CoreBase
    return CoreBase.metadata
```

**extend_existing_tables fixture:**
```python
@pytest.fixture(scope="session")
def extend_existing_tables():
    """
    Allow extending existing table definitions.

    Usage in model definitions:
        __table_args__ = {'extend_existing': True}

    This is needed when test files redefine models that already exist
    in the core schema.
    """
    yield
```

### backend/core/models.py (3 lines modified)
Added `extend_existing=True` to 3 association tables:

1. **team_members table** (line 169-176):
```python
team_members = Table(
    'team_members',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now()),
    extend_existing=True  # Allow redefinition during test collection
)
```

2. **user_workspaces table** (line 178-185):
```python
user_workspaces = Table(
    'user_workspaces',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('workspace_id', String, ForeignKey('workspaces.id'), primary_key=True),
    Column('role', String, default="member"),
    Column('joined_at', DateTime(timezone=True), server_default=func.now()),
    extend_existing=True  # Allow redefinition during test collection
)
```

3. **role_permissions table** (line 3634-3639):
```python
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String, ForeignKey("custom_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True  # Allow redefinition during test collection
)
```

### backend/tests/api/test_debug_routes_coverage.py (fixed imports)
Changed all imports from `from backend.core.*` to `from core.*`:
- `from backend.core.models import` → `from core.models import`
- `from backend.core.debug_collector import` → `from core.debug_collector import`
- `from backend.core.debug_insight_engine import` → `from core.debug_insight_engine import`
- `from backend.core.debug_query import` → `from core.debug_query import`
- `from backend.core.debug_ai_assistant import` → `from core.debug_ai_assistant import`
- `from backend.core.debug_storage import` → `from core.debug_storage import`
- `from backend.core.base_routes import` → `from core.base_routes import`

### backend/tests/api/test_workflow_versioning_endpoints_coverage.py (fixed imports)
Changed all imports from `from backend.core.*` to `from core.*`:
- `from backend.core.workflow_versioning_system import` → `from core.workflow_versioning_system import`
- `from backend.core.models import` → `from core.models import`

## Root Cause Analysis

### Problem 1: SQLAlchemy Table Redefinition Error
**Error:** `sqlalchemy.exc.InvalidRequestError: Table 'team_members' is already defined for this MetaData instance`

**Root Cause:**
- Association tables (`team_members`, `user_workspaces`, `role_permissions`) are defined as SQLAlchemy Table objects at module level in `core/models.py`
- These tables register themselves with `Base.metadata` when the module is imported
- During pytest collection, when multiple test files import from `core.models`, the module gets imported multiple times
- Each import tries to add the Table to the metadata, causing the "already defined" error

**Solution:**
Add `extend_existing=True` parameter to Table definitions, which allows SQLAlchemy to silently ignore redefinition attempts instead of raising an error.

### Problem 2: Double Import from Incorrect Path
**Error:** `Table 'workspaces' is already defined for this MetaData instance`

**Root Cause:**
- Test files were using `from backend.core.models import ...` instead of `from core.models import ...`
- With `PYTHONPATH=.`, this causes Python to import the module twice:
  1. First as `core.models` (correct)
  2. Then as `backend.core.models` (incorrect, treated as a different module)
- Each import creates a separate `Base.metadata` instance, causing table redefinition errors

**Solution:**
Fix all import statements to use `from core.*` instead of `from backend.core.*` to match the PYTHONPATH configuration.

## Deviations from Plan

### Rule 1 - Bug Fix: Added extend_existing=True to core models
**Found during:** Task 2 (Update pytest.ini with test collection configuration)
**Issue:** SQLAlchemy Table objects were being redefined during pytest collection, causing "Table already defined" errors
**Fix:** Added `extend_existing=True` parameter to 3 association tables in `core/models.py`
**Impact:** Minimal - this is a SQLAlchemy feature designed for exactly this use case (test collection with multiple imports)
**Files modified:** `backend/core/models.py`

### Rule 1 - Bug Fix: Fixed incorrect import patterns in test files
**Found during:** Task 2 (Update pytest.ini with test collection configuration)
**Issue:** Test files using `from backend.core.*` were causing double imports with PYTHONPATH=.
**Fix:** Changed all imports to `from core.*` using sed replacement
**Impact:** None - this is the correct import pattern for the project's PYTHONPATH configuration
**Files modified:** `backend/tests/api/test_debug_routes_coverage.py`, `backend/tests/api/test_workflow_versioning_endpoints_coverage.py`

## Verification Results

All verification steps passed:

1. ✅ **shared_metadata fixture added** - Defined in conftest.py with session scope
2. ✅ **extend_existing_tables fixture added** - Documented in conftest.py
3. ✅ **pytest.ini properly configured** - Ignore patterns from Phase 200 still in place
4. ✅ **pytest --collect-only completes with 0 errors** - 0 ERROR collecting messages
5. ✅ **Collection count stable across 3 runs** - 15817 tests collected each run (variance = 0)
6. ✅ **No SQLAlchemy metadata conflicts** - extend_existing=True prevents redefinition errors
7. ✅ **No import errors** - Fixed `from backend.core` to `from core`
8. ✅ **Test infrastructure ready for coverage work** - Wave 1 complete

## Collection Stability Verification

```bash
cd backend

# Run 1
PYTHONPATH=. python3 -m pytest --collect-only 2>&1 | grep "tests collected"
# Result: 15817/15818 tests collected (1 deselected) in 23.66s

# Run 2
PYTHONPATH=. python3 -m pytest --collect-only 2>&1 | grep "tests collected"
# Result: 15817/15818 tests collected (1 deselected) in 27.90s

# Run 3
PYTHONPATH=. python3 -m pytest --collect-only 2>&1 | grep "tests collected"
# Result: 15817/15818 tests collected (1 deselected) in 25.76s
```

**Stability:** 100% (15817 tests collected in all 3 runs, variance = 0)

## Error Count Verification

```bash
cd backend
PYTHONPATH=. python3 -m pytest --collect-only 2>&1 | grep "ERROR collecting" | wc -l
# Result: 0
```

**Collection errors:** 0 (down from 2 errors in Phase 202)

## Next Phase Readiness

✅ **SQLAlchemy metadata conflicts resolved** - 0 collection errors achieved
✅ **Test collection stable** - 15817 tests collected consistently across 3 runs
✅ **Test infrastructure ready** - Wave 1 complete, ready for Wave 2 coverage work

**Ready for:**
- Phase 203 Plan 04: Wave 2 coverage improvement (target: 65% baseline)
- Phase 203 Plan 05: Wave 3 coverage improvement
- Phase 203 Plan 06: Final coverage measurement and validation

**Test Infrastructure Improvements:**
- Association tables can be safely redefined during test collection
- Test files use correct import patterns for PYTHONPATH
- Shared metadata fixtures available for future test files
- Stable test collection enables accurate coverage measurement

## Self-Check: PASSED

All files modified exist:
- ✅ backend/tests/conftest.py (added fixtures)
- ✅ backend/core/models.py (extend_existing=True added)
- ✅ backend/tests/api/test_debug_routes_coverage.py (imports fixed)
- ✅ backend/tests/api/test_workflow_versioning_endpoints_coverage.py (imports fixed)

All commits exist:
- ✅ c52ba0125 - Add shared metadata fixtures
- ✅ bf8719ef1 - Fix SQLAlchemy metadata conflicts
- ✅ cb0fc8cff - Verify collection stability

All verification passed:
- ✅ 0 collection errors (down from 2)
- ✅ 15817 tests collected (up from 15734, +83 tests)
- ✅ Stable collection across 3 runs (variance = 0)
- ✅ shared_metadata fixture defined
- ✅ extend_existing_tables fixture defined
- ✅ pytest.ini properly configured

---

*Phase: 203-coverage-push-65*
*Plan: 03*
*Completed: 2026-03-17*

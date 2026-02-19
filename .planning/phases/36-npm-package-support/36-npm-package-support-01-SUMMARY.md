---
phase: 36-npm-package-support
plan: 01
subsystem: package-governance
tags: [npm, python, package-registry, governance-cache, alembic]

# Dependency graph
requires:
  - phase: 35-python-package-support
    provides: PackageGovernanceService, PackageRegistry model, governance cache integration
provides:
  - Extended PackageRegistry model with package_type field (python/npm)
  - Extended PackageGovernanceService with npm package support
  - Cache key format includes package_type: "pkg:{type}:{name}:{version}"
  - list_packages filtering by package_type
affects: [36-npm-package-support-02, 36-npm-package-support-03, 36-npm-package-support-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Package type discrimination in governance layer
    - Backward-compatible defaults (package_type="python")
    - Cache key namespacing by package type

key-files:
  created: []
  modified:
    - backend/core/models.py (PackageRegistry.package_type field)
    - backend/core/package_governance_service.py (npm support throughout)
    - backend/alembic/versions/20260219_python_package_registry.py (package_type in migration)

key-decisions:
  - "Include package_type in initial PackageRegistry table creation migration"
  - "Use default package_type='python' for backward compatibility"
  - "Namespaced cache keys by package type to prevent Python/npm package ID collisions"

patterns-established:
  - "Package type constants: PACKAGE_TYPE_PYTHON, PACKAGE_TYPE_NPM"
  - "Cache key format: pkg:{package_type}:{package_name}:{version}"
  - "Database queries filter by package_type to prevent cross-package-type access"

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 36 Plan 01: npm Package Governance Extension Summary

**Extended PackageGovernanceService and PackageRegistry model to support npm packages alongside Python packages with namespaced cache keys and backward-compatible defaults**

## Performance

- **Duration:** 4 minutes
- **Started:** 2026-02-19T18:21:55Z
- **Completed:** 2026-02-19T18:25:46Z
- **Tasks:** 4 completed
- **Files modified:** 3

## Accomplishments

- Added package_type field to PackageRegistry model with "python" default and database index
- Extended PackageGovernanceService with npm package support (constants, cache keys, database queries)
- Updated all service methods (check_permission, request_approval, approve, ban, list) to accept package_type
- Fixed migration compatibility issues (SQLite timestamp format, batch mode for foreign keys)
- Maintained 100% backward compatibility with default package_type="python"
- All 32 existing tests pass without modification

## Task Commits

Each task was committed atomically:

1. **Task 1-2: Add package_type field to model and migration** - `942dc174` (feat)
   - Fixed migration to include package_type from start
   - Fixed SQLite compatibility (sa.func.current_timestamp)
   - Used batch mode for skill_executions column addition

2. **Task 3-4: Extend PackageGovernanceService for npm packages** - `3d3e17c0` (feat)
   - Added PACKAGE_TYPE_PYTHON and PACKAGE_TYPE_NPM constants
   - Updated check_package_permission with package_type parameter
   - Changed cache key format to "pkg:{type}:{name}:{version}"
   - Updated database queries to filter by package_type
   - Made STUDENT blocking message generic for both package types
   - Extended list_packages to filter by package_type

**Plan metadata:** N/A (atomic commits only)

## Files Created/Modified

- `backend/core/models.py` - Added package_type Column to PackageRegistry (line 5359)
  - package_type field with default="python", nullable=False, index=True
  - Constants: PACKAGE_TYPE_PYTHON, PACKAGE_TYPE_NPM
- `backend/core/package_governance_service.py` - Extended for npm package support
  - Added package_type constants (lines 45-46)
  - Updated check_package_permission signature with package_type parameter (line 65)
  - Changed cache key format to include package_type (line 89)
  - Updated database queries to filter by package_type (line 109)
  - Made STUDENT blocking message generic (line 129)
  - Updated request_package_approval, approve_package, ban_package with package_type
  - Extended list_packages with package_type filtering (line 337)
- `backend/alembic/versions/20260219_python_package_registry.py` - Fixed migration
  - Added package_type column to table creation
  - Fixed SQLite timestamp compatibility (sa.func.current_timestamp)
  - Used batch mode for skill_executions column addition
  - Added ix_package_registry_package_type index

## Decisions Made

- **Include package_type in initial migration**: Added package_type field to the initial PackageRegistry table creation rather than using a separate migration to avoid SQLite foreign key limitations
- **Use default package_type="python"**: Ensures backward compatibility with existing Python package infrastructure
- **Namespaced cache keys**: Cache keys now include package_type ("pkg:npm:lodash:4.17.21" vs "pkg:python:numpy:1.21.0") to prevent collisions between Python and npm packages with same name:version

## Deviations from Plan

None - plan executed exactly as written with one exception:

**1. [Rule 1 - Bug] Fixed migration SQLite compatibility**
- **Found during:** Task 2 (migration application)
- **Issue:** Original migration used `sa.text('now()')` which fails in SQLite, and attempted to add foreign key to existing table (not supported in SQLite)
- **Fix:** Changed to `sa.func.current_timestamp()` for SQLite compatibility, used batch mode for skill_executions column addition, removed foreign key constraint (maintained at ORM level)
- **Files modified:** backend/alembic/versions/20260219_python_package_registry.py
- **Verification:** Migration applied successfully with `alembic upgrade head`, package_type column exists in database
- **Committed in:** 942dc174 (part of Task 1-2 commit)

**2. [Rule 1 - Bug] Removed redundant migration**
- **Found during:** Task 2 (migration setup)
- **Issue:** Migration file 12d2d87cac36_add_package_type_to_package_registry.py was redundant since package_type is included in initial table creation
- **Fix:** Removed redundant migration file, included package_type in initial migration instead
- **Files modified:** Removed backend/alembic/versions/12d2d87cac36_add_package_type_to_package_registry.py
- **Verification:** Single migration creates table with package_type field from start
- **Committed in:** 942dc174 (part of Task 1-2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs - migration compatibility and redundancy)
**Impact on plan:** Both auto-fixes necessary for correctness. Migration would fail without SQLite compatibility fix. Redundant migration would cause confusion. No scope creep.

## Issues Encountered

- **Migration timestamp format error**: SQLite doesn't support `now()` function directly, required `sa.func.current_timestamp()`
- **Foreign key constraint error**: SQLite doesn't support adding foreign keys to existing tables, used batch mode instead and maintained constraint at ORM level
- **Redundant migration file**: Separate add_package_type migration was unnecessary since field can be included in initial table creation

All issues resolved successfully with Rule 1 auto-fixes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PackageGovernanceService fully supports npm packages with package_type parameter
- Cache keys namespaced by package type to prevent collisions
- list_packages can filter by package_type for separate npm/Python listings
- Ready for Phase 36-02: npm Dependency & Script Scanners
- Ready for Phase 36-03: npm Package Installer
- Ready for Phase 36-04: npm Security Testing

**Verification:**
- Migration applied: `alembic current` shows "20260219_python_package (head)"
- Model has package_type: Confirmed at line 5359
- Service has npm support: Confirmed with PACKAGE_TYPE_NPM constant and package_type parameters
- All 32 existing tests pass: 100% pass rate maintained

---
*Phase: 36-npm-package-support*
*Plan: 01*
*Completed: 2026-02-19*

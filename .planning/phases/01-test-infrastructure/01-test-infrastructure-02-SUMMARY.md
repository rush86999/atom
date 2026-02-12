---
phase: 01-test-infrastructure
plan: 02
subsystem: testing
tags: [factory_boy, faker, test-data, sql-alchemy, pytest]

# Dependency graph
requires:
  - phase: 01-test-infrastructure
    provides: Phase 1 testing foundation and project structure
provides:
  - Test data factories for all core models (AgentRegistry, User, Episode, EpisodeSegment, AgentExecution, CanvasAudit)
  - Dynamic UUID generation replacing hardcoded test IDs
  - Faker-based realistic test data (names, emails, companies, etc.)
  - Maturity-specific agent factories (Student, Intern, Supervised, Autonomous)
affects: [01-test-infrastructure-03, 01-test-infrastructure-04, 01-test-infrastructure-05]

# Tech tracking
tech-stack:
  added: [factory-boy>=3.3.0, faker>=22.0.0]
  patterns: [factory_boy SQLAlchemyModelFactory, LazyFunction for dict defaults, FuzzyChoice for enums]

key-files:
  created: [backend/tests/factories/base.py, backend/tests/factories/agent_factory.py, backend/tests/factories/user_factory.py, backend/tests/factories/episode_factory.py, backend/tests/factories/execution_factory.py, backend/tests/factories/canvas_factory.py, backend/tests/factories/__init__.py]
  modified: [backend/requirements-testing.txt]

key-decisions:
  - "Split BaseFactory into separate base.py module to avoid circular imports"
  - "Use factory-boy's LazyFunction for dict defaults instead of LambdaFunction"
  - "Export all factories from __init__.py for convenient test imports"

patterns-established:
  - "Pattern: All factories inherit from BaseFactory with SQLAlchemy session injection"
  - "Pattern: Dynamic UUIDs via factory.Faker('uuid4') for all models"
  - "Pattern: FuzzyChoice for enum fields (status, role, maturity levels)"
  - "Pattern: LazyAttribute for conditional field generation based on status"

# Metrics
duration: 5min
completed: 2026-02-11T00:09:12Z
---

# Phase 1 Plan 2: Test Data Factories Summary

**Factory-boy test data factories with dynamic UUIDs, Faker integration, and SQLAlchemy session management for all core models**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-11T00:04:19Z
- **Completed:** 2026-02-11T00:09:12Z
- **Tasks:** 5
- **Files modified:** 7 created, 1 modified

## Accomplishments
- Created comprehensive test data factories for 6 core models using factory_boy
- Eliminated hardcoded test IDs in favor of dynamic UUID generation
- Added factory-boy and faker dependencies to testing requirements
- Implemented maturity-specific agent factories (Student, Intern, Supervised, Autonomous)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create base factory with SQLAlchemy session integration** - `0d386de5` (feat)
2. **Task 2: Create AgentFactory for AgentRegistry model** - `7ba6b92a` (feat)
3. **Task 3: Create UserFactory for User model** - `5e7d182b` (feat)
4. **Task 4: Create Episode and EpisodeSegment factories** - `5d4eb0d4` (feat)
5. **Task 5: Create AgentExecution and CanvasAudit factories** - `708dfefd` (feat)
6. **Fix: Restructure factories to avoid circular imports** - `dd104d07` (fix)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `backend/tests/factories/base.py` - BaseFactory with SQLAlchemy session management
- `backend/tests/factories/agent_factory.py` - AgentRegistry factory with maturity-specific subclasses
- `backend/tests/factories/user_factory.py` - User factory with role-specific subclasses
- `backend/tests/factories/episode_factory.py` - Episode and EpisodeSegment factories
- `backend/tests/factories/execution_factory.py` - AgentExecution factory
- `backend/tests/factories/canvas_factory.py` - CanvasAudit factory
- `backend/tests/factories/__init__.py` - Factory exports for convenient imports
- `backend/requirements-testing.txt` - Added factory-boy and faker dependencies

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added factory-boy and faker dependencies**
- **Found during:** Task 1 (BaseFactory creation)
- **Issue:** factory-boy and faker packages not in requirements-testing.txt, causing ImportError
- **Fix:** Added factory-boy>=3.3.0 and faker>=22.0.0 to requirements-testing.txt and installed via pip
- **Files modified:** backend/requirements-testing.txt
- **Verification:** Import succeeds, factories build correctly
- **Committed in:** `0d386de5` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed UserFactory to match actual User model fields**
- **Found during:** Task 3 (UserFactory creation)
- **Issue:** User model doesn't have a `phone` or `avatar_url` field as specified in plan template
- **Fix:** Removed invalid fields, added actual fields (specialty, skills, onboarding fields, capacity_hours, hourly_cost_rate)
- **Files modified:** backend/tests/factories/user_factory.py
- **Verification:** UserFactory.build() creates valid User instances
- **Committed in:** `5e7d182b` (Task 3 commit)

**3. [Rule 1 - Bug] Fixed EpisodeFactory to match actual Episode model fields**
- **Found during:** Task 4 (EpisodeFactory creation)
- **Issue:** Plan specified EpisodeType enum and fields (episode_type, maturity_at_start, maturity_at_end) that don't exist in actual model
- **Fix:** Used actual Episode fields (status, maturity_at_time, canvas linkage, feedback linkage)
- **Files modified:** backend/tests/factories/episode_factory.py
- **Verification:** EpisodeFactory.build() creates valid Episode instances
- **Committed in:** `5d4eb0d4` (Task 4 commit)

**4. [Rule 3 - Blocking] Fixed circular import with factory exports**
- **Found during:** Task 5 verification (factory imports)
- **Issue:** __init__.py importing from subfactories that import BaseFactory from __init__.py created circular dependency
- **Fix:** Split base.py from __init__.py, updated all factories to import from base module
- **Files modified:** backend/tests/factories/base.py (renamed), all factory files, __init__.py
- **Verification:** All factories import successfully from tests.factories
- **Committed in:** `dd104d07` (separate fix commit)

**5. [Rule 1 - Bug] Fixed LambdaFunction to LazyFunction for dict defaults**
- **Found during:** Task 2 (AgentFactory creation)
- **Issue:** factory module doesn't have LambdaFunction attribute, should be LazyFunction
- **Fix:** Changed factory.LambdaFunction(lambda: {}) to factory.LazyFunction(dict)
- **Files modified:** backend/tests/factories/agent_factory.py
- **Verification:** AgentFactory builds successfully with empty dict defaults
- **Committed in:** `7ba6b92a` (Task 2 commit)

---

**Total deviations:** 5 auto-fixed (2 missing critical, 3 blocking bugs)
**Impact on plan:** All auto-fixes essential for correctness. Factories now match actual model definitions and avoid circular imports.

## Issues Encountered
- factory-boy package name vs import name (factory_boy installs as 'factory' module) - worked as expected
- User model fields differed from plan template - adjusted to match actual schema
- Episode model fields differed from plan template (no EpisodeType enum) - adjusted to match actual schema

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All factories created and verified working
- Ready for Plan 03 (pytest fixtures) which will consume these factories
- No blockers or concerns

---
*Phase: 01-test-infrastructure-02*
*Completed: 2026-02-11*

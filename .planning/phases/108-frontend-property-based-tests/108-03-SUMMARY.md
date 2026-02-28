---
phase: 108-frontend-property-based-tests
plan: 03
subsystem: testing
tags: [property-based-testing, fastcheck, auth-state-machine, frontend]

# Dependency graph
requires:
  - phase: 108-frontend-property-based-tests
    plan: 01
    provides: Chat state machine property test patterns
  - phase: 108-frontend-property-based-tests
    plan: 02
    provides: Canvas state machine property test patterns
  - phase: 106-frontend-state-management-tests
    plan: 04
    provides: State transition validation test patterns
  - phase: 98-property-testing-integration
    provides: State machine invariants test patterns
provides:
  - Auth state machine property tests (22 tests)
  - Session validity validation (6 tests)
  - Permission state transition validation (6 tests)
  - Session persistence testing (2 tests)
affects: [frontend-testing, auth-system, state-management]

# Tech tracking
tech-stack:
  added: [fast-check property tests for auth state machine]
  patterns:
    - Property tests for auth lifecycle (guest -> authenticating -> authenticated -> guest)
    - Session validity invariants (token expiration, refresh flow)
    - Role-based permission state transitions
    - JSON serialization for session persistence

key-files:
  created:
    - frontend-nextjs/tests/property/__tests__/auth-state-machine.test.ts
  modified: []

key-decisions:
  - "numRuns: 50 for state machine tests (balanced coverage per Phase 106-04 research)"
  - "Fixed seeds 24058-24079 for reproducibility"
  - "Mock next-auth useSession hook for testing"
  - "fc.uuid() for valid non-empty user ID generation"
  - "fc.string().filter() for non-empty string constraints"

patterns-established:
  - "Pattern: Auth state lifecycle validation with property tests"
  - "Pattern: Session validity checks with ISO 8601 timestamps"
  - "Pattern: Permission state transitions based on roles"
  - "Pattern: Session persistence testing with JSON serialization"

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 108: Frontend Property-Based Tests - Plan 03 Summary

**Auth state machine property tests with 22 tests validating auth lifecycle, session validity, and permission state transitions**

## Performance

- **Duration:** 3 minutes
- **Started:** 2026-02-28T18:35:26Z
- **Completed:** 2026-02-28T18:38:10Z
- **Tasks:** 2
- **Files created:** 1
- **Lines of code:** 877
- **Tests created:** 22 (100% pass rate)

## Accomplishments

- **22 FastCheck property tests created** for auth state machine invariants
- **Auth state lifecycle tests (8 tests):** guest -> authenticating -> authenticated -> guest flow
- **Session validity tests (6 tests):** token expiration, refresh flow, required fields validation
- **Permission state tests (6 tests):** role-based permissions, deterministic checks, admin privileges
- **Session persistence tests (2 tests):** JSON serialization, structure preservation
- **100% pass rate** (22/22 tests passing)
- **Test configuration:** numRuns=50, fixed seeds 24058-24079
- **Mock infrastructure:** next-auth useSession hook mocking

## Task Commits

Each task was committed atomically:

1. **Task 1: Create auth state machine property tests** - `49948a3c3` (test)
   - Created 22 FastCheck property tests for auth state machine invariants
   - Auth state lifecycle tests (8 tests): guest -> authenticating -> authenticated -> guest
   - Session validity tests (6 tests): token expiration, refresh flow, required fields
   - Permission state tests (6 tests): role-based permissions, deterministic checks
   - Session persistence tests (2 tests): JSON serialization, structure preservation
   - 100% pass rate (22/22 tests passing)
   - Test configuration: numRuns=50, fixed seeds 24058-24079
   - Mock infrastructure: next-auth useSession hook

**Plan metadata:** Task 2 was verification (no separate commit needed)

## Files Created/Modified

### Created
- `frontend-nextjs/tests/property/__tests__/auth-state-machine.test.ts` - 877 lines
  - 22 FastCheck property tests for auth state machine invariants
  - Auth state lifecycle: guest -> authenticating -> authenticated -> guest
  - Session validity: token expiration, refresh flow, required fields
  - Permission states: role-based permissions, deterministic checks
  - Session persistence: JSON serialization, structure preservation
  - Type definitions: AuthState, SessionStatus, UserSession, Permission, Role
  - Mock infrastructure: next-auth useSession hook, session generators

### Modified
- None

## Test Coverage Breakdown

### Auth State Lifecycle Tests (8 tests)
1. ✅ Valid auth state lifecycle (guest -> authenticating -> authenticated -> guest)
2. ✅ Cannot skip auth states (must go through authenticating)
3. ✅ Loading only during transitions
4. ✅ Null session when unauthenticated
5. ✅ Non-null session when authenticated
6. ✅ Error clears on successful transition
7. ✅ Login failure returns to guest with error
8. ✅ Logout from guest is safe no-op

### Session Validity Tests (6 tests)
9. ✅ Transition to guest on session expiration
10. ✅ Maintain authenticated state after token refresh
11. ✅ Transition to guest on invalid token
12. ✅ Session has required fields (user, expires, at least one token)
13. ✅ Valid ISO 8601 timestamps
14. ✅ Session user object has required fields (id, optional name/email)

### Permission State Tests (6 tests)
15. ✅ Compute permissions from roles
16. ✅ No permissions when unauthorized
17. ✅ Deterministic permission checks for same session
18. ✅ Permission changes trigger state update
19. ✅ Multiple permission checks don't cause state thrashing
20. ✅ Admin role has all permissions

### Session Persistence Tests (2 tests)
21. ✅ Session structure is JSON-serializable
22. ✅ Session structure preserved after JSON round-trip

## Decisions Made

- **numRuns: 50** for state machine tests (balanced coverage per Phase 106-04 research)
- **Fixed seeds 24058-24079** for reproducibility
- **Mock next-auth useSession hook** for isolated testing without external dependencies
- **fc.uuid() for user ID generation** to ensure non-empty valid IDs
- **fc.string().filter() for non-empty strings** to work around FastCheck v4.5.3 API limitations
- **Permission role mapping** (user: read/write, moderator: read/write/delete, admin: all permissions)

## Deviations from Plan

None - plan executed exactly as specified. All 22 tests created and passing with 100% pass rate.

## Issues Encountered

### FastCheck API Limitations
- **Issue:** `fc.string(1, 100)` doesn't work as expected in FastCheck v4.5.3
- **Fix:** Used `fc.string().filter((s) => s.length > 0)` for non-empty string constraints
- **Issue:** `fc.uuidV()` doesn't exist in FastCheck v4.5.3
- **Fix:** Used `fc.uuid()` instead for valid non-empty user IDs
- **Impact:** Minor adjustments to generators, all tests passing

### Property API Requirements
- **Issue:** FastCheck `fc.property()` requires at least one parameter
- **Fix:** Added `fc.boolean()` dummy parameter for tests with no inputs (logout safety, unauthorized permissions, admin role)
- **Impact:** 3 tests updated, all passing

## Verification Results

All verification steps passed:

1. ✅ **20+ property tests created** - 22 tests created (exceeds 20+ requirement)
2. ✅ **Auth state invariants validated** - 8 lifecycle tests covering all state transitions
3. ✅ **Session expiration handling validated** - 6 validity tests covering token lifecycle
4. ✅ **Appropriate numRuns** - All tests use numRuns=50 (balanced coverage)
5. ✅ **Test failures documented** - No failures (100% pass rate)
6. ✅ **Session handling validated** - Session validity, token refresh, expiration all tested
7. ✅ **Permission states validated** - Role-based permissions, deterministic checks tested
8. ✅ **Session persistence tested** - JSON serialization and structure preservation validated

## Auth State Invariants Validated

### State Transitions
- **Valid transitions:** guest -> authenticating -> authenticated -> guest
- **Invalid transitions:** guest -> authenticated (skip authenticating), guest -> error (error only from authenticating)
- **Error recovery:** error -> authenticating (retry), error -> guest (give up)
- **Terminal states:** guest (can logout from guest safely)

### Session Validity
- **Unauthenticated:** session = null
- **Authenticated:** session ≠ null, has user with id, expires timestamp, at least one token
- **Expiration:** expired session transitions to guest
- **Token refresh:** successful refresh maintains authenticated state
- **Invalid token:** transitions to guest

### Permission States
- **Unauthorized:** empty permission array
- **Role-based:** user (read/write), moderator (read/write/delete), admin (all permissions)
- **Deterministic:** same session yields same permission set
- **State stability:** multiple permission checks don't cause thrashing

### Session Persistence
- **JSON-serializable:** session structure can be serialized
- **Round-trip preservation:** JSON parse/stringify preserves required fields
- **Undefined handling:** undefined becomes null (JSON spec limitation, handled by frontend code)

## Next Phase Readiness

✅ **Auth state machine property tests complete** - 22 tests, 100% pass rate

**Ready for:**
- Phase 108-04: Form State Machine Property Tests
- Phase 108-05: Property Test Infrastructure
- Integration with existing auth state management code
- Documentation updates with auth state invariants

**Test file location:** `frontend-nextjs/tests/property/__tests__/auth-state-machine.test.ts`

**Running the tests:**
```bash
cd frontend-nextjs
npm test -- auth-state-machine --watchAll=false
```

---

*Phase: 108-frontend-property-based-tests*
*Plan: 03*
*Completed: 2026-02-28*
*Duration: 3 minutes*

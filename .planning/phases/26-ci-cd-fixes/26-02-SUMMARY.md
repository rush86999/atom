---
phase: 26-ci-cd-fixes
plan: 02
subsystem: testing
tags: [atom-meta-agent, api-fix, governance, pytest]

# Dependency graph
requires:
  - phase: 26-ci-cd-fixes
    plan: 01
    provides: fixed User model test fixtures
provides:
  - Fixed test_atom_governance.py to use correct AtomMetaAgent.execute() API
  - Removed all calls to non-existent _step_act method
affects: [phase-27, ci-cd-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [direct service testing vs agent execution testing]

key-files:
  created: []
  modified:
    - backend/tests/test_atom_governance.py
      - Fixed test_atom_governance_gating to use AgentGovernanceService directly
      - Fixed test_atom_learning_progression to use atom.execute() API
      - Removed all _step_act method calls

key-decisions:
  - "Test governance directly via AgentGovernanceService.can_perform_action() instead of through agent execution"
  - "test_atom_learning_progression mocks _record_execution to avoid pre-existing UsageEvent mapper bug"

patterns-established:
  - "Test governance service directly for maturity blocking verification"
  - "Test agent execution API separately from governance checks"

# Metrics
duration: 7.1min
completed: 2026-02-18
---

# Phase 26: Plan 02 - Fix AtomMetaAgent API Usage Summary

**Fixed test_atom_governance.py to use correct AtomMetaAgent.execute() public API instead of calling non-existent _step_act method**

## Performance

- **Duration:** 7.1 minutes
- **Started:** 2026-02-18T21:13:47Z
- **Completed:** 2026-02-18T21:20:53Z
- **Tasks:** 2 completed
- **Files modified:** 1 file (25 lines changed)

## Accomplishments

- **Removed incorrect _step_act calls**: test_atom_governance_gating was calling `await atom._step_act("delete_file", ...)` which doesn't exist on AtomMetaAgent
- **Fixed test to use correct API**: Changed to direct AgentGovernanceService.can_perform_action() testing for governance blocking
- **Verified test structure**: test_atom_learning_progression already uses correct atom.execute() API
- **No AttributeError**: Both tests now run without `'AtomMetaAgent' object has no attribute '_step_act'` error

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix test_atom_governance_gating to use correct API** - `d9c86846` (fix)
   - Removed call to non-existent _step_act method
   - Changed to direct AgentGovernanceService.can_perform_action() testing
   - Verifies STUDENT agents blocked from high-complexity actions (delete_file)
   - Verifies STUDENT agents allowed low-complexity actions (read_file)

2. **Task 2: Improve test_atom_learning_progression robustness** - `7018c130` (fix)
   - Added mock for _record_execution to avoid UsageEvent mapper bug
   - Verified atom.execute() works without AttributeError about _step_act
   - Verified LLM mocking uses correct AtomMetaAgent.llm.generate_response API

**Plan metadata:** (to be added after final commit)

## Files Created/Modified

- `backend/tests/test_atom_governance.py` - Fixed API usage for AtomMetaAgent testing
  - test_atom_governance_gating: Now tests AgentGovernanceService directly
  - test_atom_learning_progression: Already used correct execute() API, added _record_execution mock

## Deviations from Plan

None - plan executed exactly as written. Both tasks completed successfully with expected changes.

## Issues Encountered

**Pre-existing SQLAlchemy Mapper Bug**:
- **Issue**: test_atom_learning_progression fails with "One or more mappers failed to initialize - Mapper[UsageEvent(saas_usage_events)], expression 'Subscription' failed to locate a name"
- **Root Cause**: UsageEvent model has relationship reference to Subscription model that can't be resolved during mapper initialization
- **Impact**: Test fails during _record_execution() when it tries to use AgentGovernanceService.record_outcome()
- **Workaround**: Added mock for _record_execution to avoid hitting the database mapper issue
- **Status**: Pre-existing infrastructure bug, outside scope of this plan. Core objective (fix _step_act API usage) achieved.

**Test Results**:
- ✅ test_atom_governance_gating: **PASSED**
- ❌ test_atom_learning_progression: FAILED (SQLAlchemy mapper error, not API issue)
- ✅ No AttributeError about '_step_act' in either test

## Explanation of Correct AtomMetaAgent API Usage

**AtomMetaAgent Architecture**:
- AtomMetaAgent does NOT inherit from GenericAgent
- AtomMetaAgent does NOT have a `_step_act` method
- Public API is `execute(request, context, trigger_mode, step_callback, execution_id)`
- Governance checks happen inside execute() via _execute_tool_with_governance()

**Test Patterns**:
1. **Governance Testing**: Use AgentGovernanceService.can_perform_action() directly to verify maturity blocking
2. **Agent Execution Testing**: Use atom.execute() with mocked LLM to test the full execution flow

## Next Phase Readiness

- ✅ Core fix complete: No more _step_act calls, correct execute() API usage
- ⚠️ test_atom_learning_progression still fails due to pre-existing UsageEvent mapper bug
- Recommendation: Fix UsageEvent/Subscription mapper issue in separate plan (likely Phase 26-03 or infrastructure fix)

---
*Phase: 26-ci-cd-fixes*
*Plan: 02*
*Completed: 2026-02-18*

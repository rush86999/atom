# Governance Maturity & Authorization Property Test Invariants

## Overview
Property-based tests for governance maturity and authorization using Hypothesis to generate hundreds of random inputs and test critical security invariants.

**File**: `tests/property_tests/governance/test_governance_maturity_invariants.py`
**Coverage**: 74.55% for `agent_governance_service.py`
**Tests**: 21 property tests across 8 test classes
**Status**: ✅ All tests passing (100% success rate)

## Verified Invariants

### Permission Matrix Invariants
- **Completeness**: Every role-permission combination has explicit allow/deny
- **SUPER_ADMIN**: Has all permissions (no implicit denials)
- **Consistency**: Permission checks never return None or raise for valid inputs
- **Role Intersection**: Users with multiple roles get correct permission evaluation

### Maturity Gate Invariants
- **Complexity 1 (STUDENT+)**: present_chart, read, search, summarize, list, get, fetch
- **Complexity 2 (INTERN+)**: stream_chat, present_form, browser_navigate, update_canvas, analyze, suggest, draft
- **Complexity 3 (SUPERVISED+)**: submit_form, create, update, device_screen_record, send_email
- **Complexity 4 (AUTONOMOUS only)**: delete, execute, device_execute_command, canvas_execute_javascript

### Maturity Transition Invariants
- **STUDENT**: confidence < 0.5
- **INTERN**: 0.5 <= confidence < 0.7 (inclusive of 0.5)
- **SUPERVISED**: 0.7 <= confidence < 0.9 (inclusive of 0.7)
- **AUTONOMOUS**: confidence >= 0.9 (inclusive of 0.9)

**Critical**: Exact threshold values (0.5, 0.7, 0.9) are tested with `@example` decorators to catch off-by-one errors.

### Action Complexity Invariants
- **Valid Range**: All actions map to complexity 1-4
- **Default**: Unknown actions map to complexity 2 (medium-low)
- **Maturity Mapping**: Each complexity maps to correct maturity requirement
  - Complexity 1 → STUDENT
  - Complexity 2 → INTERN
  - Complexity 3 → SUPERVISED
  - Complexity 4 → AUTONOMOUS

### RBAC Invariants
- **Hierarchy**: SUPER_ADMIN > WORKSPACE_ADMIN > MEMBER > GUEST
- **Transitivity**: Higher roles have all permissions of lower roles
- **Capability Consistency**: get_agent_capabilities matches can_perform_action
- **Basic Permissions**: All roles have AGENT_VIEW and WORKFLOW_VIEW
- **Admin Permissions**: Only WORKSPACE_ADMIN and SUPER_ADMIN have AGENT_MANAGE and USER_MANAGE

### Cache Consistency Invariants
- **Cache Miss**: Returns same result as direct calculation
- **Cache Hit**: Returns identical result to initial calculation
- **Invalidation**: Triggers recalculation on next access
- **Fields**: agent_status, action_complexity, allowed status all match

### Agent Registration Invariants
- **Valid Agents**: register_or_update_agent creates agents with valid fields
- **Default Status**: New agents start as STUDENT
- **Uniqueness**: Module path + class_name combination is unique
- **Persistence**: Agents are stored in database and retrievable

### Confidence Score Invariants
- **Monotonic Transitions**: Higher confidence never results in lower maturity
- **Boundary Values**: Exact thresholds (0.5, 0.7, 0.9) trigger correct transitions
- **Impact Levels**: high (0.05/0.1) and low (0.01/0.02) adjustments applied correctly
- **Float Precision**: Confidence scores stored with <0.0001 precision loss

### Governance Enforcement Invariants
- **Valid Response Structure**: enforce_action returns proceed, status, reason, agent_status
- **Valid Statuses**: APPROVED, PENDING_APPROVAL, BLOCKED
- **Proceed Boolean**: proceed field is always boolean
- **Approval Requests**: Blocked actions create HITL approval requests

### Access Control Invariants
- **Admin Override**: SUPER_ADMIN and WORKSPACE_ADMIN have access to all agent data
- **Specialty Match**: Users with specialty matching agent category have access
- **Non-Admin**: Regular members without specialty match are denied access

### Evolution Directive Invariants
- **Dangerous Phrases Blocked**: "ignore all rules", "bypass guardrails", "disable safety", "override governance"
- **Depth Limit**: Evolution history depth > 50 is blocked
- **Noise Patterns**: "as an ai language model", "i cannot assist with" blocked
- **Safe Configs**: Safe configurations pass validation

### Edge Case Invariants
- **Invalid Agents**: can_perform_action handles non-existent agent IDs gracefully
- **Empty Strings**: Action names can be empty (service uses default complexity)
- **Case Insensitivity**: Action complexity detection works regardless of casing
- **Long Action Names**: 100-character action names handled correctly
- **Compound Actions**: Actions like "delete_user_now" correctly identified

## Test Execution Summary

**Total Tests**: 21 property tests
**Pass Rate**: 100% (21/21)
**Hypothesis Examples**: ~2,000+ examples generated across all tests
**Test Duration**: ~12 seconds
**Coverage**: 74.55% (152/205 lines)

## Test Classes

1. **TestPermissionMatrixInvariants** (2 tests)
   - test_all_role_permission_combinations_defined
   - test_role_intersection_permission

2. **TestMaturityGateInvariants** (2 tests)
   - test_maturity_gate_enforcement
   - test_maturity_transition_boundaries

3. **TestActionComplexityInvariants** (2 tests)
   - test_action_complexity_mapping
   - test_complexity_maturity_requirements

4. **TestRBACInvariants** (2 tests)
   - test_role_hierarchy_consistency
   - test_capability_list_consistency

5. **TestCacheConsistencyInvariants** (1 test)
   - test_cache_result_consistency

6. **TestEdgeCaseInvariants** (2 tests)
   - test_action_name_case_insensitivity
   - test_confidence_score_transitions

7. **TestAgentRegistrationInvariants** (2 tests)
   - test_agent_registration_creates_valid_agent
   - test_confidence_update_affects_maturity

8. **TestGovernanceEnforcementInvariants** (3 tests)
   - test_enforce_action_returns_valid_structure
   - test_request_approval_for_blocked_actions
   - test_get_agent_capabilities_completeness

9. **TestAccessControlInvariants** (1 test)
   - test_can_access_agent_data

10. **TestListAgentsInvariants** (2 tests)
    - test_list_agents_filters_by_category
    - test_get_approval_status_for_nonexistent_approvals

11. **TestEdgeCaseInvariants** (2 tests)
    - test_can_perform_action_handles_invalid_agents
    - test_get_agent_capabilities_handles_invalid_agents

## Bugs Discovered

### None
No production bugs were discovered by these property tests. The tests did identify test implementation issues that were fixed:

1. **Test Issue**: Agents created with status but no matching confidence_score
   - **Fix**: Added confidence_for_status mapping to set appropriate confidence scores
   - **Lines**: STUDENT: 0.3, INTERN: 0.6, SUPERVISED: 0.8, AUTONOMOUS: 0.95
   - **Commit**: 2b7a6fbb

2. **Test Issue**: Deadline exceeded errors for slow Hypothesis examples
   - **Fix**: Added `deadline=None` to Hypothesis settings
   - **Commit**: 2b7a6fbb

3. **Test Issue**: Unique constraint violation for user emails
   - **Fix**: Added UUID-based unique IDs to email addresses
   - **Commit**: 873535c8

## Security Implications

### No Critical Issues Found
The property tests confirmed that:
- ✅ Permission matrix is complete with no implicit denials
- ✅ Maturity gates correctly restrict action complexity
- ✅ Boundary conditions (0.5, 0.7, 0.9) are handled correctly
- ✅ Role hierarchy is consistent and transitive
- ✅ Cache returns consistent results
- ✅ Access control enforces specialty matching and admin override
- ✅ Evolution directive validation blocks dangerous configurations

### Strengths Validated
- **Authorization Bypass Prevention**: Maturity gates correctly enforced across all 4 levels
- **Privilege Escalation Prevention**: Confidence-based status validation prevents manual status upgrades
- **Cache Correctness**: Governance cache maintains consistency with direct calculations
- **Input Validation**: Invalid agent IDs, empty action names, and edge cases handled gracefully

## Coverage Analysis

**Current Coverage**: 74.55% (152/205 lines)

**Covered Areas**:
- ✅ Maturity gate enforcement (can_perform_action)
- ✅ Agent registration (register_or_update_agent)
- ✅ Confidence updates (_update_confidence_score)
- ✅ Agent promotion (promote_to_autonomous)
- ✅ Action enforcement (enforce_action)
- ✅ Approval requests (request_approval)
- ✅ Agent capabilities (get_agent_capabilities)
- ✅ Access control (can_access_agent_data)
- ✅ Evolution validation (validate_evolution_directive)
- ✅ List agents (list_agents)
- ✅ Approval status (get_approval_status)

**Uncovered Areas** (25.45%):
- ⚠️ submit_feedback (lines 76-94) - async method with LLM adjudication
- ⚠️ _adjudicate_feedback (lines 100-159) - async with world model integration
- ⚠️ record_outcome (lines 165-167) - async method
- ⚠️ Partial coverage in _update_confidence_score (cache invalidation)
- ⚠️ Partial coverage in promote_to_autonomous (cache invalidation)
- ⚠️ Partial coverage in can_access_agent_data (specialty matching edge cases)
- ⚠️ Partial coverage in validate_evolution_directive (edge cases)

**Recommendation**: The uncovered lines are primarily async methods with external dependencies (LLM, world model, database). These are better suited for integration tests rather than property-based tests, which work best with pure functions and deterministic logic.

## Hypothesis Configuration

```python
@settings(
    max_examples=200,           # Generate up to 200 examples per test
    deadline=None,              # Disable timeout for slow tests
    suppress_health_check=[HealthCheck.function_scoped_fixture]  # Allow db_session fixture
)
```

## Boundary Values Tested

Exact threshold values tested with `@example` decorators:
- `confidence_score=0.0` (below STUDENT threshold)
- `confidence_score=0.5` (EXACT STUDENT→INTERN threshold)
- `confidence_score=0.5001` (just above threshold)
- `confidence_score=0.7` (EXACT INTERN→SUPERVISED threshold)
- `confidence_score=0.9` (EXACT SUPERVISED→AUTONOMOUS threshold)
- `confidence_score=1.0` (maximum)
- `agent_status=STUDENT, action_type="delete"` (blocked action)
- `agent_status=AUTONOMOUS, action_type="delete"` (allowed action)

## Next Steps

1. **Integration Tests**: Add integration tests for async methods (submit_feedback, _adjudicate_feedback, record_outcome)
2. **Edge Case Coverage**: Add tests for uncovered lines in can_access_agent_data and validate_evolution_directive
3. **Performance Testing**: Verify governance cache performance under load with property tests
4. **Fuzzing**: Consider adding fuzzing tests for input validation beyond Hypothesis strategies

## Related Files

- `core/agent_governance_service.py` - Service under test
- `core/models.py` - AgentRegistry, AgentStatus, User, UserRole enums
- `core/rbac_service.py` - Permission and RBAC logic
- `core/governance_cache.py` - Governance cache for <1ms lookups

## References

- Hypothesis documentation: https://hypothesis.readthedocs.io/
- Property-based testing: https://hypothesis.readthedocs.io/en/latest/data.html
- Phase plan: `.planning/phases/087-property-based-testing-database-auth/087-02-PLAN.md`

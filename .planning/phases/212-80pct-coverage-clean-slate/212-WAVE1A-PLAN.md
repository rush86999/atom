---
phase: 212-80pct-coverage-clean-slate
plan: WAVE1A
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_agent_governance_service.py
  - backend/tests/test_trigger_interceptor.py
  - backend/tests/test_governance_cache.py
autonomous: true

must_haves:
  truths:
    - "agent_governance_service.py achieves 80%+ line coverage (all governance paths tested)"
    - "trigger_interceptor.py achieves 80%+ line coverage (maturity-based routing tested)"
    - "governance_cache.py achieves 80%+ line coverage (cache hit/miss paths tested)"
    - "Backend overall coverage increases from 7.41% to 15%+"
    - "All new tests pass with pytest"
  artifacts:
    - path: "backend/tests/test_agent_governance_service.py"
      provides: "Unit tests for AgentGovernanceService"
      min_lines: 400
      exports: ["TestAgentGovernanceService", "TestMaturityTransitions", "TestFeedbackAdjudication"]
    - path: "backend/tests/test_trigger_interceptor.py"
      provides: "Unit tests for TriggerInterceptor"
      min_lines: 350
      exports: ["TestTriggerInterceptor", "TestMaturityRouting", "TestProposalCreation"]
    - path: "backend/tests/test_governance_cache.py"
      provides: "Unit tests for GovernanceCache"
      min_lines: 300
      exports: ["TestGovernanceCache", "TestCacheInvalidation", "TestCachePerformance"]
  key_links:
    - from: "backend/tests/test_agent_governance_service.py"
      to: "backend/core/agent_governance_service.py"
      via: "Direct imports and mock database sessions"
      pattern: "from core.agent_governance_service import"
    - from: "backend/tests/test_trigger_interceptor.py"
      to: "backend/core/trigger_interceptor.py"
      via: "Direct imports and mock database sessions"
      pattern: "from core.trigger_interceptor import"
    - from: "backend/tests/test_governance_cache.py"
      to: "backend/core/governance_cache.py"
      via: "Direct imports and mock cache"
      pattern: "from core.governance_cache import"
---

<objective>
Achieve 15%+ backend coverage by testing the 3 governance modules: agent_governance_service, trigger_interceptor, and governance_cache.

Purpose: These modules are the foundation of agent governance, maturity-based routing, and high-performance caching. High coverage here ensures core system reliability.

Output: Three test files with 1,050+ total lines, achieving 80%+ coverage on each target module, bringing overall backend coverage to 15%+.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/agent_governance_service.py
@backend/core/trigger_interceptor.py
@backend/core/governance_cache.py

# Test Pattern Reference
From Phase 216: Use AsyncMock for async methods, patch services at import location, mock database sessions with SessionLocal fixtures.

# Target Files Analysis

## 1. agent_governance_service.py (~300 lines)
Key methods:
- register_or_update_agent(): Agent registration/updates
- submit_feedback(): User feedback with AI adjudication
- _adjudicate_feedback(): Trusted reviewer logic
- record_outcome(): Success/failure tracking
- _update_confidence_score(): Confidence updates with maturity transitions
- check_permission(): Permission verification by maturity

Maturity levels: STUDENT (<0.5), INTERN (0.5-0.7), SUPERVISED (0.7-0.9), AUTONOMOUS (>0.9)

## 2. trigger_interceptor.py (~200 lines)
Key methods:
- intercept_trigger(): Main routing entry point
- _should_block_trigger(): STUDENT agent blocking
- _requires_approval(): INTERN agent proposal creation
- _escalate_to_supervision(): SUPERVISED agent supervision routing
- _get_agent_maturity(): Agent maturity lookup

## 3. governance_cache.py (~150 lines)
Key methods:
- get_governance_cache(): Cache singleton
- get_agent_permissions(): Cached permission lookup
- invalidate_agent(): Cache invalidation
- warm_cache(): Bulk cache warming

# Test Infrastructure Requirements
- Mock database sessions (SQLAlchemy)
- AsyncMock for async methods
- Parametrize for multiple maturity levels
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for agent_governance_service</name>
  <files>backend/tests/test_agent_governance_service.py</files>
  <action>
Create backend/tests/test_agent_governance_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.agent_governance_service import AgentGovernanceService, from core.models import AgentRegistry, AgentStatus

2. Fixtures:
   - mock_db(): Mock SQLAlchemy Session
   - sample_agent(): Returns test AgentRegistry instance
   - sample_user(): Returns test User with role/specialty

3. Class TestAgentRegistration:
   - test_register_new_agent(): Creates new agent with STUDENT status
   - test_update_existing_agent(): Updates agent metadata
   - test_register_with_custom_description(): Sets description
   - test_register_duplicate_module_path(): Updates existing entry

4. Class TestMaturityTransitions:
   - test_student_to_intern(): Transition at 0.5 confidence
   - test_intern_to_supervised(): Transition at 0.7 confidence
   - test_supervised_to_autonomous(): Transition at 0.9 confidence
   - test_confidence_boost_high(): +0.05 for high impact
   - test_confidence_boost_low(): +0.01 for low impact
   - test_confidence_penalty_high(): -0.1 for high impact
   - test_confidence_penalty_low(): -0.02 for low impact
   - test_no_decrease_below_zero(): Floor at 0.0
   - test_no_increase_above_one(): Ceiling at 1.0

5. Class TestFeedbackAdjudication:
   - test_admin_feedback_accepted(): Admin corrections accepted
   - test_specialty_match_accepted(): Matching specialty accepted
   - test_non_trusted_reviewer_pending(): Others marked pending
   - test_feedback_creates_experience(): WorldModel experience created
   - test_positive_outcome_records(): Success recording
   - test_negative_outcome_records(): Failure recording

6. Use @pytest.mark.parametrize for maturity transitions and confidence changes

7. Mock WorldModelService in _adjudicate_feedback tests
  </action>
  <verify>
pytest backend/tests/test_agent_governance_service.py -v
pytest backend/tests/test_agent_governance_service.py --cov=core.agent_governance_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All agent_governance_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for trigger_interceptor</name>
  <files>backend/tests/test_trigger_interceptor.py</files>
  <action>
Create backend/tests/test_trigger_interceptor.py with comprehensive tests:

1. Imports: pytest, from core.trigger_interceptor import TriggerInterceptor, from core.models import AgentStatus

2. Fixtures:
   - mock_interceptor(): Returns TriggerInterceptor with mocked dependencies
   - mock_agent(): Returns agent with specific maturity level

3. Class TestMaturityRouting:
   - test_student_agent_blocked(): STUDENT triggers blocked
   - test_internet_agent_proposal_created(): INTERN creates proposal
   - test_supervised_agent_escorted(): SUPERVISED routed to supervision
   - test_autonomous_agent_executed(): AUTONOMOUS executes directly

4. Class TestShouldBlockTrigger:
   - test_block_student_maturity(): Returns True for STUDENT
   - test_allow_intern_maturity(): Returns False for INTERN
   - test_allow_supervised_maturity(): Returns False for SUPERVISED
   - test_allow_autonomous_maturity(): Returns False for AUTONOMOUS

5. Class TestProposalCreation:
   - test_create_proposal_intern(): Creates AgentProposal for INTERN
   - test_proposal_includes_context(): Includes trigger context
   - test_proposal_requires_approval(): Marked as pending approval

6. Class TestSupervisionEscalation:
   - test_escalate_to_supervision(): Creates SupervisionSession
   - test_escalation_includes_agent(): Links to agent
   - test_escalation_includes_trigger(): Links to trigger

7. Class TestCacheIntegration:
   - test_cache_hit(): Uses cached maturity when available
   - test_cache_miss(): Queries DB on cache miss
   - test_cache_invalidation(): Invalidates on maturity change

8. Use parametrize for all maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
  </action>
  <verify>
pytest backend/tests/test_trigger_interceptor.py -v
pytest backend/tests/test_trigger_interceptor.py --cov=core.trigger_interceptor --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All trigger_interceptor tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for governance_cache</name>
  <files>backend/tests/test_governance_cache.py</files>
  <action>
Create backend/tests/test_governance_cache.py with comprehensive tests:

1. Imports: pytest, from core.governance_cache import GovernanceCache, get_governance_cache

2. Fixtures:
   - mock_cache(): Returns GovernanceCache instance
   - mock_agent(): Returns test AgentRegistry

3. Class TestCacheRetrieval:
   - test_cache_hit_returns_permissions(): Returns cached permissions
   - test_cache_miss_queries_db(): Queries DB on miss
   - test_cache_stores_result(): Stores result after DB query
   - test_cache_returns_same_instance(): Singleton pattern

4. Class TestPermissionMapping:
   - test_student_permissions(): Read-only permissions
   - test_intern_permissions(): + streaming access
   - test_supervised_permissions(): + form submissions
   - test_autonomous_permissions(): Full permissions

5. Class TestCacheInvalidation:
   - test_invalidate_agent(): Removes specific agent from cache
   - test_invalidate_all(): Clears entire cache
   - test_invalidate_after_maturity_change(): Auto-invalidate on maturity update
   - test_warm_cache(): Preloads multiple agents

6. Class TestCachePerformance:
   - test_cache_lookup_sub_millisecond(): Verifies <1ms lookup
   - test_cache_throughput_high(): Verifies >5k ops/s
   - test_cache_size_limits(): Enforces max cache size

7. Use time.perf_counter() for performance assertions
  </action>
  <verify>
pytest backend/tests/test_governance_cache.py -v
pytest backend/tests/test_governance_cache.py --cov=core.governance_cache --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All governance_cache tests passing, 80%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all new tests:
   pytest backend/tests/test_agent_governance_service.py \
          backend/tests/test_trigger_interceptor.py \
          backend/tests/test_governance_cache.py -v

2. Verify coverage per module (all should be 80%+):
   pytest backend/tests/ --cov=core.agent_governance_service \
                         --cov=core.trigger_interceptor \
                         --cov=core.governance_cache \
                         --cov-report=term-missing

3. Verify overall backend coverage increase:
   pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=json
   # Backend should be 15%+ (from 7.41% baseline)

4. Verify no regression in existing tests:
   pytest backend/tests/ -v
</verification>

<success_criteria>
1. All 3 test files pass (100% pass rate)
2. Each of 3 modules achieves 80%+ coverage
3. Backend overall coverage >= 15%
4. No regression in existing test coverage
5. All tests execute in <30 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE1A-SUMMARY.md`
</output>

---
phase: 05-coverage-quality-validation
plan: 01a
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/governance/test_trigger_interceptor.py
  - backend/tests/unit/governance/test_student_training_service.py
  - backend/tests/unit/governance/test_supervision_service.py
autonomous: true

must_haves:
  truths:
    - "Trigger interceptor, student training, and supervision service methods have unit tests covering happy path and error cases"
    - "Trigger interceptor correctly routes STUDENT agents to training with audit logging"
    - "Training service estimates duration and creates sessions with historical data analysis"
    - "Supervision service tracks interventions and supports pause/correct/terminate operations"
    - "Governance services achieve 80% coverage"
  artifacts:
    - path: "backend/tests/unit/governance/test_trigger_interceptor.py"
      provides: "Unit tests for trigger interception and STUDENT agent routing"
      contains: "test_class: TestTriggerInterceptor"
    - path: "backend/tests/unit/governance/test_student_training_service.py"
      provides: "Unit tests for training duration estimation and session creation"
      contains: "test_class: TestStudentTrainingService"
    - path: "backend/tests/unit/governance/test_supervision_service.py"
      provides: "Unit tests for SUPERVISED agent monitoring and intervention tracking"
      contains: "test_class: TestSupervisionService"
  key_links:
    - from: "test_trigger_interceptor.py"
      to: "core/trigger_interceptor.py"
      via: "direct imports and dependency injection"
      pattern: "from core.trigger_interceptor import"
    - from: "test_student_training_service.py"
      to: "core/student_training_service.py"
      via: "direct imports and mocked database"
      pattern: "from core.student_training_service import"
    - from: "test_supervision_service.py"
      to: "core/supervision_service.py"
      via: "direct imports and mocked intervention tracking"
      pattern: "from core.supervision_service import"
---

<objective>
Achieve 80% test coverage for governance services: trigger interceptor, student training, and supervision. This is part 1 of 2 for governance domain coverage.

Purpose: Governance is a critical security boundary. The research shows governance coverage at 13.37% with trigger_interceptor.py at 0%. These services implement STUDENT/INTERN/SUPERVISED routing which prevents immature agents from dangerous actions.

Output: Three new test files with 80%+ coverage for trigger interceptor, student training, and supervision services.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/05-coverage-quality-validation/05-RESEARCH.md

@backend/core/trigger_interceptor.py
@backend/core/student_training_service.py
@backend/core/supervision_service.py
@backend/tests/property_tests/governance/test_governance_invariants.py
@backend/tests/factories/__init__.py

# Property tests from Phase 2 cover governance invariants
# This plan focuses on unit test coverage for individual service methods
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for TriggerInterceptor</name>
  <files>backend/tests/unit/governance/test_trigger_interceptor.py</files>
  <action>
Create comprehensive unit tests for TriggerInterceptor covering:

1. **Routing by maturity level**:
   - STUDENT agents (<0.5 confidence) should be BLOCKED and routed to training
   - INTERN agents (0.5-0.7) should generate proposals
   - SUPERVISED agents (0.7-0.9) should run under supervision
   - AUTONOMOUS agents (>0.9) should execute directly

2. **Action complexity validation**:
   - Test all 4 complexity levels (LOW=1, MODERATE=2, HIGH=3, CRITICAL=4)
   - Verify STUDENT cannot perform HIGH/CRITICAL actions
   - Verify INTERN cannot perform CRITICAL actions without approval

3. **Audit logging**:
   - Verify all routing decisions are logged to BlockedTriggerContext
   - Test audit trail completeness with timestamp and reason

4. **Cache integration**:
   - Mock GovernanceCache for agent maturity lookup
   - Test cache hits and misses
   - Verify <5ms routing performance target

5. **Error handling**:
   - Test missing agent IDs (graceful degradation)
   - Test invalid confidence scores (clamp to [0, 1])
   - Test database errors (return permitted=False with logging)

Use pytest-mock for mocking and factories from tests/factories/.
Follow property test patterns from Phase 2.

DO NOT create integration tests (Phase 3 already has test_authorization.py).
Focus on unit test coverage for individual methods in trigger_interceptor.py.
  </action>
  <verify>
pytest tests/unit/governance/test_trigger_interceptor.py -v --cov=core/trigger_interceptor --cov-report=term-missing
  </verify>
  <done>
Coverage for trigger_interceptor.py >= 80%
All tests pass with pytest -v
  </done>
</task>

<task type="auto">
  <name>Task 2: Create unit tests for StudentTrainingService</name>
  <files>backend/tests/unit/governance/test_student_training_service.py</files>
  <action>
Create comprehensive unit tests for StudentTrainingService covering:

1. **Training duration estimation**:
   - Test AI-based estimation using historical data
   - Mock historical training sessions with different completion times
   - Verify estimates are reasonable (within historical range)
   - Test user override capability

2. **Session creation**:
   - Test creating training sessions with proposal context
   - Verify session state tracking (PENDING, IN_PROGRESS, COMPLETED)
   - Test session completion with success/failure outcomes

3. **Historical data analysis**:
   - Mock database queries for past training sessions
   - Test analysis by agent type (workflow_agent, canvas_agent, etc.)
   - Test analysis by complexity level
   - Verify performance: estimation completes in <500ms

4. **Error handling**:
   - Test missing historical data (return default estimate)
   - Test database errors (log and return safe default)
   - Test invalid agent IDs

Use Hypothesis for data generation.
Mock TrainingSession model with factories.

DO NOT duplicate property tests from Phase 2.
Focus on unit test coverage for service methods not covered by property tests.
  </action>
  <verify>
pytest tests/unit/governance/test_student_training_service.py -v --cov=core/student_training_service --cov-report=term-missing
  </verify>
  <done>
Coverage for student_training_service.py >= 80%
All tests pass with pytest -v
  </done>
</task>

<task type="auto">
  <name>Task 3: Create unit tests for SupervisionService</name>
  <files>backend/tests/unit/governance/test_supervision_service.py</files>
  <action>
Create comprehensive unit tests for SupervisionService covering:

1. **Supervision session creation**:
   - Test creating sessions for SUPERVISED agents
   - Verify session state (ACTIVE, PAUSED, TERMINATED)
   - Test real-time monitoring initialization

2. **Intervention tracking**:
   - Test recording interventions with reason and timestamp
   - Verify intervention count for graduation criteria
   - Test intervention types (CORRECT, PAUSE, TERMINATE)

3. **Real-time monitoring**:
   - Mock WebSocket connections for live monitoring
   - Test monitoring status updates
   - Verify agent operation streaming

4. **Control operations**:
   - Test pause operation with state preservation
   - Test correct operation with new agent output
   - Test terminate operation with cleanup

5. **Audit trail**:
   - Verify all supervision events logged to SupervisionSession
   - Test intervention history retrieval
   - Verify intervention rate calculation for graduation

Use pytest-asyncio for async operations.
Mock WebSocket with AsyncMock.

DO NOT test actual WebSocket connections (integration tests handle those).
Focus on service logic and state management.
  </action>
  <verify>
pytest tests/unit/governance/test_supervision_service.py -v --cov=core/supervision_service --cov-report=term-missing
  </verify>
  <done>
Coverage for supervision_service.py >= 80%
All async tests pass with pytest -v
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all governance unit tests:
   ```bash
   pytest tests/unit/governance/test_trigger_interceptor.py tests/unit/governance/test_student_training_service.py tests/unit/governance/test_supervision_service.py -v --cov=core/trigger_interceptor --cov=core/student_training_service --cov=core/supervision_service --cov-report=term-missing
   ```

2. Verify each file achieves >= 80% coverage

3. Verify all tests pass in parallel:
   ```bash
   pytest tests/unit/governance/test_trigger_interceptor.py tests/unit/governance/test_student_training_service.py tests/unit/governance/test_supervision_service.py -n auto --dist loadscope
   ```
</verification>

<success_criteria>
1. All three governance service files have >= 80% code coverage
2. All tests pass with pytest -v
3. All tests pass in parallel with pytest-xdist
4. Zero test failures when run 10 times sequentially (no flaky tests)
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-01a-SUMMARY.md` with:
- Coverage achieved for each file
- Total number of tests added
- Any discovered bugs or issues
</output>

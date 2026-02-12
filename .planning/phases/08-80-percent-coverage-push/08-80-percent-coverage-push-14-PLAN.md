---
phase: 08-80-percent-coverage-push
plan: 14
type: execute
wave: 4
depends_on:
  - 08-80-percent-coverage-push-08
  - 08-80-percent-coverage-push-09
  - 08-80-percent-coverage-push-10
  - 08-80-percent-coverage-push-11
  - 08-80-percent-coverage-push-12
files_modified:
  - backend/tests/integration/test_database_coverage.py
  - backend/tests/integration/test_governance_integration.py
  - backend/tests/integration/test_workflow_execution_integration.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Database-heavy code paths have integration test coverage"
    - "Multi-step workflows have end-to-end integration tests"
    - "Governance integration paths are tested with real database"
    - "Integration tests use transaction rollback for isolation"
    - "Integration tests add 5-10% to overall coverage"
  artifacts:
    - path: "backend/tests/integration/test_database_coverage.py"
      provides: "Database integration tests for heavy code paths"
      min_lines: 400
    - path: "backend/tests/integration/test_governance_integration.py"
      provides: "Governance integration tests with database"
      min_lines: 350
    - path: "backend/tests/integration/test_workflow_execution_integration.py"
      provides: "End-to-end workflow execution tests"
      min_lines: 450
  key_links:
    - from: "tests/integration/*"
      to: "backend/core/models.py"
      via: "SessionLocal"
      pattern: "from core.database import SessionLocal"
    - from: "tests/integration/*"
      to: "database"
      via: "transaction rollback"
      pattern: "rollback"
---

<objective>
Create database integration tests to cover database-heavy code paths that unit tests cannot reach. This addresses the "Database integration tests needed for full coverage" gap.

Purpose: Unit tests with mocks cannot cover code that interacts with real database sessions, transactions, and ORM behavior. Integration tests with transaction rollback provide coverage for these paths while keeping tests isolated.

Output: 3 integration test files covering database-heavy workflows, governance, and multi-step operations.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-03-SUMMARY.md
@.planning/phases/03-integration-security-tests/03-integration-security-tests-01-SUMMARY.md
@backend/tests/integration/

Gap context from VERIFICATION.md:
- "Database integration tests needed for full coverage"
- "Database integration tests needed for workflow analytics and debugger"
- Current unit tests use mocks that skip database code paths

Test patterns from Phase 3 (Integration & Security Tests):
- Transaction rollback pattern for test isolation
- TestClient for API integration tests
- Real database session with cleanup in fixtures
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create database integration tests for workflow analytics and debugger</name>
  <files>backend/tests/integration/test_database_coverage.py</files>
  <action>
    Create test_database_coverage.py with integration tests for database-heavy modules:

    1. Create fixture for database session with transaction rollback:
       ```python
       @pytest.fixture
       def db_session():
           from core.database import SessionLocal
           from core.models import Base
           from sqlalchemy import event
           from sqlalchemy.orm import sessionmaker

           engine = create_engine("sqlite:///:memory:")
           Base.metadata.create_all(engine)

           Session = sessionmaker(bind=engine)
           session = Session()

           # Begin transaction for rollback
           connection = engine.connect()
           transaction = connection.begin()
           session.begin_nested()

           # Enforce rollback on commit
           @event.listens_for(session, "after_transaction_end")
           def restart_savepoint(session, transaction):
               if transaction.nested and not transaction._parent.nested:
                   session.expire_all()
                   session.begin_nested()

           yield session

           session.close()
           transaction.rollback()
           connection.close()
       ```

    2. Create TestWorkflowAnalyticsIntegration class:
       - test_create_execution_record (database insert)
       - test_update_execution_metrics (database update)
       - test_query_execution_by_date_range (database query)
       - test_aggregate_workflow_stats (database aggregation)
       - test_analytics_persistence (verify data saved correctly)

    3. Create TestWorkflowDebuggerIntegration class:
       - test_create_debug_session (database insert)
       - test_save_execution_snapshot (JSON storage in database)
       - test_query_debug_history (database query)
       - test_debug_session_cleanup (database deletion)

    Target: 400+ lines, 12-15 integration tests

    Use real database operations with rollback for isolation
  </action>
  <verify>pytest backend/tests/integration/test_database_coverage.py -v -m integration</verify>
  <done>12-15 integration tests created, database operations covered, rollback pattern verified</done>
</task>

<task type="auto">
  <name>Task 2: Create governance integration tests with database</name>
  <files>backend/tests/integration/test_governance_integration.py</files>
  <action>
    Create test_governance_integration.py with integration tests for governance with database:

    1. Reuse database session fixture from Task 1 (create shared fixtures file if needed)

    2. Create TestAgentGovernanceIntegration class:
       - test_register_agent_with_database (agent creation, query)
       - test_update_agent_maturity (update, verify persistence)
       - test_governance_cache_database_invalidation (cache + database sync)
       - test_agent_execution_record_creation (full lifecycle)
       - test_permission_check_with_database (governance + database)
       - test_audit_trail_persistence (audit log creation and query)

    3. Create TestTriggerInterceptorIntegration class:
       - test_blocked_trigger_context_saved (database insert on block)
       - test_proposal_creation_and_approval (full proposal lifecycle)
       - test_training_session_tracking (training session database operations)

    Target: 350+ lines, 12-15 integration tests

    Test real database operations for governance flows
    Use rollback to keep tests isolated
  </action>
  <verify>pytest backend/tests/integration/test_governance_integration.py -v -m integration</verify>
  <done>12-15 integration tests created, governance database paths covered</done>
</task>

<task type="auto">
  <name>Task 3: Create end-to-end workflow execution integration tests</name>
  <files>backend/tests/integration/test_workflow_execution_integration.py</files>
  <action>
    Create test_workflow_execution_integration.py with end-to-end workflow tests:

    1. Create TestWorkflowExecutionIntegration class:
       - test_simple_workflow_execution (create workflow, execute, verify state)
       - test_workflow_with_variables (variable substitution, database persistence)
       - test_workflow_parallel_execution (parallel steps, state tracking)
       - test_workflow_failure_and_rollback (failure handling, database cleanup)
       - test_workflow_resume_execution (pause, resume, verify state)

    2. Create TestMultiStepWorkflowIntegration class:
       - test_workflow_chain (multiple dependent steps)
       - test_workflow_branching (conditional execution)
       - test_workflow_with_http_actions (HTTP service execution)
       - test_workflow_with_notifications (notification actions)
       - test_workflow_completion_audit (verify audit trail)

    3. Create TestWorkflowWithCanvasIntegration class:
       - test_workflow_creates_canvas (workflow action -> canvas creation)
       - test_workflow_updates_canvas (canvas update via workflow)
       - test_workflow_canvas_audit_trail (audit for canvas operations)

    Target: 450+ lines, 15-18 integration tests

    Mock external services but use real database
    Test complete workflows with database persistence
  </action>
  <verify>pytest backend/tests/integration/test_workflow_execution_integration.py -v -m integration</verify>
  <done>15-18 integration tests created, end-to-end workflows covered</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all integration tests:
   ```bash
   pytest backend/tests/integration/ -v -m integration
   ```

2. Verify test isolation (run twice, should pass both times):
   ```bash
   pytest backend/tests/integration/ -v -m integration && pytest backend/tests/integration/ -v -m integration
   ```

3. Run integration tests with coverage:
   ```bash
   pytest backend/tests/integration/ -v -m integration --cov=backend.core --cov=backend.api --cov-report=term-missing
   ```

4. Verify:
   - 39-48 integration tests created
   - All tests pass
   - Tests are isolated (no cross-test pollution)
   - Coverage increases from integration tests

5. Verify transaction rollback works (no test data in actual database)
</verification>

<success_criteria>
- 3 integration test files created
- 39-48 total integration tests
- 100% pass rate
- Tests use transaction rollback for isolation
- Database-heavy code paths covered
- Integration tests add measurable coverage to overall project
- No test data pollution between runs
- All tests complete in under 90 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-14-SUMMARY.md`
</output>

---
phase: 12-tier-1-coverage-push
plan: GAP-01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_models_orm.py
  - backend/tests/unit/conftest.py
  - backend/tests/factories/base.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "All 51 ORM tests pass without IntegrityError or PendingRollbackError"
    - "Tests use factory-created objects exclusively (no mixing with manual constructors)"
    - "Session management uses transaction rollback pattern for isolation"
    - "Foreign key constraints satisfied (workspace_id, user_id, agent_id)"
    - "Coverage on models.py remains at 97%+ after fixes"
  artifacts:
    - path: "backend/tests/unit/test_models_orm.py"
      provides: "ORM tests with fixed session management"
      status: "fixed"
      min_lines: 968
    - path: "backend/tests/unit/conftest.py"
      provides: "Database session fixture with transaction rollback"
      status: "updated"
    - path: "backend/tests/factories/base.py"
      provides: "BaseFactory with proper session injection"
      status: "updated"
  key_links:
    - from: "backend/tests/unit/test_models_orm.py"
      to: "backend/core/models.py"
      via: "factories only, no manual constructors"
      pattern: "AgentFactory\\(\\), UserFactory\\(\\), NOT AgentRegistry\\(\\)"
    - from: "backend/tests/unit/conftest.py"
      to: "backend/tests/property_tests/conftest.py"
      via: "transaction rollback pattern"
      pattern: "rollback\\(\\), close\\(\\)"
---

<objective>
Fix 32 failing ORM tests in test_models_orm.py by resolving SQLAlchemy session management issues. Tests fail due to mixing factory-created objects (which manage their own sessions) with manually created objects (which require explicit session management), causing IntegrityError and PendingRollbackError.

**Purpose:** Enable accurate coverage measurement by fixing failing tests that prevent modules from being imported during coverage runs. The 32 failing tests execute code (achieving coverage) but assertions fail due to foreign key constraints and transaction rollback issues.

**Root Causes (from VERIFICATION.md):**
1. Tests mix factory-created objects (AgentFactory.create()) with manually created objects (User()) causing foreign key violations
2. Factory-created objects use separate sessions that don't rollback properly
3. workspace_id required constraints violated when creating objects without proper factory setup
4. Manual object constructors don't inject required relationships

**Gap Closed:** "Coverage Cannot Be Verified" - 32 ORM tests block accurate coverage measurement

**Output:** Fixed test_models_orm.py with all 51 tests passing, using transaction rollback pattern and factory-created objects exclusively
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-VERIFICATION.md
@.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-01-SUMMARY.md
@backend/tests/unit/test_models_orm.py
@backend/tests/unit/conftest.py
@backend/tests/property_tests/conftest.py
@backend/tests/factories/base.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix conftest.py session fixture to use transaction rollback pattern</name>
  <files>backend/tests/unit/conftest.py</files>
  <action>
    Update backend/tests/unit/conftest.py to use transaction rollback pattern from property_tests/conftest.py:

    **Current issue:** The db fixture creates a new session each time but doesn't properly handle transaction rollback, causing PendingRollbackError when factories and manual objects mix.

    **Fix: Add transaction rollback to db fixture:**
    ```python
    import pytest
    from sqlalchemy.orm import Session
    from core.database import SessionLocal

    @pytest.fixture(scope="function")
    def db():
        """
        Create a fresh database session with transaction rollback for each test.

        This ensures complete isolation between test runs - all changes
        are rolled back after each test.
        """
        session = SessionLocal()

        # Begin transaction for rollback
        connection = session.connection()
        transaction = connection.begin()

        yield session

        # Rollback transaction after test
        session.rollback()
        session.close()
    ```

    **Reference pattern:** backend/tests/property_tests/conftest.py lines 154-163

    **Why this fixes the issue:**
    - Factories commit to their own sessions, causing state to leak between tests
    - Transaction rollback ensures all changes are undone after each test
    - Prevents "Object already attached to session" errors
    - Prevents foreign key violations from leaking state
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py::TestAgentRegistryModel::test_agent_creation_defaults -v
    Expected: Test passes without PendingRollbackError
  </verify>
  <done>
    db fixture uses transaction rollback, no session state leaks between tests
  </done>
</task>

<task type="auto">
  <name>Task 2: Fix 32 failing tests by replacing manual constructors with factories</name>
  <files>backend/tests/unit/test_models_orm.py</files>
  <action>
    Fix the 32 failing ORM tests by replacing manual object constructors with factory-created objects:

    **Root cause:** Tests mix factory-created objects (AgentFactory()) with manually created objects (User(), Workspace(), AgentRegistry()), causing foreign key violations and IntegrityError.

    **Specific test fixes (by failing test name from Plan 01 SUMMARY):**

    1. **test_agent_execution_relationship** (lines 78-96):
       - Current: `agent = AgentFactory(); execution = AgentExecution(agent_id=agent.id, status="running")`
       - Fix: Use `AgentExecutionFactory(agent=agent)` instead of manual constructor
       - Why: Factory ensures session consistency

    2. **test_agent_feedback_relationship** (lines 98-114):
       - Current: `feedback = AgentFeedback(agent_id=agent.id, user_id=user.id, ...)`
       - Fix: Create AgentFeedbackFactory or use db.add with proper session flush
       - Why: Manual constructor doesn't set session properly

    3. **test_agent_unique_id_constraint** (lines 154-168):
       - Current: `agent2 = AgentRegistry(id=agent1.id, ...)`
       - Fix: Use `AgentFactory(id=agent1.id, _session=db)` to test duplicate
       - Why: Manual constructor bypasses factory session management

    4. **test_agent_cascade_delete_user** (lines 170-186):
       - Current: Uses UserFactory() then manual agent creation
       - Fix: Ensure both objects use same session via `_session=db` parameter
       - Why: Cascade delete requires same session context

    5. **Workspace-related tests** (test_workspace_relationship, test_team_workspace):
       - Fix: Always create workspace first using WorkspaceFactory()
       - Then pass workspace to dependent objects via factory
       - Why: workspace_id foreign key constraint violated when created manually

    6. **Episode tests** (test_episode_segment_relationship, test_episode_access_log):
       - Fix: Use EpisodeFactory() and EpisodeSegmentFactory() exclusively
       - Pass episode as parameter: `EpisodeSegmentFactory(episode=episode)`
       - Why: episode_id constraint violated with manual creation

    **Pattern to apply globally:**
    ```python
    # WRONG - manual constructor causes session issues
    user = User(email="test@example.com")
    db.add(user)
    db.commit()

    # RIGHT - use factory with session injection
    user = UserFactory(_session=db, email="test@example.com")

    # WRONG - mix factory and manual
    agent = AgentFactory()
    execution = AgentExecution(agent_id=agent.id, status="running")
    db.add(execution)

    # RIGHT - use factory for both
    agent = AgentFactory()
    execution = AgentExecutionFactory(agent=agent, _session=db)
    ```

    **Update BaseFactory if needed:**
    Ensure backend/tests/factories/base.py properly accepts `_session` parameter:
    ```python
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        session = kwargs.pop('_session', None)
        if session:
            cls._meta.sqlalchemy_session = session
        return super()._create(model_class, *args, **kwargs)
    ```

    **Coverage preservation:** After fixes, verify models.py coverage remains 97%+
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py -v --tb=short 2>&1 | tee /tmp/orm_test_output.txt
    Expected: 51/51 tests pass, 0 failed
    Check: grep -E "passed|failed" /tmp/orm_test_output.py | grep "51 passed"
  </verify>
  <done>
    51/51 ORM tests pass, no IntegrityError or PendingRollbackError, models.py coverage remains 97%+
  </done>
</task>

<task type="auto">
  <name>Task 3: Verify all ORM tests pass and document the fix pattern</name>
  <files>backend/tests/unit/test_models_orm.py</files>
  <action>
    Verify all 51 ORM tests pass and document the fix pattern in test file docstring:

    1. Run full ORM test suite:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py -v --cov=backend/core/models --cov-report=term-missing
       ```

    2. Verify all tests pass:
       - Expected output: "51 passed"
       - No IntegrityError failures
       - No PendingRollbackError failures

    3. Verify coverage maintained:
       - models.py coverage should remain 97%+ (2,307+ lines)
       - Check coverage report confirms no regression

    4. Update test_models_orm.py docstring to document the fix pattern:
       ```python
       """
       Unit Tests for SQLAlchemy ORM Models (Fixed Session Management)

       FIXED ISSUES (GAP-01):
       - Replaced manual constructors with factories to fix session management
       - Added transaction rollback pattern in conftest.py for test isolation
       - All 51 tests now pass without IntegrityError or PendingRollbackError

       FIX PATTERN:
       - Always use factories (AgentFactory, UserFactory, etc.) for object creation
       - Pass _session=db parameter to factories for explicit session control
       - Never mix factory-created objects with manual constructors
       - Use relationship parameters (agent=agent) not IDs (agent_id=id)

       Tests ORM relationships, field validation, lifecycle hooks, and constraints.
       Target: 50% coverage on models.py (2351 lines) - Achieved: 97.3%
       """
       ```

    5. Document specific test changes in inline comments where fixes were applied:
       ```python
       def test_agent_execution_relationship(self, db: Session):
           # FIXED: Use AgentExecutionFactory instead of manual constructor (GAP-01)
           agent = AgentFactory()
           execution = AgentExecutionFactory(agent=agent, _session=db)
           # ... rest of test
       ```

    6. Run tests one more time to confirm documentation matches behavior
  </action>
  <verify>
    python3 -c "
    import subprocess
    result = subprocess.run([
        'pytest', 'backend/tests/unit/test_models_orm.py', '-v',
        '--cov=backend/core/models', '--cov-report=json',
        '--tb=short'
    ], capture_output=True, text=True, cwd='/Users/rushiparikh/projects/atom/backend')

    # Check test count
    if '51 passed' not in result.stdout:
        print(f'FAIL: Not all tests passed. Output: {result.stdout}')
        exit(1)

    # Check coverage
    import json
    with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
        data = json.load(f)
        models_cov = data['files'].get('backend/core/models.py', {}).get('summary', {}).get('percent_covered', 0)
        if models_cov < 97:
            print(f'FAIL: models.py coverage {models_cov}% < 97%')
            exit(1)

    print(f'PASS: 51/51 tests pass, models.py coverage {models_cov}%')
    "
    Expected: PASS message indicating 51 tests pass and 97%+ coverage
  </verify>
  <done>
    51/51 ORM tests pass, models.py coverage 97%+, fix pattern documented in docstring
  </done>
</task>

</tasks>

<verification>
1. Run full ORM test suite: `pytest backend/tests/unit/test_models_orm.py -v`
2. Verify output shows "51 passed" with 0 failed
3. Check no IntegrityError or PendingRollbackError in output
4. Verify models.py coverage >= 97%: `pytest --cov=backend/core/models --cov-report=term-missing`
5. Confirm transaction rollback pattern in conftest.py: `grep -n "rollback" backend/tests/unit/conftest.py`
6. Verify factories used exclusively: `grep -E "(AgentRegistry|User|Workspace)\(" backend/tests/unit/test_models_orm.py | grep -v "Factory"` should return empty
</verification>

<success_criteria>
- 51/51 ORM tests pass (100% pass rate, up from 51%)
- No IntegrityError or PendingRollbackError failures
- models.py coverage remains >= 97% (no regression)
- Transaction rollback pattern implemented in conftest.py
- All object creation uses factories (no manual constructors)
- Fix pattern documented in test file docstring
- Coverage measurement now possible without test failures blocking module imports
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-GAP-01-SUMMARY.md` with:
- Number of tests fixed (32/51 now passing)
- Before/after test pass rate (51% -> 100%)
- Coverage maintained on models.py (97%+)
- Specific fixes applied (factory pattern, transaction rollback)
- Gap closed: "Coverage Cannot Be Verified" now resolvable
</output>

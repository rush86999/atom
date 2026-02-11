---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-01
subsystem: governance-testing
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/governance/conftest.py
  - backend/tests/unit/governance/test_student_training_service.py
  - backend/tests/unit/governance/test_supervision_service.py
  - backend/tests/unit/governance/test_proposal_service.py
  - backend/tests/unit/governance/test_agent_graduation_governance.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Governance domain achieves 80% coverage (all services >80%)"
    - "All governance tests pass without database table errors"
    - "Integration tests cover action execution methods in proposal_service.py"
    - "Graduation exam and constitutional validation paths are tested"
  artifacts:
    - path: "backend/tests/unit/governance/conftest.py"
      provides: "Database fixtures with all required tables"
      contains: "Workspace, ChatSession, TrainingSession, SupervisionSession, User models"
    - path: "backend/tests/unit/governance/test_student_training_service.py"
      provides: "Student training service tests >80% coverage"
      min_tests_passing: 18
    - path: "backend/tests/unit/governance/test_supervision_service.py"
      provides: "Supervision service tests >80% coverage"
      min_tests_passing: 12
    - path: "backend/tests/integration/governance/test_proposal_execution.py"
      provides: "Integration tests for action execution methods"
      min_lines: 200
    - path: "backend/tests/integration/governance/test_graduation_exams.py"
      provides: "Integration tests for graduation exam execution"
      min_lines: 150
  key_links:
    - from: "backend/tests/unit/governance/conftest.py"
      to: "core/models.py"
      via: "model imports before Base.metadata.create_all()"
      pattern: "from core.models import \\(.*, Workspace,.*ChatSession.*\\)"
---

<objective>
Fix governance domain database setup issues and add integration tests to achieve 80% coverage across all governance services.

**Purpose:** The governance domain currently has only trigger_interceptor at 83% coverage. Other services range from 14-61% due to database table creation issues (Workspace, TrainingSession, SupervisionSession, ChatSession not registered with Base) and missing integration tests for complex paths (action execution, graduation exams).

**Output:** Fixed conftest.py with all models imported, passing tests for student_training_service and supervision_service, and new integration test files for proposal execution and graduation exams.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-01a-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@backend/core/models.py
@backend/tests/unit/governance/conftest.py
@backend/tests/property_tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Fix database table creation in governance conftest.py</name>
  <files>backend/tests/unit/governance/conftest.py</files>
  <action>
    Reference property_tests/conftest.py for the correct import pattern.

    Add the following missing models to the import statement:
    - Workspace (currently causing 16 test failures in student_training_service)
    - ChatSession (needed for session management tests)
    - Ensure TrainingSession, SupervisionSession, BlockedTriggerContext are imported

    The models are defined in core/models.py at these locations:
    - Workspace: line 151
    - ChatSession: line 970
    - TrainingSession: line 3775
    - SupervisionSession: line 3609
    - BlockedTriggerContext: line 3682

    Import pattern should be:
    ```python
    from core.models import (
        AgentRegistry, AgentStatus, AgentProposal, ProposalStatus, ProposalType,
        SupervisionSession, SupervisionStatus, BlockedTriggerContext,
        TrainingSession, TriggerSource, User, UserRole, Workspace, ChatSession
    )
    ```

    After importing models, verify Base.metadata.create_all() creates all tables by adding a debug print that logs table names.
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/unit/governance/test_student_training_service.py -v --tb=short

    Expected: All 20 tests pass (currently only 4 passing due to "no such table: training_sessions" errors)
  </verify>
  <done>
    "no such table" errors eliminated for governance tests. student_training_service tests go from 4/20 passing to 18+/20 passing.
  </done>
</task>

<task type="auto">
  <name>Add integration tests for proposal action execution methods</name>
  <files>backend/tests/integration/governance/test_proposal_execution.py</files>
  <action>
    Create a new integration test file for testing the action execution methods in proposal_service.py (lines 363-747).

    The file should test:
    1. Canvas action proposal execution (forms, sheets, charts)
    2. Browser automation action proposals
    3. Device capability action proposals
    4. Deep link action proposals
    5. Complex multi-step action proposals

    Use the existing integration test patterns from tests/integration/ as reference.

    Mock external dependencies (Playwright for browser, Expo modules for device) but use real database with test data.

    File structure:
    - Import necessary modules and fixtures from property_tests/conftest.py
    - Create a TestProposalExecution class with methods for each action type
    - Use pytest.mark.asyncio for async test methods
    - Target 200+ lines of tests covering the uncovered action execution paths
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/integration/governance/test_proposal_execution.py -v --cov=core/proposal_service --cov-report=term-missing

    Expected: New tests pass, proposal_service.py coverage increases from 46% to 70%+
  </verify>
  <done>
    Integration tests for action execution created. proposal_service.py coverage increases by 20-30% points.
  </done>
</task>

<task type="auto">
  <name>Add integration tests for graduation exam and constitutional validation</name>
  <files>backend/tests/integration/governance/test_graduation_exams.py</files>
  <action>
    Create a new integration test file for testing the graduation exam execution and constitutional validation paths in agent_graduation_service.py.

    The file should test:
    1. Graduation exam execution with SandboxExecutor
    2. Constitutional compliance validation against Knowledge Graph rules
    3. Intervention rate calculation and thresholds
    4. Readiness score calculation (40% episodes, 30% intervention, 30% constitutional)
    5. Exam pass/fail scenarios for each maturity level transition

    Key paths to cover (currently uncovered):
    - Lines 253-285 in agent_graduation_service.py (graduation exam execution)
    - Constitutional validation logic

    Use the existing test patterns from test_agent_graduation_governance.py as a starting point.

    Target 150+ lines of tests.
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/integration/governance/test_graduation_exams.py -v --cov=core/agent_graduation_service --cov-report=term-missing

    Expected: New tests pass, agent_graduation_service.py coverage increases from 42% to 65%+
  </verify>
  <done>
    Integration tests for graduation exams created. agent_graduation_service.py coverage increases by 20-30% points.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run all governance tests: pytest tests/unit/governance/ tests/integration/governance/ -v --cov=core --cov=api --cov-report=term
2. Verify no "no such table" errors remain
3. Verify governance domain coverage exceeds 80%:
   - trigger_interceptor: >80% (already 83%)
   - student_training_service: >80%
   - supervision_service: >80%
   - proposal_service: >70%
   - agent_graduation_governance: >70%
4. Run coverage report: pytest --cov=core/trigger_interceptor,core/student_training_service,core/supervision_service,core/proposal_service --cov-report=html
</verification>

<success_criteria>
Governance domain achieves 80% average coverage across all services:
- All database table creation errors eliminated
- student_training_service: 80%+ coverage (from 23%)
- supervision_service: 80%+ coverage (from 14%)
- proposal_service: 70%+ coverage (from 46%)
- agent_graduation_governance: 70%+ coverage (from 51%)
- Integration test suite created for action execution and graduation exams
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-01-SUMMARY.md`
</output>

---
phase: 08-80-percent-coverage-push
plan: 18
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_proposal_evaluation.py
  - backend/tests/unit/test_execution_recovery.py
  - backend/tests/unit/test_workflow_context.py
  - backend/tests/unit/test_atom_training_orchestrator.py
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "Proposal evaluation has 70%+ test coverage"
    - "Execution recovery has 70%+ test coverage"
    - "Workflow context has 70%+ test coverage"
    - "Atom training orchestrator has 70%+ test coverage"
    - "Tests cover proposal scoring and decision logic"
    - "Tests cover recovery scenarios and state restoration"
    - "Tests cover context management and training orchestration"
  artifacts:
    - path: "backend/tests/unit/test_proposal_evaluation.py"
      provides: "Unit tests for proposal evaluation logic"
      min_lines: 500
      tests_count: 16
    - path: "backend/tests/unit/test_execution_recovery.py"
      provides: "Unit tests for execution recovery"
      min_lines: 480
      tests_count: 15
    - path: "backend/tests/unit/test_workflow_context.py"
      provides: "Unit tests for workflow context management"
      min_lines: 450
      tests_count: 14
    - path: "backend/tests/unit/test_atom_training_orchestrator.py"
      provides: "Unit tests for training orchestration"
      min_lines: 550
      tests_count: 17
  key_links:
    - from: "test_proposal_evaluation.py"
      to: "core/proposal_evaluation.py"
      via: "Mock proposal scoring"
      pattern: "mock.*score"
    - from: "test_execution_recovery.py"
      to: "core/execution_recovery.py"
      via: "Mock recovery scenarios"
      pattern: "mock.*recovery"
    - from: "test_workflow_context.py"
      to: "core/workflow_context.py"
      via: "Mock context state"
      pattern: "mock.*context"
    - from: "test_atom_training_orchestrator.py"
      to: "core/atom_training_orchestrator.py"
      via: "Mock training sessions"
      pattern: "mock.*training"
---

<objective>
Create comprehensive unit tests for 4 zero-coverage files covering proposal evaluation, execution recovery, workflow context, and training orchestration to achieve 70%+ coverage per file.

Purpose: These files (161+159+157+190 = 667 lines) represent critical agent governance, workflow recovery, and training functionality. Testing them will add ~467 lines of coverage and improve overall project coverage by ~0.8%.

Output: 4 test files with 62 total tests covering proposal evaluation, execution recovery, workflow context, and training orchestration.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-08-SUMMARY.md
@backend/core/proposal_evaluation.py
@backend/core/execution_recovery.py
@backend/core/workflow_context.py
@backend/core/atom_training_orchestrator.py

Test patterns from Phase 8.5:
- AsyncMock for async operations
- Fixture-based test setup
- Business logic testing
- State management tests
- Error handling tests
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for proposal evaluation</name>
  <files>backend/tests/unit/test_proposal_evaluation.py</files>
  <action>
    Create test_proposal_evaluation.py with comprehensive tests for core/proposal_evaluation.py (161 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime
       from core.proposal_evaluation import ProposalEvaluator
       from core.models import AgentProposal

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def evaluator(mock_db):
           return ProposalEvaluator(mock_db)
       ```

    2. Test ProposalEvaluator.evaluate_proposal:
       - test_evaluate_proposal_success (valid proposal)
       - test_evaluate_proposal_with_risk_score (risk assessment)
       - test_evaluate_proposal_low_confidence (below threshold)
       - test_evaluate_proposal_high_confidence (above threshold)

    3. Test ProposalEvaluator.score_proposal:
       - test_score_proposal_success (calculate score)
       - test_score_proposal_with_history (historical data)
       - test_score_proposal_new_agent (no history)
       - test_score_proposal_complex_action (complexity penalty)

    4. Test ProposalEvaluator.compare_proposals:
       - test_compare_proposals_success (compare 2)
       - test_compare_proposals_ranking (ranking)
       - test_compare_proposals_tie (equal scores)
       - test_compare_proposals_invalid_input (validation error)

    5. Test ProposalEvaluator.validate_proposal:
       - test_validate_proposal_success (valid proposal)
       - test_validate_proposal_missing_fields (incomplete)
       - test_validate_proposal_invalid_action (invalid action type)
       - test_validate_proposal_unauthorized_agent (403 error)

    6. Test ProposalEvaluator.check_approval_criteria:
       - test_check_approval_success (meets criteria)
       - test_check_approval_fail_risk (too risky)
       - test_check_approval_fail_maturity (agent too immature)
       - test_check_approval_fail_permissions (lacks permissions)

    Target: 500+ lines, 16 tests
    Test scoring and evaluation logic
    Test validation and approval checks
    Test comparison and ranking
  </action>
  <verify>pytest backend/tests/unit/test_proposal_evaluation.py -v</verify>
  <done>16 tests created, all passing, 70%+ coverage on proposal_evaluation.py</done>
</task>

<task type="auto">
  <name>Task 2: Create unit tests for execution recovery</name>
  <files>backend/tests/unit/test_execution_recovery.py</files>
  <action>
    Create test_execution_recovery.py with comprehensive tests for core/execution_recovery.py (159 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime
       from core.execution_recovery import ExecutionRecoveryService

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def recovery_service(mock_db):
           return ExecutionRecoveryService(mock_db)
       ```

    2. Test ExecutionRecoveryService.recover_execution:
       - test_recover_execution_success (successful recovery)
       - test_recover_execution_from_checkpoint (checkpoint restore)
       - test_recover_execution_partial_failure (partial recovery)
       - test_recover_execution_no_checkpoint (start over)

    3. Test ExecutionRecoveryService.save_checkpoint:
       - test_save_checkpoint_success (valid checkpoint)
       - test_save_checkpoint_with_state (state preservation)
       - test_save_checkpoint_overwrite (update checkpoint)
       - test_save_checkpoint_failure (handle DB error)

    4. Test ExecutionRecoveryService.restore_state:
       - test_restore_state_success (state restored)
       - test_restore_state_with_variables (variable restoration)
       - test_restore_state_not_found (no checkpoint)
       - test_restore_state_corrupted (handle corruption)

    5. Test ExecutionRecoveryService.detect_failure:
       - test_detect_failure_timeout (timeout detection)
       - test_detect_failure_crash (crash detection)
       - test_detect_failure_network_error (network error)
       - test_detect_failure_no_failure (healthy state)

    6. Test ExecutionRecoveryService.retry_execution:
       - test_retry_execution_success (retry succeeds)
       - test_retry_execution_max_retries (exhausted retries)
       - test_retry_execution_with_backoff (exponential backoff)
       - test_retry_execution_different_strategy (strategy change)

    Target: 480+ lines, 15 tests
    Test recovery scenarios and state restoration
    Test checkpoint save/restore
    Test failure detection and retry logic
  </action>
  <verify>pytest backend/tests/unit/test_execution_recovery.py -v</verify>
  <done>15 tests created, all passing, 70%+ coverage on execution_recovery.py</done>
</task>

<task type="auto">
  <name>Task 3: Create unit tests for workflow context</name>
  <files>backend/tests/unit/test_workflow_context.py</files>
  <action>
    Create test_workflow_context.py with comprehensive tests for core/workflow_context.py (157 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime
       from core.workflow_context import WorkflowContextManager

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def context_manager(mock_db):
           return WorkflowContextManager(mock_db)
       ```

    2. Test WorkflowContextManager.create_context:
       - test_create_context_success (valid context)
       - test_create_context_with_variables (variable initialization)
       - test_create_context_with_metadata (metadata preservation)
       - test_create_context_invalid_data (validation error)

    3. Test WorkflowContextManager.update_context:
       - test_update_context_success (valid update)
       - test_update_context_variables (variable update)
       - test_update_context_merge (merge with existing)
       - test_update_context_not_found (404 error)

    4. Test WorkflowContextManager.get_context:
       - test_get_context_success (found context)
       - test_get_context_with_variables (variable retrieval)
       - test_get_context_not_found (empty context)
       - test_get_context_expired (expired context)

    5. Test WorkflowContextManager.delete_context:
       - test_delete_context_success (valid delete)
       - test_delete_context_not_found (404 error)
       - test_delete_context_cleanup (cleanup related data)

    6. Test WorkflowContextManager.manage_context_lifecycle:
       - test_lifecycle_activate (activate context)
       - test_lifecycle_suspend (suspend context)
       - test_lifecycle_archive (archive context)
       - test_lifecycle_restore (restore archived)

    7. Test WorkflowContextManager.context_variables:
       - test_set_variable_success (set variable)
       - test_get_variable_success (get variable)
       - test_delete_variable_success (delete variable)
       - test_variable_not_found (missing variable)

    Target: 450+ lines, 14 tests
    Test context lifecycle management
    Test variable operations
    Test metadata and state handling
  </action>
  <verify>pytest backend/tests/unit/test_workflow_context.py -v</verify>
  <done>14 tests created, all passing, 70%+ coverage on workflow_context.py</done>
</task>

<task type="auto">
  <name>Task 4: Create unit tests for atom training orchestrator</name>
  <files>backend/tests/unit/test_atom_training_orchestrator.py</files>
  <action>
    Create test_atom_training_orchestrator.py with comprehensive tests for core/atom_training_orchestrator.py (190 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime, timedelta
       from core.atom_training_orchestrator import AtomTrainingOrchestrator

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def orchestrator(mock_db):
           return AtomTrainingOrchestrator(mock_db)
       ```

    2. Test AtomTrainingOrchestrator.create_training_session:
       - test_create_session_success (valid session)
       - test_create_session_with_curriculum (curriculum-based)
       - test_create_session_estimated_duration (time estimation)
       - test_create_session_invalid_agent (validation error)

    3. Test AtomTrainingOrchestrator.start_training:
       - test_start_training_success (start session)
       - test_start_training_with_scenarios (scenario-based)
       - test_start_training_not_ready (agent not ready)
       - test_start_training_already_active (already running)

    4. Test AtomTrainingOrchestrator.update_progress:
       - test_update_progress_success (progress update)
       - test_update_progress_complete_session (mark complete)
       - test_update_progress_failed_session (mark failed)
       - test_update_progress_not_found (404 error)

    5. Test AtomTrainingOrchestrator.evaluate_training:
       - test_evaluate_training_success (evaluation)
       - test_evaluate_training_pass_threshold (meets threshold)
       - test_evaluate_training_fail_threshold (below threshold)
       - test_evaluate_training_with_feedback (feedback incorporation)

    6. Test AtomTrainingOrchestrator.manage_training_scenarios:
       - test_add_scenario_success (add scenario)
       - test_add_scenario_with_dependencies (dependent scenarios)
       - test_complete_scenario_success (complete scenario)
       - test_skip_scenario_success (skip scenario)

    7. Test AtomTrainingOrchestrator.graduate_agent:
       - test_graduate_agent_success (promote agent)
       - test_graduate_agent_not_eligible (not ready)
       - test_graduate_agent_update_maturity (maturity update)
       - test_graduate_agent_with_conditions (conditional promotion)

    Target: 550+ lines, 17 tests
    Test training session lifecycle
    Test progress tracking and evaluation
    Test scenario management
    Test agent graduation logic
  </action>
  <verify>pytest backend/tests/unit/test_atom_training_orchestrator.py -v</verify>
  <done>17 tests created, all passing, 70%+ coverage on atom_training_orchestrator.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all new tests:
   ```bash
   pytest backend/tests/unit/test_proposal_evaluation.py -v
   pytest backend/tests/unit/test_execution_recovery.py -v
   pytest backend/tests/unit/test_workflow_context.py -v
   pytest backend/tests/unit/test_atom_training_orchestrator.py -v
   ```

2. Run tests with coverage:
   ```bash
   pytest backend/tests/unit/test_proposal_evaluation.py --cov=backend.core.proposal_evaluation --cov-report=term-missing
   pytest backend/tests/unit/test_execution_recovery.py --cov=backend.core.execution_recovery --cov-report=term-missing
   pytest backend/tests/unit/test_workflow_context.py --cov=backend.core.workflow_context --cov-report=term-missing
   pytest backend/tests/unit/test_atom_training_orchestrator.py --cov=backend.core.atom_training_orchestrator --cov-report=term-missing
   ```

3. Verify:
   - 62 tests total (16+15+14+17)
   - All tests pass
   - Each file achieves 70%+ coverage
   - Overall project coverage increases by ~0.8%
</verification>

<success_criteria>
- 4 test files created
- 62 total tests (16+15+14+17)
- 100% pass rate
- Each target file achieves 70%+ coverage
- Overall project coverage increases from ~7.3% to ~8.1%
- Tests use AsyncMock patterns from Phase 8.5
- All tests complete in under 60 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-18-SUMMARY.md`
</output>

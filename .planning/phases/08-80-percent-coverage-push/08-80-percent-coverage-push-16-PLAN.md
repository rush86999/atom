---
phase: 08-80-percent-coverage-push
plan: 16
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_workflow_coordinator.py
  - backend/tests/unit/test_workflow_parallel_executor.py
  - backend/tests/unit/test_workflow_validation.py
  - backend/tests/unit/test_workflow_retrieval.py
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "Workflow coordinator has 70%+ test coverage"
    - "Workflow parallel executor has 70%+ test coverage"
    - "Workflow validation has 70%+ test coverage"
    - "Workflow retrieval has 70%+ test coverage"
    - "Tests cover orchestration and execution logic"
    - "Tests cover validation rules and error handling"
    - "Tests cover query and retrieval operations"
  artifacts:
    - path: "backend/tests/unit/test_workflow_coordinator.py"
      provides: "Unit tests for workflow orchestration"
      min_lines: 550
      tests_count: 17
    - path: "backend/tests/unit/test_workflow_parallel_executor.py"
      provides: "Unit tests for parallel workflow execution"
      min_lines: 500
      tests_count: 16
    - path: "backend/tests/unit/test_workflow_validation.py"
      provides: "Unit tests for workflow validation logic"
      min_lines: 480
      tests_count: 15
    - path: "backend/tests/unit/test_workflow_retrieval.py"
      provides: "Unit tests for workflow query and retrieval"
      min_lines: 450
      tests_count: 14
  key_links:
    - from: "test_workflow_coordinator.py"
      to: "core/workflow_coordinator.py"
      via: "AsyncMock for workflow execution"
      pattern: "AsyncMock.*execute"
    - from: "test_workflow_parallel_executor.py"
      to: "core/workflow_parallel_executor.py"
      via: "Mock parallel execution"
      pattern: "mock.*parallel"
    - from: "test_workflow_validation.py"
      to: "core/workflow_validation.py"
      via: "Validation test scenarios"
      pattern: "test.*validate"
    - from: "test_workflow_retrieval.py"
      to: "core/workflow_retrieval.py"
      via: "Mock database queries"
      pattern: "mock.*query"
---

<objective>
Create comprehensive unit tests for 4 workflow orchestration and validation zero-coverage files to achieve 70%+ coverage per file.

Purpose: These files (197+179+165+163 = 704 lines) represent core workflow orchestration, parallel execution, validation, and retrieval functionality. Testing them will add ~493 lines of coverage and improve overall project coverage by ~0.9%.

Output: 4 test files with 62 total tests covering workflow coordinator, parallel executor, validation, and retrieval.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-11-SUMMARY.md
@backend/core/workflow_coordinator.py
@backend/core/workflow_parallel_executor.py
@backend/core/workflow_validation.py
@backend/core/workflow_retrieval.py

Test patterns from Phase 8.5:
- AsyncMock for async operations
- Fixture-based test setup
- Input validation tests
- Error handling tests
- Workflow engine patterns
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for workflow coordinator</name>
  <files>backend/tests/unit/test_workflow_coordinator.py</files>
  <action>
    Create test_workflow_coordinator.py with comprehensive tests for core/workflow_coordinator.py (197 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime
       from core.workflow_coordinator import WorkflowCoordinator

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def mock_executor():
           executor = AsyncMock()
           executor.execute_workflow = AsyncMock(return_value={"status": "completed"})
           return executor

       @pytest.fixture
       def coordinator(mock_db, mock_executor):
           return WorkflowCoordinator(mock_db, mock_executor)
       ```

    2. Test WorkflowCoordinator.coordinate_workflow_execution:
       - test_coordinate_workflow_success (successful execution)
       - test_coordinate_workflow_with_dependencies (dependency resolution)
       - test_coordinate_workflow_parallel_independent (parallel execution)
       - test_coordinate_workflow_failure_handling (failure recovery)
       - test_coordinate_workflow_timeout (timeout handling)

    3. Test WorkflowCoordinator.manage_workflow_state:
       - test_manage_state_running_to_completed (state transition)
       - test_manage_state_running_to_failed (error state)
       - test_manage_state_paused_and_resume (pause/resume)
       - test_manage_state_invalid_transition (validation error)

    4. Test WorkflowCoordinator.coordinate_multi_step_workflow:
       - test_multi_step_sequential_execution (sequential steps)
       - test_multi_step_parallel_execution (parallel steps)
       - test_multi_step_mixed_execution (mixed parallel/sequential)
       - test_multi_step_failure_rollback (rollback on failure)

    5. Test WorkflowCoordinator.handle_workflow_events:
       - test_handle_workflow_created_event (creation event)
       - test_handle_workflow_step_completed_event (step completion)
       - test_handle_workflow_failed_event (failure event)
       - test_handle_workflow_custom_event (custom events)

    6. Test WorkflowCoordinator.coordinate_workflow_callbacks:
       - test_coordinate_pre_execution_callback (before execution)
       - test_coordinate_post_execution_callback (after execution)
       - test_coordinate_error_callback (on error)
       - test_coordinate_callback_failure (callback error handling)

    Target: 550+ lines, 17 tests
    Test orchestration logic with mocked executor
    Test state management and transitions
    Test event handling and callbacks
  </action>
  <verify>pytest backend/tests/unit/test_workflow_coordinator.py -v</verify>
  <done>17 tests created, all passing, 70%+ coverage on workflow_coordinator.py</done>
</task>

<task type="auto">
  <name>Task 2: Create unit tests for workflow parallel executor</name>
  <files>backend/tests/unit/test_workflow_parallel_executor.py</files>
  <action>
    Create test_workflow_parallel_executor.py with comprehensive tests for core/workflow_parallel_executor.py (179 lines):

    1. Import and setup:
       ```python
       import pytest
       import asyncio
       from unittest.mock import AsyncMock, MagicMock, patch
       from core.workflow_parallel_executor import WorkflowParallelExecutor

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def executor(mock_db):
           return WorkflowParallelExecutor(mock_db)
       ```

    2. Test WorkflowParallelExecutor.execute_parallel_steps:
       - test_execute_parallel_success (parallel execution)
       - test_execute_parallel_with_dependencies (dependency-aware)
       - test_execute_parallel_all_independent (full parallelization)
       - test_execute_parallel_partial_failure (some steps fail)
       - test_execute_parallel_timeout (timeout handling)

    3. Test WorkflowParallelExecutor.manage_concurrency:
       - test_manage_concurrency_limit (max concurrent limit)
       - test_manage_concurrency_queue (queueing when limit reached)
       - test_manage_concurrency_dynamic_scaling (dynamic adjustment)

    4. Test WorkflowParallelExecutor.collect_parallel_results:
       - test_collect_results_success (collect all results)
       - test_collect_results_with_failures (mixed success/failure)
       - test_collect_results_timeout_handling (incomplete results)

    5. Test WorkflowParallelExecutor.handle_parallel_errors:
       - test_handle_parallel_error_continue (continue on error)
       - test_handle_parallel_error_stop (stop on error)
       - test_handle_parallel_error_retry (retry failed steps)

    6. Test WorkflowParallelExecutor.parallel_step_validation:
       - test_validate_parallel_eligible (can run in parallel)
       - test_validate_parallel_not_eligible (has dependencies)
       - test_validate_parallel_state_conflict (conflict detection)

    Target: 500+ lines, 16 tests
    Test parallel execution logic
    Test concurrency management
    Test error handling and result collection
  </action>
  <verify>pytest backend/tests/unit/test_workflow_parallel_executor.py -v</verify>
  <done>16 tests created, all passing, 70%+ coverage on workflow_parallel_executor.py</done>
</task>

<task type="auto">
  <name>Task 3: Create unit tests for workflow validation</name>
  <files>backend/tests/unit/test_workflow_validation.py</files>
  <action>
    Create test_workflow_validation.py with comprehensive tests for core/workflow_validation.py (165 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import MagicMock, patch
       from core.workflow_validation import WorkflowValidator
       from pydantic import ValidationError

       @pytest.fixture
       def validator():
           return WorkflowValidator()
       ```

    2. Test WorkflowValidator.validate_workflow_structure:
       - test_validate_structure_success (valid workflow)
       - test_validate_structure_missing_steps (missing required)
       - test_validate_structure_invalid_steps (invalid step format)
       - test_validate_structure_circular_dependencies (cycle detection)

    3. Test WorkflowValidator.validate_workflow_steps:
       - test_validate_steps_success (all steps valid)
       - test_validate_steps_invalid_action_type (invalid action)
       - test_validate_steps_missing_required_fields (incomplete step)
       - test_validate_steps_invalid_parameters (parameter validation)

    4. Test WorkflowValidator.validate_workflow_dependencies:
       - test_validate_dependencies_success (valid deps)
       - test_validate_dependencies_missing_step (broken reference)
       - test_validate_dependencies_circular (circular reference)
       - test_validate_dependencies_self_reference (self-dependency)

    5. Test WorkflowValidator.validate_workflow_parameters:
       - test_validate_parameters_success (valid params)
       - test_validate_parameters_invalid_type (type mismatch)
       - test_validate_parameters_missing_required (missing required)
       - test_validate_parameters_invalid_value (value validation)

    6. Test WorkflowValidator.validate_workflow_triggers:
       - test_validate_triggers_success (valid triggers)
       - test_validate_triggers_invalid_cron (invalid cron expression)
       - test_validate_triggers_invalid_event (invalid event type)
       - test_validate_triggers_missing_handler (no handler)

    Target: 480+ lines, 15 tests
    Test all validation rules
    Test error messages and error codes
    Test edge cases and invalid inputs
  </action>
  <verify>pytest backend/tests/unit/test_workflow_validation.py -v</verify>
  <done>15 tests created, all passing, 70%+ coverage on workflow_validation.py</done>
</task>

<task type="auto">
  <name>Task 4: Create unit tests for workflow retrieval</name>
  <files>backend/tests/unit/test_workflow_retrieval.py</files>
  <action>
    Create test_workflow_retrieval.py with comprehensive tests for core/workflow_retrieval.py (163 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime, timedelta
       from core.workflow_retrieval import WorkflowRetrievalService

       @pytest.fixture
       def mock_db():
           db = AsyncMock()
           mock_query = MagicMock()
           db.query.return_value = mock_query
           return db

       @pytest.fixture
       def service(mock_db):
           return WorkflowRetrievalService(mock_db)
       ```

    2. Test WorkflowRetrievalService.get_workflow_by_id:
       - test_get_by_id_success (found workflow)
       - test_get_by_id_not_found (404 error)
       - test_get_by_id_with_version (specific version)
       - test_get_by_id_invalid_id (validation error)

    3. Test WorkflowRetrievalService.list_workflows:
       - test_list_workflows_success (list all)
       - test_list_workflows_with_filters (by status, tag)
       - test_list_workflows_paginated (pagination)
       - test_list_workflows_sorted (sorting)

    4. Test WorkflowRetrievalService.search_workflows:
       - test_search_workflows_by_name (name search)
       - test_search_workflows_by_tag (tag search)
       - test_search_workflows_full_text (full text)
       - test_search_workflows_no_results (empty)

    5. Test WorkflowRetrievalService.get_workflow_history:
       - test_get_history_success (version history)
       - test_get_history_with_limit (limited versions)
       - test_get_history_empty (no history)

    6. Test WorkflowRetrievalService.get_workflow_executions:
       - test_get_executions_success (execution list)
       - test_get_executions_with_status (filter by status)
       - test_get_executions_date_range (date filtering)
       - test_get_executions_paginated (pagination)

    Target: 450+ lines, 14 tests
    Test query operations with mocked database
    Test filtering and pagination
    Test search functionality
  </action>
  <verify>pytest backend/tests/unit/test_workflow_retrieval.py -v</verify>
  <done>14 tests created, all passing, 70%+ coverage on workflow_retrieval.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all new tests:
   ```bash
   pytest backend/tests/unit/test_workflow_coordinator.py -v
   pytest backend/tests/unit/test_workflow_parallel_executor.py -v
   pytest backend/tests/unit/test_workflow_validation.py -v
   pytest backend/tests/unit/test_workflow_retrieval.py -v
   ```

2. Run tests with coverage:
   ```bash
   pytest backend/tests/unit/test_workflow_coordinator.py --cov=backend.core.workflow_coordinator --cov-report=term-missing
   pytest backend/tests/unit/test_workflow_parallel_executor.py --cov=backend.core.workflow_parallel_executor --cov-report=term-missing
   pytest backend/tests/unit/test_workflow_validation.py --cov=backend.core.workflow_validation --cov-report=term-missing
   pytest backend/tests/unit/test_workflow_retrieval.py --cov=backend.core.workflow_retrieval --cov-report=term-missing
   ```

3. Verify:
   - 62 tests total (17+16+15+14)
   - All tests pass
   - Each file achieves 70%+ coverage
   - Overall project coverage increases by ~0.9%
</verification>

<success_criteria>
- 4 test files created
- 62 total tests (17+16+15+14)
- 100% pass rate
- Each target file achieves 70%+ coverage
- Overall project coverage increases from 20.66% toward 21.7%
- Tests use AsyncMock patterns from Phase 8.5
- All tests complete in under 60 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-16-SUMMARY.md`
</output>

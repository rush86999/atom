---
phase: 08-80-percent-coverage-push
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_workflow_engine.py
autonomous: true

must_haves:
  truths:
    - "Workflow engine execution lifecycle is fully tested"
    - "Parallel workflow execution is tested with proper synchronization"
    - "Error recovery and rollback scenarios are covered"
    - "Workflow state management persistence is verified"
  artifacts:
    - path: "backend/tests/unit/test_workflow_engine.py"
      provides: "Comprehensive tests for workflow execution engine"
      min_lines: 500
  key_links:
    - from: "backend/tests/unit/test_workflow_engine.py"
      to: "backend/core/workflow_engine.py"
      via: "import WorkflowEngine class"
      pattern: "from core.workflow_engine import"
    - from: "test_workflow_engine.py"
      to: "backend/core/execution_state_manager.py"
      via: "mock state manager for persistence tests"
      pattern: "Mock.*ExecutionStateManager"
---

<objective>
Create comprehensive unit tests for the WorkflowEngine class, the largest single file requiring coverage (1,089 uncovered lines). The workflow engine is critical infrastructure that orchestrates multi-step workflows with parallel execution, error recovery, and state persistence.

Purpose: Ensure workflow execution reliability by testing all execution paths including success cases, error scenarios, parallel execution, state management, and graph-based workflows.
Output: Comprehensive test suite for workflow_engine.py achieving 80%+ coverage
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@backend/tests/coverage_reports/COVERAGE_PRIORITY_ANALYSIS.md
@backend/tests/conftest.py
@backend/tests/factories/execution_factory.py
@backend/core/workflow_engine.py
@backend/core/execution_state_manager.py
@backend/core/models.py
</context>

<tasks>

<task type="auto">
  <name>Create WorkflowEngine initialization and configuration tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Create backend/tests/unit/test_workflow_engine.py with initialization tests:

    Test WorkflowEngine class setup:
    1. test_workflow_engine_init() - verify max_concurrent_steps, semaphore, var_pattern
    2. test_workflow_engine_default_config() - verify defaults (max_concurrent_steps=5)
    3. test_var_pattern_compilation() - verify variable reference regex works
    4. test_cancellation_tracking() - verify cancellation_requests set initialized

    Use pytest.fixture to create WorkflowEngine instances:
    ```python
    @pytest.fixture
    def workflow_engine():
        return WorkflowEngine(max_concurrent_steps=3)
    ```

    Verify:
    - self.var_pattern is compiled regex
    - self.semaphore is asyncio.Semaphore with correct value
    - self.cancellation_requests is empty set()
    - self.max_concurrent_steps matches constructor argument
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestWorkflowEngineInit -v</verify>
  <done>All initialization tests pass (4+ tests)</done>
</task>

<task type="auto">
  <name>Create workflow execution lifecycle tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add workflow lifecycle tests to test_workflow_engine.py:

    Test the complete workflow execution flow:
    1. test_start_workflow_creates_execution() - execution_id generated
    2. test_start_workflow_with_background_tasks() - background task queued
    3. test_start_workflow_without_background_tasks() - asyncio.create_task used
    4. test_run_execution_success() - complete workflow execution
    5. test_run_execution_with_input_data() - input_data passed to steps
    6. test_get_workflow_status() - status retrieval

    Mock state_manager with AsyncMock:
    - create_execution() returns execution_id
    - get_execution_state() returns state dict
    - update_execution_status() updates status
    - update_step_status() updates step status

    Mock ws_manager with AsyncMock:
    - notify_workflow_status() sends WebSocket updates

    Verify:
    - create_execution called with workflow_id and input_data
    - Execution status transitions: RUNNING -> COMPLETED
    - WebSocket notifications sent for status changes
    - Background tasks added when background_tasks provided
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestWorkflowExecutionLifecycle -v</verify>
  <done>All lifecycle tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create step orchestration and dependency tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add step orchestration tests to test_workflow_engine.py:

    Test step execution order and dependencies:
    1. test_execute_sequential_steps() - steps run in order
    2. test_parallel_steps_execute_concurrently() - independent steps run in parallel
    3. test_step_with_dependencies_waits() - dependent steps wait for prerequisites
    4. test_step_failure_stops_dependents() - failed steps block downstream
    5. test_continue_on_error_flag() - steps with continue_on_error don't stop workflow
    6. test_step_timeout() - steps timeout after configured duration

    Create mock workflow with steps:
    ```python
    mock_workflow = {
        "id": "test-workflow",
        "steps": [
            {"id": "step1", "action": "action1", "parameters": {}},
            {"id": "step2", "action": "action2", "parameters": {}}
        ]
    }
    ```

    Mock _execute_step() with AsyncMock returning results.
    Use asyncio.Event for synchronization in parallel tests.
    Verify execution order with call tracking lists.
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestStepOrchestration -v</verify>
  <done>All orchestration tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create parameter resolution and variable reference tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add parameter resolution tests to test_workflow_engine.py:

    Test variable reference resolution:
    1. test_resolve_parameters_simple() - simple variable substitution
    2. test_resolve_parameters_nested() - nested object references
    3. test_resolve_parameters_array() - array element references
    4. test_missing_variable_raises_error() - MissingInputError for undefined vars
    5. test_resolve_parameters_with_multiple_refs() - multiple vars in one parameter
    6. test_resolve_parameters_no_vars() - parameters without variables pass through

    Test the _resolve_parameters() method with:
    - State dict containing step outputs: {"step1": {"output": {"result": 42}}}
    - Parameters with refs: {"value": "${step1.output.result}"}
    - Expected resolved: {"value": 42}

    Verify MissingInputError raised with:
    - error message containing missing variable name
    - missing_var attribute set to variable name

    Test edge cases:
    - Empty string variables
    - Undefined step references
    - Circular references (should be caught)
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestParameterResolution -v</verify>
  <done>All parameter resolution tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create graph-based workflow conversion tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add graph conversion tests to test_workflow_engine.py:

    Test node-to-step conversion:
    1. test_convert_nodes_to_steps_simple() - linear workflow
    2. test_convert_nodes_to_steps_with_branches() - branches converted to steps
    3. test_topological_sort() - Kahn's algorithm correct ordering
    4. test_convert_preserves_node_config() - config mapped to parameters
    5. test_trigger_node_handling() - trigger type preserved
    6. test_cycle_detection() - or handle cycles gracefully

    Test _convert_nodes_to_steps() with:
    ```python
    workflow = {
        "id": "graph-workflow",
        "nodes": [
            {"id": "node1", "type": "trigger", "config": {"action": "manual"}},
            {"id": "node2", "type": "action", "title": "Step 2", "config": {"service": "api"}}
        ],
        "connections": [
            {"source": "node1", "target": "node2"}
        ]
    }
    ```

    Verify:
    - Nodes converted to steps with correct sequence_order
    - Config.parameters copied to step.parameters
    - Type and action preserved
    - Connections determine step order

    Test _build_execution_graph() creates proper adjacency lists.
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestGraphConversion -v</verify>
  <done>All graph conversion tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create conditional connection and branching tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add conditional branching tests to test_workflow_engine.py:

    Test conditional workflow execution:
    1. test_has_conditional_connections() - detect conditional workflows
    2. test_evaluate_connection_condition() - condition evaluation logic
    3. test_condition_true_activates_connection() - true condition enables next step
    4. test_condition_false_blocks_connection() - false condition prevents execution
    5. test_no_condition_always_activates() - missing condition = always true
    6. test_conditional_branch_execution() - multiple branches with conditions

    Test with workflow containing conditional connections:
    ```python
    workflow = {
        "connections": [
            {"source": "step1", "target": "step2a", "condition": "result == 'success'"},
            {"source": "step1", "target": "step2b", "condition": "result == 'failure'"}
        ]
    }
    ```

    Test _evaluate_condition() method with:
    - String comparisons
    - Numeric comparisons
    - Boolean expressions
    - Nested field references

    Verify activated_connections set updated correctly.
    Verify ready_steps() respects activation status.
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestConditionalExecution -v</verify>
  <done>All conditional execution tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create error handling and rollback tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add error handling tests to test_workflow_engine.py:

    Test workflow error scenarios:
    1. test_step_failure_marks_workflow_failed() - failure propagates
    2. test_step_exception_logged() - exceptions captured in state
    3. test_continue_on_error_skips_failure() - flagged errors don't stop workflow
    4. test_rollback_on_critical_failure() - rollback triggered
    5. test_retry_failed_step() - retry logic for transient failures
    6. test_handle_timeout() - timeout handling

    Mock _execute_step() to raise exceptions:
    - ExternalServiceError for API failures
    - ValidationError for invalid data
    - TimeoutError for timeouts

    Verify state_manager.update_step_status() called with "FAILED".
    Verify error message stored in execution state.
    Verify WebSocket notification sent for failure.
    Verify rollback actions executed when configured.

    Test analytics.track_step_execution() called with:
    - status="FAILED"
    - duration_ms recorded
    - error details
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestErrorHandling -v</verify>
  <done>All error handling tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create workflow cancellation and pause/resume tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add cancellation and pause/resume tests to test_workflow_engine.py:

    Test workflow control operations:
    1. test_cancel_workflow() - cancel running workflow
    2. test_pause_workflow_for_missing_input() - automatic pause on MissingInputError
    3. test_resume_workflow() - resume from paused state
    4. test_cancellation_checks_semaphore() - in-flight steps complete
    5. test_pause_creates_checkpoint() - state saved on pause
    6. test_resume_restores_checkpoint() - state loaded on resume

    Test cancel_workflow():
    - Add execution_id to cancellation_requests
    - Verify running steps check cancellation flag
    - Verify workflow status set to CANCELLED

    Test pause behavior:
    - Mock _resolve_parameters() to raise MissingInputError
    - Verify step status set to PAUSED
    - Verify WebSocket notification with missing_var
    - Verify execution status set to PAUSED

    Test resume:
    - Create new execution with saved state
    - Verify workflow continues from paused step
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestCancellationAndPause -v</verify>
  <done>All cancellation/pause tests pass (6+ tests)</done>
</task>

<task type="auto">
  <name>Create input/output schema validation tests</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Add schema validation tests to test_workflow_engine.py:

    Test JSON schema validation for step inputs/outputs:
    1. test_validate_input_schema_pass() - valid input passes validation
    2. test_validate_input_schema_fail() - invalid input raises ValidationError
    3. test_validate_output_schema_pass() - valid output passes
    4. test_validate_output_schema_fail() - invalid output raises error
    5. test_no_schema_skip_validation() - missing schema skips validation
    6. test_schema_type_validation() - type checking in schemas

    Test with jsonschema validation:
    ```python
    step = {
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        }
    }
    ```

    Verify jsonschema.validate() called with correct schema.
    Verify ValidationError raised for invalid data.
    Verify validation skipped when schema is empty dict.

    Test various schema types:
    - String validation
    - Number validation (int, float)
    - Array validation
    - Nested object validation
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py::TestSchemaValidation -v</verify>
  <done>All schema validation tests pass (6+ tests)</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/unit/test_workflow_engine.py -v to verify all tests pass
2. Run pytest --cov=backend/core/workflow_engine backend/tests/unit/test_workflow_engine.py to verify coverage
3. Check that coverage.json shows 80%+ coverage for workflow_engine.py
4. Verify parallel execution tests use proper async synchronization (asyncio.Event, asyncio.Semaphore)
5. Confirm all mocked dependencies (state_manager, ws_manager, analytics) are properly isolated
</verification>

<success_criteria>
- test_workflow_engine.py created with 50+ tests
- 80%+ code coverage on workflow_engine.py
- All workflow execution paths tested (success, failure, parallel, conditional)
- Error handling scenarios covered (exceptions, timeouts, rollbacks)
- Pause/resume functionality verified
- Schema validation tested
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-02-SUMMARY.md`
</output>

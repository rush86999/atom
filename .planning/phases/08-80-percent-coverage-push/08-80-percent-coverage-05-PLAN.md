---
phase: 08-80-percent-coverage-push
plan: 05
type: execute
wave: 2
depends_on: []
files_modified:
  - backend/tests/unit/test_workflow_analytics_engine.py
  - backend/tests/unit/test_workflow_debugger.py
autonomous: true

must_haves:
  truths:
    - "Workflow execution analytics tracking is tested"
    - "Performance metrics collection is verified"
    - "Debug breakpoints and tracing functionality is covered"
    - "Error diagnosis and reporting are tested"
  artifacts:
    - path: "backend/tests/unit/test_workflow_analytics_engine.py"
      provides: "Tests for workflow analytics engine"
      min_lines: 350
    - path: "backend/tests/unit/test_workflow_debugger.py"
      provides: "Tests for workflow debugger"
      min_lines: 300
  key_links:
    - from: "backend/tests/unit/test_workflow_analytics_engine.py"
      to: "backend/core/workflow_analytics_engine.py"
      via: "import analytics engine classes"
      pattern: "from core.workflow_analytics_engine import"
    - from: "backend/tests/unit/test_workflow_debugger.py"
      to: "backend/core/workflow_debugger.py"
      via: "import debugger classes"
      pattern: "from core.workflow_debugger import"
---

<objective>
Create comprehensive tests for the workflow analytics and debugging systems, covering execution tracking, performance metrics, debug breakpoints, execution tracing, and error diagnosis for workflows.

Purpose: Ensure reliable workflow observability and debugging capabilities for monitoring production workflows and diagnosing issues.
Output: Test suites for workflow_analytics_engine.py and workflow_debugger.py achieving 80%+ coverage
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
@backend/core/workflow_analytics_engine.py
@backend/core/workflow_debugger.py
@backend/core/models.py
@backend/tests/factories/execution_factory.py
</context>

<tasks>

<task type="auto">
  <name>Create workflow analytics engine initialization and tracking tests</name>
  <files>backend/tests/unit/test_workflow_analytics_engine.py</files>
  <action>
    Create backend/tests/unit/test_workflow_analytics_engine.py:

    Test WorkflowAnalyticsEngine initialization:
    1. test_analytics_engine_init() - verify engine initialization
    2. test_get_analytics_engine() - singleton pattern
    3. test_track_workflow_start() - workflow start tracking
    4. test_track_workflow_complete() - workflow completion tracking
    5. test_track_workflow_failure() - workflow failure tracking
    6. test_track_step_execution() - step execution tracking
    7. test_record_step_timing() - timing metrics

    Mock database session:
    ```python
    @pytest.fixture
    def mock_db():
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def analytics_engine():
        from core.workflow_analytics_engine import WorkflowAnalyticsEngine
        return WorkflowAnalyticsEngine()
    ```

    Test tracking methods:
    - Verify events stored correctly
    - Timestamps recorded accurately
    - Workflow IDs associated with events
    - User IDs tracked for analytics
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_engine.py::TestAnalyticsInit -v</verify>
  <done>All initialization tests pass (7+ tests)</done>
</task>

<task type="auto">
  <name>Create performance metrics collection tests</name>
  <files>backend/tests/unit/test_workflow_analytics_engine.py</files>
  <action>
    Add performance metrics tests to test_workflow_analytics_engine.py:

    Test performance tracking:
    1. test_record_execution_time() - execution duration
    2. test_record_step_duration() - per-step timing
    3. test_calculate_average_duration() - average computation
    4. test_calculate_percentile_duration() - p50, p95, p99
    5. test_track_memory_usage() - memory metrics
    6. test_track_cpu_usage() - CPU metrics
    7. test_record_concurrent_executions() - concurrency tracking
    8. test_calculate_throughput() - workflows per time period

    Test metric calculations:
    - Average over time window
    - Percentile calculations
    - Rate calculations (executions/minute)
    - Resource usage aggregation

    Mock timing data:
    ```python
    mock_executions = [
        {"duration_ms": 100, "workflow_id": "wf1"},
        {"duration_ms": 200, "workflow_id": "wf1"},
        {"duration_ms": 150, "workflow_id": "wf2"}
    ]
    ```

    Verify:
    - Correct statistical calculations
    - Time window filtering
    - Outlier handling
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_engine.py::TestPerformanceMetrics -v</verify>
  <done>All performance metrics tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create analytics query and aggregation tests</name>
  <files>backend/tests/unit/test_workflow_analytics_engine.py</files>
  <action>
    Add query tests to test_workflow_analytics_engine.py:

    Test analytics queries:
    1. test_get_workflow_statistics() - overall workflow stats
    2. test_get_step_statistics() - per-step stats
    3. test_get_error_rate() - error rate calculation
    4. test_get_success_rate() - success rate calculation
    5. test_get_most_failed_steps() - failure hotspots
    6. test_get_slowest_steps() - performance bottlenecks
    7. test_get_execution_trends() - time-series trends
    8. test_get_user_analytics() - per-user analytics
    9. test_filter_by_time_range() - time-based filtering
    10. test_aggregate_by_workflow_type() - grouping by type

    Mock query results from database:
    ```python
    @pytest.fixture
    def mock_query_result():
        return Mock(
            count=lambda: 100,
            filter=lambda self, **kwargs: self,
            group_by=lambda self, *args: self,
            all=lambda: [{"workflow_id": "wf1", "count": 50}]
        )
    ```

    Test aggregations:
    - COUNT, SUM, AVG operations
    - GROUP BY queries
    - HAVING clauses
    - JOIN operations for related data

    Verify query building:
    - Correct filters applied
    - Proper joins constructed
    - Time range filtering works
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_engine.py::TestAnalyticsQueries -v</verify>
  <done>All query tests pass (10+ tests)</done>
</task>

<task type="auto">
  <name>Create workflow debugger initialization and breakpoint tests</name>
  <files>backend/tests/unit/test_workflow_debugger.py</files>
  <action>
    Create backend/tests/unit/test_workflow_debugger.py:

    Test WorkflowDebugger initialization:
    1. test_debugger_init() - verify debugger initialization
    2. test_set_breakpoint() - set execution breakpoint
    3. test_clear_breakpoint() - remove breakpoint
    4. test_list_breakpoints() - enumerate breakpoints
    5. test_breakpoint_at_step() - breakpoint at specific step
    6. test_conditional_breakpoint() - breakpoint with condition
    7. test_breakpoint_hit_count() - track breakpoint hits

    Mock debugger session:
    ```python
    @pytest.fixture
    def workflow_debugger():
        from core.workflow_debugger import WorkflowDebugger
        return WorkflowDebugger()

    @pytest.fixture
    def mock_execution():
        execution = Mock()
        execution.id = "exec-1"
        execution.workflow_id = "wf-1"
        execution.status = "RUNNING"
        return execution
    ```

    Test breakpoint operations:
    - Breakpoints set on workflow IDs
    - Breakpoints set on step IDs
    - Conditional breakpoints evaluated
    - Breakpoints persist across executions
  </action>
  <verify>pytest backend/tests/unit/test_workflow_debugger.py::TestDebuggerInit -v</verify>
  <done>All debugger initialization tests pass (7+ tests)</done>
</task>

<task type="auto">
  <name>Create execution tracing and stepping tests</name>
  <files>backend/tests/unit/test_workflow_debugger.py</files>
  <action>
    Add execution tracing tests to test_workflow_debugger.py:

    Test tracing functionality:
    1. test_start_tracing() - begin execution trace
    2. test_stop_tracing() - end execution trace
    3. test_get_trace() - retrieve trace data
    4. test_step_into() - step into function
    5. test_step_over() - step over function
    6. test_step_out() - step out of function
    7. test_continue_execution() - resume from breakpoint
    8. test_pause_execution() - pause running workflow

    Mock execution state:
    ```python
    @pytest.fixture
    def mock_execution_state():
        return {
            "current_step": "step1",
            "stack": ["workflow", "step1"],
            "variables": {"input": "value"},
            "status": "paused"
        }
    ```

    Test stepping operations:
    - Stack frame tracking
    - Variable inspection
    - Call stack navigation
    - Resume/pause state management

    Verify trace captures:
    - Function entry/exit
    - Variable values
    - Return values
    - Exceptions raised
  </action>
  <verify>pytest backend/tests/unit/test_workflow_debugger.py::TestExecutionTracing -v</verify>
  <done>All tracing tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create error diagnosis and reporting tests</name>
  <files>backend/tests/unit/test_workflow_debugger.py</files>
  <action>
    Add error diagnosis tests to test_workflow_debugger.py:

    Test error diagnosis:
    1. test_diagnose_error() - error root cause analysis
    2. test_get_error_context() - context around error
    3. test_get_stack_trace() - stack trace extraction
    4. test_suggest_fix() - fix suggestion
    5. test_similar_errors() - find similar historical errors
    6. test_error_categories() - categorize error types
    7. test_error_frequency() - track error frequency
    8. test_generate_error_report() - comprehensive error report

    Test error scenarios:
    - ValidationError: input validation failures
    - ExternalServiceError: API failures
    - TimeoutError: execution timeouts
    - ConstraintError: database constraints

    Mock error data:
    ```python
    @pytest.fixture
    def mock_error():
        error = Exception("Test error")
        error.__traceback__ = Mock()
        return error
    ```

    Verify diagnosis includes:
    - Error type and message
    - Stack trace
    - Variable state at error
    - Suggested fixes
    - Similar errors with solutions
  </action>
  <verify>pytest backend/tests/unit/test_workflow_debugger.py::TestErrorDiagnosis -v</verify>
  <done>All error diagnosis tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create variable inspection and state snapshot tests</name>
  <files>backend/tests/unit/test_workflow_debugger.py</files>
  <action>
    Add variable inspection tests to test_workflow_debugger.py:

    Test state inspection:
    1. test_inspect_variable() - inspect variable value
    2. test_list_variables() - list all variables in scope
    3. test_get_execution_state() - get full execution state
    4. test_create_snapshot() - create state snapshot
    5. test_restore_snapshot() - restore from snapshot
    6. test_compare_states() - compare two states
    7. test_watch_variable() - set variable watch
    8. test_watch_triggered() - watch condition triggered

    Test variable types:
    - Primitive types (string, number, boolean)
    - Complex types (dict, list)
    - Workflow-specific types (step output)

    Mock state snapshots:
    ```python
    snapshot = {
        "step": "step1",
        "variables": {"input": "value", "counter": 5},
        "timestamp": datetime.utcnow()
    }
    ```

    Verify:
    - Variables captured correctly
    - Snapshots restore accurately
    - Watches trigger on change
    - State comparison works
  </action>
  <verify>pytest backend/tests/unit/test_workflow_debugger.py::TestVariableInspection -v</verify>
  <done>All variable inspection tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create analytics export and reporting tests</name>
  <files>backend/tests/unit/test_workflow_analytics_engine.py</files>
  <action>
    Add export tests to test_workflow_analytics_engine.py:

    Test analytics export:
    1. test_export_to_csv() - CSV export
    2. test_export_to_json() - JSON export
    3. test_generate_report() - generate analytics report
    4. test_email_report() - email report delivery
    5. test_schedule_report() - scheduled reports
    6. test_dashboard_data() - dashboard API data

    Mock export functions:
    ```python
    @pytest.fixture
    def mock_file_export():
        with patch('core.workflow_analytics_engine.open') as mock:
            mock.return_value.__enter__ = Mock(return_value=Mock())
            mock.return_value.__exit__ = Mock(return_value=False)
            yield mock
    ```

    Test export formats:
    - CSV with proper headers
    - JSON with proper structure
    - Report generation with charts
    - Scheduled report triggers

    Verify:
    - Data formatting correct
    - Files written successfully
    - Report generation complete
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_engine.py::TestAnalyticsExport -v</verify>
  <done>All export tests pass (6+ tests)</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/unit/test_workflow_analytics_engine.py -v to verify analytics tests pass
2. Run pytest backend/tests/unit/test_workflow_debugger.py -v to verify debugger tests pass
3. Run pytest --cov=backend/core/workflow_analytics_engine backend/tests/unit/test_workflow_analytics_engine.py to verify coverage
4. Run pytest --cov=backend/core/workflow_debugger backend/tests/unit/test_workflow_debugger.py to verify coverage
5. Check coverage.json shows 70%+ coverage for both files (465 uncovered lines targeted)
6. Verify all database operations use Mock(spec=Session)
</verification>

<success_criteria>
- test_workflow_analytics_engine.py created with 30+ tests
- test_workflow_debugger.py created with 30+ tests
- 70%+ coverage on both files
- Performance metrics tested
- Breakpoint functionality tested
- Execution tracing verified
- Error diagnosis covered
- Variable inspection tested
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-05-SUMMARY.md`
</output>

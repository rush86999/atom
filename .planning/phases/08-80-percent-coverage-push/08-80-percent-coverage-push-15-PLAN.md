---
phase: 08-80-percent-coverage-push
plan: 15
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_workflow_analytics_endpoints.py
  - backend/tests/unit/test_workflow_analytics_service.py
  - backend/tests/unit/test_canvas_coordinator.py
  - backend/tests/unit/test_audit_service.py
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "Workflow analytics endpoints have 70%+ test coverage"
    - "Workflow analytics service has 70%+ test coverage"
    - "Canvas coordinator has 70%+ test coverage"
    - "Audit service has 70%+ test coverage"
    - "All 4 files have comprehensive input validation tests"
    - "All 4 files have error handling tests"
    - "Tests cover database operations and query logic"
  artifacts:
    - path: "backend/tests/unit/test_workflow_analytics_endpoints.py"
      provides: "Unit tests for workflow analytics API endpoints"
      min_lines: 600
      tests_count: 20
    - path: "backend/tests/unit/test_workflow_analytics_service.py"
      provides: "Unit tests for workflow analytics business logic"
      min_lines: 550
      tests_count: 18
    - path: "backend/tests/unit/test_canvas_coordinator.py"
      provides: "Unit tests for canvas coordination logic"
      min_lines: 500
      tests_count: 16
    - path: "backend/tests/unit/test_audit_service.py"
      provides: "Unit tests for audit trail service"
      min_lines: 450
      tests_count: 15
  key_links:
    - from: "test_workflow_analytics_endpoints.py"
      to: "core/workflow_analytics_endpoints.py"
      via: "FastAPI TestClient"
      pattern: "client\\.get|client\\.post"
    - from: "test_workflow_analytics_service.py"
      to: "core/workflow_analytics_service.py"
      via: "AsyncMock for database"
      pattern: "AsyncMock.*db"
    - from: "test_canvas_coordinator.py"
      to: "core/canvas_coordinator.py"
      via: "Mock canvas operations"
      pattern: "mock_canvas"
    - from: "test_audit_service.py"
      to: "core/audit_service.py"
      via: "Mock database session"
      pattern: "mock.*session"
---

<objective>
Create comprehensive unit tests for 4 high-impact workflow and canvas zero-coverage files to achieve 70%+ coverage per file.

Purpose: These files (333+212+183+164 = 892 lines) represent critical workflow analytics and canvas coordination functionality. Testing them will add ~625 lines of coverage and improve overall project coverage by ~1.1%.

Output: 4 test files with 69-75 total tests covering workflow analytics endpoints, analytics service, canvas coordinator, and audit service.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-10-SUMMARY.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-11-SUMMARY.md
@backend/core/workflow_analytics_endpoints.py
@backend/core/workflow_analytics_service.py
@backend/core/canvas_coordinator.py
@backend/core/audit_service.py

Test patterns from Phase 8.5:
- AsyncMock for database operations
- TestClient for FastAPI endpoints
- Fixture-based test setup
- Input validation tests
- Error handling tests
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for workflow analytics endpoints</name>
  <files>backend/tests/unit/test_workflow_analytics_endpoints.py</files>
  <action>
    Create test_workflow_analytics_endpoints.py with comprehensive tests for core/workflow_analytics_endpoints.py (333 lines):

    1. Import and setup:
       ```python
       import pytest
       from fastapi.testclient import TestClient
       from unittest.mock import AsyncMock, MagicMock, patch
       from core.workflow_analytics_endpoints import router
       from core.models import WorkflowExecution, AgentExecution

       @pytest.fixture
       def client():
           return TestClient(router)

       @pytest.fixture
       def mock_db():
           return AsyncMock()
       ```

    2. Test GET /analytics/workflows/execution:
       - test_get_workflow_execution_stats_success (valid data)
       - test_get_workflow_execution_stats_empty (no data)
       - test_get_workflow_execution_stats_date_range (with filters)
       - test_get_workflow_execution_stats_invalid_date (400 error)

    3. Test GET /analytics/workflows/performance:
       - test_get_workflow_performance_success (valid metrics)
       - test_get_workflow_performance_aggregation (avg/max/min)
       - test_get_workflow_performance_by_agent (filter by agent)
       - test_get_workflow_performance_no_data (empty response)

    4. Test GET /analytics/workflows/trends:
       - test_get_workflow_trends_success (time series data)
       - test_get_workflow_trends_invalid_interval (400 error)
       - test_get_workflow_trends_custom_range (date filtering)

    5. Test POST /analytics/workflows/export:
       - test_export_workflow_analytics_success (CSV export)
       - test_export_workflow_analytics_invalid_format (400 error)
       - test_export_workflow_analytics_filter_validation (query params)

    6. Test GET /analytics/workflows/errors:
       - test_get_workflow_errors_success (error list)
       - test_get_workflow_errors_filtered (by severity)
       - test_get_workflow_errors_empty (no errors)

    7. Test GET /analytics/workflows/comparison:
       - test_compare_workflows_success (compare 2 workflows)
       - test_compare_workflows_invalid_ids (400 error)
       - test_compare_workflows_not_found (404 error)

    Target: 600+ lines, 20 tests
    Use TestClient for all endpoint tests
    Mock database queries with AsyncMock
    Test all success and error paths
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_endpoints.py -v</verify>
  <done>20 tests created, all passing, 70%+ coverage on workflow_analytics_endpoints.py</done>
</task>

<task type="auto">
  <name>Task 2: Create unit tests for workflow analytics service</name>
  <files>backend/tests/unit/test_workflow_analytics_service.py</files>
  <action>
    Create test_workflow_analytics_service.py with comprehensive tests for core/workflow_analytics_service.py (212 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime, timedelta
       from core.workflow_analytics_service import WorkflowAnalyticsService

       @pytest.fixture
       def mock_db():
           db = AsyncMock()
           db.query = MagicMock()
           db.filter = MagicMock()
           db.group_by = MagicMock()
           return db

       @pytest.fixture
       def service():
           return WorkflowAnalyticsService()
       ```

    2. Test WorkflowAnalyticsService.calculate_execution_metrics:
       - test_calculate_metrics_success (valid execution)
       - test_calculate_metrics_multiple_executions (aggregate)
       - test_calculate_metrics_with_failures (error tracking)
       - test_calculate_metrics_empty_data (zero state)

    3. Test WorkflowAnalyticsService.get_workflow_trends:
       - test_get_trends_daily (daily aggregation)
       - test_get_trends_weekly (weekly aggregation)
       - test_get_trends_custom_range (date filtering)
       - test_get_trends_no_data (empty series)

    4. Test WorkflowAnalyticsService.compare_workflow_performance:
       - test_compare_workflows_success (comparison)
       - test_compare_workflows_metrics (duration, success rate)
       - test_compare_workflows_invalid_input (validation)

    5. Test WorkflowAnalyticsService.get_error_analysis:
       - test_get_error_analysis_success (error breakdown)
       - test_get_error_analysis_by_type (categorization)
       - test_get_error_analysis_no_errors (clean state)

    6. Test WorkflowAnalyticsService.generate_analytics_report:
       - test_generate_report_success (full report)
       - test_generate_report_summary_only (summary mode)
       - test_generate_report_with_charts (chart data)

    Target: 550+ lines, 18 tests
    Test business logic with mocked database
    Cover all calculation paths
    Test edge cases and error conditions
  </action>
  <verify>pytest backend/tests/unit/test_workflow_analytics_service.py -v</verify>
  <done>18 tests created, all passing, 70%+ coverage on workflow_analytics_service.py</done>
</task>

<task type="auto">
  <name>Task 3: Create unit tests for canvas coordinator</name>
  <files>backend/tests/unit/test_canvas_coordinator.py</files>
  <action>
    Create test_canvas_coordinator.py with comprehensive tests for core/canvas_coordinator.py (183 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from core.canvas_coordinator import CanvasCoordinator
       from core.models import CanvasAudit

       @pytest.fixture
       def mock_db():
           return AsyncMock()

       @pytest.fixture
       def coordinator():
           return CanvasCoordinator()
       ```

    2. Test CanvasCoordinator coordinate_canvas_creation:
       - test_coordinate_creation_success (valid canvas)
       - test_coordinate_creation_with_permissions (governance check)
       - test_coordinate_creation_invalid_type (400 error)
       - test_coordinate_creation_governance_denied (403 error)

    3. Test CanvasCoordinator coordinate_multi_agent_canvas:
       - test_multi_agent_coordination_success (parallel agents)
       - test_multi_agent_coordination_sequential (sequential mode)
       - test_multi_agent_coordination_locked (locked mode)
       - test_multi_agent_coordination_conflict (conflict resolution)

    4. Test CanvasCoordinator coordinate_canvas_update:
       - test_coordinate_update_success (valid update)
       - test_coordinate_update_version_check (version validation)
       - test_coordinate_update_concurrent (optimistic locking)

    5. Test CanvasCoordinator.coordinate_canvas_sharing:
       - test_coordinate_share_success (share canvas)
       - test_coordinate_share_permissions (permission check)
       - test_coordinate_share_already_shared (idempotent)

    6. Test CanvasCoordinator coordinate_canvas_favorites:
       - test_coordinate_add_favorite_success (add favorite)
       - test_coordinate_remove_favorite_success (remove favorite)
       - test_coordinate_list_favorites_success (list favorites)

    Target: 500+ lines, 16 tests
    Test coordination logic for all canvas operations
    Mock database operations
    Test multi-agent scenarios
  </action>
  <verify>pytest backend/tests/unit/test_canvas_coordinator.py -v</verify>
  <done>16 tests created, all passing, 70%+ coverage on canvas_coordinator.py</done>
</task>

<task type="auto">
  <name>Task 4: Create unit tests for audit service</name>
  <files>backend/tests/unit/test_audit_service.py</files>
  <action>
    Create test_audit_service.py with comprehensive tests for core/audit_service.py (164 lines):

    1. Import and setup:
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from datetime import datetime
       from core.audit_service import AuditService
       from core.models import AuditLog

       @pytest.fixture
       def mock_db():
           db = AsyncMock()
           db.add = MagicMock()
           db.commit = MagicMock()
           db.flush = MagicMock()
           return db

       @pytest.fixture
       def audit_service():
           return AuditService()
       ```

    2. Test AuditService.log_action:
       - test_log_action_success (valid log)
       - test_log_action_with_metadata (rich context)
       - test_log_action_database_error (handle DB error)
       - test_log_action_batch (multiple logs)

    3. Test AuditService.query_audit_logs:
       - test_query_logs_success (valid query)
       - test_query_logs_with_filters (by user, action, date)
       - test_query_logs_paginated (pagination)
       - test_query_logs_empty (no results)

    4. Test AuditService.get_audit_trail:
       - test_get_audit_trail_success (entity trail)
       - test_get_audit_trail_filtered (by action type)
       - test_get_audit_trail_not_found (empty trail)

    5. Test AuditService.export_audit_logs:
       - test_export_logs_success (CSV export)
       - test_export_logs_filtered (filtered export)
       - test_export_logs_no_data (empty export)

    6. Test AuditService.retention_policy:
       - test_retention_cleanup_old_logs (delete old)
       - test_retention_preserve_recent (keep recent)
       - test_retention_archival (archive before delete)

    Target: 450+ lines, 15 tests
    Test all CRUD operations for audit logs
    Test filtering and pagination
    Test retention policy logic
  </action>
  <verify>pytest backend/tests/unit/test_audit_service.py -v</verify>
  <done>15 tests created, all passing, 70%+ coverage on audit_service.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all new tests:
   ```bash
   pytest backend/tests/unit/test_workflow_analytics_endpoints.py -v
   pytest backend/tests/unit/test_workflow_analytics_service.py -v
   pytest backend/tests/unit/test_canvas_coordinator.py -v
   pytest backend/tests/unit/test_audit_service.py -v
   ```

2. Run tests with coverage:
   ```bash
   pytest backend/tests/unit/test_workflow_analytics_endpoints.py --cov=backend.core.workflow_analytics_endpoints --cov-report=term-missing
   pytest backend/tests/unit/test_workflow_analytics_service.py --cov=backend.core.workflow_analytics_service --cov-report=term-missing
   pytest backend/tests/unit/test_canvas_coordinator.py --cov=backend.core.canvas_coordinator --cov-report=term-missing
   pytest backend/tests/unit/test_audit_service.py --cov=backend.core.audit_service --cov-report=term-missing
   ```

3. Verify:
   - 69 tests total (20+18+16+15)
   - All tests pass
   - Each file achieves 70%+ coverage
   - Overall project coverage increases by ~1.1%
</verification>

<success_criteria>
- 4 test files created
- 69 total tests (20+18+16+15)
- 100% pass rate
- Each target file achieves 70%+ coverage
- Overall project coverage increases from 4.4% to ~5.5%
- Tests use AsyncMock and TestClient patterns from Phase 8.5
- All tests complete in under 60 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-15-SUMMARY.md`
</output>

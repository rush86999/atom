---
phase: 08-80-percent-coverage-push
plan: 10
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_atom_agent_endpoints.py
  - backend/tests/unit/test_advanced_workflow_system.py
  - backend/tests/unit/test_workflow_versioning_system.py
  - backend/tests/unit/test_workflow_marketplace.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "atom_agent_endpoints.py has baseline unit tests with 25%+ coverage"
    - "advanced_workflow_system.py has baseline unit tests with 25%+ coverage"
    - "workflow_versioning_system.py has baseline unit tests with 25%+ coverage"
    - "workflow_marketplace.py has baseline unit tests with 25%+ coverage"
    - "All new tests pass with pytest"
  artifacts:
    - path: "backend/tests/unit/test_atom_agent_endpoints.py"
      provides: "Baseline unit tests for agent endpoints"
      min_lines: 400
    - path: "backend/tests/unit/test_advanced_workflow_system.py"
      provides: "Baseline unit tests for advanced workflow system"
      min_lines: 300
    - path: "backend/tests/unit/test_workflow_versioning_system.py"
      provides: "Baseline unit tests for workflow versioning"
      min_lines: 250
    - path: "backend/tests/unit/test_workflow_marketplace.py"
      provides: "Baseline unit tests for workflow marketplace"
      min_lines: 300
  key_links:
    - from: "test_atom_agent_endpoints.py"
      to: "core/atom_agent_endpoints.py"
      via: "import"
      pattern: "from core.atom_agent_endpoints import"
    - from: "test_advanced_workflow_system.py"
      to: "core/advanced_workflow_system.py"
      via: "import"
      pattern: "from core.advanced_workflow_system import"
    - from: "test_workflow_versioning_system.py"
      to: "core/workflow_versioning_system.py"
      via: "import"
      pattern: "from core.workflow_versioning_system import"
    - from: "test_workflow_marketplace.py"
      to: "core/workflow_marketplace.py"
      via: "import"
      pattern: "from core.workflow_marketplace import"
---

<objective>
Create baseline unit tests for 4 remaining zero-coverage core modules: atom_agent_endpoints, advanced_workflow_system, workflow_versioning_system, and workflow_marketplace. These complete the 10 zero-coverage files gap.

Purpose: Establish test coverage for API endpoints and advanced workflow systems. Baseline 25%+ target accounts for complex FastAPI endpoint testing challenges.

Output: 4 new test files with 250-400 lines each, achieving 25%+ coverage on target modules.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-01-SUMMARY.md
@backend/core/atom_agent_endpoints.py
@backend/core/advanced_workflow_system.py
@backend/core/workflow_versioning_system.py
@backend/core/workflow_marketplace.py

Gap context from VERIFICATION.md:
- "test_atom_agent_endpoints.py - not created"
- "test_advanced_workflow_system.py - not created"
- "test_workflow_versioning_system.py - not created"
- "test_workflow_marketplace.py - not created"
- 10 zero-coverage files remain untested

Test patterns from prior plans:
- AsyncMock for async service dependencies
- FeatureFlags mock for governance bypass
- For API tests: TestClient from fastapi.testclient
- Mock request/response patterns for endpoint testing
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create baseline unit tests for atom_agent_endpoints.py</name>
  <files>backend/tests/unit/test_atom_agent_endpoints.py</files>
  <action>
    Create test_atom_agent_endpoints.py with baseline unit tests for agent API endpoints:

    1. Read core/atom_agent_endpoints.py to understand the endpoint structure
    2. Create test class TestAgentEndpointsInit with 2-3 tests for FastAPI app initialization
    3. Create test class TestChatEndpoint with 4-5 tests for /chat endpoint
    4. Create test class TestStreamEndpoint with 3-4 tests for streaming endpoint
    5. Create test class TestAgentEndpoints with 4-5 tests for agent CRUD operations

    Use TestClient from fastapi.testclient for endpoint testing
    Mock llm_handler, governance_service dependencies
    Test request validation and response formatting

    Target: 400+ lines, 15-20 tests, 25%+ coverage

    Focus on:
    - Endpoint routing (correct endpoints respond)
    - Request/response validation
    - Error handling (400, 404, 500 responses)
    - Authentication/authorization checks (mocked)
  </action>
  <verify>pytest backend/tests/unit/test_atom_agent_endpoints.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 25%+ coverage on atom_agent_endpoints.py</done>
</task>

<task type="auto">
  <name>Task 2: Create baseline unit tests for advanced_workflow_system.py</name>
  <files>backend/tests/unit/test_advanced_workflow_system.py</files>
  <action>
    Create test_advanced_workflow_system.py with baseline unit tests for AdvancedWorkflowSystem:

    1. Read core/advanced_workflow_system.py to understand the class structure
    2. Create test class TestAdvancedWorkflowInit with 3-4 tests for initialization
    3. Create test class TestNestedWorkflows with 4-5 tests for workflow composition
    4. Create test class TestParallelExecution with 3-4 tests for parallel execution logic
    5. Create test class TestWorkflowErrors with 3-4 tests for error handling

    Mock workflow_engine, state_manager dependencies
    Test workflow composition logic
    Test parallel execution coordination

    Target: 300+ lines, 15-20 tests, 25%+ coverage

    Focus on orchestration logic, not full workflow execution
  </action>
  <verify>pytest backend/tests/unit/test_advanced_workflow_system.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 25%+ coverage on advanced_workflow_system.py</done>
</task>

<task type="auto">
  <name>Task 3: Create baseline unit tests for workflow_versioning_system.py</name>
  <files>backend/tests/unit/test_workflow_versioning_system.py</files>
  <action>
    Create test_workflow_versioning_system.py with baseline unit tests for WorkflowVersioningSystem:

    1. Read core/workflow_versioning_system.py to understand the class structure
    2. Create test class TestVersioningInit with 2-3 tests for initialization
    3. Create test class TestVersionCreation with 4-5 tests for version creation
    4. Create test class TestVersionRollback with 3-4 tests for rollback operations
    5. Create test class TestVersionDiff with 3-4 tests for diff generation

    Mock database operations for version storage
    Test version numbering logic
    Test rollback logic

    Target: 250+ lines, 15-20 tests, 25%+ coverage

    Focus on version management logic
  </action>
  <verify>pytest backend/tests/unit/test_workflow_versioning_system.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 25%+ coverage on workflow_versioning_system.py</done>
</task>

<task type="auto">
  <name>Task 4: Create baseline unit tests for workflow_marketplace.py</name>
  <files>backend/tests/unit/test_workflow_marketplace.py</files>
  <action>
    Create test_workflow_marketplace.py with baseline unit tests for WorkflowMarketplace:

    1. Read core/workflow_marketplace.py to understand the class structure
    2. Create test class TestMarketplaceInit with 2-3 tests for initialization
    3. Create test class TestWorkflowPublish with 4-5 tests for publishing workflows
    4. Create test class TestWorkflowDiscovery with 3-4 tests for search/discovery
    5. Create test class TestMarketplaceErrors with 3-4 tests for error handling

    Mock workflow storage/database
    Test publishing workflow logic
    Test search and filtering logic

    Target: 300+ lines, 15-20 tests, 25%+ coverage

    Focus on marketplace operations logic
  </action>
  <verify>pytest backend/tests/unit/test_workflow_marketplace.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 25%+ coverage on workflow_marketplace.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run pytest on all four new test files:
   ```bash
   pytest backend/tests/unit/test_atom_agent_endpoints.py backend/tests/unit/test_advanced_workflow_system.py backend/tests/unit/test_workflow_versioning_system.py backend/tests/unit/test_workflow_marketplace.py -v
   ```

2. Verify all tests pass (60-80 tests total expected)

3. Run coverage report:
   ```bash
   pytest backend/tests/unit/test_atom_agent_endpoints.py backend/tests/unit/test_advanced_workflow_system.py backend/tests/unit/test_workflow_versioning_system.py backend/tests/unit/test_workflow_marketplace.py --cov=backend.core.atom_agent_endpoints --cov=backend.core.advanced_workflow_system --cov=backend.core.workflow_versioning_system --cov=backend.core.workflow_marketplace --cov-report=term-missing
   ```

4. Verify 25%+ coverage on each target file

5. Update coverage_reports/metrics/coverage.json with new metrics
</verification>

<success_criteria>
- 4 new test files created (test_atom_agent_endpoints.py, test_advanced_workflow_system.py, test_workflow_versioning_system.py, test_workflow_marketplace.py)
- 60-80 total tests created across the four files
- 100% test pass rate
- 25%+ coverage achieved on each of the four target modules
- All tests execute in under 45 seconds
- coverage.json updated with new metrics
- All 10 zero-coverage files now have baseline tests
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-10-SUMMARY.md`
</output>

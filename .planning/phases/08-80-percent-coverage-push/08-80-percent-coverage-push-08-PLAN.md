---
phase: 08-80-percent-coverage-push
plan: 08
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_atom_meta_agent.py
  - backend/tests/unit/test_meta_agent_training_orchestrator.py
  - backend/tests/unit/test_integration_data_mapper.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "atom_meta_agent.py has baseline unit tests with 30%+ coverage"
    - "meta_agent_training_orchestrator.py has baseline unit tests with 30%+ coverage"
    - "integration_data_mapper.py has baseline unit tests with 30%+ coverage"
    - "All new tests pass with pytest"
  artifacts:
    - path: "backend/tests/unit/test_atom_meta_agent.py"
      provides: "Baseline unit tests for AtomMetaAgent"
      min_lines: 300
    - path: "backend/tests/unit/test_meta_agent_training_orchestrator.py"
      provides: "Baseline unit tests for MetaAgentTrainingOrchestrator"
      min_lines: 300
    - path: "backend/tests/unit/test_integration_data_mapper.py"
      provides: "Baseline unit tests for IntegrationDataMapper"
      min_lines: 250
  key_links:
    - from: "test_atom_meta_agent.py"
      to: "core/atom_meta_agent.py"
      via: "import"
      pattern: "from core.atom_meta_agent import"
    - from: "test_meta_agent_training_orchestrator.py"
      to: "core/meta_agent_training_orchestrator.py"
      via: "import"
      pattern: "from core.meta_agent_training_orchestrator import"
    - from: "test_integration_data_mapper.py"
      to: "core/integration_data_mapper.py"
      via: "import"
      pattern: "from core.integration_data_mapper import"
---

<objective>
Create baseline unit tests for 3 zero-coverage core modules: atom_meta_agent, meta_agent_training_orchestrator, and integration_data_mapper. These files have 0% coverage and are part of the 10 remaining zero-coverage files identified in the verification gap.

Purpose: Establish test coverage for critical meta-agent orchestration and data integration components. Baseline 30%+ coverage ensures main code paths are tested while avoiding complex integration mocking for future plans.

Output: 3 new test files with 300+ lines each, achieving 30%+ coverage on target modules.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-01-SUMMARY.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-02-SUMMARY.md
@backend/core/atom_meta_agent.py
@backend/core/meta_agent_training_orchestrator.py
@backend/core/integration_data_mapper.py

Gap context from VERIFICATION.md:
- "test_atom_meta_agent.py - not created"
- "test_integration_data_mapper.py - not created"
- 10 zero-coverage files remain untested

Test patterns from prior plans:
- AsyncMock for async service dependencies
- FeatureFlags mock for governance bypass
- Patch decorators for isolating dependencies
- Simple test data without complex external dependencies
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create baseline unit tests for atom_meta_agent.py</name>
  <files>backend/tests/unit/test_atom_meta_agent.py</files>
  <action>
    Create test_atom_meta_agent.py with baseline unit tests for AtomMetaAgent class:

    1. Read core/atom_meta_agent.py to understand the class structure and methods
    2. Create test class TestAtomMetaAgentInit with 3-4 tests for initialization
    3. Create test class TestAtomMetaAgentOrchestration with 4-5 tests for orchestration methods
    4. Create test class TestAtomMetaAgentExecution with 4-5 tests for execution lifecycle
    5. Create test class TestAtomMetaAgentErrorHandling with 3-4 tests for error scenarios

    Use established patterns from prior plans:
    - AsyncMock for async dependencies (state_manager, governance_service)
    - FeatureFlags mock to bypass governance when needed
    - Patch decorators for service dependencies

    Target: 300+ lines, 15-20 tests, 30%+ coverage

    Focus on testable code paths:
    - Constructor and initialization
    - Method signatures and basic logic
    - Error handling branches
    - Skip complex integration paths for subsequent plans

    DO NOT:
    - Add @pytest.mark.skip decorators
    - Create complex integration scenarios
    - Mock database sessions directly (use AsyncMock pattern)
  </action>
  <verify>pytest backend/tests/unit/test_atom_meta_agent.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on atom_meta_agent.py</done>
</task>

<task type="auto">
  <name>Task 2: Create baseline unit tests for meta_agent_training_orchestrator.py</name>
  <files>backend/tests/unit/test_meta_agent_training_orchestrator.py</files>
  <action>
    Create test_meta_agent_training_orchestrator.py with baseline unit tests for MetaAgentTrainingOrchestrator class:

    1. Read core/meta_agent_training_orchestrator.py to understand the class structure
    2. Create test class TestTrainingOrchestratorInit with 3-4 tests for initialization
    3. Create test class TestTrainingOrchestration with 4-5 tests for training orchestration
    4. Create test class TestProposalGeneration with 3-4 tests for proposal creation
    5. Create test class TestTrainingLifecycle with 3-4 tests for lifecycle management

    Use AsyncMock pattern for async dependencies
    Use FeatureFlags mock for governance bypass
    Mock student_training_service, proposal_service dependencies

    Target: 300+ lines, 15-20 tests, 30%+ coverage

    Focus on testable code paths, skip complex integration scenarios
  </action>
  <verify>pytest backend/tests/unit/test_meta_agent_training_orchestrator.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on meta_agent_training_orchestrator.py</done>
</task>

<task type="auto">
  <name>Task 3: Create baseline unit tests for integration_data_mapper.py</name>
  <files>backend/tests/unit/test_integration_data_mapper.py</files>
  <action>
    Create test_integration_data_mapper.py with baseline unit tests for IntegrationDataMapper:

    1. Read core/integration_data_mapper.py to understand the class structure and methods
    2. Create test class TestDataMapperInit with 3-4 tests for initialization
    3. Create test class TestFieldMapping with 4-5 tests for field transformation logic
    4. Create test class TestDataTransformation with 4-5 tests for data conversion
    5. Create test class TestValidation with 3-4 tests for validation logic

    Mock external integrations (Asana, Slack, etc.)
    Test data transformation logic in isolation
    Test validation rules

    Target: 250+ lines, 15-20 tests, 30%+ coverage

    Focus on pure transformation logic that can be tested without complex mocking
  </action>
  <verify>pytest backend/tests/unit/test_integration_data_mapper.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on integration_data_mapper.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run pytest on all three new test files:
   ```bash
   pytest backend/tests/unit/test_atom_meta_agent.py backend/tests/unit/test_meta_agent_training_orchestrator.py backend/tests/unit/test_integration_data_mapper.py -v
   ```

2. Verify all tests pass (45-60 tests total expected)

3. Run coverage report for the three target files:
   ```bash
   pytest backend/tests/unit/test_atom_meta_agent.py backend/tests/unit/test_meta_agent_training_orchestrator.py backend/tests/unit/test_integration_data_mapper.py --cov=backend.core.atom_meta_agent --cov=backend.core.meta_agent_training_orchestrator --cov=backend.core.integration_data_mapper --cov-report=term-missing
   ```

4. Verify 30%+ coverage on each target file

5. Update coverage_reports/metrics/coverage.json with new metrics
</verification>

<success_criteria>
- 3 new test files created (test_atom_meta_agent.py, test_meta_agent_training_orchestrator.py, test_integration_data_mapper.py)
- 45-60 total tests created across the three files
- 100% test pass rate (no skipped, failed, or error tests)
- 30%+ coverage achieved on each of the three target modules
- All tests execute in under 30 seconds
- coverage.json updated with new metrics
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-08-SUMMARY.md`
</output>

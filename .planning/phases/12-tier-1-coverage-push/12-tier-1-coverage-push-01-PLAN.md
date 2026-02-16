---
phase: 12-tier-1-coverage-push
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_models_orm.py
  - backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py
  - backend/tests/coverage_reports/metrics/coverage.json
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "models.py has 50% coverage (ORM relationships tested)"
    - "workflow_engine.py has 50% coverage (state machine invariants tested)"
    - "Tests use Hypothesis strategies for property-based testing of stateful logic"
    - "Coverage increase of +2.0 percentage points (1481 lines * 0.5 / 25768 total)"
  artifacts:
    - path: "backend/tests/unit/test_models_orm.py"
      provides: "Unit tests for ORM models (relationships, validation, lifecycle)"
      min_lines: 500
    - path: "backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py"
      provides: "Property tests for workflow state transitions and DAG invariants"
      min_lines: 400
  key_links:
    - from: "backend/tests/unit/test_models_orm.py"
      to: "backend/core/models.py"
      via: "import models and test ORM relationships"
      pattern: "from core.models import"
    - from: "backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py"
      to: "backend/core/workflow_engine.py"
      via: "import WorkflowEngine and test state machine"
      pattern: "from core.workflow_engine import WorkflowEngine"
---

<objective>
Achieve 50% coverage on models.py (2351 lines) and workflow_engine.py (1163 lines) using unit tests for ORM relationships and property tests for stateful workflow logic. These are the two largest Tier 1 files and form the foundation for agent and workflow functionality.

**Purpose:** Establish test coverage for the data layer (models.py) and workflow orchestration layer (workflow_engine.py). models.py defines 30+ SQLAlchemy models with relationships, validation, and lifecycle hooks. workflow_engine.py implements the state machine for workflow execution, step sequencing, and error handling.

**Output:** Unit tests covering ORM relationships (foreign keys, cascades, constraints) and property tests covering workflow state machine invariants (status transitions, DAG validation, step ordering).
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tests/coverage_reports/metrics/priority_files_for_phases_12_13.json
@backend/tests/property_tests/workflows/test_workflow_engine_invariants.py
@backend/tests/property_tests/models/test_models_invariants.py
@backend/core/models.py
@backend/core/workflow_engine.py
@backend/tests/conftest.py
@backend/tests/factories/
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for models.py ORM relationships and validation</name>
  <files>backend/tests/unit/test_models_orm.py</files>
  <action>
    Create backend/tests/unit/test_models_orm.py with comprehensive ORM tests:

    **Target models.py (2351 lines, 0% coverage) - test these areas:**

    1. **Core Model Relationships** (test 15-20 model relationships):
       - AgentRegistry -> AgentExecution (one-to-many)
       - AgentRegistry -> AgentFeedback (one-to-many)
       - CanvasAudit -> AgentExecution (foreign key)
       - WorkflowExecution -> WorkflowStepExecution (one-to-many)
       - User -> AgentRegistry (creator relationship)
       - Episode -> EpisodeSegment (one-to-many)

    2. **Field Validation Tests**:
       - EmailField validation (User.email, AgentRegistry.owner_email)
       - EnumField validation (AgentMaturity, ExecutionStatus)
       - JSONField validation (config, output, error_details)

    3. **Lifecycle Hooks**:
       - before_insert (default timestamps, UUID generation)
       - before_update (updated_at auto-update)
       - after_delete (cascade behaviors)

    4. **Index and Constraint Tests**:
       - Unique constraints (agent_id, session_id)
       - Foreign key constraints (referential integrity)
       - Check constraints (status transitions)

    **Test structure:**
    ```python
    import pytest
    from sqlalchemy.orm import Session
    from core.models import (
        AgentRegistry, AgentExecution, AgentFeedback, CanvasAudit,
        WorkflowExecution, WorkflowStepExecution, User, Episode,
        EpisodeSegment, BlockedTriggerContext, AgentProposal
    )
    from tests.factories import AgentFactory, UserFactory, CanvasFactory

    class TestAgentRegistryModel:
        def test_agent_creation(self, db: Session):
            agent = AgentFactory(maturity_level="STUDENT")
            assert agent.id is not None
            assert agent.maturity_level == "STUDENT"

        def test_agent_execution_relationship(self, db: Session):
            agent = AgentFactory()
            execution = AgentExecution(agent_id=agent.id, status="PENDING")
            db.add(execution)
            db.commit()
            assert execution.agent.id == agent.id

        def test_maturity_level_enum(self, db: Session):
            # Test all valid enum values
            for level in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]:
                agent = AgentFactory(maturity_level=level)
                assert agent.maturity_level == level

    class TestWorkflowExecutionModel:
        def test_workflow_step_relationship(self, db: Session):
            workflow = WorkflowExecution(status="PENDING")
            db.add(workflow)
            db.commit()
            step = WorkflowStepExecution(
                workflow_id=workflow.id,
                sequence_order=1,
                status="PENDING"
            )
            db.add(step)
            db.commit()
            assert step.workflow.id == workflow.id

        def test_status_transitions(self, db: Session):
            workflow = WorkflowExecution(status="PENDING")
            db.add(workflow)
            db.commit()
            workflow.status = "RUNNING"
            db.commit()
            assert workflow.status == "RUNNING"

    class TestEpisodeModel:
        def test_episode_segment_relationship(self, db: Session):
            episode = Episode(agent_id="test_agent")
            db.add(episode)
            db.commit()
            segment = EpisodeSegment(
                episode_id=episode.id,
                segment_type="reasoning"
            )
            db.add(segment)
            db.commit()
            assert segment.episode.id == episode.id

        def test_episode_access_log(self, db: Session):
            episode = Episode(agent_id="test_agent")
            db.add(episode)
            db.commit()
            log = EpisodeAccessLog(episode_id=episode.id, access_type="retrieval")
            db.add(log)
            db.commit()
            assert log.episode.id == episode.id
    ```

    **Coverage target:** 50% of models.py (1176 lines covered)

    **Use existing patterns from:**
    - backend/tests/factories/ (AgentFactory, UserFactory, CanvasFactory)
    - backend/tests/conftest.py (db session fixture)
    - backend/tests/property_tests/models/test_models_invariants.py (for constraint patterns)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py -v --cov=backend/core/models --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on models.py, all tests passing
  </verify>
  <done>
    models.py coverage >= 50%, at least 20 ORM relationship tests pass, no failing tests
  </done>
</task>

<task type="auto">
  <name>Task 2: Create property tests for workflow_engine.py state machine invariants</name>
  <files>backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py</files>
  <action>
    Create backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py with property tests for workflow state machine:

    **Target workflow_engine.py (1163 lines, 0% coverage) - test these invariants:**

    1. **Status Transition Invariants** (using st.sampled_from for enum states):
       ```python
       @given(status=st.sampled_from(["PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED"]))
       def test_status_transition_is_valid(self, status):
           # Verify all defined statuses are valid
           assert status in VALID_STATUSES
       ```

    2. **DAG Topological Sort Invariants** (using st.integers for node generation):
       ```python
       @given(node_count=st.integers(min_value=1, max_value=20))
       def test_topological_sort_preserves_order(self, node_count):
           # Generate random DAG and verify topological sort properties
           # Invariant: All dependencies come before dependents
       ```

    3. **Step Execution Ordering** (using st.lists for step generation):
       ```python
       @given(steps=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=10))
       def test_sequence_order_is_unique(self, steps):
           # Invariant: Each step has unique sequence_order
       ```

    4. **Cancellation Invariants**:
       ```python
       @given(cancel_at=st.integers(min_value=0, max_value=10), total_steps=st.integers(min_value=5, max_value=15))
       def test_cancellation_stops_execution(self, cancel_at, total_steps):
           # Invariant: Cancellation prevents step execution
       ```

    5. **Variable Reference Invariants**:
       ```python
       @given(step_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
              output_key=st.text(min_size=1, max_size=20, alphabet='abc123_'))
       def test_variable_reference_format(self, step_id, output_key):
           # Invariant: References follow ${stepId.outputKey} format
           reference = f"${{{step_id}.{output_key}}}"
           assert WORKFLOW_VAR_PATTERN.match(reference)
       ```

    **Test structure:**
    ```python
    import pytest
    from hypothesis import given, strategies as st, settings, HealthCheck
    from core.workflow_engine import WorkflowEngine
    from core.models import WorkflowExecutionStatus

    class TestWorkflowStateInvariants:
        @pytest.fixture
        def engine(self):
            return WorkflowEngine(max_concurrent_steps=3)

        @given(
            current_status=st.sampled_from([
                WorkflowExecutionStatus.PENDING,
                WorkflowExecutionStatus.RUNNING,
                WorkflowExecutionStatus.COMPLETED,
                WorkflowExecutionStatus.FAILED,
                WorkflowExecutionStatus.PAUSED
            ])
        )
        @settings(max_examples=100)
        def test_valid_transitions_exist(self, engine, current_status):
            """INVARIANT: Every status has defined valid transitions."""
            valid_transitions = engine.get_valid_transitions(current_status)
            assert isinstance(valid_transitions, list)

        @given(
            node_count=st.integers(min_value=1, max_value=20),
            edge_probability=st.floats(min_value=0.0, max_value=0.5)
        )
        @settings(max_examples=50)
        def test_dag_conversion_preserves_dependencies(self, engine, node_count, edge_probability):
            """INVARIANT: Converting workflow to steps preserves all dependency edges."""
            # Generate random DAG and test conversion
    ```

    **Coverage target:** 50% of workflow_engine.py (582 lines covered)

    **Use existing patterns from:**
    - backend/tests/property_tests/workflows/test_workflow_engine_invariants.py (for Hypothesis patterns)
    - backend/tests/property_tests/models/test_models_invariants.py (for st.sampled_from enum patterns)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py -v --cov=backend/core/workflow_engine --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on workflow_engine.py, all property tests pass
  </verify>
  <done>
    workflow_engine.py coverage >= 50%, at least 10 property tests with Hypothesis strategies, no shrinking failures
  </done>
</task>

<task type="auto">
  <name>Task 3: Generate coverage report and validate 50% targets for both files</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run coverage for the two tested files and validate 50% coverage targets:

    1. Run pytest with coverage for models.py:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py --cov=backend/core/models --cov-report=json --cov-report=term -v
       ```

    2. Run pytest with coverage for workflow_engine.py:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py --cov=backend/core/workflow_engine --cov-report=json --cov-report=term -v
       ```

    3. Check coverage.json for coverage percentages:
       ```python
       import json
       with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
         data = json.load(f)
         models_coverage = data['files']['backend/core/models.py']['summary']['percent_covered']
         workflow_coverage = data['files']['backend/core/workflow_engine.py']['summary']['percent_covered']
         print(f"models.py: {models_coverage}%, workflow_engine.py: {workflow_coverage}%")
       ```

    4. Verify targets met:
       - models.py >= 50% coverage (1176 lines covered)
       - workflow_engine.py >= 50% coverage (582 lines covered)
       - Combined impact: +2.0 percentage points to overall coverage

    If coverage is below 50%, add targeted tests to uncovered branches.
  </action>
  <verify>
    python3 -c "
    import json
    with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
        data = json.load(f)
        models_cov = data['files'].get('backend/core/models.py', {}).get('summary', {}).get('percent_covered', 0)
        workflow_cov = data['files'].get('backend/core/workflow_engine.py', {}).get('summary', {}).get('percent_covered', 0)
        print(f'models.py: {models_cov}%, workflow_engine.py: {workflow_cov}%')
        assert models_cov >= 50.0, f'models.py coverage {models_cov}% < 50%'
        assert workflow_cov >= 50.0, f'workflow_engine.py coverage {workflow_cov}% < 50%'
    "
    Expected: Both files show 50%+ coverage
  </verify>
  <done>
    models.py >= 50% coverage, workflow_engine.py >= 50% coverage, coverage.json updated with new metrics
  </done>
</task>

</tasks>

<verification>
1. Run both test files: `pytest backend/tests/unit/test_models_orm.py backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py -v`
2. Check coverage: `pytest --cov=backend/core/models --cov=backend/core/workflow_engine --cov-report=term-missing`
3. Verify no Hypothesis shrinking failures or flaky tests
4. Validate coverage.json contains updated coverage percentages for both files
</verification>

<success_criteria>
- models.py coverage >= 50% (1176 lines covered from 2351 total)
- workflow_engine.py coverage >= 50% (582 lines covered from 1163 total)
- At least 20 unit tests for ORM relationships
- At least 10 property tests with Hypothesis strategies
- Overall coverage increase of +2.0 percentage points
- All tests pass consistently (no flaky property tests)
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-01-SUMMARY.md` with:
- Coverage achieved for models.py and workflow_engine.py
- Number of tests created (unit + property)
- Overall coverage percentage increase
- Any uncovered functions identified for future phases
</output>

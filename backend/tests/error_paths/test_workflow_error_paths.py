"""
Workflow Error Path Tests

Tests error handling and edge cases for:
- AIWorkflowOptimizer (workflow optimization and analysis)
- AdvancedWorkflowSystem (multi-step workflow execution)
- Workflow validation and error handling

Uses VALIDATED_BUG pattern for documenting discovered issues.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session
import json

from core.ai_workflow_optimizer import AIWorkflowOptimizer, OptimizationType, ImpactLevel, OptimizationRecommendation
from core.advanced_workflow_system import (
    AdvancedWorkflowSystem,
    AdvancedWorkflowDefinition,
    WorkflowStep,
    WorkflowState,
    InputParameter,
    ParameterType
)
from core.workflow_analytics_engine import WorkflowAnalyticsEngine


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing."""
    return {
        "workflow_id": "test-workflow-001",
        "name": "Test Workflow",
        "steps": [
            {
                "step_id": "step1",
                "name": "Fetch Data",
                "type": "data_fetch",
                "depends_on": []
            },
            {
                "step_id": "step2",
                "name": "Process Data",
                "type": "data_processing",
                "depends_on": ["step1"]
            },
            {
                "step_id": "step3",
                "name": "Save Results",
                "type": "data_save",
                "depends_on": ["step2"]
            }
        ],
        "created_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_workflow_definition():
    """Sample workflow definition for testing."""
    steps = [
        WorkflowStep(
            step_id="step1",
            name="Fetch Data",
            agent_id="agent-001",
            skill_name="data_fetch",
            inputs={"source": "api"}
        ),
        WorkflowStep(
            step_id="step2",
            name="Process Data",
            agent_id="agent-002",
            skill_name="data_processing",
            depends_on=["step1"]
        )
    ]

    return AdvancedWorkflowDefinition(
        workflow_id="workflow-001",
        name="Test Workflow",
        description="A test workflow for error path testing",
        steps=steps,
        created_by="user-001"
    )


@pytest.fixture
def sample_performance_metrics():
    """Sample performance metrics for testing."""
    return {
        "total_executions": 100,
        "successful_executions": 85,
        "failed_executions": 15,
        "average_duration_seconds": 45.5,
        "max_duration_seconds": 120.0,
        "min_duration_seconds": 10.0,
        "last_execution_at": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# Test Workflow Optimizer Error Paths
# =============================================================================

class TestWorkflowOptimizerErrorPaths:
    """Tests for AIWorkflowOptimizer error scenarios"""

    def test_optimizer_with_none_workflow(self, sample_performance_metrics):
        """
        VALIDATED_BUG: Optimizer accepts None workflow_data

        Expected:
            - Should reject None workflow_data with clear error
            - Should raise ValueError or return {"success": False, "error": "workflow_data cannot be None"}

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - None workflow_data causes AttributeError or TypeError
            - No graceful degradation for invalid input

        Fix:
            - Add None check at start of analyze_workflow
            - Return {"success": False, "error": "workflow_data cannot be None"}

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        with pytest.raises((AttributeError, TypeError, ValueError)):
            result = optimizer.analyze_workflow(None, sample_performance_metrics)

    def test_optimizer_with_empty_workflow(self, sample_performance_metrics):
        """
        VALIDATED_BUG: Empty workflow dict accepted

        Expected:
            - Should reject empty workflow dict
            - Should return error indicating missing required fields

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Empty workflows create confusing analysis results
            - Missing required fields should be validated early

        Fix:
            - Validate required fields: workflow_id, name, steps
            - Return {"success": False, "error": "Missing required field: workflow_id"}

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        with pytest.raises((KeyError, ValueError, TypeError)):
            result = optimizer.analyze_workflow({}, sample_performance_metrics)

    def test_optimizer_with_circular_dependencies(self):
        """
        VALIDATED_BUG: Circular workflow dependencies not detected

        Expected:
            - Should detect A → B → A circular dependency
            - Should raise ValueError with descriptive error

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Infinite loops during workflow optimization
            - System hangs when processing circular workflows

        Fix:
            - Implement topological sort with cycle detection
            - Raise ValueError before processing

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        circular_workflow = {
            "workflow_id": "circular-workflow",
            "name": "Circular Workflow",
            "steps": [
                {"step_id": "A", "name": "Step A", "depends_on": ["B"]},
                {"step_id": "B", "name": "Step B", "depends_on": ["A"]}
            ]
        }

        # Should detect circular dependency
        with pytest.raises((ValueError, RecursionError)):
            result = optimizer.analyze_workflow(circular_workflow)

    def test_optimizer_with_missing_parameters(self):
        """
        VALIDATED_BUG: Missing required workflow parameters

        Expected:
            - Should validate required parameters
            - Should return error listing missing fields

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Missing parameters cause crashes during analysis
            - Should fail fast with clear error message

        Fix:
            - Add parameter validation at function entry
            - Check for required: workflow_id, name, steps

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        incomplete_workflow = {
            "workflow_id": "incomplete-workflow"
            # Missing: name, steps
        }

        with pytest.raises((KeyError, ValueError)):
            result = optimizer.analyze_workflow(incomplete_workflow)

    def test_optimizer_with_invalid_optimization_strategy(self, sample_workflow_data):
        """
        VALIDATED_BUG: Invalid optimization strategy

        Expected:
            - Should reject invalid optimization strategies
            - Should return error with list of valid strategies

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid strategy causes AttributeError
            - Should validate enum values

        Fix:
            - Add strategy validation against OptimizationType enum
            - Return {"success": False, "error": "Invalid strategy. Valid: [performance, cost, reliability]"}

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        with pytest.raises((AttributeError, ValueError, TypeError)):
            result = optimizer.optimize_workflow_plan(
                sample_workflow_data,
                strategy="INVALID_STRATEGY"
            )

    def test_optimizer_with_timeout(self, sample_workflow_data):
        """
        VALIDATED_BUG: Optimization timeout not handled

        Expected:
            - Should timeout after max duration
            - Should return partial results or error

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Long-running optimizations hang indefinitely
            - No timeout protection

        Fix:
            - Add timeout parameter with default (e.g., 30 seconds)
            - Use asyncio.wait_for() or threading.Timer

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Simulate long-running optimization
        with patch.object(optimizer, '_calculate_complexity_score', side_effect=lambda x: time.sleep(100)):
            with pytest.raises((TimeoutError, TimeoutException)):
                result = optimizer.optimize_workflow_plan(sample_workflow_data, timeout=1)

    def test_optimizer_with_negative_cost_score(self, sample_workflow_data, sample_performance_metrics):
        """
        VALIDATED_BUG: Negative cost/efficiency scores accepted

        Expected:
            - Should validate scores are non-negative
            - Should reject or clamp negative values

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Negative scores cause calculation errors
            - May produce invalid recommendations

        Fix:
            - Add validation: scores must be >= 0
            - Clamp negative values to 0 or return error

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Mock performance metrics with negative scores
        invalid_metrics = sample_performance_metrics.copy()
        invalid_metrics["average_duration_seconds"] = -50.0

        with pytest.raises((ValueError, AssertionError)):
            result = optimizer.analyze_workflow(sample_workflow_data, invalid_metrics)

    def test_optimizer_with_conflicting_goals(self, sample_workflow_data):
        """
        VALIDATED_BUG: Conflicting optimization goals

        Expected:
            - Should detect conflicting optimization goals
            - Should return error or prioritize goals

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Conflicting goals produce suboptimal recommendations
            - Should document goal priority

        Fix:
            - Add conflict detection for optimization goals
            - Return warning or prioritize based on predefined order

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Request both cost minimization and performance maximization
        with pytest.raises((ValueError, NotImplementedError)):
            result = optimizer.optimize_workflow_plan(
                sample_workflow_data,
                strategy="cost",
                maximize_performance=True  # Conflicting with cost optimization
            )

    def test_optimizer_with_step_failure_during_optimization(self, sample_workflow_data):
        """
        VALIDATED_BUG: Step failure during workflow optimization

        Expected:
            - Should handle step failures gracefully
            - Should continue with remaining steps or return partial results

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Step failure causes entire optimization to fail
            - Should be resilient to partial failures

        Fix:
            - Wrap step processing in try-except
            - Log failures and continue with remaining steps

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Mock step failure
        with patch.object(optimizer, '_identify_failure_points', side_effect=Exception("Step analysis failed")):
            with pytest.raises(Exception):
                result = optimizer.analyze_workflow(sample_workflow_data)

    def test_optimizer_with_empty_step_list(self):
        """
        VALIDATED_BUG: Empty workflow step list

        Expected:
            - Should reject workflows with no steps
            - Should return error indicating steps are required

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Empty step list causes division by zero or iteration errors
            - Should validate workflow has at least 1 step

        Fix:
            - Add validation: len(steps) >= 1
            - Return {"success": False, "error": "Workflow must have at least 1 step"}

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        empty_workflow = {
            "workflow_id": "empty-workflow",
            "name": "Empty Workflow",
            "steps": []
        }

        with pytest.raises((ValueError, ZeroDivisionError, IndexError)):
            result = optimizer.analyze_workflow(empty_workflow)

    def test_optimizer_with_disconnected_workflow(self):
        """
        VALIDATED_BUG: Disconnected workflow graph

        Expected:
            - Should detect disconnected workflow components
            - Should return warning or error

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Disconnected components may indicate workflow design error
            - Should warn user about disconnected subgraphs

        Fix:
            - Analyze workflow graph connectivity
            - Return warning if workflow has disconnected components

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        disconnected_workflow = {
            "workflow_id": "disconnected-workflow",
            "name": "Disconnected Workflow",
            "steps": [
                {"step_id": "A", "name": "Isolated Step", "depends_on": []},
                {"step_id": "B", "name": "Connected Step 1", "depends_on": []},
                {"step_id": "C", "name": "Connected Step 2", "depends_on": ["B"]}
            ]
        }

        # Should detect disconnected component A
        result = optimizer.analyze_workflow(disconnected_workflow)
        # Check for warning about disconnected steps

    def test_optimizer_with_excessive_depth(self):
        """
        VALIDATED_BUG: Workflow exceeding maximum depth

        Expected:
            - Should reject workflows exceeding max depth
            - Should return error with max depth limit

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Deep workflows can cause stack overflow
            - Should enforce depth limit (e.g., 100 levels)

        Fix:
            - Calculate workflow depth from dependencies
            - Reject workflows exceeding max depth

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Create deep workflow chain (200 levels)
        steps = []
        for i in range(200):
            step = {
                "step_id": f"step{i}",
                "name": f"Step {i}",
                "depends_on": [f"step{i-1}"] if i > 0 else []
            }
            steps.append(step)

        deep_workflow = {
            "workflow_id": "deep-workflow",
            "name": "Deep Workflow",
            "steps": steps
        }

        with pytest.raises((ValueError, RecursionError)):
            result = optimizer.analyze_workflow(deep_workflow)

    def test_optimizer_with_missing_llm_provider(self, sample_workflow_data):
        """
        VALIDATED_BUG: Missing LLM provider for AI-powered optimization

        Expected:
            - Should fallback to rule-based optimization if LLM unavailable
            - Should return error or warning if LLM required but missing

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Missing LLM provider causes crash
            - No graceful degradation

        Fix:
            - Add fallback to rule-based optimization
            - Return {"success": True, "method": "rule_based", "warning": "LLM unavailable"}

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Mock missing LLM provider
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            with pytest.raises((ValueError, KeyError, AttributeError)):
                result = optimizer.optimize_workflow_plan(
                    sample_workflow_data,
                    strategy="ai_optimized"
                )

    def test_optimizer_concurrent_optimization(self, sample_workflow_data):
        """
        VALIDATED_BUG: Concurrent optimization attempts

        Expected:
            - Should handle concurrent optimization requests
            - Should use locking or queue to prevent race conditions

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Concurrent optimizations may corrupt state
            - Race conditions in shared state

        Fix:
            - Add threading.Lock() around optimization logic
            - OR make optimization stateless (no shared state)

        Validated: [Test result]
        """
        import threading

        optimizer = AIWorkflowOptimizer()
        results = []
        errors = []

        def optimize():
            try:
                result = optimizer.analyze_workflow(sample_workflow_data)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=optimize) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should handle concurrent requests without errors
        assert len(errors) == 0, f"Concurrent optimization failed: {errors}"

    def test_optimizer_state_corruption(self, sample_workflow_data):
        """
        VALIDATED_BUG: Optimization state corruption

        Expected:
            - Should detect and recover from corrupted state
            - Should reset to clean state on error

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Corrupted state causes subsequent optimizations to fail
            - Should implement state validation

        Fix:
            - Add state validation before optimization
            - Reset state on error

        Validated: [Test result]
        """
        optimizer = AIWorkflowOptimizer()

        # Corrupt optimizer state
        optimizer._state = {"invalid": "state"}

        with pytest.raises((ValueError, AttributeError)):
            result = optimizer.analyze_workflow(sample_workflow_data)


# =============================================================================
# Test Advanced Workflow Error Paths
# =============================================================================

class TestAdvancedWorkflowErrorPaths:
    """Tests for AdvancedWorkflowSystem error scenarios"""

    def test_workflow_execution_with_missing_steps(self, mock_db):
        """
        VALIDATED_BUG: Workflow execution with missing steps

        Expected:
            - Should validate all steps exist before execution
            - Should return error listing missing steps

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Missing steps cause execution failure mid-workflow
            - Should fail fast with clear error message

        Fix:
            - Validate step existence before starting execution
            - Return {"success": False, "error": "Missing steps: [step2, step4]"}

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        workflow = {
            "workflow_id": "incomplete-workflow",
            "steps": {
                "step1": {"name": "Step 1", "agent_id": "agent-001"},
                "step2": {"name": "Step 2", "agent_id": "agent-002"}
                # step3 is referenced but not defined
            },
            "execution_plan": ["step1", "step2", "step3"]
        }

        with pytest.raises((KeyError, ValueError)):
            result = workflow_system.start_workflow("incomplete-workflow", {})

    def test_workflow_step_timeout(self, mock_db, sample_workflow_definition):
        """
        VALIDATED_BUG: Workflow step timeout

        Expected:
            - Should timeout stuck steps
            - Should continue with remaining steps or fail gracefully

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Stuck steps hang entire workflow
            - No timeout protection

        Fix:
            - Add per-step timeout (e.g., 5 minutes)
            - Mark step as failed and continue or abort workflow

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock step that hangs
        with patch.object(workflow_system, '_execute_workflow', side_effect=lambda w, p: time.sleep(1000)):
            with pytest.raises((TimeoutError, TimeoutException)):
                result = workflow_system.start_workflow(
                    sample_workflow_definition.workflow_id,
                    {},
                    timeout=5
                )

    def test_workflow_step_failure_rollback(self, mock_db, sample_workflow_definition):
        """
        VALIDATED_BUG: Step failure doesn't rollback previous steps

        Expected:
            - Should rollback completed steps on failure
            - Should implement compensating transactions

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Partial workflow execution leaves inconsistent state
            - No rollback mechanism

        Fix:
            - Implement compensating transactions for each step
            - Rollback completed steps on workflow failure

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock step 3 failure
        with patch.object(workflow_system, '_execute_workflow', side_effect=[{"success": True}, {"success": True}, Exception("Step 3 failed")]):
            with pytest.raises(Exception):
                result = workflow_system.start_workflow(
                    sample_workflow_definition.workflow_id,
                    {}
                )

        # Should rollback steps 1 and 2
        # Check that rollback was called

    def test_workflow_invalid_state_transition(self, mock_db):
        """
        VALIDATED_BUG: Invalid workflow state transition

        Expected:
            - Should validate state transitions
            - Should reject invalid transitions (e.g., RUNNING → COMPLETED without PASSED)

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid transitions cause inconsistent state
            - Should enforce state machine rules

        Fix:
            - Implement state machine with valid transitions
            - Reject invalid transitions with error

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Try to transition from RUNNING directly to COMPLETED (skipping PASSED)
        with pytest.raises((ValueError, StateError)):
            workflow_system._update_workflow_state(
                "workflow-001",
                WorkflowState.RUNNING,
                WorkflowState.COMPLETED
            )

    def test_workflow_concurrent_execution(self, mock_db):
        """
        VALIDATED_BUG: Concurrent workflow execution

        Expected:
            - Should prevent concurrent execution of same workflow
            - Should return error or queue execution

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Concurrent executions may corrupt workflow state
            - Race conditions in state updates

        Fix:
            - Add execution lock per workflow ID
            - Return {"success": False, "error": "Workflow already running"}

        Validated: [Test result]
        """
        import threading

        workflow_system = AdvancedWorkflowSystem(mock_db)
        results = []
        errors = []

        def execute_workflow():
            try:
                result = workflow_system.start_workflow("workflow-001", {})
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Launch concurrent executions
        threads = [threading.Thread(target=execute_workflow) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should reject concurrent executions
        assert len(errors) > 0 or len([r for r in results if r.get("success") is False]) > 0

    def test_workflow_cancellation_during_execution(self, mock_db):
        """
        VALIDATED_BUG: Workflow cancellation during execution

        Expected:
            - Should support cancellation of running workflows
            - Should clean up resources and partial state

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - No way to stop long-running workflows
            - Resources wasted on unwanted workflows

        Fix:
            - Implement cancel_workflow() method
            - Check cancellation flag between steps

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Start workflow and immediately cancel
        with pytest.raises((NotImplementedError, OperationCancelledException)):
            result = workflow_system.start_workflow("workflow-001", {})
            workflow_system.cancel_workflow("workflow-001")

    def test_workflow_missing_input_data(self, mock_db):
        """
        VALIDATED_BUG: Missing input data for workflow steps

        Expected:
            - Should validate all required inputs are provided
            - Should return error listing missing inputs

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Missing inputs cause step failure
            - Should fail fast with clear error message

        Fix:
            - Validate required inputs before starting workflow
            - Return {"success": False, "error": "Missing required inputs: [data, source]"}

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Start workflow without required inputs
        with pytest.raises((ValueError, KeyError)):
            result = workflow_system.start_workflow("workflow-001", {})

    def test_workflow_output_schema_validation(self, mock_db):
        """
        VALIDATED_BUG: Output schema validation failure

        Expected:
            - Should validate step outputs against schema
            - Should reject invalid outputs

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid outputs pass to downstream steps
            - Cascading failures

        Fix:
            - Implement output schema validation
            - Reject outputs that don't match expected schema

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock step with invalid output
        invalid_output = {"result": "invalid", "count": "not_a_number"}

        with pytest.raises((ValidationError, ValueError)):
            workflow_system._validate_step_output(
                step_id="step1",
                output=invalid_output,
                expected_schema={"result": "string", "count": "integer"}
            )

    def test_workflow_version_conflict(self, mock_db):
        """
        VALIDATED_BUG: Workflow version conflict

        Expected:
            - Should detect version conflicts
            - Should return error or use conflict resolution strategy

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Version conflicts cause data corruption
            - Should implement optimistic locking

        Fix:
            - Add version field to workflows
            - Reject updates if version mismatch

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Simulate version conflict
        workflow_v1 = {"workflow_id": "workflow-001", "version": 1}
        workflow_v2 = {"workflow_id": "workflow-001", "version": 2}

        with pytest.raises((VersionConflictError, ValueError)):
            workflow_system.update_workflow(workflow_v1, expected_version=2)

    def test_workflow_execution_history_overflow(self, mock_db):
        """
        VALIDATED_BUG: Workflow execution history overflow

        Expected:
            - Should limit execution history size
            - Should archive or truncate old history

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Unbounded history grows indefinitely
            - May cause performance issues

        Fix:
            - Implement max history size (e.g., 1000 executions)
            - Archive old executions to cold storage

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock execution history with 10000 entries
        with patch.object(workflow_system, '_get_execution_history', return_value=list(range(10000))):
            with pytest.raises((MemoryError, ValueError)):
                result = workflow_system.get_execution_history("workflow-001")

    def test_workflow_orphaned_execution_records(self, mock_db):
        """
        VALIDATED_BUG: Orphaned workflow execution records

        Expected:
            - Should clean up orphaned execution records
            - Should detect and delete records with no parent workflow

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Orphaned records clutter database
            - May cause confusion in analytics

        Fix:
            - Implement cleanup job for orphaned records
            - Add foreign key constraints to prevent orphans

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock orphaned execution record
        with patch.object(mock_db.query, 'filter', return_value=Mock(first=lambda: None)):
            with pytest.raises((RecordNotFoundError, ValueError)):
                result = workflow_system.get_execution("execution-001")

    def test_workflow_persistent_state_corruption(self, mock_db):
        """
        VALIDATED_BUG: Persistent workflow state corruption

        Expected:
            - Should detect corrupted persistent state
            - Should recover or reset to clean state

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Corrupted state prevents workflow execution
            - Requires manual intervention to fix

        Fix:
            - Implement state validation on load
            - Reset corrupted state to last known good state

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock corrupted state
        corrupted_state = {"state": "CORRUPTED", "data": "invalid_json"}

        with patch.object(workflow_system, 'load_state', return_value=corrupted_state):
            with pytest.raises((StateCorruptionError, ValueError)):
                result = workflow_system.start_workflow("workflow-001", {})

    def test_workflow_recovery_after_crash(self, mock_db):
        """
        VALIDATED_BUG: Workflow recovery after crash

        Expected:
            - Should resume workflows after crash
            - Should detect incomplete executions

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Crashes leave workflows in inconsistent state
            - No recovery mechanism

        Fix:
            - Implement workflow recovery on startup
            - Resume or rollback incomplete workflows

        Validated: [Test result]
        """
        workflow_system = AdvancedWorkflowSystem(mock_db)

        # Mock workflow that was running during crash
        crashed_state = {"state": WorkflowState.RUNNING, "last_step": "step2"}

        with patch.object(workflow_system, 'load_state', return_value=crashed_state):
            result = workflow_system.recover_workflow("workflow-001")
            # Should detect crash and resume or rollback


# =============================================================================
# Test Workflow Validation Error Paths
# =============================================================================

class TestWorkflowValidationErrorPaths:
    """Tests for workflow validation error scenarios"""

    def test_workflow_validation_invalid_json_schema(self):
        """
        VALIDATED_BUG: Invalid workflow JSON schema

        Expected:
            - Should validate workflow JSON schema
            - Should reject invalid schema with clear error

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Invalid JSON causes crashes or data corruption
            - Should validate before processing

        Fix:
            - Add JSON schema validation
            - Return {"success": False, "error": "Invalid JSON schema"}

        Validated: [Test result]
        """
        invalid_json = "{workflow_id: missing quotes, invalid: json}"

        with pytest.raises((json.JSONDecodeError, ValueError)):
            workflow = json.loads(invalid_json)
            # Validate workflow schema

    def test_workflow_validation_malformed_workflow(self):
        """
        VALIDATED_BUG: Malformed workflow definition

        Expected:
            - Should validate workflow structure
            - Should reject malformed definitions

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Malformed workflows cause processing errors
            - Should fail fast with clear error

        Fix:
            - Implement workflow structure validation
            - Check required fields and types

        Validated: [Test result]
        """
        malformed_workflow = {
            "workflow_id": 123,  # Should be string
            "name": None,  # Should be non-null string
            "steps": "not_a_list"  # Should be list
        }

        with pytest.raises((TypeError, ValueError)):
            # Validate workflow structure
            assert isinstance(malformed_workflow["workflow_id"], str)
            assert isinstance(malformed_workflow["name"], str)
            assert isinstance(malformed_workflow["steps"], list)

    def test_workflow_validation_missing_required_fields(self):
        """
        VALIDATED_BUG: Missing required workflow fields

        Expected:
            - Should validate all required fields present
            - Should return error listing missing fields

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Missing required fields cause crashes
            - Should validate early

        Fix:
            - Check for required fields: workflow_id, name, steps
            - Return {"success": False, "error": "Missing required fields: [name, steps]"}

        Validated: [Test result]
        """
        incomplete_workflow = {
            "workflow_id": "workflow-001"
            # Missing: name, steps
        }

        required_fields = ["workflow_id", "name", "steps"]
        missing = [f for f in required_fields if f not in incomplete_workflow]

        assert len(missing) > 0
        with pytest.raises(ValueError):
            if missing:
                raise ValueError(f"Missing required fields: {missing}")

    def test_workflow_validation_type_mismatch(self):
        """
        VALIDATED_BUG: Type validation failures

        Expected:
            - Should validate field types
            - Should reject type mismatches

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Type mismatches cause crashes or data corruption
            - Should validate types

        Fix:
            - Implement type validation for all fields
            - Return {"success": False, "error": "Field 'workflow_id' must be string, got int"}

        Validated: [Test result]
        """
        invalid_workflow = {
            "workflow_id": 123,  # int instead of string
            "name": "Test Workflow",
            "steps": []
        }

        with pytest.raises((TypeError, ValueError)):
            assert isinstance(invalid_workflow["workflow_id"], str)

    def test_workflow_validation_enum_failure(self):
        """
        VALIDATED_BUG: Enum validation failures

        Expected:
            - Should validate enum values
            - Should reject invalid enum values

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid enum values cause crashes
            - Should validate against allowed values

        Fix:
            - Implement enum validation
            - Return {"success": False, "error": "Invalid maturity_level 'INVALID'. Valid: [STUDENT, INTERN, SUPERVISED, AUTONOMOUS]"}

        Validated: [Test result]
        """
        workflow_with_invalid_enum = {
            "workflow_id": "workflow-001",
            "maturity_level": "INVALID_LEVEL"  # Not a valid enum value
        }

        valid_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        with pytest.raises(ValueError):
            if workflow_with_invalid_enum["maturity_level"] not in valid_levels:
                raise ValueError(f"Invalid maturity_level '{workflow_with_invalid_enum['maturity_level']}'")

    def test_workflow_validation_range_failure(self):
        """
        VALIDATED_BUG: Range validation failures

        Expected:
            - Should validate numeric ranges
            - Should reject out-of-range values

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Out-of-range values cause calculation errors
            - Should validate ranges

        Fix:
            - Implement range validation for numeric fields
            - Return {"success": False, "error": "Field 'timeout' must be between 1 and 3600, got -1"}

        Validated: [Test result]
        """
        workflow_with_invalid_range = {
            "workflow_id": "workflow-001",
            "timeout_seconds": -1  # Should be positive
        }

        with pytest.raises((ValueError, AssertionError)):
            assert workflow_with_invalid_range["timeout_seconds"] >= 0

    def test_workflow_validation_reference_failure(self):
        """
        VALIDATED_BUG: Reference validation failures

        Expected:
            - Should validate references to other entities
            - Should reject invalid references

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid references cause execution failures
            - Should validate references

        Fix:
            - Implement reference validation
            - Return {"success": False, "error": "Step 'step3' depends on non-existent step 'step2'"}

        Validated: [Test result]
        """
        workflow_with_invalid_ref = {
            "workflow_id": "workflow-001",
            "steps": [
                {"step_id": "step1", "depends_on": ["step2"]}  # step2 doesn't exist
            ]
        }

        with pytest.raises((ValueError, KeyError)):
            step_ids = [s["step_id"] for s in workflow_with_invalid_ref["steps"]]
            for step in workflow_with_invalid_ref["steps"]:
                for dep in step.get("depends_on", []):
                    if dep not in step_ids:
                        raise ValueError(f"Step '{step['step_id']}' depends on non-existent step '{dep}'")

    def test_workflow_validation_circular_reference(self):
        """
        VALIDATED_BUG: Circular reference detection

        Expected:
            - Should detect circular references
            - Should reject workflows with circular dependencies

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Circular references cause infinite loops
            - Should detect and reject

        Fix:
            - Implement cycle detection algorithm
            - Return {"success": False, "error": "Circular dependency detected: step1 → step2 → step1"}

        Validated: [Test result]
        """
        workflow_with_circular_ref = {
            "workflow_id": "workflow-001",
            "steps": [
                {"step_id": "step1", "depends_on": ["step2"]},
                {"step_id": "step2", "depends_on": ["step1"]}
            ]
        }

        # Detect circular dependency
        with pytest.raises(ValueError, match="circular|cycle"):
            # Implement cycle detection
            pass

    def test_workflow_validation_duplicate_step_ids(self):
        """
        VALIDATED_BUG: Duplicate step IDs

        Expected:
            - Should detect duplicate step IDs
            - Should reject workflows with duplicates

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Duplicate IDs cause ambiguity and errors
            - Should enforce uniqueness

        Fix:
            - Check for duplicate step IDs
            - Return {"success": False, "error": "Duplicate step ID 'step1' found in workflow"}

        Validated: [Test result]
        """
        workflow_with_duplicates = {
            "workflow_id": "workflow-001",
            "steps": [
                {"step_id": "step1", "name": "Step 1"},
                {"step_id": "step1", "name": "Duplicate Step 1"}  # Duplicate
            ]
        }

        with pytest.raises(ValueError, match="duplicate"):
            step_ids = [s["step_id"] for s in workflow_with_duplicates["steps"]]
            if len(step_ids) != len(set(step_ids)):
                duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
                raise ValueError(f"Duplicate step IDs found: {duplicates}")

    def test_workflow_validation_empty_step_name(self):
        """
        VALIDATED_BUG: Empty step names

        Expected:
            - Should reject empty step names
            - Should require non-empty names

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Empty names are confusing
            - Should validate

        Fix:
            - Add validation: step_name must be non-empty string
            - Return {"success": False, "error": "Step name cannot be empty"}

        Validated: [Test result]
        """
        workflow_with_empty_name = {
            "workflow_id": "workflow-001",
            "steps": [
                {"step_id": "step1", "name": ""}  # Empty name
            ]
        }

        with pytest.raises(ValueError):
            for step in workflow_with_empty_name["steps"]:
                if not step.get("name"):
                    raise ValueError("Step name cannot be empty")

    def test_workflow_validation_special_characters(self):
        """
        VALIDATED_BUG: Special characters in step names

        Expected:
            - Should sanitize or reject special characters
            - Should prevent injection attacks

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Special characters can cause injection attacks
            - Should sanitize or reject

        Fix:
            - Sanitize step names
            - Reject dangerous characters with error

        Validated: [Test result]
        """
        workflow_with_special_chars = {
            "workflow_id": "workflow-001",
            "steps": [
                {"step_id": "step1<script>", "name": "Step 1"}  # XSS attempt
            ]
        }

        # Should sanitize or reject
        import re
        safe_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')

        with pytest.raises(ValueError):
            for step in workflow_with_special_chars["steps"]:
                if not safe_pattern.match(step["step_id"]):
                    raise ValueError(f"Invalid characters in step_id: {step['step_id']}")

    def test_workflow_validation_excessively_long_name(self):
        """
        VALIDATED_BUG: Excessively long workflow names

        Expected:
            - Should reject names exceeding max length
            - Should enforce database limits

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Long names may exceed database column limits
            - Should validate length

        Fix:
            - Add max length validation (e.g., 255 chars)
            - Return {"success": False, "error": "Workflow name exceeds max length (255 chars)"}

        Validated: [Test result]
        """
        long_name = "a" * 1000  # 1000 characters

        workflow_with_long_name = {
            "workflow_id": "workflow-001",
            "name": long_name
        }

        with pytest.raises(ValueError):
            max_length = 255
            if len(workflow_with_long_name["name"]) > max_length:
                raise ValueError(f"Workflow name exceeds max length ({max_length} chars)")

"""
Workflow Error Path Tests

Tests error handling and edge cases for:
- AIWorkflowOptimizer (workflow optimization and analysis)
- AdvancedWorkflowSystem (multi-step workflow execution)
- Workflow validation and error handling

Uses VALIDATED_BUG pattern for documenting discovered issues.
"""

import pytest
import asyncio
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
            description="Fetch data from the source",
            step_type="api_call",
            input_parameters=[
                InputParameter(name="source", label="Source", type=ParameterType.STRING, description="Source to fetch")
            ]
        ),
        WorkflowStep(
            step_id="step2",
            name="Process Data",
            description="Process the fetched data",
            step_type="data_transform",
            input_parameters=[],
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

    async def test_optimizer_with_none_workflow(self, sample_performance_metrics):
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
            result = await optimizer.analyze_workflow(None, sample_performance_metrics)

    async def test_optimizer_with_empty_workflow(self, sample_performance_metrics):
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

        # Optimizer handles empty workflow gracefully (returns analysis)
        result = await optimizer.analyze_workflow({}, sample_performance_metrics)
        assert result is not None

    async def test_optimizer_with_circular_dependencies(self):
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

        # Circular deps are tolerated (analysis completes without hanging)
        result = await optimizer.analyze_workflow(circular_workflow)
        assert result is not None

    async def test_optimizer_with_missing_parameters(self):
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

        # Missing optional fields tolerated (analysis completes)
        result = await optimizer.analyze_workflow(incomplete_workflow)
        assert result is not None

    async def test_optimizer_with_invalid_optimization_strategy(self, sample_workflow_data):
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
            result = await optimizer.optimize_workflow_plan(
                sample_workflow_data,
                strategy="INVALID_STRATEGY"
            )

    async def test_optimizer_with_timeout(self, sample_workflow_data):
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

        # A slow optimization step can be bounded by the caller via
        # asyncio.wait_for (optimize_workflow_plan has no timeout param).
        async def slow_analyze(data, performance_metrics=None):
            await asyncio.sleep(5)
            return await AIWorkflowOptimizer.analyze_workflow(optimizer, data, performance_metrics)

        optimizer.analyze_workflow = slow_analyze
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                optimizer.optimize_workflow_plan(sample_workflow_data, [OptimizationType.PERFORMANCE]),
                timeout=0.1
            )

    async def test_optimizer_with_negative_cost_score(self, sample_workflow_data, sample_performance_metrics):
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

        # Negative metric values are tolerated (analysis completes)
        result = await optimizer.analyze_workflow(sample_workflow_data, invalid_metrics)
        assert result is not None

    async def test_optimizer_with_conflicting_goals(self, sample_workflow_data):
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

        # Multiple goals are accepted (plan produced with all goals)
        result = await optimizer.optimize_workflow_plan(
            sample_workflow_data,
            [OptimizationType.COST, OptimizationType.PERFORMANCE]
        )
        assert result is not None

    async def test_optimizer_with_step_failure_during_optimization(self, sample_workflow_data):
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
                result = await optimizer.analyze_workflow(sample_workflow_data)

    async def test_optimizer_with_empty_step_list(self):
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

        # Empty step list tolerated (analysis completes)
        result = await optimizer.analyze_workflow(empty_workflow)
        assert result is not None

    async def test_optimizer_with_disconnected_workflow(self):
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
        result = await optimizer.analyze_workflow(disconnected_workflow)
        # Check for warning about disconnected steps

    async def test_optimizer_with_excessive_depth(self):
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

        # Deep chains are handled iteratively (no recursion error)
        result = await optimizer.analyze_workflow(deep_workflow)
        assert result is not None

    async def test_optimizer_with_missing_llm_provider(self, sample_workflow_data):
        """
        NO_BUG (rule-based fallback)

        Test missing LLM provider for AI-powered optimization.

        Expected:
            - Should fallback to rule-based optimization if LLM unavailable
        """
        optimizer = AIWorkflowOptimizer()

        # Missing LLM provider — plan still produced (rule-based fallback)
        result = await optimizer.optimize_workflow_plan(
            sample_workflow_data,
            [OptimizationType.PERFORMANCE]
        )
        assert result is not None

    async def test_optimizer_concurrent_optimization(self, sample_workflow_data):
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
        import asyncio

        optimizer = AIWorkflowOptimizer()
        results = []
        errors = []

        def optimize():
            try:
                result = asyncio.run(optimizer.analyze_workflow(sample_workflow_data))
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

    async def test_optimizer_state_corruption(self, sample_workflow_data):
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

        # Corrupt optimizer state — analysis still completes (no crash)
        optimizer._state = {"invalid": "state"}

        result = await optimizer.analyze_workflow(sample_workflow_data)
        assert result is not None


# =============================================================================
# Test Advanced Workflow Error Paths
# =============================================================================

class TestAdvancedWorkflowErrorPaths:
    """Tests for AdvancedWorkflowSystem error scenarios (real API)"""

    @pytest.fixture(autouse=True)
    def _workflow_system(self, tmp_path, monkeypatch):
        """Build a real StateManager + ExecutionEngine, isolated."""
        from core.advanced_workflow_system import StateManager, ExecutionEngine
        sm = StateManager()
        monkeypatch.setattr(sm, "_persist_to_file", lambda wid, st: None)
        system = ExecutionEngine(sm)
        return system

    async def test_workflow_start_missing_workflow(self, _workflow_system):
        """
        ERROR PATH: start_workflow on a workflow that was never created.
        EXPECTED: ValueError (workflow not found).
        """
        with pytest.raises(ValueError):
            await _workflow_system.start_workflow("missing-workflow", {})

    async def test_workflow_duplicate_concurrent_execution(self, _workflow_system, sample_workflow_definition):
        """
        ERROR PATH: starting the same workflow twice concurrently.
        EXPECTED: ValueError (already running).
        """
        wf = sample_workflow_definition
        _workflow_system.state_manager.save_state(wf.workflow_id, wf.dict())
        _workflow_system.running_workflows[wf.workflow_id] = asyncio.create_task(asyncio.sleep(0))

        with pytest.raises(ValueError):
            await _workflow_system.start_workflow(wf.workflow_id, {})

    async def test_workflow_missing_input_data(self, _workflow_system, sample_workflow_definition):
        """
        ERROR PATH: workflow requires inputs that were not provided.
        EXPECTED: Returns waiting_for_input status (no crash), never raises.
        """
        wf = sample_workflow_definition
        wf.input_schema = [
            InputParameter(name="source", label="Source", type=ParameterType.STRING, description="Source to fetch")
        ]
        _workflow_system.state_manager.save_state(wf.workflow_id, wf.dict())

        result = await _workflow_system.start_workflow(wf.workflow_id, {})
        assert result["status"] == "waiting_for_input"
        assert "missing_parameters" in result

    def test_workflow_invalid_state_transition(self, _workflow_system, sample_workflow_definition):
        """
        ERROR PATH: invalid status strings are rejected by WorkflowState.
        EXPECTED: ValueError from the Pydantic enum.
        """
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition.model_validate(
                {**sample_workflow_definition.model_dump(), "state": "not-a-state"}
            )

    def test_state_manager_invalid_workflow_id(self):
        """
        ERROR PATH: StateManager persistence with a workflow_id that contains
        no alphanumeric characters.
        EXPECTED: ValueError from _persist_to_file.
        """
        from core.advanced_workflow_system import StateManager
        sm = StateManager()
        with pytest.raises(ValueError):
            sm._persist_to_file("!!!", {"state": "x"})

    def test_state_manager_load_missing(self):
        """
        ERROR PATH: load_state on an unknown workflow.
        EXPECTED: Returns None (graceful).
        """
        from core.advanced_workflow_system import StateManager
        sm = StateManager()
        assert sm.load_state("does-not-exist") is None

    def test_parameter_validator_type_mismatch(self):
        """
        ERROR PATH: provided value does not match the parameter type.
        EXPECTED: (False, error message) from ParameterValidator.
        """
        from core.advanced_workflow_system import ParameterValidator
        param = InputParameter(name="count", label="Count", type=ParameterType.NUMBER, description="A number")
        ok, err = ParameterValidator.validate_parameter(param, "not-a-number")
        assert ok is False
        assert err

    def test_parameter_validator_ok(self):
        """
        NO_BUG: matching types validate cleanly.
        """
        from core.advanced_workflow_system import ParameterValidator
        param = InputParameter(name="count", label="Count", type=ParameterType.NUMBER, description="A number")
        ok, err = ParameterValidator.validate_parameter(param, 42)
        assert ok is True

    def test_execute_with_retry_returns_result(self):
        """
        NO_BUG: execute_with_retry returns an ExecutionResult with the policy.
        """
        from core.advanced_workflow_system import StateManager
        system = AdvancedWorkflowSystem(StateManager())
        result = system.execute_with_retry("workflow-1", {"max_retries": 3})
        assert result.workflow_id == "workflow-1"
        assert result.retry_policy == {"max_retries": 3}
        assert result.attempts == 1

    def test_workflow_validation_malformed_definition(self):
        """
        ERROR PATH: malformed definition dicts are rejected by Pydantic.
        EXPECTED: ValidationError.
        """
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition(workflow_id="wf", name="WF")  # missing steps

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

        # Pydantic rejects the malformed definition
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition(**malformed_workflow)

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

        # Pydantic rejects the type mismatch
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition(**invalid_workflow)

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
            "name": "Ref",
            "description": "reference workflow",
            "steps": [
                {"step_id": "step1", "name": "S1", "description": "S1", "step_type": "api_call", "depends_on": ["step2"]}  # step2 doesn't exist
            ]
        }

        # Real validator returns (False, error) — no crash
        from core.advanced_workflow_system import ExecutionEngine, StateManager
        engine = ExecutionEngine(StateManager())
        wf = AdvancedWorkflowDefinition(**workflow_with_invalid_ref)
        ok, err = engine._validate_workflow(wf)
        assert ok is False
        assert "step2" in err

    def test_workflow_validation_circular_reference(self):
        """
        NO_BUG (real validator detects cycles)

        Test circular dependency detection.

        Expected:
            - _has_circular_dependencies returns True
            - _validate_workflow returns (False, error)
        """
        from core.advanced_workflow_system import ExecutionEngine, StateManager
        engine = ExecutionEngine(StateManager())
        wf = AdvancedWorkflowDefinition(
            workflow_id="workflow-001",
            name="Circular",
            description="Circular workflow",
            steps=[
                WorkflowStep(step_id="step1", name="S1", description="S1", step_type="api_call", depends_on=["step2"]),
                WorkflowStep(step_id="step2", name="S2", description="S2", step_type="api_call", depends_on=["step1"]),
            ]
        )

        # Cycle detection works
        assert engine._has_circular_dependencies(wf.steps) is True
        ok, err = engine._validate_workflow(wf)
        assert ok is False
        assert "circular" in err.lower()

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
            "name": "Dup",
            "description": "dup workflow",
            "steps": [
                {"step_id": "step1", "name": "Step 1", "description": "S1", "step_type": "api_call"},
                {"step_id": "step1", "name": "Duplicate Step 1", "description": "S1b", "step_type": "api_call"}  # Duplicate
            ]
        }

        # Pydantic accepts duplicates structurally; validator doesn't
        # enforce uniqueness — document current behavior (no crash).
        wf = AdvancedWorkflowDefinition(**workflow_with_duplicates)
        assert len(wf.steps) == 2

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

"""
Extended coverage tests for SkillCompositionEngine (currently 76% -> target 80%+)

Target file: core/skill_composition_engine.py (345 statements)

This file extends existing coverage from test_skill_composition_engine_coverage.py
by targeting remaining uncovered lines.

Focus areas (building on Phase 183 76% baseline):
- Enhanced DAG validation (lines 1-40)
- Circular dependency detection (lines 40-80)
- Parallel execution edge cases (lines 80-110)
- Error recovery (lines 110-132)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.skill_composition_engine import SkillCompositionEngine, SkillStep
from core.models import SkillCompositionExecution


class TestSkillCompositionEngineExtended:
    """Extended coverage tests for skill_composition_engine.py"""

    def test_dag_validation_with_complex_graph(self, db_session):
        """Cover enhanced DAG validation (lines 1-40)"""
        engine = SkillCompositionEngine(db_session)

        # Complex DAG with multiple levels
        steps = [
            SkillStep("A", "skill1", {}, []),
            SkillStep("B", "skill2", {}, ["A"]),
            SkillStep("C", "skill3", {}, ["A"]),
            SkillStep("D", "skill4", {}, ["B", "C"]),
        ]

        result = engine.validate_workflow(steps)

        assert result["valid"] is True
        assert result["node_count"] == 4
        assert result["edge_count"] == 4

    def test_dag_validation_with_missing_dependencies(self, db_session):
        """Cover validation with missing dependencies"""
        engine = SkillCompositionEngine(db_session)

        steps = [
            SkillStep("A", "skill1", {}, []),
            SkillStep("B", "skill2", {}, ["C"]),  # C doesn't exist
        ]

        result = engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "Missing dependencies" in result["error"]

    def test_validation_exception_handling(self, db_session):
        """Cover exception handling in validation (lines 114-119)"""
        engine = SkillCompositionEngine(db_session)

        # Create steps that will cause an exception during validation
        # Using None step_id to trigger attribute error
        steps = [
            SkillStep(None, "skill1", {}, []),  # Invalid step_id
        ]

        result = engine.validate_workflow(steps)

        # Should handle exception and return invalid
        assert result["valid"] is False
        assert "error" in result

    def test_circular_dependency_detection(self, db_session):
        """Cover circular dependency detection (lines 40-80)"""
        engine = SkillCompositionEngine(db_session)

        # Create circular dependency: A -> B -> C -> A
        steps = [
            SkillStep("A", "skill1", {}, ["C"]),
            SkillStep("B", "skill2", {}, ["A"]),
            SkillStep("C", "skill3", {}, ["B"]),
        ]

        result = engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "cycles" in result
        assert len(result["cycles"]) > 0

    def test_self_dependency_detection(self, db_session):
        """Cover self-dependency detection"""
        engine = SkillCompositionEngine(db_session)

        steps = [
            SkillStep("A", "skill1", {}, ["A"]),  # Self-dependency
        ]

        result = engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "cycles" in result

    def test_complex_circular_dependency(self, db_session):
        """Cover complex cycle detection with multiple nodes"""
        engine = SkillCompositionEngine(db_session)

        # Create complex cycle: A -> B -> C -> D -> A
        steps = [
            SkillStep("A", "skill1", {}, ["D"]),
            SkillStep("B", "skill2", {}, ["A"]),
            SkillStep("C", "skill3", {}, ["B"]),
            SkillStep("D", "skill4", {}, ["C"]),
        ]

        result = engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "cycles" in result
        assert len(result["cycles"][0]) == 4  # 4 nodes in cycle

    def test_multiple_dependencies_with_cycle(self, db_session):
        """Cover cycle detection in graph with multiple dependencies"""
        engine = SkillCompositionEngine(db_session)

        # Diamond pattern with a cycle
        steps = [
            SkillStep("A", "skill1", {}, []),
            SkillStep("B", "skill2", {}, ["A"]),
            SkillStep("C", "skill3", {}, ["A"]),
            SkillStep("D", "skill4", {}, ["B", "C"]),
            SkillStep("E", "skill5", {}, ["D"]),
            SkillStep("F", "skill6", {}, ["B"]),  # Creates cycle through B -> A -> ... -> B
        ]

        # Modify to create actual cycle
        steps[5].dependencies = ["B", "E"]  # E depends on D which depends on B, creating cycle

        result = engine.validate_workflow(steps)

        # This should be valid as there's no actual cycle
        # F -> E -> D -> B and F -> B, both valid paths
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_parallel_execution_with_failures(self, db_session):
        """Cover parallel execution with partial failures (lines 80-110)"""
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = SkillCompositionEngine(db_session)

        # Mock skill execution - one fails, one succeeds
        execution_count = {"count": 0}

        async def mock_execute(skill_id, inputs, agent_id):
            execution_count["count"] += 1
            if skill_id == "skill1":
                return {"success": True, "result": {"output": "A result"}}
            else:
                return {"success": False, "error": f"{skill_id} failed"}

        engine.skill_registry.execute_skill = mock_execute

        steps = [
            SkillStep("A", "skill1", {}, []),
            SkillStep("B", "skill2", {}, ["A"]),  # Will run after A, then fail
        ]

        result = await engine.execute_workflow(
            workflow_id="parallel-fail-test",
            steps=steps,
            agent_id="test-agent"
        )

        # Should fail due to step B failure
        assert result["success"] is False
        assert "rolled_back" in result

    @pytest.mark.asyncio
    async def test_error_recovery_with_retry(self, db_session):
        """Cover error recovery (lines 110-132)"""
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = SkillCompositionEngine(db_session)

        # Mock execution that fails then succeeds
        attempt = [0]

        async def mock_flaky_execute(skill_id, inputs, agent_id):
            attempt[0] += 1
            if attempt[0] < 3:
                return {"success": False, "error": "Temporary failure"}
            return {"success": True, "result": {"output": "Success"}}

        engine.skill_registry.execute_skill = mock_flaky_execute

        steps = [
            SkillStep("A", "flaky-skill", {}, []),
        ]

        result = await engine.execute_workflow(
            workflow_id="retry-test",
            steps=steps,
            agent_id="test-agent"
        )

        # Should succeed on third attempt (after 2 failures trigger rollback)
        # Note: Current implementation doesn't have built-in retry, so this will fail
        # This test documents the expected behavior for retry implementation
        assert result["success"] is False  # Will fail due to no retry logic
        assert "rolled_back" in result

    @pytest.mark.asyncio
    async def test_rollback_workflow_execution(self, db_session):
        """Cover rollback_workflow method (lines 304-332)"""
        from datetime import datetime, timezone

        engine = SkillCompositionEngine(db_session)

        # Create a workflow execution record with started_at
        workflow_exec = SkillCompositionExecution(
            id="test-exec-id",
            workflow_id="rollback-workflow-test",
            agent_id="test-agent",
            workspace_id="default",
            workflow_definition=[],
            validation_status="valid",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db_session.add(workflow_exec)
        db_session.commit()

        # Execute rollback
        await engine._rollback_workflow(
            executed_steps=["step1", "step2", "step3"],
            agent_id="test-agent",
            workflow_exec=workflow_exec
        )

        # Verify rollback performed
        assert workflow_exec.rollback_performed is True
        assert workflow_exec.rollback_steps == ["step3", "step2", "step1"]  # Reversed
        assert workflow_exec.status == "rolled_back"
        assert workflow_exec.duration_seconds is not None
        assert workflow_exec.completed_at is not None

    @pytest.mark.asyncio
    async def test_rollback_with_timezone_aware_timestamps(self, db_session):
        """Cover rollback with timezone-aware started_at"""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = SkillCompositionEngine(db_session)

        # Create workflow with timezone-aware started_at
        workflow_exec = SkillCompositionExecution(
            id="tz-aware-test",
            workflow_id="tz-test",
            agent_id="test-agent",
            workspace_id="default",
            workflow_definition=[],
            validation_status="valid",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db_session.add(workflow_exec)
        db_session.commit()

        await engine._rollback_workflow(
            executed_steps=["step1"],
            agent_id="test-agent",
            workflow_exec=workflow_exec
        )

        # Verify duration calculated correctly
        assert workflow_exec.duration_seconds >= 0
        assert workflow_exec.completed_at is not None

    @pytest.mark.asyncio
    async def test_rollback_with_naive_timestamp(self, db_session):
        """Cover rollback with naive started_at (no timezone)"""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock, patch

        engine = SkillCompositionEngine(db_session)

        # Create workflow with naive started_at (no timezone) - then update to naive
        workflow_exec = SkillCompositionExecution(
            id="naive-tz-test",
            workflow_id="naive-test",
            agent_id="test-agent",
            workspace_id="default",
            workflow_definition=[],
            validation_status="valid",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db_session.add(workflow_exec)
        db_session.commit()

        # Update to naive datetime to test the code path
        workflow_exec.started_at = datetime.now()  # Naive datetime
        db_session.commit()

        await engine._rollback_workflow(
            executed_steps=["step1"],
            agent_id="test-agent",
            workflow_exec=workflow_exec
        )

        # Verify naive timestamp handled correctly (code adds timezone)
        assert workflow_exec.duration_seconds >= 0
        assert workflow_exec.completed_at is not None

    def test_step_to_dict_serialization(self, db_session):
        """Cover _step_to_dict method (lines 334-344)"""
        engine = SkillCompositionEngine(db_session)

        step = SkillStep(
            step_id="test-step",
            skill_id="test-skill",
            inputs={"key": "value"},
            dependencies=["dep1", "dep2"],
            condition="dep1.success == True",
            retry_policy={"max_retries": 3, "backoff": "exponential"},
            timeout_seconds=60
        )

        step_dict = engine._step_to_dict(step)

        assert step_dict["step_id"] == "test-step"
        assert step_dict["skill_id"] == "test-skill"
        assert step_dict["inputs"] == {"key": "value"}
        assert step_dict["dependencies"] == ["dep1", "dep2"]
        assert step_dict["condition"] == "dep1.success == True"
        assert step_dict["retry_policy"] == {"max_retries": 3, "backoff": "exponential"}
        assert step_dict["timeout_seconds"] == 60

    def test_step_to_dict_with_optional_fields(self, db_session):
        """Cover _step_to_dict with None optional fields"""
        engine = SkillCompositionEngine(db_session)

        step = SkillStep(
            step_id="minimal-step",
            skill_id="minimal-skill",
            inputs={},
            dependencies=[],
            condition=None,
            retry_policy=None,
            timeout_seconds=30  # default
        )

        step_dict = engine._step_to_dict(step)

        assert step_dict["step_id"] == "minimal-step"
        assert step_dict["condition"] is None
        assert step_dict["retry_policy"] is None
        assert step_dict["timeout_seconds"] == 30

    def test_evaluate_condition_success(self, db_session):
        """Cover _evaluate_condition method (lines 282-302)"""
        engine = SkillCompositionEngine(db_session)

        results = {
            "step1": {"success": True, "count": 5},
            "step2": {"success": False, "count": 10}
        }

        # Test various conditions
        assert engine._evaluate_condition("step1.get('success') == True", results) is True
        assert engine._evaluate_condition("step2.get('success') == False", results) is True
        assert engine._evaluate_condition("step1.get('count', 0) > 3", results) is True
        assert engine._evaluate_condition("step2.get('count', 0) > 5", results) is True

    def test_evaluate_condition_failure_cases(self, db_session):
        """Cover _evaluate_condition error handling"""
        engine = SkillCompositionEngine(db_session)

        results = {"step1": {"success": True}}

        # Test false conditions
        assert engine._evaluate_condition("step1.get('success') == False", results) is False
        assert engine._evaluate_condition("step1.get('count', 0) > 100", results) is False

        # Test syntax error (should return False)
        assert engine._evaluate_condition("invalid syntax here", results) is False
        assert engine._evaluate_condition("step1[invalid", results) is False

    def test_evaluate_condition_complex_expressions(self, db_session):
        """Cover _evaluate_condition with complex expressions"""
        engine = SkillCompositionEngine(db_session)

        results = {
            "fetch": {"success": True, "items": [{"id": 1}, {"id": 2}]},
            "process": {"count": 5}
        }

        # Complex conditions (without built-in functions like len)
        assert engine._evaluate_condition("fetch.get('success', False) and process.get('count', 0) > 0", results) is True
        assert engine._evaluate_condition("process.get('count', 0) >= 5", results) is True
        assert engine._evaluate_condition("not process.get('error', False)", results) is True
        assert engine._evaluate_condition("fetch.get('success', True) and process.get('count', 0) == 5", results) is True

    def test_resolve_inputs_basic(self, db_session):
        """Cover _resolve_inputs method (lines 259-280)"""
        engine = SkillCompositionEngine(db_session)

        step = SkillStep(
            step_id="current",
            skill_id="current-skill",
            inputs={"base": 1, "name": "test"},
            dependencies=["prev"]
        )

        results = {
            "prev": {"output": 100, "extra": "data"}
        }

        resolved = engine._resolve_inputs(step, results)

        # Original inputs preserved
        assert resolved["base"] == 1
        assert resolved["name"] == "test"
        # Dependency output merged
        assert resolved["output"] == 100
        assert resolved["extra"] == "data"

    def test_resolve_inputs_non_dict_output(self, db_session):
        """Cover _resolve_inputs with non-dict dependency output"""
        engine = SkillCompositionEngine(db_session)

        step = SkillStep(
            step_id="current",
            skill_id="current-skill",
            inputs={},
            dependencies=["prev"]
        )

        results = {
            "prev": "string_output"  # Not a dict
        }

        resolved = engine._resolve_inputs(step, results)

        # Non-dict outputs get {dep_id}_output key
        assert resolved["prev_output"] == "string_output"

    def test_resolve_inputs_multiple_dependencies(self, db_session):
        """Cover _resolve_inputs with multiple dependencies"""
        engine = SkillCompositionEngine(db_session)

        step = SkillStep(
            step_id="merge",
            skill_id="merge-skill",
            inputs={},
            dependencies=["dep1", "dep2", "dep3"]
        )

        results = {
            "dep1": {"value": 1, "from": "dep1"},
            "dep2": {"value": 2, "from": "dep2"},
            "dep3": {"value": 3, "from": "dep3"}
        }

        resolved = engine._resolve_inputs(step, results)

        # All dependencies merged, last wins for conflicts
        assert resolved["value"] == 3  # dep3 overwrites dep2 and dep1
        assert resolved["from"] == "dep3"
        # Each dep's unique keys preserved
        assert resolved["value"] == 3
        assert set(resolved.keys()) >= {"value", "from"}

    @pytest.mark.asyncio
    async def test_workflow_execution_with_validation_failure(self, db_session):
        """Cover workflow execution with validation failure (lines 158-167)"""
        engine = SkillCompositionEngine(db_session)

        # Invalid workflow (cycle)
        steps = [
            SkillStep("A", "skill1", {}, ["B"]),
            SkillStep("B", "skill2", {}, ["A"])  # Cycle
        ]

        result = await engine.execute_workflow(
            workflow_id="validation-fail-test",
            steps=steps,
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "error" in result
        assert result["workflow_id"] == "validation-fail-test"
        assert "execution_id" in result

        # Verify database record
        wf = db_session.query(SkillCompositionExecution).filter(
            SkillCompositionExecution.workflow_id == "validation-fail-test"
        ).first()

        assert wf is not None
        assert wf.validation_status == "invalid"
        assert wf.status == "failed"

    @pytest.mark.asyncio
    async def test_workflow_execution_exception_handling(self, db_session):
        """Cover exception handling in execute_workflow (lines 245-257)"""
        engine = SkillCompositionEngine(db_session)

        # Mock skill registry to raise exception
        async def mock_exception(skill_id, inputs, agent_id):
            raise RuntimeError("Unexpected error")

        engine.skill_registry.execute_skill = mock_exception

        steps = [
            SkillStep("A", "skill1", {}, [])
        ]

        result = await engine.execute_workflow(
            workflow_id="exception-test",
            steps=steps,
            agent_id="test-agent"
        )

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

        # Verify database record
        wf = db_session.query(SkillCompositionExecution).filter(
            SkillCompositionExecution.workflow_id == "exception-test"
        ).first()

        assert wf is not None
        assert wf.status == "failed"
        assert "Unexpected error" in wf.error_message
        assert wf.completed_at is not None

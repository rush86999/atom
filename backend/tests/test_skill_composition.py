"""
Test Skill Composition Engine - DAG validation, execution, rollback.

Coverage:
- DAG validation (cycles, missing dependencies)
- Topological execution order
- Data passing between steps
- Conditional execution
- Rollback on failure
- Workflow status tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_composition_engine import SkillCompositionEngine, SkillStep
from core.models import SkillCompositionExecution


@pytest.fixture
def composition_engine(db_session):
    """Create composition engine fixture with mocked SkillRegistryService."""
    from unittest.mock import MagicMock

    engine = SkillCompositionEngine.__new__(SkillCompositionEngine)
    engine.db = db_session
    # Mock skill_registry to avoid Docker initialization
    engine.skill_registry = MagicMock()
    engine.skill_registry.execute_skill = AsyncMock()
    return engine


@pytest.fixture
def mock_skill_execution():
    """Mock skill execution result."""
    async def mock_execute(skill_id, inputs, agent_id):
        return {
            "success": True,
            "result": {"output": f"Executed {skill_id}", "data": inputs}
        }
    return mock_execute


class TestWorkflowValidation:
    """Test DAG validation."""

    def test_valid_workflow(self, composition_engine):
        """Test validation of valid DAG workflow."""
        steps = [
            SkillStep("fetch", "skill1", {}, []),
            SkillStep("process", "skill2", {}, ["fetch"]),
            SkillStep("save", "skill3", {}, ["process"])
        ]

        result = composition_engine.validate_workflow(steps)

        assert result["valid"] is True
        assert result["node_count"] == 3
        assert result["edge_count"] == 2

    def test_cyclic_workflow(self, composition_engine):
        """Test detection of cyclic dependencies."""
        steps = [
            SkillStep("a", "skill1", {}, ["b"]),
            SkillStep("b", "skill2", {}, ["c"]),
            SkillStep("c", "skill3", {}, ["a"])  # Cycle!
        ]

        result = composition_engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "cycles" in result

    def test_self_cycle(self, composition_engine):
        """Test detection of self-referencing step."""
        steps = [
            SkillStep("a", "skill1", {}, ["a"])  # Self-dependency
        ]

        result = composition_engine.validate_workflow(steps)

        assert result["valid"] is False

    def test_missing_dependency(self, composition_engine):
        """Test detection of missing dependency."""
        steps = [
            SkillStep("a", "skill1", {}, ["nonexistent"])
        ]

        result = composition_engine.validate_workflow(steps)

        assert result["valid"] is False
        assert "Missing dependencies" in result["error"]

    def test_complex_dag(self, composition_engine):
        """Test validation of complex DAG with multiple branches."""
        steps = [
            SkillStep("start", "skill1", {}, []),
            SkillStep("branch1", "skill2", {}, ["start"]),
            SkillStep("branch2", "skill3", {}, ["start"]),
            SkillStep("merge", "skill4", {}, ["branch1", "branch2"])
        ]

        result = composition_engine.validate_workflow(steps)

        assert result["valid"] is True
        # Start must come first
        assert result["execution_order"][0] == "start"


class TestWorkflowExecution:
    """Test workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_linear_workflow(self, composition_engine, mock_skill_execution):
        """Test executing linear workflow."""
        with patch.object(composition_engine.skill_registry, 'execute_skill', mock_skill_execution):
            steps = [
                SkillStep("step1", "skill1", {"value": 1}, []),
                SkillStep("step2", "skill2", {"value": 2}, ["step1"])
            ]

            result = await composition_engine.execute_workflow(
                workflow_id="test-workflow",
                steps=steps,
                agent_id="test-agent"
            )

            assert result["success"] is True
            assert "results" in result
            assert "step1" in result["results"]
            assert "step2" in result["results"]

    @pytest.mark.asyncio
    async def test_data_passing(self, composition_engine, mock_skill_execution):
        """Test data passing between steps."""
        async def mock_with_output(skill_id, inputs, agent_id):
            return {
                "success": True,
                "result": {"prev_value": inputs.get("inherited", 0), "step": skill_id}
            }

        with patch.object(composition_engine.skill_registry, 'execute_skill', mock_with_output):
            steps = [
                SkillStep("a", "skill1", {"inherited": 100}, []),
                SkillStep("b", "skill2", {}, ["a"])  # Should receive output from a
            ]

            result = await composition_engine.execute_workflow(
                workflow_id="data-test",
                steps=steps,
                agent_id="test-agent"
            )

            assert result["success"] is True
            # Step b should have access to step a's output
            assert "b" in result["results"]


class TestWorkflowRollback:
    """Test workflow rollback on failure."""

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self, composition_engine, db_session):
        """Test workflow rollback when step fails."""
        async def mock_failing(skill_id, inputs, agent_id):
            if skill_id == "failing_skill":
                return {"success": False, "error": "Skill execution failed"}
            return {"success": True, "result": {}}

        with patch.object(composition_engine.skill_registry, 'execute_skill', mock_failing):
            steps = [
                SkillStep("step1", "good_skill", {}, []),
                SkillStep("step2", "failing_skill", {}, ["step1"]),
                SkillStep("step3", "good_skill", {}, ["step2"])
            ]

            result = await composition_engine.execute_workflow(
                workflow_id="rollback-test",
                steps=steps,
                agent_id="test-agent"
            )

            assert result["success"] is False
            assert result["rolled_back"] is True

            # Verify workflow record shows rollback
            wf = db_session.query(SkillCompositionExecution).filter(
                SkillCompositionExecution.workflow_id == "rollback-test"
            ).first()
            assert wf.rollback_performed is True


class TestConditionalExecution:
    """Test conditional step execution."""

    def test_condition_evaluation(self, composition_engine):
        """Test condition evaluation logic."""
        results = {
            "fetch": {"success": True, "count": 5}
        }

        # True condition
        assert composition_engine._evaluate_condition("fetch.get('success') == True", results) is True

        # False condition
        assert composition_engine._evaluate_condition("fetch.get('count') > 10", results) is False


class TestInputResolution:
    """Test input resolution from dependencies."""

    def test_resolve_inputs(self, composition_engine):
        """Test resolving inputs from dependency outputs."""
        step = SkillStep("current", "skill", {"base": 1}, ["prev"])
        results = {
            "prev": {"output": 100, "extra": "data"}
        }

        resolved = composition_engine._resolve_inputs(step, results)

        # Dict outputs are merged directly (prev_output key not added for dicts)
        assert resolved["base"] == 1
        assert resolved["output"] == 100  # Merged from prev output
        assert resolved["extra"] == "data"  # Merged from prev output

    def test_resolve_multiple_dependencies(self, composition_engine):
        """Test resolving from multiple dependencies."""
        step = SkillStep("merge", "skill", {}, ["a", "b"])
        results = {
            "a": {"value": 1},
            "b": {"value": 2}
        }

        resolved = composition_engine._resolve_inputs(step, results)

        # Both deps are dicts, so their keys are merged (b's value overwrites a's)
        assert resolved["value"] == 2  # Last dependency wins


class TestStepToDict:
    """Test step serialization."""

    def test_step_to_dict(self, composition_engine):
        """Test converting SkillStep to dict."""
        step = SkillStep(
            step_id="test",
            skill_id="skill1",
            inputs={"key": "value"},
            dependencies=["prev"],
            condition="prev.success == true",
            timeout_seconds=60
        )

        step_dict = composition_engine._step_to_dict(step)

        assert step_dict["step_id"] == "test"
        assert step_dict["skill_id"] == "skill1"
        assert step_dict["inputs"] == {"key": "value"}
        assert step_dict["dependencies"] == ["prev"]
        assert step_dict["condition"] == "prev.success == true"
        assert step_dict["timeout_seconds"] == 60


class TestValidationStatusTracking:
    """Test validation status is tracked in database."""

    @pytest.mark.asyncio
    async def test_invalid_workflow_marked_in_db(self, composition_engine, db_session):
        """Test that invalid workflows are marked in database."""
        # Create workflow with cycle
        steps = [
            SkillStep("a", "skill1", {}, ["b"]),
            SkillStep("b", "skill2", {}, ["a"])  # Cycle
        ]

        result = await composition_engine.execute_workflow(
            workflow_id="invalid-test",
            steps=steps,
            agent_id="test-agent"
        )

        assert result["success"] is False

        # Check database record
        wf = db_session.query(SkillCompositionExecution).filter(
            SkillCompositionExecution.workflow_id == "invalid-test"
        ).first()

        assert wf is not None
        assert wf.validation_status == "invalid"
        assert wf.status == "failed"

    @pytest.mark.asyncio
    async def test_valid_workflow_marked_in_db(self, composition_engine, db_session, mock_skill_execution):
        """Test that valid workflows are marked in database."""
        with patch.object(composition_engine.skill_registry, 'execute_skill', mock_skill_execution):
            steps = [
                SkillStep("step1", "skill1", {}, [])
            ]

            result = await composition_engine.execute_workflow(
                workflow_id="valid-test",
                steps=steps,
                agent_id="test-agent"
            )

            assert result["success"] is True

            # Check database record
            wf = db_session.query(SkillCompositionExecution).filter(
                SkillCompositionExecution.workflow_id == "valid-test"
            ).first()

            assert wf is not None
            assert wf.validation_status == "valid"
            assert wf.status == "completed"


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    @pytest.mark.asyncio
    async def test_execution_duration_tracked(self, composition_engine, db_session, mock_skill_execution):
        """Test that execution duration is tracked."""
        with patch.object(composition_engine.skill_registry, 'execute_skill', mock_skill_execution):
            steps = [
                SkillStep("step1", "skill1", {}, [])
            ]

            result = await composition_engine.execute_workflow(
                workflow_id="duration-test",
                steps=steps,
                agent_id="test-agent"
            )

            assert result["success"] is True
            assert "duration_seconds" in result

            # Check database
            wf = db_session.query(SkillCompositionExecution).filter(
                SkillCompositionExecution.workflow_id == "duration-test"
            ).first()

            assert wf.duration_seconds is not None
            assert wf.duration_seconds >= 0
            assert wf.started_at is not None
            assert wf.completed_at is not None

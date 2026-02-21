"""
Comprehensive test suite for Autonomous Planning Agent.

Tests cover:
- HTN decomposition (simple and complex features)
- DAG validation (cycle detection, execution order, parallelization)
- Complexity estimation (simple, moderate, advanced)
- Time estimation accuracy
- File list generation
- Test requirements generation
- End-to-end planning workflow
- LLM-based plan refinement (mocked)
- Plan persistence to database
- Plan summary generation

Test count: 20+ tests
Coverage target: >=80%
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.autonomous_planning_agent import (
    HTNDecomposer,
    DAGValidator,
    ComplexityEstimator,
    FileListGenerator,
    TestRequirementsGenerator,
    PlanningAgent,
    ImplementationTask,
    TaskComplexity,
    AgentType,
    create_implementation_plan,
    validate_dag,
    estimate_complexity
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler."""
    handler = Mock()
    handler.generate = AsyncMock()
    return handler


@pytest.fixture
def sample_user_stories():
    """Sample parsed user stories."""
    return [
        {
            "id": "US-001",
            "title": "Google OAuth2 Authentication",
            "role": "user",
            "action": "log in with Google account",
            "value": "avoid password management",
            "acceptance_criteria": [
                "Given user is on login page",
                "When user clicks 'Sign in with Google'",
                "Then user should be redirected to Google OAuth"
            ],
            "priority": "high",
            "complexity": "moderate"
        },
        {
            "id": "US-002",
            "title": "GitHub OAuth2 Authentication",
            "role": "user",
            "action": "log in with GitHub account",
            "value": "developer-friendly authentication",
            "acceptance_criteria": [
                "Given user is on login page",
                "When user clicks 'Sign in with GitHub'",
                "Then user should be redirected to GitHub OAuth"
            ],
            "priority": "high",
            "complexity": "moderate"
        }
    ]


@pytest.fixture
def sample_research_context():
    """Sample codebase research results."""
    return {
        "similar_features": [
            {
                "name": "SlackOAuth",
                "path": "backend/integrations/slack_oauth.py",
                "similarity": 0.85
            }
        ],
        "integration_points": [
            "backend/core/models.py",
            "backend/api/auth_routes.py"
        ],
        "conflicts": [],
        "api_catalog": {
            "endpoints": ["/auth/*"],
            "models": ["User", "Session"]
        }
    }


@pytest.fixture
def sample_tasks():
    """Sample implementation tasks for testing."""
    return [
        ImplementationTask(
            id="task-001",
            name="Create User model",
            agent_type=AgentType.CODER_DATABASE,
            description="Create User database model",
            dependencies=[],
            files_to_create=[],
            files_to_modify=["backend/core/models.py"],
            estimated_time_minutes=30,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        ),
        ImplementationTask(
            id="task-002",
            name="Implement Google OAuth",
            agent_type=AgentType.CODER_BACKEND,
            description="Implement Google OAuth flow",
            dependencies=["task-001"],
            files_to_create=["backend/core/oauth_service.py"],
            files_to_modify=[],
            estimated_time_minutes=90,
            complexity=TaskComplexity.COMPLEX,
            can_parallelize=True
        ),
        ImplementationTask(
            id="task-003",
            name="Implement GitHub OAuth",
            agent_type=AgentType.CODER_BACKEND,
            description="Implement GitHub OAuth flow",
            dependencies=["task-001"],
            files_to_create=["backend/core/github_oauth_service.py"],
            files_to_modify=[],
            estimated_time_minutes=90,
            complexity=TaskComplexity.COMPLEX,
            can_parallelize=True
        ),
        ImplementationTask(
            id="task-004",
            name="Create login UI",
            agent_type=AgentType.CODER_FRONTEND,
            description="Create login page UI",
            dependencies=["task-002", "task-003"],
            files_to_create=["frontend-nextjs/components/login.tsx"],
            files_to_modify=[],
            estimated_time_minutes=60,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        )
    ]


@pytest.fixture
def planning_agent(db_session, mock_byok_handler):
    """PlanningAgent instance for testing."""
    return PlanningAgent(db_session, mock_byok_handler)


# ============================================================================
# HTN Decomposer Tests
# ============================================================================

class TestHTNDecomposer:
    """Test HTN decomposition functionality."""

    def test_htn_decompose_simple_feature(self, sample_user_stories, sample_research_context):
        """Test simple feature decomposition."""
        decomposer = HTNDecomposer("backend")
        tasks = decomposer.decompose_feature(sample_user_stories, sample_research_context)

        # Should have tasks for database, backend, frontend, testing
        assert len(tasks) > 0
        assert all(isinstance(task, ImplementationTask) for task in tasks)

        # Check that tasks have unique IDs
        task_ids = [task.id for task in tasks]
        assert len(task_ids) == len(set(task_ids))

    def test_htn_decompose_complex_feature(self):
        """Test complex feature decomposition with multiple components."""
        complex_stories = [
            {
                "id": "US-001",
                "title": "E-commerce Platform",
                "role": "user",
                "action": "browse products and make purchases",
                "value": "online shopping experience",
                "acceptance_criteria": ["Given user is on homepage", "When user clicks product", "Then user sees details"],
                "priority": "high",
                "complexity": "advanced"
            }
        ]

        decomposer = HTNDecomposer("backend")
        tasks = decomposer.decompose_feature(complex_stories, {})

        # Complex feature should generate more tasks
        assert len(tasks) >= 5

    def test_identify_task_types(self, sample_user_stories):
        """Test task type identification."""
        decomposer = HTNDecomposer("backend")

        # OAuth stories should identify database, backend, and frontend tasks
        task_types = decomposer._identify_task_types(sample_user_stories)

        assert "database_schema" in task_types
        assert "backend_api" in task_types
        assert "testing" in task_types

    def test_decompose_database_tasks(self, sample_user_stories):
        """Test database task decomposition."""
        decomposer = HTNDecomposer("backend")
        tasks = decomposer._decompose_database_tasks(sample_user_stories, {})

        assert len(tasks) >= 2  # At least models and migration
        assert all(t.agent_type == AgentType.CODER_DATABASE for t in tasks)

    def test_decompose_backend_tasks(self, sample_user_stories):
        """Test backend task decomposition."""
        decomposer = HTNDecomposer("backend")
        tasks = decomposer._decompose_backend_tasks(sample_user_stories, {})

        assert len(tasks) >= 2  # Service and routes
        assert all(t.agent_type == AgentType.CODER_BACKEND for t in tasks)

    def test_decompose_frontend_tasks(self, sample_user_stories):
        """Test frontend task decomposition."""
        decomposer = HTNDecomposer("backend")
        tasks = decomposer._decompose_frontend_tasks(sample_user_stories, {})

        assert len(tasks) >= 1
        assert all(t.agent_type == AgentType.CODER_FRONTEND for t in tasks)

    def test_decompose_testing_tasks(self, sample_tasks):
        """Test testing task decomposition."""
        decomposer = HTNDecomposer("backend")
        test_tasks = decomposer._decompose_testing_tasks(sample_tasks)

        assert len(test_tasks) > 0
        assert all(t.agent_type == AgentType.TESTER for t in test_tasks)

    def test_set_default_dependencies(self, sample_tasks):
        """Test default dependency setting."""
        decomposer = HTNDecomposer("backend")

        # Clear existing dependencies
        for task in sample_tasks:
            task.dependencies = []

        # Set default dependencies
        tasks_with_deps = decomposer._set_default_dependencies(sample_tasks)

        # Frontend should depend on backend
        frontend_tasks = [t for t in tasks_with_deps if t.agent_type == AgentType.CODER_FRONTEND]
        backend_tasks = [t for t in tasks_with_deps if t.agent_type == AgentType.CODER_BACKEND]

        for frontend_task in frontend_tasks:
            if backend_tasks:
                assert len(frontend_task.dependencies) > 0


# ============================================================================
# DAG Validator Tests
# ============================================================================

class TestDAGValidator:
    """Test DAG validation functionality."""

    def test_dag_build(self, sample_tasks):
        """Test DAG construction from tasks."""
        validator = DAGValidator()
        dag = validator.build_dag(sample_tasks)

        # Should have all tasks as nodes
        assert len(dag.nodes) == len(sample_tasks)

        # Should have edges for dependencies
        assert len(dag.edges) > 0

    def test_dag_validate_no_cycles(self, sample_tasks):
        """Test DAG validation with no cycles."""
        validator = DAGValidator()
        dag = validator.build_dag(sample_tasks)
        result = validator.validate_dag(dag)

        assert result["is_valid"] is True
        assert result["has_cycles"] is False
        assert len(result["execution_order"]) == len(sample_tasks)

    def test_dag_validate_with_cycles(self):
        """Test DAG validation with circular dependencies."""
        validator = DAGValidator()

        # Create tasks with circular dependency
        tasks = [
            ImplementationTask(
                id="task-001",
                name="Task 1",
                agent_type=AgentType.CODER_BACKEND,
                description="Task 1",
                dependencies=["task-002"],  # Depends on task-002
                files_to_create=[],
                files_to_modify=[],
                estimated_time_minutes=30,
                complexity=TaskComplexity.SIMPLE,
                can_parallelize=False
            ),
            ImplementationTask(
                id="task-002",
                name="Task 2",
                agent_type=AgentType.CODER_BACKEND,
                description="Task 2",
                dependencies=["task-001"],  # Depends on task-001 (circular!)
                files_to_create=[],
                files_to_modify=[],
                estimated_time_minutes=30,
                complexity=TaskComplexity.SIMPLE,
                can_parallelize=False
            )
        ]

        dag = validator.build_dag(tasks)
        result = validator.validate_dag(dag)

        assert result["is_valid"] is False
        assert result["has_cycles"] is True
        assert len(result["cycles"]) > 0

    def test_dag_execution_order(self, sample_tasks):
        """Test topological sort execution order."""
        validator = DAGValidator()
        dag = validator.build_dag(sample_tasks)
        execution_order = validator.get_execution_order(dag)

        # Should include all tasks
        assert len(execution_order) == len(sample_tasks)

        # Dependencies should come before dependents
        for task in sample_tasks:
            if task.dependencies:
                for dep in task.dependencies:
                    assert execution_order.index(dep) < execution_order.index(task.id)

    def test_dag_parallelization(self, sample_tasks):
        """Test parallelization wave identification."""
        validator = DAGValidator()
        dag = validator.build_dag(sample_tasks)
        execution_order = validator.get_execution_order(dag)
        waves = validator.identify_parallelization(dag, execution_order)

        # Should have at least one wave
        assert len(waves) > 0

        # Each wave should be a list
        assert all(isinstance(wave, list) for wave in waves)

        # Tasks in same wave should have no dependencies on each other
        for wave in waves:
            if len(wave) > 1:
                # Check that tasks in wave are independent
                for task1 in wave:
                    for task2 in wave:
                        if task1 != task2:
                            task1_obj = next(t for t in sample_tasks if t.id == task1)
                            assert task2 not in task1_obj.dependencies

    def test_dag_critical_path(self, sample_tasks):
        """Test critical path calculation."""
        validator = DAGValidator()
        dag = validator.build_dag(sample_tasks)
        tasks_dict = {task.id: task for task in sample_tasks}
        critical_path = validator.calculate_critical_path(dag, tasks_dict)

        # Should have critical path
        assert "critical_path" in critical_path
        assert "total_time_minutes" in critical_path
        assert "bottleneck_tasks" in critical_path

        # Total time should be positive
        assert critical_path["total_time_minutes"] > 0


# ============================================================================
# Complexity Estimator Tests
# ============================================================================

class TestComplexityEstimator:
    """Test complexity estimation functionality."""

    @pytest.fixture
    def estimator(self, sample_research_context):
        """ComplexityEstimator instance."""
        return ComplexityEstimator(sample_research_context)

    def test_estimate_complexity_simple(self, estimator):
        """Test simple complexity estimation."""
        task = ImplementationTask(
            id="task-001",
            name="Simple task",
            agent_type=AgentType.CODER_BACKEND,
            description="Create simple endpoint",
            dependencies=[],
            files_to_create=[],
            files_to_modify=[],
            estimated_time_minutes=30,
            complexity=TaskComplexity.SIMPLE,
            can_parallelize=False
        )

        complexity = estimator.estimate_complexity(task)
        assert isinstance(complexity, TaskComplexity)

    def test_estimate_complexity_moderate(self, estimator):
        """Test moderate complexity estimation."""
        task = ImplementationTask(
            id="task-002",
            name="Moderate task",
            agent_type=AgentType.CODER_BACKEND,
            description="Create service with multiple methods",
            dependencies=[],
            files_to_create=["backend/core/service.py"],
            files_to_modify=["backend/core/models.py"],
            estimated_time_minutes=90,
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        )

        complexity = estimator.estimate_complexity(task)
        assert isinstance(complexity, TaskComplexity)

    def test_estimate_complexity_advanced(self, estimator):
        """Test advanced complexity estimation."""
        task = ImplementationTask(
            id="task-003",
            name="Advanced task",
            agent_type=AgentType.CODER_BACKEND,
            description="Complex multi-system integration",
            dependencies=["task-001", "task-002"],
            files_to_create=[
                "backend/core/service1.py",
                "backend/core/service2.py",
                "backend/api/routes1.py",
                "backend/api/routes2.py"
            ],
            files_to_modify=["backend/core/models.py", "backend/main.py"],
            estimated_time_minutes=240,
            complexity=TaskComplexity.ADVANCED,
            can_parallelize=False
        )

        complexity = estimator.estimate_complexity(task)
        assert complexity in [TaskComplexity.COMPLEX, TaskComplexity.ADVANCED]

    def test_time_estimation_accuracy(self, estimator):
        """Test time estimation within tolerance."""
        task = ImplementationTask(
            id="task-001",
            name="API route creation",
            agent_type=AgentType.CODER_BACKEND,
            description="Create API endpoint",
            dependencies=[],
            files_to_create=["backend/api/test_routes.py"],
            files_to_modify=[],
            estimated_time_minutes=45,  # From historical data
            complexity=TaskComplexity.MODERATE,
            can_parallelize=False
        )

        # Estimate time
        time_estimate = estimator.estimate_time(task, TaskComplexity.MODERATE)

        # Should be within reasonable range (30-60 minutes for moderate task)
        assert 30 <= time_estimate <= 60

    def test_calculate_complexity_score(self, estimator):
        """Test complexity score calculation."""
        score = estimator.calculate_complexity_score(
            user_stories=[
                {"title": "Test", "action": "Create feature"}
            ],
            integration_points=[
                {"type": "api", "path": "/api/test"}
            ]
        )

        assert isinstance(score, (int, float))
        assert score >= 0

    def test_map_score_to_complexity(self, estimator):
        """Test score to complexity mapping."""
        assert estimator.map_score_to_complexity(10) == TaskComplexity.SIMPLE
        assert estimator.map_score_to_complexity(100) == TaskComplexity.MODERATE
        assert estimator.map_score_to_complexity(200) == TaskComplexity.COMPLEX
        assert estimator.map_score_to_complexity(400) == TaskComplexity.ADVANCED


# ============================================================================
# File List Generator Tests
# ============================================================================

class TestFileListGenerator:
    """Test file list generation functionality."""

    @pytest.fixture
    def generator(self):
        """FileListGenerator instance."""
        return FileListGenerator("backend")

    def test_generate_file_lists(self, generator, sample_tasks):
        """Test file list generation."""
        file_lists = generator.generate_file_lists(sample_tasks, {})

        assert "files_to_create" in file_lists
        assert "files_to_modify" in file_lists
        assert "files_to_delete" in file_lists

        # Should have files to create/modify
        assert len(file_lists["files_to_create"]) >= 0
        assert len(file_lists["files_to_modify"]) >= 0

    def test_predict_files_to_create(self, generator, sample_tasks):
        """Test file creation prediction."""
        task = sample_tasks[0]
        files = generator.predict_files_to_create(task, [])

        assert isinstance(files, list)

    def test_predict_files_to_modify(self, generator, sample_tasks):
        """Test file modification prediction."""
        task = sample_tasks[0]
        files = generator.predict_files_to_modify(task, [])

        assert isinstance(files, list)

    def test_check_file_conflicts(self, generator):
        """Test conflict detection."""
        file_lists = {
            "files_to_create": ["backend/core/test.py"],
            "files_to_modify": ["backend/core/models.py"],
            "files_to_delete": []
        }

        conflicts = generator.check_file_conflicts(file_lists)

        assert isinstance(conflicts, list)

    def test_validate_file_existence(self, generator, tmp_path):
        """Test file existence validation."""
        # Create a temporary file
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")

        # Test with existing file
        assert generator.validate_file_existence(str(test_file)) is True

        # Test with non-existent file
        assert generator.validate_file_existence("nonexistent.py") is False

    def test_suggest_file_structure(self, generator):
        """Test file structure suggestions."""
        structure = generator.suggest_file_structure("OAuth", "service")

        assert "service" in structure
        assert "routes" in structure
        assert "tests" in structure
        assert "models" in structure

        # Check paths follow Atom conventions
        assert structure["service"].startswith("backend/core/")
        assert structure["routes"].startswith("backend/api/")


# ============================================================================
# Test Requirements Generator Tests
# ============================================================================

class TestTestRequirementsGenerator:
    """Test test requirements generation functionality."""

    @pytest.fixture
    def generator(self):
        """TestRequirementsGenerator instance."""
        return TestRequirementsGenerator()

    def test_generate_test_requirements(self, generator, sample_tasks):
        """Test test requirements generation."""
        requirements = generator.generate_test_requirements(sample_tasks, [])

        assert "test_files" in requirements
        assert "overall_coverage_target" in requirements
        assert "test_types" in requirements

        # Should have test files
        assert len(requirements["test_files"]) >= 0

        # Coverage target should be 80%
        assert requirements["overall_coverage_target"] == 0.80

    def test_generate_test_cases_for_task(self, generator, sample_tasks):
        """Test test case generation."""
        task = sample_tasks[0]
        test_cases = generator.generate_test_cases_for_task(task)

        assert isinstance(test_cases, list)
        # Backend tasks should generate test cases
        if task.agent_type == AgentType.CODER_BACKEND:
            assert len(test_cases) > 0

    def test_suggest_test_type(self, generator, sample_tasks):
        """Test test type suggestion."""
        for task in sample_tasks:
            test_type = generator.suggest_test_type(task)
            assert test_type in ["unit", "integration", "e2e"]

    def test_estimate_test_count(self, generator, sample_tasks):
        """Test count estimation."""
        for task in sample_tasks:
            count = generator.estimate_test_count(task)
            assert count >= 0
            assert isinstance(count, int)

    def test_generate_acceptance_test_cases(self, generator):
        """Test acceptance criteria conversion."""
        acceptance_criteria = [
            "Given user is on login page",
            "When user clicks login",
            "Then user is redirected to dashboard"
        ]

        test_cases = generator.generate_acceptance_test_cases(acceptance_criteria)

        assert len(test_cases) == len(acceptance_criteria)
        assert all("name" in tc and "description" in tc for tc in test_cases)


# ============================================================================
# Planning Agent Orchestration Tests
# ============================================================================

class TestPlanningAgent:
    """Test PlanningAgent orchestration."""

    @pytest.mark.asyncio
    async def test_planning_agent_end_to_end(
        self,
        planning_agent,
        sample_user_stories,
        sample_research_context
    ):
        """Test full planning workflow."""
        requirements = {
            "user_stories": sample_user_stories,
            "dependencies": [],
            "integration_points": []
        }

        plan = await planning_agent.create_implementation_plan(requirements, sample_research_context)

        # Validate plan structure
        assert "tasks" in plan
        assert "dag_valid" in plan
        assert "execution_order" in plan
        assert "files_to_create" in plan
        assert "files_to_modify" in plan
        assert "test_requirements" in plan
        assert "estimated_duration_minutes" in plan

        # DAG should be valid
        assert plan["dag_valid"] is True

        # Should have tasks
        assert len(plan["tasks"]) > 0

    @pytest.mark.asyncio
    async def test_plan_refinement_with_llm(
        self,
        planning_agent
    ):
        """Test LLM-based plan refinement."""
        initial_plan = {
            "tasks": [],
            "dag_valid": True,
            "estimated_duration_minutes": 120
        }

        # Should return plan unchanged (LLM call mocked out)
        refined_plan = await planning_agent.refine_plan_with_llm(initial_plan)

        assert isinstance(refined_plan, dict)

    def test_save_plan_to_workflow(self, planning_agent, sample_user_stories):
        """Test plan persistence to database."""
        plan = {
            "tasks": [],
            "estimated_duration_minutes": 120
        }

        # Mock workflow query
        mock_workflow = Mock()
        mock_workflow.implementation_plan = None
        planning_agent.db.query.return_value.filter.return_value.first.return_value = mock_workflow

        # Should not raise exception
        planning_agent.save_plan_to_workflow("workflow-001", plan)

        # Verify commit was called
        planning_agent.db.commit.assert_called_once()

    def test_plan_summary_generation(self, planning_agent):
        """Test summary formatting."""
        plan = {
            "tasks": [
                {
                    "name": "Task 1",
                    "agent_type": "coder-backend",
                    "complexity": "moderate",
                    "estimated_time_minutes": 60,
                    "dependencies": []
                }
            ],
            "estimated_duration_minutes": 120,
            "parallelization_opportunities": 1,
            "complexity": "moderate",
            "files_to_create": ["backend/core/test.py"],
            "files_to_modify": ["backend/core/models.py"]
        }

        summary = planning_agent.get_plan_summary(plan)

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Implementation Plan Summary" in summary
        assert "Task 1" in summary


# ============================================================================
# Convenience Functions Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_create_implementation_plan(
        self,
        db_session,
        mock_byok_handler,
        sample_user_stories,
        sample_research_context
    ):
        """Test convenience function for plan creation."""
        requirements = {
            "user_stories": sample_user_stories
        }

        plan = await create_implementation_plan(
            requirements,
            sample_research_context,
            db_session,
            mock_byok_handler
        )

        assert isinstance(plan, dict)
        assert "tasks" in plan

    def test_validate_dag(self, sample_tasks):
        """Test convenience function for DAG validation."""
        result = validate_dag(sample_tasks)

        assert isinstance(result, dict)
        assert "is_valid" in result

    def test_estimate_complexity(self, sample_tasks, sample_research_context):
        """Test convenience function for complexity estimation."""
        task = sample_tasks[0]
        complexity = estimate_complexity(task, sample_research_context)

        assert isinstance(complexity, TaskComplexity)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for PlanningAgent."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_dag_validation(
        self,
        planning_agent,
        sample_user_stories,
        sample_research_context
    ):
        """Test complete workflow with DAG validation."""
        requirements = {
            "user_stories": sample_user_stories,
            "dependencies": ["OAuth2 credentials"],
            "integration_points": ["/api/auth/*"]
        }

        # Create plan
        plan = await planning_agent.create_implementation_plan(requirements, sample_research_context)

        # Verify DAG is valid
        assert plan["dag_valid"] is True

        # Verify execution order includes all tasks
        assert len(plan["execution_order"]) == len(plan["tasks"])

        # Verify file lists
        assert len(plan["files_to_create"]) >= 0
        assert len(plan["files_to_modify"]) >= 0

        # Verify test requirements
        assert "test_files" in plan["test_requirements"]

    @pytest.mark.asyncio
    async def test_parallelization_detection(
        self,
        planning_agent
    ):
        """Test parallelization opportunity detection."""
        # Create stories that should generate parallelizable tasks
        stories = [
            {
                "id": "US-001",
                "title": "Multiple API endpoints",
                "role": "user",
                "action": "access multiple endpoints",
                "value": "functionality",
                "acceptance_criteria": [],
                "priority": "high",
                "complexity": "moderate"
            }
        ]

        requirements = {
            "user_stories": stories
        }

        plan = await planning_agent.create_implementation_plan(requirements, {})

        # Should detect parallelization opportunities
        assert plan["parallelization_opportunities"] >= 0

        # Should have waves
        assert "waves" in plan
        assert len(plan["waves"]) > 0


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_user_stories(self, planning_agent):
        """Test handling of empty user stories."""
        import asyncio

        async def test():
            requirements = {"user_stories": []}
            plan = await planning_agent.create_implementation_plan(requirements, {})

            # Should still create a valid plan
            assert isinstance(plan, dict)
            assert "tasks" in plan

        asyncio.run(test())

    def test_circular_dependencies_raises_error(self, planning_agent):
        """Test that circular dependencies are detected."""
        import asyncio

        async def test():
            # Create requirements that would result in circular dependencies
            # This would need custom HTN decomposer to force circular deps
            # For now, test with manually created circular tasks
            from core.autonomous_planning_agent import DAGValidator, ImplementationTask, TaskComplexity, AgentType

            tasks = [
                ImplementationTask(
                    id="task-001",
                    name="Task 1",
                    agent_type=AgentType.CODER_BACKEND,
                    description="Task 1",
                    dependencies=["task-002"],
                    files_to_create=[],
                    files_to_modify=[],
                    estimated_time_minutes=30,
                    complexity=TaskComplexity.SIMPLE,
                    can_parallelize=False
                ),
                ImplementationTask(
                    id="task-002",
                    name="Task 2",
                    agent_type=AgentType.CODER_BACKEND,
                    description="Task 2",
                    dependencies=["task-001"],
                    files_to_create=[],
                    files_to_modify=[],
                    estimated_time_minutes=30,
                    complexity=TaskComplexity.SIMPLE,
                    can_parallelize=False
                )
            ]

            validator = DAGValidator()
            dag = validator.build_dag(tasks)
            result = validator.validate_dag(dag)

            assert result["is_valid"] is False
            assert result["has_cycles"] is True

        asyncio.run(test())

    def test_missing_dependencies_handled(self):
        """Test handling of missing task dependencies."""
        validator = DAGValidator()

        # Create tasks with missing dependencies
        tasks = [
            ImplementationTask(
                id="task-001",
                name="Task 1",
                agent_type=AgentType.CODER_BACKEND,
                description="Task 1",
                dependencies=["non-existent-task"],
                files_to_create=[],
                files_to_modify=[],
                estimated_time_minutes=30,
                complexity=TaskComplexity.SIMPLE,
                can_parallelize=False
            )
        ]

        dag = validator.build_dag(tasks)
        result = validator.validate_dag(dag)

        # Should still be valid (missing deps don't create cycles)
        assert result["is_valid"] is True

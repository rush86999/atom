"""
Shared test fixtures for auto_dev tests.

Provides mock LLM service, mock sandbox, test database sessions,
and sample data for testing Auto-Dev components.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.auto_dev.models import SkillCandidate, ToolMutation, WorkflowVariant


# =============================================================================
# Mock LLM Service Fixture
# =============================================================================

@pytest.fixture
def mock_auto_dev_llm():
    """
    Mock LLM service that returns deterministic responses.

    Provides both sync and async call interfaces.
    Supports configurable error modes (rate_limited, timeout).
    Simulates token counting.
    """
    llm = MagicMock()

    # Async generate_completion method
    async def mock_generate_completion(**kwargs):
        messages = kwargs.get("messages", [])
        task_type = kwargs.get("task_type", "general")

        # Deterministic responses based on task type
        if task_type == "code":
            return {
                "content": '''def optimized_function(data):
    """Optimized implementation."""
    return [x * 2 for x in data]
''',
                "tokens": 150,
            }
        elif "skill" in str(messages).lower():
            return {
                "content": '''def new_skill(input_data):
    """Auto-generated skill from failure pattern."""
    result = process_data(input_data)
    return result
''',
                "tokens": 120,
            }
        else:
            return {
                "content": "Generated response based on context.",
                "tokens": 50,
            }

    llm.generate_completion = AsyncMock(side_effect=mock_generate_completion)
    llm.call = AsyncMock(return_value={"content": "LLM response"})

    # Token counting simulation
    llm.count_tokens = Mock(return_value=100)

    # Error mode support
    llm.error_mode = None

    async def error_generate_completion(**kwargs):
        if llm.error_mode == "rate_limited":
            raise Exception("Rate limit exceeded")
        elif llm.error_mode == "timeout":
            raise asyncio.TimeoutError("LLM timeout")
        return await mock_generate_completion(**kwargs)

    llm.generate_completion = AsyncMock(side_effect=error_generate_completion)

    return llm


# =============================================================================
# Mock Sandbox Fixture
# =============================================================================

@pytest.fixture
def mock_sandbox():
    """
    Mock sandbox executor that simulates ContainerSandbox.execute_raw_python().

    Returns configurable success/failure results.
    Tracks execution history for verification.
    Simulates timeout.
    """
    sandbox = MagicMock()
    sandbox.execution_history = []

    async def mock_execute(
        tenant_id: str,
        code: str,
        input_params: dict[str, Any] | None = None,
        timeout: int = 60,
        safety_level: str = "MEDIUM_RISK",
        **kwargs,
    ) -> dict[str, Any]:
        # Track execution
        execution = {
            "tenant_id": tenant_id,
            "code": code[:100],  # Truncate for logging
            "input_params": input_params,
            "timeout": timeout,
        }
        sandbox.execution_history.append(execution)

        # Simulate syntax error
        if "SyntaxError" in code or "syntax error" in code.lower():
            return {
                "status": "failed",
                "output": "SyntaxError: invalid syntax",
                "execution_seconds": 0.1,
                "execution_id": "exec-error-001",
                "environment": "mock",
            }

        # Simulate runtime error
        if "raise" in code and "Exception" in code:
            return {
                "status": "failed",
                "output": "RuntimeError: Simulated error",
                "execution_seconds": 0.2,
                "execution_id": "exec-error-002",
                "environment": "mock",
            }

        # Simulate timeout
        if timeout < 5:
            return {
                "status": "failed",
                "output": f"Execution timed out after {timeout}s",
                "execution_seconds": float(timeout),
                "execution_id": "exec-timeout-001",
                "environment": "mock",
            }

        # Simulate successful execution
        return {
            "status": "success",
            "output": "Execution successful",
            "execution_seconds": 0.5,
            "execution_id": "exec-success-001",
            "environment": "mock",
        }

    sandbox.execute_raw_python = AsyncMock(side_effect=mock_execute)

    return sandbox


# =============================================================================
# Test Database Fixture
# =============================================================================

@pytest.fixture(scope="function")
def auto_dev_db_session():
    """
    Test database session with Auto-Dev models.

    Creates ToolMutation, WorkflowVariant, SkillCandidate tables.
    Transaction rollback after each test.
    Pre-populated test data.
    """
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    from core.auto_dev.models import Base
    Base.metadata.create_all(engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup: rollback and close
    session.rollback()
    session.close()


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_tenant_id():
    """Sample tenant ID for testing."""
    return "tenant-001"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent-001"


@pytest.fixture
def sample_episode_id():
    """Sample episode ID for testing."""
    return "episode-001"


@pytest.fixture
def sample_task_event(sample_tenant_id, sample_agent_id, sample_episode_id):
    """Sample TaskEvent with failure data."""
    from core.auto_dev.event_hooks import TaskEvent

    return TaskEvent(
        episode_id=sample_episode_id,
        agent_id=sample_agent_id,
        tenant_id=sample_tenant_id,
        task_description="Process sales data and generate report",
        error_trace="ValueError: Invalid data format\n  at process_sales(), line 42",
        outcome="failure",
        metadata={
            "tool_name": "process_sales",
            "retry_count": 3,
            "execution_seconds": 5.2,
        },
    )


@pytest.fixture
def sample_skill_execution_event(sample_tenant_id, sample_agent_id):
    """Sample SkillExecutionEvent with metrics."""
    from core.auto_dev.event_hooks import SkillExecutionEvent

    return SkillExecutionEvent(
        execution_id="exec-001",
        agent_id=sample_agent_id,
        tenant_id=sample_tenant_id,
        skill_id="skill-001",
        skill_name="data_processor",
        execution_seconds=8.5,
        token_usage=6500,
        success=True,
        output="Processed 1000 records",
        metadata={
            "input_size": 1000,
            "output_size": 500,
        },
    )


@pytest.fixture
def sample_episode(auto_dev_db_session, sample_agent_id, sample_tenant_id):
    """Sample Episode with tool calls and errors."""
    try:
        from core.models import AgentEpisode

        episode = AgentEpisode(
            id="episode-001",
            agent_id=sample_agent_id,
            tenant_id=sample_tenant_id,
            task_description="Analyze customer data and generate insights",
            maturity_at_time="AUTONOMOUS",  # Required field
            outcome="failure",  # Required field
            success=False,
            status="active",  # Required field
            confidence_score=0.5,
            constitutional_score=1.0,
            human_intervention_count=0,
            step_efficiency=1.0,
            access_count=0,
            importance_score=0.5,
            decay_score=1.0,
            metadata_json={
                "tool_calls": ["analyze_data", "generate_report"],
                "errors": ["TypeError: Invalid format"],
                "total_duration_seconds": 12.5,
            },
        )
        auto_dev_db_session.add(episode)
        auto_dev_db_session.commit()
        auto_dev_db_session.refresh(episode)

        return episode
    except ImportError:
        # Episode model not available in test environment
        return None


@pytest.fixture
def sample_agent(auto_dev_db_session, sample_agent_id, sample_tenant_id):
    """Sample Agent with AUTONOMOUS maturity."""
    try:
        from core.models import AgentRegistry

        agent = AgentRegistry(
            id=sample_agent_id,
            tenant_id=sample_tenant_id,
            name="Test Agent",
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
            metadata_json={},
        )
        auto_dev_db_session.add(agent)
        auto_dev_db_session.commit()
        auto_dev_db_session.refresh(agent)

        return agent
    except ImportError:
        # AgentRegistry model not available in test environment
        return None


@pytest.fixture
def sample_skill_candidate(auto_dev_db_session, sample_tenant_id, sample_agent_id, sample_episode_id):
    """Sample SkillCandidate for testing."""
    candidate = SkillCandidate(
        id="candidate-001",
        tenant_id=sample_tenant_id,
        agent_id=sample_agent_id,
        source_episode_id=sample_episode_id,
        skill_name="auto_data_processor",
        skill_description="Automatically generated skill for data processing",
        generated_code='''def process_data(data):
    """Process data efficiently."""
    return [x * 2 for x in data]
''',
        failure_pattern={
            "error_type": "ValueError",
            "task_description": "Process sales data",
        },
        validation_status="pending",
        fitness_score=None,
    )
    auto_dev_db_session.add(candidate)
    auto_dev_db_session.commit()
    auto_dev_db_session.refresh(candidate)

    return candidate


@pytest.fixture
def sample_workflow_variant(auto_dev_db_session, sample_tenant_id, sample_agent_id):
    """Sample WorkflowVariant for testing."""
    variant = WorkflowVariant(
        id="variant-001",
        tenant_id=sample_tenant_id,
        parent_variant_id=None,
        agent_id=sample_agent_id,
        workflow_definition={
            "steps": [
                {"name": "load_data", "tool": "data_loader"},
                {"name": "process", "tool": "processor"},
            ],
        },
        fitness_score=0.75,
        fitness_signals={
            "proxy": {
                "execution_success": True,
                "syntax_error": False,
                "execution_latency_ms": 1200,
            },
        },
        evaluation_status="evaluated",
    )
    auto_dev_db_session.add(variant)
    auto_dev_db_session.commit()
    auto_dev_db_session.refresh(variant)

    return variant


@pytest.fixture
def sample_tool_mutation(auto_dev_db_session, sample_tenant_id):
    """Sample ToolMutation for testing."""
    mutation = ToolMutation(
        id="mutation-001",
        tenant_id=sample_tenant_id,
        parent_tool_id="tool-001",
        tool_name="data_processor",
        mutated_code='''def optimized_processor(data):
    """Optimized data processor."""
    return [x * 3 for x in data]
''',
        sandbox_status="passed",
        execution_error=None,
    )
    auto_dev_db_session.add(mutation)
    auto_dev_db_session.commit()
    auto_dev_db_session.refresh(mutation)

    return mutation


# =============================================================================
# Workspace Settings Fixture
# =============================================================================

@pytest.fixture
def sample_workspace_settings():
    """Sample workspace settings with Auto-Dev enabled."""
    return {
        "auto_dev": {
            "enabled": True,
            "memento_skills": True,
            "alpha_evolver": True,
            "background_evolution": False,
            "max_mutations_per_day": 10,
            "max_skill_candidates_per_day": 5,
        }
    }


@pytest.fixture
def sample_workspace_settings_disabled():
    """Sample workspace settings with Auto-Dev disabled."""
    return {
        "auto_dev": {
            "enabled": False,
            "memento_skills": False,
            "alpha_evolver": False,
            "background_evolution": False,
        }
    }


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_episode(
    session,
    episode_id: str,
    agent_id: str,
    tenant_id: str,
    task_description: str,
    outcome: str = "failure",
    success: bool = False,
    status: str = "active",
    **kwargs
):
    """Helper function to create test Episode objects with required fields."""
    try:
        from core.models import AgentEpisode

        episode = AgentEpisode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            task_description=task_description,
            maturity_at_time=kwargs.get("maturity_at_time", "AUTONOMOUS"),
            outcome=outcome,
            success=success,
            status=status,
            confidence_score=kwargs.get("confidence_score", 0.5),
            constitutional_score=kwargs.get("constitutional_score", 1.0),
            human_intervention_count=kwargs.get("human_intervention_count", 0),
            step_efficiency=kwargs.get("step_efficiency", 1.0),
            access_count=kwargs.get("access_count", 0),
            importance_score=kwargs.get("importance_score", 0.5),
            decay_score=kwargs.get("decay_score", 1.0),
            metadata_json=kwargs.get("metadata_json", {}),
        )
        session.add(episode)
        session.commit()
        session.refresh(episode)
        return episode
    except ImportError:
        return None

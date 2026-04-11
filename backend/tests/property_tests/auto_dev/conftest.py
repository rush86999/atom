"""
Property-Based Testing Configuration for Auto-Dev

This module provides Hypothesis strategies and pytest fixtures for testing
Auto-Dev components (EventBus, FitnessService, CapabilityGate, ContainerSandbox,
MementoEngine, Database Models).

Property-based testing generates hundreds of test cases automatically to verify
invariants that must ALWAYS hold true.
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from hypothesis import strategies as st
import pytest
from datetime import datetime, timedelta
from typing import Any

# =============================================================================
# Hypothesis Strategies for Auto-Dev Data Types
# =============================================================================

# Fitness score strategy (normalized to [0.0, 1.0])
fitness_scores = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=100
)

# Maturity level strategy
maturity_levels = st.sampled_from(['student', 'intern', 'supervised', 'autonomous'])

# Event data strategy (random dictionaries with string keys and mixed values)
event_data = st.dictionaries(
    keys=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
    values=st.one_of(
        st.text(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none()
    ),
    min_size=0,
    max_size=20
)

# Capability strategy
capabilities = st.sampled_from([
    'file_operations',
    'network_access',
    'system_commands',
    'database_write',
    'api_calls',
    'user_interaction',
    'auto_dev.memento_skills',
    'auto_dev.alpha_evolver',
    'auto_dev.background_evolution'
])

# Valid skill name strategy (alphanumeric with underscores)
valid_skill_names = st.text(min_size=1, max_size=50).filter(
    lambda x: x.replace('_', '').replace('-', '').isalnum() and len(x) > 0
)

# Agent ID strategy (UUID-like strings)
agent_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Tenant ID strategy
tenant_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Episode ID strategy
episode_ids = st.text(min_size=36, max_size=36, alphabet='abcdef0123456789-')

# Proxy signals strategy (for FitnessService)
proxy_signals = st.dictionaries(
    keys=st.sampled_from([
        'execution_success',
        'syntax_error',
        'execution_latency_ms',
        'user_approved_proposal',
        'expects_delayed_eval'
    ]),
    values=st.one_of(st.booleans(), st.floats(min_value=0.0, max_value=10000.0)),
    min_size=1,
    max_size=5
)

# External signals strategy (for FitnessService webhook evaluation)
external_signals = st.dictionaries(
    keys=st.sampled_from([
        'invoice_created',
        'crm_conversion',
        'conversion_success',
        'email_bounce',
        'error_signal',
        'conversion_value'
    ]),
    values=st.one_of(st.booleans(), st.floats(min_value=0.0, max_value=10000.0)),
    min_size=1,
    max_size=6
)

# Workspace settings strategy (for CapabilityGate)
workspace_settings = st.dictionaries(
    keys=st.sampled_from([
        'auto_dev',
        'max_mutations_per_day',
        'max_skill_candidates_per_day',
        'enabled'
    ]),
    values=st.one_of(
        st.booleans(),
        st.integers(min_value=1, max_value=100),
        st.dictionaries(
            keys=st.sampled_from(['enabled', 'memento_skills', 'alpha_evolver', 'background_evolution']),
            values=st.one_of(st.booleans(), st.integers(min_value=1, max_value=100)),
            min_size=1,
            max_size=4
        )
    ),
    min_size=0,
    max_size=4
)

# =============================================================================
# Pytest Fixtures for Auto-Dev Components
# =============================================================================

@pytest.fixture
def event_bus():
    """Provide EventBus instance for testing."""
    from core.auto_dev.event_hooks import EventBus
    bus = EventBus()
    yield bus
    bus.clear()  # Clean up after test


@pytest.fixture
def fitness_service(db_session):
    """Provide FitnessService instance for testing."""
    from core.auto_dev.fitness_service import FitnessService
    return FitnessService(db_session)


@pytest.fixture
def capability_gate(db_session):
    """Provide AutoDevCapabilityService instance for testing."""
    from core.auto_dev.capability_gate import AutoDevCapabilityService
    return AutoDevCapabilityService(db_session)


@pytest.fixture
def container_sandbox():
    """Provide ContainerSandbox instance for testing."""
    from core.auto_dev.container_sandbox import ContainerSandbox
    return ContainerSandbox()


@pytest.fixture
def memento_engine(db_session):
    """Provide MementoEngine instance for testing."""
    from core.auto_dev.memento_engine import MementoEngine
    return MementoEngine(db_session)


@pytest.fixture
def db_session():
    """
    Provide a test database session with automatic rollback.

    This fixture creates a new database session for each test and ensures
    all changes are rolled back after the test completes.
    """
    from core.models import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_agent(db_session):
    """Create a sample agent for testing."""
    from core.models import AgentRegistry
    import uuid

    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="test_agent",
        role="assistant",
        maturity="student",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def sample_workspace_settings():
    """Provide sample workspace settings for testing."""
    return {
        "auto_dev": {
            "enabled": True,
            "memento_skills": True,
            "alpha_evolver": True,
            "background_evolution": False,
            "max_mutations_per_day": 10,
            "max_skill_candidates_per_day": 5
        }
    }


# =============================================================================
# Test Helpers
# =============================================================================

def create_task_event(
    episode_id: str = None,
    agent_id: str = None,
    tenant_id: str = None,
    outcome: str = "success"
) -> Any:
    """Helper to create TaskEvent objects for testing."""
    from core.auto_dev.event_hooks import TaskEvent
    import uuid

    return TaskEvent(
        episode_id=episode_id or str(uuid.uuid4()),
        agent_id=agent_id or str(uuid.uuid4()),
        tenant_id=tenant_id or str(uuid.uuid4()),
        task_description="Test task",
        outcome=outcome,
        metadata={"test": True}
    )


def create_skill_execution_event(
    execution_id: str = None,
    agent_id: str = None,
    tenant_id: str = None,
    success: bool = True
) -> Any:
    """Helper to create SkillExecutionEvent objects for testing."""
    from core.auto_dev.event_hooks import SkillExecutionEvent
    import uuid

    return SkillExecutionEvent(
        execution_id=execution_id or str(uuid.uuid4()),
        agent_id=agent_id or str(uuid.uuid4()),
        tenant_id=tenant_id or str(uuid.uuid4()),
        skill_id="test_skill",
        skill_name="Test Skill",
        execution_seconds=1.5,
        token_usage=100,
        success=success,
        output="Test output"
    )


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "property: Mark test as property-based test using Hypothesis"
    )
    config.addinivalue_line(
        "markers",
        "slow: Mark test as slow-running (integration tests, Docker-dependent)"
    )
    config.addinivalue_line(
        "markers",
        "docker_required: Mark test as requiring Docker (ContainerSandbox tests)"
    )

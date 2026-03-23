"""Test worker isolation fixtures."""
import os
import pytest


def test_worker_database_fixture(worker_database):
    """Test that worker_database fixture provides session factory."""
    # worker_database is a session factory
    SessionLocal = worker_database
    assert SessionLocal is not None
    
    # Create a session
    session = SessionLocal()
    assert session is not None
    session.close()


def test_db_session_uses_worker_database(db_session):
    """Test that db_session uses worker_database for isolation."""
    # db_session should provide a working session
    from core.models import AgentRegistry
    
    # Create an agent
    agent = AgentRegistry(
        id="test_agent_123",
        name="Test Agent",
        category="test",
        module_path="test.module",
        class_name="TestClass"
    )
    db_session.add(agent)
    db_session.commit()
    
    # Verify agent exists in this session
    retrieved = db_session.query(AgentRegistry).filter_by(id="test_agent_123").first()
    assert retrieved is not None
    assert retrieved.name == "Test Agent"


def test_unique_resource_name_has_worker_id(unique_resource_name):
    """Test that unique_resource_name includes worker ID."""
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    assert worker_id in unique_resource_name, f"Worker ID {worker_id} not in {unique_resource_name}"


def test_parallel_agents_dont_conflict(unique_resource_name, db_session):
    """Test that parallel tests with unique IDs don't conflict."""
    from core.models import AgentRegistry
    
    # Each test gets a unique resource name with worker ID
    agent_id = f"agent_{unique_resource_name}"
    
    agent = AgentRegistry(
        id=agent_id,
        name=f"Agent {agent_id}",
        category="test",
        module_path="test.module",
        class_name="TestClass"
    )
    db_session.add(agent)
    db_session.commit()
    
    # Verify this agent exists
    retrieved = db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert retrieved is not None

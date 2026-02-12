"""
Scenario test fixtures.

Extends security/conftest.py fixtures for scenario testing.
"""
import pytest
from sqlalchemy.orm import Session
from tests.factories.user_factory import MemberUserFactory
from core.auth import create_access_token
from core.models import User, AgentRegistry, AgentStatus, WorkflowTemplate

# Import db_session directly from property_tests to avoid circular import
from tests.property_tests.conftest import db_session

# Import other fixtures from security/conftest (avoiding db_session which creates circular import)
from tests.security.conftest import (
    test_user_with_password,
    valid_auth_token,
    admin_user,
    admin_token,
)


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a FastAPI TestClient for testing API endpoints.
    """
    from fastapi.testclient import TestClient
    from core.database import get_db
    from main_api_app import app

    # Override the database dependency
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def member_token(db_session: Session) -> str:
    """Create authentication token for regular member user."""
    user = MemberUserFactory(_session=db_session)
    return create_access_token(data={"sub": str(user.id)})


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        role="member"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_agent(db_session: Session):
    """Create a test agent with default settings."""
    agent = AgentRegistry(
        name="TestAgent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence=0.5,
        capabilities=["test_capability"],
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def supervised_agent(db_session: Session):
    """Create a SUPERVISED maturity level agent."""
    agent = AgentRegistry(
        name="SupervisedAgent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.SUPERVISED.value,
        confidence=0.8,
        capabilities=["test_capability"],
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def template_factory(db_session: Session):
    """Factory for creating workflow templates."""
    def _create(**kwargs):
        template = WorkflowTemplate(
            name=kwargs.get("name", "Test Template"),
            description=kwargs.get("description", "Test description"),
            created_by=kwargs.get("created_by", "test_user"),
            steps=kwargs.get("steps", [{"id": "step1", "action": "test"}])
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template
    return _create


# Re-export fixtures from security/conftest for convenience
__all__ = [
    "client",
    "db_session",
    "test_user_with_password",
    "valid_auth_token",
    "admin_user",
    "admin_token",
    "member_token",
    "test_user",
    "test_agent",
    "supervised_agent",
    "template_factory",
]

"""
API-first fixtures for fast test initialization.

This module provides pytest fixtures that use API calls to quickly set up
test data, bypassing slow UI navigation (10-100x speedup).
"""

import pytest
from typing import Dict, Any
from sqlalchemy.orm import Session

from tests.e2e_ui.utils.api_setup import (
    APIClient,
    create_test_user,
    authenticate_user,
    get_test_user_token,
    create_test_project,
    install_test_skill
)


# ============================================================================
# Base Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Get the base URL for API requests.

    Returns:
        Base URL (default: http://localhost:8001)
    """
    return "http://localhost:8001"


@pytest.fixture(scope="function")
def api_client(api_base_url: str) -> APIClient:
    """
    Provide an API client instance for making HTTP requests.

    Args:
        api_base_url: Base URL for API requests

    Returns:
        APIClient instance
    """
    return APIClient(base_url=api_base_url)


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_user_data() -> Dict[str, str]:
    """
    Provide test user data for creating a user.

    Returns:
        Dictionary with user email, password, first_name, last_name
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test-{unique_id}@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": f"User{unique_id}"
    }


@pytest.fixture(scope="function")
def setup_test_user(api_client: APIClient, test_user_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Create a test user via API and return user data with token.

    This fixture bypasses UI login for 10-100x speedup.

    Args:
        api_client: APIClient instance
        test_user_data: User data dictionary

    Returns:
        Dictionary with user data and access_token

    Example:
        def test_example(setup_test_user):
            user = setup_test_user["user"]
            token = setup_test_user["access_token"]
    """
    # Create user via API
    user_response = create_test_user(
        client=api_client,
        email=test_user_data["email"],
        password=test_user_data["password"],
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"]
    )

    # Authenticate and get token
    token = get_test_user_token(
        client=api_client,
        email=test_user_data["email"],
        password=test_user_data["password"]
    )

    return {
        "user": user_response.get("user", user_response),
        "access_token": token,
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    }


@pytest.fixture(scope="function")
def authenticated_api_client(api_client: APIClient, setup_test_user: Dict[str, Any]) -> APIClient:
    """
    Provide an API client with authentication token already set.

    Args:
        api_client: APIClient instance
        setup_test_user: User data with access_token

    Returns:
        APIClient instance with token set
    """
    token = setup_test_user["access_token"]
    api_client.set_token(token)
    return api_client


# ============================================================================
# Project Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_project_data() -> Dict[str, str]:
    """
    Provide test project data.

    Returns:
        Dictionary with project name and description
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return {
        "name": f"Test Project {unique_id}",
        "description": f"Test project description {unique_id}"
    }


@pytest.fixture(scope="function")
def setup_test_project(authenticated_api_client: APIClient, test_project_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Create a test project via API and return project data.

    Args:
        authenticated_api_client: Authenticated APIClient instance
        test_project_data: Project data dictionary

    Returns:
        Project data response from API

    Example:
        def test_example(setup_test_project):
            project = setup_test_project["project"]
            project_id = project["id"]
    """
    response = create_test_project(
        client=authenticated_api_client,
        name=test_project_data["name"],
        description=test_project_data["description"]
    )

    return {
        "project": response.get("project", response),
        "name": test_project_data["name"],
        "description": test_project_data["description"]
    }


# ============================================================================
# Skill Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_skill_data() -> Dict[str, str]:
    """
    Provide test skill data.

    Returns:
        Dictionary with skill_id and agent_id
    """
    return {
        "skill_id": "test-skill-001",
        "agent_id": "test-agent-001"
    }


@pytest.fixture(scope="function")
def setup_test_skill(authenticated_api_client: APIClient, test_skill_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Install a test skill via API and return skill data.

    Args:
        authenticated_api_client: Authenticated APIClient instance
        test_skill_data: Skill data dictionary

    Returns:
        Skill installation response from API

    Example:
        def test_example(setup_test_skill):
            result = setup_test_skill["result"]
            skill_id = result.get("skill_id")
    """
    response = install_test_skill(
        client=authenticated_api_client,
        skill_id=test_skill_data["skill_id"],
        agent_id=test_skill_data["agent_id"]
    )

    return {
        "result": response,
        "skill_id": test_skill_data["skill_id"],
        "agent_id": test_skill_data["agent_id"]
    }


# ============================================================================
# Agent Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_agent_data() -> Dict[str, str]:
    """
    Provide test agent data for creating agents.

    Returns:
        Dictionary with agent_id, name, status (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)

    Example:
        def test_example(test_agent_data):
            agent_id = test_agent_data["agent_id"]
            status = test_agent_data["status"]
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return {
        "agent_id": f"test-agent-{unique_id}",
        "name": f"Test Agent {unique_id}",
        "category": "testing",
        "module_path": "backend/test_agents",
        "class_name": "TestAgent",
        "description": f"Test agent for E2E testing {unique_id}",
        "status": "STUDENT"  # Default to STUDENT maturity
    }


@pytest.fixture(scope="function")
def setup_test_agent(test_agent_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Create a test agent via database and return agent data.

    This fixture bypasses UI agent creation for 10-100x speedup.
    Uses direct database access via db_session fixture.

    Args:
        test_agent_data: Agent data dictionary

    Returns:
        Dictionary with agent data including agent_id, name, status

    Example:
        def test_example(setup_test_agent):
            agent = setup_test_agent["agent"]
            agent_id = setup_test_agent["agent_id"]
    """
    import sys
    import os
    # Add backend to path for imports
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from core.models import AgentRegistry, AgentStatus
    from sqlalchemy.orm import Session

    # Import db_session fixture - we need to use pytest's request fixture
    # to get the db_session dynamically
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://atom:atom_test@localhost:5432/atom_test"
    )

    # Create engine and session
    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Create agent directly in database
        agent = AgentRegistry(
            name=test_agent_data["name"],
            category=test_agent_data["category"],
            module_path=test_agent_data["module_path"],
            class_name=test_agent_data["class_name"],
            description=test_agent_data["description"],
            status=AgentStatus[test_agent_data["status"].upper()].value,
            confidence_score=0.5  # Default confidence score
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)

        return {
            "agent": agent,
            "agent_id": str(agent.id),
            "name": agent.name,
            "status": agent.status,
            "category": agent.category
        }
    finally:
        db.close()


def create_test_agent_direct(db: Session, name: str, status: str, category: str = "testing", confidence_score: float = 0.5) -> Dict[str, Any]:
    """
    Helper function to create an agent with specified maturity level directly in database.

    This is a convenience function for inline agent creation in tests.
    Uses direct database session for fast agent creation without API calls.

    Args:
        db: SQLAlchemy database session
        name: Agent name
        status: Agent maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        category: Agent category (default: "testing")
        confidence_score: Agent confidence score (default: 0.5)

    Returns:
        Dictionary with agent_id and confirmation

    Example:
        agent = create_test_agent_direct(db, "My Student Agent", "STUDENT")
        agent_id = agent["agent_id"]
    """
    import uuid
    from core.models import AgentRegistry, AgentStatus

    unique_id = str(uuid.uuid4())[:8]

    # Create agent directly in database
    agent = AgentRegistry(
        name=name,
        category=category,
        module_path="backend/test_agents",
        class_name="TestAgent",
        description=f"Test agent {name}",
        status=AgentStatus[status.upper()].value,
        confidence_score=confidence_score
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    return {
        "agent_id": str(agent.id),
        "agent": agent,
        "name": name,
        "status": status,
        "category": category,
        "success": True
    }


# ============================================================================
# Combined Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def setup_full_test_state(
    authenticated_api_client: APIClient,
    setup_test_project: Dict[str, Any],
    setup_test_skill: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Set up complete test state with user, project, and skill.

    This fixture provides a fully initialized test state without any UI navigation.

    Args:
        authenticated_api_client: Authenticated APIClient instance
        setup_test_project: Project data
        setup_test_skill: Skill data

    Returns:
        Dictionary with all test data

    Example:
        def test_example(setup_full_test_state):
            project = setup_full_test_state["project"]
            skill = setup_full_test_state["skill"]
    """
    return {
        "project": setup_test_project["project"],
        "skill": setup_test_skill["result"],
        "client": authenticated_api_client
    }

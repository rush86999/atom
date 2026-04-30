"""
Pytest configuration and fixtures for regression tests.

This module provides test database setup with automatic table creation
for regression testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base
from fastapi.testclient import TestClient
from main import app
from core.database import get_db


@pytest.fixture(scope="function")
def db_engine():
    """
    Create a file-based SQLite database engine for testing.

    This fixture creates a fresh database for each test function,
    ensuring complete isolation between tests.

    Uses file-based storage to ensure TestClient database connections
    can see the same tables (fixes :memory: connection isolation issue).
    """
    import tempfile
    import os

    # Create temp file for database
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Drop all tables and remove file after test
    Base.metadata.drop_all(engine)
    engine.dispose()
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture(scope="function")
def db(db_engine):
    """
    Create a database session for test operations.

    This fixture provides a clean database session with automatic
    rollback after each test to maintain test isolation.
    """
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()

    yield session

    # Cleanup: Close session and rollback any uncommitted changes
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """
    Create a FastAPI TestClient with test database override.

    This fixture overrides the get_db dependency to use the test database
    instead of the production database, ensuring tests don't affect real data.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # Don't close - fixture manages lifecycle

    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create test client
    test_client = TestClient(app)

    yield test_client

    # Clean up override
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client):
    """
    Create authentication headers for test requests.

    This fixture creates a test user and returns auth headers.
    """
    # Create test user
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User"
        }
    )

    # Login to get token
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpass123"
        }
    )

    token = login_response.json().get("data", {}).get("token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def test_agent(client, auth_headers):
    """
    Create a test agent for testing.

    This fixture creates a test agent and returns its ID.
    """
    response = client.post(
        "/api/agents/custom",
        json={
            "name": "Test Agent",
            "description": "A test agent",
            "category": "testing",
            "configuration": {"test": True}
        },
        headers=auth_headers
    )

    agent_data = response.json().get("data", {})
    agent_id = agent_data.get("id", "")

    # Return an object with id attribute
    class TestAgent:
        def __init__(self, id):
            self.id = id

    return TestAgent(agent_id)

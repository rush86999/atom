"""
Pytest configuration and fixtures for property tests.

This module provides test database setup with automatic table creation
for property-based testing.
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
    Create an in-memory SQLite database engine for testing.

    This fixture creates a fresh database for each test function,
    ensuring complete isolation between tests.
    """
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Drop all tables after test
    Base.metadata.drop_all(engine)


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

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


@pytest.fixture(scope="function", autouse=True)
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

    # Reconfigure SessionLocal to bind to the test engine
    import core.database
    core.database.SessionLocal.configure(bind=engine)

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
def db_session(db_engine):
    """
    Create a database session scoped to a single test function.

    This is a thin alias around `db_engine` that other conftest files
    (security/, scenarios/, integration/websocket/, integration/test_websocket_integration)
    import via `from tests.property_tests.conftest import db_session`.
    It mirrors the `db` fixture but uses the explicit Session context manager
    pattern for clean teardown.
    """
    SessionLocal = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = SessionLocal()

    yield session

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

"""
Pytest configuration and fixtures
"""

import os
import sys
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main_api_app import app

from core.database import Base, get_db

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    # Create all tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up after test
        db.rollback()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with a database session"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services to prevent real API calls"""
    with patch('dotenv.load_dotenv'):
        yield


@pytest.fixture(autouse=True, scope="session")
def clean_test_databases():
    """Clean up test databases before and after test session"""
    # Clean up before tests
    import os
    db_files = [
        "./test.db",
        "./atom.db",
        "./atom_dev.db",
        "./analytics.db",
    ]
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)

    yield

    # Clean up after tests
    for db_file in db_files:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except:
                pass

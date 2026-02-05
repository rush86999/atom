"""
Pytest configuration and fixtures
"""

import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main_api_app import app

from core.database import Base, get_db

# Import all models so they're registered with Base.metadata
# Must import models that inherit from Base before creating tables
from core.models import (
    AgentRegistry, AgentExecution, AgentFeedback,
    AgentOperationTracker, AgentRequestLog, CanvasAudit,
    Episode, EpisodeSegment, EpisodeAccessLog,
    User, UserRole, Workspace,
    WorkflowExecution, WorkflowExecutionStatus
)

# Test database (sync)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async test database
SQLALCHEMY_TEST_DATABASE_URL_ASYNC = "sqlite+aiosqlite:///./test_async.db"
async_engine = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL_ASYNC, connect_args={"check_same_thread": False}
)
AsyncTestingSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # If index already exists, recreate tables one by one to avoid conflicts
        if "already exists" in str(e):
            from core.database import get_database_url
            import re

            # Extract database name from URL
            db_url = get_database_url()
            db_name = re.search(r'sqlite:///\.?/?([^/]+\.db)', db_url)
            if db_name:
                db_file = db_name.group(1)
                if os.path.exists(db_file):
                    os.remove(db_file)
                    # Try creating tables again
                    Base.metadata.create_all(bind=engine)
            else:
                raise
        else:
            raise

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
    db_files = [
        "./test.db",
        "./test_async.db",
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


@pytest.fixture(autouse=True)
async def async_setup():
    """Setup async database for tests that need it"""
    # Create all tables
    async with async_engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.drop_all)
        except:
            pass
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up
    async with async_engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.drop_all)
        except:
            pass


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest_asyncio.fixture
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh async database session for tests that need it"""
    async with AsyncTestingSessionLocal() as session:
        yield session

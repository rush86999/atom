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
    DeviceNode,
    Episode, EpisodeSegment, EpisodeAccessLog,
    User, UserRole, Workspace,
    WorkflowExecution, WorkflowExecutionStatus,
    MobileDevice, OfflineAction, SyncState
)

# Test database (sync)
import os
test_db_path = os.path.join(os.path.dirname(__file__), "..", "test.db")
SQLALCHEMY_TEST_DATABASE_URL = f"sqlite:///{test_db_path}"
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
    import logging
    logger = logging.getLogger(__name__)

    # Remove test database file if it exists to ensure clean state
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Create all tables - create individually to handle errors gracefully
    created_count = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
            created_count += 1
        except Exception as e:
            # Log error but continue creating other tables
            logger.warning(f"Warning creating table {table.name}: {e}")

    logger.warning(f"[MENUBAR TEST] Created {created_count}/{len(Base.metadata.tables)} tables")

    # Debug: Verify critical tables exist
    import sqlite3
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('agent_executions', 'canvas_audit', 'device_nodes')")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    logger.warning(f"[MENUBAR TEST] Critical tables created: {tables}")

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up after test - remove database file to ensure fresh state
        db.rollback()
        Base.metadata.drop_all(bind=engine)
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


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


@pytest.fixture
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

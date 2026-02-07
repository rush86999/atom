"""
Shared fixtures for property-based tests.

Provides database sessions, test agents, and common test data for Hypothesis tests.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import Base
from core.models import AgentRegistry, AgentStatus


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs.
    """
    # Use in-memory SQLite for fast, isolated tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables, ignoring duplicate index errors
    # This is a workaround for duplicate index definitions in models
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        if "already exists" in str(e):
            # Ignore duplicate index errors
            pass
        else:
            raise

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def test_agent(db_session: Session):
    """
    Create a test agent with default settings.
    """
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
def test_agents(db_session: Session):
    """
    Create multiple test agents with different maturity levels.
    """
    agents = []
    for status in AgentStatus:
        agent = AgentRegistry(
            name=f"TestAgent_{status.value}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status.value,
            confidence=0.5,
            capabilities=["test_capability"],
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)
        agents.append(agent)

    return agents

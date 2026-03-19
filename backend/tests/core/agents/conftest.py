"""
Agent service test fixtures.

Provides fixtures for agent graduation service testing.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession,
    SkillExecution,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs by using a
    temporary SQLite database file that is deleted after each test.
    Each test gets its own database, preventing UNIQUE constraint violations
    and state leakage between tests.
    """
    # Use file-based temp SQLite for tests to ensure all connections see the same database
    # In-memory SQLite (:memory:) creates a separate database for each connection
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor, we just need the path

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create all tables, handling missing foreign key references from optional modules
    # Same approach as property_tests conftest.py
    tables_created = 0
    tables_skipped = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            tables_created += 1
        except exc.NoReferencedTableError:
            # Skip tables with missing FK references (from optional modules)
            tables_skipped += 1
            continue
        except (exc.CompileError, exc.UnsupportedCompilationError):
            # Skip tables with unsupported types (JSONB in SQLite)
            tables_skipped += 1
            continue
        except Exception as e:
            # Ignore duplicate table/index errors
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            else:
                raise

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass  # File might already be deleted


@pytest.fixture
def test_agent_student(db_session):
    """Create a test STUDENT agent."""
    agent = AgentRegistry(
        id="test-agent-student",
        name="Test Student Agent",
        status=AgentStatus.STUDENT,
        tenant_id="default",
        created_at=datetime.now()
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_agent_intern(db_session):
    """Create a test INTERN agent."""
    agent = AgentRegistry(
        id="test-agent-intern",
        name="Test Intern Agent",
        status=AgentStatus.INTERN,
        tenant_id="default",
        created_at=datetime.now()
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_agent_supervised(db_session):
    """Create a test SUPERVISED agent."""
    agent = AgentRegistry(
        id="test-agent-supervised",
        name="Test Supervised Agent",
        status=AgentStatus.SUPERVISED,
        tenant_id="default",
        created_at=datetime.now()
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_episodes_for_intern(db_session, test_agent_intern):
    """Create test episodes for INTERN promotion."""
    agent_id = test_agent_intern.id
    episodes = []

    for i in range(15):  # More than minimum 10 for INTERN
        episode = Episode(
            id=f"episode-{i}",
            agent_id=agent_id,
            title=f"Episode {i}",
            maturity_at_time="INTERN",
            status="completed",
            human_intervention_count=1,  # Low interventions (10% rate)
            constitutional_score=0.85,  # Above 0.70 threshold
            started_at=datetime.now() - timedelta(days=i+1)
        )
        db_session.add(episode)
        episodes.append(episode)

    db_session.commit()
    return episodes


@pytest.fixture
def test_supervision_sessions(db_session, test_agent_supervised):
    """Create test supervision sessions."""
    agent_id = test_agent_supervised.id
    sessions = []

    for i in range(5):
        session = SupervisionSession(
            id=f"session-{i}",
            agent_id=agent_id,
            agent_name="Test Supervised Agent",
            supervisor_id="supervisor-123",
            workspace_id="default",
            status="completed",
            started_at=datetime.now() - timedelta(hours=i+1),
            duration_seconds=3600,  # 1 hour each
            intervention_count=1,
            supervisor_rating=4.5
        )
        db_session.add(session)
        sessions.append(session)

    db_session.commit()
    return sessions

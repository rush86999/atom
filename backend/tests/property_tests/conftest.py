"""
Shared fixtures for property-based tests.

Provides database sessions, test agents, and common test data for Hypothesis tests.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports to prevent
# recursion in models_registration.py during test setup
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings, HealthCheck
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker


# ============================================================================
# HYPOTHESIS PROPERTY-BASED TESTING SETTINGS
# ============================================================================
#
# Property tests run with max_examples iterations to comprehensively validate
# invariants. For CI optimization, we use fewer examples (50) vs local (200).
#
# Performance targets (see TESTING_GUIDE.md):
# - Fast tier: <10s (simple invariants)
# - Medium tier: <60s (database operations)
# - Slow tier: <100s (complex system invariants)
#
# Usage in tests:
#   @given(...)
#   @settings(DEFAULT_PROFILE)
#   def test_something(...):
#       ...
# ============================================================================

# CI profile: faster tests with fewer examples
ci_profile = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# Local profile: thorough testing with more examples
local_profile = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow]
)

# Auto-select based on environment
# In CI (GitHub Actions, GitLab CI, etc.), use max_examples=50
# In local development, use max_examples=200 for thorough testing
DEFAULT_PROFILE = ci_profile if os.getenv("CI") else local_profile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import Base
# Import main app for TestClient
from main_api_app import app
from core.models import (
    AgentRegistry, AgentStatus, AgentExecution, AgentFeedback,
    Episode, EpisodeSegment, EpisodeAccessLog,
    AgentProposal, ProposalStatus, ProposalType,
    SupervisionSession, SupervisionStatus,
    BlockedTriggerContext,
    TrainingSession,
    TriggerSource,
    User,
    WorkflowExecution,
    ActiveToken,
    RevokedToken
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs.
    """
    # Flag to ensure warning is only logged once per test run
    global _tables_warning_logged
    if '_tables_warning_logged' not in globals():
        _tables_warning_logged = False

    # Use in-memory SQLite for fast, isolated tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables, handling missing foreign key references from optional modules
    # Optional modules (accounting, service_delivery, saas, ecommerce) may have
    # foreign key references to tables that aren't imported during testing.
    # We create tables one by one and skip those with missing dependencies.
    #
    # IMPORTANT: Don't use Base.metadata.create_all() because it will raise
    # NoReferencedTableError which pytest captures as a test setup ERROR even
    # if we catch and handle it. Instead, create tables individually.
    import warnings
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
        except Exception as e:
            # Ignore other errors (like duplicate index definitions)
            # These don't prevent tests from running
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                # Table or index already exists - this is fine
                continue
            else:
                # Re-raise unexpected exceptions
                raise

    # Log what happened (only once per test run)
    if tables_skipped > 0 and not _tables_warning_logged:
        warnings.warn(
            f"Skipping {tables_skipped} tables with missing foreign key references "
            f"from optional modules. Created {tables_created} core tables.",
            UserWarning
        )
        _tables_warning_logged = True

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
        confidence_score=0.5,
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
            confidence_score=0.5,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)
        agents.append(agent)

    return agents


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a FastAPI TestClient for testing API endpoints.
    """
    from core.dependency import get_db

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

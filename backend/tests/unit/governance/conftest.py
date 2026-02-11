"""
Fixtures for unit tests in governance directory.

Provides database session and common test data.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.database import Base
# Import all models to ensure they're registered with Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentProposal,
    ProposalStatus,
    ProposalType,
    SupervisionSession,
    SupervisionStatus,
    BlockedTriggerContext,
    TrainingSession,
    TriggerSource,
    User,
    UserRole,
)


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

    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        if "already exists" in str(e):
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
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        name="Test User",
        role=UserRole.MEMBER.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

"""
Fixtures for unit tests in governance directory.

Provides database session and common test data.
"""

import pytest
import uuid
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
    Workspace,  # line 151 in models.py - needed for student_training_service tests
    ChatSession,  # line 970 in models.py - needed for session management tests
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

    # Create all tables individually to handle duplicate index errors gracefully
    # models.py has duplicate index definitions that cause create_all to fail partway through
    # By creating tables one-by-one, we ensure all tables are created even if some have index issues
    created_count = 0
    skipped_count = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
            created_count += 1
        except Exception as e:
            # Table already exists or has index issues - skip
            skipped_count += 1

    print(f"\n[DEBUG] Created {created_count} tables, skipped {skipped_count} with errors")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()

    # ServiceFactory caches session-bound services in thread-local
    # (get_episode_service/get_governance_service/get_context_resolver).
    # Without clearing this, a later test reuses a service bound to THIS
    # test's disposed in-memory engine -> "no such table: <x>".
    from core.service_factory import ServiceFactory
    for attr in ("episode_service", "governance_service", "context_resolver",
                 "guardrails_service", "memory_consolidation_service",
                 "activity_publisher", "knowledge_extractor", "graphrag_engine"):
        if hasattr(ServiceFactory._thread_local, attr):
            delattr(ServiceFactory._thread_local, attr)


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email=f"test-{uuid.uuid4()}@example.com", role=UserRole.MEMBER.value, first_name="Test", last_name="User", status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

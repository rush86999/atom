"""
Fixtures for systems-level coverage tests.

Provides database session and common test data with proper schema.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime

from core.database import Base
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
    Tenant,
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

    # Create all tables individually to handle JSONB type issues
    # SQLite doesn't support JSONB, so we need to handle this gracefully
    created_count = 0
    skipped_count = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
            created_count += 1
        except Exception as e:
            # Table has JSONB columns or other issues - skip
            skipped_count += 1

    print(f"\n[DEBUG] Created {created_count} tables, skipped {skipped_count} with errors")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Create default tenant
    try:
        tenant = Tenant(
            id="default",
            name="Default Tenant",
            subdomain="default",
            status="active",
        )
        session.add(tenant)
        session.commit()
    except Exception:
        pass  # Tenant table may not exist

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def test_tenant(db_session: Session) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Test Tenant",
        status="active",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture(scope="function")
def test_user(db_session: Session, test_tenant: Tenant) -> User:
    """Create a test user."""
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER.value,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session: Session, test_tenant: Tenant) -> User:
    """Create an admin user."""
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

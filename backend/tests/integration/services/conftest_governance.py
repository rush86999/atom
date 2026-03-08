"""
Shared fixtures for governance service integration tests.

This conftest provides fixtures specifically for testing AgentGovernanceService
without conflicts from other test fixtures.

Key fixtures:
- governance_db: Fresh database session for governance tests
- governance_cache: GovernanceCache with short TTL for testing
- governance_service: AgentGovernanceService instance
- governance_test_agent: Factory for creating test agents
- governance_test_user: Factory for creating test users
"""

import pytest
import os
import tempfile
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
    UserStatus,
)


@pytest.fixture(scope="function")
def governance_db():
    """
    Create a fresh database session for governance tests.

    Uses file-based temp SQLite to avoid circular dependencies.

    Yields:
        Session: SQLAlchemy database session
    """
    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                continue

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
            pass


@pytest.fixture(scope="function")
def governance_cache():
    """
    Create a GovernanceCache instance with short TTL for testing.

    Uses 1-second TTL to test expiration behavior without long waits.

    Yields:
        GovernanceCache: Cache instance with short TTL
    """
    cache = GovernanceCache(max_size=100, ttl_seconds=1)
    yield cache
    cache.clear()


@pytest.fixture(scope="function")
def governance_service(governance_db: Session):
    """
    Create an AgentGovernanceService instance with test database session.

    Yields:
        AgentGovernanceService: Service instance for testing
    """
    service = AgentGovernanceService(governance_db)
    yield service


@pytest.fixture(scope="function")
def governance_test_agent(governance_db: Session):
    """
    Factory fixture for creating test agents for governance tests.

    Usage:
        agent = governance_test_agent(name="Test Agent", status=AgentStatus.INTERN)
        agent = governance_test_agent(confidence_score=0.8)

    Yields:
        callable: Factory function that creates and returns an AgentRegistry
    """
    created_agents = []

    def _create_agent(
        name: str = "Test Agent",
        category: str = "Testing",
        module_path: str = "test.module",
        class_name: str = "TestAgent",
        status: AgentStatus = AgentStatus.STUDENT,
        confidence_score: float = 0.5,
        enabled: bool = True
    ) -> AgentRegistry:
        """Create a test agent in the database."""
        agent = AgentRegistry(
            name=name,
            description=f"Test agent for {name}",
            category=category,
            module_path=module_path,
            class_name=class_name,
            status=status.value if isinstance(status, AgentStatus) else status,
            confidence_score=confidence_score,
            enabled=enabled,
            created_at=datetime.now(timezone.utc)
        )
        governance_db.add(agent)
        governance_db.commit()
        governance_db.refresh(agent)
        created_agents.append(agent)
        return agent

    yield _create_agent

    # Cleanup is handled by governance_db cleanup


@pytest.fixture(scope="function")
def governance_test_user(governance_db: Session):
    """
    Factory fixture for creating test users for governance tests.

    Usage:
        user = governance_test_user(email="test@example.com")
        user = governance_test_user(role=UserRole.ADMIN)

    Yields:
        callable: Factory function that creates and returns a User
    """
    created_users = []

    def _create_user(
        email: str = "test@example.com",
        role: UserRole = UserRole.MEMBER,
        specialty: str = None,
        reputation: float = 0.5
    ) -> User:
        """Create a test user in the database."""
        user = User(
            email=email,
            name="Test User",
            role=role.value if isinstance(role, UserRole) else role,
            status=UserStatus.ACTIVE.value,
            specialty=specialty,
            reputation_score=reputation,
            created_at=datetime.now(timezone.utc)
        )
        governance_db.add(user)
        governance_db.commit()
        governance_db.refresh(user)
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup is handled by governance_db cleanup

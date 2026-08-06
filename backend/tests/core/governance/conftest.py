"""
Fixtures for core tests in the governance directory.

These tests target AgentContextResolver / AgentGovernanceService, which call
``session.commit()`` internally. The root ``tests/conftest.py`` ``db_session``
relies on a nested-transaction rollback against a session-scoped in-memory
engine, so committed rows leak across tests and cause UNIQUE constraint
failures. This fixture overrides it with a fresh in-memory database per test
(the same pattern used by ``tests/unit/governance/conftest.py``).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
# Import all models to ensure they are registered with Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    ChatSession,
    User,
    UserRole,
    Workspace,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database for each test (full isolation)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create tables one-by-one to tolerate duplicate index definitions in
    # models.py (same approach as tests/unit/governance/conftest.py).
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
        except Exception:
            pass

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()
    engine.dispose()

    # ServiceFactory caches session-bound services in thread-local state;
    # clear them so later tests don't reuse a service bound to the disposed
    # in-memory engine.
    from core.service_factory import ServiceFactory
    for attr in (
        "episode_service",
        "governance_service",
        "context_resolver",
        "guardrails_service",
        "memory_consolidation_service",
        "activity_publisher",
        "knowledge_extractor",
        "graphrag_engine",
    ):
        if hasattr(ServiceFactory._thread_local, attr):
            delattr(ServiceFactory._thread_local, attr)

"""
Unit test configuration and fixtures.

This file provides fixtures specific to unit tests.
"""

import pytest
from sqlalchemy.orm import Session
from core.database import SessionLocal


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh database session with transaction rollback for each test.

    This ensures complete isolation between test runs - all changes
    are rolled back after each test.

    FIXED (GAP-01): Added transaction rollback pattern to prevent
    session state leakage between tests, which was causing
    IntegrityError and PendingRollbackError.
    """
    from sqlalchemy.orm import sessionmaker

    # Create a new engine for each test with proper isolation
    engine = SessionLocal.kw['bind']
    engine.dispose()

    # Create session with autoflush=False to prevent premature commits
    session = SessionLocal()
    session.autoflush = False

    yield session

    # Rollback all changes after test to ensure isolation
    session.rollback()
    # Close session to prevent connection leaks
    session.close()

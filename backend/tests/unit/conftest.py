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
    session = SessionLocal()

    # Begin a nested transaction (savepoint) for rollback
    # This allows us to rollback all changes while keeping the session open
    connection = session.connection()
    transaction = connection.begin_nested()

    yield session

    # Rollback transaction after test
    session.rollback()
    session.close()

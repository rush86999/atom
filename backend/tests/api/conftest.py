"""
Conftest for API integration tests.

Provides database session fixture for API tests.
"""

import pytest
from sqlalchemy.orm import Session

from core.database import SessionLocal


@pytest.fixture
def db():
    """Create a test database session.

    Uses transaction rollback pattern to isolate test data.
    """
    db = SessionLocal()
    db.begin_nested()  # Begin transaction for test isolation

    try:
        yield db
        db.rollback()  # Rollback all changes, including committed data
    finally:
        db.close()

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

    Uses rollback pattern to isolate test data.
    """
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()

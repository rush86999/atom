"""
Unit test configuration and fixtures.

This file provides fixtures specific to unit tests.
"""

import pytest
from core.database import SessionLocal


@pytest.fixture(scope="function")
def db():
    """
    Create a test database session for unit tests.

    Uses SessionLocal to create a fresh database session for each test.
    The session is closed after the test completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

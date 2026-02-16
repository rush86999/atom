"""
Unit test configuration and fixtures.

This file provides fixtures specific to unit tests.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import Base


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs by using a
    temporary SQLite database file that is deleted after each test.
    Each test gets its own database, preventing UNIQUE constraint violations
    and state leakage between tests.
    """
    # Use file-based temp SQLite for tests to ensure all connections see the same database
    # In-memory SQLite (:memory:) creates a separate database for each connection
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor, we just need the path

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create all tables, handling missing foreign key references from optional modules
    # Same approach as property_tests conftest.py
    tables_created = 0
    tables_skipped = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            tables_created += 1
        except exc.NoReferencedTableError:
            # Skip tables with missing FK references (from optional modules)
            tables_skipped += 1
            continue
        except Exception as e:
            # Ignore duplicate table/index errors
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            else:
                raise

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
            pass  # File might already be deleted

"""
Minimal conftest for rate limit tests (avoids main_api_app import issues).

This conftest provides only the db_session fixture needed for rate limit tests,
avoiding the import conflict between core/security.py and core/security/__init__.py.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

import pytest
from hypothesis import settings, HealthCheck
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.database import Base
from core.models import (
    AgentRegistry, AgentStatus,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs.
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

    # Create all tables
    import warnings
    tables_created = 0
    tables_skipped = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            tables_created += 1
        except exc.NoReferencedTableError:
            tables_skipped += 1
            continue
        except Exception as e:
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
            pass


# Hypothesis settings
HYPOTHESIS_SETTINGS = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200,
    "deadline": None
}

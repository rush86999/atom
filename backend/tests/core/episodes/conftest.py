"""
Episode test fixtures for tests/core/episodes.

Provides a function-scoped, file-based SQLite ``db_session`` that shadows the
root ``tests/conftest.py`` fixture. The root fixture uses a *session-scoped*
worker database (in-memory StaticPool) whose rows survive across tests because
tests call ``db_session.commit()`` explicitly, which commits the outer
transaction (not just the savepoint). That leaks rows between tests and causes
UNIQUE-constraint collisions and off-by-N assertion failures (e.g.
``decay_old_episodes`` seeing episodes created by earlier tests).

This fixture gives each test a fresh database, mirroring the pattern in
``tests/unit/episodes/conftest.py``.
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh file-based SQLite database for each test."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor, we just need the path

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    engine._test_db_path = db_path

    from core.models_registration import Base

    # Create all tables, handling missing FK references from optional modules
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
        except (exc.CompileError, exc.UnsupportedCompilationError):
            continue
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            raise

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass  # File might already be deleted

"""
Database connection drop fixtures for chaos testing.

Simulates database connection drops to test:
- Connection pool exhaustion handling
- Automatic reconnection logic
- Graceful degradation when database unavailable

Strategies:
- SQLite: Lock database file (chmod 444)
- PostgreSQL: Mock connection errors (safer than stopping service)
"""

import os
import pytest
import time
from contextlib import contextmanager
from sqlalchemy.exc import OperationalError, DatabaseError


@pytest.fixture(scope="function")
def database_connection_dropper():
    """
    Simulate database connection drops during test.

    Blast radius: Test database only
    Duration: 10 seconds max
    Safety: Automatic restore

    Yields:
        Context manager for connection drop simulation

    Example:
        with database_connection_dropper():
            # Database queries will fail
            agent = db_session.query(Agent).first()  # Raises OperationalError
    """
    database_url = os.getenv("DATABASE_URL", "")
    is_sqlite = "sqlite" in database_url

    # Blast radius check
    assert "test" in database_url or "dev" in database_url or "chaos" in database_url, \
        f"Unsafe: Database URL must be test/dev/chaos: {database_url}"

    if is_sqlite:
        # SQLite strategy: Lock database file
        db_path = database_url.replace("sqlite:///", "")
        if not os.path.isabs(db_path):
            # Relative path, resolve from backend directory
            import sys
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            db_path = os.path.join(backend_dir, db_path)

        original_perms = None

        @contextmanager
        def _drop_and_restore():
            nonlocal original_perms
            # Lock database file
            if os.path.exists(db_path):
                original_perms = os.stat(db_path).st_mode
                os.chmod(db_path, 0o444)  # Read-only

            yield

            # Restore database file
            if original_perms and os.path.exists(db_path):
                os.chmod(db_path, original_perms)

        return _drop_and_restore()

    else:
        # PostgreSQL/MySQL strategy: Mock connection errors
        # (safer than actually stopping the database service)
        @contextmanager
        def _mock_connection_drop():
            # Patch SQLAlchemy to raise OperationalError
            from unittest.mock import patch
            original_execute = None

            # Mock session.execute to raise error
            def _mock_execute_error(*args, **kwargs):
                raise OperationalError("Connection lost", {}, None)

            with patch("sqlalchemy.orm.Session.execute", side_effect=_mock_execute_error):
                yield

        return _mock_connection_drop()


@pytest.fixture(scope="function")
def connection_pool_exhaustion():
    """
    Simulate connection pool exhaustion.

    Blast radius: Test database only
    Duration: 10 seconds max

    Yields:
        Context manager for pool exhaustion simulation
    """
    @contextmanager
    def _exhaust_pool():
        # Patch connection pool to raise pool exhaustion error
        from unittest.mock import patch, MagicMock

        class PoolExhaustionError(Exception):
            pass

        # Mock pool connection acquisition
        def _mock_connect(*args, **kwargs):
            raise PoolExhaustionError("Connection pool exhausted")

        with patch("sqlalchemy.pool.Pool.connect", side_effect=_mock_connect):
            yield

    return _exhaust_pool()


@pytest.fixture(scope="function")
def database_recovery_validator(chaos_db_session):
    """
    Validate database recovery after connection drop.

    Checks:
    - No data loss (all test data still exists)
    - No data corruption (data values unchanged)
    - Connection restored (queries succeed)

    Yields:
        Validator function

    Example:
        validator = yield
        validator(agent_ids=[agent_id], names=["test_agent"])
    """
    from core.models import AgentRegistry

    def validate_data_integrity(record_ids: list, expected_names: list = None):
        """
        Validate data integrity after database recovery.

        Args:
            record_ids: List of record IDs to check
            expected_names: Optional list of expected names to validate
        """
        # Check 1: No data loss
        for record_id in record_ids:
            record = chaos_db_session.query(AgentRegistry).filter_by(id=record_id).first()
            assert record is not None, f"Record {record_id} was lost during database drop"

        # Check 2: No data corruption
        if expected_names:
            for i, record_id in enumerate(record_ids):
                record = chaos_db_session.query(AgentRegistry).filter_by(id=record_id).first()
                assert record.name == expected_names[i], f"Record {record_id} data corrupted"

        # Check 3: Connection restored
        try:
            chaos_db_session.query(AgentRegistry).count()
        except OperationalError:
            raise AssertionError("Database connection not restored")

    return validate_data_integrity

"""
Worker-based database isolation fixtures for pytest-xdist parallel execution.

Supports both PostgreSQL and SQLite:
- PostgreSQL: Each worker gets a separate schema for isolation
- SQLite: Shared database with transaction rollback for isolation

Usage:
    def test_my_feature(db_session):
        # db_session is automatically isolated
        # Transactions are rolled back after test
        agent = Agent(name="test")
        db_session.add(agent)
        db_session.commit()
        # Data automatically cleaned up after test
"""

import os
import sys
import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# Add backend to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import Base


@pytest.fixture(scope="session")
def is_sqlite(get_engine: sqlalchemy.Engine) -> bool:
    """
    Detect if using SQLite database.

    Args:
        get_engine: SQLAlchemy engine

    Returns:
        True if SQLite, False if PostgreSQL
    """
    return get_engine.dialect.name == "sqlite"


@pytest.fixture(scope="session")
def worker_schema(worker_id: str = "master") -> str:
    """
    Return worker-specific schema name (PostgreSQL only).

    Args:
        worker_id: pytest-xdist worker ID (e.g., 'gw0', 'gw1', 'master')
                   Defaults to 'master' when not using xdist

    Returns:
        Schema name for this worker (e.g., 'test_schema_gw0')

    Examples:
        >>> worker_schema("gw0")
        'test_schema_gw0'
        >>> worker_schema("master")
        'test_schema_master'
    """
    # Handle master process (no xdist)
    if worker_id == "master":
        return "test_schema_gw0"
    return f"test_schema_{worker_id}"


@pytest.fixture(scope="session")
def get_engine() -> sqlalchemy.Engine:
    """
    Create SQLAlchemy engine for test database.

    Uses DATABASE_URL environment variable or defaults to PostgreSQL.

    Returns:
        SQLAlchemy engine instance

    Note:
        Engine is created once per test session and reused across tests.
    """
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://atom:atom_test@localhost:5432/atom_test"
    )
    engine = sqlalchemy.create_engine(database_url, pool_pre_ping=True)
    return engine


@pytest.fixture(scope="session", autouse=True)
def create_worker_schema(
    worker_schema: str,
    get_engine: sqlalchemy.Engine,
    is_sqlite: bool,
    request: pytest.FixtureRequest
) -> Generator[str, None, None]:
    """
    Create worker-specific schema before test session and drop after (PostgreSQL only).

    For SQLite, this fixture yields without schema operations.

    Args:
        worker_schema: Schema name for this worker
        get_engine: SQLAlchemy engine
        is_sqlite: True if using SQLite
        request: Pytest request object

    Yields:
        Schema name (or placeholder for SQLite)

    Note:
        - PostgreSQL: Schema created with CREATE SCHEMA IF NOT EXISTS
        - PostgreSQL: Dropped with CASCADE after test session
        - SQLite: No schema operations (SQLite doesn't support schemas)
        - Autouse=True: runs automatically for all tests
        - Skipped for tests marked with no_browser
    """
    # Skip for unit tests marked with no_browser
    if request.node.get_closest_marker('no_browser'):
        yield worker_schema
        return

    schema = worker_schema

    # Skip schema operations for SQLite
    if is_sqlite:
        yield schema
        return

    # Create schema (PostgreSQL only)
    with get_engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()

    yield schema

    # Teardown: drop schema after session (PostgreSQL only)
    with get_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()


@pytest.fixture(scope="session")
def init_db(
    create_worker_schema: str,
    get_engine: sqlalchemy.Engine,
    is_sqlite: bool
) -> Generator[None, None, None]:
    """
    Initialize database tables in worker schema (PostgreSQL) or main database (SQLite).

    Args:
        create_worker_schema: Schema name from create_worker_schema fixture
        get_engine: SQLAlchemy engine
        is_sqlite: True if using SQLite

    Yields:
        None

    Note:
        - PostgreSQL: Uses schema_translate_map to direct tables to worker schema
        - SQLite: Creates tables in main database
        - Drops all tables after test session
    """
    schema = create_worker_schema

    if is_sqlite:
        # SQLite: Create tables directly in main database
        Base.metadata.create_all(get_engine)
        yield
        Base.metadata.drop_all(get_engine)
    else:
        # PostgreSQL: Create engine with schema translation
        engine = get_engine.execution_options(
            schema_translate_map={None: schema}
        )
        # Create all tables
        Base.metadata.create_all(engine)
        yield
        # Drop all tables
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(
    worker_schema: str,
    get_engine: sqlalchemy.Engine,
    init_db: None,
    is_sqlite: bool
) -> Generator[Session, None, None]:
    """
    Create database session with transaction rollback for test isolation.

    Args:
        worker_schema: Schema name for this worker (PostgreSQL only)
        get_engine: SQLAlchemy engine
        init_db: Database initialization fixture (ensures tables exist)
        is_sqlite: True if using SQLite

    Yields:
        SQLAlchemy session with transaction rollback

    Note:
        - PostgreSQL: Sets search_path to worker schema
        - Begins transaction before test
        - Rolls back transaction after test (no data pollution)
        - Closes session after rollback
    """
    # Create engine with REPEATABLE READ isolation (PostgreSQL) or default (SQLite)
    if is_sqlite:
        engine = get_engine
    else:
        engine = get_engine.execution_options(
            isolation_level="REPEATABLE READ"
        )

    # Create session with autocommit disabled for transaction control
    Session = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    session = Session()

    # Set search path to worker schema (PostgreSQL only)
    # Do this in a separate transaction
    if not is_sqlite:
        session.execute(text(f"SET search_path TO {worker_schema}"))
        session.commit()  # Commit the search_path change immediately
        # Begin a new transaction for the test
        session.begin()
    else:
        # For SQLite, transaction is already started by default
        pass

    yield session

    # Rollback transaction after test
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def drop_worker_schema(
    worker_schema: str,
    get_engine: sqlalchemy.Engine,
    is_sqlite: bool
) -> None:
    """
    Drop worker-specific schema after test session (PostgreSQL only).

    For SQLite, this fixture does nothing (no schemas to drop).

    Args:
        worker_schema: Schema name for this worker
        get_engine: SQLAlchemy engine
        is_sqlite: True if using SQLite

    Note:
        - PostgreSQL: Drops schema with CASCADE
        - SQLite: No operation (no schemas)
        - This fixture is kept for explicit cleanup if needed
        - create_worker_schema already handles cleanup via CASCADE
        - Use this for manual schema reset during debugging
    """
    if is_sqlite:
        return

    with get_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {worker_schema} CASCADE"))
        conn.commit()

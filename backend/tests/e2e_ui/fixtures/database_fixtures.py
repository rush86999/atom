"""
Worker-based database isolation fixtures for pytest-xdist parallel execution.

Each test worker (gw0, gw1, gw2, gw3) gets a separate PostgreSQL schema
to prevent data collisions during parallel test execution.

Usage:
    def test_my_feature(db_session):
        # db_session is automatically isolated to worker's schema
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
def worker_schema(worker_id: str) -> str:
    """
    Return worker-specific schema name.

    Args:
        worker_id: pytest-xdist worker ID (e.g., 'gw0', 'gw1', 'master')

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
    request: pytest.FixtureRequest
) -> Generator[str, None, None]:
    """
    Create worker-specific schema before test session and drop after.

    Args:
        worker_schema: Schema name for this worker
        get_engine: SQLAlchemy engine
        request: Pytest request object

    Yields:
        Schema name

    Note:
        - Schema created with CREATE SCHEMA IF NOT EXISTS
        - Dropped with CASCADE after test session
        - Autouse=True: runs automatically for all tests
        - Skipped for tests marked with no_browser
    """
    # Skip for unit tests marked with no_browser
    if request.node.get_closest_marker('no_browser'):
        yield worker_schema
        return

    schema = worker_schema

    # Create schema
    with get_engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()

    yield schema

    # Teardown: drop schema after session
    with get_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()


@pytest.fixture(scope="session")
def init_db(
    create_worker_schema: str,
    get_engine: sqlalchemy.Engine
) -> Generator[None, None, None]:
    """
    Initialize database tables in worker schema.

    Args:
        create_worker_schema: Schema name from create_worker_schema fixture
        get_engine: SQLAlchemy engine

    Yields:
        None

    Note:
        - Creates all tables using SQLAlchemy Base.metadata
        - Uses schema_translate_map to direct tables to worker schema
        - Drops all tables after test session
    """
    schema = create_worker_schema

    # Create engine with schema translation
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
    init_db: None
) -> Generator[Session, None, None]:
    """
    Create database session with transaction rollback for test isolation.

    Args:
        worker_schema: Schema name for this worker
        get_engine: SQLAlchemy engine
        init_db: Database initialization fixture (ensures tables exist)

    Yields:
        SQLAlchemy session with transaction rollback

    Note:
        - Sets search_path to worker schema
        - Begins transaction before test
        - Rolls back transaction after test (no data pollution)
        - Closes session after rollback
    """
    # Create engine with REPEATABLE READ isolation
    engine = get_engine.execution_options(
        isolation_level="REPEATABLE READ"
    )

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Set search path to worker schema
    session.execute(text(f"SET search_path TO {worker_schema}"))

    # Begin transaction
    connection = session.connection()
    transaction = connection.begin()

    yield session

    # Rollback transaction after test
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def drop_worker_schema(
    worker_schema: str,
    get_engine: sqlalchemy.Engine
) -> None:
    """
    Drop worker-specific schema after test session.

    Args:
        worker_schema: Schema name for this worker
        get_engine: SQLAlchemy engine

    Note:
        - This fixture is kept for explicit cleanup if needed
        - create_worker_schema already handles cleanup via CASCADE
        - Use this for manual schema reset during debugging
    """
    with get_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {worker_schema} CASCADE"))
        conn.commit()

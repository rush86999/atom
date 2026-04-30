"""
PostgreSQL test fixtures for integration tests.

This module provides pytest fixtures for testing with a real PostgreSQL database.
These fixtures are designed to work with the test database setup in docker-compose.test.yml.

Key features:
- Separate test database (atom_test_db) isolated from development/production
- Automatic schema migration via Alembic
- Connection pooling for performance
- Automatic cleanup after tests
- Support for JSONB columns and recursive CTEs

Usage:
    @pytest.mark.postgresql
    def test_with_postgresql(postgresql_db):
        # Use postgresql_db fixture for database session
        result = postgresql_db.execute(text("SELECT 1")).scalar()
        assert result == 1
"""

import os
import sys
import pytest
import time
import subprocess
from typing import Generator, Optional
from pathlib import Path
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import OperationalError


# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import models for table creation
from core.models import Base


# PostgreSQL test database configuration
TEST_POSTGRES_HOST = os.getenv("TEST_POSTGRES_HOST", "127.0.0.1")
TEST_POSTGRES_PORT = os.getenv("TEST_POSTGRES_PORT", "5434")
TEST_POSTGRES_USER = os.getenv("TEST_POSTGRES_USER", "atom_test")
TEST_POSTGRES_PASSWORD = os.getenv("TEST_POSTGRES_PASSWORD", "atom_test_password")
TEST_POSTGRES_DB = os.getenv("TEST_POSTGRES_DB", "atom_test_db")

# Construct test database URL
TEST_DATABASE_URL = (
    f"postgresql://{TEST_POSTGRES_USER}:{TEST_POSTGRES_PASSWORD}"
    f"@{TEST_POSTGRES_HOST}:{TEST_POSTGRES_PORT}/{TEST_POSTGRES_DB}"
)


def _is_postgresql_running() -> bool:
    """Check if PostgreSQL test database is running and accessible."""
    try:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _start_postgresql_docker() -> bool:
    """Start PostgreSQL test database using Docker Compose.

    Returns:
        True if started successfully, False otherwise
    """
    backend_dir = Path(__file__).parent.parent.parent
    docker_compose_file = backend_dir / "docker-compose.test.yml"

    if not docker_compose_file.exists():
        print(f"Warning: docker-compose.test.yml not found at {docker_compose_file}")
        return False

    try:
        # Start PostgreSQL container
        subprocess.run(
            ["docker-compose", "-f", str(docker_compose_file), "up", "-d", "postgresql_test"],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Wait for database to be ready
        for _ in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            if _is_postgresql_running():
                print("PostgreSQL test database is ready")
                return True

        print("Warning: PostgreSQL test database did not become ready")
        return False

    except subprocess.TimeoutExpired:
        print("Warning: Timeout starting PostgreSQL test database")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to start PostgreSQL: {e}")
        return False
    except Exception as e:
        print(f"Warning: Unexpected error starting PostgreSQL: {e}")
        return False


@pytest.fixture(scope="session")
def postgresql_container() -> Generator[bool, None, None]:
    """
    Start PostgreSQL test container for the test session.

    This fixture is session-scoped and runs once before all tests.
    It attempts to connect to an existing PostgreSQL test database,
    and starts one via Docker Compose if not available.

    Skips PostgreSQL tests if the database cannot be started.

    Yields:
        bool: True if PostgreSQL is available, False otherwise
    """
    # Check if PostgreSQL is already running
    if _is_postgresql_running():
        print("Using existing PostgreSQL test database")
        yield True
        return

    # Try to start PostgreSQL via Docker Compose
    print("Attempting to start PostgreSQL test database...")
    success = _start_postgresql_docker()

    if not success:
        print("Warning: PostgreSQL test database unavailable, tests will be skipped")

    yield success

    # Optional: Stop container after session (commented out for performance)
    # subprocess.run(
    #     ["docker-compose", "-f", str(docker_compose_file), "down"],
    #     capture_output=True
    # )


@pytest.fixture(scope="session")
def postgresql_engine(postgresql_container) -> Generator[Optional[Engine], None, None]:
    """
    Create SQLAlchemy engine for PostgreSQL test database.

    This fixture is session-scoped and creates the engine once.
    It runs Alembic migrations to set up the schema.

    Skipped if postgresql_container is False.

    Yields:
        Engine: SQLAlchemy engine or None if PostgreSQL unavailable
    """
    if not postgresql_container:
        yield None
        return

    # Create engine with connection pooling
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Connection pool size
        max_overflow=10,  # Additional connections when pool is full
        echo=False  # Set to True for SQL query logging
    )

    # Create all tables (or run Alembic migrations)
    try:
        print("Creating database schema...")
        Base.metadata.create_all(engine)
        print("Database schema created successfully")
    except Exception as e:
        print(f"Warning: Failed to create schema: {e}")
        engine.dispose()
        yield None
        return

    yield engine

    # Cleanup: drop all tables after session
    try:
        print("Dropping database schema...")
        Base.metadata.drop_all(engine)
        print("Database schema dropped successfully")
    except Exception as e:
        print(f"Warning: Failed to drop schema: {e}")
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def postgresql_db(postgresql_engine) -> Generator[Optional[Session], None, None]:
    """
    Create a new database session for each test function.

    This fixture is function-scoped and provides a clean database
    for each test. All changes are rolled back after the test.

    Usage:
        @pytest.mark.postgresql
        def test_something(postgresql_db):
            if postgresql_db is None:
                pytest.skip("PostgreSQL unavailable")

            # Use postgresql_db for database operations
            agent = AgentRegistry(name="test")
            postgresql_db.add(agent)
            postgresql_db.commit()

    Args:
        postgresql_engine: Session-scoped engine fixture

    Yields:
        Session: SQLAlchemy session or None if PostgreSQL unavailable
    """
    if postgresql_engine is None:
        yield None
        return

    # Create session
    SessionLocal = sessionmaker(bind=postgresql_engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    # Start transaction for rollback
    connection = session.connection()
    transaction = connection.begin_nested()

    yield session

    # Rollback transaction (instant cleanup)
    try:
        session.rollback()
    except Exception:
        pass
    finally:
        session.close()


@pytest.fixture(scope="function")
def postgresql_clean_db(postgresql_db: Session) -> Generator[Optional[Session], None, None]:
    """
    Provide a completely empty database for each test.

    This fixture deletes all data before the test runs.
    Use this when you need a guaranteed clean slate.

    Usage:
        @pytest.mark.postgresql
        def test_with_clean_db(postgresql_clean_db):
            if postgresql_clean_db is None:
                pytest.skip("PostgreSQL unavailable")

            # Database is completely empty
            assert postgresql_clean_db.query(AgentRegistry).count() == 0

    Args:
        postgresql_db: Function-scoped session fixture

    Yields:
        Session: SQLAlchemy session with empty database
    """
    if postgresql_db is None:
        yield None
        return

    # Delete all data before test
    try:
        for table in reversed(Base.metadata.sorted_tables):
            postgresql_db.execute(table.delete())
        postgresql_db.commit()
    except Exception as e:
        print(f"Warning: Failed to clean database: {e}")

    yield postgresql_db


@pytest.fixture(scope="session")
def postgresql_url() -> str:
    """
    Return the PostgreSQL test database URL.

    Useful for tests that need to create their own engine.

    Usage:
        def test_custom_engine(postgresql_url):
            engine = create_engine(postgresql_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
    """
    return TEST_DATABASE_URL


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def skip_if_no_postgresql(func):
    """
    Decorator to skip test if PostgreSQL is unavailable.

    Usage:
        @skip_if_no_postgresql
        def test_postgresql_feature(postgresql_db):
            # Test will be skipped if postgresql_db is None
            assert postgresql_db.query(AgentRegistry).count() == 0
    """
    def wrapper(postgresql_db, *args, **kwargs):
        if postgresql_db is None:
            pytest.skip("PostgreSQL test database unavailable")
        return func(postgresql_db, *args, **kwargs)
    return wrapper


def get_postgresql_version(session: Session) -> str:
    """
    Get PostgreSQL server version.

    Args:
        session: SQLAlchemy session

    Returns:
        str: PostgreSQL version (e.g., "PostgreSQL 15.2")
    """
    result = session.execute(text("SELECT version()")).scalar()
    return result


def check_jsonb_support(session: Session) -> bool:
    """
    Check if JSONB is supported (PostgreSQL-specific feature).

    Args:
        session: SQLAlchemy session

    Returns:
        bool: True if JSONB is supported
    """
    try:
        result = session.execute(
            text("SELECT '[]'::jsonb")
        ).scalar()
        return result == []
    except Exception:
        return False


def check_recursive_cte_support(session: Session) -> bool:
    """
    Check if recursive CTEs are supported (PostgreSQL-specific feature).

    Args:
        session: SQLAlchemy session

    Returns:
        bool: True if recursive CTEs are supported
    """
    try:
        result = session.execute(
            text("""
                WITH RECURSIVE cte AS (
                    SELECT 1 AS n
                    UNION ALL
                    SELECT n + 1 FROM cte WHERE n < 5
                )
                SELECT COUNT(*) FROM cte
            """)
        ).scalar()
        return result == 5
    except Exception:
        return False


# ============================================================================
# PYTEST MARKERS
# ============================================================================

def pytest_configure(config):
    """
    Register custom pytest markers.
    """
    config.addinivalue_line(
        "markers", "postgresql: mark test as requiring PostgreSQL database"
    )


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_test_entity_type(
    session: Session,
    slug: str,
    display_name: str,
    json_schema: dict
) -> None:
    """
    Create a test entity type definition.

    Args:
        session: SQLAlchemy session
        slug: Unique identifier
        display_name: Human-readable name
        json_schema: JSON Schema for validation
    """
    from core.models import EntityTypeDefinition

    entity_type = EntityTypeDefinition(
        slug=slug,
        display_name=display_name,
        json_schema=json_schema,
        is_active=True
    )
    session.add(entity_type)
    session.commit()


def create_test_graph_node(
    session: Session,
    entity_id: str,
    entity_type: str,
    name: str,
    workspace_id: str = "default"
) -> None:
    """
    Create a test graph node.

    Args:
        session: SQLAlchemy session
        entity_id: Unique entity identifier
        entity_type: Type of entity
        name: Entity name
        workspace_id: Workspace identifier
    """
    from core.models import GraphNode

    node = GraphNode(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        workspace_id=workspace_id
    )
    session.add(node)
    session.commit()


def create_test_graph_edge(
    session: Session,
    from_entity: str,
    to_entity: str,
    rel_type: str,
    workspace_id: str = "default"
) -> None:
    """
    Create a test graph edge.

    Args:
        session: SQLAlchemy session
        from_entity: Source entity ID
        to_entity: Target entity ID
        rel_type: Relationship type
        workspace_id: Workspace identifier
    """
    from core.models import GraphEdge

    edge = GraphEdge(
        from_entity=from_entity,
        to_entity=to_entity,
        rel_type=rel_type,
        workspace_id=workspace_id
    )
    session.add(edge)
    session.commit()

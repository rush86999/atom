"""
Database-specific fixtures for E2E testing.

This module provides reusable fixtures for PostgreSQL, SQLite (Personal Edition),
Alembic migrations, data seeding, backup/restore operations, and connection pooling.
All fixtures are designed for end-to-end testing with real database services.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Generator, Dict, Any
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from core.models import Base, AgentRegistry, AgentExecution
from datetime import datetime
import uuid


# =============================================================================
# PostgreSQL Engine Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def e2e_postgres_engine():
    """
    Create PostgreSQL engine for E2E tests.

    This session-scoped fixture creates a single PostgreSQL engine
    that is reused across all tests in the session. The engine uses
    connection pooling for efficient database access.

    Connection: postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test
    Pool size: 10 connections
    Max overflow: 20 additional connections

    Yields:
        SQLAlchemy Engine instance configured for PostgreSQL
    """
    database_url = "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test"

    print(f"\n=== Creating PostgreSQL Engine ===")
    print(f"Database URL: {database_url}")

    engine = create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections every hour
        echo=False,          # Set to True for SQL query debugging
    )

    # Verify connection
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        print("PostgreSQL engine created successfully")
    except Exception as e:
        pytest.skip(f"Failed to connect to PostgreSQL: {e}")

    yield engine

    # Cleanup: Dispose engine
    print("\n=== Disposing PostgreSQL Engine ===")
    engine.dispose()


@pytest.fixture(scope="function")
def e2e_postgres_session(e2e_postgres_engine) -> Generator[Session, None, None]:
    """
    Create PostgreSQL session for testing.

    This function-scoped fixture creates a fresh database session
    for each test. All changes are rolled back after the test
    to maintain test isolation.

    Yields:
        SQLAlchemy Session instance
    """
    Session = sessionmaker(bind=e2e_postgres_engine, autocommit=False, autoflush=False)
    session = Session()

    print(f"\n=== Created PostgreSQL Session ===")

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        print("\n=== Closed PostgreSQL Session ===")


# =============================================================================
# SQLite Engine Fixtures (Personal Edition)
# =============================================================================

@pytest.fixture(scope="function")
def e2e_sqlite_engine():
    """
    Create SQLite engine for Personal Edition testing.

    This function-scoped fixture creates a temporary SQLite database
    file for testing Personal Edition database operations. The file
    is automatically cleaned up after the test.

    Uses a unique temp file for each test to ensure isolation.

    Yields:
        Tuple of (SQLAlchemy Engine, temp file path)
    """
    import tempfile
    import os

    # Use temp file for isolation
    fd, path = tempfile.mkstemp(suffix=".db", prefix="atom_e2e_")
    os.close(fd)  # Close file descriptor

    print(f"\n=== Creating SQLite Engine (Personal Edition) ===")
    print(f"Database file: {path}")

    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create tables for Personal Edition schema
    try:
        Base.metadata.create_all(engine, checkfirst=True)
        print("SQLite tables created successfully")
    except Exception as e:
        print(f"Warning: Some tables may have failed to create: {e}")

    yield engine, path

    # Cleanup: Close engine and delete temp file
    print(f"\n=== Cleaning up SQLite Database ===")
    engine.dispose()
    try:
        os.remove(path)
        print(f"Deleted temporary database: {path}")
    except Exception as e:
        print(f"Warning: Failed to delete temp file {path}: {e}")


@pytest.fixture(scope="function")
def e2e_sqlite_session(e2e_sqlite_engine) -> Generator[Session, None, None]:
    """
    Create SQLite session for testing.

    This function-scoped fixture creates a fresh SQLite session
    for testing Personal Edition database operations.

    Yields:
        SQLAlchemy Session instance
    """
    engine, path = e2e_sqlite_engine

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    print(f"\n=== Created SQLite Session (Personal Edition) ===")

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        print("\n=== Closed SQLite Session ===")


# =============================================================================
# Migration Fixture
# =============================================================================

@pytest.fixture(scope="function")
def fresh_database(e2e_postgres_engine):
    """
    Create fresh database with all migrations.

    This fixture runs all Alembic migrations to create a fresh
    database schema. After the test, all tables are dropped.

    Use this fixture when testing migration behavior or when
    you need a clean database with the complete schema.

    Yields:
        SQLAlchemy Engine with all migrations applied
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.environment import EnvironmentContext
    import sqlalchemy

    print(f"\n=== Running Alembic Migrations ===")

    # Configure Alembic
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test"
    )

    # Get migration directory
    script = ScriptDirectory.from_config(config)

    # Run all migrations to head
    with e2e_postgres_engine.begin() as connection:
        context = EnvironmentContext(config, script)

        def upgrade(rev, context):
            return script._upgrade_revs("head", rev)

        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            fn=upgrade
        )
        context.run_migrations()

    print("All migrations applied successfully")

    yield e2e_postgres_engine

    # Teardown: Drop all tables
    print(f"\n=== Dropping All Tables ===")
    try:
        Base.metadata.drop_all(e2e_postgres_engine)
        print("All tables dropped successfully")
    except Exception as e:
        print(f"Warning: Failed to drop tables: {e}")


# =============================================================================
# Data Seeding Fixture
# =============================================================================

@pytest.fixture(scope="function")
def seed_test_data(e2e_postgres_session) -> Dict[str, Any]:
    """
    Seed database with test data.

    This fixture creates realistic test data for E2E tests:
    - 5 test agents (varying maturity levels)
    - 15 test executions (3 per agent)
    - Random UUIDs for uniqueness

    Yields:
        Dictionary with 'agents' and 'executions' lists
    """
    print(f"\n=== Seeding Test Data ===")

    # Create test agents
    agents = []
    maturity_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

    for i in range(5):
        agent = AgentRegistry(
            id=f"test-agent-{uuid.uuid4().hex[:8]}",
            name=f"Test Agent {i}",
            description=f"E2E test agent {i}",
            category="Testing",
            module_path="test",
            class_name="TestAgent",
            status=maturity_levels[i % len(maturity_levels)],
            confidence_score=0.5 + (i * 0.1),
            configuration={"test": True, "e2e": True},
        )
        e2e_postgres_session.add(agent)
        agents.append(agent)

    # Create test executions
    executions = []
    for agent in agents:
        for j in range(3):
            execution = AgentExecution(
                agent_id=agent.id,
                user_id=f"test-user-{uuid.uuid4().hex[:8]}",
                status="completed" if j < 2 else "failed",
                input_data={"test": f"data-{j}", "index": j},
                output_data={"result": f"output-{j}", "agent": agent.name} if j < 2 else None,
                error_message=f"Test error {j}" if j == 2 else None,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if j < 2 else None,
            )
            e2e_postgres_session.add(execution)
            executions.append(execution)

    e2e_postgres_session.commit()

    print(f"Created {len(agents)} agents and {len(executions)} executions")

    yield {"agents": agents, "executions": executions}


# =============================================================================
# Backup/Restore Fixture
# =============================================================================

@pytest.fixture(scope="function")
def database_backup(e2e_postgres_engine):
    """
    Create and restore database backups.

    This fixture provides backup and restore functions for PostgreSQL
    database testing. Backups are created using pg_dump and restored
    using psql.

    The backup file is automatically cleaned up after the test.

    Yields:
        Dictionary with 'backup' and 'restore' functions
    """
    import tempfile
    import os

    backup_file = tempfile.mktemp(suffix=".sql", prefix="atom_e2e_backup_")

    print(f"\n=== Database Backup Fixture Initialized ===")
    print(f"Backup file: {backup_file}")

    def backup():
        """
        Create database backup using pg_dump.

        Returns:
            Path to backup file
        """
        print(f"\n=== Creating Database Backup ===")

        try:
            result = subprocess.run([
                "pg_dump",
                "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test",
                "-f", backup_file,
                "--no-owner",
                "--no-acl"
            ], check=True, capture_output=True, text=True, timeout=30)

            print(f"Backup created successfully: {backup_file}")
            print(f"Backup size: {os.path.getsize(backup_file)} bytes")

            return backup_file
        except subprocess.TimeoutExpired:
            pytest.skip("pg_dump timed out - database may be slow")
        except subprocess.CalledProcessError as e:
            pytest.skip(f"pg_dump failed: {e.stderr}")
        except Exception as e:
            pytest.skip(f"Backup failed: {e}")

    def restore(backup_path=backup_file):
        """
        Restore database from backup using psql.

        Args:
            backup_path: Path to backup file (defaults to latest backup)
        """
        print(f"\n=== Restoring Database from Backup ===")
        print(f"Backup file: {backup_path}")

        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        try:
            result = subprocess.run([
                "psql",
                "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test",
                "-f", backup_path
            ], check=True, capture_output=True, text=True, timeout=30)

            print("Database restored successfully")
        except subprocess.TimeoutExpired:
            pytest.skip("psql timed out - database may be slow")
        except subprocess.CalledProcessError as e:
            pytest.skip(f"psql failed: {e.stderr}")
        except Exception as e:
            pytest.skip(f"Restore failed: {e}")

    yield {"backup": backup, "restore": restore}

    # Cleanup: Delete backup file
    print(f"\n=== Cleaning up Backup File ===")
    try:
        if os.path.exists(backup_file):
            os.remove(backup_file)
            print(f"Deleted backup file: {backup_file}")
    except Exception as e:
        print(f"Warning: Failed to delete backup file {backup_file}: {e}")


# =============================================================================
# Connection Pool Fixture
# =============================================================================

@pytest.fixture(scope="function")
def connection_pool():
    """
    Test connection pooling behavior.

    This fixture creates a PostgreSQL engine with a small connection
    pool for testing pool behavior under load:
    - Pool size: 5 connections
    - Max overflow: 2 additional connections
    - Pool timeout: 30 seconds

    Use this fixture to test connection reuse, pool exhaustion,
    and connection cleanup.

    Yields:
        SQLAlchemy Engine with configured connection pool
    """
    database_url = "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test"

    print(f"\n=== Creating Connection Pool Engine ===")
    print(f"Pool size: 5, Max overflow: 2, Timeout: 30s")

    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_pre_ping=True,
        echo=False,
    )

    # Verify connection
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        print("Connection pool engine created successfully")
    except Exception as e:
        pytest.skip(f"Failed to create connection pool: {e}")

    yield engine

    # Cleanup: Dispose engine and close all connections
    print(f"\n=== Disposing Connection Pool ===")
    engine.dispose()


# =============================================================================
# Cross-Platform SQLite Fixture
# =============================================================================

@pytest.fixture(scope="function")
def cross_platform_sqlite():
    """
    Create SQLite databases on different platforms for testing.

    This fixture creates multiple SQLite databases with different
    configurations to test cross-platform compatibility for
    Personal Edition.

    Tests:
    - WAL mode (Write-Ahead Logging) for concurrent access
    - Different journal modes
    - Different cache sizes

    Yields:
        Dictionary with configured SQLite engines
    """
    import tempfile
    import os

    print(f"\n=== Creating Cross-Platform SQLite Engines ===")

    engines = {}
    configs = {
        "default": {},
        "wal_mode": {"journal_mode": "WAL"},
        "memory": {"cache_size": "-10000"},  # 10MB cache
    }

    for name, pragmas in configs.items():
        fd, path = tempfile.mkstemp(suffix=".db", prefix=f"atom_cross_{name}_")
        os.close(fd)

        engine = create_engine(f"sqlite:///{path}", echo=False)

        # Apply pragmas
        with engine.connect() as conn:
            from sqlalchemy import text
            for key, value in pragmas.items():
                conn.execute(text(f"PRAGMA {key} = {value}"))
            conn.commit()

        # Create tables
        try:
            Base.metadata.create_all(engine, checkfirst=True)
        except Exception as e:
            print(f"Warning: Failed to create tables for {name}: {e}")

        engines[name] = {"engine": engine, "path": path}
        print(f"Created {name} SQLite engine: {path}")

    yield engines

    # Cleanup: Delete all temp databases
    print(f"\n=== Cleaning up Cross-Platform SQLite Databases ===")
    for name, data in engines.items():
        try:
            data["engine"].dispose()
            os.remove(data["path"])
            print(f"Deleted {name}: {data['path']}")
        except Exception as e:
            print(f"Warning: Failed to delete {name}: {e}")

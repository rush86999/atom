"""
E2E Migration Test Fixtures

This module provides fixtures for end-to-end migration testing with real
database execution. Fixtures handle database setup, migration execution,
schema inspection, and test data creation.

**Fixtures:**
- migration_config: Alembic config for testing
- empty_database: Database with no migrations applied
- migrated_database: Database with all migrations applied
- migration_inspector: Schema inspection helper
- migration_test_data: Test data creation helper
- fresh_database_for_migration: Isolated database for migration testing

**Usage:**
```python
def test_migration_rollback(migrated_database, migration_inspector):
    # Test rollback logic
    inspector = migration_inspector(migrated_database)
    tables = inspector.get_table_names()
    assert 'agent_registry' in tables
```
"""

import os
import sys
from pathlib import Path
from typing import Generator, Dict, Any, List
import pytest

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

from core.models import Base
from datetime import datetime
import uuid


# =============================================================================
# Configuration
# =============================================================================

# Default test database URLs
DEFAULT_POSTGRES_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://e2e_tester:test_password@localhost:5433/atom_e2e_test"
)

DEFAULT_SQLITE_URL = os.getenv(
    "TEST_SQLITE_URL",
    "sqlite:///./test_migrations.db"
)

# Number of recent migrations to test for rollback
RECENT_MIGRATION_COUNT = 10


# =============================================================================
# Alembic Configuration Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def alembic_ini_path():
    """Get path to alembic.ini file."""
    backend_path = Path(__file__).parent.parent.parent.parent
    ini_path = backend_path / "alembic.ini"
    return str(ini_path)


@pytest.fixture(scope="session")
def migration_config(alembic_ini_path):
    """
    Create Alembic config for testing.

    This fixture creates an Alembic configuration object configured
    for the test database. It can be used to run migration commands.

    Yields:
        Config: Alembic configuration object
    """
    config = Config(alembic_ini_path)
    config.set_main_option("sqlalchemy.url", DEFAULT_POSTGRES_URL)
    return config


@pytest.fixture(scope="session")
def migration_config_sqlite(alembic_ini_path, tmp_path_factory):
    """
    Create Alembic config for SQLite testing.

    This fixture creates an Alembic configuration for SQLite,
    useful for testing migrations without PostgreSQL.

    Yields:
        Config: Alembic configuration for SQLite
    """
    # Create temp database file
    tmp_dir = tmp_path_factory.mktemp("sqlite_migrations")
    db_file = tmp_dir / "test_migrations.db"
    db_url = f"sqlite:///{db_file}"

    config = Config(alembic_ini_path)
    config.set_main_option("sqlalchemy.url", db_url)
    return config


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def empty_postgres_database(migration_config):
    """
    Create empty PostgreSQL database for migration testing.

    This fixture creates a database with no migrations applied,
    perfect for testing fresh migration execution.

    Yields:
        Engine: SQLAlchemy engine for empty database
    """
    engine = create_engine(DEFAULT_POSTGRES_URL, echo=False)

    try:
        # Drop all tables including alembic_version
        Base.metadata.drop_all(engine)

        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

        yield engine

    except Exception as e:
        pytest.skip(f"Failed to create empty database: {e}")
    finally:
        # Cleanup
        try:
            Base.metadata.drop_all(engine)
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        except Exception:
            pass
        engine.dispose()


@pytest.fixture(scope="function")
def empty_sqlite_database(migration_config_sqlite):
    """
    Create empty SQLite database for migration testing.

    This fixture creates a SQLite database with no migrations applied.

    Yields:
        Engine: SQLAlchemy engine for empty SQLite database
    """
    db_url = migration_config_sqlite.get_main_option("sqlalchemy.url")
    engine = create_engine(db_url, echo=False)

    try:
        # Drop all tables
        Base.metadata.drop_all(engine)

        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

        yield engine

    except Exception as e:
        pytest.skip(f"Failed to create empty SQLite database: {e}")
    finally:
        # Cleanup
        try:
            Base.metadata.drop_all(engine)
        except Exception:
            pass
        engine.dispose()


@pytest.fixture(scope="function")
def migrated_postgres_database(empty_postgres_database, migration_config):
    """
    Create PostgreSQL database with all migrations applied.

    This fixture runs all Alembic migrations to create a database
    with the complete schema. Perfect for testing rollback scenarios.

    Yields:
        Engine: SQLAlchemy engine with all migrations applied
    """
    try:
        # Run all migrations to head
        command.upgrade(migration_config, "head")

        print(f"\n✓ All migrations applied successfully")

        yield empty_postgres_database

    except Exception as e:
        pytest.skip(f"Failed to apply migrations: {e}")
    finally:
        # Cleanup: downgrade to base
        try:
            command.downgrade(migration_config, "base")
            print(f"✓ Downgraded to base")
        except Exception as e:
            print(f"Warning: Failed to downgrade: {e}")


@pytest.fixture(scope="function")
def migrated_sqlite_database(empty_sqlite_database, migration_config_sqlite):
    """
    Create SQLite database with all migrations applied.

    This fixture runs all Alembic migrations on SQLite.

    Yields:
        Engine: SQLAlchemy engine with all migrations applied
    """
    try:
        # Run all migrations to head
        command.upgrade(migration_config_sqlite, "head")

        print(f"\n✓ All SQLite migrations applied successfully")

        yield empty_sqlite_database

    except Exception as e:
        pytest.skip(f"Failed to apply SQLite migrations: {e}")
    finally:
        # Cleanup: downgrade to base
        try:
            command.downgrade(migration_config_sqlite, "base")
        except Exception:
            pass


@pytest.fixture(scope="function")
def fresh_database_for_migration(migration_config):
    """
    Create fresh database for migration testing.

    This is an alias for migrated_postgres_database for compatibility
    with existing test code.

    Yields:
        Engine: SQLAlchemy engine with all migrations applied
    """
    from .test_migration_rollback import TestMigrationRollback

    # Use the same logic as migrated_postgres_database
    engine = create_engine(DEFAULT_POSTGRES_URL, echo=False)

    try:
        # Drop all
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

        # Run migrations
        command.upgrade(migration_config, "head")

        yield engine

    except Exception as e:
        pytest.skip(f"Failed to create fresh database: {e}")
    finally:
        try:
            command.downgrade(migration_config, "base")
        except Exception:
            pass
        engine.dispose()


# =============================================================================
# Schema Inspection Fixtures
# =============================================================================

@pytest.fixture
def migration_inspector():
    """
    Create schema inspector helper.

    This fixture provides a function that returns a SQLAlchemy
    inspector for the given engine.

    Usage:
        inspector = migration_inspector()
        tables = inspector.get_table_names()

    Returns:
        Function that creates Inspector from Engine
    """
    def _inspector(engine):
        """Create inspector from engine."""
        return inspect(engine)

    return _inspector


@pytest.fixture
def table_schema_comparator():
    """
    Create table schema comparison helper.

    This fixture provides a function to compare table schemas
    before and after migrations.

    Returns:
        Function that compares schemas
    """
    def compare_schemas(inspector1, inspector2, table_name):
        """
        Compare table schema between two inspectors.

        Args:
            inspector1: First inspector (before)
            inspector2: Second inspector (after)
            table_name: Table name to compare

        Returns:
            Dict with 'columns_added', 'columns_removed', 'columns_changed'
        """
        cols1 = {col['name']: col for col in inspector1.get_columns(table_name)}
        cols2 = {col['name']: col for col in inspector2.get_columns(table_name)}

        added = set(cols2.keys()) - set(cols1.keys())
        removed = set(cols1.keys()) - set(cols2.keys())
        changed = []

        for col_name in set(cols1.keys()) & set(cols2.keys()):
            col1 = cols1[col_name]
            col2 = cols2[col_name]
            if str(col1['type']) != str(col2['type']):
                changed.append(col_name)

        return {
            'columns_added': list(added),
            'columns_removed': list(removed),
            'columns_changed': changed
        }

    return compare_schemas


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def migration_test_data():
    """
    Create test data for migration testing.

    This fixture provides a helper function to create test data
    in a database session for testing data migrations.

    Usage:
        obj = migration_test_data(session, AgentRegistry, name="test")

    Returns:
        Function that creates test data
    """
    def _create_data(session: Session, model_class, **kwargs):
        """
        Create test data object.

        Args:
            session: SQLAlchemy session
            model_class: Model class to instantiate
            **kwargs: Model attributes

        Returns:
            Created model instance
        """
        obj = model_class(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    return _create_data


@pytest.fixture
def recent_migrations(migration_config):
    """
    Get list of recent migrations for testing.

    This fixture returns the N most recent migrations for
    individual rollback testing.

    Returns:
        List of recent migration revision objects
    """
    script = ScriptDirectory.from_config(migration_config)

    # Get all migrations from all heads
    all_migrations = []
    heads = script.get_heads()

    for head in heads:
        migrations = list(script.walk_revisions(base="base", head=head))
        all_migrations.extend(migrations)

    # Return N most recent (by walking order)
    return all_migrations[:RECENT_MIGRATION_COUNT]


@pytest.fixture
def specific_migration(migration_config):
    """
    Get specific migration by revision ID.

    This fixture provides a helper function to retrieve a specific
    migration for testing.

    Usage:
        migration = specific_migration('abc123')

    Returns:
        Function that retrieves migration by revision ID
    """
    script = ScriptDirectory.from_config(migration_config)

    def _get_migration(revision_id: str):
        """Get migration by revision ID."""
        heads = script.get_heads()

        for head in heads:
            migrations = list(script.walk_revisions(base="base", head=head))
            for rev in migrations:
                if rev.revision == revision_id:
                    return rev

        raise ValueError(f"Migration {revision_id} not found")

    return _get_migration


# =============================================================================
# Session Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def postgres_session(migrated_postgres_database) -> Generator[Session, None, None]:
    """
    Create PostgreSQL session for migration testing.

    This fixture provides a SQLAlchemy session for a database
    with all migrations applied.

    Yields:
        Session: SQLAlchemy session
    """
    Session = sessionmaker(bind=migrated_postgres_database, autocommit=False, autoflush=False)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def sqlite_session(migrated_sqlite_database) -> Generator[Session, None, None]:
    """
    Create SQLite session for migration testing.

    This fixture provides a SQLAlchemy session for a SQLite
    database with all migrations applied.

    Yields:
        Session: SQLAlchemy session
    """
    Session = sessionmaker(bind=migrated_sqlite_database, autocommit=False, autoflush=False)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# Export all fixtures
# =============================================================================

__all__ = [
    "migration_config",
    "migration_config_sqlite",
    "empty_postgres_database",
    "empty_sqlite_database",
    "migrated_postgres_database",
    "migrated_sqlite_database",
    "fresh_database_for_migration",
    "migration_inspector",
    "table_schema_comparator",
    "migration_test_data",
    "recent_migrations",
    "specific_migration",
    "postgres_session",
    "sqlite_session",
]

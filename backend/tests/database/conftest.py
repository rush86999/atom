"""
Database-specific fixtures for model testing.

This conftest.py provides database session fixtures with proper transaction
rollback for test isolation. It's scoped to the database package to avoid
conflicts with the root conftest.py.

**Fixtures:**
- db_session: Database session with transaction rollback
- fresh_database: Completely fresh in-memory database
- model_inspector: SQLAlchemy inspector for schema validation
- constraint_checker: Helper for testing database constraints
- constraint_violation_checker: Enhanced constraint violation testing
- transaction_session: Session with explicit transaction control
- concurrent_sessions: Multiple sessions for concurrency testing
- constraint_test_data: Pre-configured test data

**Usage:**
These fixtures are automatically available to all tests in this package.
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from typing import Any, Dict, List

# Import models and database configuration
from core.models import Base
from core.database import SessionLocal


@pytest.fixture
def db_session():
    """
    Create a database session with transaction rollback for test isolation.

    This fixture provides a SQLAlchemy session that automatically rolls back
    all changes at the end of each test. This ensures tests don't affect each
    other and don't require manual cleanup.

    **Usage:**
    ```python
    def test_agent_creation(db_session: Session):
        agent = AgentFactory(_session=db_session, name="test")
        db_session.flush()
        assert agent.name == "test"
        # Automatically rolled back after test
    ```

    **Pattern:**
    - Use flush(), not commit() (commit would persist beyond rollback)
    - Use _session parameter with factories
    - All changes automatically rolled back after test

    **Yields:**
        Session: SQLAlchemy session with transaction rollback
    """
    db = SessionLocal()
    # Begin nested transaction for rollback
    db.begin_nested()

    try:
        yield db
        # Rollback all changes at end of test
        db.rollback()
    finally:
        db.close()


@pytest.fixture(scope="function")
def fresh_database():
    """
    Create a completely fresh in-memory database for isolated testing.

    This fixture creates a new in-memory SQLite database with all tables
    created from scratch. It's useful for tests that require complete
    isolation from any other test state.

    **Usage:**
    ```python
    def test_with_fresh_db(fresh_database: Session):
        # Completely isolated database
        user = UserFactory(_session=fresh_database)
        fresh_database.flush()
    ```

    **Note:** This is slower than db_session because it recreates all tables.
    Use db_session for most tests, only use fresh_database when you need
    complete isolation.

    **Yields:**
        Session: SQLAlchemy session for fresh in-memory database
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables to clean up
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def model_inspector(fresh_database: Session):
    """
    Provide SQLAlchemy inspector for schema validation queries.

    This fixture gives access to SQLAlchemy's inspector which can query
    database schema information like columns, indexes, foreign keys, etc.

    **Usage:**
    ```python
    def test_table_columns(model_inspector: Inspector):
        columns = model_inspector.get_columns('agents')
        column_names = [col['name'] for col in columns]
        assert 'id' in column_names
        assert 'name' in column_names
    ```

    **Returns:**
        Inspector: SQLAlchemy inspector for schema queries
    """
    # Get inspector from fresh database connection
    inspector = inspect(fresh_database.bind)
    return inspector


@pytest.fixture
def constraint_checker():
    """
    Helper function to test database constraints.

    This fixture provides a helper function that tests whether a given
    field value violates a database constraint (raises IntegrityError).

    **Usage:**
    ```python
    def test_email_unique(db_session: Session, constraint_checker):
        user1 = UserFactory(_session=db_session, email="test@example.com")
        db_session.flush()

        # Test that duplicate email raises IntegrityError
        constraint_checker(
            db_session,
            UserFactory,
            "email",
            "test@example.com"
        )
    ```

    **Parameters:**
        db_session: Database session
        model_factory: Factory function to create model instance
        field: Field name to test
        invalid_value: Invalid value to test

    **Raises:**
        AssertionError: If constraint is not violated ( IntegrityError not raised)
    """
    def check_constraint(
        db_session: Session,
        model_factory: Any,
        field: str,
        invalid_value: Any
    ) -> None:
        """
        Test that invalid value raises IntegrityError.

        Args:
            db_session: Database session
            model_factory: Factory callable (e.g., UserFactory)
            field: Field name to test
            invalid_value: Value that should violate constraint
        """
        from sqlalchemy.exc import IntegrityError

        try:
            # Try to create object with invalid value
            obj = model_factory(_session=db_session, **{field: invalid_value})
            db_session.flush()

            # If we get here, constraint was NOT violated
            raise AssertionError(
                f"Expected IntegrityError for field '{field}' with value "
                f"'{invalid_value}', but no error was raised. Constraint "
                f"may not be properly configured."
            )
        except IntegrityError:
            # Expected outcome - constraint was violated
            db_session.rollback()
            return

    return check_constraint


@pytest.fixture
def table_row_counter(fresh_database: Session):
    """
    Helper function to count rows in a table.

    **Usage:**
    ```python
    def test_agent_count(table_row_counter):
        count = table_row_counter(AgentRegistry)
        assert count == 0
    ```

    **Parameters:**
        model: SQLAlchemy model class

    **Returns:**
        int: Number of rows in the table
    """
    def count_rows(model: Any) -> int:
        """Count rows in model's table."""
        return fresh_database.query(model).count()

    return count_rows


@pytest.fixture
def foreign_key_checker(fresh_database: Session):
    """
    Helper to test foreign key constraints.

    **Usage:**
    ```python
    def test_execution_fk(foreign_key_checker):
        # Test that agent_id must reference valid agent
        foreign_key_checker(
            AgentExecution,
            "agent_id",
            "invalid-uuid-12345"
        )
    ```

    **Parameters:**
        model: SQLAlchemy model class
        field: Foreign key field name
        invalid_value: Invalid foreign key value

    **Raises:**
        AssertionError: If foreign key constraint not violated
    """
    def check_fk(model: Any, field: str, invalid_value: str) -> None:
        """Test foreign key constraint."""
        from sqlalchemy.exc import IntegrityError

        try:
            obj = model(**{field: invalid_value})
            fresh_database.add(obj)
            fresh_database.flush()

            raise AssertionError(
                f"Expected IntegrityError for foreign key field '{field}' "
                f"with invalid value '{invalid_value}', but no error was "
                f"raised. Foreign key constraint may not be configured."
            )
        except IntegrityError:
            fresh_database.rollback()
            return

    return check_fk


@pytest.fixture
def constraint_violation_checker():
    """
    Helper to test constraint violations with enhanced support.

    This fixture provides a helper function that tests constraint violations
    for different types (unique, foreign_key, not_null).

    **Usage:**
    ```python
    def test_email_unique(db_session: Session, constraint_violation_checker):
        user1 = UserFactory(_session=db_session, email="test@example.com")
        db_session.flush()

        # Test that duplicate email raises IntegrityError
        constraint_violation_checker(
            db_session,
            UserFactory,
            "email",
            "test@example.com",
            constraint_type="unique"
        )
    ```

    **Parameters:**
        db_session: Database session
        model_factory: Factory callable (e.g., UserFactory)
        field: Field name to test
        value: Value to test (duplicate or invalid)
        constraint_type: Type of constraint ("unique", "foreign_key", "not_null")

    **Raises:**
        AssertionError: If constraint is not violated (IntegrityError not raised)
    """
    from sqlalchemy.exc import IntegrityError

    def check_violation(
        db_session: Session,
        model_factory: Any,
        field: str,
        value: Any,
        constraint_type: str = "unique"
    ) -> None:
        """
        Test that constraint violation raises IntegrityError.

        Args:
            db_session: Database session
            model_factory: Factory callable
            field: Field name to test
            value: Value that should violate constraint
            constraint_type: Type of constraint (unique, foreign_key, not_null)
        """
        try:
            if constraint_type == "unique":
                # First insert should succeed
                obj1 = model_factory(_session=db_session, **{field: value})
                db_session.flush()

                # Duplicate should fail
                with pytest.raises(IntegrityError):
                    obj2 = model_factory(_session=db_session, **{field: value})
                    db_session.flush()

            elif constraint_type == "foreign_key":
                # Invalid FK should fail
                with pytest.raises(IntegrityError):
                    obj = model_factory(_session=db_session, **{field: value})
                    db_session.flush()

            elif constraint_type == "not_null":
                # NULL should fail
                with pytest.raises(Exception):  # May be IntegrityError or other
                    obj = model_factory(_session=db_session, **{field: None})
                    db_session.flush()

            db_session.rollback()

        except (AssertionError, IntegrityError):
            # Re-raise for test verification
            db_session.rollback()
            raise

    return check_violation


@pytest.fixture
def transaction_session():
    """
    Session with explicit transaction control.

    This fixture provides a database session where you have explicit control
    over transaction begin, commit, and rollback. Unlike db_session which
    auto-rolls back, this session requires manual transaction management.

    **Usage:**
    ```python
    def test_manual_transaction(transaction_session: Session):
        transaction = transaction_session.begin()
        try:
            agent = AgentFactory(_session=transaction_session, name="test")
            transaction_session.flush()
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
    ```

    **Note:** You must manually commit or rollback the transaction.

    **Yields:**
        Session: SQLAlchemy session with manual transaction control
    """
    db = SessionLocal()
    transaction = db.begin()

    try:
        yield db
        # Rollback if not explicitly committed/rolled back
        if transaction.is_active:
            transaction.rollback()
    finally:
        db.close()


@pytest.fixture
def concurrent_sessions():
    """
    Create multiple database sessions for concurrency testing.

    This fixture provides multiple independent database sessions that can
    be used to test concurrent access, race conditions, and isolation levels.

    **Usage:**
    ```python
    def test_concurrent_access(concurrent_sessions: List[Session]):
        session1, session2, session3 = concurrent_sessions

        # Use sessions concurrently (e.g., in threads)
        # Each session is independent
    ```

    **Yields:**
        List[Session]: List of 3 independent database sessions
    """
    sessions = [SessionLocal() for _ in range(3)]

    try:
        yield sessions
    finally:
        # Close all sessions
        for session in sessions:
            try:
                session.close()
            except Exception:
                pass


@pytest.fixture
def constraint_test_data(db_session):
    """
    Pre-configured test data for constraint testing.

    This fixture creates common reference data (users, agents, workspaces)
    that can be used in constraint tests. It flushes the data but doesn't
    commit, so it's rolled back automatically by db_session.

    **Usage:**
    ```python
    def test_fk_constraint(db_session: Session, constraint_test_data):
        data = constraint_test_data
        # Use pre-created user, agent, workspace
        execution = AgentExecutionFactory(
            _session=db_session,
            agent_id=data["agent"].id
        )
    ```

    **Returns:**
        dict: Dictionary with 'user', 'agent', 'workspace' keys
    """
    # Create reference data
    user = UserFactory(_session=db_session)
    agent = AgentFactory(_session=db_session, user_id=user.id)
    workspace = WorkspaceFactory(_session=db_session)

    # Flush to make visible in current session
    db_session.flush()

    return {
        "user": user,
        "agent": agent,
        "workspace": workspace
    }


# Export all fixtures for this package
__all__ = [
    "db_session",
    "fresh_database",
    "model_inspector",
    "constraint_checker",
    "constraint_violation_checker",
    "transaction_session",
    "concurrent_sessions",
    "constraint_test_data",
    "table_row_counter",
    "foreign_key_checker",
]

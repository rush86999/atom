"""
Database Session Manager for Atom Platform

Provides centralized database session management with automatic
commit/rollback handling and connection pooling.
"""

import contextlib
import logging
from typing import Generator, Optional
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from core.database import SessionLocal, engine

logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    """
    Centralized database session management with automatic lifecycle handling.

    Provides context managers and utilities for safe database operations.
    Ensures proper commit/rollback behavior and connection cleanup.

    Example:
        # Context manager (recommended)
        with DatabaseSessionManager.get_session() as db:
            agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
            agent.name = "Updated Name"
            # Automatic commit on success, rollback on exception

        # With manual error handling
        with DatabaseSessionManager.get_session() as db:
            try:
                agent = create_agent(db, agent_data)
                db.commit()
                return agent
            except Exception as e:
                db.rollback()
                raise

        # With explicit transaction control
        with DatabaseSessionManager.managed_transaction() as db:
            agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
            agent.execute()
            # Explicit commit/rollback required
    """

    @staticmethod
    @contextlib.contextmanager
    def get_session(
        autocommit: bool = True,
        autoflush: bool = True,
        expire_on_commit: bool = False
    ) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic commit/rollback.

        Args:
            autocommit: Automatically commit on successful block completion
            autoflush: Automatically flush before queries
            expire_on_commit: Expire instances after commit (detaches from session)

        Yields:
            Session: SQLAlchemy database session

        Example:
            with DatabaseSessionManager.get_session() as db:
                agent = db.query(AgentRegistry).first()
                agent.name = "Updated"
                # Commits automatically on success, rolls back on exception
        """
        db = SessionLocal()
        db.autoflush = autoflush
        db.expire_on_commit = expire_on_commit

        try:
            yield db
            if autocommit:
                db.commit()
                logger.debug("Database transaction committed successfully")
        except Exception as e:
            db.rollback()
            logger.error(f"Database transaction rolled back due to error: {str(e)}")
            raise
        finally:
            db.close()

    @staticmethod
    @contextlib.contextmanager
    def managed_transaction() -> Generator[Session, None, None]:
        """
        Context manager for transactions requiring manual commit/rollback control.

        Use this when you need explicit control over when commits happen,
        typically for complex multi-step operations.

        Args:
            None

        Yields:
            Session: SQLAlchemy database session

        Example:
            with DatabaseSessionManager.managed_transaction() as db:
                agent = db.query(AgentRegistry).first()
                agent.update_step1()
                db.flush()  # Flush but don't commit yet

                agent.update_step2()
                db.flush()

                # Only commit if all steps succeed
                db.commit()
        """
        db = SessionLocal()

        try:
            yield db
            # No automatic commit - caller must call db.commit() explicitly
        except Exception as e:
            db.rollback()
            logger.error(f"Transaction rolled back: {str(e)}")
            raise
        finally:
            db.close()

    @staticmethod
    @contextlib.contextmanager
    def nested_transaction(db: Session) -> Generator[Session, None, None]:
        """
        Create a nested transaction (savepoint) within an existing session.

        Useful for operations that need to be atomic within a larger transaction.

        Args:
            db: Existing database session

        Yields:
            Session: Same session with nested transaction active

        Example:
            with DatabaseSessionManager.get_session() as db:
                # Outer transaction
                agent = db.query(AgentRegistry).first()

                with DatabaseSessionManager.nested_transaction(db):
                    # Inner transaction (savepoint)
                    # Can be rolled back independently
                    agent.risky_operation()
                # If inner transaction fails, outer continues
        """
        try:
            savepoint = db.begin_nested()
            yield db
            savepoint.commit()
        except Exception as e:
            savepoint.rollback()
            logger.error(f"Nested transaction rolled back: {str(e)}")
            raise

    @staticmethod
    def execute_in_transaction(
        operation,
        *args,
        **kwargs
    ):
        """
        Execute a database operation within a transaction context.

        Convenience function for simple operations.

        Args:
            operation: Function to execute (receives db session as first arg)
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Result of the operation

        Example:
            def get_agent_name(db, agent_id):
                agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
                return agent.name if agent else None

            name = DatabaseSessionManager.execute_in_transaction(
                get_agent_name, "agent-123"
            )
        """
        with DatabaseSessionManager.get_session() as db:
            return operation(db, *args, **kwargs)

    @staticmethod
    def bulk_operation(
        operation: str,
        items: list,
        db: Session,
        batch_size: int = 100
    ) -> dict:
        """
        Execute bulk database operations with batching.

        Args:
            operation: Type of operation ("insert", "update", "delete")
            items: List of items to process
            db: Database session
            batch_size: Number of items per batch

        Returns:
            Dict with operation statistics

        Example:
            with DatabaseSessionManager.get_session() as db:
                stats = DatabaseSessionManager.bulk_operation(
                    "insert",
                    new_agents,
                    db,
                    batch_size=500
                )
                print(f"Inserted {stats['total_success']} agents")
        """
        stats = {
            "total_attempted": len(items),
            "total_success": 0,
            "total_failed": 0,
            "batches": (len(items) + batch_size - 1) // batch_size
        }

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            try:
                if operation == "insert":
                    db.add_all(batch)
                elif operation == "delete":
                    for item in batch:
                        db.delete(item)
                elif operation == "update":
                    for item in batch:
                        db.merge(item)

                db.flush()
                stats["total_success"] += len(batch)

            except SQLAlchemyError as e:
                logger.error(f"Bulk {operation} failed for batch {i // batch_size}: {str(e)}")
                stats["total_failed"] += len(batch)
                db.rollback()

        if stats["total_success"] > 0:
            db.commit()

        return stats


# Convenience functions for common patterns

@contextlib.contextmanager
def get_db_session(
    autocommit: bool = True,
    autoflush: bool = True
) -> Generator[Session, None, None]:
    """
    Convenience function for database session context manager.

    Args:
        autocommit: Automatically commit on success
        autoflush: Automatically flush before queries

    Yields:
        Session: Database session

    Example:
        with get_db_session() as db:
            agent = db.query(AgentRegistry).first()
            agent.name = "Updated"
    """
    with DatabaseSessionManager.get_session(autocommit, autoflush) as db:
        yield db


def with_db_session(operation: callable, *args, **kwargs):
    """
    Execute a function with a database session.

    Args:
        operation: Function that takes db as first argument
        *args: Additional positional arguments
        **kwargs: Additional keyword arguments

    Returns:
        Result of the operation

    Example:
        def update_agent(db, agent_id, name):
            agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
            agent.name = name
            return agent

        agent = with_db_session(update_agent, "agent-123", "New Name")
    """
    with DatabaseSessionManager.get_session() as db:
        return operation(db, *args, **kwargs)

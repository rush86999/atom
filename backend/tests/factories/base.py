"""
Test data factories for Atom platform.

Uses factory_boy for dynamic, isolated test data generation.
All factories inherit from BaseFactory which manages SQLAlchemy sessions.
"""

import os
import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.orm import Session

# Import at runtime to avoid import errors
def get_session():
    from core.database import SessionLocal
    return SessionLocal()


class BaseFactory(SQLAlchemyModelFactory):
    """
    Base factory for all test data factories.

    Uses a SQLAlchemy session for persistence.
    Each test gets a fresh session via dependency injection.
    """

    class Meta:
        abstract = True  # Don't create a model for BaseFactory
        sqlalchemy_session = None  # Set dynamically
        sqlalchemy_session_persistence = "commit"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle session injection with enforcement.

        Args:
            model_class: SQLAlchemy model class
            _session: Database session (REQUIRED in test environment)

        Raises:
            RuntimeError: If _session not provided in test environment

        In test environment (detected by PYTEST_XDIST_WORKER_ID), the _session
        parameter is MANDATORY to ensure proper test isolation.
        """
        session = kwargs.pop('_session', None)
        is_test_env = os.environ.get('PYTEST_XDIST_WORKER_ID') is not None

        if is_test_env and session is None:
            raise RuntimeError(
                "{0}.create() requires _session parameter in test environment. "
                "Usage: {0}.create(_session=db_session, ...)".format(cls.__name__)
            )

        if session:
            # Use provided session (from test fixture)
            cls._meta.sqlalchemy_session = session
            # Don't commit when using test session - let rollback handle it
            cls._meta.sqlalchemy_session_persistence = "flush"
        else:
            # Use default session
            if cls._meta.sqlalchemy_session is None:
                cls._meta.sqlalchemy_session = get_session()
            cls._meta.sqlalchemy_session_persistence = "commit"
        return super()._create(model_class, *args, **kwargs)

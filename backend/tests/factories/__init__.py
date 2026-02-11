"""
Test data factories for Atom platform.

Uses factory_boy for dynamic, isolated test data generation.
All factories inherit from BaseFactory which manages SQLAlchemy sessions.
"""

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
        """Override to handle session injection."""
        session = kwargs.pop('_session', None)
        if session:
            # Use provided session (from test fixture)
            cls._meta.sqlalchemy_session = session
        else:
            # Use default session
            if cls._meta.sqlalchemy_session is None:
                cls._meta.sqlalchemy_session = get_session()
        return super()._create(model_class, *args, **kwargs)

"""
Budget test configuration and fixtures.

This file provides fixtures specific to budget/cost attribution tests.
Uses isolated Base to avoid foreign key dependency issues.
"""

import os
import sys
import tempfile
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

import pytest
import uuid
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Text, Boolean, func
from sqlalchemy.orm import declarative_base, Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# Create isolated Base for budget tests (avoid foreign key dependencies)
BudgetBase = declarative_base()


class Transaction(BudgetBase):
    """Simplified Transaction model for budget tests."""
    __tablename__ = "accounting_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, nullable=False)
    external_id = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(precision=19, scale=4), nullable=True)
    metadata_json = Column(Text, nullable=True)
    is_intercompany = Column(Boolean, default=False)
    counterparty_workspace_id = Column(String, nullable=True)
    category = Column(String(50), nullable=False, index=True, default='other')
    project_id = Column(String, nullable=True)
    milestone_id = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# Import the real Transaction model into the accounting module namespace
# so CostAttributionService can find it
import sys
import accounting.models
accounting.models.Transaction = Transaction


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh in-memory database for each budget test.

    This ensures complete isolation between test runs.
    """
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create all tables (no foreign key issues with isolated Base)
    BudgetBase.metadata.create_all(engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except:
            pass

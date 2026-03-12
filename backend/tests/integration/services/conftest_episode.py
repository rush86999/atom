"""
Episode service test fixtures with accounting module workaround.

Avoids SQLAlchemy metadata conflicts by preventing accounting.models import.
Phase 165 known issue: Duplicate Transaction model in core/models.py and accounting/models.py
"""

import os
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import pool
import tempfile
from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# CRITICAL WORKAROUND: Prevent accounting.models import before any model imports
# This prevents "Table 'accounting_transactions' is already defined" error
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Create a mock accounting module BEFORE any imports
class MockAccount:
    pass

class MockTransaction:
    pass

class MockJournalEntry:
    pass

class MockEntity:
    pass

class MockInvoice:
    pass

mock_accounting = ModuleType('accounting')
mock_accounting.models = MagicMock()
mock_accounting.models.Account = MockAccount
mock_accounting.models.Transaction = MockTransaction
mock_accounting.models.JournalEntry = MockJournalEntry
mock_accounting.models.Entity = MockEntity
mock_accounting.models.Invoice = MockInvoice
mock_accounting.models.InvoiceStatus = MagicMock()
mock_accounting.models.EntityType = MagicMock()
mock_accounting.models.EntryType = MagicMock()

sys.modules['accounting'] = mock_accounting
sys.modules['accounting.models'] = mock_accounting.models

# Add parent directory to path for imports
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# NOW safe to import models
from core.database import Base
from core.episode_segmentation_service import EpisodeSegmentationService, EpisodeBoundaryDetector
from core.models import (
    AgentEpisode,
    EpisodeSegment,
    ChatSession,
    ChatMessage,
    CanvasAudit,
    AgentFeedback,
    AgentRegistry,
    AgentExecution,
    User,
)

Episode = AgentEpisode


@pytest.fixture(scope="function")
def db_session():
    """
    Create fresh database session for episode tests.
    """
    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Use pooled connections with check_same_thread=False for SQLite
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
        echo=False,
        pool_pre_ping=True
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create ONLY the tables we need for episode testing
    tables_to_create = [
        'users',
        'agent_registry',
        'agent_feedback',
        'chat_sessions',
        'chat_messages',
        'agent_executions',
        'canvas_audit',
        'agent_episodes',
        'episode_segments',
        'episode_access_logs',
    ]

    for table_name in tables_to_create:
        if table_name in Base.metadata.tables:
            try:
                Base.metadata.tables[table_name].create(engine, checkfirst=True)
            except Exception as e:
                print(f"Warning: Could not create table {table_name}: {e}")

    # Create session with expire_on_commit=False
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass


@pytest.fixture(scope="function")
def mock_lancedb_embeddings():
    """
    Mock LanceDB embedding generation with semantic similarity vectors.

    Returns vectors that produce predictable similarity scores:
    - Same topic: [0.9, 0.1, 0.0] (high similarity)
    - Different topic: [0.1, 0.9, 0.0] (low similarity <0.75)
    """
    mock_db = Mock()
    mock_db.embed_text = Mock(side_effect=lambda text: (
        [0.9, 0.1, 0.0] if "python" in text.lower() or "web" in text.lower()
        else [0.1, 0.9, 0.0]  # Cooking/topic change
    ))
    mock_db.search = Mock(return_value=[])
    mock_db.db = Mock()
    mock_db.table_names = Mock(return_value=[])
    return mock_db


@pytest.fixture(scope="function")
def segmentation_service_mocked(db_session, mock_lancedb_embeddings):
    """
    Create EpisodeSegmentationService instance with mocked LanceDB.
    """
    # Mock BYOK handler and CanvasSummaryService
    with patch('core.episode_segmentation_service.BYOKHandler') as mock_byok:
        with patch('core.episode_segmentation_service.CanvasSummaryService') as mock_canvas:
            with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb_embeddings):
                service = EpisodeSegmentationService(db_session)
                service.lancedb = mock_lancedb_embeddings
                yield service
